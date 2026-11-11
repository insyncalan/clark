"""Row 1034: the Dashboard never scrolls sideways (found at 360 and 375 px, blamed on the milestones strip div.mv-strip).

Run: python3 dev/run_tests.py test_row_1034_no_sideways
The Dashboard has three parts that could be wider than a narrow card: the milestones line (it scrolls inside its own box), the Health tile
(held to 292 px) and the use case rows (five fixed columns). Chrome is run at 1400 and 900 px only: nothing in the Dashboard's sections scrolls
sideways and the page does not either, and the milestones line keeps scrolling inside its own box. The narrow rules (a 360 px card) are
checked in the style sheet itself.
"""
import re
import tempfile
import unittest
from pathlib import Path

from clark import page
from test_server import chrome, wait, Running
from test_work_items import FIXED_DATE, load_demo, page_target

CSS = (Path(page.__file__).parent / "shell.css").read_text(encoding="utf-8")
MEASURE = r"""(() => {
  const sec = document.querySelector('.secs'), bad = [];
  for (const e of sec.querySelectorAll('*')) { if (e.closest('.mv-wrap') && !e.classList.contains('mv-wrap')) continue;
    if (e.scrollWidth > e.clientWidth + 1 && e.clientWidth > 0 && getComputedStyle(e).overflowX === 'visible') bad.push(e.className); }
  const w = document.querySelector('.mv-wrap'), de = document.documentElement;
  return {bad, page: de.scrollWidth > innerWidth, wrapInside: w ? w.getBoundingClientRect().right <= sec.getBoundingClientRect().right + 1 : null};
})()"""


class Css(unittest.TestCase):
    def test_the_narrow_rules_are_in_the_style_sheet(self):
        self.assertRegex(CSS, r"\.tcell\.health \{[^}]*min-width: min\(292px, 100%\)")
        self.assertRegex(CSS, r"\.mv, \.msv-swap \{ min-width: 0; max-width: 100%; \}")
        self.assertRegex(CSS, r"\.mv-wrap \{[^}]*max-width: 100%")
        self.assertRegex(CSS, r"@media \(max-width: 640px\) \{ \.ucbar \{ grid-template-columns: auto minmax\(0, 1fr\); \} \.ucbar > :nth-child\(n\+3\) \{ grid-column: 1 / -1;")


class Dashboard(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store, cls.folder, _ = load_demo()
        cls.projects = cls.store.read("projects")

    @classmethod
    def tearDownClass(cls):
        cls.store.close()

    def test_nothing_scrolls_sideways_at_1400_and_900(self):
        s = Running(data_for=self.store.data_for, projects=lambda archived=False: self.projects, page_html=lambda: page.page_html(tempfile.mkdtemp()))
        self.addCleanup(s.close)
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = page_target(cdp)
                cdp.call("Page.enable", {}, sid)
                cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE}, sid)
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
                cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{s.port}/#dashboard&p=TUL"}, sid)
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.secs .glance')", sid)), "the Dashboard drew")
                got = cdp.js(MEASURE, sid)
                self.assertEqual(got["bad"], [], f"{width}px: nothing in a section runs past its box")
                self.assertFalse(got["page"], f"{width}px: the page does not scroll sideways")
                self.assertIn(got["wrapInside"], (True, None), f"{width}px: the milestones line stays in its section")


if __name__ == "__main__":
    unittest.main()
