"""Row 1314: the Classic Work items page as the prototype draws it, in the Classic theme layer only.

Run: python3 dev/run_tests.py test_work_items_classic_1314
Covers the filter underline, the joined square layout pair with a grey chosen half, and the heading hairlines. Cards (shell.css) must not carry any of it.
"""
import re
import unittest

from _paths import ROOT

RULES = (ROOT / "src" / "clark" / "themes" / "prototype-2.0" / "rules.css").read_text(encoding="utf-8")
SHELL = (ROOT / "src" / "clark" / "page" / "shell.css").read_text(encoding="utf-8")


def block(selector):
    m = re.search(r"^" + re.escape(selector) + r" \{(.*?)\}$", RULES, re.M)
    assert m, selector
    return m.group(1)


class ClassicRules(unittest.TestCase):
    def test_filter_line_is_underline_only(self):
        b = block(".fline")
        self.assertIn("border: 0;", b)
        self.assertIn("border-bottom: 1px solid var(--grey-200)", b)
        self.assertIn("border-radius: 0", b)
        self.assertIn("background: none", b)
        self.assertIn("margin-right: 0", block(".fline-tail"))

    def test_layout_pair_is_square_and_chosen_half_is_grey_not_aqua(self):
        self.assertIn("border-radius: var(--radius-sm)", block(".vicons .lsw, .vicons .btn.sm.vgb"))
        b = block('.vicons .lsw button[aria-pressed="true"]')
        self.assertIn("background-color: var(--grey-100)", b)
        self.assertIn("background-image: none", b)
        self.assertIn("outline-offset: -2px", block('.vicons .lsw button[aria-pressed="true"]:focus-visible'))

    def test_heading_has_hairlines_between_columns_only(self):
        b = block("table.items thead th + th, .wil-table thead th + th")
        self.assertIn("border-left: 1px solid var(--grey-200)", b)

    def test_only_tokens(self):
        for sel in (".fline", ".fline-tail", ".vicons .lsw, .vicons .btn.sm.vgb", "table.items thead th + th, .wil-table thead th + th"):
            self.assertNotRegex(block(sel), r"#[0-9a-fA-F]{3,6}\b")

    def test_cards_stylesheet_has_none_of_it(self):
        self.assertNotIn("Row 1314", SHELL)
        self.assertNotIn("table.items thead th + th", SHELL)


if __name__ == "__main__":
    unittest.main()
