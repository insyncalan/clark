"""Item 1174: Move up and Move down must count only the sections the page draws. The Dashboard leaves a stored Needs section out
(item 1158), but edit/actions.js, edit/drag.js and edit/AddDialog.jsx read data.report_sections unfiltered, so a section next to
a stored Needs section swaps with one nobody can see.

Run: cd tests && PYTHONPATH=../src:../vendor:. python3 -m unittest test_edit_needs_section_hidden
Part 1 runs the page's own canStep (bundled with the pinned esbuild, run in node; no browser) on [A, Needs, B]. Part 2 reads the
three files and wants every read of report_sections to leave the Needs type out. Both FAIL until the product code is fixed.
"""
import json
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

from _paths import ROOT

from test_title_limit import bundle  # noqa: E402

SRC = ROOT / "src" / "clark" / "page" / "src"
FILES = ("edit/actions.js", "edit/drag.js", "edit/AddDialog.jsx")

STAND_IN = ("globalThis.addEventListener = () => {}; globalThis.removeEventListener = () => {}; globalThis.window = globalThis;"
            "globalThis.location = { search: '', hash: '', pathname: '/', href: 'http://x/' };"
            "globalThis.document = { addEventListener() {}, querySelector() { return null; }, documentElement: { dataset: {} } };"
            "const kept = {}; globalThis.localStorage = { getItem: k => kept[k] ?? null, setItem: (k, v) => { kept[k] = v; }, removeItem: k => { delete kept[k]; } };")

# stored order: A, a Needs section (not drawn), B. The person sees A then B.
SECTIONS = [
    {"id": "A", "type": "text", "title": "Summary", "beside": 0, "hidden": 0},
    {"id": "N", "type": "needs", "title": "Needs from you", "beside": 0, "hidden": 0},
    {"id": "B", "type": "text", "title": "This week", "beside": 0, "hidden": 0},
]


class MoveNextToNeeds(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls._tmp.cleanup)
        tmp = Path(cls._tmp.name)
        out = bundle('export { canStep } from "@src/edit/actions.js";'
                     'export { data } from "@src/stores/report.js";', tmp, None, "needs.cjs")
        js = (STAND_IN + "const m = require(process.argv[1]);"
              "m.data.value = { report_sections: " + json.dumps(SECTIONS) + " };"
              "const pick = (r) => ({ ok: r.ok, before: r.payload ? r.payload.before : undefined });"
              "console.log(JSON.stringify({ bUp: pick(m.canStep('B', -1)), aDown: pick(m.canStep('A', 1)) }));")
        done = subprocess.run(["node", "-e", js, str(out)], capture_output=True, text=True)
        assert done.returncode == 0, done.stderr[-800:]
        cls.got = json.loads(done.stdout)

    def test_move_up_on_the_section_after_needs_passes_the_one_that_shows(self):
        # drawn list is [A, B]; B up lands directly before A. Unfiltered it lands before N, which is a swap with the invisible one.
        self.assertEqual(self.got["bUp"], {"ok": True, "before": "A"}, "Move up on B should put B before A, not before the Needs section")

    def test_move_down_on_the_section_before_needs_passes_the_one_that_shows(self):
        # drawn list is [A, B]; A down lands last (before: null). Unfiltered it lands before B, one place down past an invisible row.
        self.assertEqual(self.got["aDown"], {"ok": True, "before": None}, "Move down on A should put A last, not just past the Needs section")


class EveryReadLeavesNeedsOut(unittest.TestCase):
    def test_each_read_of_report_sections_filters_the_needs_type(self):
        for rel in FILES:
            with self.subTest(file=rel):
                text = (SRC / rel).read_text(encoding="utf-8")
                reads = [ln for ln in text.splitlines() if "report_sections" in ln and not ln.lstrip().startswith("//")]
                self.assertTrue(reads, "the file reads report_sections")
                for ln in reads:
                    self.assertRegex(ln, re.compile(r"""["']needs["']"""), "this read leaves the Needs type out: " + ln.strip())


if __name__ == "__main__":
    unittest.main()
