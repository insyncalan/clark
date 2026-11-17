"""Row 1214: when the page lets go of a drag because the person moves through history (Back, Forward), the store clears the
preview list as well as the line and the picked section, so the others do not stay out of place. Run:
cd tests && PYTHONPATH=../src:../vendor:. python3 -m unittest test_drag_leave_list_1214
No Chrome. report.js is bundled with the pinned esbuild and run in node against a stand-in window; a popstate is fired by hand. The
stand-in answers at 1400 and 900 (matchMedia), the store acts the same at both.
"""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from test_title_limit import bundle  # noqa: E402

DRIVER = r"""
const cfg = JSON.parse(process.argv[2]);
const L = {};
globalThis.window = globalThis;
globalThis.addEventListener = (t, f) => { (L[t] = L[t] || []).push(f); }; globalThis.removeEventListener = () => {};
globalThis.matchMedia = () => ({ matches: cfg.width <= 900, addEventListener() {}, removeEventListener() {} });
globalThis.requestAnimationFrame = () => 1; globalThis.cancelAnimationFrame = () => {}; globalThis.scrollTo = () => {}; globalThis.scrollBy = () => {};
globalThis.innerHeight = 800; globalThis.scrollX = 0; globalThis.scrollY = 0;
globalThis.location = { search: '', hash: '#dashboard', pathname: '/', href: 'http://x/' };
globalThis.history = { state: null, pushState() {}, replaceState() {}, back() {} };
globalThis.document = { addEventListener() {}, removeEventListener() {}, querySelector() { return null; }, querySelectorAll() { return []; },
  createElement() { return { style: {}, setAttribute() {}, remove() {} }; }, body: {}, activeElement: null, documentElement: { dataset: {} } };
const kept = {}; globalThis.localStorage = { getItem: k => kept[k] ?? null, setItem: (k, v) => { kept[k] = v; }, removeItem: k => { delete kept[k]; } };
globalThis.fetch = async () => ({ ok: true, status: 200, json: async () => ({ ok: true }), text: async () => '' });
const m = require(process.argv[1]);
m.dragFrom.value = 'A'; m.dropAt.value = { id: 'B', where: 'after' }; m.dragList.value = [{ id: 'B' }, { id: 'A' }];
let atMove = null; let first = true;
m.view.subscribe(() => { if (first) { first = false; return; } atMove = { list: m.dragList.value === undefined ? 'undefined' : 'set', from: m.dragFrom.value ?? null }; });
location.hash = '#settings';
for (const f of (L.popstate || [])) f({});
console.log(JSON.stringify({ listeners: (L.popstate || []).length, from: m.dragFrom.value ?? null, drop: m.dropAt.value ?? null,
  list: m.dragList.value === undefined ? 'undefined' : 'set', atMove }));
"""


class DragLeaveList(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls._tmp.cleanup)
        cls.out = bundle('export { dragFrom, dropAt, dragList, view } from "@src/stores/report.js";', Path(cls._tmp.name), None, "dragleave.cjs")

    def test_going_back_clears_the_line_the_picked_section_and_the_preview_list(self):
        for w in (1400, 900):
            with self.subTest(width=w):
                done = subprocess.run(["node", "-e", DRIVER, str(self.out), json.dumps({"width": w})], capture_output=True, text=True)
                self.assertEqual(done.returncode, 0, done.stderr[-800:])
                got = json.loads(done.stdout)
                self.assertGreaterEqual(got["listeners"], 1, "the page listens for Back")
                self.assertIsNone(got["from"])
                self.assertIsNone(got["drop"])
                self.assertEqual(got["list"], "undefined", "the others do not stay out of place")


    def test_the_drag_is_let_go_before_the_page_moves_to_the_address(self):
        for w in (1400, 900):
            with self.subTest(width=w):
                done = subprocess.run(["node", "-e", DRIVER, str(self.out), json.dumps({"width": w})], capture_output=True, text=True)
                self.assertEqual(done.returncode, 0, done.stderr[-800:])
                at = json.loads(done.stdout)["atMove"]
                self.assertIsNotNone(at, "the page moved to the address")
                self.assertEqual(at["list"], "undefined", "the preview list is already gone when the page redraws")
                self.assertIsNone(at["from"], "the picked section is already let go when the page redraws")


if __name__ == "__main__":
    unittest.main()
