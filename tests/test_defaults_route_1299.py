"""Row 1299, S6 (first part): GET and POST /api/defaults (src/clark/app_settings.py, routed by server.py) over the install's one install_defaults
row (row 1300): review days, the Gantt tab for the editor and for the client, and the tab's name. Every test talks to a real server. A project's
own value and the rule that a project follows the default are not part of this slice. Fictional data only.

Run: python3 dev/run_tests.py test_defaults_route_1299
"""
import sqlite3
import unittest

from _paths import SRC  # noqa: F401

from clark import app_settings, store as st
from test_app_settings_route import Base

TODAY = {"review_days": 14, "gantt_editor": False, "gantt_client": False, "gantt_name": "Gantt"}


class Defaults(Base):
    def stored(self):
        store = st.open_store(self.db, onedrive_roots=[])
        try:
            return tuple(store.con.execute("SELECT review_days, gantt_editor, gantt_client, gantt_name FROM install_defaults").fetchall()[0])
        finally:
            store.close()

    def post(self, body):
        return self.call("POST", "/api/defaults", body)

    def test_a_new_file_reads_today_s_values(self):
        self.assertEqual(self.call("GET", "/api/defaults"), (200, {"ok": True, "saved": True, "defaults": TODAY}))

    def test_each_value_is_saved_and_read_back(self):
        for body, key, want, row in [({"review_days": 30}, "review_days", 30, (30, 0, 0, "Gantt")),
                                     ({"gantt_editor": True}, "gantt_editor", True, (30, 1, 0, "Gantt")),
                                     ({"gantt_client": True}, "gantt_client", True, (30, 1, 1, "Gantt")),
                                     ({"gantt_name": "  Plan  "}, "gantt_name", "Plan", (30, 1, 1, "Plan"))]:
            status, got = self.post(body)
            self.assertEqual((status, got["ok"], got["defaults"][key]), (200, True, want))
            self.assertIsInstance(got["apply_id"], int)
            self.assertEqual(self.stored(), row)
            self.assertEqual(self.call("GET", "/api/defaults")[1]["defaults"][key], want)

    def test_the_same_value_changes_nothing(self):
        before = self.snapshot()
        for body in ({"review_days": 14}, {"gantt_editor": False}, {"gantt_name": "Gantt"}):
            status, got = self.post(body)
            self.assertEqual((status, got["message"]), (200, app_settings.MESSAGES["same"]))
        self.assertEqual(self.snapshot(), before)

    def test_values_that_are_not_allowed_change_nothing(self):
        before = self.snapshot()
        for body in ({"review_days": 0}, {"review_days": 366}, {"review_days": True}, {"review_days": "7"}, {"review_days": 7.0},
                     {"gantt_editor": 1}, {"gantt_client": "yes"}, {"gantt_name": ""}, {"gantt_name": "   "}, {"gantt_name": "x" * 31},
                     {"gantt_name": 5}):
            status, got = self.post(body)
            self.assertEqual((status, got["code"]), (400, "bad_default"), body)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.stored(), (14, 0, 0, "Gantt"))

    def test_a_body_of_the_wrong_shape_is_refused(self):
        before = self.snapshot()
        for body in ({}, {"review_days": 30, "gantt_editor": True}, {"other": 1}, {"undo": 3, "review_days": 30}, [1], "x"):
            status, got = self.post(body)
            self.assertEqual((status, got["code"]), (400, "bad_request"), body)
        for body in ({"undo": 0}, {"undo": True}, {"undo": "1"}):
            self.assertEqual(self.post(body)[0], 400, body)
        self.assertEqual(self.snapshot(), before)

    def test_undo_takes_the_change_back_once(self):
        step = self.post({"review_days": 45})[1]["apply_id"]
        status, got = self.post({"undo": step})
        self.assertEqual((status, got["defaults"]["review_days"], got["message"]), (200, 14, app_settings.MESSAGES["undone"]))
        self.assertEqual(self.stored(), (14, 0, 0, "Gantt"))
        self.assertEqual(self.post({"undo": step})[0], 409)

    def test_undo_of_another_setting_s_step_is_refused(self):
        other = self.call("POST", "/api/ask-enabled", {"enabled": False})[1]["apply_id"]
        status, got = self.post({"undo": other})
        self.assertEqual((status, got["code"]), (409, "no_undo"))
        self.assertFalse(self.stored_ask())

    def test_a_file_without_the_table_is_not_ready(self):
        con = sqlite3.connect(str(self.db))
        con.execute("DROP TABLE install_defaults")
        con.commit()
        con.close()
        self.assertEqual(self.call("GET", "/api/defaults"), (200, {"ok": True, "saved": False, "defaults": None}))
        status, got = self.post({"review_days": 30})
        self.assertEqual((status, got["code"]), (409, "not_ready"))

    def test_the_route_needs_the_token(self):
        status, _ = self.call("GET", "/api/defaults", token="wrong")
        self.assertIn(status, (401, 403))
        status, _ = self.call("POST", "/api/defaults", {"review_days": 30}, token="wrong")
        self.assertIn(status, (401, 403))
        self.assertEqual(self.stored(), (14, 0, 0, "Gantt"))


if __name__ == "__main__":
    unittest.main()
