"""Row 1390, AP3 (DoD3): the Priority chip in Classic is the sheet's tone pair: Urgent maroon 6B1D2A with white text, High red F4DEDB with B3392F.
Medium and Low are not part of AP3 and are not pinned to a colour here (they keep the row 1409 pairs); they must still draw and differ. Measured as computed style in a real browser at 1400 and 900, light, on the
Work items page (#work) and in the Dashboard's work items list. The Cards theme is not pinned (item 1363).
Run: python3 dev/run_tests.py test_page_priority_chip_1390"""
import json
import re
import unittest
from pathlib import Path

import test_server  # noqa: F401  drives Chrome through the template harness
import test_tpl_workitems as T
import test_work_items_mockup_1195 as M
import _testpage as testpage
from _real_server import real_server
from clark import page, theme
from test_server import chrome
from test_report_editor import tearDownModule  # noqa: F401

LEVELS = {"Urgent": ("6B1D2A", "FFFFFF"), "High": ("F4DEDB", "B3392F")}
OTHERS = ("Medium", "Low")
COMBOS = {"Low": ("Low", "Low"), "Medium": ("Medium", "Low"), "High": ("High", "Medium"), "Urgent": ("High", "High")}
MEASURE = ("JSON.stringify(Object.fromEntries([...document.querySelectorAll(%s)].map((e) => { const s = getComputedStyle(e); return [e.textContent, [s.backgroundColor, s.color]]; })))")


def hexes(s):
    return "".join("%02X" % int(float(v)) for v in re.findall(r"[\d.]+", s)[:3])


def seed(test):
    for lv, (im, li) in COMBOS.items():
        with test.store.step("dashboard", T.USER) as st:
            st.create("raid", {"project": "ABC", "type": "Risk", "description": f"Chip {lv}", "raised": "2026-10-01", "source": "demo",
                               "impact": im, "likelihood": li, "owner": "Pat Demo"})


def check(test, got, where):
    test.assertEqual(set(got), set(LEVELS) | set(OTHERS), where)
    seen = {w: (hexes(got[w][0]), hexes(got[w][1])) for w in got}
    test.assertEqual(len(set(seen.values())), 4, f"{where}: four different looks {seen}")
    for word, (bg, fg) in LEVELS.items():
        test.assertEqual(seen[word], (bg, fg), f"{where}: {word} chip is {bg} with {fg}; all measured {seen}")


class OnThePage(M.Look):
    def test_page_priority_chip_matches_the_sheet(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                seed(self)
                p = self.show(cdp, width)
                p.js("location.hash = '#work&p=ABC&f=mode:all'")
                p.until("new Set([...document.querySelectorAll('#work .c-prio .wil-pr')].map((e) => e.textContent)).size > 3", "the page chips drew")
                check(self, json.loads(p.js(MEASURE % json.dumps("#work .c-prio .wil-pr"))), f"page {width}")


class OnTheDashboard(T.PageBase):
    add, show = T.InThePage.add, T.InThePage.show

    def setUp(self):
        super().setUp()
        T.plant(self)
        self.s.close()
        css = theme.css("prototype-2.0")
        self.s = real_server(self.store.path, self.store.data_for, page_html=lambda: page.layer_theme(testpage.html(), css), seam=self.seam)
        self.addCleanup(self.s.close)
        seed(self)
        with self.store.step("dashboard", T.USER) as st:
            text = st.create("report_sections", {"project": "ABC", "type": "text", "title": "Fictional notes", "sort_order": 1})
        self.ref = self.add({"mode": "all", "columns": ["id", "owner", "due", "status", "priority"], "max": 40}, after=text, beside=1)

    def test_page_priority_chip_matches_the_sheet(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.show(cdp, width)
                p.edit()
                sel = f"[data-id=\"{self.ref}\"] .wil-table td .wil-pr"
                p.until(f"new Set([...document.querySelectorAll('{sel}')].map((e) => e.textContent)).size > 3", "the chips drew")
                check(self, json.loads(p.js(MEASURE % json.dumps(sel))), f"dashboard {width}")


class Source(unittest.TestCase):
    def test_the_high_pair_sits_in_rules_2_before_row_1314_and_rules_1_does_not_name_it(self):
        base = Path(__file__).resolve().parent.parent / "src/clark/themes/prototype-2.0"
        two = (base / "rules-2.css").read_text(encoding="utf-8")
        self.assertIn("--pri-high-bg: var(--pri-high-sheet-bg); --pri-high-fg: var(--pri-high-sheet-fg);", two)
        self.assertLess(two.index("--pri-high-bg: var(--pri-high-sheet-bg)"), two.index("/* Row 1314"))
        dark = "--pri-high-bg: var(--status-red-tint); --pri-high-fg: var(--status-red-text);"      # dark and auto-dark keep the status tokens (the sheet's red is light only)
        self.assertIn(":root[data-theme=dark] { " + dark + " }", two)
        self.assertIn(":root[data-theme=auto] { " + dark + " } }", two)
        tokens = (base / "tokens.css").read_text(encoding="utf-8")
        self.assertIn("--pri-high-sheet-bg: #F4DEDB; --pri-high-sheet-fg: #B3392F;", tokens)
        self.assertNotIn("F4DEDB", (base / "rules.css").read_text(encoding="utf-8").upper())


if __name__ == "__main__":
    unittest.main()
