"""Item 1007: the prototype's work item peek stays still after a dropdown choice.

A choice saves, the page refreshes and the peek is drawn again; the redraw keeps the scroll position
of the peek body and the focus on the field that had it.
Run: python3 dev/run_tests.py test_prototype_peek_still
"""
import unittest

import _paths  # noqa: F401
from _paths import ROOT


class PrototypePeekStill(unittest.TestCase):
    def setUp(self):
        self.text = (ROOT / "system/prototype/peek.js").read_text(encoding="utf-8")

    def test_redraw_remembers_the_scroll_and_the_focused_field(self):
        self.assertIn("scrollTop || 0", self.text)
        self.assertIn("a.tagName !== 'BUTTON' ? a.id", self.text)

    def test_redraw_puts_them_back(self):
        self.assertIn("s.scrollTop = keep.top", self.text)
        self.assertIn("f.focus({ preventScroll: true })", self.text)


if __name__ == "__main__":
    unittest.main()
