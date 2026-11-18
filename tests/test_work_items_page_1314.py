"""Row 1314: the Classic Work items page as the prototype draws it (filter underline, joined square layout pair, violet + New view,
heading hairlines, Priority pill, tabs that wrap at 900 px and below).

Run: python3 dev/run_tests.py test_work_items_page_1314
Each rule is pinned by the last rule that sets the property for the selector, so a change that is taken out fails the test.
"""
import re
import unittest

from _paths import SRC

CSS = (SRC / "clark" / "page" / "shell.css").read_text(encoding="utf-8")
BLOCK = CSS[CSS.index("Row 1314"):]


def last(selector):
    """The body of the last rule in the row 1314 block whose selector list is exactly `selector`."""
    found = re.findall(r"(?:^|\n)" + re.escape(selector) + r"\s*\{([^}]*)\}", BLOCK)
    assert found, selector
    return found[-1]


class Rules(unittest.TestCase):
    def test_the_filter_line_is_an_underline_only(self):
        r = last(".fline")
        self.assertIn("border-width: 0 0 1px", r)
        self.assertIn("border-radius: 0", r)
        self.assertIn("background: none", r)

    def test_the_layout_pair_is_joined_and_square_and_not_aqua(self):
        self.assertIn("border-radius: var(--radius-sm)", last(".vicons .seg.lsw"))
        on = last('.vicons .seg.lsw button[aria-pressed="true"]')
        self.assertIn("background-image: none", on)
        self.assertNotIn("pill", on)
        self.assertIn("border-radius: var(--radius-sm)", last(".btn.sm.vgb"))

    def test_new_view_is_violet_and_medium(self):
        r = last(".vnew")
        self.assertIn("color: var(--status-blue-text)", r)
        self.assertIn("font-weight: var(--weight-medium)", r)

    def test_the_table_heading_has_hairlines_between_columns_only(self):
        r = last("table.items thead th + th, .wil-table thead th + th")
        self.assertIn("border-left: 1px solid var(--grey-200)", r)

    def test_priority_is_a_pill(self):
        self.assertIn("border-radius: var(--radius-pill)", last(".wil-pr"))

    def test_tabs_wrap_at_900_and_below(self):
        m = re.search(r"@media \(max-width: 900px\) \{\s*\.vtabs \{([^}]*)\}", BLOCK)
        self.assertTrue(m)
        self.assertIn("flex-wrap: wrap", m.group(1))
        self.assertIn("overflow: visible", m.group(1))

    def test_nothing_added_uses_a_bare_colour_or_looping_animation(self):
        self.assertNotRegex(BLOCK, r"#[0-9a-fA-F]{3,6}\b")
        self.assertNotIn("infinite", BLOCK)


if __name__ == "__main__":
    unittest.main()
