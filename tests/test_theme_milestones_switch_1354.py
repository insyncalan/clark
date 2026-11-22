"""Row 1354: the chosen cell of the Milestones switches takes the prototype 2.0 values (index.html lines 189-193).

Run: python3 dev/run_tests.py test_theme_milestones_switch_1354
Pins the text of the Row 1354 block of rules.css: navy with white text in light, #2b3850 in dark, and in dark only a 1px inset edge in --ui,
because #2b3850 against the --surface #121c28 beside it measures 1.46 to 1 (below 3 to 1). No other ring, border or outline.
"""
import unittest

from _paths import ROOT

FOLDER = ROOT / "src" / "clark" / "themes" / "prototype-2.0"
RULES = ((FOLDER / "rules.css").read_text(encoding="utf-8") + (FOLDER / "rules-2.css").read_text(encoding="utf-8"))
TOKENS = (FOLDER / "tokens.css").read_text(encoding="utf-8")
MARK = "/* Row 1354"
BLOCK = "\n".join(RULES[RULES.index(MARK):].split("\n")[:4]) + "\n"
SEL = '.msv-sw .msv-b[aria-current="true"], .mv-txt button[aria-current="true"]'
DSEL = ', '.join(':root[data-theme=%s] ' + p.strip() for p in SEL.split(",")).replace('%s', '{0}')
DARK = ' { background: var(--grey-200); box-shadow: inset 0 0 0 1px var(--grey-500); }'


def lum(h):
    c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    c = [x / 12.92 if x <= .03928 else ((x + .055) / 1.055) ** 2.4 for x in c]
    return .2126 * c[0] + .7152 * c[1] + .0722 * c[2]


class Row1354(unittest.TestCase):
    def test_light_is_navy_with_white_text(self):
        self.assertIn(SEL + ' { background: var(--brand-navy); color: var(--white); }', BLOCK)

    def test_dark_is_2b3850_with_a_1px_inset_ui_edge_in_dark_and_auto(self):
        self.assertIn(DSEL.format("dark") + DARK, BLOCK)
        self.assertIn('@media (prefers-color-scheme: dark) { ' + DSEL.format("auto") + DARK + ' }', BLOCK)
        self.assertIn("--grey-200: #2B3850", TOKENS)
        self.assertIn("--grey-500: #6F7FA3", TOKENS)

    def test_the_edge_is_needed_because_the_contrast_is_under_3_to_1(self):
        a, b = lum("#2b3850"), lum("#121c28")
        self.assertLess((max(a, b) + .05) / (min(a, b) + .05), 3.0)
        self.assertIn("--surface: #121C28", TOKENS)

    def test_nothing_else_and_before_row_1314(self):
        rules = BLOCK.split("*/", 1)[1]
        for word in ("outline", "border"):
            self.assertNotIn(word, rules)
        self.assertEqual(rules.count("box-shadow"), 2)
        self.assertLess(RULES.index(MARK), RULES.index("/* Row 1314"))
        self.assertEqual(RULES.count("/* Row 1314"), 1)


if __name__ == "__main__":
    unittest.main()
