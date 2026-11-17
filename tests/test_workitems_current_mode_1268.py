"""Row 1268, mutation checks: the "current" mode of a Work items list (section_kinds/workitems.py) and the letter-tile header.

Run: python3 dev/run_tests.py test_workitems_current_mode_1268
"""
import unittest

from _paths import SRC

from clark.section_kinds import workitems


def dec(n, status, due):
    return {"id": f"D-{n}", "kind": "decision", "status": status, "due": due, "owner": "", "workstream": "", "priority": ""}


class Current(unittest.TestCase):
    def ids(self, rows):
        v = workitems.check({"mode": "current", "kinds": ["decision"], "max": 50}, {})
        return set(workitems.matching(v, rows, "2026-10-28"))

    def test_a_decision_made_today_counts_and_one_made_in_the_future_does_not(self):      # mutation check: 0 <= t - a
        got = self.ids([dec(1, "Made", "2026-10-28"), dec(2, "Made", "2026-10-29"), dec(3, "Made", "2026-10-14"), dec(4, "Made", "2026-10-13")])
        self.assertEqual(got, {"D-1", "D-3"})


class Header(unittest.TestCase):
    def test_the_letter_tile_column_has_a_name_for_a_screen_reader(self):      # mutation check: aria-label on the tile header
        src = (SRC / "clark" / "page" / "src" / "templates" / "WorkItemsList.jsx").read_text(encoding="utf-8")
        self.assertIn('<th class="wil-c-tile" scope="col" aria-label={WORDS.columns.type} />', src)


if __name__ == "__main__":
    unittest.main()
