"""Row 1214: what edit/drag.js leaves behind when a drag ends, pinned.

Run: cd tests && PYTHONPATH=../src:../vendor:. python3 -m unittest test_drag_listeners_1214
No Chrome. startDrag is bundled and run in node against the stand-in DOM of test_drag_skips_needs_section, with one change: the
stand-in document keeps its listeners as the real one does, by type, function and capture flag, so a removal that names another
capture flag removes nothing.
- after a release (and after Esc and a leave) no listener of the drag is left on the document, the capture one included;
- a drop whose placement throws at once says so, lets go of the preview list and of the saving hold, and a new drag can start.
"""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from test_drag_skips_needs_section import STAND_IN  # noqa: E402
from test_title_limit import bundle  # noqa: E402

SECTIONS = [{"id": i, "type": "text", "title": i.upper(), "beside": 0, "hidden": 0} for i in "abcd"]
RECTS = [["a", 0, 200], ["b", 220, 420], ["c", 440, 640], ["d", 660, 860]]

LISTENERS = ("const live = [];"
             "const same = (a, t, f, c) => a.t === t && a.f === f && a.c === c;"
             "document.addEventListener = (t, f, c) => { const cap = c === true || !!(c && c.capture); if (!live.some((a) => same(a, t, f, cap))) live.push({ t, f, c: cap }); docL[t] = f; };"
             "document.removeEventListener = (t, f, c) => { const cap = c === true || !!(c && c.capture); const i = live.findIndex((a) => same(a, t, f, cap)); if (i >= 0) live.splice(i, 1); };"
             "const left = () => live.map((a) => a.t + (a.c ? ' (capture)' : ''));")


class DragState(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls._tmp.cleanup)
        cls.out = bundle('export { startDrag } from "@src/edit/drag.js";'
                         'export { data, dropAt, dragFrom, dragList } from "@src/stores/report.js";', Path(cls._tmp.name), None, "dragstate.cjs")

    def run_node(self, body):
        js = (STAND_IN + LISTENERS + "const m = require(process.argv[1]);"
              "globalThis.__rects = " + json.dumps(RECTS) + ";"
              "m.data.value = { report_sections: " + json.dumps(SECTIONS) + " };"
              "const handle = { setPointerCapture() {}, focus() {}, addEventListener() {}, removeEventListener() {} };"
              "const down = () => m.startDrag({ button: 0, clientX: 800, clientY: 800, pointerId: 1, preventDefault() {} }, handle, 'd', 4);"
              "const moveTo = (x, y) => { docL.pointermove({ pointerId: 1, clientX: x, clientY: y }); rest(); };"
              "(async () => {" + body + "})();")
        done = subprocess.run(["node", "-e", js, str(self.out)], capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr[-800:])
        return json.loads(done.stdout)

    def test_the_stand_in_document_removes_only_with_the_same_capture_flag(self):
        got = self.run_node("const f = () => {}; document.addEventListener('keydown', f, true); document.removeEventListener('keydown', f);"
                            "const kept = left(); document.removeEventListener('keydown', f, true); console.log(JSON.stringify({ kept, after: left() }));")
        self.assertEqual(got, {"kept": ["keydown (capture)"], "after": []})

    def test_a_drag_puts_four_listeners_on_the_document_and_a_release_takes_every_one_off(self):
        got = self.run_node("down(); const during = left(); moveTo(800, 320); docL.pointerup({ pointerId: 1, type: 'pointerup' });"
                            "await new Promise((r) => setImmediate(r)); console.log(JSON.stringify({ during, after: left() }));")
        self.assertEqual(sorted(got["during"]), ["keydown (capture)", "pointercancel", "pointermove", "pointerup"])
        self.assertEqual(got["after"], [], "the capture listener for Esc must not outlive the drag")

    def test_a_release_without_a_move_takes_every_listener_off(self):
        got = self.run_node("down(); docL.pointerup({ pointerId: 1, type: 'pointerup' }); console.log(JSON.stringify({ after: left() }));")
        self.assertEqual(got["after"], [])

    def test_a_cancelled_pointer_takes_every_listener_off(self):
        got = self.run_node("down(); moveTo(800, 320); docL.pointercancel({ pointerId: 1, type: 'pointercancel' }); console.log(JSON.stringify({ after: left() }));")
        self.assertEqual(got["after"], [])

    def test_a_drop_whose_placement_throws_lets_go_of_the_list_and_the_hold_and_a_new_drag_starts(self):
        got = self.run_node(
            "down(); moveTo(800, 320);"
            "const shown = m.dragList.value ? m.dragList.value.length : null;"          # the preview list is up while the pointer rests
            "m.data.value = { get report_sections() { throw new Error('placement cannot start'); } };"       # placeAt reads the list and throws before it sends anything
            "docL.pointerup({ pointerId: 1, type: 'pointerup' });"
            "for (let i = 0; i < 10; i++) await new Promise((r) => setImmediate(r));"
            "const list = m.dragList.value === undefined, none = left();"
            "m.data.value = { report_sections: " + json.dumps(SECTIONS) + " };"
            "down();"
            "console.log(JSON.stringify({ shown, list, none, again: left() }));")
        self.assertEqual(got["shown"], 4, "the preview list was up before the drop")
        self.assertTrue(got["list"], "the preview list is gone")
        self.assertEqual(got["none"], [], "no listener of the first drag is left")
        self.assertEqual(sorted(got["again"]), ["keydown (capture)", "pointercancel", "pointermove", "pointerup"], "a new drag started: the saving hold is released")

    def test_a_drop_that_is_refused_later_lets_go_too(self):
        got = self.run_node(
            "globalThis.fetch = async () => ({ ok: false, status: 500, json: async () => ({}), text: async () => '' });"
            "down(); moveTo(800, 320); docL.pointerup({ pointerId: 1, type: 'pointerup' });"
            "for (let i = 0; i < 30; i++) await new Promise((r) => setImmediate(r));"
            "const list = m.dragList.value === undefined; down();"
            "console.log(JSON.stringify({ list, again: left() }));")
        self.assertTrue(got["list"])
        self.assertEqual(len(got["again"]), 4, "a new drag can start")


if __name__ == "__main__":
    unittest.main()
