"""Private room rosters and presence across browser sessions and tabs."""

import unittest

from fastapi.testclient import TestClient

from app import realtime, rooms
from app.main import app


class MemberTests(unittest.TestCase):
    def setUp(self):
        rooms.rooms.clear()
        rooms.sessions.clear()
        rooms.attempts.clear()
        realtime.connections.clear()
        self.owner = self.enterContext(TestClient(app))
        self.guest = self.enterContext(TestClient(app))
        self.headers = {"X-NetDrop": "1"}
        result = self.owner.post("/api/rooms", headers=self.headers,
                                 json={"name": "Members", "pin": "123456", "display_name": "Rhimar"})
        self.room_id = result.json()["id"]
        self.base = f"/api/rooms/{self.room_id}"

    def members(self):
        return self.owner.get(self.base + "/members").json()["members"]

    def join(self, name="Alex"):
        return self.guest.post(self.base + "/join", headers=self.headers,
                               json={"pin": "123456", "display_name": name})

    def test_private_roster_names_and_leave(self):
        self.assertEqual(self.guest.get(self.base + "/members").status_code, 403)
        self.assertEqual(self.join("  Alex  ").status_code, 200)
        members = self.members()
        self.assertEqual([member["name"] for member in members], ["Rhimar", "Alex"])
        self.assertEqual([member["is_you"] for member in members], [True, False])
        self.assertTrue(all(set(member) == {"id", "name", "is_you", "online"} for member in members))
        self.assertNotIn(rooms.COOKIE, str(members))
        self.join()
        self.assertEqual(len(self.members()), 2, "Rejoining must not duplicate a browser")
        other = self.guest.post("/api/rooms", headers=self.headers,
                                json={"name": "Other", "pin": "654321"}).json()["id"]
        self.assertEqual(len(self.guest.get(f"/api/rooms/{other}/members").json()["members"]), 1)
        self.guest.post(self.base + "/leave", headers=self.headers)
        self.assertEqual(len(self.members()), 1)
        self.assertEqual(self.guest.get(self.base + "/members").status_code, 403)

    def test_default_name_validation_and_expiry(self):
        self.assertEqual(self.join("x" * 41).status_code, 422)
        self.assertEqual(self.join("   ").status_code, 200)
        self.assertTrue(self.members()[1]["name"].startswith("Guest "))
        guest_session = rooms.sessions[self.guest.cookies.get(rooms.COOKIE)]
        guest_session["expires"] = 0
        self.assertEqual(len(self.members()), 1)

    def test_live_join_tabs_disconnect_and_leave(self):
        headers = {"origin": "http://testserver"}
        with self.owner.websocket_connect(self.base + "/live", headers=headers) as owner_ws:
            self.assertEqual(owner_ws.receive_json()["type"], "ready")
            self.assertTrue(self.members()[0]["online"])
            self.join()
            self.assertEqual(owner_ws.receive_json()["type"], "changed")
            self.assertFalse(self.members()[1]["online"])
            with self.guest.websocket_connect(self.base + "/live", headers=headers) as guest_ws:
                self.assertEqual(guest_ws.receive_json()["type"], "ready")
                self.assertEqual(owner_ws.receive_json()["type"], "changed")
                self.assertTrue(self.members()[1]["online"])
                with self.guest.websocket_connect(self.base + "/live", headers=headers) as second_tab:
                    self.assertEqual(second_tab.receive_json()["type"], "ready")
                    self.assertEqual(owner_ws.receive_json()["type"], "changed")
                    self.assertEqual(len(self.members()), 2)
                self.assertEqual(owner_ws.receive_json()["type"], "changed")
                self.assertTrue(self.members()[1]["online"], "One open tab keeps a member online")
            self.assertEqual(owner_ws.receive_json()["type"], "changed")
            self.assertFalse(self.members()[1]["online"])
            self.guest.post(self.base + "/leave", headers=self.headers)
            self.assertEqual(owner_ws.receive_json()["type"], "changed")
            self.assertEqual(len(self.members()), 1)
