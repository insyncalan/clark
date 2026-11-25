"""Row 1205, Help words, part c: the peek top line names Delete, the Details entry names the open decision rows, and the milestone peek help keeps its words.

Run: python3 dev/run_tests.py test_help_1205_words_c
Quick tier: reads helpContent.json, starts no browser.
"""
import json
import unittest

from _paths import SRC

HELP = SRC / "clark" / "page" / "src" / "help" / "helpContent.json"


def every_string(node):
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for v in node.values():
            yield from every_string(v)
    elif isinstance(node, list):
        for v in node:
            yield from every_string(v)


STRINGS = list(every_string(json.loads(HELP.read_text(encoding="utf-8"))))
TEXT = "\n".join(STRINGS)


class Words(unittest.TestCase):
    def test_peek_top_menu_names_delete(self):
        new = "a menu of actions for this item: **Duplicate**, **Archive** and **Delete**, then"
        self.assertEqual(TEXT.count(new), 1)
        self.assertNotIn("such as **Duplicate**", TEXT)

    def test_details_entry_open_decision_rows(self):
        line = next(t for t in STRINGS if t.startswith("**Details** (in Edit a tab, with Activity"))
        self.assertIn("a decision has its own rows instead; an open decision also has Raised and Last reviewed. Status,", line)

    def test_milestone_peek_names_achieved_on_and_use_case(self):
        line = next(t for t in STRINGS if t.startswith("**Dates**: Agreed (the baseline)"))
        self.assertIn("an Achieved on date, a row in Edit", line)
        rows = next(t for t in STRINGS if t.startswith("**The rows**: in Edit, Description, Agreed date"))
        self.assertIn("Workstream, Use case and Client wording", rows)

    def test_milestone_peek_state_buttons_edit_only_view_chip(self):
        state = next(t for t in STRINGS if t.startswith("**State**: Forecast, On track, At risk, Slipped, Overdue"))
        self.assertIn("In Edit the State chip opens the five you can pick", state)
        under = next(t for t in STRINGS if t.startswith("**Under the title**"))
        self.assertIn("in View and in a published file, the header line with the state", under)


if __name__ == "__main__":
    unittest.main()
