"""Row 1286 (M5c follow-up): the tests pin the sticky-header clearance of a menu.

Run: python3 dev/run_tests.py test_menu_pin_header_1286
The real page in headless Chrome (Classic) over a demo database, 1400 and 900 wide, light and dark. The page is scrolled until the options button of the
open view tab sits under the sticky page header (its bottom edge 20 px above the header's bottom edge), the menu is opened from the keyboard (focus without
scrolling, then Enter) and measured: the box starts at or below the header's bottom (read from the DOM), ends inside the window, every line is the one
under its own centre point, and the line holding the keyboard focus is wholly below the header and inside the window with a drawn focus ring.
Reverting the header clearance in Menu.jsx (the `lo` limit of MenuPanel) turns this red. Chrome is required: the test fails, never skips, without it.
"""
import json
import unittest

from test_bulk_bar import Base  # noqa: E402
from test_server import chrome, wait  # noqa: E402
from test_work_board_page import tearDownModule, setUpModule  # noqa: E402,F401
from test_work_filters import set_line  # noqa: E402
import _dbg1549  # noqa: E402

GAP = 20          # how far above the header's bottom edge the button's bottom edge is put
HEIGHT = 520      # a window short enough for the page to scroll that far
# Scroll the page so the button's bottom edge is GAP px above the header's bottom edge; the answer is where it ended up.
PLACE = """(() => {
  const top = document.querySelector('.top'), b = document.querySelector('#viewTabMenu');
  const hb = Math.round(top.getBoundingClientRect().bottom);
  scrollBy(0, Math.round(b.getBoundingClientRect().bottom) - (hb - %d));
  const r = b.getBoundingClientRect();
  return { headerBottom: Math.round(top.getBoundingClientRect().bottom), btnBottom: Math.round(r.bottom), btnTop: Math.round(r.top), scrollY: Math.round(scrollY) };
})()"""
MEASURE = """(() => {
  const top = document.querySelector('.top'), hb = Math.round(top.getBoundingClientRect().bottom);
  const el = [...document.querySelectorAll('#viewTabMenuList')].filter(e => e.getBoundingClientRect().height > 0).pop();
  if (!el) return null;
  const r = el.getBoundingClientRect(), kids = [...el.querySelectorAll('[role^=menuitem]')], covered = [];
  const f = document.activeElement, fr = f ? f.getBoundingClientRect() : null, fc = f ? getComputedStyle(f) : null;
  const ring = !!f && ((fc.outlineStyle !== 'none' && parseFloat(fc.outlineWidth) >= 1) || (fc.boxShadow !== 'none' && fc.boxShadow !== '') || f.matches(':focus-visible'));
  const focusIn = !!f && el.contains(f), focusHit = focusIn ? document.elementFromPoint(fr.left + fr.width / 2, fr.top + fr.height / 2) : null;
  const btn = Math.round(document.querySelector('#viewTabMenu').getBoundingClientRect().bottom);
  const out = { headerBottom: hb, btnBottom: btn, menuTop: Math.round(r.top), menuBottom: Math.round(r.bottom), h: innerHeight, lines: kids.length, ring, focusIn,
                focusTop: fr ? Math.round(fr.top) : null, focusBottom: fr ? Math.round(fr.bottom) : null, focusHit: !!focusHit && (focusHit === f || f.contains(focusHit)) };
  for (const k of kids) {
    k.scrollIntoView({block: 'nearest'});
    const b = k.getBoundingClientRect(), hit = document.elementFromPoint(b.left + b.width / 2, b.top + b.height / 2);
    if (!hit || !(hit === k || k.contains(hit))) covered.push(k.textContent.trim());
  }
  out.covered = covered;
  return out;
})()"""


