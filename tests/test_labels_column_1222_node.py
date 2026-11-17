"""Item 1195 slice S6 (row 1222): the Work items table can show a Labels column, chosen from the column menu. Pure functions.

Run: python3 dev/run_tests.py test_labels_column_1222_node
Quick tier: no browser. Bundled by the pinned esbuild and run in node (skipped when node is not on the machine).
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

ENTRY = ROOT / "tests" / "fixtures" / "labelscolumn_node.js"
PAGE_SRC = SRC / "clark" / "page" / "src"
_BUNDLE = {}

DATA = ("{actions:[{id:'A-1',description:'a',status:'Open'},{id:'A-2',description:'b',status:'Open'}],"
        "raid:[{id:'R-1',type:'Risk',description:'c',status:'Open'}],"
        "decisions:[{id:'D-1',decision:'d',status:'Pending'}],"
        "labels:{'A-1':['Sensitive','Board'],'R-1':['Board'],'D-1':['Legal']}}")


def bundle():
    if "code" not in _BUNDLE:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "lc.js"
            done = esbuild.run(["--bundle", "--format=iife", "--global-name=LC", "--target=es2020", "--charset=utf8", "--tsconfig-raw={}",
                                *build_page.preact_flags(), f"--alias:@src={PAGE_SRC}", str(ENTRY), f"--outfile={out}"],
                               cwd=tmp, capture_output=True, text=True)
            assert done.returncode == 0, done.stderr
            _BUNDLE["code"] = out.read_text(encoding="utf-8")
    return _BUNDLE["code"]


def run_node(probe):
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("no node")
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "probe.js"
        script.write_text(bundle() + ";\nconst W = LC;\nconst data = " + DATA + ";\nconsole.log(JSON.stringify(" + probe + "));", encoding="utf-8")
        done = subprocess.run([node, str(script)], capture_output=True, text=True)
        assert done.returncode == 0, done.stderr
        return json.loads(done.stdout)


class LabelsColumn(unittest.TestCase):
    def test_every_row_carries_its_labels_from_the_data(self):
        self.assertEqual(run_node("W.rowsOf(data).map((r) => [r.id, r.labels])"),
                         [["A-1", ["Sensitive", "Board"]], ["A-2", []], ["R-1", ["Board"]], ["D-1", ["Legal"]]])

    def test_a_file_without_labels_gives_every_row_none(self):
        self.assertEqual(run_node("W.rowsOf({actions:[{id:'A-1',description:'a'}]}).map((r) => r.labels)"), [[]])

    def test_a_name_that_is_not_text_or_is_empty_is_left_out_and_a_non_list_gives_none(self):
        self.assertEqual(run_node("W.rowsOf({actions:[{id:'A-1',description:'a'},{id:'A-2',description:'b'}],labels:{'A-1':['X',null,'',3,'Y'],'A-2':'Z'}}).map((r) => r.labels)"),
                         [["X", "Y"], []])

    def test_the_cell_text_is_the_names_joined_and_empty_for_none(self):
        self.assertEqual(run_node("[W.labelsText({labels:['Sensitive','Board']}), W.labelsText({labels:[]}), W.labelsText({}), W.labelsText(null)]"), ["Sensitive, Board", "", "", ""])

    def test_the_work_menu_offers_labels_after_use_case_and_it_is_not_standard_or_locked(self):
        self.assertEqual(run_node("W.TABLE_COLUMNS.work.map((c) => c.id)"),
                         ["status", "item", "owner", "due", "prio", "id", "type", "workstream", "milestone", "raised", "closed", "usecase", "labels", "latest", "wording"])
        self.assertEqual(run_node("W.TABLE_COLUMNS.work.find((c) => c.id === 'labels')"), {"id": "labels", "label": "Labels"})

    def test_ticking_labels_shows_it_and_the_standard_set_is_unchanged(self):
        self.assertIn("labels", run_node("W.toggled('work', W.shownIds('work', null), 'labels')"))
        self.assertNotIn("labels", run_node("W.standardIds('work')"))

    def test_the_milestone_tables_do_not_get_it(self):
        self.assertEqual(run_node("['milestones','msDash'].map((t) => W.TABLE_COLUMNS[t].some((c) => c.id === 'labels'))"), [False, False])


if __name__ == "__main__":
    unittest.main()
