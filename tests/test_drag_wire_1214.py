"""Row 1214: the wiring of the live drag in edit/drag.js. The target is decided from the rectangles measured when the drag starts,
the slot moves only after the pointer has rested 110 ms on a new target, the page is redrawn only when the shown target changes,
the drop is the shown target, and Esc puts everything back.

Run: cd tests && PYTHONPATH=../src:../vendor:. python3 -m unittest test_drag_wire_1214
No Chrome. drag.js's own startDrag is bundled with the pinned esbuild and run in node against stand-in DOM objects and a stand-in
clock: a timer set by the page runs when the test moves the clock past it, so nothing here waits in real time. A release sends
its change through the page's own placeAt; the request body is read from a stand-in fetch.
"""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from test_drag_skips_needs_section import STAND_IN  # noqa: E402
from test_title_limit import bundle  # noqa: E402


def sec(id):
    return {"id": id, "type": "text", "title": id.upper(), "beside": 0, "hidden": 0}


# Rows a, b, c, d, each 1000 wide and 200 high, 20 apart: b is top 220, bottom 420; its right half starts at x 500.
SECTIONS = [sec("a"), sec("b"), sec("c"), sec("d")]
RECTS = [["a", 0, 200], ["b", 220, 420], ["c", 440, 640], ["d", 660, 860]]
SHAKE = [[800 + dx, 320 + dy] for dx, dy in [(0, 0), (3, -2), (-3, 3), (2, 2), (-2, -3), (3, 0), (0, 3), (-3, -1), (1, -3), (0, 0)]]


