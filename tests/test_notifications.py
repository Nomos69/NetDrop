"""Brevo invitations and upload alerts use mocked provider calls only."""
import asyncio
import unittest
from unittest.mock import AsyncMock, patch

import httpx
from fastapi.testclient import TestClient

from app import config, notifications, rooms
from app.main import app


class NotificationTests(unittest.TestCase):
    def setUp(self):
        rooms.rooms.clear(); rooms.sessions.clear(); rooms.attempts.clear()
        self.client = self.enterContext(TestClient(app))
        self.headers = {"X-NetDrop": "1"}
        self.room = self.client.post("/api/rooms", headers=self.headers,
                                     json={"name": "Study", "pin": "1234"}).json()["id"]
        self.base = f"/api/rooms/{self.room}"
        for key, value in [("BREVO_API_KEY", "test-secret"), ("BREVO_SENDER_EMAIL", "host@example.com"),
                           ("LOCAL_URL", "http://192.168.1.5:8000")]:
            self.enterContext(patch.object(config, key, value))
        self.post = self.enterContext(patch("app.notifications.httpx.AsyncClient.post", new_callable=AsyncMock))
        self.post.return_value = httpx.Response(201, json={"messageId": "test"})

    def invite(self):
        return self.client.post(self.base + "/email-invitation", headers=self.headers,
                                json={"email": "guest@example.com"})

    def test_invitation_has_token_not_pin_and_token_is_validated(self):
        self.assertEqual(self.invite().status_code, 200)
        payload = self.post.call_args.kwargs["json"]
        self.assertNotIn("1234", payload["textContent"])
        token = payload["textContent"].split("invite=")[1].split("\n")[0]
        self.assertTrue(token)
        self.assertEqual(self.client.post(self.base + "/validate-invitation", headers=self.headers,
                                          json={"token": token}).status_code, 200)
        self.assertEqual(self.client.post(self.base + "/validate-invitation", headers=self.headers,
                                          json={"token": "x" * 24}).status_code, 403)

    def test_only_owner_sends_invitation(self):
        with TestClient(app) as guest:
            guest.post(self.base + "/join", headers=self.headers, json={"pin": "1234"})
            self.assertEqual(guest.post(self.base + "/email-invitation", headers=self.headers,
                                        json={"email": "guest@example.com"}).status_code, 403)

    def test_subscription_and_upload_alert_are_private(self):
        response = self.client.post(self.base + "/subscriptions", headers=self.headers,
                                    json={"email": "guest@example.com", "enabled": True})
        self.assertEqual(response.status_code, 200)
        room = rooms.rooms[self.room]
        item = {"kind": "file", "name": "private.txt", "expires_at": 10 ** 12}
        with patch("app.notifications.send_email", new_callable=AsyncMock) as send:
            async def queue():
                notifications.queue_upload_alerts(room, item)
                await asyncio.sleep(0)
            asyncio.run(queue())
            payload = send.call_args.args[0]
        self.assertNotIn("private.txt", payload["textContent"])
        self.assertNotIn("1234", payload["textContent"])
        self.assertEqual(self.client.post(self.base + "/subscriptions", headers=self.headers,
                                          json={"email": "guest@example.com", "enabled": False}).status_code, 200)

    def test_provider_failure_does_not_block_upload(self):
        self.client.post(self.base + "/subscriptions", headers=self.headers,
                         json={"email": "guest@example.com", "enabled": True})
        self.post.return_value = httpx.Response(503)
        response = self.client.post(self.base + "/files", headers={**self.headers, "X-Filename": "hello.txt"}, content=b"hello")
        self.assertEqual(response.status_code, 201)
