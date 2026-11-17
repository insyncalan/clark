"""Item 1290: the published-page chip cross keeps the 24 px hit box, the cross hover fill stays grey-200, and the drawn cross box is border-box.
Reads the shipped shell.css rules, so it needs no browser.

Run: python3 dev/run_tests.py test_filter_chip_hitbox_1290
"""
import re
import unittest
from pathlib import Path

CSS = (Path(__file__).resolve().parent.parent / "src" / "clark" / "page" / "shell.css").read_text(encoding="utf-8")


def rule(selector):
    m = re.search(r"^" + re.escape(selector) + r" \{([^}]*)\}", CSS, re.M)
    assert m, selector
    return m.group(1)


class FilterChipHitBox(unittest.TestCase):
    def test_the_published_page_cross_hit_box_is_24(self):
        body = rule(".factive.pub .fchip button")
        self.assertIn("width: 24px", body)
        self.assertIn("height: 24px", body)

    def test_the_cross_hover_fill_is_grey_200(self):
        self.assertIn("background: var(--grey-200)", rule(".fchip button:hover"))

    def test_the_cross_box_is_border_box_so_padding_stays_inside_24(self):
        self.assertIn("box-sizing: border-box", rule(".fchip button"))


if __name__ == "__main__":
    unittest.main()
