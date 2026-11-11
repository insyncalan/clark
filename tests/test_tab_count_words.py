"""A saved view's tab names its count in plain words: "1 item", never "1 items" (a screen reader says the aria-label). Quick tier: reads files."""
import unittest

from _paths import ROOT

SRC = (ROOT / "src" / "clark" / "page" / "src" / "components" / "FilterLine.jsx").read_text(encoding="utf-8")


class TabCountWords(unittest.TestCase):
    def test_the_tab_label_has_no_fixed_plural(self):
        self.assertNotIn("${count} items", SRC)

    def test_the_tab_label_says_item_for_one(self):
        self.assertIn('count === 1 ? "item" : "items"', SRC)


if __name__ == "__main__":
    unittest.main()
