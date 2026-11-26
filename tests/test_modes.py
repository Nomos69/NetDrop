"""Mode routing configuration and HTTPS protection for online sharing."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from zeroconf._exceptions import EventLoopBlocked

from app import config, rooms
from app.main import app


class ModeTests(unittest.TestCase):
    def setUp(self):
        rooms.rooms.clear()
        rooms.sessions.clear()
        rooms.attempts.clear()
        storage = self.enterContext(tempfile.TemporaryDirectory())
        self.enterContext(patch.object(config, "UPLOAD_DIR", Path(storage)))
        self.enterContext(patch.object(config, "LOCAL_DISCOVERY", False))
        self.headers = {"X-NetDrop": "1"}

    def test_local_room_uses_lan_origin_and_never_exposes_pin(self):
        with patch.object(config, "SHARING_MODE", "local"), \
                patch.object(config, "LOCAL_URL", "http://192.168.1.12:8000"), \
                TestClient(app, base_url="http://127.0.0.1:8000") as client:
            sharing = client.get("/api/sharing").json()
            self.assertEqual(sharing["mode"], "local")
            self.assertEqual(sharing["local_url"], "http://192.168.1.12:8000")
            self.assertTrue(sharing["local_installer_url"].startswith("https://"))
            self.assertTrue(sharing["ubuntu_installer_url"].endswith(".deb"))

            room = client.post("/api/rooms", headers=self.headers,
                               json={"name": "Local", "pin": "1234"}).json()
            self.assertEqual(room["mode"], "local")
            self.assertEqual(room["local_url"], "http://192.168.1.12:8000")
            self.assertNotIn("pin", room)

            discovered = client.get("/api/rooms/discover").json()["rooms"]
            self.assertEqual(discovered, [
                {"id": room["id"], "name": "Local", "expires_at": room["expires_at"]}
            ])
            with patch("app.rooms.qrcode.make", wraps=rooms.qrcode.make) as make:
                self.assertEqual(client.get(f'/api/rooms/{room["id"]}/invitation.svg').status_code, 200)
            self.assertEqual(
                make.call_args.args[0],
                "http://192.168.1.12:8000/#room=" + room["id"],
            )

    def test_local_origin_defaults_to_request_origin(self):
        with patch.object(config, "SHARING_MODE", "local"), \
                patch.object(config, "LOCAL_URL", ""), \
                TestClient(app, base_url="http://127.0.0.1:8000") as client:
            sharing = client.get("/api/sharing").json()
            self.assertEqual(sharing["local_url"], "http://127.0.0.1:8000")
            room = client.post("/api/rooms", headers=self.headers,
                               json={"name": "Local", "pin": "1234"}).json()
            self.assertEqual(room["local_url"], "http://127.0.0.1:8000")

    def test_online_server_does_not_expose_local_room_discovery(self):
        with patch.object(config, "SHARING_MODE", "online"), \
                patch.object(config, "ONLINE_URL", "https://example.com"), \
                TestClient(app, base_url="https://example.com") as client:
            self.assertEqual(client.get("/api/rooms/discover").status_code, 404)

    def test_local_server_starts_when_mdns_registration_times_out(self):
        zeroconf = Mock()
        zeroconf.register_service.side_effect = EventLoopBlocked()
        with self.assertLogs("app.local_discovery", level="WARNING") as captured:
            with patch.object(config, "SHARING_MODE", "local"), \
                    patch.object(config, "LOCAL_DISCOVERY", True), \
                    patch("app.local_discovery.local_ipv4_addresses",
                          return_value=["192.168.1.12"]), \
                    patch("app.local_discovery.Zeroconf", return_value=zeroconf), \
                    TestClient(app) as client:
                self.assertEqual(client.get("/up").status_code, 200)
        self.assertIn("continuing with direct LAN access", captured.output[0])
        zeroconf.close.assert_called_once()

    def test_online_https_sharing_and_private_download(self):
        with patch.object(config, "SHARING_MODE", "online"), \
                patch.object(config, "ONLINE_URL", "https://example.com"), \
                TestClient(app, base_url="https://example.com") as owner, \
                TestClient(app, base_url="https://example.com") as guest:
            sharing = owner.get("/api/sharing").json()
            self.assertEqual(sharing["mode"], "online")
            self.assertEqual(sharing["online_url"], "https://example.com")
            result = owner.post("/api/rooms", headers=self.headers,
                                json={"name": "Online", "pin": "1234"})
            self.assertIn("Secure", result.headers["set-cookie"])
            room = result.json()
            self.assertEqual(room["mode"], "online")
            base = f'/api/rooms/{room["id"]}'
            upload = owner.post(base + "/files", content=b"online file",
                                headers={**self.headers, "X-Filename": "online.txt"}).json()
            url = base + "/files/" + upload["id"]
            self.assertEqual(guest.get(url).status_code, 403)
            self.assertEqual(guest.post(base + "/join", headers=self.headers,
                                       json={"pin": "1234"}).status_code, 200)
            self.assertEqual(guest.get(url).content, b"online file")

    def test_public_https_detected_without_online_configuration(self):
        with patch.object(config, "SHARING_MODE", "local"), \
                patch.object(config, "ONLINE_URL", ""), \
                TestClient(app, base_url="https://netdrop.example.com") as client:
            data = client.get("/api/sharing").json()
            self.assertEqual(data["mode"], "online")
            self.assertEqual(data["online_url"], "https://netdrop.example.com")
            room = client.post("/api/rooms", headers=self.headers,
                               json={"name": "Hosted", "pin": "1234"}).json()
            self.assertEqual(room["mode"], "online")
            self.assertEqual(client.get(f'/api/rooms/{room["id"]}').json()["mode"], "online")
        for origin in ["http://192.168.1.2:8000", "https://127.0.0.1:8000", "https://host.local"]:
            with patch.object(config, "SHARING_MODE", "local"), TestClient(app, base_url=origin) as client:
                self.assertEqual(client.get("/api/sharing").json()["mode"], "local")
        with patch.object(config, "SHARING_MODE", "local"), TestClient(
                app, base_url="http://netdrop.example.com") as client:
            self.assertEqual(client.get("/api/sharing").status_code, 403)

    def test_online_rejects_plaintext_requests_and_websockets(self):
        with patch.object(config, "SHARING_MODE", "online"), TestClient(app) as client:
            for path in ["/", "/api/sharing", "/api/rooms/example/items"]:
                self.assertEqual(client.get(path).status_code, 403)
            self.assertEqual(client.post("/api/rooms", headers=self.headers,
                                         json={"name": "Unsafe", "pin": "1234"}).status_code, 403)
            self.assertEqual(client.get("/up").status_code, 200)
            with self.assertRaises(WebSocketDisconnect):
                with client.websocket_connect("/api/rooms/example/live",
                                              headers={"origin": "http://testserver"}):
                    pass
            self.assertFalse(rooms.rooms)

    def test_invalid_server_urls(self):
        for value in ["http://example.com", "https://user:secret@example.com",
                      "https://example.com/path", "https://example.com?pin=1234",
                      "javascript:alert(1)", "https://example.com:bad", "https://bad host"]:
            with self.subTest(value=value), patch.dict("os.environ", {"TEST_MODE_URL": value}):
                with self.assertRaises(ValueError):
                    config.server_url("TEST_MODE_URL", online=True)
        with patch.dict("os.environ", {"TEST_MODE_URL": "https://example.com/"}):
            self.assertEqual(config.server_url("TEST_MODE_URL", online=True), "https://example.com")
        with patch.dict("os.environ", {"TEST_MODE_URL": "http://192.168.1.12:8000"}):
            self.assertEqual(config.server_url("TEST_MODE_URL"), "http://192.168.1.12:8000")

    def test_invalid_download_urls(self):
        for value in ["http://example.com/file.deb", "https://user:secret@example.com/file.deb",
                      "https://example.com:bad/file.deb", "https://bad host/file.deb"]:
            with self.subTest(value=value), patch.dict("os.environ", {"TEST_DOWNLOAD_URL": value}):
                with self.assertRaises(ValueError):
                    config.https_download_url("TEST_DOWNLOAD_URL", "https://example.com/file.deb")
        with patch.dict("os.environ", {"TEST_DOWNLOAD_URL": "https://example.com/package.deb"}):
            self.assertEqual(
                config.https_download_url("TEST_DOWNLOAD_URL", "https://example.com/file.deb"),
                "https://example.com/package.deb",
            )

    def test_lan_hostname_validation(self):
        with patch.dict("os.environ", {"TEST_LAN_HOSTNAME": "netdrop"}):
            self.assertEqual(config.lan_hostname("TEST_LAN_HOSTNAME"), "netdrop")
        for value in ["netdrop.local", "net drop", "-netdrop", "netdrop-"]:
            with self.subTest(value=value), patch.dict("os.environ", {"TEST_LAN_HOSTNAME": value}):
                with self.assertRaises(ValueError):
                    config.lan_hostname("TEST_LAN_HOSTNAME")


if __name__ == "__main__":
    unittest.main()
