"""Row 1269, slice A: GET and POST /api/theme (src/clark/app_settings.py, routed by server.py). Every test talks to a real server.

Run: python3 dev/run_tests.py test_theme_setting_route
Fictional data in a temporary clark database.
"""
import json
import unittest

from _paths import SRC  # noqa: F401
from clark import app_settings, server as sv, store as st
from test_app_settings_route import Base


class Theme(Base):
    def theme(self, value):
        return self.call("POST", "/api/theme", {"theme": value})

    def stored(self):
        store = st.open_store(self.db, onedrive_roots=[])
        try:
            return store.theme()
        finally:
            store.close()

    def keep_cards(self):
        """A value an earlier version stored (row 1363: Cards can no longer be chosen, but a stored one is left alone)."""
        store = st.open_store(self.db, onedrive_roots=[])
        try:
            with store.con:
                store.con.execute("UPDATE app_settings SET theme = 'cards' WHERE id = 1")
        finally:
            store.close()

    def test_classic_to_start_with_and_cards_cannot_be_chosen(self):
        self.assertEqual(self.call("GET", "/api/theme"), (200, {"ok": True, "theme": "classic", "saved": True}))
        status, got = self.theme("cards")
        self.assertEqual((status, got["code"]), (400, "bad_theme"))
        self.assertEqual(self.stored(), "classic")

    def test_a_stored_cards_value_is_read_back_and_can_be_changed_to_classic(self):
        self.keep_cards()
        self.assertEqual(self.call("GET", "/api/theme")[1]["theme"], "cards")
        self.assertEqual(self.stored(), "cards")
        status, got = self.theme("classic")
        self.assertEqual((status, got["theme"]), (200, "classic"))
        self.assertIsInstance(got["apply_id"], int)

    def test_the_same_value_changes_nothing(self):
        before = self.snapshot()
        status, got = self.theme("classic")
        self.assertEqual((status, got["theme"], got["message"]), (200, "classic", app_settings.MESSAGES["same"]))
        self.assertEqual(self.snapshot(), before)

    def test_undo_takes_the_change_back_once(self):
        self.keep_cards()
        step = self.theme("classic")[1]["apply_id"]
        status, got = self.call("POST", "/api/theme", {"undo": step})
        self.assertEqual((status, got["theme"]), (200, "cards"))
        self.assertEqual(self.call("POST", "/api/theme", {"undo": step})[0], 409)
        self.assertEqual(self.stored(), "cards")

    def test_an_undo_of_the_ask_switch_is_not_accepted_here_and_the_other_way_round(self):
        ask_step = self.ask(False)[1]["apply_id"]
        before = self.snapshot()
        status, got = self.call("POST", "/api/theme", {"undo": ask_step})
        self.assertEqual((status, got["code"]), (409, "no_undo"))
        self.assertEqual(self.snapshot(), before)
        self.keep_cards()
        theme_step = self.theme("classic")[1]["apply_id"]
        status, got = self.call("POST", "/api/ask-enabled", {"undo": theme_step})
        self.assertEqual((status, got["code"]), (409, "no_undo"))
        self.assertEqual(self.stored(), "classic")

    def test_bad_bodies_are_refused_and_nothing_changes(self):
        before = self.snapshot()
        for body in ({"theme": "Classic"}, {"theme": "dark"}, {"theme": 1}, {"theme": None}, {"theme": ["cards"]}, {"theme": "cards"}):
            status, got = self.call("POST", "/api/theme", body)
            self.assertEqual((status, got["code"]), (400, "bad_theme"), body)
        for body in ({}, {"theme": "cards", "x": 1}, {"enabled": True}, [], "cards", {"undo": "1"}, {"undo": True}, {"undo": 0}):
            self.assertEqual(self.call("POST", "/api/theme", body)[0], 400, body)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.stored(), "classic")

    def test_no_token_no_change(self):
        status, _, _ = self.s.api("POST", "/api/theme", json.dumps({"theme": "cards"}).encode(), token="wrong")
        self.assertIn(status, (401, 403))
        self.assertEqual(self.stored(), "classic")

    def test_the_route_is_a_save_route_with_a_small_body_limit(self):
        self.assertIn("/api/theme", sv.SAVE_PATHS)
        self.assertEqual(sv.ROUTE_BODY_LIMITS["/api/theme"], 1024)


class NotReady(Base):
    ready = False

    def test_a_file_that_cannot_keep_it_says_so(self):
        status, got = self.call("GET", "/api/theme")
        self.assertEqual((status, got["theme"], got["saved"]), (200, "cards", False))
        status, got = self.call("POST", "/api/theme", {"theme": "classic"})
        self.assertEqual((status, got["code"]), (409, "not_ready"))


if __name__ == "__main__":
    unittest.main()
