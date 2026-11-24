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


if __name__ == "__main__":
    unittest.main()
