"""Row 1409: ONE colour per priority (Low green, Medium amber, High red, Urgent maroon), the same in the Work items table chip and in the
rating matrix cell, at 1400 and 900, light and dark. Both read the four --pri-* pairs in rules.css; neither names a colour of its own.
Run: python3 dev/run_tests.py test_priority_one_mapping_1409"""
import json
import re
import unittest
from pathlib import Path

import test_server  # noqa: F401  drives Chrome through the template harness
import test_tpl_workitems as base
import _testpage as testpage
from _real_server import real_server
from clark import page, theme
from test_server import chrome
from test_report_editor import tearDownModule  # noqa: F401

RULES = (Path(__file__).resolve().parent.parent / "src/clark/themes/prototype-2.0/rules.css").read_text(encoding="utf-8")
LEVELS = {"Low": "low", "Medium": "medium", "High": "high", "Urgent": "urgent"}
COMBOS = {"Low": ("Low", "Low"), "Medium": ("Medium", "Low"), "High": ("High", "Medium"), "Urgent": ("High", "High")}


def lum(rgb):
    c = [v / 255 for v in rgb]
    c = [v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4 for v in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def rgb(s):
    return [float(v) for v in re.findall(r"[\d.]+", s)[:3]]


def contrast(fg, bg):
    a, b = sorted((lum(rgb(fg)), lum(rgb(bg))), reverse=True)
    return (a + 0.05) / (b + 0.05)


class Source(unittest.TestCase):
    def test_four_pairs_one_source_no_literals(self):
        for lv in LEVELS.values():
            self.assertRegex(RULES, rf"--pri-{lv}-bg: var\(--[a-z-]+\);", lv)
            self.assertRegex(RULES, rf"--pri-{lv}-fg: var\(--[a-z-]+\);", lv)
        self.assertRegex(RULES, r"--pri-urgent-bg: var\(--tone-urgent\)")
        self.assertRegex(RULES, r"--pri-high-bg: var\(--status-red-tint\)")
        self.assertRegex(RULES, r"--pri-medium-bg: var\(--status-amber-tint\)")
        self.assertRegex(RULES, r"--pri-low-bg: var\(--status-green-tint\)")

    def test_chip_and_matrix_use_the_same_rule(self):
        for name in LEVELS:
            self.assertRegex(RULES, rf"\.wil-pr\[data-pri=\"?{name}\"?\],\s*\.cpop \.rmx-c\[data-level=\"?{name}\"?\]\s*\{{", name)


class Live(base.PageBase):
    add, show = base.InThePage.add, base.InThePage.show

    def setUp(self):
        super().setUp()
        base.plant(self)
        self.s.close()
        css = theme.css("prototype-2.0")
        self.s = real_server(self.store.path, self.store.data_for, page_html=lambda: page.layer_theme(testpage.html(), css), seam=self.seam)
        self.addCleanup(self.s.close)
        for lv, (im, li) in COMBOS.items():
            with self.store.step("dashboard", base.USER) as st:
                st.create("raid", {"project": "ABC", "type": "Risk", "description": f"Mapping {lv}", "raised": "2026-10-01", "source": "demo",
                                   "impact": im, "likelihood": li, "owner": "Pat Demo"})
        with self.store.step("dashboard", base.USER) as st:
            text = st.create("report_sections", {"project": "ABC", "type": "text", "title": "Fictional notes", "sort_order": 1})
        self.ref = self.add({"mode": "all", "columns": ["id", "owner", "due", "status", "priority"], "max": 40}, after=text, beside=1)

    def test_table_chip_and_matrix_cell_have_one_colour_per_priority(self):
        for dark in (False, True):
            for width in (1400, 900):
                with self.subTest(dark=dark, width=width), chrome() as cdp:
                    where = f"{'dark' if dark else 'light'} {width}"
                    p = self.show(cdp, width, dark=dark)
                    p.edit()
                    sel = f"[data-id=\"{self.ref}\"] .wil-table td .wil-pr"
                    p.until(f"[...document.querySelectorAll('{sel}')].some((e) => e.textContent === 'Urgent')", f"{where}: chips drew")
                    chips = json.loads(p.js(f"JSON.stringify(Object.fromEntries([...document.querySelectorAll('{sel}')].map((e) => {{ const s = getComputedStyle(e); return [e.textContent, [s.backgroundColor, s.color]]; }})))"))
                    p.js(f"[...document.querySelectorAll('[data-id=\"{self.ref}\"] .wil-table .cell-pick[data-cell^=\"ABC-0\"][data-cell$=\":priority\"]')][0].click()")
                    p.until("!!document.querySelector('[data-pop] .rmx-c')", f"{where}: matrix opened")
                    cells = json.loads(p.js("JSON.stringify(Object.fromEntries([...document.querySelectorAll('[data-pop] .rmx-c')].map((e) => { const s = getComputedStyle(e); return [e.dataset.level, [s.backgroundColor, s.color]]; })))"))
                    for lv in LEVELS:
                        self.assertIn(lv, chips, where)
                        self.assertEqual(chips[lv], cells[lv], f"{where}: {lv} chip and matrix agree")
                        self.assertGreaterEqual(contrast(chips[lv][1], chips[lv][0]), 4.5, f"{where}: {lv} reads")
                    self.assertEqual(len({tuple(v) for v in chips.values()}), 4, f"{where}: four different looks {chips}")
                    urg = rgb(chips["Urgent"][0])
                    self.assertTrue(urg[0] > urg[1] * 1.8 and urg[0] > urg[2] * 1.5, f"{where}: Urgent is maroon, a dark red {urg}")
                    self.assertNotEqual(chips["High"][0], chips["Urgent"][0], where)


if __name__ == "__main__":
    unittest.main()
