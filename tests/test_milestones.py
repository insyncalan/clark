"""#32: milestone state, slip and the original date (src/clark/milestones.py), by the rules in data-model.md.

Run: python3 dev/run_tests.py test_milestones
Every test fixes "today" as ON, so nothing depends on the real date. Milestones are fictional demo rows.
"""
import unittest

from clark import milestones as ms

ON = "2026-10-28"


def row(**values):
    """A Planned milestone with no dates and no state of the user's, with `values` over it."""
    return {"id": "DEMO-M-001", "project": "DEMO", "name": "Pilot live", "status": "Planned", "baseline_date": None,
            "forecast_date": None, "state": None, "state_set": 0, "state_reason": None, **values}


class EachState(unittest.TestCase):
    def test_achieved(self):
        self.assertEqual(ms.milestone_state(row(status="Done", baseline_date="2026-10-01"), ON), "Achieved")

    def test_at_risk_is_the_user_s(self):
        self.assertEqual(ms.milestone_state(row(baseline_date="2026-12-01", state="At risk", state_set=1), ON), "At risk")
        self.assertNotIn("At risk", {ms.suggested_state(row(baseline_date=d, forecast_date=f), ON)
                                     for d, f in (("2026-12-01", None), ("2026-12-01", "2027-01-01"), ("2026-10-01", None))})

    def test_forecast_is_the_user_s(self):
        self.assertEqual(ms.milestone_state(row(forecast_date="2027-02-01", state="Forecast", state_set=1), ON), "Forecast")

    def test_overdue_is_from_the_agreed_date(self):
        self.assertEqual(ms.milestone_state(row(baseline_date="2026-10-27"), ON), "Overdue")
        self.assertEqual(ms.milestone_state(row(baseline_date="2026-10-27", forecast_date="2026-11-30"), ON), "Overdue",
                         "a later forecast doesn't stop an agreed date from having passed")

    def test_slipped(self):
        self.assertEqual(ms.milestone_state(row(baseline_date="2026-11-30", forecast_date="2026-12-14"), ON), "Slipped")

    def test_on_track(self):
        self.assertEqual(ms.milestone_state(row(baseline_date="2026-11-30"), ON), "On track")
        self.assertEqual(ms.milestone_state(row(baseline_date="2026-11-30", forecast_date="2026-11-23"), ON), "On track")
        self.assertEqual(ms.milestone_state(row(baseline_date=ON), ON), "On track", "due today isn't overdue yet")
        self.assertEqual(ms.milestone_state(row(), ON), "On track", "no dates at all")


class Order(unittest.TestCase):
    """The first match wins: Achieved, the user's own (with Forecast), Overdue, Slipped, On track."""

    def test_achieved_beats_the_user_s_state_and_the_dates(self):
        for state in ("At risk", "Forecast"):
            self.assertEqual(ms.milestone_state(row(status="Done", baseline_date="2026-10-01", state=state, state_set=1),
                                                ON), "Achieved")

    def test_the_user_s_state_beats_the_dates(self):
        late = row(baseline_date="2026-10-01", forecast_date="2026-11-30")
        for state in ("On track", "At risk", "Slipped", "Forecast"):
            self.assertEqual(ms.milestone_state({**late, "state": state, "state_set": 1, "state_reason": "Supplier confirmed"},
                                                ON), state)

    def test_a_state_without_state_set_is_ignored(self):
        self.assertEqual(ms.milestone_state(row(baseline_date="2026-10-01", state="On track", state_set=0), ON), "Overdue")

    def test_overdue_beats_slipped(self):
        self.assertEqual(ms.suggested_state(row(baseline_date="2026-10-01", forecast_date="2026-12-01"), ON), "Overdue")

    def test_slipped_beats_on_track(self):
        self.assertEqual(ms.suggested_state(row(baseline_date="2026-11-01", forecast_date="2026-11-02"), ON), "Slipped")


