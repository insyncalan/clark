"""Row 1214: what a drag in edit/drag.js leaves behind and when. While a section is dragged the page store knows which one (dragFrom), the
ghost and the old-place outline are on the page; every way the drag ends (release, Esc) takes them away, clears the drag stores, tells the
glide where the sections were, and leaves no listener on the document.

Run: cd tests && PYTHONPATH=../src:../vendor:. python3 -m unittest test_drag_state_1214
No Chrome. startDrag is bundled with the pinned esbuild and run in node against stand-in DOM objects and a stand-in clock, as in
test_drag_wire_1214. Run at 1400 (two columns) and 900 (one column) by the stand-in media query.
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


SECTIONS = [sec("a"), sec("b"), sec("c"), sec("d")]
RECTS = [["a", 0, 200], ["b", 220, 420], ["c", 440, 640], ["d", 660, 860]]
REST = 130          # a move, then the clock runs past the 110 ms rest


class DragState(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls._tmp.cleanup)
        cls.out = bundle('export { startDrag } from "@src/edit/drag.js";'
                         'export { data, dropAt, dragFrom, dragList } from "@src/stores/report.js";', Path(cls._tmp.name), None, "dragstate.cjs")

    def run_script(self, steps, width=1400):
        """steps: [x, y, ms] or [x, y, ms, pointerId] (a move, then the clock runs ms), "esc", "blur" (the window loses focus), "up", "up2" (a release of pointer 2), "lost", "lost2" (the handle, taken off the page, loses the capture of pointer 1, 2), "hidden" (the handle stays on the page but loses the capture, as when the preview hides it), "gone" (the grip is taken off the page and the browser says nothing: no lostpointercapture), "hiddenaway" (that, and no grip for the section can be found by the page's query), "swap" (the page draws a new grip for the section and takes the old one off, nothing else), "swaplost" (that, and the old grip loses the capture). Returns one snapshot after the start and one after each step."""
        js = (STAND_IN
              + "const m = require(process.argv[1]); const L = {}, W = {}, body = [], notes = [];"
              "globalThis.addEventListener = (t, f) => { W[t] = f; }; globalThis.removeEventListener = (t, f) => { if (W[t] === f) delete W[t]; };"
              "globalThis.matchMedia = () => ({ matches: " + ("true" if width == 900 else "false") + " });"
              "globalThis.__rects = " + json.dumps(RECTS) + ";"
              "const el = () => { const o = { style: {}, setAttribute() {}, remove() { const i = body.indexOf(o); if (i >= 0) body.splice(i, 1); } }; return o; };"
              "const secs = { querySelectorAll() { notes.push({ drop: m.dropAt.value ?? null, list: m.dragList.value ? 1 : null }); return []; } };"
              "globalThis.document = { addEventListener(t, f) { L[t] = f; }, removeEventListener(t, f) { if (L[t] === f) delete L[t]; },"
              " querySelector(q) { return q === '.secs' ? secs : null; }, createElement: el, body: { appendChild(o) { body.push(o); } },"
              " querySelectorAll() { return globalThis.__rects.map(([id, top, bottom]) => ({ dataset: { id }, getBoundingClientRect: () => ({ left: 0, right: 1000, top, bottom }) })); }, documentElement: { dataset: {} } };"
              "const sent = []; globalThis.fetch = async (u, o) => { sent.push(1); return { ok: false, status: 500, json: async () => ({}), text: async () => '' }; };"
              "const fire = () => { for (let i = 0; i < timers.length; i++) { const t = timers[i]; if (t && t[0] <= now) { timers[i] = null; t[1](); } } };"
              "m.data.value = { report_sections: " + json.dumps(SECTIONS) + " };"
              "globalThis.CSS = { escape: (x) => String(x) }; const grips = new Set(['d']); const docQuery = document.querySelector; document.querySelector = (q) => { const g = /data-id=\"([^\"]*)\"/.exec(q); if (g && /data-drag/.test(q)) return grips.has(g[1]) ? { isNew: true } : null; return docQuery(q); };"
              "const H = {}; const handle = { isConnected: true, setPointerCapture() {}, focus() {}, addEventListener(t, f) { H[t] = f; }, removeEventListener(t, f) { if (H[t] === f) delete H[t]; } };"
              "const snap = () => ({ from: m.dragFrom.value ?? null, list: m.dragList.value ? 1 : null, drop: m.dropAt.value ?? null, drawn: body.length,"
              " listeners: Object.keys(L).sort(), onWindow: Object.keys(W), onHandle: Object.keys(H), sent: sent.length, notes: notes.length, noted: notes.slice() });"
              "(async () => {"
              "m.startDrag({ button: 0, clientX: 200, clientY: 700, pointerId: 1, preventDefault() {} }, handle, 'd', 4);"
              "const out = [snap()];"
              "for (const s of " + json.dumps(steps) + ") {"
              "  if (s === 'esc') L.keydown && L.keydown({ key: 'Escape' });"
              "  else if (s === 'lost' || s === 'lost2' || s === 'hidden' || s === 'hiddenaway') { if (H.lostpointercapture) { const f = H.lostpointercapture; if (s === 'hiddenaway') grips.delete('d'); if (s !== 'hidden' && s !== 'hiddenaway') { handle.isConnected = false; grips.delete('d'); } f({ pointerId: s === 'lost2' ? 2 : 1, type: 'lostpointercapture' }); } }"
              "  else if (s === 'gone') { handle.isConnected = false; grips.delete('d'); }"
              "  else if (s === 'blur') W.blur && W.blur({ type: 'blur' });"
              "  else if (s === 'swap' || s === 'swaplost') { handle.isConnected = false; if (s === 'swaplost') H.lostpointercapture && H.lostpointercapture({ pointerId: 1, type: 'lostpointercapture' }); }"
              "  else if (s === 'up' || s === 'up2') L.pointerup && L.pointerup({ pointerId: s === 'up' ? 1 : 2, type: 'pointerup' });"
              "  else { L.pointermove && L.pointermove({ pointerId: s[3] || 1, clientX: s[0], clientY: s[1] }); now += s[2]; fire(); }"
              "  out.push(snap());"
              "}"
              "for (let i = 0; i < 20; i++) await new Promise((r) => setImmediate(r));"
              "out.push(snap());"
              "console.log(JSON.stringify(out));"
              "})();")
        done = subprocess.run(["node", "-e", js, str(self.out)], capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr[-800:])
        return json.loads(done.stdout)

    def test_a_grip_taken_off_the_page_ends_the_drag_at_the_next_move_without_any_lost_capture_event(self):
        # Row 1277: headless Chrome on macOS never fires lostpointercapture for a removed grip, so the move is what ends the drag.
        for width in (1400, 900):
            with self.subTest(width=width):
                got = self.run_script([[200, 330, REST], "gone", [200, 420, REST]], width)
                self.assertEqual(got[1]["drawn"], 3, "the drag is on before the grip goes")
                self.assertEqual(got[2]["drawn"], 3, "nothing ends it until the pointer moves: no event came")
                self.assertEqual((got[3]["from"], got[3]["drop"], got[3]["list"], got[3]["drawn"]), (None, None, None, 0))
                self.assertEqual((got[3]["listeners"], got[3]["onWindow"], got[3]["onHandle"]), ([], [], []))
                self.assertEqual(got[-1]["sent"], 0, "and a release after it drops nothing")
                got = self.run_script([[200, 330, REST], "gone", [200, 420, REST], "up"], width)
                self.assertEqual((got[-1]["sent"], got[-1]["drawn"]), (0, 0))

    def test_a_grip_the_page_drew_again_does_not_end_the_drag_at_a_move(self):
        got = self.run_script([[200, 330, REST], "swap", [200, 420, REST]])
        self.assertEqual(got[3]["from"], "d")
        self.assertEqual(got[3]["drawn"], 3)

    def test_while_dragging_the_store_names_the_section_and_the_ghost_and_outline_are_drawn(self):
        for width in (1400, 900):
            with self.subTest(width=width):
                got = self.run_script([[200, 330, REST]], width)
                self.assertEqual(got[0]["from"], None, "not before the pointer has moved")
                self.assertEqual(got[1]["from"], "d")
                self.assertEqual(got[1]["drawn"], 3, "the ghost, the old-place outline and the status line")
                self.assertIsNotNone(got[1]["drop"], "a slot is shown")
                self.assertEqual(got[1]["list"], 1, "the list the others make room by")

    def test_a_release_takes_everything_away(self):
        for width in (1400, 900):
            with self.subTest(width=width):
                for steps, left in (([[200, 330, REST], "up"], 0), ([[200, 330, 50], "up"], 1)):
                    got = self.run_script(steps, width)
                    self.assertEqual((got[-1]["from"], got[-1]["drop"], got[-1]["drawn"]), (None, None, left), steps)       # a release before the rest drops nowhere: the one thing left is the live region that says "stays where it is" (it stays, so the next drop is heard)
                    self.assertIsNone(got[-1]["list"], steps)

    def test_the_list_is_let_go_on_a_release_that_drops_nowhere(self):
        for width in (1400, 900):
            with self.subTest(width=width):
                got = self.run_script([[200, 330, REST], "esc", "up"], width)
                self.assertIsNone(got[-1]["list"])
                got = self.run_script([[200, 330, 50], "up"], width)
                self.assertEqual((got[-1]["from"], got[-1]["drawn"], got[-1]["list"]), (None, 1, None))      # the live region that says "stays where it is" is all that is left

    def test_esc_takes_everything_away_at_once(self):
        for width in (1400, 900):
            with self.subTest(width=width):
                got = self.run_script([[200, 330, REST], "esc"], width)
                self.assertEqual(got[1]["drawn"], 3)
                self.assertEqual((got[2]["from"], got[2]["drop"], got[2]["list"], got[2]["drawn"]), (None, None, None, 0))

    def test_the_glide_is_told_where_the_sections_were_before_the_page_changes(self):
        for width in (1400, 900):
            with self.subTest(width=width):
                got = self.run_script([[200, 330, REST]], width)
                first = got[1]["noted"][0]
                self.assertEqual((first["drop"], first["list"]), (None, None), "noted before the slot and the list are set, not after")

    def test_a_release_and_esc_each_tell_the_glide_once_more(self):
        for width in (1400, 900):
            with self.subTest(width=width):
                got = self.run_script([[200, 330, 50], "up"], width)
                self.assertEqual(got[2]["notes"], got[1]["notes"] + 1, "the release")
                got = self.run_script([[200, 330, 50], "esc"], width)
                self.assertEqual(got[2]["notes"], got[1]["notes"] + 1, "Esc")

    def test_no_listener_stays_on_the_document_after_the_drag(self):
        for width in (1400, 900):
            with self.subTest(width=width):
                got = self.run_script([[200, 330, REST]], width)
                self.assertEqual(got[1]["listeners"], ["keydown", "lostpointercapture", "pointercancel", "pointermove", "pointerup"])
                for steps in ([[200, 330, REST], "up"], [[200, 330, REST], "esc", "up"]):
                    self.assertEqual(self.run_script(steps, width)[-1]["listeners"], [], steps)

    def test_a_move_of_another_pointer_neither_starts_nor_steers_the_drag(self):
        for width in (1400, 900):
            with self.subTest(width=width):
                got = self.run_script([[200, 650, REST, 2]], width)
                self.assertEqual((got[1]["from"], got[1]["drawn"]), (None, 0), "another pointer does not start it")
                got = self.run_script([[200, 330, REST], [200, 650, REST, 2]], width)
                self.assertEqual(got[1]["drop"], got[2]["drop"], "another pointer does not move the slot")

    def test_a_release_of_another_pointer_does_not_end_the_drag(self):
        for width in (1400, 900):
            with self.subTest(width=width):
                got = self.run_script([[200, 330, REST], "up2"], width)
                self.assertEqual((got[2]["from"], got[2]["drawn"], got[2]["listeners"]), ("d", 3, got[1]["listeners"]))
                self.assertEqual(got[2]["drop"], got[1]["drop"])

    def test_a_handle_that_loses_the_pointer_ends_the_drag_without_a_drop(self):
        for width in (1400, 900):
            with self.subTest(width=width):
                got = self.run_script([[200, 330, REST], "lost"], width)
                self.assertIsNotNone(got[1]["drop"], "a slot was shown")
                self.assertEqual((got[2]["from"], got[2]["drop"], got[2]["list"], got[2]["drawn"]), (None, None, None, 0))
                self.assertEqual((got[2]["listeners"], got[2]["onHandle"], got[-1]["sent"]), ([], [], 0), "nothing left, nothing sent")
                self.assertEqual(got[2]["notes"], got[1]["notes"] + 1, "the glide is told once")

    def test_a_hidden_grip_that_loses_the_capture_is_still_on_the_page_and_the_drag_goes_on(self):
        for width in (1400, 900):
            with self.subTest(width=width):
                got = self.run_script([[200, 330, REST], "hidden", "up"], width)
                self.assertEqual((got[2]["from"], got[2]["drawn"], got[2]["listeners"]), ("d", 3, got[1]["listeners"]))
                self.assertEqual(got[-1]["sent"], 1, "and it still drops")

    def test_a_grip_still_on_the_page_that_loses_the_capture_does_not_end_the_drag_even_if_the_page_query_misses_it(self):
        for width in (1400, 900):
            with self.subTest(width=width):
                got = self.run_script([[200, 330, REST], "hiddenaway", "up"], width)
                self.assertEqual((got[2]["from"], got[2]["drawn"], got[2]["listeners"]), ("d", 3, got[1]["listeners"]))
                self.assertEqual(got[-1]["sent"], 1, "and it still drops")

    def test_the_lost_capture_of_another_pointer_is_ignored(self):
        for width in (1400, 900):
            with self.subTest(width=width):
                got = self.run_script([[200, 330, REST], "lost2"], width)
                self.assertEqual((got[2]["from"], got[2]["drawn"], got[2]["listeners"]), ("d", 3, got[1]["listeners"]))
                self.assertEqual(got[2]["drop"], got[1]["drop"])

    def test_a_normal_drop_drops_once_and_the_capture_released_after_it_changes_nothing(self):
        for width in (1400, 900):
            with self.subTest(width=width):
                got = self.run_script([[200, 330, REST], "up", "lost"], width)
                self.assertEqual(got[-1]["sent"], 1, "the drop, once, after the release of the capture too")
                self.assertEqual(got[3]["notes"], got[2]["notes"], "and does not run the clean-up again")
                self.assertEqual((got[2]["listeners"], got[2]["onHandle"]), ([], []))

    def test_a_grip_replaced_by_a_new_one_for_the_same_section_does_not_end_the_drag(self):
        for width in (1400, 900):
            with self.subTest(width=width):
                got = self.run_script([[200, 330, REST], "swaplost", [200, 100, REST], "up"], width)
                self.assertEqual((got[2]["from"], got[2]["drawn"], got[2]["listeners"]), ("d", 3, got[1]["listeners"]))
                self.assertEqual(got[2]["drop"], got[1]["drop"], "the slot stays")
                self.assertIsNotNone(got[3]["drop"], "and follows the pointer to a new target")
                self.assertEqual(got[-1]["sent"], 1, "one drop")

    def test_a_replaced_grip_that_says_nothing_leaves_the_drag_alive(self):
        for width in (1400, 900):
            with self.subTest(width=width):
                got = self.run_script([[200, 330, REST], "swap"], width)
                self.assertEqual((got[2]["from"], got[2]["drawn"], got[2]["listeners"]), ("d", 3, got[1]["listeners"]))

    def test_a_section_that_is_gone_ends_the_drag_without_a_drop(self):
        for width in (1400, 900):
            with self.subTest(width=width):
                got = self.run_script([[200, 330, REST], "lost", "up"], width)
                self.assertEqual((got[2]["from"], got[2]["drawn"], got[2]["listeners"], got[2]["onHandle"]), (None, 0, [], []))
                self.assertEqual(got[-1]["sent"], 0, "nothing sent")

    def test_a_window_that_loses_focus_ends_the_drag_without_a_drop(self):
        for width in (1400, 900):
            with self.subTest(width=width):
                got = self.run_script([[200, 330, REST], "blur", "up"], width)
                self.assertEqual(got[1]["onWindow"], ["blur"])
                self.assertIsNotNone(got[1]["drop"], "a slot was shown")
                self.assertEqual((got[2]["from"], got[2]["drop"], got[2]["list"], got[2]["drawn"]), (None, None, None, 0))
                self.assertEqual((got[2]["listeners"], got[2]["onWindow"], got[2]["onHandle"], got[-1]["sent"]), ([], [], [], 0), "nothing left, nothing sent")
                self.assertEqual(got[2]["notes"], got[1]["notes"] + 1, "the glide is told once")

    def test_a_blur_before_the_drag_has_moved_leaves_nothing_and_a_release_drops_nothing(self):
        for width in (1400, 900):
            with self.subTest(width=width):
                got = self.run_script(["blur", "up"], width)
                self.assertEqual((got[1]["listeners"], got[1]["onWindow"], got[1]["onHandle"], got[-1]["sent"]), ([], [], [], 0))

    def test_a_normal_release_takes_the_blur_listener_away_too(self):
        got = self.run_script([[200, 330, REST], "up"])
        self.assertEqual((got[2]["onWindow"], got[-1]["sent"]), ([], 1))

    def test_the_handle_listens_for_the_lost_capture_while_dragging(self):
        got = self.run_script([[200, 330, REST]])
        self.assertEqual(got[0]["onHandle"], ["lostpointercapture"])


if __name__ == "__main__":
    unittest.main()
