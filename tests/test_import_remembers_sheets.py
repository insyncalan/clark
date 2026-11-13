"""#1106: the "What to import" window opens with the sheets ticked last time (logic/dataCard.js startSheets; ImportWorkbook.jsx keeps them).

Run: python3 dev/run_tests.py test_import_remembers_sheets
Quick tier: no browser. The module is bundled by the pinned esbuild and run in node (skipped when node is not on the machine).
"""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _paths import ROOT, SRC, TOOLS

sys.path.insert(0, str(TOOLS))
import build_page  # noqa: E402
import esbuild  # noqa: E402

ENTRY = ROOT / "tests" / "fixtures" / "datacard_node.js"
PAGE_SRC = SRC / "clark" / "page" / "src"
EDIT = PAGE_SRC / "edit" / "ImportWorkbook.jsx"
_BUNDLE = {}


def bundle():
    if "code" not in _BUNDLE:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "dc.js"
            done = esbuild.run(["--bundle", "--format=iife", "--global-name=Q", "--target=es2020", "--charset=utf8", "--tsconfig-raw={}",
                                *build_page.preact_flags(), f"--alias:@src={PAGE_SRC}", str(ENTRY), f"--outfile={out}"],
                               cwd=tmp, capture_output=True, text=True)
            assert done.returncode == 0, done.stderr
            _BUNDLE["code"] = out.read_text(encoding="utf-8")
    return _BUNDLE["code"]


def start(sheets, saved):
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("no node")
    probe = f"Q.startSheets({json.dumps([{'table': t} for t in sheets])}, {json.dumps(saved)})"
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "probe.js"
        script.write_text(bundle() + ";\nconsole.log(JSON.stringify(" + probe + "));", encoding="utf-8")
        done = subprocess.run([node, str(script)], capture_output=True, text=True)
        assert done.returncode == 0, done.stderr
        return json.loads(done.stdout)


FIVE = ["actions", "raid", "decisions", "milestones", "use_cases"]


class StartSheets(unittest.TestCase):
    def test_only_the_sheets_ticked_last_time_are_ticked(self):
        self.assertEqual(start(FIVE, ["actions"]), {"actions": True, "raid": False, "decisions": False, "milestones": False, "use_cases": False})

    def test_nothing_remembered_ticks_every_sheet(self):
        for saved in (None, [], "x", {"actions": True}):
            self.assertEqual(start(FIVE, saved), {t: True for t in FIVE}, saved)

    def test_a_remembered_sheet_the_workbook_lacks_is_not_ticked_or_listed(self):
        self.assertEqual(start(["actions", "milestones"], ["milestones", "decisions"]), {"actions": False, "milestones": True})

    def test_when_none_of_the_remembered_sheets_are_in_the_workbook_every_sheet_is_ticked(self):
        self.assertEqual(start(["raid", "milestones"], ["actions"]), {"raid": True, "milestones": True})


def probe(js):
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("no node")
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "probe.js"
        script.write_text(bundle() + ";\nconsole.log(JSON.stringify((() => { " + js + " })()));", encoding="utf-8")
        done = subprocess.run([node, str(script)], capture_output=True, text=True)
        assert done.returncode == 0, done.stderr
        return json.loads(done.stdout)


STUB = "const mk = (init, fail) => { const m = {...init}; return { getItem: (k) => { if (fail === 'get') throw new Error('blocked'); return k in m ? m[k] : null; }, setItem: (k, v) => { if (fail === 'set') throw new Error('quota'); m[k] = v; }, m }; };"


class RememberAndRecall(unittest.TestCase):
    def test_what_is_remembered_comes_back(self):
        self.assertEqual(probe(STUB + "const s = mk({}); Q.rememberSheets(['raid'], s); return [Q.recalledSheets(s), s.m[Q.SHEETS_KEY]]"), [["raid"], '["raid"]'])

    def test_nothing_stored_corrupt_or_blocked_recalls_nothing_and_never_throws(self):
        self.assertEqual(probe(STUB + "return [Q.recalledSheets(mk({})), Q.recalledSheets(mk({[Q.SHEETS_KEY]: '{not json'})), Q.recalledSheets(mk({}, 'get')), Q.recalledSheets(undefined)]"), [None, None, None, None])

    def test_a_full_or_blocked_store_is_ignored_when_remembering(self):
        self.assertEqual(probe(STUB + "const s = mk({}, 'set'); Q.rememberSheets(['raid'], s); Q.rememberSheets(['raid'], undefined); return Object.keys(s.m)"), [])

    def test_a_corrupt_choice_ticks_every_sheet(self):
        self.assertEqual(probe(STUB + "return Q.startSheets([{table: 'actions'}, {table: 'raid'}], Q.recalledSheets(mk({[Q.SHEETS_KEY]: '{not json'})))"), {"actions": True, "raid": True})


class TheWindowKeepsThem(unittest.TestCase):
    def test_the_import_page_asks_for_the_ticks_and_saves_them_only_after_a_check_that_went_through(self):
        src = EDIT.read_text(encoding="utf-8")
        self.assertIn("L.startSheets(sheets, L.recalledSheets())", src)
        read = src[src.index("async function read_("):]
        read = read[:read.index("// Get the template")]
        self.assertLess(read.index("await api.check("), read.index("if (!r.ok)"))
        self.assertLess(read.index("if (!r.ok)"), read.index("L.rememberSheets(tables)"), "a failed check keeps the old choice")
        self.assertIn('"use_cases"], false)', src, "the none-of-the-five fallback keeps nothing")
        self.assertIn("if (keep) L.rememberSheets(tables)", read)


class SheetLine(unittest.TestCase):
    def test_the_gantt_sheet_is_counted_when_it_has_items(self):
        r = probe("return [Q.sheetLine({items: [{table: 'gantt_lines', kind: 'new'}, {table: 'gantt_lines', kind: 'new'}, {table: 'gantt_lines', kind: 'changed'}]}), Q.sheetLine({items: []})]")
        self.assertTrue(r[0].endswith(" · Gantt: 2 new, 1 updated"), r[0])
        self.assertNotIn("Gantt", r[1])


if __name__ == "__main__":
    unittest.main()
