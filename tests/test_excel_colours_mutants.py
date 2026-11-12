"""Mutation-kill tests for src/clark/excel_colours.py: every value table pinned cell by cell (a flipped colour in any one is caught), the
late rule's edges, and hostile cell values (the cell text is user text). Run from tests/: python3 -m unittest test_excel_colours_mutants"""
import unittest
from datetime import date

from _paths import SRC  # noqa: F401

from clark import excel_colours as ec, look

TODAY = date(2026, 11, 11)

EXPECTED = {
    ("actions", "priority"): {"Urgent": "red", "High": "amber", "Medium": "grey", "Low": "grey"},
    ("raid", "priority"): {"Urgent": "red", "High": "red", "Medium": "amber", "Low": "green"},
    ("actions", "status"): {"Open": "green", "Delayed": "amber", "Closed": "blue", "Cancelled": "grey"},
    ("raid", "status"): {"Open": "green", "Closed": "blue", "Cancelled": "grey"},
    ("raid", "impact"): {"High": "red", "Medium": "amber", "Low": "green"},
    ("raid", "likelihood"): {"High": "red", "Medium": "amber", "Low": "green"},
    ("milestones", "shown_state"): {"Achieved": "green", "On track": "green", "At risk": "amber", "Slipped": "red",
                                    "Overdue": "red", "Forecast": "blue"},
    ("milestones", "state"): {"Achieved": "green", "On track": "green", "At risk": "amber", "Slipped": "red",
                              "Overdue": "red", "Forecast": "blue"},
    ("decisions", "status"): {"Pending": "green", "Made": "blue", "Withdrawn": "grey"},
    ("use_cases", "status"): {"On track": "green", "Flag": "amber", "High risk": "red", "Done": "grey"},
}


class Tables(unittest.TestCase):
    def test_every_value_has_exactly_its_colour(self):
        for (table, field), values in EXPECTED.items():
            for value, colour in values.items():
                self.assertEqual(ec.colour_for(table, field, value), colour, (table, field, value))

    def test_no_field_has_a_value_the_pin_does_not_know(self):
        self.assertEqual(set(ec.BY_FIELD), set(EXPECTED))
        for key, values in ec.BY_FIELD.items():
            self.assertEqual(values, EXPECTED[key], key)

    def test_the_late_rules_are_these_and_no_others(self):
        self.assertEqual(ec.LATE, {("actions", "due_date"): ("status", {"Open", "Delayed"}),
                                   ("raid", "due_date"): ("status", {"Open"}),
                                   ("decisions", "needed_by"): ("status", {"Pending"})})

    def test_every_colour_is_fill_tint_then_text_and_the_header_and_late_tokens_are_the_looks(self):
        for name in ("red", "amber", "green", "blue", "grey"):
            self.assertEqual(ec.COLOURS[name], ("tone-%s-tint" % name, "tone-%s-text" % name))
            self.assertEqual(ec.hexes(name), (look.colour("tone-%s-tint" % name), look.colour("tone-%s-text" % name)))
        self.assertEqual(ec.HEADER_FILL, look.colour("brand-navy"))
        self.assertEqual(ec.HEADER_TEXT, look.colour("white"))
        self.assertEqual(ec.LATE_TEXT, look.colour("tone-red-text"))
        with self.assertRaises(KeyError):
            ec.hexes("purple")


class Late(unittest.TestCase):
    def late(self, table, field, status, when, status_field=None):
        sf = status_field or ec.LATE[(table, field)][0]
        return ec.is_late(table, field, {sf: status, field: when}, TODAY)

    def test_before_today_is_late_today_and_after_are_not(self):
        self.assertTrue(self.late("actions", "due_date", "Open", "2026-11-10"))
        self.assertFalse(self.late("actions", "due_date", "Open", "2026-11-11"))
        self.assertFalse(self.late("actions", "due_date", "Open", "2026-11-12"))

    def test_only_the_open_states_of_each_table_count(self):
        for (table, field), (_, open_states) in ec.LATE.items():
            for status in ("Open", "Delayed", "Pending", "Closed", "Made", "Cancelled", "Withdrawn", ""):
                self.assertEqual(self.late(table, field, status, "2000-01-01"), status in open_states, (table, status))

    def test_a_field_with_no_rule_is_never_late(self):
        self.assertFalse(ec.is_late("actions", "created", {"status": "Open", "created": "2000-01-01"}, TODAY))
        self.assertFalse(ec.is_late("nope", "due_date", {"status": "Open", "due_date": "2000-01-01"}, TODAY))
        self.assertFalse(ec.is_late("raid", "needed_by", {"status": "Open", "needed_by": "2000-01-01"}, TODAY))

    def test_a_missing_status_or_date_is_not_late(self):
        self.assertFalse(ec.is_late("actions", "due_date", {"due_date": "2000-01-01"}, TODAY))
        self.assertFalse(ec.is_late("actions", "due_date", {"status": "Open"}, TODAY))
        self.assertFalse(ec.is_late("actions", "due_date", {}, TODAY))


class Hostile(unittest.TestCase):
    def test_a_cell_that_is_not_text_has_no_colour_and_never_raises(self):
        for value in (None, 1, 1.5, True, b"Open", ["Open"], {"Open": 1}, ("Open",), {"a"}, object()):
            for table, field in ec.BY_FIELD:
                self.assertIsNone(ec.colour_for(table, field, value), repr(value))

    def test_text_that_only_looks_like_a_status_has_no_colour(self):
        for value in ("", " ", "open", "OPEN", " Open", "Open ", "Open\n", "Open\x00", "Ope​n", "Ｏpen", "Open;", "Open'--",
                      "<b>Open</b>", "=Open", "Op" * 5000, "Urgent\u0000", "high", "HIGH"):
            for table, field in ec.BY_FIELD:
                self.assertIsNone(ec.colour_for(table, field, value), repr(value)[:30])

    def test_an_unknown_table_or_field_has_no_colour(self):
        for table, field in (("", ""), ("nope", "status"), ("actions", "nope"), (None, None), ("actions", None), ("Actions", "status")):
            self.assertIsNone(ec.colour_for(table, field, "Open"))

    def test_a_status_that_is_not_text_is_never_open_and_never_raises(self):
        for status in (None, 1, ["Open"], {"Open"}, {"a": 1}, ("Open",), b"Open", float("nan")):
            self.assertFalse(ec.is_late("actions", "due_date", {"status": status, "due_date": "2000-01-01"}, TODAY), repr(status))

    def test_a_date_that_is_not_a_date_is_never_late_and_never_raises(self):
        for when in (None, 5, 20001231, [], {}, "", " ", "tomorrow", "2000-13-01", "2000-02-30", "0000-00-00", "11/10/2026",
                     "2000-01-01\x00", "9" * 5000, "２０２６-１１-１０", "2026-11-10T00:00:00Z", b"2000-01-01"):
            self.assertFalse(ec.is_late("actions", "due_date", {"status": "Open", "due_date": when}, TODAY), repr(when)[:30])

    def test_the_far_past_and_far_future_compare_as_dates(self):
        self.assertTrue(ec.is_late("actions", "due_date", {"status": "Open", "due_date": "0001-01-01"}, TODAY))
        self.assertFalse(ec.is_late("actions", "due_date", {"status": "Open", "due_date": "9999-12-31"}, TODAY))


if __name__ == "__main__":
    unittest.main()
