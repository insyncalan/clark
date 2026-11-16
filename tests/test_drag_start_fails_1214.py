"""Row 1214: a drag start that cannot measure the sections must not block the next one. Run:
cd tests && PYTHONPATH=../src:../vendor:. python3 -m unittest test_drag_start_fails_1214
No Chrome. drag.js's startDrag is bundled with the pinned esbuild and run in node against stand-in DOM objects.
Run at 1400 and 900. Rule held: a start whose measuring throws leaves no drag marked on, so the next press starts a drag of its own.
"""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from test_title_limit import bundle  # noqa: E402

SECTIONS = [{"id": i, "type": "text", "title": t, "beside": 0, "hidden": 0} for i, t in (("A", "Summary"), ("B", "This week"), ("C", "Next week"))]
RECTS = [["A", 0, 100], ["B", 120, 220], ["C", 240, 340]]

DRIVER = r"""
const cfg = JSON.parse(process.argv[2]);
let clock = 0; const timers = []; let seq = 0;
Object.defineProperty(globalThis, 'performance', { value: { now: () => clock }, configurable: true });
globalThis.setTimeout = (fn, ms) => { const id = ++seq; timers.push({ id, at: clock + ms, fn }); return id; };
globalThis.clearTimeout = (id) => { const k = timers.findIndex((t) => t.id === id); if (k >= 0) timers.splice(k, 1); };
globalThis.addEventListener = () => {}; globalThis.removeEventListener = () => {}; globalThis.window = globalThis;
globalThis.matchMedia = () => ({ matches: cfg.width <= 900 });
globalThis.requestAnimationFrame = () => 1; globalThis.cancelAnimationFrame = () => {}; globalThis.scrollBy = () => {}; globalThis.innerHeight = 800;
globalThis.location = { search: '', hash: '', pathname: '/', href: 'http://x/' };
globalThis.scrollX = 0; globalThis.scrollY = 0;
const docL = {}; let adds = 0, live = 0;
globalThis.document = { addEventListener(t, f) { adds++; docL[t] = f; }, removeEventListener(t) { delete docL[t]; }, querySelector() { return null; },
  createElement() { live++; return { style: {}, setAttribute() {}, remove() { live--; } }; }, body: { appendChild() {} },
  querySelectorAll() { if (globalThis.broken) throw new Error('cannot measure'); return cfg.rects.map(([id, top, bottom]) => ({ dataset: { id }, getBoundingClientRect: () => ({ left: 0, right: 400, top, bottom }) })); }, documentElement: { dataset: {} } };
const kept = {}; globalThis.localStorage = { getItem: k => kept[k] ?? null, setItem: (k, v) => { kept[k] = v; }, removeItem: k => { delete kept[k]; } };
globalThis.fetch = async () => ({ ok: true, status: 200, json: async () => ({ ok: true, data: { report_sections: cfg.sections } }), text: async () => '{}' });
const m = require(process.argv[1]);
m.project.value = 'ABC'; m.data.value = { report_sections: cfg.sections };
const handle = { setPointerCapture() {}, focus() {}, addEventListener() {}, removeEventListener() {} };
const press = (id, pid) => m.startDrag({ button: 0, clientX: 0, clientY: 0, pointerId: pid, preventDefault() {} }, handle, id, 3);
const advance = (to) => { for (let n = 0; n < 1000; n++) { timers.sort((a, b) => a.at - b.at); const t = timers[0]; if (!t || t.at > to) break; timers.shift(); clock = t.at; t.fn(); } clock = to; };
globalThis.broken = true;
let thrown = 0;
try { press('C', 1); } catch (x) { thrown++; }
const afterFail = Object.keys(docL);
globalThis.broken = false;
press('C', 2);
console.log(JSON.stringify({ thrown, afterFail, adds, listeners: Object.keys(docL).sort() }));
"""


class DragStartFails(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls._tmp.cleanup)
        cls.out = bundle('export { startDrag } from "@src/edit/drag.js";'
                         'export { data, dropAt, dragList, dragFrom, project } from "@src/stores/report.js";', Path(cls._tmp.name), None, "dragstartfails.cjs")

    def run_drag(self, width):
        cfg = {"width": width, "rects": RECTS, "sections": SECTIONS}
        done = subprocess.run(["node", "-e", DRIVER, str(self.out), json.dumps(cfg)], capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr[-800:])
        return json.loads(done.stdout)

    def test_a_start_that_cannot_measure_leaves_the_next_press_free_to_start(self):
        for w in (1400, 900):
            with self.subTest(width=w):
                got = self.run_drag(w)
                self.assertEqual(got["thrown"], 1, "the unmeasurable start fails")
                self.assertEqual(got["afterFail"], [], "and adds no document listener")
                self.assertEqual(got["adds"], 4, "the next press added its own four listeners")


if __name__ == "__main__":
    unittest.main()
