"""Mutation guards for draft_email.is_late / due_info, and their parity with the Work items list's overdue bucket.

Run: python3 dev/run_tests.py test_draft_email_late_mutants
Fictional data only.
"""
import unittest

import _paths  # noqa: F401
from clark import draft_email as de
from clark.section_kinds import workitems as wi

TODAY = "2026-10-13"


class IsLate(unittest.TestCase):
    def test_strictly_before_today_only(self):
        self.assertTrue(de.is_late({"due": "2026-10-12"}, TODAY))
        self.assertFalse(de.is_late({"due": TODAY}, TODAY))
        self.assertFalse(de.is_late({"due": "2026-10-14"}, TODAY))

    def test_completed_is_never_late_in_any_spelling(self):
        for status in ("Completed", "completed", " COMPLETED "):
            self.assertFalse(de.is_late({"due": "2026-01-01", "status": status}, TODAY), status)
        for status in ("Open", "Delayed", "", None):
            self.assertTrue(de.is_late({"due": "2026-01-01", "status": status}, TODAY), repr(status))

    def test_no_due_or_no_today_is_never_late(self):
        for item in ({}, {"due": ""}, {"due": None}):
            self.assertFalse(de.is_late(item, TODAY))
        for today in ("", None):
            self.assertFalse(de.is_late({"due": "2026-01-01"}, today))

    def test_the_result_is_a_real_bool(self):
        self.assertIs(de.is_late({"due": "2026-01-01"}, TODAY), True)
        self.assertIs(de.is_late({}, TODAY), False)


class DueInfo(unittest.TestCase):
    def test_overdue_singular_and_plural_edges(self):
        self.assertEqual(de.due_info("2026-10-12", TODAY), {"date": "12-10-2026", "words": "1 day overdue", "level": "over"})
        self.assertEqual(de.due_info("2026-10-11", TODAY)["words"], "2 days overdue")

    def test_today_is_soon_not_over(self):
        self.assertEqual(de.due_info(TODAY, TODAY), {"date": "13-10-2026", "words": "due today", "level": "soon"})

    def test_window_edge_follows_soon_and_default_is_seven(self):
        self.assertEqual(de.DUE_SOON_DAYS, 7)
        self.assertEqual(de.due_info("2026-10-20", TODAY)["level"], "soon")
        self.assertEqual(de.due_info("2026-10-21", TODAY)["level"], "")
        self.assertEqual(de.due_info("2026-10-16", TODAY, soon=3)["level"], "soon")
        self.assertEqual(de.due_info("2026-10-17", TODAY, soon=3)["level"], "")
        self.assertEqual(de.due_info("2026-10-14", TODAY, soon=0), {"date": "14-10-2026", "words": "", "level": ""})

    def test_decisions_say_needed_everywhere_in_the_window(self):
        self.assertEqual(de.due_info(TODAY, TODAY, "decisions")["words"], "needed today")
        self.assertEqual(de.due_info("2026-10-14", TODAY, "decisions")["words"], "needed tomorrow")
        self.assertEqual(de.due_info("2026-10-20", TODAY, "decisions")["words"], "needed in 7 days")
        self.assertEqual(de.due_info("2026-10-12", TODAY, "decisions")["words"], "1 day overdue")
        self.assertEqual(de.due_info("2026-10-14", TODAY, "risks")["words"], "due tomorrow")

    def test_done_keeps_its_date_but_is_never_overdue(self):
        self.assertEqual(de.due_info("2026-10-01", TODAY, done=True), {"date": "01-10-2026", "words": "", "level": ""})
        self.assertEqual(de.due_info("2026-10-01", TODAY, done=False)["level"], "over")
        self.assertEqual(de.due_info(TODAY, TODAY, done=True)["level"], "soon")      # done only mutes the past
        self.assertEqual(de.due_info("2026-10-14", TODAY, done=True)["words"], "due tomorrow")

    def test_no_date_and_bad_dates(self):
        for blank in (None, ""):
            self.assertEqual(de.due_info(blank, TODAY), {"date": "No date", "words": "", "level": ""})
        self.assertEqual(de.due_info("soon", TODAY), {"date": "soon", "words": "", "level": ""})
        self.assertEqual(de.due_info("2026-10-12", "nonsense"), {"date": "2026-10-12", "words": "", "level": ""})


class Parity(unittest.TestCase):
    """The email's overdue and the Work items list's overdue bucket are one rule over the same rows."""

    def test_same_verdict_across_dates_and_statuses(self):
        for status in ("Open", "Delayed", "Pending", "Completed"):
            for due in ("2026-10-01", "2026-10-12", TODAY, "2026-10-14", "2026-10-20", "2026-10-21"):
                row = {"due": due, "status": status}
                late = de.is_late(row, TODAY)
                info = de.due_info(due, TODAY, done=status == "Completed")
                with self.subTest(status=status, due=due):
                    self.assertEqual(wi._bucket(row, TODAY) == "overdue", late)
                    self.assertEqual(info["level"] == "over", late)

    def test_the_soon_edge_agrees(self):
        for due, soon in (("2026-10-20", True), ("2026-10-21", False), (TODAY, True)):
            row = {"due": due, "status": "Open"}
            self.assertEqual(wi._bucket(row, TODAY) == "soon", soon, due)
            self.assertEqual(de.due_info(due, TODAY)["level"] == "soon", soon, due)


if __name__ == "__main__":
    unittest.main()
