"""Hostile tests for row 1021: odd statuses, odd dates, odd types and the old/new colour crossing in the Word and Excel copies.

Run: python3 dev/run_tests.py test_hostile_1021
"""
import unittest

from _paths import SRC  # noqa: F401  (puts src/ on the path)

from clark import docx_build, excel_colours, glance

TODAY = "2026-10-28"


def ctx():
    return docx_build._Ctx(excel_colours.TOKENS, TODAY)


def status(row, kind):
    body, fill = docx_build._status_cell(row, kind, ctx())
    return body, fill


class OddInputs(unittest.TestCase):
    def test_odd_rows_never_raise_and_always_say_a_word(self):
        odd = [None, "", " ", "Open‮", "\U0001F525" * 50, "x" * 100000, "<w:b/>&", 7, [], {}, "closed", "CLOSED"]
        for st in odd:
            for due in (None, "", "2026-02-30", "0000-00-00", "2026-10-28\n", "9999-12-31", "x" * 5000, 20261028):
                for pr in (None, "", "Urgent", "urgent", "High", 5):
                    for kind in ("action", "risk", "issue", "assumption", "", "ACTION"):
                        row = {"status": st, "priority": pr, "due_date": due}
                        try:
                            body, _fill = status(row, kind)
                        except Exception as e:      # noqa: BLE001
                            self.fail(f"raised {e!r} for {row} {kind}")
                        self.assertIsInstance(body, str)

    def test_markup_in_status_is_escaped_for_other_raid_types(self):
        body, _ = status({"status": "<w:b/>&\x00\x0b done"}, "assumption")
        self.assertNotIn("<w:b/>&", body.replace("&lt;w:b/&gt;&amp;", ""))
        self.assertNotIn("\x00", body)

    def test_unknown_priority_is_not_urgent_and_not_maroon(self):
        for pr in ("urgent", "URGENT", " Urgent", "Urgent "):
            _, fill = status({"status": "Open", "priority": pr, "due_date": "2026-12-31"}, "action")
            self.assertNotEqual(fill, excel_colours.TOKENS["tone-urgent"], pr)


class OutOfOrder(unittest.TestCase):
    def test_same_row_twice_and_after_a_different_row_is_the_same(self):
        c = ctx()
        a = {"status": "Open", "priority": "Urgent", "due_date": "2020-01-01"}
        b = {"status": "Closed", "priority": "Urgent", "due_date": "2020-01-01"}
        first = docx_build._status_cell(a, "action", c)
        docx_build._status_cell(b, "action", c)
        self.assertEqual(first, docx_build._status_cell(a, "action", c))

    def test_urgent_closed_action_does_not_read_as_urgent_maroon(self):
        """A closed Urgent action must read Closed (blue), not the maroon open tile."""
        _, fill = status({"status": "Closed", "priority": "Urgent", "due_date": "2020-01-01"}, "action")
        self.assertNotEqual(fill, excel_colours.TOKENS["tone-urgent"])

    def test_cancelled_urgent_does_not_read_as_urgent_maroon(self):
        body, fill = status({"status": "Cancelled", "priority": "Urgent"}, "risk")
        self.assertNotEqual(fill, excel_colours.TOKENS["tone-urgent"])
        self.assertIn("Cancelled", body)


class OldNewCrossing(unittest.TestCase):
    def test_every_colour_name_resolves_to_a_tone_token_in_both_copies(self):
        for name, (fill, text) in excel_colours.COLOURS.items():
            self.assertTrue(fill.startswith("tone-") and text.startswith("tone-"), name)
            self.assertIn(fill, excel_colours.TOKENS)
            self.assertIn(text, excel_colours.TOKENS)

    def test_status_tables_only_name_colours_that_exist(self):
        for table in (excel_colours.ACTION_STATUS, excel_colours.RAID_STATUS, excel_colours.DECISION_STATUS):
            for word, colour in table.items():
                self.assertIn(colour, excel_colours.COLOURS, word)

    def test_client_pill_is_the_only_place_open_becomes_on_track(self):
        today = TODAY
        for kind in ("risk", "issue", "decision", "assumption", "dependency"):
            p = glance.client_pill({"kind": kind, "status": "Open", "priority": "Low"}, today)
            self.assertNotEqual(p["text"], "On track", kind)
        self.assertEqual(glance.client_pill({"kind": "action", "status": "Open", "due_date": "2026-12-31"}, today)["text"], "On track")
        self.assertEqual(glance.client_pill({"kind": "action", "status": "Open", "due_date": "2026-11-04"}, today)["text"], "Due soon")
        self.assertEqual(glance.client_pill({"kind": "action", "status": "Open", "due_date": "2026-11-05"}, today)["text"], "On track")


if __name__ == "__main__":
    unittest.main()
