"""Row 1375: on the Dashboard, a wheel over the Work items box that has reached its end keeps scrolling the page (Classic).
The box scrolls on its own (Show N of M), and at its top or bottom edge the scroll must pass to the page, in both directions, never
stall inside the box. The box keeps scrolling its own rows while it can still move. Checks the computed overscroll-behavior-y and a
real wheel at 1400 and 900 px.
Run: TZ=UTC python3 dev/run_tests.py test_wil_scroll_chain_1375
"""
import json
import tempfile
import time
import unittest

from _real_server import real_server
from clark import page, theme

import test_tpl_workitems as base
from test_report_editor import tearDownModule  # noqa: F401
from test_server import chrome

BOX = "[data-id=\"%s\"] [data-wil-scroll]"
PAGE_Y = "Math.round(window.scrollY)"


class Chain(base.PageBase):
    add, show = base.InThePage.add, base.InThePage.show

    def setUp(self):
        super().setUp()
        self.s.close()
        css = theme.css("prototype-2.0")       # Classic only: the page with the Classic layer on top
        self.s = real_server(self.store.path, self.store.data_for, page_html=lambda: page.layer_theme(page.page_html(tempfile.mkdtemp()), css), seam=self.seam)
        self.addCleanup(self.s.close)
        base.plant(self)
        self.ref = self.add({"mode": "all", "columns": ["id", "owner", "due", "status", "priority"], "max": 2})

    def load(self, cdp, width):
        p = self.show(cdp, width)
        p.until(f"!!document.querySelector('{BOX % self.ref}') && document.querySelectorAll('[data-id=\"{self.ref}\"] .wil-lines li, [data-id=\"{self.ref}\"] .wil-table tbody tr').length > 0", "the list drew")
        p.js("(() => { const s = document.createElement('div'); s.id = 'spacer-1375'; s.style.height = '4000px'; document.body.appendChild(s); })()")
        p.js(f"document.querySelector('{BOX % self.ref}').scrollIntoView({{block: 'center'}})")
        time.sleep(0.5)
        return p

    def wheel(self, p, dy):
        x, y = p.js(f"(() => {{ const r = document.querySelector('{BOX % self.ref}').getBoundingClientRect(); return [Math.round(r.left + r.width / 2), Math.round(r.top + r.height / 2)]; }})()")
        p.cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y}, p.sid)
        p.cdp.call("Input.dispatchMouseEvent", {"type": "mouseWheel", "x": x, "y": y, "deltaX": 0, "deltaY": dy, "pointerType": "mouse"}, p.sid)
        last, still, end = None, 0, time.time() + 5
        while still < 3 and time.time() < end:
            time.sleep(0.1)
            now = p.js(f"[{PAGE_Y}, Math.round(document.querySelector('{BOX % self.ref}').scrollTop)]")
            still = still + 1 if now == last else 0
            last = now
        return last

    def test_the_box_does_not_hold_the_scroll(self):
        with chrome() as cdp:
            p = self.load(cdp, 1400)
            self.assertEqual(p.js(f"getComputedStyle(document.querySelector('{BOX % self.ref}')).overscrollBehaviorY"), "auto")

    def test_the_other_five_section_scroll_boxes_never_contain_or_none_the_wheel(self):
        probe = ("(() => { const host = document.querySelector('#report .sec-body') || document.querySelector('#report'); const got = {};"
                 " for (const k of %s) { const d = document.createElement('div'); d.className = k; host.appendChild(d); got[k] = getComputedStyle(d).overscrollBehaviorY; d.remove(); }"
                 " return got; })()")
        boxes = ["mv-wrap", "msl-scroll", "gt-scroll", "gt-gx", "tpl-table-wrap"]
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.load(cdp, width)
                got = p.js(probe % json.dumps(boxes))
                self.assertEqual(set(got), set(boxes))
                for k, v in got.items():
                    self.assertNotIn(v, ("contain", "none"), f"{width} {k}: a Dashboard section scroll box must not hold the wheel")
                self.assertEqual(p.js(probe % json.dumps(["wil-scroll"]))["wil-scroll"], "auto", f"{width}: the Work items box passes the wheel on")

    def test_wheel_at_the_end_of_the_box_moves_the_page_both_ways_1400_900(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.load(cdp, width)
                self.assertTrue(p.js(f"(b => b.scrollHeight > b.clientHeight + 20)(document.querySelector('{BOX % self.ref}'))"), "the box scrolls (the test's own check)")
                # inside the box: it moves its own rows, the page stays
                p.js(f"document.querySelector('{BOX % self.ref}').scrollTop = 0")
                y0 = p.js(PAGE_Y)
                page, top = self.wheel(p, 40)
                self.assertGreater(top, 0, f"{width}: the box still scrolls its own rows")
                # bottom edge: keep scrolling down, the page moves
                p.js(f"(b => b.scrollTop = b.scrollHeight)(document.querySelector('{BOX % self.ref}'))")
                # The page can sit on a half pixel (the At a glance figures have a normal line height, Row 1404), so the box's end is
                # fractional and the first wheel only uses up the last sub-pixel without handing on. One small wheel settles it; the
                # 300 px wheel below must then move the page.
                self.wheel(p, 3)
                y1 = p.js(PAGE_Y)
                page, _ = self.wheel(p, 300)
                self.assertGreater(page, y1, f"{width}: a wheel down at the bottom of the box moved the page")
                # top edge: keep scrolling up, the page moves
                p.js(f"document.querySelector('{BOX % self.ref}').scrollTop = 0")
                y2 = p.js(PAGE_Y)
                page, _ = self.wheel(p, -300)
                self.assertLess(page, y2, f"{width}: a wheel up at the top of the box moved the page")


if __name__ == "__main__":
    unittest.main()
