"""Mutation sweep on src/clark/milestones.py: each test here kills a mutant the older test_milestones left alive.

Run: python3 dev/run_tests.py test_milestones_mutants
Today is fixed by patching milestones.today, so nothing depends on the real date. Milestones are fictional (fabrikam).
"""
import unittest
from datetime import date
from unittest import mock

from clark import milestones as ms

ON = "2026-10-28"


def row(**values):
    return {"id": "FAB-M-001", "project": "FAB", "name": "Pilot live", "status": "Planned", "baseline_date": None,
            "forecast_date": None, "state": None, "state_set": 0, "state_reason": None, **values}


class Today(unittest.TestCase):
    def test_today_is_a_full_iso_date(self):
        self.assertEqual(ms.today(), date.today().isoformat())
        self.assertRegex(ms.today(), r"^\d{4}-\d{2}-\d{2}$")

    def test_suggested_state_defaults_to_today(self):
        with mock.patch.object(ms, "today", lambda: ON):
            self.assertEqual(ms.suggested_state(row(baseline_date="2026-10-27")), "Overdue")
            self.assertEqual(ms.suggested_state(row(baseline_date="2026-10-29")), "On track")

    def test_slip_days_defaults_to_today(self):
        with mock.patch.object(ms, "today", lambda: ON):
            self.assertEqual(ms.slip_days(row(baseline_date="2026-10-21")), 7)
            self.assertEqual(ms.slip_days(row(baseline_date="2026-11-30")), 0)


class Suggested(unittest.TestCase):
    def test_a_forecast_without_an_agreed_date_is_on_track(self):
        self.assertEqual(ms.suggested_state(row(forecast_date="2027-01-01"), ON), "On track")


class Shown(unittest.TestCase):
    def test_state_set_without_a_state_falls_back_to_the_dates(self):
        self.assertEqual(ms.milestone_state(row(baseline_date="2026-10-01", state=None, state_set=1), ON), "Overdue")


class Reason(unittest.TestCase):
    def test_a_state_not_set_by_the_user_needs_none(self):
        self.assertFalse(ms.needs_reason(row(baseline_date="2026-10-01", state="On track", state_set=0), ON))

    def test_set_flag_without_a_state_needs_none(self):
        self.assertFalse(ms.needs_reason(row(baseline_date="2026-10-01", state=None, state_set=1), ON))

    def test_achieved_set_by_the_user_needs_none(self):
        self.assertFalse(ms.needs_reason(row(baseline_date="2026-10-01", state="Achieved", state_set=1), ON))

    def test_the_date_given_is_the_one_used(self):
        r = row(baseline_date="2026-10-01", state="On track", state_set=1)
        self.assertTrue(ms.needs_reason(r, ON))
        self.assertFalse(ms.needs_reason(r, "2026-09-01"), "not yet overdue on that day, so On track is fair")


class Slip(unittest.TestCase):
    def test_a_row_with_no_status_counts_as_planned(self):
        self.assertEqual(ms.slip_days({"baseline_date": "2026-10-21"}, ON), 7)


if __name__ == "__main__":
    unittest.main()
