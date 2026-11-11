"""needs_reason (src/clark/milestones.py) never raises on a hostile state: a list, a dict, a number or an unknown word.

Run: python3 dev/run_tests.py test_needs_reason_guard
Milestones are fictional demo rows.
"""
import unittest

from clark import milestones as ms

ON = "2026-10-28"


def row(**values):
    return {"id": "DEMO-M-001", "project": "DEMO", "name": "Pilot live", "status": "Planned", "baseline_date": "2026-10-01",
            "forecast_date": None, "state": None, "state_set": 1, "state_reason": None, **values}


class HostileState(unittest.TestCase):
    def test_non_string_states_are_false(self):
        for bad in (["On track"], {"a": 1}, 7, 1.5, True, ("At risk",), {"On track"}):
            with self.subTest(state=bad):
                self.assertIs(ms.needs_reason(row(state=bad), ON), False)

    def test_unknown_word_is_false(self):
        for bad in ("Stray", "on track", "At risk ", "__proto__"):
            with self.subTest(state=bad):
                self.assertIs(ms.needs_reason(row(state=bad), ON), False)

    def test_real_states_still_decide(self):
        self.assertTrue(ms.needs_reason(row(state="On track"), ON))
        self.assertFalse(ms.needs_reason(row(state="Overdue"), ON))


if __name__ == "__main__":
    unittest.main()