class Reason(unittest.TestCase):
    """A user's state better than the dates suggest needs a reason (for #31's checks); Forecast never does."""

    def test_better_than_the_dates_needs_a_reason(self):
        self.assertTrue(ms.needs_reason(row(baseline_date="2026-10-01", state="On track", state_set=1), ON))
        self.assertTrue(ms.needs_reason(row(baseline_date="2026-11-01", forecast_date="2026-12-01", state="At risk",
                                            state_set=1), ON))

    def test_the_same_or_worse_needs_none(self):
        self.assertFalse(ms.needs_reason(row(baseline_date="2026-12-01", state="At risk", state_set=1), ON))
        self.assertFalse(ms.needs_reason(row(baseline_date="2026-10-01", state="Overdue", state_set=1), ON))
        self.assertFalse(ms.needs_reason(row(baseline_date="2026-10-01"), ON), "no state of the user's")

    def test_forecast_never_does(self):
        self.assertFalse(ms.needs_reason(row(baseline_date="2026-10-01", state="Forecast", state_set=1), ON))

    def test_the_rank_table_is_creaite_s(self):
        self.assertEqual(ms.MS_RANK, {"Achieved": 0, "On track": 1, "At risk": 2, "Slipped": 3, "Overdue": 4})
        self.assertNotIn("Forecast", ms.MS_RANK)
        self.assertEqual(ms.STATES, ("Achieved", "On track", "At risk", "Slipped", "Overdue", "Forecast"))


class ClientWords(unittest.TestCase):
    def test_creaite_s_words(self):
        self.assertEqual(ms.MS_CLIENT_WORD["Slipped"], "Expected later")
        self.assertEqual(ms.MS_CLIENT_WORD["Overdue"], "Late")
        self.assertEqual({s: ms.client_word(s) for s in ms.STATES},
                         {"Achieved": "Achieved", "On track": "On track", "At risk": "At risk", "Slipped": "Expected later",
                          "Overdue": "Late", "Forecast": "Forecast"})


class Slip(unittest.TestCase):
    def test_a_later_forecast(self):
        self.assertEqual(ms.slip_days(row(baseline_date="2026-11-30", forecast_date="2026-12-14"), ON), 14)

    def test_on_time_or_early_is_zero(self):
        self.assertEqual(ms.slip_days(row(baseline_date="2026-11-30", forecast_date="2026-11-30"), ON), 0)
        self.assertEqual(ms.slip_days(row(baseline_date="2026-11-30", forecast_date="2026-11-16"), ON), 0)

    def test_no_forecast(self):
        self.assertEqual(ms.slip_days(row(baseline_date="2026-11-30"), ON), 0, "not due yet")
        self.assertEqual(ms.slip_days(row(baseline_date="2026-10-21"), ON), 7, "overdue: the days since the agreed date")

    def test_overdue_counts_to_today_or_the_later_forecast(self):
        self.assertEqual(ms.slip_days(row(baseline_date="2026-10-21", forecast_date="2026-10-25"), ON), 7)
        self.assertEqual(ms.slip_days(row(baseline_date="2026-10-21", forecast_date="2026-11-04"), ON), 14)

    def test_only_planned_milestones_with_an_agreed_date(self):
        self.assertIsNone(ms.slip_days(row(forecast_date="2026-12-01"), ON))
        for status in ("Done", "Cancelled"):
            self.assertIsNone(ms.slip_days(row(status=status, baseline_date="2026-10-01"), ON))


class Original(unittest.TestCase):
    def change(self, apply_id, new, item="DEMO-M-001", field="baseline_date", op="update", tbl="milestones"):
        return {"apply_id": apply_id, "tbl": tbl, "item_id": item, "field": field, "op": op, "old_value": None,
                "new_value": new}

    def test_the_first_agreed_date_in_change_log(self):
        log = [self.change(1, "2026-11-01", op="insert"), self.change(2, "2026-11-15"), self.change(3, "2026-11-30")]
        self.assertEqual(ms.original_date(log, "DEMO-M-001", current="2026-11-30"), "2026-11-01")

    def test_undone_applies_and_undo_rows_are_skipped(self):
        log = [self.change(1, "2026-10-15"), self.change(2, "2026-10-20", op="undo"), self.change(3, "2026-11-01")]
        self.assertEqual(ms.original_date(log, "DEMO-M-001", current="2026-11-30", undone={1}), "2026-11-01")

    def test_other_items_fields_and_tables_are_ignored(self):
        log = [self.change(1, "2026-09-01", item="DEMO-M-002"), self.change(1, "2026-09-02", field="forecast_date"),
               self.change(1, "2026-09-03", tbl="actions"), self.change(1, None), self.change(2, "2026-11-01")]
        self.assertEqual(ms.original_date(log, "DEMO-M-001"), "2026-11-01")

    def test_with_no_history_it_is_the_current_date(self):
        self.assertEqual(ms.original_date([], "DEMO-M-001", current="2026-11-30"), "2026-11-30")
        self.assertIsNone(ms.original_date([], "DEMO-M-001"))


if __name__ == "__main__":
    unittest.main()
