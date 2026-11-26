"""Row 1286 (PR 1993), hostile pass on the NEW logic only: ColsPanel (ColumnsMenu.jsx, the Classic placement of the Columns menu, one microtask after MenuPanel)
Fictional data only. (The three AP4 icon-tone selectors were removed with row 1540 AP3.)

Run: python3 dev/run_tests.py test_columns_menu_hostile_1286
Real page in headless Chrome (Classic): absurd window heights (1, 8, 20, 50, 5000), the heading at the foot of the window, ten quick open and close rounds, a
second window size between opens.
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
 return {floor: Math.round(bb), top: Math.round(r.top), bottom: Math.round(r.bottom), h: innerHeight, oy: c.overflowY, mh: el.style.maxHeight, scroll: el.scrollHeight, client: el.clientHeight}; })()"""
SETTLE = ("document.fonts.ready.then(() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(() => r(true)))))"
          ".then(() => { const m = document.querySelector('.cols-menu'); return m ? Promise.all(m.getAnimations().map(a => a.finished)).then(() => true) : true; })"
          ".then(() => new Promise(r => requestAnimationFrame(() => r(true))))")


class ColsPanelHostile(base.InThePage):
    def setUp(self):
        super().setUp()
        plain = testpage.html
        testpage.html = lambda branding=None: page.layer_theme(plain(branding), themes.css("prototype-2.0"))
        self.addCleanup(setattr, testpage, "html", plain)

    def ready(self, cdp):
        ref = self.add({"mode": "all", "columns": ["id", "owner"], "owner": ["Pat Demo", "Lee Demo"]})
        p = self.show(cdp)
        p.edit()
        self.head = f"[data-id=\"{ref}\"] [data-wil-edit] .wil-table th.wil-c-owner"
        p.until(f"!!document.querySelector({json.dumps(self.head)})", "the list")
        p.js("window.__errs = []; addEventListener('error', function(e){window.__errs.push(String(e.message))}); addEventListener('unhandledrejection', function(e){window.__errs.push('rej')})")
        return p

    def size(self, cdp, p, w, h):
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": h, "deviceScaleFactor": 1, "mobile": False}, p.sid)
        p.until(f"innerHeight === {h}", f"window {w}x{h}")

    def show_menu(self, p, block="start"):
        p.js(f"document.querySelector({json.dumps(self.head)}).scrollIntoView({{block:{json.dumps(block)}}})")
        time.sleep(0.25)
        p.js(f"document.querySelector({json.dumps(self.head)}).dispatchEvent(new MouseEvent('contextmenu', {{bubbles: true, cancelable: true}}))")
        p.until(f"!!({MEASURE})", "the Columns menu opened")
        p.js(SETTLE)    # row 1286: read only once the m-drop open animation (translateY(-4px), 120 ms) has finished
        return p.js(MEASURE)

    def shut(self, p):
        p.js("document.querySelector('.cols-menu') && document.querySelector('.cols-menu').dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}))")
        p.until("!document.querySelector('.cols-menu')", "closed")

    def test_absurd_window_heights_never_throw_and_always_close(self):
        with chrome() as cdp:
            p = self.ready(cdp)
            for h in (1, 8, 20, 50, 96, 5000):
                self.size(cdp, p, 1400, h)
                got = self.show_menu(p)
                self.assertEqual(p.js("window.__errs"), [], f"h={h}")
                self.assertIsNotNone(got, f"h={h}")
                self.assertNotIn("NaN", json.dumps(got), f"h={h}: {got}")
                self.shut(p)

    def test_a_very_tall_window_leaves_the_menu_uncut_and_unmoved(self):
        with chrome() as cdp:
            p = self.ready(cdp)
            self.size(cdp, p, 1400, 900)
            ref = self.show_menu(p)
            self.shut(p)
            self.size(cdp, p, 1400, 5000)
            got = self.show_menu(p)
            self.assertEqual(got["mh"], "", f"nothing cut: {got}")
            self.assertEqual(got["bottom"] - got["top"], ref["bottom"] - ref["top"], f"same height: {got} vs {ref}")
            self.assertLessEqual(got["bottom"], got["h"])

    def test_a_foot_one_to_seven_pixels_above_the_window_bottom_is_lifted_to_the_8px_margin(self):
        with chrome() as cdp:
            p = self.ready(cdp)
            self.size(cdp, p, 1400, 900)
            tall = self.show_menu(p)
            self.shut(p)
            for gap in (1, 4, 7):
                h = tall["bottom"] + gap
                self.size(cdp, p, 1400, h)
                got = self.show_menu(p)
                self.assertLessEqual(got["bottom"], h - 8 + 1, f"gap {gap}: {got}")
                self.assertGreaterEqual(got["top"], got["floor"], f"gap {gap}: {got}")
                self.shut(p)
            self.size(cdp, p, 1400, tall["bottom"] + 8)      # exactly the margin: no move
            got = self.show_menu(p)
            self.assertEqual(got["bottom"], tall["bottom"], f"foot exactly 8 above the bottom stays: {got}")
            self.shut(p)

    def test_heading_at_the_foot_of_the_window_keeps_the_menu_inside(self):
        with chrome() as cdp:
            p = self.ready(cdp)
            for h in (260, 420, 700):
                self.size(cdp, p, 1400, h)
                got = self.show_menu(p, block="end")
                self.assertGreaterEqual(got["top"], got["floor"], f"h={h}: {got}")
                self.assertLessEqual(got["bottom"], got["h"], f"h={h}: {got}")
                self.shut(p)

    def test_ten_quick_rounds_give_the_same_place_each_time_and_leave_nothing_behind(self):
        with chrome() as cdp:
            p = self.ready(cdp)
            self.size(cdp, p, 1400, 300)
            first = self.show_menu(p)
            self.shut(p)
            for i in range(10):
                got = self.show_menu(p)
                self.assertEqual((got["top"], got["bottom"]), (first["top"], first["bottom"]), f"round {i}: {got} vs {first}")
                self.assertEqual(p.js("document.querySelectorAll('.cols-menu').length"), 1)
                self.shut(p)
            self.assertEqual(p.js("window.__errs"), [])

    def test_open_and_close_in_one_task_does_not_throw_from_the_microtask(self):
        with chrome() as cdp:
            p = self.ready(cdp)
            self.size(cdp, p, 1400, 300)
            p.js(f"(function(){{var h=document.querySelector({json.dumps(self.head)}); h.dispatchEvent(new MouseEvent('contextmenu',{{bubbles:true,cancelable:true}}));"
                 "var m=document.querySelector('.cols-menu'); if (m) m.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}));})()")
            time.sleep(0.5)
            self.assertEqual(p.js("window.__errs"), [])

    def test_the_cut_menu_keeps_the_focused_item_in_view_under_the_keys(self):
        """164 high: the menu is cut and scrolls; End and Down must bring the focused row into the visible part of the box."""
        with chrome() as cdp:
            p = self.ready(cdp)
            self.size(cdp, p, 1400, 164)
            got = self.show_menu(p)
            self.assertGreater(got["scroll"], got["client"], "the menu is cut, as this test needs")
            p.key("End", vk=35)
            vis = p.js("(function(){var a=document.activeElement,b=a.getBoundingClientRect(),m=document.querySelector('.cols-menu').getBoundingClientRect();"
                       "return {inside:b.top>=m.top-1&&b.bottom<=m.bottom+1,top:b.top,bottom:b.bottom,mt:m.top,mb:m.bottom,tag:a.textContent}})()")
            self.assertTrue(vis["inside"], f"the last row has the focus but is out of sight: {vis}")



for _name in dir(base.InThePage):      # the Work items tests of the base class are run by their own file, not again here
    if _name.startswith("test_") and _name not in ColsPanelHostile.__dict__:
        setattr(ColsPanelHostile, _name, None)

if __name__ == "__main__":
    unittest.main()
