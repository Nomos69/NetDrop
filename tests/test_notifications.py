"""Brevo contract, authorization and failure isolation; no real email sent."""
import unittest
from unittest.mock import AsyncMock, patch

import httpx
from fastapi.testclient import TestClient

from app import config, notifications, rooms
from app.main import app


class NotificationTests(unittest.TestCase):
    def setUp(self):
        rooms.rooms.clear()
        rooms.sessions.clear()
        rooms.attempts.clear()
        self.client = self.enterContext(TestClient(app))
        self.headers = {'X-NetDrop': '1'}
        self.room = self.client.post('/api/rooms', headers=self.headers,
                                    json={'name': '<Study>', 'pin': '123456'}).json()['id']
        self.path = f'/api/rooms/{self.room}/email-invitation'
        for key, value in [('BREVO_API_KEY', 'test-secret'), ('BREVO_SENDER_EMAIL', 'host@example.com'),
                           ('LOCAL_URL', 'http://192.168.1.5:8000')]:
            self.enterContext(patch.object(config, key, value))
        self.post = self.enterContext(patch('app.notifications.httpx.AsyncClient.post', new_callable=AsyncMock))
        self.post.return_value = httpx.Response(201, json={'messageId': '<test>'})

    def send(self, **values):
        return self.client.post(self.path, headers=self.headers,
                                json={'email': 'guest@example.com', 'pin': '123456', **values})

    def reset_rate(self):
        rooms.sessions[self.client.cookies.get(rooms.COOKIE)]['email_attempts'] = []

    def test_api_contract_and_duplicate_suppression(self):
        self.assertEqual(self.send().json()['status'], 'accepted')
        args = self.post.call_args
        self.assertEqual(args.args[0], 'https://api.brevo.com/v3/smtp/email')
        self.assertEqual(args.kwargs['headers']['api-key'], 'test-secret')
        payload = args.kwargs['json']
        self.assertIn('PIN: 123456', payload['textContent'])
        self.assertIn('/#room=' + self.room, payload['textContent'])
        self.assertIn('&lt;Study&gt;', payload['htmlContent'])
        self.assertEqual(self.send().status_code, 429)
        self.reset_rate()
        self.assertEqual(self.send().status_code, 409)
        self.assertEqual(self.post.await_count, 1)

    def test_authorization_and_validation(self):
        with TestClient(app) as stranger:
            self.assertEqual(stranger.post(self.path, headers=self.headers,
                json={'email': 'guest@example.com', 'pin': '123456'}).status_code, 403)
            stranger.post(f'/api/rooms/{self.room}/join', headers=self.headers, json={'pin': '123456'})
            self.assertEqual(stranger.post(self.path, headers=self.headers,
                json={'email': 'guest@example.com', 'pin': '123456'}).status_code, 403)
        self.assertEqual(self.client.post(self.path, json={'email': 'a@b.com', 'pin': '123456'}).status_code, 403)
        self.assertEqual(self.send(email='invalid').status_code, 422)
        self.assertEqual(self.send(pin='654321').status_code, 403)
        self.post.assert_not_awaited()

    def test_unconfigured_and_failure_do_not_break_sharing(self):
        with patch.object(config, 'BREVO_API_KEY', ''):
            self.assertEqual(self.send().status_code, 503)
        self.post.return_value = httpx.Response(401, json={'message': 'secret provider details'})
        response = self.send()
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('secret provider details', response.text)
        self.assertEqual(self.client.get(f'/api/rooms/{self.room}/items').status_code, 200)
        self.assertEqual(self.post.await_count, 1)

    def test_rate_limit_retries_are_bounded(self):
        self.post.side_effect = [httpx.Response(429), httpx.Response(429), httpx.Response(201, json={'messageId': 'ok'})]
        with patch('app.notifications.asyncio.sleep', new_callable=AsyncMock):
            self.assertEqual(self.send().status_code, 200)
        self.assertEqual(self.post.await_count, 3)

    def test_timeout_is_not_retried(self):
        self.post.side_effect = httpx.ReadTimeout('private request data')
        self.assertEqual(self.send().status_code, 502)
        self.assertEqual(self.post.await_count, 1)
        self.reset_rate()
        self.assertEqual(self.send().status_code, 409)

    def test_long_retry_after_and_server_errors_stop(self):
        for response in [httpx.Response(429, headers={'Retry-After': '600'}), httpx.Response(500)]:
            self.reset_rate()
            rooms.rooms[self.room]['email_invitations'] = {}
            self.post.reset_mock()
            self.post.return_value = response
            self.assertEqual(self.send().status_code, 503)
            self.assertEqual(self.post.await_count, 1)

    def test_failed_email_does_not_block_upload_download(self):
        import tempfile
        from pathlib import Path
        self.post.return_value = httpx.Response(503)
        self.assertEqual(self.send().status_code, 503)
        with tempfile.TemporaryDirectory() as folder, patch.object(config, 'UPLOAD_DIR', Path(folder)):
            base = f'/api/rooms/{self.room}'
            result = self.client.post(base + '/files', headers={**self.headers, 'X-Filename': 'hello.txt'}, content=b'hello')
            self.assertEqual(result.status_code, 201)
            self.assertEqual(self.client.get(base + '/files/' + result.json()['id']).content, b'hello')

    def test_missing_origin_and_invalid_acceptance(self):
        with patch.object(config, 'LOCAL_URL', ''):
            self.assertEqual(self.send().status_code, 503)
        self.post.assert_not_awaited()
        self.reset_rate()
        self.post.return_value = httpx.Response(201, content=b'invalid')
        self.assertEqual(self.send().status_code, 502)
