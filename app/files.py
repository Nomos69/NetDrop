"""Room-scoped file, text, and link sharing."""

import asyncio
import logging
import os
import re
import secrets
import time
from datetime import datetime, timezone
from urllib.parse import unquote, urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from app import config
from app.rooms import authorize, browser_write, rooms
from app.realtime import publish

router = APIRouter(prefix="/api/rooms/{room_id}")
logger = logging.getLogger(__name__)
pending_uploads = set()


class ContentInput(BaseModel):
    kind: str = Field(pattern=r"^(text|link)$")
    content: str = Field(min_length=1, max_length=10000)

def public_item(item):
    return {key: value for key, value in item.items() if key != "path" and not key.startswith("_")}


def new_item(kind):
    return {"id": secrets.token_hex(16), "kind": kind,
            "created_at": datetime.now(timezone.utc).isoformat()}


def check_capacity(room):
    cleanup_room(room)
    if sum(not expired(item) for item in room["items"].values()) >= 500:
        raise HTTPException(409, "This room has reached its content limit.")


@router.get("/items")
async def list_items(room=Depends(authorize)):
    cleanup_room(room)
    return {"items": [public_item(item) for item in reversed(list(room["items"].values())) if not expired(item)],
            "max_upload_bytes": config.MAX_UPLOAD_BYTES, "ttl_seconds": config.FILE_TTL_SECONDS}


@router.post("/items", status_code=201, dependencies=[Depends(browser_write)])
async def share_content(body: ContentInput, room=Depends(authorize)):
    check_capacity(room)
    content = body.content.strip()
    if not content:
        raise HTTPException(422, "Enter text or a link.")
    if body.kind == "link":
        try:
            url = urlsplit(content)
            valid = url.scheme in ("http", "https") and bool(url.hostname) and not any(c.isspace() for c in content)
        except ValueError:
            valid = False
        if not valid:
            raise HTTPException(422, "Links must be valid http:// or https:// addresses.")
    item = new_item(body.kind)
    item["content"] = content
    item["expires_at"] = now() + config.FILE_TTL_SECONDS
    room["items"][item["id"]] = item
    publish(room["id"])
    return public_item(item)


@router.post("/files", status_code=201, dependencies=[Depends(browser_write)])
async def upload(request: Request, room=Depends(authorize)):
    check_capacity(room)
    name = unquote(request.headers.get("x-filename", "")).replace("\\", "/").split("/")[-1]
    if not name or name in (".", "..") or len(name) > 255 or any(ord(c) < 32 or ord(c) == 127 for c in name):
        raise HTTPException(422, "Provide a valid filename.")
    length = request.headers.get("content-length")
    if length:
        try:
            size = int(length)
        except ValueError:
            raise HTTPException(400, "Invalid content length.")
        if size < 0:
            raise HTTPException(400, "Invalid content length.")
        if size > config.MAX_UPLOAD_BYTES:
            raise HTTPException(413, "File exceeds the upload limit.")
    item = new_item("file")
    path = config.UPLOAD_DIR / item["id"]
    size = 0
    completed = False
    pending_uploads.add(path)
    try:
        with path.open("xb") as output:
            async for chunk in request.stream():
                size += len(chunk)
                if size > config.MAX_UPLOAD_BYTES:
                    raise HTTPException(413, "File exceeds the upload limit.")
                output.write(chunk)
        check_capacity(room)
        # Lifetime begins only after the upload has been fully saved.
        saved_at = now()
        os.utime(path, (saved_at, saved_at))
        item.update(name=name, size=size, path=path,
                    created_at=datetime.fromtimestamp(saved_at, timezone.utc).isoformat(),
                    expires_at=saved_at + config.FILE_TTL_SECONDS)
        room["items"][item["id"]] = item
        completed = True
    except OSError as error:
        raise HTTPException(507, "Unable to save the file on the host.") from error
    finally:
        pending_uploads.discard(path)
        if not completed:
            path.unlink(missing_ok=True)
    publish(room["id"])
    return public_item(item)


@router.get("/files/{item_id}")
async def download(item_id: str, room=Depends(authorize)):
    item = room["items"].get(item_id)
    if item is None or item["kind"] != "file" or not item["path"].is_file():
        raise HTTPException(404, "File not found in this room.")
    if expired(item):
        cleanup_room(room)
        raise HTTPException(410, "This file has expired.")
    return DownloadResponse(room, item)


# Keep time behind one function so expiry boundaries can be tested without waiting.
def now():
    return time.time()


def expired(item):
    return item["expires_at"] <= now()


def cleanup_room(room):
    changed = False
    for item_id, item in list(room["items"].items()):
        if not expired(item):
            continue
        if not item.get("_expiry_notified"):
            item["_expiry_notified"] = True
            changed = True
        if item.get("_downloads", 0):
            continue
        if item["kind"] == "file":
            try:
                item["path"].unlink(missing_ok=True)
            except OSError:
                logger.exception("Could not remove expired file %s; will retry", item_id)
                continue
        del room["items"][item_id]
    if changed:
        publish(room["id"])


def cleanup_once():
    for room in list(rooms.values()):
        cleanup_room(room)
    tracked = {item["path"] for room in rooms.values() for item in room["items"].values()
               if item["kind"] == "file"} | pending_uploads
    # Room indexes reset on restart. Remove only old, generated NetDrop filenames.
    for path in config.UPLOAD_DIR.iterdir():
        if path in tracked or not re.fullmatch(r"[0-9a-f]{32}", path.name):
            continue
        try:
            if not path.is_symlink() and path.is_file() and path.stat().st_mtime + config.FILE_TTL_SECONDS <= now():
                path.unlink()
        except OSError:
            logger.exception("Could not remove orphaned upload %s; will retry", path.name)


async def cleanup_loop():
    while True:
        await asyncio.sleep(config.CLEANUP_INTERVAL_SECONDS)
        try:
            cleanup_once()
        except OSError:
            logger.exception("Upload cleanup failed; will retry")


class DownloadResponse(FileResponse):
    """Reserve a file until transmission finishes, including client disconnects."""

    def __init__(self, room, item):
        self.room = room
        self.item = item
        super().__init__(item["path"], filename=item["name"], media_type="application/octet-stream",
                         headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "no-store"})

    async def __call__(self, scope, receive, send):
        if expired(self.item):
            response = JSONResponse({"detail": "This file has expired."}, status_code=410)
            await response(scope, receive, send)
            return
        self.item["_downloads"] = self.item.get("_downloads", 0) + 1
        try:
            # Do not hand off a path to the server: the lease covers actual bytes sent.
            scope = {**scope, "extensions": {key: value for key, value in scope.get("extensions", {}).items()
                                             if key != "http.response.pathsend"}}
            await super().__call__(scope, receive, send)
        finally:
            self.item["_downloads"] -= 1
            cleanup_room(self.room)
