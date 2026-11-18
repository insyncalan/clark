"""Row 1314 (filters part): the filters strip of the Work items page in the Classic theme, as the prototype draws it.

Run: python3 dev/run_tests.py test_filters_strip_1314
Rules are read from the Classic theme's rules.css: an underline-only filter line, a joined square List/Board pair with a grey chosen half,
a violet + New view, and tabs that wrap at 900 px and below.
"""
import re
import unittest

from _paths import ROOT

RULES = (ROOT / "src" / "clark" / "themes" / "prototype-2.0" / "rules.css").read_text(encoding="utf-8")


def block(selector):
    m = re.search(r"^" + re.escape(selector) + r" \{(.*?)\}$", RULES, re.M)
    assert m, selector
    return m.group(1)


class FiltersStrip(unittest.TestCase):
    def test_filter_line_is_underline_only(self):
        b = block(".fline")
        self.assertIn("border: 0;", b)
        self.assertIn("border-bottom: 1px solid var(--grey-200)", b)
        self.assertIn("border-radius: 0", b)
        self.assertIn("background: none", b)

    def test_view_buttons_are_square_and_chosen_is_not_aqua(self):
        self.assertIn("border-radius: var(--radius-sm)", block(".vicons .lsw, .vicons .btn.sm.vgb"))
        b = block('.vicons .lsw button[aria-pressed="true"]')
        self.assertIn("background-image: none", b)
        self.assertNotIn("pill", b)

    def test_new_view_is_violet(self):
        b = block(".vnew")
        self.assertIn("color: var(--status-blue-text)", b)
        self.assertIn("font-weight: var(--weight-medium)", b)

    def test_tabs_wrap_at_900(self):
        m = re.search(r"@media \(max-width: 900px\) \{ \.vtabs \{([^}]*)\} \.fvrow \{([^}]*)\} \}", RULES)
        self.assertTrue(m)
        self.assertIn("flex-wrap: wrap", m.group(1))
        self.assertIn("overflow: visible", m.group(1))
        self.assertIn("flex-wrap: wrap", m.group(2))


if __name__ == "__main__":
    unittest.main()
