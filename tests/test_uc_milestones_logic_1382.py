"""Row 1107, the mutation hunt on PR 1382: the page's two rules for direct use case to milestone links (logic/ucRow.js), without a browser.
Run: python3 dev/run_tests.py test_uc_milestones_logic_1382
Quick tier: the module is bundled by the pinned esbuild and run in node (skipped when node is not on the machine).
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

ENTRY = ROOT / "tests" / "fixtures" / "uc_row_node.js"
PAGE_SRC = SRC / "clark" / "page" / "src"
_BUNDLE = {}

DATA = {
    "milestones": [{"id": "M1", "name": "Kick off"}, {"id": "M2", "name": "Go live"}, {"id": "M3", "name": "Old", "archived": 1}, {"id": "M4", "name": "Wrap"}],
    "use_cases": [{"id": "U1", "ref": "UC1", "title": "Invoices"}, {"id": "U2", "title": "Payments"}, {"id": "U3", "ref": "UC3", "title": "Gone", "archived": 1}],
    "uc_milestones": [{"use_case": "U1", "milestone": "M1"}, {"use_case": "U1", "milestone": "M3"}, {"use_case": "U2", "milestone": "M1"},
                      {"use_case": "U3", "milestone": "M1"}, {"use_case": "U2", "milestone": "M4"}],
}


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
        script.write_text(_BUNDLE["code"] + ";\nconsole.log(JSON.stringify(" + probe + "));", encoding="utf-8")
        done = subprocess.run([node, str(script)], capture_output=True, text=True)
        assert done.returncode == 0, done.stderr
        return json.loads(done.stdout)


class Rules(unittest.TestCase):
    def test_a_use_case_can_be_linked_to_the_live_milestones_it_has_no_direct_link_to_in_the_project_order(self):
        self.assertEqual(run(f"UC.linkableMilestones({json.dumps(DATA)}, 'U1')"), [{"id": "M2", "name": "Go live"}, {"id": "M4", "name": "Wrap"}])
        self.assertEqual(run(f"UC.linkableMilestones({json.dumps(DATA)}, 'U2')"), [{"id": "M2", "name": "Go live"}])
        self.assertEqual(run(f"UC.linkableMilestones({json.dumps(DATA)}, 'U9')"), [{"id": "M1", "name": "Kick off"}, {"id": "M2", "name": "Go live"}, {"id": "M4", "name": "Wrap"}])
        self.assertEqual(run("UC.linkableMilestones(null, 'U1')"), [])
        self.assertEqual(run("UC.linkableMilestones({}, 'U1')"), [])

    def test_a_milestone_lists_the_live_use_cases_linked_straight_to_it_in_the_project_order(self):
        self.assertEqual(run(f"UC.usecasesOfMilestone({json.dumps(DATA)}, 'M1')"), [{"id": "U1", "ref": "UC1", "title": "Invoices"}, {"id": "U2", "title": "Payments"}])
        self.assertEqual(run(f"UC.usecasesOfMilestone({json.dumps(DATA)}, 'M4')"), [{"id": "U2", "title": "Payments"}])
        self.assertEqual(run(f"UC.usecasesOfMilestone({json.dumps(DATA)}, 'M2')"), [])
        self.assertEqual(run("UC.usecasesOfMilestone(null, 'M1')"), [])


if __name__ == "__main__":
    unittest.main()
