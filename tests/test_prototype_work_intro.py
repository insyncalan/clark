"""Item 1006: the prototype's Work items page has no 'Select an item to open it beside the list' line.

The build dropped it in 1.0.3 (item 805); the prototype under system/prototype now matches.
Run: python3 dev/run_tests.py test_prototype_work_intro
"""
import re
import unittest

import _paths  # noqa: F401
from _paths import ROOT


class PrototypeWorkIntro(unittest.TestCase):
    def test_no_prototype_source_carries_the_intro_line(self):
        for p in sorted((ROOT / "system/prototype").glob("*.js")):
            text = p.read_text(encoding="utf-8")
            self.assertNotIn("Select an item to open it beside", text, p.name)
            self.assertNotIn("shows or hides it from the client", text, p.name)

    def test_work_items_head_is_the_title_alone(self):
        text = (ROOT / "system/prototype/views.js").read_text(encoding="utf-8")
        self.assertRegex(text, re.escape('<div class="head"><div><h1>Work items</h1></div>'))


if __name__ == "__main__":
    unittest.main()
