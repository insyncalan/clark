"""Rows 1315/1316/1319: the 28px height of the Classic text segment buttons is measured, min-height and rendered, at 1400 and 900, light and dark.

Run: python3 dev/run_tests.py test_gap_1319_height
Three rules are pinned, each by its own element: `.mv-txt button` (Row 1316), the plain `.seg` text button (Row 1319) and `#milestones .cal-sc button` (Row 1315).
The first two are probed on elements added to the real page, so no other rule can mask a changed value. Fails, never skips, without Chrome.
"""
import json
import time
import unittest

from _paths import ROOT
from test_server import chrome
from test_work_board_page import Base, page_target

from clark import page

NAME = "prototype-2.0"
READ = """(() => {
  const h = document.createElement('div');
  h.innerHTML = '<span class="mv-txt" id="p-mv"><button type="button">Week</button><span aria-hidden="true">.</span><button type="button">Month</button></span><span class="seg" id="p-seg"><button type="button">One</button><button type="button">Two</button></span>';
  document.body.appendChild(h);
  const m = (e) => { const c = getComputedStyle(e); return [c.minHeight, Math.round(e.getBoundingClientRect().height * 100) / 100]; };
  const of = (s) => [...document.querySelectorAll(s)].map(m);
  return JSON.stringify({mv: of('#p-mv button'), seg: of('#p-seg button'), cal: of('#milestones .cal-sc button')});
})()"""
WANT = ["28px", 28]


class Height(Base):
    def setUp(self):
        super().setUp()
        self.s.httpd.page_html = lambda: page.page_html(branding=page.NO_BRAND, theme=NAME)

    def read(self, width, dark):
        with chrome() as cdp:
            try:
                sid = self.visit(cdp, width=width, hash_="#milestones&p=ABC", wait_for=".frame.milestones")
            except AssertionError:
                sid = page_target(cdp)
            if dark:
                cdp.js("document.documentElement.dataset.theme = 'dark'", sid)
            time.sleep(0.5)
            return json.loads(cdp.js(READ, sid))

    def test_text_segment_buttons_are_28px_high(self):
        for width in (1400, 900):
            for dark in (False, True):
                got = self.read(width, dark)
                where = f"{width} {'dark' if dark else 'light'}"
                self.assertEqual(got["mv"], [WANT, WANT], f".mv-txt button, {where}")
                self.assertEqual(got["seg"], [WANT, WANT], f".seg button, {where}")
                self.assertTrue(got["cal"], f"the calendar scale buttons are on the page, {where}")
                for row in got["cal"]:
                    self.assertEqual(row, WANT, f".cal-sc button, {where}")


if __name__ == "__main__":
    unittest.main()
