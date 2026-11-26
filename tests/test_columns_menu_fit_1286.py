"""Row 1286 (B-M5b): the Columns menu of a Work items table stays inside a short window (top >= 0, bottom <= window height) and scrolls inside itself.

Run: python3 dev/run_tests.py test_columns_menu_fit_1286
The real page in headless Chrome (Classic, and a Cards pin), 1400 and 900 wide, window heights 164, 130 and 420; the menu top never goes under the sticky top bar (its floor). The menu is opened by a right click on the Owner heading
of a Work items table in Edit, with the heading scrolled to the top of the window. Chrome is required: the test fails, never skips, without it.
"""
import json
import time
import unittest

import _testpage as testpage
import test_tpl_workitems as base
from clark import page, theme as themes
from test_report_editor import tearDownModule  # noqa: F401
from test_server import chrome

MEASURE = """(() => { const el = document.querySelector('.cols-menu'); if (!el) return null; const r = el.getBoundingClientRect(), c = getComputedStyle(el);
 const bar = document.querySelector('.top'), bb = bar ? bar.getBoundingClientRect().bottom : 0;
 return {floor: Math.round(bb), top: Math.round(r.top), bottom: Math.round(r.bottom), h: innerHeight, oy: c.overflowY,  scroll: el.scrollHeight, client: el.clientHeight}; })()"""


class ColumnsMenuFit(base.InThePage):
    def setUp(self):
        super().setUp()
        plain = testpage.html
        testpage.html = lambda branding=None: page.layer_theme(plain(branding), themes.css("prototype-2.0"))      # the Classic page: <style id="theme"> is what classicTheme() looks for
        self.addCleanup(setattr, testpage, "html", plain)

    def test_columns_menu_inside_short_windows(self):
        ref = self.add({"mode": "all", "columns": ["id", "owner"], "owner": ["Pat Demo", "Lee Demo"]})
        with chrome() as cdp:
            p = self.show(cdp)
            p.edit()
            head = f"[data-id=\"{ref}\"] [data-wil-edit] .wil-table th.wil-c-owner"
            p.until(f"!!document.querySelector({json.dumps(head)})", "the list")
            for w, h in ((1400, 164), (1400, 130), (1400, 420), (900, 164), (900, 420)):      # at 900 the top bar is 121px tall: a 130 window is all bar, with no room under it for any menu
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": h, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                p.until(f"innerHeight === {h}", f"window {w}x{h}")
                p.js(f"document.querySelector({json.dumps(head)}).scrollIntoView({{block:'start'}})")
                time.sleep(0.3)
                p.js(f"document.querySelector({json.dumps(head)}).dispatchEvent(new MouseEvent('contextmenu', {{bubbles: true, cancelable: true}}))")
                p.until(f"!!({MEASURE})", f"the Columns menu opened at {w}x{h}")
                got = p.js(MEASURE)
                self.assertGreaterEqual(got["top"], 0, f"at {w}x{h}: {got}")
                self.assertGreaterEqual(got["top"], got["floor"], f"at {w}x{h}: the menu top is under the sticky top bar: {got}")
                self.assertLessEqual(got["bottom"], got["h"], f"at {w}x{h}: {got}")
                self.assertIn(got["oy"], ("auto", "scroll"), f"at {w}x{h}: {got}")
                p.js("document.querySelector('.cols-menu').dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}))")
                p.until("!document.querySelector('.cols-menu')", f"closed at {w}x{h}")

    def test_the_columns_menu_fits_a_short_window(self):
        """Row 1540 AP5: the Columns menu stays inside windows 420 and 280 high, 1400 and 900 wide, light and dark, under the sticky bar, and scrolls inside itself."""
        ref = self.add({"mode": "all", "columns": ["id", "owner"], "owner": ["Pat Demo", "Lee Demo"]})
        with chrome() as cdp:
            p = self.show(cdp)
            p.edit()
            head = f"[data-id=\"{ref}\"] [data-wil-edit] .wil-table th.wil-c-owner"
            p.until(f"!!document.querySelector({json.dumps(head)})", "the list")
            for w in (1400, 900):
                for h in (420, 280):
                    for theme in ("light", "dark"):
                        cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": h, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                        p.until(f"innerWidth === {w} && innerHeight === {h}", f"window {w}x{h}")
                        p.js(f"document.documentElement.dataset.theme = {json.dumps(theme)}")
                        p.js(f"document.querySelector({json.dumps(head)}).scrollIntoView({{block:'start'}})")
                        time.sleep(0.3)
                        p.js(f"document.querySelector({json.dumps(head)}).dispatchEvent(new MouseEvent('contextmenu', {{bubbles: true, cancelable: true}}))")
                        p.until(f"!!({MEASURE})", f"the Columns menu opened at {w}x{h} {theme}")
                        got = p.js(MEASURE)
                        where = f"at {w}x{h} {theme}: {got}"
                        self.assertGreaterEqual(got["top"], got["floor"], where)
                        self.assertLessEqual(got["bottom"], got["h"], where)
                        self.assertIn(got["oy"], ("auto", "scroll"), where)
                        p.js("document.querySelector('.cols-menu').dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}))")
                        p.until("!document.querySelector('.cols-menu')", f"closed at {w}x{h}")

    def test_columns_menu_foot_is_shifted_up_to_the_window_bottom_margin(self):
        """A menu that fits the window (it is not cut) but whose foot, placed under the heading, would be lower than 8px above the window bottom is moved up so its foot is at innerHeight - 8.

        Accepted gap (Tech Debt v1.4): the 900x130 window, where room <= 0 (the top bar fills it), is not tested.
        """
        ref = self.add({"mode": "all", "columns": ["id", "owner"], "owner": ["Pat Demo", "Lee Demo"]})
        with chrome() as cdp:
            p = self.show(cdp)
            p.edit()
            head = f"[data-id=\"{ref}\"] [data-wil-edit] .wil-table th.wil-c-owner"
            p.until(f"!!document.querySelector({json.dumps(head)})", "the list")

            def opened(h):
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": 1400, "height": h, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                p.until(f"innerHeight === {h}", f"window 1400x{h}")
                p.js(f"document.querySelector({json.dumps(head)}).scrollIntoView({{block:'start'}})")
                time.sleep(0.3)
                p.js(f"document.querySelector({json.dumps(head)}).dispatchEvent(new MouseEvent('contextmenu', {{bubbles: true, cancelable: true}}))")
                p.until(f"!!({MEASURE})", f"the Columns menu opened at 1400x{h}")
                p.until("document.getAnimations().length === 0", "animations finished")      # the menu is measured at rest
                return p.js(MEASURE)

            def closed():
                p.js("document.querySelector('.cols-menu').dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}))")
                p.until("!document.querySelector('.cols-menu')", "closed")

            tall = opened(900)      # nothing is cut or moved: its top is where it sits under the heading, its height is the whole menu
            closed()
            natural_foot = tall["bottom"]
            h = natural_foot + 4      # the foot (natural_foot) is 4px below the 8px margin, and the menu is lower than the window less the floor and the margin: no cut
            self.assertLessEqual(tall["bottom"] - tall["top"], h - tall["floor"] - 8, f"the window is tall enough to need no cut: {tall}")
            got = opened(h)
            self.assertLessEqual(abs(got["bottom"] - (h - 8)), 1, f"at 1400x{h}: the menu foot is at the window bottom less 8: {got}")
            self.assertGreaterEqual(got["top"], got["floor"], f"at 1400x{h}: {got}")
            self.assertLess(got["top"], tall["top"], f"at 1400x{h}: the menu was moved up from {tall['top']}: {got}")
            closed()

