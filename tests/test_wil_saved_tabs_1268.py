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

    def test_foot_words_say_scroll_only_when_more_rows_than_most_rows(self):      # row 1268: killer for total > max vs total >= max
        self.assertEqual(run('WL.footWords(3, 2)'), "Showing 2 of 3, scroll for the rest")
        self.assertEqual(run('WL.footWords(2, 2)'), "Showing 2 of 2")
        self.assertEqual(run('WL.footWords(1, 2)'), "Showing 1 of 1")
        self.assertEqual(run('WL.reviewWords(7)'), "Review all 7 items")

    def test_foot_words_every_branch_for_cards_and_classic(self):      # row 1195: Cards keeps main's words in every state; Classic: ruling NEW-WORDS 04:2x
        cases = [
            # (total, max, all, classic, words)
            (25, 10, False, False, "Showing 10 of 25, scroll for the rest"),      # Cards cut
            (25, 10, True, False, "Showing 10 of 25, scroll for the rest"),      # Cards after Show all: unchanged
            (8, 10, False, False, "Showing 8 of 8"),      # Cards nothing cut
            (8, 10, True, False, "Showing 8 of 8"),
            (1, 10, False, False, "Showing 1 of 1"),
            (10, 10, False, False, "Showing 10 of 10"),
            (25, 10, False, True, "Showing 10 of 25, scroll for the rest"),      # Classic cut
            (25, 10, True, True, "Showing all of 25"),      # Classic after Show all
            (8, 10, False, True, "Showing all of 8"),      # Classic nothing cut
            (8, 10, True, True, "Showing all of 8"),
            (1, 10, False, True, "Showing all of 1"),
            (10, 10, False, True, "Showing all of 10"),
            (11, 10, False, True, "Showing 10 of 11, scroll for the rest"),
        ]
        for total, mx, all_, classic, words in cases:
            self.assertEqual(run(f'WL.footWords({total}, {mx}, {str(all_).lower()}, {str(classic).lower()})'), words, (total, mx, all_, classic))
        self.assertEqual(run('WL.footWords(25, 10)'), "Showing 10 of 25, scroll for the rest", "main's two-argument call")

    def test_page_state_for_review_all_maps_kinds_to_the_pages_type_and_keeps_the_choices(self):      # row 1268: killer for the kinds mapping
        def st(kinds, **kw):
            return run(f'WL.pageState({json.dumps({**EMPTY, "kinds": kinds, **kw})})')
        self.assertEqual(st([])["type"], "all")
        self.assertEqual(st(["action"])["type"], "action")
        self.assertEqual(st(["decision"])["type"], "decision")
        self.assertEqual(st(["risk"])["type"], "risk")
        self.assertEqual(st(["issue"])["type"], "risk")
        self.assertEqual(st(["risk", "issue"])["type"], "risk")
        self.assertEqual(st(["action", "risk"])["type"], "all")
        for mixed in (["decision", "action"], ["action", "decision"], ["decision", "risk"], ["issue", "action"], ["issue", "decision"]):
            self.assertEqual(st(mixed)["type"], "all", mixed)
        r = st(["action"], owner=["Pat Demo"], mode="closed")
        self.assertEqual((r["mode"], r["filters"]), ("closed", {"owner": ["Pat Demo"]}))


if __name__ == "__main__":
    unittest.main()
