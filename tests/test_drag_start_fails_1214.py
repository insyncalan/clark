"""Row 1214: a drag that cannot start (the sections cannot be measured) must not block the next one. Run:
cd tests && PYTHONPATH=../src:../vendor:. python3 -m unittest test_drag_start_fails_1214
No Chrome. Same node harness as test_drag_ends_1214, at 1400 and 900.
"""
import json
import subprocess
import tempfile
from pathlib import Path
import unittest

import test_drag_wired_1214 as wired  # noqa: E402
from test_title_limit import bundle  # noqa: E402
from test_drag_wired_1214 import DRIVER as BASE, RECTS, W  # noqa: E402

DRIVER = BASE
for a, b in (
    ("const docL = {};", "const docL = {}; let adds = 0, thrown = 0;"),
    ("addEventListener(t, f) { docL[t] = f; }", "addEventListener(t, f) { adds++; docL[t] = f; }"),
    ("console.log(JSON.stringify({ log,", "console.log(JSON.stringify({ adds, thrown, listeners: Object.keys(docL), log,"),
    ("    if (op.ev === 'esc')",
     "    if (op.ev === 'rawup') { docL.pointerup && docL.pointerup({ pointerId: 1, type: 'pointerup' }); for (let i = 0; i < 30; i++) await new Promise((r) => setImmediate(r)); }\n"
     "    if (op.ev === 'trystart') { try { m.startDrag({ button: 0, clientX: 0, clientY: 0, pointerId: 1, preventDefault() {} }, handle, 'A', 3); } catch (x) { thrown++; } }\n"
     "    if (op.ev === 'esc')"),
):
    assert DRIVER.count(a) == 1, a
    DRIVER = DRIVER.replace(a, b)


class DragStartFails(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls._tmp.cleanup)
        cls.out = bundle('export { startDrag } from "@src/edit/drag.js";'
                         'export { data, dropAt, dragFrom, dragList, project } from "@src/stores/report.js";'
                         'export { toast } from "@src/stores/changes.js";', Path(cls._tmp.name), None, "dragstartfails.cjs")

    def run_drag(self, width, ops):
        cfg = {"early": 0, "fail": None, "width": width, "ops": ops, "moved": "C", "rects": RECTS,
               "sections": wired.SECTIONS}
        done = subprocess.run(["node", "-e", DRIVER, str(self.out), json.dumps(cfg)], capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr[-800:])
        return json.loads(done.stdout)

    def test_a_start_that_cannot_measure_leaves_the_next_drag_free_to_start(self):
        for w in W.values():
            with self.subTest(width=w):
                got = self.run_drag(w, [
                    {"t": 1, "ev": "rawup"},                      # the first drag (started by the driver) ends
                    {"t": 2, "ev": "rects", "rects": None},       # the sections cannot be measured
                    {"t": 3, "ev": "trystart"},                   # this start fails
                    {"t": 4, "ev": "rects", "rects": RECTS},      # measurable again
                    {"t": 5, "ev": "trystart"},                   # a new drag must start now
                ])
                self.assertEqual(got["thrown"], 1, "only the unmeasurable start fails")
                self.assertEqual(got["adds"], 8, "the first and the last start each add the four listeners")


if __name__ == "__main__":
    unittest.main()
