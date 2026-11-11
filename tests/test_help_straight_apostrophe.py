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


if __name__ == "__main__":
    unittest.main()
