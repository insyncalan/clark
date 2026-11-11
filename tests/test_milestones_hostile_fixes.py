"""Hostile rows fed to milestones.py give a plain answer or the module's own refusal (KeyError for a word that is not a state),
never a stray TypeError or ValueError. Fictional data (fabrikam)."""
import unittest

from clark import milestones

TODAY = "2026-11-11"
ODD = [5, 5.5, True, [], {}, ["2026-11-01"], float("nan"), "2026-02-30", "2026-13-01", "", "<b>", "‮", "x" * 5000]
BAD_STATES = ["Nonsense", "overdue", " ", "<b>", 5, True, ["At risk"], {"a": 1}, 5.5]


class MilestonesHostileFixes(unittest.TestCase):
    def test_needs_reason_ignores_a_state_that_is_not_one_of_the_seven(self):
        for bad in BAD_STATES:
            with self.subTest(state=str(bad)[:12]):
                row = {"state": bad, "state_set": 1, "baseline_date": "2026-12-01"}
                self.assertFalse(milestones.needs_reason(row, TODAY))

    def test_non_text_dates_read_as_no_date(self):
        for bad in [5, 5.5, True, [], {}, ["2026-11-01"], float("nan")]:
            with self.subTest(v=str(bad)[:12]):
                row = {"status": "Planned", "baseline_date": bad, "forecast_date": bad}
                self.assertEqual(milestones.suggested_state(row, TODAY), "On track")
                self.assertEqual(milestones.milestone_state(row, TODAY), "On track")
                self.assertIsNone(milestones.slip_days(row, TODAY))
        row = {"baseline_date": "2026-12-01", "forecast_date": 7}
        self.assertEqual(milestones.suggested_state(row, TODAY), "On track")
        self.assertEqual(milestones.slip_days(row, TODAY), 0)

    def test_a_non_text_today_falls_back_to_the_real_today(self):
        for bad in (5, [], {}, True, "nope"):
            row = {"baseline_date": "2000-01-01"}
            self.assertEqual(milestones.suggested_state(row, bad), "Overdue")
            self.assertGreater(milestones.slip_days(row, bad), 0)

    def test_slip_days_never_raises_on_odd_dates(self):
        for bad in ODD:
            for key in ("baseline_date", "forecast_date"):
                row = {"status": "Planned", "baseline_date": "2026-11-01", "forecast_date": "2026-11-05"}
                row[key] = bad
                with self.subTest(key=key, v=str(bad)[:12]):
                    out = milestones.slip_days(row, TODAY)
                    self.assertTrue(out is None or (isinstance(out, int) and out >= 0))

    def test_an_unreadable_agreed_date_has_no_slip_and_an_unreadable_forecast_falls_back_to_it(self):
        self.assertIsNone(milestones.slip_days({"baseline_date": "2026-02-30"}, TODAY))
        self.assertIsNone(milestones.slip_days({"baseline_date": "<b>"}, TODAY))
        self.assertEqual(milestones.slip_days({"baseline_date": "2026-12-01", "forecast_date": "2026-13-01"}, TODAY), 0)
        self.assertEqual(milestones.slip_days({"baseline_date": "2026-11-01", "forecast_date": "junk"}, TODAY), 10)

    def test_client_word_gives_no_word_for_any_non_state(self):
        for bad in BAD_STATES + [None]:
            with self.subTest(state=str(bad)[:12]):
                self.assertEqual(milestones.client_word(bad), "")

    def test_milestone_state_with_a_non_text_state_is_the_dates_suggestion(self):
        for bad in (5, ["At risk"], {"a": 1}):
            row = {"state": bad, "state_set": 1, "baseline_date": "2026-12-01"}
            self.assertEqual(milestones.milestone_state(row, TODAY), "On track")


if __name__ == "__main__":
    unittest.main()
