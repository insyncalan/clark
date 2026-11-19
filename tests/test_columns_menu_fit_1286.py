"""Row 1286 (B-M5b): the Columns menu of a Work items table stays inside a short window (top >= 0, bottom <= window height) and scrolls inside itself.

Run: python3 dev/run_tests.py test_columns_menu_fit_1286
The real page in headless Chrome (Classic), 1400 wide, window heights 164, 130 and 420. The menu is opened by a right click on the Owner heading
of a Work items table in Edit, with the heading scrolled to the top of the window. Chrome is required: the test fails, never skips, without it.
"""
import json
import time
import unittest

import test_tpl_workitems as base
from test_report_editor import tearDownModule  # noqa: F401
from test_server import chrome

MEASURE = """(() => { const el = document.querySelector('.cols-menu'); if (!el) return null; const r = el.getBoundingClientRect(), c = getComputedStyle(el);
 return {top: Math.round(r.top), bottom: Math.round(r.bottom), h: innerHeight, oy: c.overflowY,  scroll: el.scrollHeight, client: el.clientHeight}; })()"""


class ColumnsMenuFit(base.InThePage):
    def test_columns_menu_inside_short_windows(self):
        ref = self.add({"mode": "all", "columns": ["id", "owner"], "owner": ["Pat Demo", "Lee Demo"]})
        with chrome() as cdp:
            p = self.show(cdp)
            p.edit()
            head = f"[data-id=\"{ref}\"] [data-wil-edit] .wil-table th.wil-c-owner"
            p.until(f"!!document.querySelector({json.dumps(head)})", "the list")
            for h in (164, 130, 420):
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": 1400, "height": h, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                p.until(f"innerHeight === {h}", f"window {h}")
                p.js(f"document.querySelector({json.dumps(head)}).scrollIntoView({{block:'start'}})")
                time.sleep(0.3)
                p.js(f"document.querySelector({json.dumps(head)}).dispatchEvent(new MouseEvent('contextmenu', {{bubbles: true, cancelable: true}}))")
                p.until(f"!!({MEASURE})", f"the Columns menu opened at {h}")
                got = p.js(MEASURE)
                self.assertGreaterEqual(got["top"], 0, f"at {h}: {got}")
                self.assertLessEqual(got["bottom"], got["h"], f"at {h}: {got}")
                self.assertIn(got["oy"], ("auto", "scroll"), f"at {h}: {got}")
                p.js("document.querySelector('.cols-menu').dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}))")
                p.until("!document.querySelector('.cols-menu')", f"closed at {h}")


if __name__ == "__main__":
    unittest.main()
