"""Item 1286 (Impeccable audit, M10): the chosen half of every segmented control looks the same on the three pages that have one.

Run: python3 dev/run_tests.py test_toggle_look_1286
Measured in Chrome on the real server and the demo database (the fixed date), Classic and Cards, 1400 and 900 px, light and dark: the chosen
Timeline or Calendar switch (.msv-b), the chosen Week, Month or Quarter on the Calendar (.cal-sc), and the chosen scale on the Gantt
(.gt-grp .gt-ib) paint the same fill (the gradient when there is one, else the colour), the same text colour and the same edge ring (Classic's switch keeps its Row 1313 heading fill, so Classic compares the Gantt and the Calendar only).
Chrome is required: this test fails, never skips, without it.
"""
import itertools
import sqlite3
import tempfile
import time
import unittest

from _editor_checks import for_url
from test_milestones_page import BrowserBase
from test_server import chrome, wait, Running
from test_work_items import FIXED_DATE, page_target

from clark import page

THEME = "prototype-2.0"
LINES = [("phase", "Discovery", "2026-09-01", "2026-10-15"), ("task", "Interviews", "2026-09-05", "2026-09-20"),
         ("milestone", "Go live", "2026-11-30", "2026-11-30"), ("phase", "Build", "2026-10-16", "2026-12-20")]
LOOK = """(sel) => { const e = document.querySelector(sel); if (!e) return null; const c = getComputedStyle(e);
  return {paint: c.backgroundImage !== 'none' ? c.backgroundImage : c.backgroundColor, fg: c.color, ring: c.boxShadow}; }"""


class ToggleLook(BrowserBase, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        con = sqlite3.connect(str(cls.store.path))
        con.execute("UPDATE projects SET show_gantt_editor = 1 WHERE code = 'MOSS'")
        for i, (kind, name, a, b) in enumerate(LINES):
            con.execute("INSERT INTO gantt_lines (id, project, type, name, start, end, sort_order) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        ("MOSS-GNT-%03d" % (i + 1), "MOSS", kind, name, a, b, i))
        con.commit()
        con.close()
        cls.projects = cls.store.read("projects")

    def serve_as(self, theme):
        html = page.page_html(branding=page.NO_BRAND, theme=THEME if theme == "classic" else None)
        s = Running(data_for=self.store.data_for, projects=lambda archived=False: self.projects, page_html=lambda *a: html)
        self.addCleanup(s.close)
        return s.port

    def looks(self, theme, width, scheme):
        """The three chosen halves, as {name: look}, in one Chrome."""
        port = self.serve_as(theme)
        got = {}
        with chrome() as cdp:
            sid = self.visit(cdp, width, "#milestones&p=MOSS", port)
            cdp.js(f"document.documentElement.dataset.theme = '{scheme}'", sid)
            got["switch"] = cdp.js(f"({LOOK})('.msv-b[aria-current=true]')", sid)
            cdp.js("document.querySelector('[data-msvb=cal]').click()", sid)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.cal-sc')", sid)))
            got["calendar"] = cdp.js(f"({LOOK})('.cal-sc button[aria-current=true]')", sid)
            cdp.call("Page.navigate", {"url": for_url(f"http://127.0.0.1:{port}/#gantt&p=MOSS")}, sid)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#gantt-page')", sid)), "the Gantt page drew")
            cdp.js("document.querySelector('[data-gp-mode=edit]').click()", sid)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.gt-grp .gt-ib[aria-pressed=true]')", sid)), "the chart's scale buttons drew")
            cdp.js(f"document.documentElement.dataset.theme = '{scheme}'", sid)
            time.sleep(0.3)
            got["gantt"] = cdp.js(f"({LOOK})('.gt-grp .gt-ib[aria-pressed=true][data-g-scale]')", sid)
        return got

    def test_the_chosen_half_looks_the_same_on_the_switch_the_calendar_and_the_gantt(self):
        for theme, width, scheme in itertools.product(("classic", "cards"), (1400, 900), ("light", "dark")):
            with self.subTest(theme=theme, width=width, scheme=scheme):
                got = self.looks(theme, width, scheme)
                for name, look in got.items():
                    self.assertIsNotNone(look, f"{name}: a chosen half is drawn")
                if theme == "cards":          # Classic's switch is the Row 1313 heading fill, pinned by test_theme_dashboard_1313
                    with self.subTest(pair="switch"):
                        self.assertEqual(got["switch"], got["calendar"], "Timeline/Calendar switch against the Calendar scale")
                with self.subTest(pair="gantt"):
                    self.assertEqual(got["gantt"], got["calendar"], "Gantt scale against the Calendar scale")


if __name__ == "__main__":
    unittest.main()
