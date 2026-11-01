"""A-D1 page side: the report's cover band (name, WEEKLY REPORT, week ending, for <client>), in a real browser.

Run: python3 dev/run_tests.py test_cover_band
Served page (View) and the published file, at 1400 and 900 px, light and dark. Fictional data.
"""
import shutil
import tempfile
import unittest
from pathlib import Path

from _demo import USER
from test_glance_page import Published, Setup
from test_report_editor import tearDownModule  # noqa: F401
from test_server import chrome

BAND = """(() => {
  const c = document.querySelector('header.cover'); if (!c) return null;
  const h = c.querySelector('h1'), line = c.querySelector('.cover-line');
  const f = document.querySelector('.frame').getBoundingClientRect(), r = c.getBoundingClientRect();
  return {name: h.textContent, line: line.textContent, kind: c.querySelector('.cover-kind').textContent,
          bg: getComputedStyle(c).backgroundColor, left: r.left - f.left, right: f.right - r.right,
          h1count: document.querySelectorAll('h1').length, wide: document.documentElement.scrollWidth <= window.innerWidth,
          fg: getComputedStyle(h).color, crumbs: document.querySelectorAll('.report .crumbs').length};
})()"""
LUM = """(() => { const rgb = (c) => c.match(/[\\d.]+/g).slice(0, 3).map(Number);
  const l = ([r, g, b]) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }; return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
  const c = document.querySelector('header.cover'), bg = l(rgb(getComputedStyle(c).backgroundColor));
  return ['h1', '.cover-line', '.cover-kind'].map((s) => { const x = l(rgb(getComputedStyle(c.querySelector(s)).color)); return (Math.max(x, bg) + 0.05) / (Math.min(x, bg) + 0.05); }); })()"""


class Served(Setup):
    def setUp(self):
        super().setUp()
        with self.store.step("dashboard", USER) as st:
            st.update("projects", "ABC", {"client_name": "Example Client", "week_ending": "2026-10-23"})

    def test_the_band_names_the_project_the_week_and_the_client(self):
        for width, dark in ((1400, False), (900, True), (1400, True)):
            with self.subTest(width=width, dark=dark), chrome() as cdp:
                p = self.show(cdp, width, dark)
                b = p.js(BAND)
                self.assertTrue(b["name"])
                self.assertEqual(b["kind"].upper(), "WEEKLY REPORT")
                self.assertIn("Week ending 23-10-2026", b["line"])
                self.assertIn("for Example Client", b["line"])
                self.assertEqual((b["h1count"], b["crumbs"]), (1, 0), "one heading, and the small client line is gone")
                self.assertLessEqual(abs(b["left"] - 1), 1.5, "full width of the frame, inside its border")
                self.assertLessEqual(abs(b["right"] - 1), 1.5)
                self.assertTrue(b["wide"], "no sideways scroll")
                self.assertGreaterEqual(min(p.js(LUM)), 4.5)


class InTheFile(Published):
    def setUp(self):
        super().setUp()
        with self.store.step("dashboard", USER) as st:
            st.update("projects", "ABC", {"client_name": "Example Client", "week_ending": "2026-10-23"})

    def test_the_published_file_draws_the_band_from_its_own_data(self):
        path = self.publish()
        for width, dark in ((1400, False), (900, True)):
            with self.subTest(width=width, dark=dark), chrome() as cdp:
                p = self.draw(cdp, path, width, dark)
                b = p.js(BAND)
                self.assertEqual(b["kind"].upper(), "WEEKLY REPORT")
                self.assertIn("Week ending 23-10-2026", b["line"])
                self.assertIn("for Example Client", b["line"])
                self.assertGreaterEqual(min(p.js(LUM)), 4.5)

    def test_a_missing_week_and_client_leave_those_parts_out(self):
        with self.store.step("dashboard", USER) as st:
            st.update("projects", "ABC", {"client_name": None, "week_ending": None})
        path = self.publish()
        with chrome() as cdp:
            line = self.draw(cdp, path).js("document.querySelector('.cover-line').textContent")
        self.assertEqual(line.strip(), "Weekly report")


if __name__ == "__main__":
    unittest.main()
