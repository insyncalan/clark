"""Row 1286 (B-M5b): the Columns menu of a Work items table stays inside a short window (top >= 0, bottom <= window height) and scrolls inside itself.

Run: python3 dev/run_tests.py test_columns_menu_fit_1286
The real page in headless Chrome (Classic), 1400 and 900 wide, window heights 164, 130 and 420; the menu top never goes under the sticky top bar (its floor). The menu is opened by a right click on the Owner heading
of a Work items table in Edit, with the heading scrolled to the top of the window. Chrome is required: the test fails, never skips, without it.
"""
import json
import time
import unittest

import test_tpl_workitems as base
from test_report_editor import tearDownModule  # noqa: F401
from test_server import chrome

MEASURE = """(() => { const el = document.querySelector('.cols-menu'); if (!el) return null; const r = el.getBoundingClientRect(), c = getComputedStyle(el);
 const bar = document.querySelector('.top'), bb = bar ? bar.getBoundingClientRect().bottom : 0;
 return {floor: Math.round(bb), top: Math.round(r.top), bottom: Math.round(r.bottom), h: innerHeight, oy: c.overflowY,  scroll: el.scrollHeight, client: el.clientHeight}; })()"""


class ColumnsMenuFit(base.InThePage):
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


if __name__ == "__main__":
    unittest.main()
