"""Bifrost 2.0 P7-03: scan.yml triggers on pull_request (no filter) and push to main only, one job Scan with one concurrency group per PR; Scan is advisory (not a Mergify condition). Not literally one run per PR: one per push.

Run: python3 dev/run_tests.py test_scan_once_p7_03
Files are read as text (PyYAML is not installed on the CI runners).
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def text(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def code(rel):
    return [ln.rstrip() for ln in text(rel).splitlines() if ln.strip() and not ln.lstrip().startswith("#")]


class ScanOnceAndAdvisory(unittest.TestCase):
    def test_scan_runs_on_the_draft_pull_request_event_with_no_branch_filter(self):
        lines = code(".github/workflows/scan.yml")
        i = lines.index("on:")
        block = []
        for ln in lines[i + 1:]:
            if not ln.startswith(" "):
                break
            block.append(ln)
        self.assertIn("  pull_request:", block)
        pr = block.index("  pull_request:")
        self.assertFalse(len(block) > pr + 1 and block[pr + 1].startswith("    "),
                         "pull_request has no branches/types filter: the draft on mergify/merge-queue/* is scanned")

    def test_a_push_scans_main_only_so_the_queue_branch_is_scanned_once_not_twice(self):
        lines = code(".github/workflows/scan.yml")
        i = lines.index("  push:")
        self.assertEqual(lines[i + 1].strip(), "branches: [main]")

    def test_one_scan_job_named_scan_with_one_concurrency_group_per_pull_request(self):
        t = text(".github/workflows/scan.yml")
        self.assertEqual(len(re.findall(r"^    name: Scan$", t, re.M)), 1)
        self.assertIn("group: scan-${{ github.event.pull_request.number || github.sha }}", t)

    def test_scan_is_advisory_in_the_queue_not_a_queue_or_merge_condition(self):
        for ln in text(".mergify.yml").splitlines():
            if ln.lstrip().startswith("#"):
                continue
            self.assertNotRegex(ln, r"check-(success|neutral|skipped)\s*=\s*Scan\b", "Scan is not a queue condition")

    def test_tests_workflow_does_not_run_the_scan_a_second_time(self):
        self.assertNotRegex("\n".join(code(".github/workflows/tests.yml")), r"ci_scan|workflows/scan\.yml")


if __name__ == "__main__":
    unittest.main()