class DragWire(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls._tmp.cleanup)
        cls.out = bundle('export { startDrag } from "@src/edit/drag.js";'
                         'export { data, dropAt } from "@src/stores/report.js";'
                         'export { place, applied } from "@src/logic/placement.js";', Path(cls._tmp.name), None, "dragwire.cjs")

    def run_script(self, moved, steps, rects_after=None):
        """steps: a list of [x, y, ms] (pointer move, then the clock runs ms), or "esc", or "up". Returns what was drawn and dropped."""
        js = (STAND_IN.replace("querySelectorAll() { return globalThis.__rects.map(",
                               "querySelectorAll() { globalThis.__measured++; return globalThis.__rects.map(")
              + "const fire = () => { for (let i = 0; i < timers.length; i++) { const t = timers[i]; if (t && t[0] <= now) { timers[i] = null; t[1](); } } };"
              "const m = require(process.argv[1]); globalThis.__measured = 0; const sent = [];"
              "globalThis.fetch = async (u, o) => { sent.push(String((o && o.body) || '')); return { ok: false, status: 500, json: async () => ({}), text: async () => '' }; };"
              "(async () => {"
              "globalThis.rect_of = (id) => globalThis.__rects.find((r) => r[0] === id);"
              "globalThis.__rects = " + json.dumps(RECTS) + ";"
              "const stored = " + json.dumps(SECTIONS) + ";"
              "m.data.value = { report_sections: stored };"
              "const L = {}; const handle = { setPointerCapture() {}, focus() {}, addEventListener(t, f) { L[t] = f; }, removeEventListener() {} };"
              "let writes = 0; m.dropAt.subscribe(() => { writes++; });"
              "const draws = []; let last; const watch = () => { const v = JSON.stringify(m.dropAt.value ?? null); if (v !== last) { last = v; draws.push(JSON.parse(v)); } };"
              "m.startDrag({ button: 0, clientX: 800, clientY: 800, pointerId: 1, preventDefault() {} }, handle, " + json.dumps(moved) + ", 4);"
              "watch(); const steps = " + json.dumps(steps) + "; const seen = [];"
              "for (const s of steps) {"
              "  if (s === 'esc') docL.keydown({ key: 'Escape' });"
              "  else if (s === 'up') { docL.pointerup({ pointerId: 1, type: 'pointerup' }); }"
              "  else if (s[0] === 'wait') { now += s[1]; fire(); }"
              "  else if (s[0] === 'scroll') { globalThis.scrollY = s[1]; }"
              "  else if (s[0] === 'rects') { globalThis.__rects = s[1]; }"
              "  else { docL.pointermove({ pointerId: 1, clientX: s[0], clientY: s[1] }); now += s[2]; fire(); }"
              "  watch(); seen.push(JSON.parse(JSON.stringify(m.dropAt.value ?? null)));"
              "}"
              "for (let i = 0; i < 20; i++) await new Promise((r) => setImmediate(r));"
              "console.log(JSON.stringify({ draws, seen, measured: globalThis.__measured, writes, sent }));"
              "})();")
        done = subprocess.run(["node", "-e", js, str(self.out)], capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr[-800:])
        return json.loads(done.stdout)

    def test_the_rects_are_measured_once_when_the_drag_starts(self):
        got = self.run_script("d", [[800, 320, 130]] * 6)
        self.assertEqual(got["measured"], 1)

    def test_a_pointer_held_almost_still_keeps_one_target_and_draws_it_once(self):
        got = self.run_script("d", [[x, y, 30] for x, y in SHAKE])
        self.assertEqual(got["draws"], [None, {"outline": "b", "side": "right"}])
        self.assertEqual(got["seen"][0], None, "not drawn before the rest")
        self.assertEqual(got["seen"][-1], {"outline": "b", "side": "right"})

    def test_the_slot_does_not_move_before_the_110_ms_rest(self):
        got = self.run_script("d", [[800, 320, 100]])
        self.assertEqual(got["seen"], [None])
        got = self.run_script("d", [[800, 320, 110]])
        self.assertEqual(got["seen"], [{"outline": "b", "side": "right"}])

    def test_a_pointer_that_stops_still_counts_as_resting_without_another_move(self):
        got = self.run_script("d", [[800, 320, 50], [800, 320, 0]])
        self.assertEqual(got["seen"], [None, None], "50 ms after the first move and 0 ms after the second: not yet at rest")
        got = self.run_script("d", [[800, 320, 50], ["wait", 59]])
        self.assertEqual(got["seen"], [None, None], "109 ms after the move: still not at rest")
        got = self.run_script("d", [[800, 320, 50], ["wait", 60]])
        self.assertEqual(got["seen"], [None, {"outline": "b", "side": "right"}], "110 ms after the move, no further move: the timer settles it")

    def test_a_quick_pass_over_another_section_changes_nothing(self):
        got = self.run_script("d", [[800, 320, 130], [800, 540, 40], [800, 320, 130]])
        self.assertEqual(got["draws"], [None, {"outline": "b", "side": "right"}])

    def test_the_page_is_redrawn_only_when_the_shown_target_changes(self):
        got = self.run_script("d", [[x, y, 30] for x, y in SHAKE] + [[800, 320, 130]] * 5)
        self.assertEqual(got["writes"], 1 + 1, "the signal's first call, then the one change")

    def test_a_scroll_during_the_drag_moves_the_pointer_in_the_frame_of_the_start_rects(self):
        # the page scrolled 100 px: the pointer at viewport y 220 is over what was y 320 when the rects were measured, b's middle
        got = self.run_script("d", [["scroll", 100], [800, 220, 130]])
        self.assertEqual(got["seen"][-1], {"outline": "b", "side": "right"})

    def test_the_sections_moving_on_the_page_do_not_change_the_target(self):
        # the page rearranges under the pointer: b's rectangle now sits elsewhere, as the preview would leave it
        moved = [["a", 0, 200], ["c", 220, 420], ["b", 440, 640], ["d", 660, 860]]
        got = self.run_script("d", [[800, 320, 130], ["rects", moved], [801, 321, 130], [799, 319, 130]])
        self.assertEqual(got["draws"], [None, {"outline": "b", "side": "right"}])

    def test_esc_puts_everything_back_and_more_movement_cannot_bring_it_back(self):
        got = self.run_script("d", [[800, 320, 130], "esc", [800, 321, 130], [800, 321, 0]])
        self.assertEqual(got["seen"], [{"outline": "b", "side": "right"}, None, None, None])

    def test_esc_before_the_rest_ends_leaves_nothing_to_draw_when_the_timer_would_have_run(self):
        got = self.run_script("d", [[800, 320, 50], "esc", ["wait", 60], ["wait", 110], ["wait", 110], "up"])
        self.assertEqual(got["seen"], [None] * 6)
        self.assertEqual(got["draws"], [None])
        self.assertEqual(got["sent"], [])

    def test_a_timer_that_runs_before_the_new_target_has_rested_sets_itself_again(self):
        # scrolled over c after 50 ms: the first timer (110 ms after the move) finds c new, so it must wait the time left
        got = self.run_script("d", [[800, 320, 50], ["scroll", 220], ["wait", 60]])
        self.assertEqual(got["seen"], [None, None, None], "c has rested 0 ms when the first timer runs")
        got = self.run_script("d", [[800, 320, 50], ["scroll", 220], ["wait", 60], ["wait", 109]])
        self.assertEqual(got["seen"][-1], None, "109 ms after the first timer: not yet")
        got = self.run_script("d", [[800, 320, 50], ["scroll", 220], ["wait", 60], ["wait", 110]])
        self.assertEqual(got["seen"][-1], {"outline": "c", "side": "right"}, "110 ms after: the second timer settles c without any move")

    def test_the_drop_makes_the_pair_whatever_the_last_pixel(self):
        for last in SHAKE:
            with self.subTest(last=last):
                got = self.run_script("d", [[x, y, 30] for x, y in SHAKE] + [[last[0], last[1], 0], "up"])
                body = " ".join(got["sent"])
                sent = [json.loads(b) for b in got["sent"]]
                self.assertEqual(len(sent), 1, got["sent"])
                self.assertEqual((sent[0]["id"], sent[0]["before"], sent[0]["flags"]), ("d", "c", {"b": 1}), "d beside b: the pair b d, then c")

    def test_a_release_before_the_rest_drops_nothing(self):
        got = self.run_script("d", [[800, 320, 50], "up"])
        self.assertEqual(got["sent"], [])

    def test_a_release_after_esc_drops_nothing(self):
        got = self.run_script("d", [[800, 320, 130], "esc", "up"])
        self.assertEqual(got["sent"], [])

    def test_release_clears_the_line(self):
        got = self.run_script("d", [[800, 320, 130], "up"])
        self.assertEqual(got["seen"][-1], None)


if __name__ == "__main__":
    unittest.main()
