"""Help text uses the curly apostrophe everywhere, the milestone peek line uses it (other older lines still have the straight one) (item words-help-1335)."""
import json
import re
import unittest

from _paths import ROOT

HELP = ROOT / "src" / "clark" / "page" / "src" / "help" / "helpContent.json"


def _strings(x):
    if isinstance(x, str):
        yield x
    elif isinstance(x, list):
        for i in x:
            yield from _strings(i)
    elif isinstance(x, dict):
        for i in x.values():
            yield from _strings(i)


class StraightApostrophe(unittest.TestCase):
    def test_none_in_help(self):
        data = json.loads(HELP.read_text(encoding="utf-8"))
        bad = [s[:70] for s in _strings(data) if "milestone's" in s]
        self.assertEqual(bad, [])


    def test_no_straight_apostrophe_between_letters_in_any_help_sentence(self):
        """Every other Help sentence has the curly one too (item words-read-q24). The one exception mirrors the Disconnect card's own
        line, which the page spells with the straight one (test_help_shown pins that pair)."""
        data = json.loads(HELP.read_text(encoding="utf-8"))
        bad = [s[:70] for s in _strings(data) if re.search(r"[A-Za-z]'[a-z]", s) and "You're still signed in to" not in s]
        self.assertEqual(bad, [])


if __name__ == "__main__":
    unittest.main()
