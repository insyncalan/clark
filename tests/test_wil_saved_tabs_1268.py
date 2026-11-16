"""Row 1268, saved-view tabs of the Work items list: the pure rules (templates/workItemsViews.js) and the starting views.

Run: python3 dev/run_tests.py test_wil_saved_tabs_1268
Quick tier: no browser. The module is bundled by the pinned esbuild and run in node (skipped when node is not on the machine).
"""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from _paths import ROOT, SRC, TOOLS

import sys
sys.path.insert(0, str(TOOLS))
import build_page  # noqa: E402
import esbuild  # noqa: E402

ENTRY = ROOT / "tests" / "fixtures" / "wil_views_node.js"
PAGE_SRC = SRC / "clark" / "page" / "src"
_BUNDLE = {}
EMPTY = {"v": 1, "kinds": [], "mode": "open", "status": [], "due": [], "owner": [], "workstream": [], "use_case": [], "priority": [], "sort": "due",
         "max": 50, "columns": ["type", "id", "owner", "due", "status"], "caption": "",
         "milestone": [], "not": {k: [] for k in ("kinds", "status", "due", "owner", "workstream", "use_case", "priority", "milestone")}, "has": [], "no": [], "text": []}      # row 1113: the whole filter a section keeps
KNOWN = [{"id": "U-1", "names": ["Invoice matching", "UC1", "UC1 Invoice matching"]}, {"id": "U-2", "names": ["Month end"]}]


def bundle():
    if "code" not in _BUNDLE:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "wil.js"
            done = esbuild.run(["--bundle", "--format=iife", "--global-name=WL", "--target=es2020", "--charset=utf8", "--tsconfig-raw={}",
                                *build_page.preact_flags(), f"--alias:@src={PAGE_SRC}", str(ENTRY), f"--outfile={out}"],
                               cwd=tmp, capture_output=True, text=True)
            assert done.returncode == 0, done.stderr
            _BUNDLE["code"] = out.read_text(encoding="utf-8")
    return _BUNDLE["code"]


def run(probe):
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("no node")
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "probe.js"
        script.write_text(bundle() + ";\nconsole.log(JSON.stringify(" + probe + "));", encoding="utf-8")
        done = subprocess.run([node, str(script)], capture_output=True, text=True)
        assert done.returncode == 0, done.stderr
        return json.loads(done.stdout)



VIEWS = [{"id": "all", "name": "All work items", "line": ""}, {"id": "actions", "name": "Actions", "line": "type:action"},
         {"id": "overdue", "name": "Overdue", "line": "due:overdue"}]


class Tabs(unittest.TestCase):
    def test_starting_views_are_the_mockups_five_in_order_and_each_reads_back_as_the_old_view_filter(self):
        got = run('WL.PAGE_VIEWS.workitemslist')
        self.assertEqual([v["name"] for v in got], ["All work items", "Actions", "Risks and issues", "Decisions", "Overdue"])
        for v in got:
            r = run(f'WL.applyView({json.dumps(v)}, {json.dumps(EMPTY)}, [])')
            old = run(f'WL.viewFilter({json.dumps(v["id"])})')
            for k in ("kinds", "due", "mode"):
                self.assertEqual(r["filter"][k], old[k], v["id"])

    def test_a_view_replaces_the_choices_and_keeps_most_rows_columns_and_caption(self):
        base = dict(EMPTY, kinds=["risk"], max=7, caption="Hello")
        r = run(f'WL.applyView({json.dumps(VIEWS[2])}, {json.dumps(base)}, [])')["filter"]
        self.assertEqual((r["kinds"], r["due"], r["max"], r["caption"]), ([], ["overdue"], 7, "Hello"))

    def test_the_dot_shows_only_when_the_on_tab_differs_from_the_filter(self):
        def st(filter, active=""):
            return run(f'WL.tabState({json.dumps(VIEWS)}, {json.dumps(filter)}, {json.dumps(active)})')
        same = st(dict(EMPTY, kinds=["action"]))
        self.assertEqual((same["active"]["id"], same["dot"]), ("actions", False))
        moved = st(dict(EMPTY, kinds=["action"], priority=["High"]), "actions")
        self.assertEqual((moved["active"]["id"], moved["dot"]), ("actions", True))
        none = st(dict(EMPTY, owner=["Pat Demo"]))
        self.assertEqual((none["active"], none["dot"]), (None, False))

    def test_a_view_the_list_cannot_read_gives_a_problem_not_a_filter(self):
        r = run(f'WL.applyView({{"id": "x", "name": "X", "line": "flavour:red"}}, {json.dumps(EMPTY)}, [])')
        self.assertIn("problem", r)
        self.assertNotIn("filter", r)


if __name__ == "__main__":
    unittest.main()
