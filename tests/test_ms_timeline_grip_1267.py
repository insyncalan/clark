"""Row 1267: the Timeline's height grip sits on the centre of the bottom edge (not the browser's corner handle), and drags and keys zoom the line.

Run: python3 dev/run_tests.py test_ms_timeline_grip_1267
Chrome launches at 1400 and 900 px.
"""
import unittest

from test_milestones_page import BrowserBase
from test_server import chrome, wait

HASH = "#milestones&p=TUL"
GEO = """(() => { const w = document.querySelector('.mv-wrap').getBoundingClientRect(), g = document.querySelector('[data-grip]').getBoundingClientRect();
  return [(g.left + g.width / 2) - (w.left + w.width / 2), w.bottom - g.bottom, w.bottom - g.top, getComputedStyle(document.querySelector('.mv-wrap')).resize]; })()"""
PCT = "document.querySelector('.mv-wrap').dataset.zoomPct"
KEY = "(k) => { const g = document.querySelector('[data-grip]'); g.focus(); g.dispatchEvent(new KeyboardEvent('keydown', {key: k, bubbles: true, cancelable: true})); }"


class Grip(BrowserBase, unittest.TestCase):
    def press(self, cdp, sid, key):
        cdp.js(f"({KEY})('{key}')", sid)

    def test_the_grip_is_centred_on_the_bottom_edge_and_the_corner_handle_is_gone(self):
        port = self.serve()
        for width in (1400, 900):
            with chrome() as cdp:
                sid = self.visit(cdp, width, HASH, port)
                dx, below, top, native = cdp.js(GEO, sid)
                self.assertLess(abs(dx), 1.5, f"{width}: centred")
                self.assertLessEqual(below, -10, f"{width}: it hangs under the strip's bottom edge, over no label")
                self.assertTrue(-3 <= top <= 12, f"{width}: its 24px box starts at the bottom edge and hangs under it ({top})")
                self.assertEqual(native, "none", f"{width}: no browser handle in the corner")

    def test_the_grip_is_a_named_slider_with_a_value(self):
        port = self.serve()
        for width in (1400, 900):
            with chrome() as cdp:
                sid = self.visit(cdp, width, HASH, port)
                got = cdp.js("(() => { const g = document.querySelector('[data-grip]'); return [g.getAttribute('role'), g.getAttribute('aria-label'), g.getAttribute('aria-valuenow'), g.getAttribute('aria-valuetext'), g.tabIndex]; })()", sid)
                self.assertEqual(got, ["slider", "Timeline height", "100", "Zoom 100%", 0], width)

    def test_arrow_keys_step_the_zoom_home_resets_and_the_ends_hold(self):
        port = self.serve()
        for width in (1400, 900):
            with chrome() as cdp:
                sid = self.visit(cdp, width, HASH, port)
                self.press(cdp, sid, "ArrowDown")
                self.assertTrue(wait(lambda: cdp.js(PCT, sid) == "110"), f"{width}: one step bigger")
                self.assertEqual(cdp.js("document.querySelector('[data-grip]').getAttribute('aria-valuetext')", sid), "Zoom 110%")
                self.assertEqual(cdp.js("document.querySelector('[data-grip]') === document.activeElement", sid), True, f"{width}: focus stays on the grip")
                self.press(cdp, sid, "ArrowUp"); self.press(cdp, sid, "ArrowUp")
                self.assertTrue(wait(lambda: cdp.js(PCT, sid) == "90"), f"{width}: two steps smaller")
                self.assertEqual(cdp.js("localStorage.getItem('clark.tlZoom.page')", sid), "0.9", f"{width}: remembered")
                for _ in range(5):
                    self.press(cdp, sid, "ArrowUp")
                self.assertTrue(wait(lambda: cdp.js(PCT, sid) == "70"), f"{width}: stops at 70")
                self.press(cdp, sid, "Home")
                self.assertTrue(wait(lambda: cdp.js(PCT, sid) == "100"), f"{width}: Home resets")

    def test_dragging_the_grip_down_zooms_and_is_remembered(self):
        port = self.serve()
        for width in (1400, 900):
            with chrome() as cdp:
                sid = self.visit(cdp, width, HASH, port)
                h = cdp.js("document.querySelector('.mv-wrap').offsetHeight", sid)
                x, y = cdp.js("(() => { const r = document.querySelector('[data-grip]').getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; })()", sid)
                cdp.call("Input.dispatchMouseEvent", {"type": "mousePressed", "x": x, "y": y, "button": "left", "clickCount": 1}, sid)
                for i in range(1, 7):
                    cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y + i * 20, "button": "left", "buttons": 1}, sid)
                cdp.call("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": x, "y": y + 120, "button": "left", "clickCount": 1}, sid)
                self.assertTrue(wait(lambda: float(cdp.js(PCT, sid)) > 100), f"{width}: zoomed in")
                self.assertGreater(cdp.js("document.querySelector('.mv-wrap').offsetHeight", sid), h + 60, f"{width}: taller")
                self.assertTrue(wait(lambda: cdp.js("localStorage.getItem('clark.tlZoom.page')", sid) not in (None, "1")), f"{width}: remembered")

    def test_the_words_say_what_the_grip_does_not_that_the_edge_drags(self):
        import json, pathlib
        port = self.serve()
        for width in (1400, 900):
            with chrome() as cdp:
                sid = self.visit(cdp, width, HASH, port)
                cap = cdp.js("(document.querySelector('.mv-zoom, .mv-cap') || {}).textContent || ''", sid)
                label = cdp.js("document.querySelector('.mv-wrap').getAttribute('aria-label')", sid)
                self.assertIn("Drag the grip below the timeline to zoom", cap, width)
                self.assertIn("drag the grip below it to zoom", label, width)
                self.assertNotIn("bottom edge", cap + label, width)
        help_text = (pathlib.Path(__file__).resolve().parent.parent / "src/clark/page/src/help/helpContent.json").read_text()
        json.loads(help_text)
        self.assertNotIn("bottom edge to zoom", help_text)
        self.assertNotIn("its bottom edge to zoom", help_text)
        self.assertEqual(help_text.count("grip below it to zoom"), 2, "both Timeline help lines name the grip")

    def test_a_touch_drag_on_the_grip_zooms_by_pointer_events(self):
        port = self.serve()
        for width in (1400, 900):
            with chrome() as cdp:
                sid = self.visit(cdp, width, HASH, port)
                h = cdp.js("document.querySelector('.mv-wrap').offsetHeight", sid)
                self.assertEqual(cdp.js("getComputedStyle(document.querySelector('[data-grip]')).touchAction", sid), "none", f"{width}: the grip holds the touch")
                x, y = cdp.js("(() => { const r = document.querySelector('[data-grip]').getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; })()", sid)
                cdp.js("(() => { window.__pt = []; for (const t of ['pointerdown', 'pointermove', 'pointerup']) document.addEventListener(t, (e) => window.__pt.push(e.pointerType), true); })()", sid)
                cdp.call("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": x, "y": y}]}, sid)
                for i in range(1, 7):
                    cdp.call("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [{"x": x, "y": y + i * 20}]}, sid)
                cdp.call("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []}, sid)
                self.assertTrue(wait(lambda: float(cdp.js(PCT, sid)) > 100), f"{width}: zoomed in by touch")
                self.assertGreater(cdp.js("document.querySelector('.mv-wrap').offsetHeight", sid), h + 60, f"{width}: taller")
                self.assertIn("touch", cdp.js("window.__pt", sid), f"{width}: the events were touch pointers")

    def test_the_ends_hold_once_settled_home_is_remembered_and_the_grip_is_off_the_paper(self):
        port = self.serve()
        for width in (1400, 900):
            with chrome() as cdp:
                sid = self.visit(cdp, width, HASH, port)
                for _ in range(12):
                    self.press(cdp, sid, "ArrowUp")
                self.assertTrue(wait(lambda: cdp.js(PCT, sid) == "70"), f"{width}: floor")
                cdp.js("new Promise((r) => setTimeout(r, 400))", sid)
                self.assertEqual(cdp.js(PCT, sid), "70", f"{width}: the floor holds after settling")
                self.assertEqual(cdp.js("document.querySelector('[data-grip]').getAttribute('aria-valuenow')", sid), "70")
                for _ in range(30):
                    self.press(cdp, sid, "ArrowDown")
                self.assertTrue(wait(lambda: cdp.js(PCT, sid) == "300"), f"{width}: ceiling")
                cdp.js("new Promise((r) => setTimeout(r, 400))", sid)
                self.assertEqual(cdp.js(PCT, sid), "300", f"{width}: the ceiling holds after settling")
                self.assertEqual(cdp.js("localStorage.getItem('clark.tlZoom.page')", sid), "3", f"{width}: ceiling remembered")
                self.press(cdp, sid, "Home")
                self.assertTrue(wait(lambda: cdp.js(PCT, sid) == "100"), f"{width}: Home resets")
                self.assertEqual(cdp.js("localStorage.getItem('clark.tlZoom.page')", sid), "1", f"{width}: Home remembered")
                self.assertNotEqual(cdp.js("getComputedStyle(document.querySelector('[data-grip]')).display", sid), "none", f"{width}: shown on screen")
                cdp.js("document.documentElement.classList.add('print-all')", sid)
                cdp.call("Emulation.setEmulatedMedia", {"media": "print"}, sid)
                self.assertEqual(cdp.js("getComputedStyle(document.querySelector('[data-grip]')).display", sid), "none", f"{width}: left off the paper")


if __name__ == "__main__":
    unittest.main()
