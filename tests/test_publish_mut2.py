"""Hand-mutation pass 2 over the guarded publish code merged in the last day (past_reports.py local_day, DAY, the visit clock;
publish_flow.py Publisher.project_brand). Each test below kills a mutant that the existing tests let live; the mutant is named in
the test. Fictional data only; no browser.

Run: python3 dev/run_tests.py test_publish_mut2
"""
import os
import sqlite3
import time
import unittest
from unittest import mock

import _paths  # noqa: F401
from _demo import USER
from clark import past_reports, publish_flow
from test_past_reports import Base, SHA


class LocalDay(unittest.TestCase):
    def test_an_unconvertible_time_has_no_day_when_the_system_says_OSError(self):
        # mutant: local_day's except drops OSError (astimezone raises it on some systems for a date the computer cannot place)
        with mock.patch.object(past_reports.timefmt, "parse", side_effect=OSError("year out of range")):
            self.assertIsNone(past_reports.local_day("2026-11-02 08:00:00"))

    def test_the_day_is_the_computers_own_not_the_logged_utc_day(self):
        # mutant: local_day without .astimezone() (the UTC date is given as the day)
        old = os.environ.get("TZ")
        self.addCleanup(lambda: (os.environ.pop("TZ", None) if old is None else os.environ.__setitem__("TZ", old), time.tzset()))
        os.environ["TZ"] = "XXX-4"                      # POSIX: four hours ahead of UTC
        time.tzset()
        self.assertEqual(past_reports.local_day("2026-11-02 21:00:00"), "2026-11-03")
        self.assertEqual(past_reports.local_day("2026-11-02 19:59:59"), "2026-11-02")
        os.environ["TZ"] = "XXX+5"                      # five hours behind
        time.tzset()
        self.assertEqual(past_reports.local_day("2026-11-02 04:00:00"), "2026-11-01")


class Listing(Base):
    def setUp(self):
        super().setUp()
        self.past = past_reports.PastReports(self.db)

    def row(self, number, week):
        con = sqlite3.connect(self.db)
        try:
            con.execute("INSERT INTO publications (project, at, week_ending, local_path, client_path, word, file_sha256, checks, by_user, number, pdf_name) "
                        "VALUES (?,?,?,?,?,?,?,?,?,?,?)", ("PUB", "2026-11-02 08:00:00.000", week, "/x/l", None, 0, SHA, "not needed", USER, number, None))
            con.commit()
        finally:
            con.close()

    def test_a_week_ending_needs_two_digits_for_the_day(self):
        # mutant: DAY's last group {1,2} (a one-digit day, "2026-11-1", would be listed as a week)
        for i, w in enumerate(("2026-11-1", "2026-11-12", "2026-1-12", "2026-11-123"), 1):
            self.row(i, w)
        status, body = self.past.listing("PUB")
        self.assertEqual(status, 200)
        self.assertEqual({p["number"]: p["week"] for p in body["publications"]},
                         {1: None, 2: "2026-11-12", 3: None, 4: None})


class VisitClock(Base):
    def test_an_address_is_good_for_exactly_the_visit_seconds(self):
        # mutant: take's `<=` made `<`
        done, body = self.publish()
        clock = [0.0]
        past = past_reports.PastReports(self.db, clock=lambda: clock[0])
        nonce = past.visit("PUB", done["number"])[1]["url"].split("=")[1]
        clock[0] = past_reports.VISIT_SECONDS
        self.assertIsNotNone(past.take(nonce), "at exactly the limit it still opens")
        nonce = past.visit("PUB", done["number"])[1]["url"].split("=")[1]
        clock[0] = past_reports.VISIT_SECONDS * 2 + 0.5
        self.assertIsNone(past.take(nonce), "just over it, it does not")

    def test_a_waiting_address_exactly_at_the_limit_is_not_dropped_by_the_next_visit(self):
        # mutant: the sweep's `>` made `>=` (the address leaves the waiting list one tick early)
        done, body = self.publish()
        clock = [0.0]
        past = past_reports.PastReports(self.db, clock=lambda: clock[0])
        first = past.visit("PUB", done["number"])[1]["url"].split("=")[1]
        clock[0] = past_reports.VISIT_SECONDS
        past.visit("PUB", done["number"])
        self.assertIn(first, past.visits)


class ProjectBrand(unittest.TestCase):
    def test_a_branding_given_to_the_publisher_wins_even_when_it_is_falsy(self):
        # mutant: `self.branding if self.branding is not None else ...` made `self.branding or ...`
        class Store:
            def read(self, *a, **k):
                raise AssertionError("the project's own brand must not be looked up when a branding was given")
        pub = publish_flow.Publisher("/nonexistent/clark.db", [], branding="", data_dir="/nonexistent")
        self.assertEqual(pub.project_brand(Store(), "ABC"), "")


if __name__ == "__main__":
    unittest.main()
