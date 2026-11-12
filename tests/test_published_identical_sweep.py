"""Row 1066, mutation sweep: with no 'Needs from you' section that the editor shows, the flagged work items go nowhere at all:
nothing is listed, nothing counts as left out and nothing is logged, however many are flagged. When the editor has a hidden
'Needs from you' section and a shown one, the shown one gets the rows. Over a real store and the real build. Fictional data.

Run: python3 dev/run_tests.py test_published_identical_sweep
"""
import logging
import unittest

import _paths  # noqa: F401
from _demo import USER, DemoStore
from clark import publish, section_bodies

NOW = "2030-01-15"
SENTINEL = "ZQ-SENTINEL-1066"       # logged by the test itself, so assertLogs (Python 3.9: no assertNoLogs) always has one line


class NoSectionToList(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store

    def flag(self, n):
        with self.s.step("dashboard", USER) as st:
            for i in range(n):
                st.create("actions", {"project": "ABC", "description": "G%03d" % i, "client_message": "G%03d" % i, "raised": "2026-10-01",
                                      "source": "demo", "client_action": 1})

    def section(self, hidden, sort_order):
        with self.s.step("dashboard", USER) as st:
            return st.create("report_sections", {"project": "ABC", "type": section_bodies.NEEDS, "title": "Needs from you", "body": "",
                                                 "sort_order": sort_order, "beside": 0, "hidden": hidden})

    def built_quietly(self):
        """The build, and the warning lines it logged about the Needs from you list (none expected)."""
        with self.assertLogs("clark.publish", level="WARNING") as got:
            made = publish.build(self.s, "ABC", now=NOW)
            logging.getLogger("clark.publish").warning(SENTINEL)
        return made, [line for line in got.output if "Needs from you" in line]

    def needs_in(self, made):
        return [x for x in made["published"]["sections"] if x["type"] == "needs"]

    def test_with_no_needs_section_more_flagged_items_than_fit_are_not_counted_as_left_out(self):
        self.flag(section_bodies.NEEDS_MAX_ROWS + 3)
        made, lines = self.built_quietly()
        self.assertEqual(self.needs_in(made), [], "row 1066: no section is made for the file")
        self.assertEqual(lines, [], "nothing was left out of a list that is not in the file, so nothing is logged")

    def test_with_only_a_hidden_needs_section_more_flagged_items_than_fit_are_not_counted_as_left_out(self):
        self.section(hidden=1, sort_order=1)
        self.flag(section_bodies.NEEDS_MAX_ROWS + 3)
        made, lines = self.built_quietly()
        self.assertEqual(self.needs_in(made), [], "the owner's hidden section stays hidden")
        self.assertEqual(lines, [])

    def test_a_hidden_needs_section_before_a_shown_one_does_not_take_the_rows(self):
        self.section(hidden=1, sort_order=1)
        shown = self.section(hidden=0, sort_order=2)
        self.flag(2)
        made, lines = self.built_quietly()
        got = self.needs_in(made)
        self.assertEqual([x["id"] for x in got], [shown])
        self.assertEqual([r["what"] for r in got[0]["rows"]], ["G000", "G001"])
        self.assertEqual(lines, [])


if __name__ == "__main__":
    unittest.main()
