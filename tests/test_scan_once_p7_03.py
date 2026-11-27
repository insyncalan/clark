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

class ScanTriggerPins(unittest.TestCase):
    """P7-03 survivors: the exact trigger set, the concurrency pair, and no second Scan start from tests.yml."""

    def _on_keys(self):
        lines = code(".github/workflows/scan.yml")
        i = lines.index("on:")
        keys = []
        for ln in lines[i + 1:]:
            if not ln.startswith(" "):
                break
            if re.match(r"^  [A-Za-z_]+:", ln):
                keys.append(ln.strip().rstrip(":").split(":")[0])
        return keys

    @staticmethod
    def _event_block(lines, key):
        """Indented lines under '  <key>:' in the on: block, up to the next key at the same indent."""
        i = lines.index("  %s:" % key)
        block = []
        for ln in lines[i + 1:]:
            if len(ln) - len(ln.lstrip(" ")) <= 2:
                break
            block.append(ln)
        return block

    def test_push_block_is_exactly_branches_main_so_no_paths_and_no_paths_ignore_skip_a_commit_on_main(self):
        lines = code(".github/workflows/scan.yml")  # a missing file raises: error, not skip
        self.assertEqual(self._event_block(lines, "push"), ["    branches: [main]"])

    def test_pull_request_block_has_no_keys_at_all(self):
        lines = code(".github/workflows/scan.yml")
        self.assertEqual(self._event_block(lines, "pull_request"), [])

    def test_trigger_set_is_exactly_pull_request_and_push_so_no_merge_group_and_no_manual_run(self):
        self.assertEqual(self._on_keys(), ["pull_request", "push"])

    def test_no_merge_group_and_no_workflow_dispatch_anywhere_in_scan_yml(self):
        t = "\n".join(code(".github/workflows/scan.yml"))
        self.assertNotIn("merge_group", t)
        self.assertNotIn("workflow_dispatch", t)

    def test_concurrency_group_is_per_pull_request_and_per_commit_on_push(self):
        t = "\n".join(code(".github/workflows/scan.yml"))
        self.assertEqual(re.findall(r"^\s+group: (.*)$", t, re.M),
                         ["scan-${{ github.event.pull_request.number || github.sha }}"])

    def test_cancel_in_progress_only_for_a_pull_request_never_for_a_push_to_main(self):
        t = "\n".join(code(".github/workflows/scan.yml"))
        self.assertEqual(re.findall(r"^\s+cancel-in-progress: (.*)$", t, re.M),
                         ["${{ github.event_name == 'pull_request' }}"])

    def test_tests_workflow_never_starts_scan_by_gh_workflow_run(self):
        t = "\n".join(code(".github/workflows/tests.yml"))
        self.assertNotRegex(t, r"gh\s+workflow\s+run\s+[\"']?(Scan|scan)")


if __name__ == "__main__":
    unittest.main()
