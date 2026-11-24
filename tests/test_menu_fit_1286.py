"""Row 1286 (B-M5): a menu never runs past the bottom of the window; when its list is longer than the window it scrolls inside itself.

Run: python3 dev/run_tests.py test_menu_fit_1286
The real page in headless Chrome (Classic) against the real server over a demo database. For each of the menus below (the selection menu
of the bar, the row menu, the View menu, the Columns menu, a cell's Status list) the window is 1400 and 900 wide (AP6), each 900 high, then a short 420 high (a menu with ten lines cannot be whole there), light and dark. The menu box must sit inside the window (top >= 0,
bottom <= window height) and, if its lines are taller than the box, the box must scroll (overflow-y auto or scroll) with the first line
reachable. Chrome is required: the test fails, never skips, without it.
"""
import json
import unittest

from test_bulk_bar import Base  # noqa: E402
from test_multi_select import MOD, peek_away, tap  # noqa: E402
from test_server import chrome, wait  # noqa: E402
from test_work_board_page import tearDownModule, setUpModule  # noqa: E402,F401
from test_work_filters import set_line, where  # noqa: E402

LOOKS = [(w, h, th) for w in (1400, 900) for h in (900, 420) for th in ("light", "dark")]     # AP6 (Row 1286 Stage 0): 1400 is the priority width, 900 stays
# The box that holds the lines of the open menu, and the measure of it.
MEASURE = """((sel) => { const el = [...document.querySelectorAll(sel)].filter(e => e.getBoundingClientRect().height > 0).pop();
  if (!el) return null;
  const r = el.getBoundingClientRect(), c = getComputedStyle(el), kids = [...el.querySelectorAll('[role^=menuitem],.menu-item')];
  const last = kids.length ? kids[kids.length - 1] : null;
  return { top: Math.round(r.top), bottom: Math.round(r.bottom), left: Math.round(r.left), right: Math.round(r.right), h: innerHeight, w: innerWidth,
           oy: c.overflowY, scroll: el.scrollHeight, client: el.clientHeight, lines: kids.length,
           lastReachable: !!last && (el.scrollHeight <= el.clientHeight + 1 || ['auto', 'scroll'].includes(c.overflowY)) }; })"""


