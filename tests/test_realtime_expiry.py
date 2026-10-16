"""Live access, exact expiry, and cleanup/download coordination."""

import asyncio
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app import config, files, realtime, rooms
from app.main import app


class LiveExpiryTests(unittest.TestCase):
    def setUp(self):
        rooms.rooms.clear()
        rooms.sessions.clear()
        rooms.attempts.clear()
        realtime.connections.clear()
        self.storage = self.enterContext(tempfile.TemporaryDirectory())
        self.enterContext(patch.object(config, 'UPLOAD_DIR', Path(self.storage)))
        self.client = self.enterContext(TestClient(app))
        self.headers = {'X-NetDrop': '1'}
        self.room_id = self.client.post('/api/rooms', json={'name': 'Live room', 'pin': '123456'}, headers=self.headers).json()['id']
        self.base = f'/api/rooms/{self.room_id}'
        self.ws_headers = {'origin': 'http://testserver'}

    def upload(self):
        result = self.client.post(self.base + '/files', content=b'file bytes', headers={**self.headers, 'X-Filename': 'test.txt'})
        self.assertEqual(result.status_code, 201)
        return result.json()

    def test_live_changes_and_leave_revocation(self):
        with self.client.websocket_connect(self.base + '/live', headers=self.ws_headers) as ws:
            self.assertEqual(ws.receive_json()['type'], 'ready')
            self.upload()
            self.assertEqual(ws.receive_json()['type'], 'changed')
            self.client.post(self.base + '/items', json={'kind': 'text', 'content': 'Live note'}, headers=self.headers)
            self.assertEqual(ws.receive_json()['type'], 'changed')
            self.client.post(self.base + '/leave', headers=self.headers)
            with self.assertRaises(WebSocketDisconnect) as error:
                ws.receive_json()
            self.assertEqual(error.exception.code, 1008)

    def test_socket_rejects_unjoined_room_and_foreign_origin(self):
        for path, headers in [(self.base + '/live', {'origin': 'http://evil.example'}),
                              ('/api/rooms/missing/live', self.ws_headers)]:
            with self.assertRaises(WebSocketDisconnect):
                with self.client.websocket_connect(path, headers=headers):
                    pass
        with TestClient(app) as stranger:
            with self.assertRaises(WebSocketDisconnect):
                with stranger.websocket_connect(self.base + '/live', headers=self.ws_headers):
                    pass

    def test_live_session_expiry(self):
        with self.client.websocket_connect(self.base + '/live', headers=self.ws_headers) as ws:
            ws.receive_json()
            for session in rooms.sessions.values():
                session['expires'] = 0
            self.client.portal.call(realtime.publish, self.room_id)
            with self.assertRaises(WebSocketDisconnect) as error:
                ws.receive_json()
            self.assertEqual(error.exception.code, 1008)

    def test_exact_expiry_and_event(self):
        with patch.object(files, 'now', return_value=1000):
            item = self.upload()
        self.assertEqual(item['expires_at'], 1000 + config.FILE_TTL_SECONDS)
        with self.client.websocket_connect(self.base + '/live', headers=self.ws_headers) as ws:
            ws.receive_json()
            with patch.object(files, 'now', return_value=item['expires_at'] - 0.01):
                self.assertEqual(self.client.get(self.base + '/files/' + item['id']).status_code, 200)
            with patch.object(files, 'now', return_value=item['expires_at']):
                self.assertEqual(self.client.get(self.base + '/files/' + item['id']).status_code, 410)
                self.assertEqual(ws.receive_json()['type'], 'changed')
                self.assertEqual(self.client.get(self.base + '/items').json()['items'], [])
            self.assertFalse((Path(self.storage) / item['id']).exists())

    def test_text_and_link_expire(self):
        with patch.object(files, 'now', return_value=1000):
            for kind, content in [('text', 'Note'), ('link', 'https://example.com')]:
                self.client.post(self.base + '/items', json={'kind':kind, 'content':content}, headers=self.headers)
        with patch.object(files, 'now', return_value=1000 + config.FILE_TTL_SECONDS):
            self.assertEqual(self.client.get(self.base + '/items').json()['items'], [])

    def test_background_cleanup_without_requests(self):
        with patch.object(config, 'FILE_TTL_SECONDS', 1), patch.object(config, 'CLEANUP_INTERVAL_SECONDS', 1):
            # A separate task uses the short interval immediately, independently of GET requests.
            async def check():
                item = files.new_item('text')
                item.update(content='Temporary', expires_at=files.now() + 0.05)
                room = rooms.rooms[self.room_id]
                room['items'][item['id']] = item
                task = asyncio.create_task(files.cleanup_loop())
                try:
                    await asyncio.sleep(1.2)
                    self.assertNotIn(item['id'], room['items'])
                finally:
                    task.cancel()
                    await asyncio.gather(task, return_exceptions=True)
            self.client.portal.call(check)

    def test_orphan_cleanup_preserves_unrelated_and_active_files(self):
        old = Path(self.storage) / ('a' * 32)
        fresh = Path(self.storage) / ('b' * 32)
        pending = Path(self.storage) / ('c' * 32)
        keep = Path(self.storage) / '.gitkeep'
        for path in (old, fresh, pending, keep):
            path.write_text('data')
        age = time.time() - config.FILE_TTL_SECONDS - 10
        for path in (old, pending, keep):
            os.utime(path, (age, age))
        files.pending_uploads.add(pending)
        try:
            self.client.portal.call(files.cleanup_once)
        finally:
            files.pending_uploads.discard(pending)
        self.assertFalse(old.exists())
        self.assertTrue(fresh.exists())
        self.assertTrue(pending.exists())
        self.assertTrue(keep.exists())

    def test_failed_delete_retries(self):
        item = self.upload()
        clock = item['expires_at'] + 1
        with patch.object(files, 'now', return_value=clock), patch.object(Path, 'unlink', side_effect=PermissionError):
            with self.assertLogs('app.files', level='ERROR'):
                self.assertEqual(self.client.get(self.base + '/items').json()['items'], [])
        path = Path(self.storage) / item['id']
        self.assertTrue(path.exists())
        with patch.object(files, 'now', return_value=clock):
            self.client.portal.call(files.cleanup_once)
        self.assertFalse(path.exists())


