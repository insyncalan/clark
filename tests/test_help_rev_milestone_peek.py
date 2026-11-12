"""Help review of the milestone-peek section: it says what the peek has today (source: edit/MilestonePeek.jsx, components/Peek.jsx).

Run: python3 dev/run_tests.py test_help_rev_milestone_peek
No browser: it reads src/clark/page/src/help/helpContent.json.
"""
import json
import pathlib
import unittest

HELP = pathlib.Path(__file__).resolve().parent.parent / "src/clark/page/src/help/helpContent.json"


def section():
    data = json.loads(HELP.read_text(encoding="utf-8"))
    found = []

    def walk(o):
        if isinstance(o, dict):
            if o.get("id") == "milestone-peek":
                found.append(o)
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(data)
    assert len(found) == 1
    return json.dumps(found[0], ensure_ascii=False)


class MilestonePeekHelp(unittest.TestCase):
    def test_no_parts_the_peek_does_not_have(self):
        t = section()
        for gone in ("The chips", "Rebaseline", "Linked work items", "the eye and the archive picture",
                     "why it has the one it has", "days later than agreed", "Across the whole screen", "Close, "):
            self.assertNotIn(gone, t)

    def test_top_bar_uses_the_buttons_own_names(self):
        t = section()
        for name in ("Previous item", "Next item", "Make this panel fill the screen", "Close this panel", "Archive"):
            self.assertIn(name, t)

    def test_rows_match_the_peek(self):
        t = section()
        for row in ("Name", "Owner", "Agreed date", "Forecast date", "Achieved on", "State", "Progress",
                    "Description", "Workstream", "Visible to client", "Client wording"):
            self.assertIn(row, t)

    def test_states_and_tabs(self):
        t = section()
        for w in ("Forecast, On track, At risk, Slipped, Overdue and Achieved", "Activity"):
            self.assertIn(w, t)


if __name__ == "__main__":
    unittest.main()
