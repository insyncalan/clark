"""Item 1286 (Impeccable audit, M10): the chosen half of every segmented control looks the same on the three pages that have one.

Run: python3 dev/run_tests.py test_toggle_look_1286
Measured in Chrome on the real server and the demo database (the fixed date), Classic and Cards, 1400 and 900 px, light and dark: the chosen
Timeline or Calendar switch (.msv-b), the chosen Week, Month or Quarter on the Calendar (.cal-sc), and the chosen scale on the Gantt
(.gt-grp .gt-ib) paint the same fill (the gradient when there is one, else the colour), the same text colour and the same edge ring. The Timeline and Calendar switch keeps its own look in both themes (Classic: the Row 1313 heading fill; Cards: unchanged), so only the Gantt and the Calendar are compared.
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
            self.scheme(cdp, sid, scheme)
            got["switch"] = cdp.js(f"({LOOK})('.msv-b[aria-current=true]')", sid)
            # the chosen half is set in the medium weight of the type scale (the Calendar scale's own semibold is not part of the shared look)
            got["switch_bg"] = cdp.js("getComputedStyle(document.querySelector('.msv-b[aria-current=true]')).backgroundColor", sid)
            got["switch_weight"] = cdp.js("[getComputedStyle(document.querySelector('.msv-b[aria-current=true]')).fontWeight, "
                                          "getComputedStyle(document.documentElement).getPropertyValue('--weight-medium').trim()]", sid)
            cdp.js("document.querySelector('[data-msvb=cal]').click()", sid)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.cal-sc')", sid)))
            got["calendar"] = cdp.js(f"({LOOK})('.cal-sc button[aria-current=true]')", sid)
            got["calendar_bg"] = cdp.js("getComputedStyle(document.querySelector('.cal-sc button[aria-current=true]')).backgroundColor", sid)
            cdp.call("Page.navigate", {"url": for_url(f"http://127.0.0.1:{port}/#gantt&p=MOSS")}, sid)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#gantt-page')", sid)), "the Gantt page drew")
            cdp.js("document.querySelector('%s').click()" % (".modes [data-mode=edit]" if theme == "classic" else "[data-gp-mode=edit]"), sid)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.gt-grp .gt-ib[aria-pressed=true]')", sid)), "the chart's scale buttons drew")
            self.scheme(cdp, sid, scheme)
            time.sleep(0.3)
            got["gantt"] = cdp.js(f"({LOOK})('.gt-grp .gt-ib[aria-pressed=true][data-g-scale]')", sid)
            # a pressed button outside the scale group (the zoom button, forced pressed here) is not given the chosen-half look
            cdp.js("document.querySelector('[data-g-zin]').setAttribute('aria-pressed', 'true')", sid)
            got["outside"] = cdp.js(f"({LOOK})('[data-g-zin]')", sid)
        return got

    def scheme(self, cdp, sid, scheme):
        """light, dark, or auto with the system asking for dark (the Theme has a rule for that case too)."""
        cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": "dark" if scheme == "auto" else scheme}]}, sid)
        cdp.js(f"document.documentElement.dataset.theme = '{scheme}'", sid)

    def test_the_chosen_half_looks_the_same_on_the_switch_the_calendar_and_the_gantt(self):
        for theme, width, scheme in itertools.product(("classic", "cards"), (1400, 900), ("light", "dark", "auto")):
            with self.subTest(theme=theme, width=width, scheme=scheme):
                got = self.looks(theme, width, scheme)
                for name, look in got.items():
                    self.assertIsNotNone(look, f"{name}: a chosen half is drawn")
                with self.subTest(pair="weight"):
                    self.assertEqual(got["switch_weight"][0], got["switch_weight"][1], "the chosen Timeline/Calendar half is in the medium weight")
                with self.subTest(pair="gantt"):
                    self.assertEqual(got["gantt"], got["calendar"], "Gantt scale against the Calendar scale")
                if theme == "classic":
                    with self.subTest(pair="outside"):
                        self.assertNotEqual(got["outside"]["paint"], got["gantt"]["paint"], "a pressed button outside the scale group keeps its own look")


if __name__ == "__main__":
    unittest.main()
