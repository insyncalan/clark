"""#1195 S5: the half-circle icon before the status word on the live Work items page, coloured as the status pill.

Run: python3 dev/run_tests.py test_status_mark_1195
Quick tier: no browser. statusMark(row, pill) in workItems.js, bundled and run in node (skipped when node is not on the machine).
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

ENTRY = ROOT / "tests" / "fixtures" / "statusmark_node.js"
PAGE_SRC = SRC / "clark" / "page" / "src"
_BUNDLE = {}
TODAY = "2026-11-17"


def bundle():
    if "code" not in _BUNDLE:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "sm.js"
            done = esbuild.run(["--bundle", "--format=iife", "--global-name=SM", "--target=es2020", "--charset=utf8", "--tsconfig-raw={}",
                                *build_page.preact_flags(), f"--alias:@src={PAGE_SRC}", str(ENTRY), f"--outfile={out}"],
                               cwd=tmp, capture_output=True, text=True)
            assert done.returncode == 0, done.stderr
            _BUNDLE["code"] = out.read_text(encoding="utf-8")
    return _BUNDLE["code"]


def mark(row):
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("no node")
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "probe.js"
        script.write_text(bundle() + ";\nconst row = %s; console.log(JSON.stringify(SM.statusMark(row, SM.clientPill(row, %s))));" % (json.dumps(row), json.dumps(TODAY)),
                          encoding="utf-8")
        done = subprocess.run([node, str(script)], capture_output=True, text=True)
        assert done.returncode == 0, done.stderr
        return json.loads(done.stdout)


def action(status, due):
    return {"kind": "action", "status": status, "due_date": due, "priority": "Medium"}


class StatusMark(unittest.TestCase):
    def test_open_action_past_its_date_is_red(self):
        self.assertEqual(mark(action("Open", "2026-11-10")), {"word": "Overdue", "tone": "r"})

    def test_due_within_seven_days_is_amber(self):
        self.assertEqual(mark(action("Open", "2026-11-24"))["tone"], "a")
        self.assertEqual(mark(action("Open", "2026-11-17")), {"word": "Due soon", "tone": "a"})

    def test_eight_days_out_is_blue(self):
        self.assertEqual(mark(action("Open", "2026-11-25")), {"word": "On track", "tone": "b"})

    def test_delayed_is_amber(self):
        self.assertEqual(mark(action("Delayed", "2026-12-30")), {"word": "Delayed", "tone": "a"})

    def test_completed_is_green_and_reads_completed_even_past_its_date(self):
        self.assertEqual(mark(action("Completed", "2026-11-01")), {"word": "Completed", "tone": "g"})
        self.assertEqual(mark(action("Completed", "2026-12-30")), {"word": "Completed", "tone": "g"})

    def test_made_decision_is_green_pending_is_blue(self):
        self.assertEqual(mark({"kind": "decision", "status": "Made"}), {"word": "Made", "tone": "g"})
        self.assertEqual(mark({"kind": "decision", "status": "Pending"})["tone"], "b")

    def test_closed_cancelled_withdrawn_are_grey(self):
        self.assertEqual(mark(action("Closed", "2026-11-01")), {"word": "Closed", "tone": "n"})
        self.assertEqual(mark(action("Cancelled", "2026-11-01")), {"word": "Cancelled", "tone": "n"})
        self.assertEqual(mark({"kind": "decision", "status": "Withdrawn"}), {"word": "Withdrawn", "tone": "n"})

    def test_other_open_status_follows_the_pill(self):
        self.assertEqual(mark(action("Blocked", "2026-12-30")), {"word": "Blocked", "tone": "a"})   # the pill reads Blocked amber
        self.assertEqual(mark(action("In progress", "2026-12-30"))["tone"], "b")

    def test_risk_keeps_red_and_amber_else_blue(self):
        r = {"kind": "risk", "status": "Open", "priority": "High"}
        self.assertEqual(mark(r)["tone"], "r")
        self.assertEqual(mark(dict(r, priority="Low"))["tone"], "b")


if __name__ == "__main__":
    unittest.main()
