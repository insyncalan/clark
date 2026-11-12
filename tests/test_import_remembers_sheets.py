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


class TheWindowKeepsThem(unittest.TestCase):
    def test_the_import_page_asks_for_and_saves_the_ticks(self):
        src = EDIT.read_text(encoding="utf-8")
        self.assertIn("L.startSheets(sheets, recalled())", src)
        self.assertIn("remember(tables);", src)
        self.assertIn("localStorage.setItem(L.SHEETS_KEY", src)


if __name__ == "__main__":
    unittest.main()
