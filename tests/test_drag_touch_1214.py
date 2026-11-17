"""Row 1214 touch: a finger holds on the grip before the section drag starts; a quick swipe scrolls the page instead.
The 400 ms hold is approved. Run: cd tests && PYTHONPATH=../src:../vendor:. python3 -m unittest test_drag_touch_1214
No Chrome. drag.js is bundled and run in node against the stand-in DOM and clock of test_drag_skips_needs_section, at 1400 and 900 px.
"""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from test_drag_skips_needs_section import STAND_IN  # noqa: E402
from test_drag_wire_1214 import RECTS, SECTIONS  # noqa: E402
from test_title_limit import bundle  # noqa: E402

WIDTHS = (1400, 900)


class DragTouch(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls._tmp.cleanup)
        cls.out = bundle('export { startDrag } from "@src/edit/drag.js";'
                         'export { data, dropAt } from "@src/stores/report.js";', Path(cls._tmp.name), None, "dragtouch.cjs")

    def run_script(self, width, kind, steps):
        """steps: [x, y, ms] (a move, then the clock runs ms), ["wait", ms], or "up". Returns what was drawn, scrolled and left pending."""
        js = (STAND_IN
              + "const fire = () => { for (let i = 0; i < timers.length; i++) { const t = timers[i]; if (t && t[0] <= now) { timers[i] = null; t[1](); } } };"
              "const m = require(process.argv[1]); const scrolls = [];"
              "globalThis.matchMedia = () => ({ matches: " + ("true" if width <= 900 else "false") + " });"
              "globalThis.scrollBy = (x, y) => { scrolls.push(y); };"
              "globalThis.__rects = " + json.dumps(RECTS) + ";"
              "m.data.value = { report_sections: " + json.dumps(SECTIONS) + " };"
              "const handle = { setPointerCapture() {}, focus() {}, addEventListener() {}, removeEventListener() {} };"
              "m.startDrag({ button: 0, clientX: 800, clientY: 800, pointerId: 1, pointerType: " + json.dumps(kind) + ", preventDefault() {} }, handle, 'd', 4);"
              "const steps = " + json.dumps(steps) + "; let drawn = false;"
              "for (const s of steps) {"
              "  if (s === 'up') docL.pointerup({ pointerId: 1, type: 'pointerup' });"
              "  else if (s[0] === 'wait') { now += s[1]; fire(); }"
              "  else { docL.pointermove({ pointerId: 1, clientX: s[0], clientY: s[1] }); now += s[2]; fire(); }"
              "  if (m.dropAt.value) drawn = true;"
              "}"
              "console.log(JSON.stringify({ drawn, scrolls, pending: timers.filter(Boolean).length }));")
        done = subprocess.run(["node", "-e", js, str(self.out)], capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr[-800:])
        return json.loads(done.stdout)

    def test_a_finger_that_holds_400_ms_then_moves_drags(self):
        for w in WIDTHS:
            with self.subTest(width=w):
                got = self.run_script(w, "touch", [["wait", 450], [800, 320, 130]])
                self.assertTrue(got["drawn"], "the slot is drawn")
                self.assertEqual(got["scrolls"], [], "the page did not scroll")

    def test_the_hold_is_exactly_400_ms(self):
        for w in WIDTHS:
            with self.subTest(width=w):
                early = self.run_script(w, "touch", [["wait", 390], [800, 320, 130]])
                self.assertFalse(early["drawn"], "390 ms is too short")
                right = self.run_script(w, "touch", [["wait", 400], [800, 320, 130]])
                self.assertTrue(right["drawn"], "400 ms is enough")

    def test_a_finger_that_moves_before_the_hold_scrolls_the_page_and_drags_nothing(self):
        for w in WIDTHS:
            with self.subTest(width=w):
                got = self.run_script(w, "touch", [[800, 770, 50], [800, 740, 50], ["wait", 600], [800, 320, 130], "up"])
                self.assertFalse(got["drawn"], "no drag, even after 400 ms has passed")
                self.assertEqual(got["scrolls"][:2], [30, 30], "the page followed the finger by hand")

    def test_a_small_shake_under_the_threshold_is_not_a_swipe_and_four_px_is(self):
        for w in WIDTHS:
            with self.subTest(width=w):
                shake = self.run_script(w, "touch", [[800, 798, 50], ["wait", 450], [800, 320, 130]])
                self.assertTrue(shake["drawn"], "2 px is a shake: the hold still ends and the drag starts")
                self.assertEqual(shake["scrolls"], [], "2 px did not scroll")
                swipe = self.run_script(w, "touch", [[800, 796, 50]])
                self.assertEqual(swipe["scrolls"], [4], "4 px is the threshold: a swipe")

    def test_a_finger_let_go_before_the_hold_leaves_no_timer_and_no_drag(self):
        for w in WIDTHS:
            with self.subTest(width=w):
                got = self.run_script(w, "touch", [["wait", 100], "up", ["wait", 600], [800, 320, 130]])
                self.assertEqual(got["pending"], 0, "the release took the hold timer away")
                self.assertFalse(got["drawn"])

    def test_a_mouse_drags_at_once_without_a_hold(self):
        for w in WIDTHS:
            with self.subTest(width=w):
                got = self.run_script(w, "mouse", [[800, 320, 130]])
                self.assertTrue(got["drawn"])
                self.assertEqual(got["scrolls"], [])


if __name__ == "__main__":
    unittest.main()
