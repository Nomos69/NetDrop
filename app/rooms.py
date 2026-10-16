"""In-memory rooms and browser sessions. Restarting the host resets access."""

import hashlib
import secrets
import time

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api")
rooms = {}
sessions = {}
attempts = {}
COOKIE = "netdrop_session"
SESSION_SECONDS = 12 * 60 * 60


class RoomInput(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    pin: str = Field(pattern=r"^[0-9]{6,12}$")


class JoinInput(BaseModel):
    pin: str = Field(pattern=r"^[0-9]{6,12}$")


async def browser_write(request: Request):
    # A custom header prevents other websites submitting cookie-authenticated forms.
    if request.headers.get("x-netdrop") != "1":
        raise HTTPException(403, "Use the NetDrop interface for this request.")


def pin_hash(pin, salt):
    return hashlib.scrypt(pin.encode(), salt=salt, n=16384, r=8, p=1)


def session_for(request):
    now = time.time()
    for token in list(sessions):
        if sessions[token]["expires"] <= now:
            del sessions[token]
    return sessions.get(request.cookies.get(COOKIE))


async def authorize(room_id: str, request: Request):
    session = session_for(request)
    if not session or room_id not in session["rooms"]:
        raise HTTPException(403, "Join this room first.")
    room = rooms.get(room_id)
    if room is None:
        raise HTTPException(404, "Room no longer exists.")
    return room


def grant(room_id, request, response):
    session = session_for(request)
    token = request.cookies.get(COOKIE)
    if session is None:
        if len(sessions) >= 1000:
            raise HTTPException(503, "Too many active sessions. Try again later.")
        token = secrets.token_urlsafe(32)
        session = {"rooms": set(), "expires": time.time() + SESSION_SECONDS}
        sessions[token] = session
    session["rooms"].add(room_id)
    response.set_cookie(COOKIE, token, httponly=True, samesite="strict",
                        secure=request.url.scheme == "https", max_age=SESSION_SECONDS)


def public_room(room):
    return {"id": room["id"], "name": room["name"]}


@router.post("/rooms", status_code=201, dependencies=[Depends(browser_write)])
async def create_room(body: RoomInput, request: Request, response: Response):
    name = body.name.strip()
    if not name:
        raise HTTPException(422, "Enter a room name.")
    if len(rooms) >= 100:
        raise HTTPException(503, "Room limit reached. Restart the host to reset rooms.")
    room_id = secrets.token_hex(6)
    salt = secrets.token_bytes(16)
    room = {"id": room_id, "name": name, "salt": salt,
            "pin_hash": pin_hash(body.pin, salt), "items": {}}
    grant(room_id, request, response)
    rooms[room_id] = room
    return public_room(room)


@router.post("/rooms/{room_id}/join", dependencies=[Depends(browser_write)])
async def join_room(room_id: str, body: JoinInput, request: Request, response: Response):
    now = time.monotonic()
    for key in list(attempts):
        if attempts[key]["until"] <= now:
            del attempts[key]
    key = request.client.host if request.client else "unknown"
    if key not in attempts:
        if len(attempts) >= 1000:
            raise HTTPException(429, "Try again in a minute.")
        attempts[key] = {"count": 0, "until": now + 60}
    attempt = attempts[key]
    if attempt["count"] >= 5:
        raise HTTPException(429, "Too many join attempts. Try again in a minute.", headers={"Retry-After": "60"})
    attempt["count"] += 1
    room = rooms.get(room_id)
    if room is None or not secrets.compare_digest(pin_hash(body.pin, room["salt"]), room["pin_hash"]):
        raise HTTPException(403, "Room ID or PIN is incorrect.")
    grant(room_id, request, response)
    return public_room(room)


@router.get("/rooms/{room_id}")
async def get_room(room=Depends(authorize)):
    return public_room(room)


@router.post("/rooms/{room_id}/leave", dependencies=[Depends(browser_write)])
async def leave_room(room_id: str, request: Request, room=Depends(authorize)):
    session_for(request)["rooms"].discard(room_id)
    from app.realtime import publish
    publish(room_id)
    return {"message": "Left room."}