class DownloadLeaseTests(unittest.IsolatedAsyncioTestCase):
    async def check_download(self, disconnect=False):
        with tempfile.TemporaryDirectory() as storage:
            path = Path(storage) / ('a' * 32)
            content = b'x' * 200000
            path.write_bytes(content)
            item = {'id':path.name, 'kind':'file', 'name':'large.bin', 'path':path, 'expires_at':1010}
            room = {'id':'test', 'items':{item['id']:item}}
            clock = [1000]
            body = bytearray()
            async def receive():
                return {'type':'http.request'}
            async def send(message):
                if message['type'] == 'http.response.body':
                    clock[0] = 1010
                    files.cleanup_room(room)
                    self.assertTrue(path.exists(), 'Cleanup deleted an active transfer')
                    self.assertEqual(item['_downloads'], 1)
                    if disconnect:
                        raise asyncio.CancelledError()
                    body.extend(message['body'])
            scope = {'type':'http', 'method':'GET', 'headers':[], 'extensions':{}, 'asgi':{'version':'3.0','spec_version':'2.4'}}
            with patch.object(files, 'now', side_effect=lambda: clock[0]):
                if disconnect:
                    with self.assertRaises(asyncio.CancelledError):
                        await files.DownloadResponse(room, item)(scope, receive, send)
                else:
                    await files.DownloadResponse(room, item)(scope, receive, send)
                    self.assertEqual(bytes(body), content)
            self.assertFalse(path.exists())
            self.assertNotIn(item['id'], room['items'])

    async def test_download_finishes_before_deletion(self):
        await self.check_download()

    async def test_disconnect_releases_download(self):
        await self.check_download(disconnect=True)
