"""Row 1354: the chosen cell of the Milestones switches takes the prototype 2.0 values (index.html lines 189-193).

Run: python3 dev/run_tests.py test_theme_milestones_switch_1354
Pins the text of the Row 1354 block of rules.css: navy with white text in light, #2b3850 in dark, and no ring, border, outline or shadow (the prototype has none).
"""
import unittest

from _paths import ROOT

FOLDER = ROOT / "src" / "clark" / "themes" / "prototype-2.0"
RULES = (FOLDER / "rules.css").read_text(encoding="utf-8")
TOKENS = (FOLDER / "tokens.css").read_text(encoding="utf-8")
MARK = "/* Row 1354"
BLOCK = RULES[RULES.index(MARK):].split("\n/* Row ", 1)[0] + "\n"
SEL = '.msv-sw .msv-b[aria-current="true"], .mv-txt button[aria-current="true"]'
DSEL = ', '.join(':root[data-theme=%s] ' + p.strip() for p in SEL.split(",")).replace('%s', '{0}')
DARK = ' { background: var(--grey-200); }'



class Row1354(unittest.TestCase):
    def test_light_is_navy_with_white_text(self):
        self.assertIn(SEL + ' { background: var(--brand-navy); color: var(--white); }', BLOCK)

    def test_dark_is_2b3850_no_edge_in_dark_and_auto(self):
        self.assertIn(DSEL.format("dark") + DARK, BLOCK)
        self.assertIn('@media (prefers-color-scheme: dark) { ' + DSEL.format("auto") + DARK + ' }', BLOCK)
        self.assertIn("--grey-200: #2B3850", TOKENS)

    def test_nothing_else_and_before_row_1314(self):
        rules = BLOCK.split("*/", 1)[1]
        for word in ("outline", "border", "box-shadow"):
            self.assertNotIn(word, rules)
        self.assertLess(RULES.index(MARK), RULES.index("/* Row 1314"))
        self.assertEqual(RULES.count("/* Row 1314"), 1)


if __name__ == "__main__":
    unittest.main()