class MenuPinHeader(Base):
    def press(self, cdp, sid, name, code, vk):
        d = {"key": name, "code": code, "windowsVirtualKeyCode": vk}
        cdp.call("Input.dispatchKeyEvent", dict(d, type="keyDown", **({"text": "\r"} if name == "Enter" else {})), sid)      # a real Enter carries its character, which presses a button
        cdp.call("Input.dispatchKeyEvent", dict(d, type="keyUp"), sid)

    def check(self, width, theme):
        where = f"{width} wide, {theme}"
        with chrome() as cdp:
            sid = self.visit(cdp, width=width, height=900)
            set_line(cdp, sid, "type:action")
            self.until(cdp, sid, "document.querySelectorAll('#work-list tr[data-id]').length >= 3 && !!document.querySelector('#viewTabMenu')", "the rows and the tab's options button")
            cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": HEIGHT, "deviceScaleFactor": 1, "mobile": False}, sid)
            self.until(cdp, sid, f"innerWidth === {width} && innerHeight === {HEIGHT}", "the window size")
            cdp.js(f"document.documentElement.dataset.theme = {json.dumps(theme)}", sid)
            # keyboard mode (the focus ring shows for keys, not for the mouse)
            self.press(cdp, sid, "Tab", "Tab", 9)
            put = cdp.js(PLACE % GAP, sid)
            print(f"PLACE {where}: {json.dumps(put)}")
            self.assertLessEqual(put["btnBottom"], put["headerBottom"] - 8, f"{where}: the button is well under the header ({put})")
            self.assertEqual(put["btnBottom"], put["headerBottom"] - GAP, f"{where}: the button is under the header ({put})")
            opened = "!!document.querySelector('#viewTabMenuList[role=menu]')"
            dbg = _dbg1549.arm(lambda e: cdp.js(e, sid), f"test_menu_pin_header_1286 {where}", '#viewTabMenuList')
            for _ in range(6):                      # a late scroll closes a menu: open again until it stays
                if cdp.js(opened, sid):
                    break
                cdp.js(PLACE % GAP, sid)                # a late scroll of the page moved the button: put it under the header again
                cdp.js("document.querySelector('#viewTabMenu').focus({preventScroll: true})", sid)
                self.press(cdp, sid, "Enter", "Enter", 13)
                if wait(lambda: cdp.js(opened, sid), 5) and not wait(lambda: not cdp.js(opened, sid), 0.5):
                    break
            try:
                self.until(cdp, sid, "!!document.querySelector('#viewTabMenuList') && document.querySelector('#viewTabMenuList').getBoundingClientRect().height > 0", f"{where}: the menu opened")
            finally:
                dbg.dump()
            got = cdp.js(MEASURE, sid)
            print(f"MEASURE {where}: {json.dumps(got)}")
            self.assertEqual(got["btnBottom"], got["headerBottom"] - GAP, (where, "the button is still under the header when measured", got))
            self.assertGreaterEqual(got["lines"], 3, (where, got))
            self.assertGreaterEqual(got["headerBottom"], 40, (where, got))
            self.assertGreaterEqual(got["menuTop"], got["headerBottom"], (where, "the menu top is at or below the header bottom", got))
            self.assertGreaterEqual(got["menuTop"], got["headerBottom"] + 8, (where, "and keeps the 8 px the code leaves under the header", got))
            self.assertLessEqual(got["menuBottom"], got["h"], (where, "the menu ends inside the window", got))
            self.assertEqual(got["covered"], [], (where, got))
            self.assertTrue(got["focusIn"], (where, "the focus is on a line of the menu", got))
            self.assertGreaterEqual(got["focusTop"], got["headerBottom"], (where, "the focused line is not under the header", got))
            self.assertLessEqual(got["focusBottom"], got["h"], (where, got))
            self.assertTrue(got["focusHit"], (where, "the focused line is not covered", got))
            self.assertTrue(got["ring"], (where, "the focused line shows its ring", got))

    def test_the_tab_menu_clears_the_header_at_1400_light(self):
        self.check(1400, "light")

    def test_the_tab_menu_clears_the_header_at_1400_dark(self):
        self.check(1400, "dark")

    def test_the_tab_menu_clears_the_header_at_900_light(self):
        self.check(900, "light")

    def test_the_tab_menu_clears_the_header_at_900_dark(self):
        self.check(900, "dark")


if __name__ == "__main__":
    unittest.main()
