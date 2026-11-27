"""The nightly's own commit of the refreshed shard times (dev/tools/shard_commit.py): one commit on its own branch with exactly one
file, named after the run, pushed without force. It never touches main and never writes over a branch that exists. The branch is
turned into a pull request by the pipeline's hands (a pull request opened by the workflow's own token starts no checks).
It runs inside a fixture repository with a bare remote (tests/_pr_fixture.py): no network, nothing of the real repository.

Run: python3 dev/run_tests.py test_shard_commit   (quick tier)
"""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _paths import ROOT  # noqa: F401  (puts dev/tools on the path)
from _pr_fixture import PrFixture

TOOL = ROOT / "dev" / "tools" / "shard_commit.py"
FILE = "dev/tools/shard_times.txt"
OLD = "# header\ntest_mod.py 1.0\n"
NEW = "# header\ntest_mod.py 2.5\n"


class Fixture(PrFixture):
    """The fixture repository with dev/tools/shard_times.txt and a bare remote called origin."""
    def __init__(self):
        super().__init__()
        self.remote = Path(tempfile.mkdtemp(prefix="pr-remote-"))
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(self.remote)], check=True)
        self.write(FILE, OLD)
        self.commit("the shard times")
        self.git("remote", "add", "origin", str(self.remote))
        self.git("push", "-q", "origin", "main")

    def __exit__(self, *exc):
        shutil.rmtree(self.remote, ignore_errors=True)
        return super().__exit__(*exc)

    def run_tool(self, *args):
        r = subprocess.run([sys.executable, str(TOOL), *args], cwd=self.dir, env=self.env, capture_output=True, text=True)
        return r.returncode, r.stdout + r.stderr

    def remote_branches(self):
        out = subprocess.run(["git", "-C", str(self.remote), "for-each-ref", "--format=%(refname:short) %(objectname)", "refs/heads"], capture_output=True, text=True).stdout
        return dict(line.split() for line in out.splitlines())


class CommitTest(unittest.TestCase):
    def test_a_refreshed_file_is_one_commit_of_one_file_on_a_branch_of_the_run_pushed_to_the_remote(self):
        with Fixture() as pr:
            main_before = pr.remote_branches()["main"]
            pr.write(FILE, NEW)
            code, out = pr.run_tool("--run-id", "45936741199", "--push")
            self.assertEqual(code, 0, out)
            result = json.loads(out.strip().splitlines()[-1])
            sha = pr.git("rev-parse", "HEAD")
            self.assertEqual(result, {"result": "done", "run_id": "45936741199", "branch": "shard-times-45936741199", "sha": sha, "pushed": True})
            self.assertEqual(pr.git("rev-parse", "--abbrev-ref", "HEAD"), "shard-times-45936741199")
            self.assertEqual(pr.git("diff", "--name-only", "main", "HEAD").splitlines(), [FILE])
            self.assertEqual(pr.git("rev-parse", "HEAD~1"), pr.git("rev-parse", "main"))
            self.assertEqual(pr.remote_branches(), {"main": main_before, "shard-times-45936741199": sha})
            self.assertIn("45936741199", pr.git("log", "-1", "--format=%B"))
            self.assertEqual(pr.git("log", "-1", "--format=%an <%ae>"), "github-actions[bot] <41898282+github-actions[bot]@users.noreply.github.com>")
            self.assertEqual(pr.read(FILE), NEW)

    def test_without_push_it_commits_locally_and_the_remote_stays_as_it_was(self):
        with Fixture() as pr:
            before = pr.remote_branches()
            pr.write(FILE, NEW)
            code, out = pr.run_tool("--run-id", "7")
            self.assertEqual(code, 0, out)
            self.assertEqual(json.loads(out.strip().splitlines()[-1])["pushed"], False)
            self.assertEqual(pr.remote_branches(), before)

    def test_a_file_that_did_not_change_is_noop_with_no_branch_and_nothing_pushed(self):
        with Fixture() as pr:
            before = pr.remote_branches()
            code, out = pr.run_tool("--run-id", "7", "--push")
            self.assertEqual(code, 0, out)
            self.assertEqual(json.loads(out.strip().splitlines()[-1])["result"], "noop")
            self.assertEqual(pr.git("rev-parse", "--abbrev-ref", "HEAD"), "main")
            self.assertEqual(pr.remote_branches(), before)


class RefusalTest(unittest.TestCase):
    """Each refusal is exit 2 'not checked': nothing is committed and nothing is pushed."""
    def refused(self, pr, expect, *args):
        before = pr.remote_branches()
        head = pr.git("rev-parse", "HEAD")
        code, out = pr.run_tool(*args)
        self.assertEqual(code, 2, out)
        self.assertIn("not checked", out.lower())
        self.assertIn(expect, out)
        self.assertEqual(pr.git("rev-parse", "HEAD"), head)
        self.assertEqual(pr.git("rev-parse", "--abbrev-ref", "HEAD"), "main")
        self.assertEqual(pr.remote_branches(), before)

    def test_another_changed_file_means_more_than_the_one_file_and_nothing_is_committed(self):
        with Fixture() as pr:
            pr.write(FILE, NEW)
            pr.write("src/clark/mod.py", "X = 1\n")
            self.refused(pr, "src/clark/mod.py", "--run-id", "7", "--push")

    def test_a_run_id_that_is_not_digits_is_refused_because_it_names_a_branch(self):
        with Fixture() as pr:
            pr.write(FILE, NEW)
            for bad in ("", "12;rm", "../x", "abc", "7 8"):
                self.refused(pr, "run id", "--run-id", bad, "--push")
            code, out = pr.run_tool("--push")
            self.assertEqual(code, 2, out)

    def test_a_file_with_no_time_in_it_is_refused(self):
        with Fixture() as pr:
            for text in ("", "# only a header\n", "garbage\n", "test_mod.py 0\n"):
                pr.write(FILE, text)
                self.refused(pr, "no time", "--run-id", "7", "--push")

    def test_a_missing_file_is_refused(self):
        with Fixture() as pr:
            pr.remove(FILE)
            self.refused(pr, FILE, "--run-id", "7", "--push")


class ExistingBranchTest(unittest.TestCase):
    def test_a_branch_of_that_run_already_on_the_remote_is_never_overwritten_and_never_forced(self):
        with Fixture() as pr:
            pr.write(FILE, NEW)
            self.assertEqual(pr.run_tool("--run-id", "9", "--push")[0], 0)
            first = pr.remote_branches()
            pr.git("checkout", "-q", "main")
            pr.git("branch", "-q", "-D", "shard-times-9")                        # a fresh checkout of the same run (a re-run of the job): no local branch, one on the remote
            pr.git("checkout", "-q", "--", FILE)
            pr.write(FILE, "# header\ntest_mod.py 9.9\n")
            code, out = pr.run_tool("--run-id", "9", "--push")
            self.assertEqual(code, 1, out)
            self.assertIn("refused", out)
            self.assertIn("shard-times-9", out)
            self.assertEqual(pr.remote_branches(), first)
            self.assertNotIn("Traceback", out)

    def test_a_local_branch_of_that_run_is_not_checked_not_a_traceback(self):
        with Fixture() as pr:
            pr.git("branch", "shard-times-9")
            pr.write(FILE, NEW)
            before = pr.remote_branches()
            code, out = pr.run_tool("--run-id", "9", "--push")
            self.assertEqual(code, 2, out)
            self.assertIn("not checked", out.lower())
            self.assertNotIn("Traceback", out)
            self.assertEqual(pr.remote_branches(), before)


if __name__ == "__main__":
    unittest.main()
