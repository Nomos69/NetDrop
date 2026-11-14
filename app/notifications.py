"""Optional Brevo email invitations and upload alerts; delivery never blocks LAN sharing."""

import asyncio
import hashlib
import logging
import secrets
import time
from html import escape

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app import config, rooms

router = APIRouter(prefix="/api")
logger = logging.getLogger(__name__)
ENDPOINT = "https://api.brevo.com/v3/smtp/email"


class Invitation(BaseModel):
    email: str = Field(max_length=254, pattern=r"^[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+$")


class Subscription(BaseModel):
    email: str = Field(max_length=254, pattern=r"^[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+$")
    enabled: bool = True


class InvitationToken(BaseModel):
    token: str = Field(min_length=20, max_length=200)


def enabled():
    return bool(config.BREVO_API_KEY and config.BREVO_SENDER_EMAIL)


def origin_for(request):
    return config.ONLINE_URL if config.sharing_mode(request) == "online" else config.LOCAL_URL


def fingerprint(email):
    return hashlib.sha256(email.lower().encode()).hexdigest()


async def send_email(payload, event_id):
    """Return provider acceptance. A timeout is deliberately not retried."""
    async with httpx.AsyncClient(timeout=5.0) as client:
        for attempt in range(1, 4):
            try:
                response = await client.post(ENDPOINT, headers={"api-key": config.BREVO_API_KEY,
                                                                 "accept": "application/json"}, json=payload)
            except httpx.RequestError:
                logger.warning("email event=%s attempt=%s state=unknown", event_id, attempt)
                return False
            if response.status_code == 201:
                try:
                    accepted = isinstance(response.json().get("messageId"), str)
                except (ValueError, AttributeError):
                    accepted = False
                logger.info("email event=%s attempt=%s state=%s", event_id, attempt,
                            "accepted" if accepted else "invalid-response")
                return accepted
            if response.status_code == 429 and attempt < 3:
                try:
                    delay = max(1, int(response.headers.get("retry-after", "1")))
                except ValueError:
                    delay = 1
                if delay <= 2:
                    await asyncio.sleep(delay)
                    continue
            logger.warning("email event=%s attempt=%s state=rejected http=%s", event_id, attempt, response.status_code)
            return False
    return False


def queue_upload_alerts(room, item):
    """Fire-and-forget after local commit; failure never changes upload success."""
    if not enabled() or not room.get("subscriptions"):
        return
    for subscription in room["subscriptions"].values():
        if subscription["enabled"]:
            asyncio.create_task(send_upload_alert(room, item, subscription["email"]))


async def send_upload_alert(room, item, email):
    if room.get("closed") or item.get("expires_at", float("inf")) <= time.time():
        return
    text = (f'A new file is available in NetDrop room: {room["name"]}.\n'
            'Open NetDrop and enter the room details you received separately. '
            'This alert contains no room PIN, file name, or file contents.')
    payload = {"sender": {"email": config.BREVO_SENDER_EMAIL, "name": config.BREVO_SENDER_NAME},
               "to": [{"email": email}], "subject": "New NetDrop upload available",
               "textContent": text, "htmlContent": "<html><body><pre>" + escape(text) + "</pre></body></html>",
               "tags": ["netdrop-upload-alert"]}
    await send_email(payload, secrets.token_hex(12))


@router.post("/rooms/{room_id}/subscriptions", dependencies=[Depends(rooms.browser_write)])
async def subscription(body: Subscription, room=Depends(rooms.authorize)):
    subscriptions = room.setdefault("subscriptions", {})
    key = fingerprint(body.email)
    if body.enabled:
        subscriptions[key] = {"email": body.email.lower(), "enabled": True}
        return {"enabled": True, "message": "Upload alerts enabled for this email address."}
    subscriptions.pop(key, None)
    return {"enabled": False, "message": "Upload alerts disabled for this email address."}


@router.post("/rooms/{room_id}/email-invitation", dependencies=[Depends(rooms.browser_write)])
async def email_invitation(body: Invitation, request: Request, room=Depends(rooms.owner_only)):
    if not enabled():
        raise HTTPException(503, "Email is not configured. The host must set the Brevo API key and verified sender.")
    origin = origin_for(request)
    if not origin:
        raise HTTPException(503, "The host must configure the public HTTPS or LAN address before emailing invitations.")
    session = rooms.session_for(request)
    now = time.monotonic()
    history = [stamp for stamp in session.get("email_attempts", []) if now - stamp < 3600]
    session["email_attempts"] = history
    if len(history) >= 10 or (history and now - history[-1] < 30):
        raise HTTPException(429, "Please wait before sending another invitation (30 seconds between sends, 10 per hour).")
    history.append(now)
    sent = room.setdefault("email_invitations", {})
    key = fingerprint(body.email)
    if key in sent and now - sent[key]["created"] < 300:
        raise HTTPException(409, "An invitation was already attempted for this address. Check the inbox or wait five minutes.")
    token = secrets.token_urlsafe(24)
    sent[key] = {"created": now, "token_hash": hashlib.sha256(token.encode()).hexdigest(),
                 "expires_at": time.time() + config.INVITATION_TTL_SECONDS}
    link = f"{origin}/#room={room['id']}&invite={token}"
    text = (f'You are invited to NetDrop room: {room["name"]}\nJoin: {link}\n\n'
            'This invitation expires. It does not grant room access: ask the owner for the PIN separately. '
            'For a local room, join the same Wi-Fi or LAN as the host.')
    accepted = await send_email({"sender": {"email": config.BREVO_SENDER_EMAIL, "name": config.BREVO_SENDER_NAME},
                                 "to": [{"email": body.email}], "subject": "Your NetDrop room invitation",
                                 "textContent": text, "htmlContent": "<html><body><pre>" + escape(text) + "</pre></body></html>",
                                 "tags": ["netdrop-invitation"]}, secrets.token_hex(12))
    if not accepted:
        sent.pop(key, None)
        raise HTTPException(503, "Email service did not accept the invitation. File sharing still works.")
    return {"status": "accepted", "message": "Invitation sent. Ask the recipient to check their inbox or spam folder."}


@router.post("/rooms/{room_id}/validate-invitation", dependencies=[Depends(rooms.browser_write)])
async def validate_invitation(room_id: str, body: InvitationToken):
    room = rooms.rooms.get(room_id)
    if not room or room.get("closed") or room["expires_at"] <= time.time():
        raise HTTPException(404, "This room is no longer available.")
    candidate = hashlib.sha256(body.token.encode()).hexdigest()
    for record in room.get("email_invitations", {}).values():
        if record["expires_at"] > time.time() and secrets.compare_digest(record["token_hash"], candidate):
            return {"valid": True}
    raise HTTPException(403, "This invitation is invalid or has expired.")
