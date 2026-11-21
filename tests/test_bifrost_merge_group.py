"""Bifrost step 9: the three bifrost checks report on merge_group (the merge queue).

Run: python3 dev/run_tests.py test_bifrost_merge_group   (quick tier, standard library only)

A merge_group event has no pull request number. ci_run.py must then print NOT CHECKED and return 0 for each check, and a
real pull request number must go the old way. bifrost-checks.yml must list merge_group, keep ${{ }} out of every run:
body (values come in through env), and keep contents: read and pull-requests: read as the only permissions.
"""
import contextlib
import importlib.util
import io
import os
import re
import sys
import tempfile
import unittest
from unittest import mock

from _paths import ROOT

CI_RUN = ROOT / ".github" / "bifrost" / "ci_run.py"
WORKFLOW = ROOT / ".github" / "workflows" / "bifrost-checks.yml"
CHECKS = ("closes-guard", "point-map", "test-exists")


def load():
    sys.path.insert(0, str(CI_RUN.parent))
    try:
        spec = importlib.util.spec_from_file_location("ci_run_under_test", CI_RUN)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    finally:
        sys.path.remove(str(CI_RUN.parent))
    return mod


def run_main(mod, argv, env=None):
    out = io.StringIO()
    with mock.patch.dict(os.environ, env or {}), contextlib.redirect_stdout(out):
        rc = mod.main(argv)
    return rc, out.getvalue()


class NoPrPath(unittest.TestCase):
    def test_no_pr_prints_not_checked_and_returns_zero(self):
        mod = load()
        for check in CHECKS:
            for argv in (["--check", check], ["--check", check, "--pr", ""]):
                with self.subTest(check=check, argv=argv):
                    with mock.patch.object(mod.P, "run_pr", side_effect=AssertionError("PR path ran")):
                        rc, out = run_main(mod, argv, {"BIFROST_ENFORCE": "1"})
                    self.assertEqual(rc, 0)
                    self.assertIn("NOT CHECKED: merge_group has no pull request", out)
                    self.assertIn(f"bifrost-{check}", out)

    def test_no_pr_writes_the_job_summary(self):
        mod = load()
        with tempfile.TemporaryDirectory() as d:
            summ = os.path.join(d, "summary.md")
            rc, _ = run_main(mod, ["--check", "point-map"], {"GITHUB_STEP_SUMMARY": summ})
            self.assertEqual(rc, 0)
            with open(summ, encoding='utf-8') as f:
                self.assertIn("NOT CHECKED: merge_group has no pull request", f.read())

    def test_pr_number_path_is_unchanged(self):
        mod = load()
        row = {"sha": "abc123", "checks": {c: {"result": "PASS", "reason": "ok"} for c in CHECKS}}
        for check in CHECKS:
            with self.subTest(check=check):
                with mock.patch.object(mod.CI, "pr", return_value={"number": 7}) as pr, \
                        mock.patch.object(mod.P, "run_pr", return_value=row) as run:
                    rc, out = run_main(mod, ["--check", check, "--pr", "7"])
                self.assertEqual(rc, 0)
                pr.assert_called_once_with(7)
                run.assert_called_once()
                self.assertIn(f"bifrost-{check}: PASS on PR #7 head abc123: ok", out)
                self.assertNotIn("merge_group", out)

    def test_pr_path_still_fails_when_enforced(self):
        mod = load()
        row = {"sha": "abc123", "checks": {c: {"result": "FAIL", "reason": "bad"} for c in CHECKS}}
        with mock.patch.object(mod.CI, "pr", return_value={}), mock.patch.object(mod.P, "run_pr", return_value=row):
            rc, _ = run_main(mod, ["--check", "point-map", "--pr", "7"], {"BIFROST_ENFORCE": "1"})
            self.assertEqual(rc, 1)
            rc, _ = run_main(mod, ["--check", "point-map", "--pr", "7"], {"BIFROST_ENFORCE": "0"})
            self.assertEqual(rc, 0)

    def test_a_non_number_pr_is_refused(self):
        mod = load()
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            mod.main(["--check", "point-map", "--pr", "7; echo x"])


class WorkflowText(unittest.TestCase):
    def setUp(self):
        self.text = WORKFLOW.read_text(encoding="utf-8")
        self.code = "\n".join(ln for ln in self.text.splitlines() if not ln.lstrip().startswith("#"))

    def test_lists_merge_group_with_checks_requested(self):
        self.assertRegex(self.code, r"(?m)^  merge_group:[^\n]*\n    types: \[checks_requested\]")

    def test_the_three_jobs_are_there(self):
        for check in CHECKS:
            self.assertRegex(self.code, rf"(?m)^  bifrost-{check}:$")

    def test_no_expression_inside_a_run_body(self):
        lines = self.code.splitlines()
        i = 0
        runs = 0
        while i < len(lines):
            m = re.match(r"^(\s*)(?:- )?run:\s*(.*)$", lines[i])
            if not m:
                i += 1
                continue
            runs += 1
            indent = len(m.group(1))
            body = [m.group(2)]
            i += 1
            while i < len(lines) and (not lines[i].strip() or len(lines[i]) - len(lines[i].lstrip()) > indent):
                body.append(lines[i])
                i += 1
            self.assertNotIn("${{", "\n".join(body))
        self.assertEqual(runs, 4)  # the three checks plus the release-label gate (Row 1501, bifrost-release-label)

    def test_pr_number_comes_in_through_env(self):
        self.assertEqual(self.code.count('--pr "$PR_NUMBER"'), 3)
        self.assertEqual(self.code.count("PR_NUMBER: ${{ github.event.pull_request.number }}"), 3)

    def test_merge_group_checkout_ref_and_concurrency(self):
        self.assertEqual(self.code.count("ref: ${{ github.event.pull_request.base.sha || github.event.merge_group.base_sha }}"), 4)  # four jobs check out the base: the three checks and the release-label gate
        self.assertIn("group: bifrost-${{ github.event.pull_request.number || github.run_id }}", self.code)

    def test_permissions_are_read_only_and_just_two(self):
        m = re.search(r"(?m)^permissions:\n((?:  .*\n)+)", self.code)
        self.assertIsNotNone(m)
        self.assertEqual([ln.strip() for ln in m.group(1).splitlines()], ["contents: read", "pull-requests: read"])
        self.assertEqual(len(re.findall(r"(?m)^\s*permissions:", self.code)), 1)
        self.assertNotIn("pull_request_target", self.code)


if __name__ == "__main__":
    unittest.main()