class ColumnsMenuCardsPinned(base.InThePage):
    """Cards is frozen: its Columns menu is placed as before Row 1286 (MenuPanel alone, cut to the window, its top left under the heading). Values measured on main."""

    PINNED = {(1400, 164): (93, 189), (1400, 420): (93, 403), (900, 164): (137, 233), (900, 420): (137, 412)}

    def test_cards_columns_menu_is_placed_as_on_main(self):
        ref = self.add({"mode": "all", "columns": ["id", "owner"], "owner": ["Pat Demo", "Lee Demo"]})
        with chrome() as cdp:
            p = self.show(cdp)
            self.assertFalse(p.js("!!document.getElementById('theme')"), "this is the Cards page")
            p.edit()
            head = f"[data-id=\"{ref}\"] [data-wil-edit] .wil-table th.wil-c-owner"
            p.until(f"!!document.querySelector({json.dumps(head)})", "the list")
            for (w, h), (top, bottom) in self.PINNED.items():
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": h, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                p.until(f"innerHeight === {h}", f"window {w}x{h}")
                p.js(f"document.querySelector({json.dumps(head)}).scrollIntoView({{block:'start'}})")
                time.sleep(0.3)
                p.js(f"document.querySelector({json.dumps(head)}).dispatchEvent(new MouseEvent('contextmenu', {{bubbles: true, cancelable: true}}))")
                p.until(f"!!({MEASURE})", f"the Columns menu opened at {w}x{h}")
                p.until("document.getAnimations().length === 0", "animations finished")
                got = p.js(MEASURE)
                self.assertEqual((got["top"], got["bottom"]), (top, bottom), f"Cards at {w}x{h}: {got}")
                p.js("document.querySelector('.cols-menu').dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}))")
                p.until("!document.querySelector('.cols-menu')", f"closed at {w}x{h}")

    def test_cards_keys_do_not_scroll_the_menu_and_the_menu_stays_open(self):
        """Cards is frozen: menuMove keeps focus({preventScroll}) with no scrollIntoView, and the scroll-closer is as on main (Menu.jsx gates both to Classic)."""
        ref = self.add({"mode": "all", "columns": ["id", "owner"], "owner": ["Pat Demo", "Lee Demo"]})
        with chrome() as cdp:
            p = self.show(cdp)
            self.assertFalse(p.js("!!document.getElementById('theme')"), "this is the Cards page")
            p.edit()
            head = f"[data-id=\"{ref}\"] [data-wil-edit] .wil-table th.wil-c-owner"
            p.until(f"!!document.querySelector({json.dumps(head)})", "the list")
            cdp.call("Emulation.setDeviceMetricsOverride", {"width": 1400, "height": 164, "deviceScaleFactor": 1, "mobile": False}, p.sid)
            p.until("innerHeight === 164", "window 1400x164")
            p.js(f"document.querySelector({json.dumps(head)}).scrollIntoView({{block:'start'}})")
            time.sleep(0.3)
            p.js(f"document.querySelector({json.dumps(head)}).dispatchEvent(new MouseEvent('contextmenu', {{bubbles: true, cancelable: true}}))")
            p.until(f"!!({MEASURE})", "the Columns menu opened")
            p.until("document.getAnimations().length === 0", "animations finished")
            p.key("End", vk=35)
            time.sleep(0.3)
            self.assertEqual(p.js("(function(){var m=document.querySelector('.cols-menu');return m?m.scrollTop:-1})()"), 0, "Cards: End moved the focus without scrolling the menu")


for _cls in (ColumnsMenuFit, ColumnsMenuCardsPinned):
    for _name in dir(base.InThePage):      # the Work items tests of the base class are run by their own file, not again here
        if _name.startswith("test_") and _name not in _cls.__dict__:
            setattr(_cls, _name, None)

if __name__ == "__main__":
    unittest.main()
