"""Bifrost 2.0 plan P7-03: Mergify's combined run is the full Ubuntu suite once; the scan runs on that draft pull request but is NOT a queue condition; no macOS on it.

Run: python3 dev/run_tests.py test_p7_03_scan_advisory
The files are read as text (PyYAML is not installed on the CI runners).
LIMIT: this pins the files, not a live queue run. The live run is recorded in the plan's done list (draft #2510: Scan failed, the pull request still merged).
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCAN_NAME = "Scan"
ALLOWED_MAC_LINES = [
    'workflow_dispatch) FULL=1; if [ "$MACOS_INPUT" = "true" ]; then MACOS=1; fi ;;',
    'schedule) FULL=1; MACOS=1; ADVISORY=1 ;;',
    'cut-v*) FULL=1; SMOKE=1; CUT=1 ;;',
    '*,full-ci,*) FULL=1; SMOKE=1 ;;',
    'if [ -n "$REL" ]; then SMOKE=1; fi',
    'if [ "$(printf \'%s\\n\' "$CHANGED" | wc -l)" -ge 3000 ]; then FULL=1; SMOKE=1; fi',
    'src/clark/updates.py|src/clark/platform.py) FULL=1; SMOKE=1 ;;',
    'clark.command|clark/__main__.py|clark/launch.py|clark/doctor.py|src/clark/launch.py|src/clark/doctor.py|src/clark/release_files.py|dev/tools/package.py) FULL=1; SMOKE=1 ;;',
]


def text(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def code(rel):
    return [ln for ln in text(rel).splitlines() if ln.strip() and not ln.lstrip().startswith("#")]


class ScanIsAdvisoryOnTheMergifyDraft(unittest.TestCase):
    def test_the_scan_workflow_runs_on_a_pull_request_so_it_runs_on_the_mergify_draft(self):
        lines = code(".github/workflows/scan.yml")
        i = lines.index("on:")
        block = []
        for ln in lines[i + 1:]:
            if not ln.startswith("  "):
                break
            block.append(ln.strip())
        self.assertIn("pull_request:", block)
        self.assertIn("name: Scan", lines, "the check is called Scan")

    def test_the_scan_job_is_gated_by_the_public_scan_variable(self):
        self.assertIn("    if: vars.CLARK_PUBLIC_SCAN == 'true'", code(".github/workflows/scan.yml"))

    def test_no_queue_or_merge_condition_names_the_scan(self):
        conds = [ln.strip() for ln in code(".mergify.yml") if ln.strip().startswith("- ")]
        self.assertTrue(conds, "the config has conditions")
        for c in conds:
            self.assertNotRegex(c, r"(?i)\bscan\b", "a condition names the scan: " + c)
        checks = [c for c in conds if c.startswith("- check-success")]
        self.assertEqual(len(checks), 8, "4 queue_conditions + 4 merge_conditions, none is the scan")

    def test_the_mergify_draft_branch_sets_only_full_and_never_a_mac_run(self):
        hits = [ln for ln in code(".github/workflows/tests.yml") if "mergify/merge-queue/" in ln]
        self.assertEqual(len(hits), 1, "one plan line decides the Mergify branch")
        line = hits[0].strip()
        self.assertEqual(line, 'if [ "${BRANCH#mergify/merge-queue/}" != "$BRANCH" ]; then FULL=1; fi')
        for var in ("MACOS", "SMOKE", "ADVISORY", "CUT"):
            self.assertNotIn(var + "=", line)

    def test_no_other_plan_line_near_the_mergify_branch_starts_a_mac_run(self):
        """The exact set of code lines that assign MACOS=1 or SMOKE=1 (comment tail cut): a Mac set started for the Mergify draft by ANOTHER line, one-line or a multi-line case arm,
        is a new line and is caught. A new legitimate Mac rule changes this list on purpose. None of the lines names mergify."""
        got = [re.sub(r"\s+#.*$", "", ln.strip()) for ln in code(".github/workflows/tests.yml") if re.search(r"\b(MACOS|SMOKE)=1", ln)]
        self.assertEqual(got, ALLOWED_MAC_LINES)
        for ln in got:
            self.assertNotIn("mergify", ln.lower())

    def test_the_mac_jobs_still_start_only_from_the_plan_outputs(self):
        lines = [ln.strip() for ln in code(".github/workflows/tests.yml")]
        self.assertIn("if: ${{ needs.plan.outputs.macos == '1' }}", lines)
        self.assertIn("if: ${{ needs.plan.outputs.smoke == '1' }}", lines)
        self.assertEqual(len([ln for ln in lines if ln.startswith("if:") and ("macos" in ln or "smoke" in ln)]), 2, "no other if: starts a Mac job")


if __name__ == "__main__":
    unittest.main()