class MenuFit(Base):
    def look(self, cdp, sid, width, height, theme):
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": height, "deviceScaleFactor": 1, "mobile": False}, sid)
        self.until(cdp, sid, f"innerWidth === {width} && innerHeight === {height}", "the window size")
        cdp.js(f"document.documentElement.dataset.theme = {json.dumps(theme)}", sid)

    def inside(self, cdp, sid, sel, what, look):
        self.until(cdp, sid, f"!!({MEASURE})({json.dumps(sel)})", f"{what}: the menu {sel} opened",
                   why=lambda: cdp.js("JSON.stringify({sel: clarkPage.selected(), pops: [...document.querySelectorAll('.cpop,.rowmenu,.ddmenu')].map(e => e.className), peek: !!document.querySelector('#peek')})", sid))
        got = cdp.js(f"({MEASURE})({json.dumps(sel)})", sid)
        where_ = f"{what} at {look}: {got}"
        self.assertGreaterEqual(got["top"], 0, where_)
        self.assertLessEqual(got["bottom"], got["h"], where_)
        self.assertGreaterEqual(got["left"], 0, where_)
        self.assertLessEqual(got["right"], got["w"], where_)
        self.assertTrue(got["lastReachable"], where_ + " (taller than its box and does not scroll)")
        self.assertGreaterEqual(got["lines"], 1, where_)

    def close(self, cdp, sid):
        cdp.call("Input.dispatchKeyEvent", {"type": "rawKeyDown", "key": "Escape", "code": "Escape", "windowsVirtualKeyCode": 27}, sid)
        cdp.call("Input.dispatchKeyEvent", {"type": "keyUp", "key": "Escape", "code": "Escape", "windowsVirtualKeyCode": 27}, sid)
        self.until(cdp, sid, "!document.querySelector('.bmenu, .rowmenu, .cols-menu, .cpop, [role=menu]:not([hidden])') || [...document.querySelectorAll('.bmenu, .rowmenu, .cols-menu, .cpop, [role=menu]')].every(e => e.classList.contains('leaving') || e.getBoundingClientRect().height === 0)", "the menu closed")

    def right_click(self, cdp, sid, selector):
        x, y = where(cdp, sid, selector)
        for kind, b in (("mousePressed", 2), ("mouseReleased", 0)):
            cdp.call("Input.dispatchMouseEvent", {"type": kind, "x": x, "y": y, "button": "right", "buttons": b, "clickCount": 1}, sid)

    def rows(self, cdp, sid):
        return [r for r in cdp.js("[...document.querySelectorAll('#work-list tr[data-id]')].map(r => r.dataset.id)", sid)]

    def loaded(self, cdp):
        sid = self.visit(cdp, width=900, height=900)
        set_line(cdp, sid, "type:action")
        self.until(cdp, sid, "document.querySelectorAll('#work-list tr[data-id]').length >= 3", "the rows")
        return sid

    def test_the_selection_menu_stays_inside_the_window(self):
        with chrome() as cdp:
            sid = self.loaded(cdp)
            rows = [r for r in self.rows(cdp, sid)][:2]
            for w, h, th in LOOKS:
                self.look(cdp, sid, w, h, th)
                tap(cdp, sid, f"#work-list tr[data-id='{rows[0]}'] .c-item .t")
                peek_away(cdp, sid, 900)
                tap(cdp, sid, f"#work-list tr[data-id='{rows[1]}'] .c-item .t", MOD)
                peek_away(cdp, sid, 900)
                self.assertEqual(cdp.js("clarkPage.selected()", sid), rows)
                self.right_click(cdp, sid, f"#work-list tr[data-id='{rows[1]}'] .c-item .t")
                self.inside(cdp, sid, ".bmenu", "selection menu", (w, h, th))
                self.close(cdp, sid)

    def test_the_row_menu_stays_inside_the_window(self):
        with chrome() as cdp:
            sid = self.loaded(cdp)
            rows = self.rows(cdp, sid)
            for w, h, th in LOOKS:
                self.look(cdp, sid, w, h, th)
                self.right_click(cdp, sid, f"#work-list tr[data-id='{rows[2]}'] .c-item .t")
                self.inside(cdp, sid, ".rowmenu .ddmenu", "row menu", (w, h, th))
                self.close(cdp, sid)

    def test_the_view_menu_stays_inside_the_window(self):
        with chrome() as cdp:
            sid = self.loaded(cdp)
            for w, h, th in LOOKS:
                self.look(cdp, sid, w, h, th)
                tap(cdp, sid, "#viewMenu")
                self.inside(cdp, sid, "#viewMenuList", "View menu", (w, h, th))
                self.close(cdp, sid)

    def test_a_cell_status_list_stays_inside_the_window(self):
        with chrome() as cdp:
            sid = self.loaded(cdp)
            rows = self.rows(cdp, sid)
            cell = f"[data-cell='{rows[2]}:status']"
            for w, h, th in LOOKS:
                self.look(cdp, sid, w, h, th)
                tap(cdp, sid, cell)
                self.inside(cdp, sid, ".cpop[role=menu]", "status list", (w, h, th))
                self.close(cdp, sid)

    def test_the_row_menu_takes_the_whole_short_window_minus_the_margin(self):
        """A row menu taller than a 280 px window is cut to the window minus 16 px (not 0, not 32) and scrolls inside itself."""
        with chrome() as cdp:
            sid = self.loaded(cdp)
            rows = self.rows(cdp, sid)
            self.look(cdp, sid, 900, 280, "light")
            self.right_click(cdp, sid, f"#work-list tr[data-id='{rows[2]}'] .c-item .t")
            self.inside(cdp, sid, ".rowmenu .ddmenu", "row menu", (900, 280, "light"))
            got = cdp.js(f"({MEASURE})('.rowmenu .ddmenu')", sid)
            self.assertGreater(got["scroll"], got["client"], got)
            self.assertIn(got["oy"], ("auto", "scroll"), got)
            self.assertLessEqual(abs((got["bottom"] - got["top"]) - (got["h"] - 16)), 1, got)
            self.close(cdp, sid)

    def test_the_view_menu_goes_above_its_button_and_scrolls_when_short_of_room(self):
        """The View menu opens under its button; in a short window it goes above the button (4 px clear of it) and its height is the room above the button, under the sticky header, minus 12 px (96 px at least), and it scrolls."""
        with chrome() as cdp:
            sid = self.loaded(cdp)
            for h in (240, 280):
                self.look(cdp, sid, 900, h, "light")
                tap(cdp, sid, "#viewMenu")
                self.inside(cdp, sid, "#viewMenuList", "View menu", (900, h, "light"))
                self.until(cdp, sid, "[document.querySelector('#viewMenuList'), document.querySelector('#viewMenu')].every(e => e.getAnimations().length === 0)", "the View menu and its button stopped moving")  # the menu drops in 4 px and the button eases 1 px: measure them settled
                got = cdp.js(f"({MEASURE})('#viewMenuList')", sid)
                btn = cdp.js("(() => { const r = document.querySelector('#viewMenu').getBoundingClientRect(); return {top: Math.round(r.top), bottom: Math.round(r.bottom), header: Math.round(document.querySelector('.top').getBoundingClientRect().bottom)}; })()", sid)
                self.assertGreater(got["scroll"], got["client"], got)
                self.assertIn(got["oy"], ("auto", "scroll"), got)
                self.assertLessEqual(got["bottom"], got["h"] - 8, got)
                self.assertLessEqual(abs(got["bottom"] - (btn["top"] - 4)), 1, (got, btn))       # above the button: 4 px calc offset from its wrapper, whose top is the button's top (the button eases 1 px up under the pointer, hence the 1 px slack)
                self.assertLessEqual(abs((got["bottom"] - got["top"]) - max(96, btn["top"] - 12 - btn["header"])), 1, (got, btn))  # the room above the button, under the sticky header, less 4 + 8 px (never under 96 px; the header is read from the page, M5c)
                self.close(cdp, sid)


if __name__ == "__main__":
    unittest.main()
