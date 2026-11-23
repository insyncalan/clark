"""Row 1286 (M5c): a menu never sits under the sticky page header.

Run: python3 dev/run_tests.py test_menu_under_header_1286
The real page in headless Chrome (Classic) over a demo database. The window is 420 high (a View menu cannot be whole there), 1400 wide first, then 900.
The View menu (Group by, Workstream and the other lines) is opened; the box must start at or below the bottom of the sticky header (read from the DOM)
and every line of the menu must be clickable: elementFromPoint at the centre of each line (scrolled into the box) is that line or inside it.
Chrome is required: the test fails, never skips, without it.
"""
import json
import unittest

from test_bulk_bar import Base  # noqa: E402
from test_multi_select import tap  # noqa: E402
from test_server import chrome  # noqa: E402
from test_work_board_page import tearDownModule, setUpModule  # noqa: E402,F401
from test_work_filters import set_line  # noqa: E402

# Header bottom, menu box and, for each line, whether the point at its centre (after scrolling it into the box) hits the line itself.
MEASURE = """(() => {
  const top = document.querySelector('.top'), hb = top ? Math.round(top.getBoundingClientRect().bottom) : 0;
  const el = [...document.querySelectorAll('#viewMenuList')].filter(e => e.getBoundingClientRect().height > 0).pop();
  if (!el) return null;
  const r = el.getBoundingClientRect(), c = getComputedStyle(el);
  const kids = [...el.querySelectorAll('[role^=menuitem]')];
  const covered = [];
  for (const k of kids) {
    k.scrollIntoView({block: 'nearest'});
    const b = k.getBoundingClientRect(), x = b.left + b.width / 2, y = b.top + b.height / 2, hit = document.elementFromPoint(x, y);
    if (!hit || !(hit === k || k.contains(hit))) covered.push(k.dataset.kind || k.textContent.trim());
  }
  el.scrollTop = 0;
  const r2 = el.getBoundingClientRect();
  return { headerBottom: hb, menuTop: Math.round(r2.top), menuBottom: Math.round(r2.bottom), overlap: Math.max(0, hb - Math.round(r2.top)), h: innerHeight,
           oy: c.overflowY, scroll: el.scrollHeight, client: el.clientHeight, lines: kids.length, covered, ids: kids.map(k => k.dataset.kind) };
})()"""


class MenuUnderHeader(Base):
    def look(self, cdp, sid, width, height):
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": height, "deviceScaleFactor": 1, "mobile": False}, sid)
        self.until(cdp, sid, f"innerWidth === {width} && innerHeight === {height}", "the window size")

    def check(self, width):
        with chrome() as cdp:
            sid = self.visit(cdp, width=width, height=900)
            set_line(cdp, sid, "type:action")
            self.until(cdp, sid, "document.querySelectorAll('#work-list tr[data-id]').length >= 3", "the rows")
            self.look(cdp, sid, width, 420)
            tap(cdp, sid, "#viewMenu")
            self.until(cdp, sid, "!!document.querySelector('#viewMenuList') && document.querySelector('#viewMenuList').getBoundingClientRect().height > 0", "the View menu opened")
            got = cdp.js(MEASURE, sid)
            print(f"MEASURE width={width} height=420: {json.dumps(got)}")
            self.assertGreaterEqual(got["lines"], 3, got)
            self.assertGreaterEqual(got["headerBottom"], 40, got)
            self.assertGreaterEqual(got["menuTop"], got["headerBottom"], got)
            self.assertEqual(got["overlap"], 0, got)
            self.assertLessEqual(got["menuBottom"], got["h"], got)
            self.assertEqual(got["covered"], [], got)

    def test_the_view_menu_is_not_under_the_header_at_1400(self):
        self.check(1400)

    def test_the_view_menu_is_not_under_the_header_at_900(self):
        self.check(900)


if __name__ == "__main__":
    unittest.main()
