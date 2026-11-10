"""Owner-requested invitations using Brevo's transactional HTTPS API."""

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
    pin: str = Field(pattern=r"^[0-9]{6,12}$")


def enabled():
    return bool(config.BREVO_API_KEY and config.BREVO_SENDER_EMAIL)


async def send_email(payload, event_id):
    """Retry explicit rejection only; a timeout may already have sent the email."""
    async with httpx.AsyncClient(timeout=5.0) as client:
        for attempt in range(1, 4):
            try:
                response = await client.post(ENDPOINT, headers={
                    "api-key": config.BREVO_API_KEY, "accept": "application/json",
                }, json=payload)
            except httpx.RequestError:
                logger.warning("email event=%s attempt=%s state=unknown", event_id, attempt)
                raise HTTPException(502, "Email delivery could not be confirmed. Check the recipient inbox before trying again.")
            if response.status_code == 201:
                try:
                    message_id = response.json().get("messageId")
                except (ValueError, AttributeError):
                    message_id = None
                if not isinstance(message_id, str) or not message_id:
                    raise HTTPException(502, "Email acceptance could not be confirmed. Check the recipient inbox before trying again.")
                logger.info("email event=%s attempt=%s state=accepted", event_id, attempt)
                return {"status": "accepted", "message": "Invitation sent. Ask the recipient to check their inbox or spam folder."}
            logger.warning("email event=%s attempt=%s state=rejected http=%s", event_id, attempt, response.status_code)
            if response.status_code == 429 and attempt < 3:
                try:
                    delay = max(1, int(response.headers.get("retry-after", "1")))
                except ValueError:
                    delay = 1
                if delay <= 2:
                    await asyncio.sleep(delay)
                    continue
            # Avoid retrying server errors: they can have an ambiguous send result.
            raise HTTPException(503, "Email service is unavailable or rejected the invitation. File sharing still works; ask the host to check Brevo settings and quota.")


@router.post("/rooms/{room_id}/email-invitation", dependencies=[Depends(rooms.browser_write)])
async def email_invitation(body: Invitation, request: Request, room=Depends(rooms.owner_only)):
    if not enabled():
        raise HTTPException(503, "Email is not configured. The host must set the Brevo API key and verified sender.")
    # Limit across all rooms owned by this browser session, including bad PINs.
    session = rooms.session_for(request)
    now = time.monotonic()
    history = [stamp for stamp in session.get("email_attempts", []) if now - stamp < 3600]
    session["email_attempts"] = history
    if len(history) >= 10 or (history and now - history[-1] < 30):
        raise HTTPException(429, "Please wait before sending another invitation (30 seconds between sends, 10 per hour).")
    history.append(now)
    if not secrets.compare_digest(rooms.pin_hash(body.pin, room["salt"]), room["pin_hash"]):
        raise HTTPException(403, "The room PIN is incorrect.")
    mode = config.sharing_mode(request)
    origin = config.ONLINE_URL if mode == "online" else config.LOCAL_URL
    if not origin:
        raise HTTPException(503, "The host must configure the public HTTPS or LAN address before emailing invitations.")
    # Hash the destination for short-lived duplicate suppression; never log addresses/PINs.
    fingerprint = hashlib.sha256(body.email.lower().encode()).hexdigest()
    sent = room.setdefault("email_invitations", {})
    for key in list(sent):
        if now - sent[key] >= 300:
            del sent[key]
    if fingerprint in sent:
        raise HTTPException(409, "An invitation was already attempted for this address. Check the inbox or wait five minutes.")
    sent[fingerprint] = now
    link = origin + "/#room=" + room["id"]
    network = "Join from the same Wi-Fi or LAN as the host." if mode == "local" else "Internet access is required."
    text = (f'You are invited to NetDrop room: {room["name"]}\n'
            f'Room ID: {room["id"]}\nPIN: {body.pin}\nJoin: {link}\n\n'
            f'{network}\nThe room is temporary and may close when the host restarts. '
            'Keep this invitation private. If you were not expecting it, ignore this email.')
    event_id = secrets.token_hex(12)
    return await send_email({
        "sender": {"email": config.BREVO_SENDER_EMAIL, "name": config.BREVO_SENDER_NAME},
        "to": [{"email": body.email}], "subject": "Your NetDrop room invitation",
        "textContent": text, "htmlContent": "<html><body><pre>" + escape(text) + "</pre></body></html>",
        "tags": ["netdrop-invitation"],
    }, event_id)
