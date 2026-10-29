"""Authorized room update signals; clients fetch a fresh list after each signal."""

import asyncio
import time
from urllib.parse import urlsplit

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.rooms import rooms, session_for
from app import config

router = APIRouter()
connections = {}


def publish(room_id):
    for event in list(connections.get(room_id, {}).values()):
        event.set()


def authorized(socket, room_id):
    session = session_for(socket)
    return session is not None and room_id in session['rooms'] and room_id in rooms and not rooms[room_id].get('closed')


@router.websocket('/api/rooms/{room_id}/live')
async def room_updates(socket: WebSocket, room_id: str):
    origin = urlsplit(socket.headers.get('origin', ''))
    expected_scheme = 'https' if socket.url.scheme == 'wss' else 'http'
    if ((config.SHARING_MODE == 'online' and socket.url.scheme != 'wss')
            or origin.scheme != expected_scheme or origin.netloc != socket.headers.get('host')
            or not authorized(socket, room_id)):
        await socket.close(code=1008)
        return
    listeners = connections.setdefault(room_id, {})
    if len(listeners) >= 100:
        await socket.close(code=1013)
        return
    await socket.accept()
    changed = asyncio.Event()
    listeners[socket] = changed
    for other, event in list(listeners.items()):
        if other is not socket:
            event.set()
    receiver = asyncio.create_task(socket.receive())
    waiter = None
    try:
        await socket.send_json({'type': 'ready'})
        while True:
            waiter = asyncio.create_task(changed.wait())
            done, _ = await asyncio.wait({receiver, waiter}, timeout=10,
                                         return_when=asyncio.FIRST_COMPLETED)
            if receiver in done:
                # This channel only sends updates; any client message ends it.
                if receiver.result()['type'] != 'websocket.disconnect':
                    await socket.close(code=1008)
                break
            if not authorized(socket, room_id):
                await socket.close(code=1008)
                break
            if waiter in done:
                changed.clear()
                await socket.send_json({'type': 'changed'})
            else:
                await socket.send_json({'type': 'heartbeat'})
            waiter.cancel()
            await asyncio.gather(waiter, return_exceptions=True)
            waiter = None
    except (WebSocketDisconnect, OSError, RuntimeError):
        pass
    finally:
        for task in (receiver, waiter):
            if task is not None:
                task.cancel()
        await asyncio.gather(*(task for task in (receiver, waiter) if task is not None),
                             return_exceptions=True)
        listeners.pop(socket, None)
        if not listeners:
            connections.pop(room_id, None)
            if room_id in rooms:
                rooms[room_id]["last_activity"] = time.time()
        publish(room_id)
