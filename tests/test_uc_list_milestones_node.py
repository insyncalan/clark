"""The Use cases list and the milestone peek count a use case's milestones the way its own page does (direct links and work items), without a browser.
Run: python3 dev/run_tests.py test_uc_list_milestones_node
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

ENTRY = ROOT / "tests" / "fixtures" / "uc_list_node.js"
PAGE_SRC = SRC / "clark" / "page" / "src"
_BUNDLE = {}

DATA = {
    "milestones": [{"id": "M1", "name": "Kick off", "baseline_date": "2026-01-01"}, {"id": "M2", "name": "Go live", "baseline_date": "2026-02-01"}, {"id": "M3", "name": "Old", "archived": 1}],
    "use_cases": [{"id": "U1", "ref": "1", "title": "Invoices"}, {"id": "U2", "ref": "2", "title": "Payments"}, {"id": "U3", "ref": "3", "title": "Gone", "archived": 1}],
    "actions": [{"id": "A1", "use_case": "U2", "milestone": "M2"}, {"id": "A2", "use_case": "U3", "milestone": "M2"}],
    "raid": [], "decisions": [],
    "uc_milestones": [{"use_case": "U1", "milestone": "M1"}, {"use_case": "U1", "milestone": "M3"}, {"use_case": "U2", "milestone": "M2"}],
}


STUBS = "globalThis.addEventListener = () => {}; globalThis.window = globalThis;\n"      # UseCaseDetail.jsx pulls in the page's stores, which listen for pagehide on load


def run(probe):
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("no node")
    if "code" not in _BUNDLE:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "uc.js"
            done = esbuild.run(["--bundle", "--format=iife", "--global-name=UC", "--target=es2020", "--charset=utf8", "--tsconfig-raw={}",
                                *build_page.preact_flags(), f"--alias:@src={PAGE_SRC}", str(ENTRY), f"--outfile={out}"], cwd=tmp, capture_output=True, text=True)
            assert done.returncode == 0, done.stderr
            _BUNDLE["code"] = out.read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "probe.js"
        script.write_text(STUBS + _BUNDLE["code"] + ";\nconsole.log(JSON.stringify(" + probe + "));", encoding="utf-8")
        done = subprocess.run([node, str(script)], capture_output=True, text=True)
        assert done.returncode == 0, done.stderr
        return json.loads(done.stdout)


class ListRows(unittest.TestCase):
    def test_a_direct_milestone_link_shows_in_the_row_the_filter_text_and_search_text(self):
        rows = run(f"UC.listOf({json.dumps(DATA)}, []).map((r) => ({{id: r.id, ms: r.ms.map((m) => m.id), text: r.text}}))")
        by = {r["id"]: r for r in rows}
        self.assertEqual(by["U1"]["ms"], ["M1"], "the archived milestone is left out")
        self.assertIn("kick off", by["U1"]["text"])
        self.assertEqual(by["U2"]["ms"], ["M2"], "reached both ways, counted once")


class Peek(unittest.TestCase):
    def test_a_milestone_lists_use_cases_reaching_it_through_work_items_too(self):
        got = run(f"UC.usecasesOfMilestone({json.dumps(DATA)}, 'M2')")
        self.assertEqual([u["id"] for u in got], ["U2"], "linked both ways once; the archived use case is left out")
        d = dict(DATA, uc_milestones=[])
        self.assertEqual([u["id"] for u in run(f"UC.usecasesOfMilestone({json.dumps(d)}, 'M2')")], ["U2"], "through a work item only")


class Card(unittest.TestCase):
    def test_a_decision_linked_milestone_is_reached_through_work_items(self):
        d = dict(DATA, actions=[], uc_milestones=[], decisions=[{"id": "D1", "use_case": "U1", "milestone": "M2"}])
        got = run(f"UC.milestonesOf({json.dumps(d)}, 'U1')")
        self.assertEqual([(k["m"]["id"], k["direct"], k["via"]) for k in got], [("M2", False, True)], "a decision counts like an action, risk or issue")


if __name__ == "__main__":
    unittest.main()
