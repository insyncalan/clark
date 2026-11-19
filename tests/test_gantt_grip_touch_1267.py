"""Row 1267: a touch drag on the Gantt chart's height grip (.gt-grip) changes the rows shown, by pointer events.

The mouse drag is in test_gantt_chart.py; this is the same drag sent as Chrome touch events, at 1400 and 900 px.

Run: python3 dev/run_tests.py test_gantt_grip_touch_1267
Needs Chrome: these tests fail, never skip, without it.
"""
import unittest

import test_gantt_chart
import test_server  # noqa: F401  (names the Chrome harness, so the tier test reads this file as a browser test as run_support does)

ROWS = "document.querySelector('[data-g-grip]').getAttribute('aria-valuenow')"


class GanttGripTouch(unittest.TestCase):
    # the chart test's rig and helpers, borrowed so its own tests are not run a second time here
    setUpClass = classmethod(test_gantt_chart.Chart.setUpClass.__func__)
    tearDownClass = classmethod(test_gantt_chart.Chart.tearDownClass.__func__)
    js, val, until, look, mount, motion, centre = (test_gantt_chart.Chart.js, test_gantt_chart.Chart.val, test_gantt_chart.Chart.until, test_gantt_chart.Chart.look, test_gantt_chart.Chart.mount, test_gantt_chart.Chart.motion, test_gantt_chart.Chart.centre)

    def touch(self, kind, points):
        self.cdp.call("Input.dispatchTouchEvent", {"type": kind, "touchPoints": [{"x": x, "y": y} for x, y in points]}, self.sid)

    def test_a_touch_drag_on_the_gantt_grip_changes_the_rows_by_pointer_events(self):
        for width in (1400, 900):
            self.look(width, "light")
            self.mount(edit=False, defaultRows=3)
            self.assertEqual(self.val(ROWS), "3", f"{width}: three rows to start")
            self.assertEqual(self.val("getComputedStyle(document.querySelector('[data-g-grip]')).touchAction"), "none", f"{width}: the grip holds the touch")
            h0 = self.val("document.querySelector('[data-g-gx]').getBoundingClientRect().height")
            g = self.centre("[data-g-grip]")
            self.js("(function(){ window.__pt = []; ['pointerdown', 'pointermove', 'pointerup'].forEach(function(t){ document.addEventListener(t, function(e){ window.__pt.push(e.pointerType); }, true); }); })()")
            self.touch("touchStart", [(g["x"], g["y"])])
            for i in range(1, 5):
                self.touch("touchMove", [(g["x"], g["y"] + i * 18)])
            self.touch("touchEnd", [])
            self.until(f"{ROWS} === '5'", f"{width}: two rows more (72 px is 2.25 rows)")
            self.assertGreater(self.val("document.querySelector('[data-g-gx]').getBoundingClientRect().height"), h0, f"{width}: taller")
            self.assertIn("touch", self.val("window.__pt"), f"{width}: the events were touch pointers")
            self.assertEqual(self.val("window.calls"), [], f"{width}: a viewer's own height is never sent anywhere")

    def test_a_touch_drag_up_on_the_gantt_grip_shows_fewer_rows(self):
        for width in (1400, 900):
            self.look(width, "light")
            self.mount(edit=False)
            full = int(self.val(ROWS))
            g = self.centre("[data-g-grip]")
            self.touch("touchStart", [(g["x"], g["y"])])
            for i in range(1, 5):
                self.touch("touchMove", [(g["x"], g["y"] - i * 18)])
            self.touch("touchEnd", [])
            self.until(f"{ROWS} === '{full - 2}'", f"{width}: two rows fewer")


if __name__ == "__main__":
    unittest.main()
