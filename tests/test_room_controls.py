"""Owner authorization, idle-room lifecycle, transfer safety and private QR invitations."""
import asyncio
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from starlette.requests import Request
from starlette.websockets import WebSocketDisconnect

from app import config, files, realtime, rooms
from app.main import app


class RoomControlTests(unittest.TestCase):
    def setUp(self):
        rooms.rooms.clear()
        rooms.sessions.clear()
        rooms.attempts.clear()
        realtime.connections.clear()
        self.storage = self.enterContext(tempfile.TemporaryDirectory())
        self.enterContext(patch.object(config, 'UPLOAD_DIR', Path(self.storage)))
        self.owner = self.enterContext(TestClient(app))
        self.guest = self.enterContext(TestClient(app))
        self.headers = {'X-NetDrop': '1'}
        result = self.owner.post('/api/rooms', json={'name': 'Controls', 'pin': '123456'}, headers=self.headers)
        self.assertTrue(result.json()['is_owner'])
        self.room_id = result.json()['id']
        self.base = '/api/rooms/' + self.room_id
        self.room = rooms.rooms[self.room_id]
        self.assertFalse(self.guest.post(self.base + '/join', json={'pin': '123456'}, headers=self.headers).json()['is_owner'])

    def upload(self):
        return self.owner.post(self.base + '/files', content=b'hello', headers={**self.headers, 'X-Filename': 'a.txt'}).json()

    def test_only_owner_can_delete_close_and_remove(self):
        item = self.upload()
        member = rooms.sessions[self.guest.cookies.get(rooms.COOKIE)]['member_id']
        for path in [self.base, self.base + '/items/' + item['id'], self.base + '/members/' + member]:
            self.assertEqual(self.guest.delete(path, headers=self.headers).status_code, 403)
            self.assertEqual(self.owner.delete(path).status_code, 403)
        self.assertEqual(self.owner.delete(self.base + '/items/' + item['id'], headers=self.headers).status_code, 200)
        self.assertEqual(self.guest.get(self.base + '/files/' + item['id']).status_code, 404)
        self.assertFalse(list(Path(self.storage).iterdir()))
        self.assertEqual(self.owner.delete(self.base + '/members/' + member, headers=self.headers).status_code, 200)
        self.assertEqual(self.guest.get(self.base + '/items').status_code, 403)
        self.assertEqual(self.owner.delete(self.base, headers=self.headers).status_code, 200)
        self.assertNotIn(self.room_id, rooms.rooms)

    def test_owner_can_leave_and_rejoin_but_pin_does_not_transfer_ownership(self):
        self.owner.post(self.base + '/leave', headers=self.headers)
        self.assertEqual(self.owner.get(self.base).status_code, 403)
        result = self.owner.post(self.base + '/join', json={'pin': '123456'}, headers=self.headers)
        self.assertTrue(result.json()['is_owner'])
        self.assertTrue(self.owner.get(self.base).json()['is_owner'])
        self.assertFalse(self.guest.get(self.base).json()['is_owner'])
        self.assertEqual(self.guest.delete(self.base, headers=self.headers).status_code, 403)

    def test_removal_revokes_live_socket_and_is_room_scoped(self):
        other = self.guest.post('/api/rooms', json={'name': 'Other', 'pin': '654321'}, headers=self.headers).json()['id']
        member = rooms.sessions[self.guest.cookies.get(rooms.COOKIE)]['member_id']
        with self.guest.websocket_connect(self.base + '/live', headers={'origin': 'http://testserver'}) as ws:
            ws.receive_json()
            self.owner.delete(self.base + '/members/' + member, headers=self.headers)
            with self.assertRaises(WebSocketDisconnect):
                ws.receive_json()
        self.assertEqual(self.guest.get('/api/rooms/' + other).status_code, 200)
        # Removal is not a permanent ban: a valid PIN can grant access again.
        self.assertEqual(self.guest.post(self.base + '/join', json={'pin': '123456'}, headers=self.headers).status_code, 200)

    def test_delete_and_close_respect_active_download_lease(self):
        item = self.upload()
        stored = self.room['items'][item['id']]
        stored['_downloads'] = 1
        self.owner.delete(self.base + '/items/' + item['id'], headers=self.headers)
        self.assertTrue(stored['path'].exists())
        self.assertEqual(self.guest.get(self.base + '/files/' + item['id']).status_code, 410)
        self.owner.delete(self.base, headers=self.headers)
        self.assertIn(self.room_id, rooms.rooms)
        self.assertEqual(self.guest.post(self.base + '/join', json={'pin': '123456'}, headers=self.headers).status_code, 403)
        stored['_downloads'] = 0
        files.cleanup_once()
        self.assertFalse(stored['path'].exists())
        self.assertNotIn(self.room_id, rooms.rooms)

    def test_idle_cleanup_keeps_live_rooms_and_transfers(self):
        self.room['last_activity'] = time.time() - config.ROOM_IDLE_SECONDS - 1
        self.room['_uploads'] = 1
        files.cleanup_once()
        self.assertIn(self.room_id, rooms.rooms)
        self.room['_uploads'] = 0
        with self.owner.websocket_connect(self.base + '/live', headers={'origin': 'http://testserver'}) as ws:
            ws.receive_json()
            files.cleanup_once()
            self.assertIn(self.room_id, rooms.rooms)
        self.assertGreater(self.room["last_activity"], time.time() - 5)
        self.room["last_activity"] = time.time() - config.ROOM_IDLE_SECONDS - 1
        files.cleanup_once()
        self.assertNotIn(self.room_id, rooms.rooms)
        self.assertNotIn(self.room_id, rooms.sessions[self.owner.cookies.get(rooms.COOKIE)]['rooms'])

    def test_close_during_upload_does_not_publish_or_leak_file(self):
        token = self.owner.cookies.get(rooms.COOKIE)
        async def incoming():
            yield b'first'
            files.retire_room(self.room)
            yield b'last'
        async def receive():
            return {'type': 'http.disconnect'}
        request = Request({'type': 'http', 'method': 'POST', 'path': self.base + '/files',
                           'headers': [(b'x-filename', b'test.txt'), (b'cookie', ('netdrop_session=' + token).encode())]}, receive)
        request.stream = incoming
        with self.assertRaises(Exception) as caught:
            asyncio.run(files.upload(request, self.room))
        self.assertEqual(caught.exception.status_code, 403)
        files.cleanup_once()
        self.assertFalse(list(Path(self.storage).iterdir()))
        self.assertNotIn(self.room_id, rooms.rooms)

    def test_qr_is_private_and_encodes_pin_free_invitation(self):
        with patch.object(config, 'LOCAL_URL', 'http://192.168.1.5:8000'), patch('app.rooms.qrcode.make', wraps=rooms.qrcode.make) as make:
            response = self.owner.get(self.base + '/invitation.svg')
            self.assertEqual(response.status_code, 200)
            self.assertIn('image/svg+xml', response.headers['content-type'])
            self.assertIn(b'<svg', response.content)
            self.assertEqual(make.call_args.args[0], 'http://192.168.1.5:8000/#room=' + self.room_id)
            self.assertNotIn('123456', make.call_args.args[0])
        with TestClient(app) as stranger:
            self.assertEqual(stranger.get(self.base + '/invitation.svg').status_code, 403)
