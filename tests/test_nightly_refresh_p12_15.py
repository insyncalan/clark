"""P12-15: the nightly refreshes dev/tools/shard_times.txt AND commits it, in a concurrency group of its own that is never cancelled.

Reads .github/workflows/tests.yml as text (standard library only, as tests/test_workflow.py does). The commit step is run with a stub
git and gh on the PATH: no real network, no real repository change.

Run: python3 dev/run_tests.py test_nightly_refresh_p12_15   (quick tier)
"""
import os
import re
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

from _paths import ROOT

TEXT = (ROOT / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8")


def job(name):
    """The text of one job of tests.yml (from '  name:' to the next two-space key)."""
    m = re.search(r"^  %s:\n(.*?)(?=^  [\w-]+:\n|\Z)" % re.escape(name), TEXT, re.S | re.M)
    assert m, "no job %s" % name
    return m.group(1)


def steps(block):
    """[(name, text)] of the steps of a job block."""
    body = block.split("    steps:\n", 1)[1]
    parts = re.split(r"^      - ", body, flags=re.M)[1:]
    return [(re.match(r"name: (.*)", p).group(1) if p.startswith("name:") else "", p) for p in parts]


def run_script(step):
    m = re.search(r"^        run: \|\n((?:          .*\n|\n)+)", step, re.M)
    if m:
        return "\n".join(ln[10:] for ln in m.group(1).splitlines())
    m = re.search(r"^        run: (.+)$", step, re.M)
    return m.group(1) if m else ""


class NightlyConcurrencyTest(unittest.TestCase):
    """Pins existing behaviour (GREEN on the base by design): row 6a, ticked."""

    def test_the_nightly_has_a_group_of_its_own_and_is_never_cancelled(self):
        group = re.search(r"^  group: (.*)$", TEXT, re.M).group(1)
        cancel = re.search(r"^  cancel-in-progress: (.*)$", TEXT, re.M).group(1)
        self.assertIn("github.event_name == 'schedule' && format('nightly-{0}', github.run_id)", group)
        self.assertIn("github.event_name == 'pull_request'", cancel)
        self.assertNotIn("schedule", cancel)      # the nightly never appears in the cancel condition


class NightlyRefreshCommitTest(unittest.TestCase):
    """The fix: the shard-times job commits the refreshed file (RED on the base: it only uploads an artifact)."""

    def setUp(self):
        self.block = job("shard-times")
        self.steps = steps(self.block)

    def _index(self, pred):
        for i, (_, s) in enumerate(self.steps):
            if pred(run_script(s)):
                return i
        return None

    def test_a_step_runs_the_refresh_and_a_later_step_commits_shard_times_txt(self):
        refresh = self._index(lambda r: "dev/tools/shard_refresh.py" in r)
        commit = self._index(lambda r: "git commit" in r and "shard_times.txt" in r)
        self.assertIsNotNone(refresh, "no step runs dev/tools/shard_refresh.py")
        self.assertIsNotNone(commit, "no step in the shard-times job commits dev/tools/shard_times.txt")
        self.assertGreater(commit, refresh)

    def test_the_job_may_write_contents_and_the_commit_step_runs_with_stub_git_and_gh(self):
        self.assertRegex(self.block, r"permissions:\n\s+contents: write")      # the job, not the whole workflow
        commit = self._index(lambda r: "git commit" in r and "shard_times.txt" in r)
        self.assertIsNotNone(commit, "no step in the shard-times job commits dev/tools/shard_times.txt")
        script = run_script(self.steps[commit][1])
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            log = d / "calls.log"
            (d / "bin").mkdir()
            for tool in ("git", "gh"):
                p = d / "bin" / tool
                p.write_text('#!/bin/sh\necho "%s $*" >> "%s"\nexit 0\n' % (tool, log), encoding="utf-8")
                p.chmod(p.stat().st_mode | stat.S_IEXEC)
            env = dict(os.environ, PATH="%s:%s" % (d / "bin", os.environ["PATH"]), GITHUB_TOKEN="stub", GH_TOKEN="stub",
                       GITHUB_REPOSITORY="o/r", GITHUB_RUN_ID="1")
            out = subprocess.run(["bash", "-e", "-c", script], cwd=str(d), env=env, capture_output=True, text=True, timeout=60)
            self.assertEqual(out.returncode, 0, out.stderr)
            calls = log.read_text(encoding="utf-8").splitlines() if log.exists() else []
        self.assertTrue(any(c.startswith("git commit") for c in calls), calls)
        self.assertTrue(any("shard_times.txt" in c for c in calls if c.startswith("git add")), calls)
        self.assertTrue(any(c.startswith(("git push", "gh pr")) for c in calls), calls)      # it leaves the runner: pushed or handed to gh


if __name__ == "__main__":
    unittest.main()
