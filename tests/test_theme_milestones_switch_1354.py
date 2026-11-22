"""Row 1354: the chosen cell of the Milestones switches takes the prototype 2.0 values (index.html lines 189-193).

Run: python3 dev/run_tests.py test_theme_milestones_switch_1354
Pins the text of the Row 1354 block of rules.css: navy with white text in light, #2b3850 in dark, and in dark only a 1px inset edge in --ui,
because #2b3850 against the --surface #121c28 beside it measures 1.46 to 1 (below 3 to 1). No other ring, border or outline.
"""
import time
import unittest

from _paths import ROOT
from test_ms_timeline_classic_1315 import Base

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


OFF = """(() => {
  const probe = document.createElement('i'); probe.style.color = 'var(--grey-700)'; document.body.appendChild(probe);
  const want = getComputedStyle(probe).color; probe.remove();
  const all = [...document.querySelectorAll('#milestones .msv-sw .msv-b, #milestones .cal-sc button')];
  return { want: want, n: all.length, off: all.filter((b) => b.getAttribute('aria-current') !== 'true').map((b) => [b.textContent.trim(), getComputedStyle(b).color]),
           on: all.filter((b) => b.getAttribute('aria-current') === 'true').map((b) => getComputedStyle(b).color),
           frame: [...document.querySelectorAll('#milestones .msv-sw, #milestones .cal-sc')].map((e) => getComputedStyle(e).borderTopColor) };
})()"""


class Row1315Off(Base, unittest.TestCase):
    def test_off_state_text_is_grey_700_on_all_five_buttons(self):      # Row 1315 AP9: grey-500 as text is only 3.13 to 1, grey-700 is 7.41 to 1 in light
        for cdp, sid, w in self.every():
            time.sleep(0.8)      # the colour transition after the theme switch has finished
            g = cdp.js(OFF, sid)
            self.assertEqual(g["n"], 5, g)
            self.assertEqual([n for n, c in g["off"]], ["Calendar", "Week", "Quarter"], g)
            for name, colour in g["off"]:
                self.assertEqual(colour, g["want"], f"{name}: off-state text is var(--grey-700) at {w}")
            self.assertTrue(all(c == "rgb(255, 255, 255)" for c in g["on"]), "the chosen half keeps white text")
            self.assertEqual(len(set(g["frame"])), 1, "the frames keep their own colour (grey-500), not the text colour")
            self.assertNotEqual(g["frame"][0], g["want"], g)


if __name__ == "__main__":
    unittest.main()
