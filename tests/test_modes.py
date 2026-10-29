"""Mode routing configuration and HTTPS protection for online sharing."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from app import config, rooms
from app.main import app


class ModeTests(unittest.TestCase):
    def setUp(self):
        rooms.rooms.clear()
        rooms.sessions.clear()
        rooms.attempts.clear()
        storage = self.enterContext(tempfile.TemporaryDirectory())
        self.enterContext(patch.object(config, 'UPLOAD_DIR', Path(storage)))
        self.headers = {'X-NetDrop': '1'}

    def test_local_discovery_without_session(self):
        with patch.object(config, 'SHARING_MODE', 'local'), TestClient(app) as client:
            self.assertEqual(client.get('/api/sharing').json()['mode'], 'local')
            self.assertFalse(client.cookies)
            room = client.post('/api/rooms', headers=self.headers,
                               json={'name': 'Local', 'pin': '123456'}).json()
            self.assertEqual(room['mode'], 'local')

    def test_online_https_sharing_and_private_download(self):
        with patch.object(config, 'SHARING_MODE', 'online'), \
                patch.object(config, 'ONLINE_URL', 'https://example.com'), \
                TestClient(app, base_url='https://example.com') as owner, \
                TestClient(app, base_url='https://example.com') as guest:
            self.assertEqual(owner.get('/api/sharing').json()['online_url'], 'https://example.com')
            result = owner.post('/api/rooms', headers=self.headers,
                                json={'name': 'Online', 'pin': '123456'})
            self.assertIn('Secure', result.headers['set-cookie'])
            room = result.json()
            self.assertEqual(room['mode'], 'online')
            base = f'/api/rooms/{room["id"]}'
            upload = owner.post(base + '/files', content=b'online file',
                                headers={**self.headers, 'X-Filename': 'online.txt'}).json()
            url = base + '/files/' + upload['id']
            self.assertEqual(guest.get(url).status_code, 403)
            self.assertEqual(guest.post(base + '/join', headers=self.headers,
                                       json={'pin': '123456'}).status_code, 200)
            self.assertEqual(guest.get(url).content, b'online file')
            with guest.websocket_connect('wss://example.com' + base + '/live',
                                          headers={'origin': 'https://example.com'}) as socket:
                self.assertEqual(socket.receive_json()['type'], 'ready')

    def test_public_https_detected_without_online_configuration(self):
        with patch.object(config, 'SHARING_MODE', 'local'), \
                patch.object(config, 'ONLINE_URL', ''), \
                TestClient(app, base_url='https://netdrop.example.com') as client:
            data = client.get('/api/sharing').json()
            self.assertEqual(data['mode'], 'online')
            self.assertEqual(data['online_url'], 'https://netdrop.example.com')
            room = client.post('/api/rooms', headers=self.headers,
                               json={'name': 'Hosted', 'pin': '123456'}).json()
            self.assertEqual(room['mode'], 'online')
            self.assertEqual(client.get(f'/api/rooms/{room["id"]}').json()['mode'], 'online')
        for origin in ['http://192.168.1.2:8000', 'https://127.0.0.1:8000', 'https://host.local']:
            with patch.object(config, 'SHARING_MODE', 'local'), TestClient(app, base_url=origin) as client:
                self.assertEqual(client.get('/api/sharing').json()['mode'], 'local')

    def test_online_rejects_plaintext_requests_and_websockets(self):
        with patch.object(config, 'SHARING_MODE', 'online'), TestClient(app) as client:
            for path in ['/', '/api/sharing', '/api/rooms/example/items']:
                self.assertEqual(client.get(path).status_code, 403)
            self.assertEqual(client.post('/api/rooms', headers=self.headers,
                                         json={'name': 'Unsafe', 'pin': '123456'}).status_code, 403)
            self.assertEqual(client.get('/up').status_code, 200)
            with self.assertRaises(WebSocketDisconnect):
                with client.websocket_connect('/api/rooms/example/live',
                                              headers={'origin': 'http://testserver'}):
                    pass
            self.assertFalse(rooms.rooms)

    def test_invalid_server_urls(self):
        for value in ['http://example.com', 'https://user:secret@example.com',
                      'https://example.com/path', 'https://example.com?pin=123456',
                      'javascript:alert(1)', 'https://example.com:bad', 'https://bad host']:
            with self.subTest(value=value), patch.dict('os.environ', {'TEST_MODE_URL': value}):
                with self.assertRaises(ValueError):
                    config.server_url('TEST_MODE_URL', online=True)
        with patch.dict('os.environ', {'TEST_MODE_URL': 'https://example.com/'}):
            self.assertEqual(config.server_url('TEST_MODE_URL', online=True), 'https://example.com')
