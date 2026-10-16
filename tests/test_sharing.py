"""Room isolation and sharing checks using temporary storage."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from app import config, rooms
from app.main import app


class SharingTests(unittest.TestCase):
    def setUp(self):
        rooms.rooms.clear()
        rooms.sessions.clear()
        rooms.attempts.clear()
        self.storage = tempfile.TemporaryDirectory()
        self.addCleanup(self.storage.cleanup)
        self.patch = patch.object(config, 'UPLOAD_DIR', Path(self.storage.name))
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.owner = self.enterContext(TestClient(app))
        self.guest = self.enterContext(TestClient(app))
        self.headers = {'X-NetDrop': '1'}
        response = self.owner.post('/api/rooms', json={'name': 'Study group', 'pin': '123456'}, headers=self.headers)
        self.assertEqual(response.status_code, 201)
        self.room = response.json()['id']
        self.base = f'/api/rooms/{self.room}'

    def join(self):
        return self.guest.post(self.base + '/join', json={'pin': '123456'}, headers=self.headers)

    def upload(self, content=b'hello', name='example.txt'):
        return self.owner.post(self.base + '/files', content=content,
                               headers={**self.headers, 'X-Filename': name})

    def test_join_isolation_leave_and_pin(self):
        self.assertEqual(self.guest.get(self.base + '/items').status_code, 403)
        wrong = self.guest.post(self.base + '/join', json={'pin': '654321'}, headers=self.headers)
        self.assertEqual(wrong.status_code, 403)
        self.assertEqual(self.join().status_code, 200)
        self.assertEqual(self.guest.get(self.base + '/items').status_code, 200)
        self.guest.post(self.base + '/leave', headers=self.headers)
        self.assertEqual(self.guest.get(self.base + '/items').status_code, 403)

    def test_pin_attempt_limit(self):
        for _ in range(5):
            self.assertEqual(self.guest.post(self.base + '/join', json={'pin': '000000'}, headers=self.headers).status_code, 403)
        self.assertEqual(self.join().status_code, 429)

    def test_download_is_room_scoped(self):
        uploaded = self.upload()
        self.assertEqual(uploaded.status_code, 201)
        item = uploaded.json()
        self.assertNotIn('path', item)
        url = self.base + '/files/' + item['id']
        self.assertEqual(self.guest.get(url).status_code, 403)
        self.join()
        self.assertEqual(self.guest.get(url).content, b'hello')
        other = self.guest.post('/api/rooms', json={'name': 'Other', 'pin': '999999'}, headers=self.headers).json()['id']
        self.assertEqual(self.guest.get(f'/api/rooms/{other}/files/{item["id"]}').status_code, 404)
        self.assertEqual(self.owner.get(url).headers['content-type'], 'application/octet-stream')

    def test_unsafe_filename_and_private_paths(self):
        result = self.upload(name='..%2F..%2Fexample.txt').json()
        self.assertEqual(result['name'], 'example.txt')
        self.assertEqual([p.name for p in Path(self.storage.name).iterdir()], [result['id']])
        self.assertEqual(self.upload(name='bad%00.txt').status_code, 422)
        for path in ['/.env', '/data/uploads/' + result['id'], '/static/../app/config.py']:
            self.assertEqual(self.owner.get(path).status_code, 404)

    def test_stream_size_limit_removes_partial_upload(self):
        with patch.object(config, 'MAX_UPLOAD_BYTES', 4):
            self.assertEqual(self.upload(b'12345').status_code, 413)
            def chunks():
                yield b'123'
                yield b'456'
            self.assertEqual(self.upload(chunks()).status_code, 413)
        self.assertEqual(list(Path(self.storage.name).iterdir()), [])
        self.assertEqual(self.owner.get(self.base + '/items').json()['items'], [])

    def test_interrupted_upload_does_not_publish(self):
        def chunks():
            yield b'partial'
            raise RuntimeError('Connection interrupted')
        with self.assertRaises(RuntimeError):
            self.upload(chunks())
        self.assertEqual(list(Path(self.storage.name).iterdir()), [])
        self.assertEqual(self.owner.get(self.base + '/items').json()['items'], [])

    def test_text_links_and_write_header(self):
        self.assertEqual(self.owner.post(self.base + '/items', json={'kind':'text', 'content':'Hello'}).status_code, 403)
        for kind, content, code in [('text', '<script>alert(1)</script>', 201), ('link', 'https://example.com', 201), ('link', 'javascript:alert(1)', 422), ('text', '   ', 422)]:
            result = self.owner.post(self.base + '/items', json={'kind': kind, 'content': content}, headers=self.headers)
            self.assertEqual(result.status_code, code)
        self.join()
        self.assertEqual(len(self.guest.get(self.base + '/items').json()['items']), 2)

    def test_expired_session(self):
        for session in rooms.sessions.values():
            session['expires'] = 0
        self.assertEqual(self.owner.get(self.base + '/items').status_code, 403)

    def test_home_and_assets(self):
        for path in ['/', '/static/styles.css', '/static/app.js']:
            self.assertEqual(self.owner.get(path).status_code, 200)


if __name__ == '__main__':
    unittest.main()
