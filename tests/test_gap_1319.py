"""Row 1319 gap: the page h1 sits 4px above what follows, a text segment button is 3px 14px, 28px, weight 600 (Classic, 1400).

Run: python3 dev/run_tests.py test_gap_1319
Measured over the demo data (fictional). The .head h1 (0px), the two-icon layout switch (2px 8px, 32px) and the top bar's switch keep their own. Fails, never skips, without Chrome.
"""
import json
import time
import unittest

from _paths import ROOT
from test_server import chrome
from test_work_board_page import Base, page_target

from clark import page

NAME = "prototype-2.0"
RULES = ROOT / "src" / "clark" / "themes" / NAME / "rules.css"
READ = """(() => JSON.stringify({h1: [...document.querySelectorAll('h1')].filter(e => !e.classList.contains('hdr-h1')).map(e => { const c = getComputedStyle(e); return [c.fontSize, c.lineHeight, c.marginBottom, c.fontWeight]; }),
  seg: [...document.querySelectorAll('.seg button')].map(e => { const c = getComputedStyle(e); return [e.parentElement.className, c.padding, c.minHeight, c.fontWeight, e.offsetHeight, getComputedStyle(e.parentElement).borderRadius]; })}))()"""
H1_30 = ["30px", "36px", "4px", "600"]
H1_HEAD = ["30px", "36px", "0px", "600"]
TEXT_SEG = ["3px 14px", "28px", "600", 28, "6px"]   # last: the segment box radius, ruled 6 on 20-11
ICON_SEG = ["2px 8px", "32px"]


class Source(unittest.TestCase):
    def test_the_rules_sit_before_the_1314_block_and_1314_stays_last(self):
        text = RULES.read_text(encoding="utf-8")
        rows = [ln for ln in text.splitlines() if ln.startswith("/* Row ")]
        self.assertTrue(rows[-1].startswith("/* Row 1314"))
        self.assertLess(text.index("/* Row 1319, spec 19-11"), text.index("/* Row 1314"))
        self.assertNotIn("keep the pill", text)


class Computed(Base):
    def setUp(self):
        super().setUp()
        self.s.httpd.page_html = lambda: page.page_html(branding=page.NO_BRAND, theme=NAME)

    def read(self, hash_, wait_for):
        with chrome() as cdp:
            try:
                sid = self.visit(cdp, width=1400, hash_=hash_, wait_for=wait_for)
            except AssertionError:
                sid = page_target(cdp)
            time.sleep(0.5)
            return json.loads(cdp.js(READ, sid))

    def test_settings_and_dashboard_h1(self):
        for hash_, wait in (("#settings", "#projects"), ("#dashboard", "h1")):
            self.assertEqual(self.read(hash_, wait)["h1"], [H1_30], hash_)

    def test_head_h1_keeps_zero_margin_and_milestones_segments(self):
        m = self.read("#milestones&p=ABC", ".frame.milestones")
        self.assertEqual(m["h1"], [H1_HEAD])
        self.assertEqual(len(m["seg"]), 5)
        for row in m["seg"]:
            self.assertEqual(row[1:], TEXT_SEG, row)

    def test_layout_switch_keeps_its_own(self):
        w = self.read("#work&p=ABC", "#work")
        self.assertEqual(w["h1"], [H1_HEAD])
        for row in w["seg"]:
            self.assertEqual(row[1:3], ICON_SEG, row)


if __name__ == "__main__":
    unittest.main()
