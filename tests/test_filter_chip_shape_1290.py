"""Item 1290: the filter chips on Work items are a rounded rectangle in the loaded brand colours (not a pill, not the fixed blue tint).
The cross takes the chip's text colour and its hover square follows the chip's corner. Plain-word chips keep the grey fill.
Reads the shipped shell.css rules, so it needs no browser.

Run: python3 dev/run_tests.py test_filter_chip_shape_1290
"""
import re
import unittest
from pathlib import Path

CSS_DIR = Path(__file__).resolve().parent.parent / "src" / "clark" / "page"
CSS = (CSS_DIR / "shell.css").read_text(encoding="utf-8")


def rule(selector):
    m = re.search(r"^" + re.escape(selector) + r" \{([^}]*)\}", CSS, re.M)
    assert m, selector
    return m.group(1)


class FilterChipShape(unittest.TestCase):
    def test_the_chip_is_a_rounded_rectangle_not_a_pill(self):
        body = rule(".fchip")
        self.assertIn("border-radius: 6px", body)
        self.assertNotIn("radius-pill", body)

    def test_the_chip_takes_the_brand_tint_and_brand_text(self):
        body = rule(".fchip")
        self.assertIn("background: var(--brand-blue-tint)", body)
        self.assertRegex(body, r"color: var\(--brand-blue\)")
        self.assertNotIn("status-blue", body)

    def test_the_cross_follows_the_chip_colour_and_corner(self):
        body = rule(".fchip button")
        self.assertIn("all: unset", body, "colour is inherited from the chip")
        self.assertNotRegex(body, r"(?<!-)color:")
        self.assertIn("border-radius: var(--radius-sm)", body)
        self.assertNotIn("50%", body)

    def test_the_chip_stays_about_25_tall(self):
        self.assertIn("min-height: 25px", rule(".fchip"))

    def test_the_chip_padding_and_cross_follow_the_mock_up(self):
        self.assertIn("padding: 0 var(--space-1) 0 9px", rule(".fchip"))
        body = rule(".fchip button")
        self.assertIn("width: 24px", body)       # the hit box stays 24 px
        self.assertIn("height: 24px", body)
        self.assertIn("padding: 1px", body)      # so the cross is drawn 22 px inside it
        self.assertIn("background-clip: content-box", body)

    def test_a_plain_word_chip_stays_grey(self):
        body = rule(".fchip.word")
        self.assertIn("background: var(--grey-100)", body)
        self.assertIn("color: var(--text)", body)

    def test_the_published_page_chip_only_changes_its_padding_and_cross_size(self):
        self.assertEqual(rule(".factive.pub .fchip").count(":"), 1)
        self.assertIn("padding:", rule(".factive.pub .fchip"))
        self.assertNotRegex(rule(".factive.pub .fchip button"), r"radius|color|background")

    def test_all_three_chip_producers_use_the_one_chip_class_with_no_own_look(self):
        src = CSS_DIR / "src" / "components"
        for name, count in (("WorkItems.jsx", 2), ("FilterLine.jsx", 1)):
            text = (src / name).read_text(encoding="utf-8")
            tags = re.findall(r"<span class=\"fchip\"[^>]*>", text)
            self.assertEqual(len(tags), count, name)
            for tag in tags:
                self.assertNotIn("style=", tag)


if __name__ == "__main__":
    unittest.main()
