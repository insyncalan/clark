"""Item 1174: a drag drop target must skip a stored Needs section, because the Dashboard does not draw it (item 1158).

Run: cd tests && PYTHONPATH=../src:../vendor:. python3 -m unittest test_drag_skips_needs_section
No Chrome. drag.js's own startDrag is bundled with the pinned esbuild and run in node against stand-in DOM objects: the sections the
page draws have rectangles, the stored Needs section has none (nothing draws it), and the pointer is moved through the handle's own
pointermove listener. What the person would see is read from dropAt, the signal the page draws the drop line or outline from, and
from the order the drop's change gives with the Needs section left out.
"""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from _paths import ROOT

from test_title_limit import bundle  # noqa: E402

STAND_IN = ("globalThis.addEventListener = () => {}; globalThis.removeEventListener = () => {}; globalThis.window = globalThis;"
            "globalThis.matchMedia = () => ({ matches: false });"
            "globalThis.location = { search: '', hash: '', pathname: '/', href: 'http://x/' };"
            "const docL = {};"
            "globalThis.document = { addEventListener(t, f) { docL[t] = f; }, removeEventListener() {}, querySelector() { return null; },"
            " querySelectorAll() { return globalThis.__rects.map(([id, top, bottom]) => ({ dataset: { id },"
            " getBoundingClientRect: () => ({ left: 0, right: 400, top, bottom }) })); }, documentElement: { dataset: {} } };"
            "const kept = {}; globalThis.localStorage = { getItem: k => kept[k] ?? null, setItem: (k, v) => { kept[k] = v; }, removeItem: k => { delete kept[k]; } };")

# stored order: A, a Needs section (not drawn), B, C. The person sees A, B, C.
def sections(a_beside=0):
    return [
        {"id": "A", "type": "text", "title": "Summary", "beside": a_beside, "hidden": 0},
        {"id": "N", "type": "needs", "title": "Needs from you", "beside": 0, "hidden": 0},
        {"id": "B", "type": "text", "title": "This week", "beside": 0, "hidden": 0},
        {"id": "C", "type": "text", "title": "Next week", "beside": 0, "hidden": 0},
    ]


RECTS = [["A", 0, 100], ["B", 120, 220], ["C", 240, 340]]     # no rectangle for N: it is not drawn


class DragSkipsNeeds(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls._tmp.cleanup)
        cls.out = bundle('export { startDrag } from "@src/edit/drag.js";'
                         'export { data, dropAt } from "@src/stores/report.js";'
                         'export { place, applied } from "@src/logic/placement.js";', Path(cls._tmp.name), None, "dragneeds.cjs")

    def drag(self, moved, a_beside, x, y):
        """Drag `moved` and leave the pointer at (x, y); return what dropAt shows and the order the person would then see."""
        js = (STAND_IN + "const m = require(process.argv[1]);"
              "globalThis.__rects = " + json.dumps(RECTS) + ";"
              "const stored = " + json.dumps(sections(a_beside)) + ";"
              "m.data.value = { report_sections: stored };"
              "const L = {}; const handle = { setPointerCapture() {}, focus() {}, addEventListener(t, f) { L[t] = f; }, removeEventListener() {} };"
              "m.startDrag({ button: 0, clientX: 0, clientY: 0, pointerId: 1, preventDefault() {} }, handle, " + json.dumps(moved) + ", 3);"
              "L.pointermove({ clientX: " + str(x) + ", clientY: " + str(y) + " });"
              "const drop = m.dropAt.value || null;"
              "let order = null;"
              "if (drop && drop.line === 'before') {"
              "  const drawn = stored.filter((s) => s.type !== 'needs');"
              "  const p = m.place(drawn, " + json.dumps(moved) + ", { before: drop.ids[0] });"
              "  order = p.ok ? m.applied(stored, p.payload).filter((s) => s.type !== 'needs').map((s) => s.id) : null;"
              "}"
              "console.log(JSON.stringify({ drop, order }));")
        done = subprocess.run(["node", "-e", js, str(self.out)], capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr[-800:])
        return json.loads(done.stdout)

    def test_dropping_before_b_lands_directly_after_a_as_the_person_sees_it(self):
        # C dragged to the bottom edge of A: the next thing drawn after A is B, not the Needs section stored between them.
        got = self.drag("C", 0, 200, 95)
        self.assertEqual(got["drop"], {"line": "before", "ids": ["B"]}, "The line should sit above B, the next section drawn after A")
        self.assertEqual(got["order"], ["A", "C", "B"], "C should land directly after A as the person sees it")

    def test_a_section_flagged_beside_the_needs_section_still_shows_as_alone_with_two_halves(self):
        # A's stored flag pairs it with the Needs section, which is not drawn, so A is alone on its row and its middle is a half.
        got = self.drag("C", 1, 100, 50)
        self.assertEqual(got["drop"], {"outline": "A", "side": "left"}, "A is drawn alone, so its middle is a half to drop beside")


if __name__ == "__main__":
    unittest.main()
