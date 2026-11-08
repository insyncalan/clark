"""#314: a failed first "I sent it" frees the in-flight guard (#258). The seam refuses the same record while one is being written;
that must end when the first one ends, whether it was refused by the store, hit a fault, or recorded. The page frees its own guard in
a finally too (tests/test_draft_email_editor.py). Fictional names. Run: python3 dev/run_tests.py test_sent_guard_freed"""
import sqlite3
import unittest
from datetime import date
from unittest import mock

import _paths  # noqa: F401
from _demo import DemoStore
from clark import draft_email_feed as feed
from clark.store import Invalid, Store


class SentGuardFreed(unittest.TestCase):
    DAY = "2026-10-28"

    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.store = self.demo.store
        self.a = self.demo.action(description="Share the plan", owner="Dana Hart", status="Open")
        self.seam = feed.make_sent(self.store.path, [], by_user="Sam Lee", today=date(2026, 10, 28))

    def req(self):
        return {"project": "ABC", "ids": [self.a], "mode": "chase", "day": self.DAY}

    def rows(self):
        return len(self.store.email_sent_for("ABC"))

    def test_a_first_press_the_store_refuses_does_not_leave_the_same_press_stuck(self):
        with mock.patch.object(Store, "log_email_sent", side_effect=Invalid("One of the ticked items is not in this project. Reload the page and tick again.")):
            status, body = self.seam(self.req())
        self.assertEqual((status, body["ok"], body["code"]), (400, False, "refused"))
        self.assertEqual(self.rows(), 0)
        status, body = self.seam(self.req())                                  # the very same press, once the cause is gone
        self.assertEqual((status, body["ok"]), (200, True), body)
        self.assertEqual(self.rows(), 1)

    def test_a_first_press_that_hits_a_fault_does_not_leave_the_same_press_stuck(self):
        with mock.patch.object(Store, "log_email_sent", side_effect=sqlite3.OperationalError("disk I/O error")):
            with self.assertRaises(sqlite3.OperationalError):                 # raised from the seam; the server answers it with its own 500
                self.seam(self.req())
        self.assertEqual(self.rows(), 0)
        status, body = self.seam(self.req())
        self.assertEqual((status, body["ok"]), (200, True), body)
        self.assertEqual(self.rows(), 1)

    def test_a_refusal_before_the_guard_is_taken_leaves_nothing_held(self):
        status, body = self.seam({**self.req(), "mode": "nonsense"})
        self.assertEqual((status, body["ok"]), (400, False))
        status, body = self.seam(self.req())
        self.assertEqual((status, body["ok"]), (200, True), body)


class SentOnce(unittest.TestCase):
    """#315: the guard that outlives the seam. The seam's in-flight set only covers a press while another is being written; a repeat
    press after the reply, or one through a second server process (a second seam on the same file), is held by the store (Store.log_email_sent)."""
    DAY = SentGuardFreed.DAY
    setUp, req, rows = SentGuardFreed.setUp, SentGuardFreed.req, SentGuardFreed.rows

    def test_a_repeat_press_after_the_reply_is_the_same_record(self):
        first = self.seam(self.req())
        again = self.seam(self.req())
        self.assertEqual((first[0], again[0]), (200, 200))
        self.assertEqual(again[1]["seq"], first[1]["seq"])
        self.assertEqual(self.rows(), 1)

    def test_a_second_server_process_is_the_same_record(self):
        other = feed.make_sent(self.store.path, [], by_user="Sam Lee", today=date(2026, 10, 28))   # its own in-flight set, the same file
        first = self.seam(self.req())
        again = other(self.req())
        self.assertEqual(again[1]["seq"], first[1]["seq"])
        self.assertEqual(self.rows(), 1)

    def test_a_press_after_the_window_is_a_new_record(self):
        first = self.seam(self.req())
        self.store.con.execute("DROP TRIGGER email_sent_no_update")                  # test only: age the record past the window
        self.store.con.execute("UPDATE email_sent SET at = datetime('now', ?)", ("-60 seconds",))
        self.store.con.commit()
        again = self.seam(self.req())
        self.assertNotEqual(again[1]["seq"], first[1]["seq"])
        self.assertEqual(self.rows(), 2)


if __name__ == "__main__":
    unittest.main()
