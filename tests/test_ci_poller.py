"""dev/tools/ci_poller.py: the tower's pull-request tester, rehearsed on a local scratch repo (no GitHub, no network, no token).

Run: python3 dev/run_tests.py test_ci_poller
A scratch repo holds three branches whose `dev/run_tests.py` is a stub (it prints the runner's own summary line and exits 0 or 1).
The poller is run over them with a LocalForge, which records every status and comment it is asked to post instead of sending them."""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import timedelta
from unittest import mock
from pathlib import Path

from _paths import ROOT

sys.path.insert(0, str(ROOT / "dev" / "tools"))
import ci_poller as poller  # noqa: E402

STUB = """import sys
verdict = open("verdict.txt", encoding="utf-8").read().strip()
if verdict == "crash":
    print("Traceback: the suite itself could not start")
    sys.exit(2)
ok = verdict == "pass"
print("Python %d.%d.1: %s, 3 tests in 0.1 s" % (sys.version_info[0], sys.version_info[1], "pass" if ok else "FAIL"))
print("2 files passed, %d failed." % (0 if ok else 1))
sys.exit(0 if ok else 1)
"""


def git(folder, *args):
    subprocess.run(["git", "-C", str(folder)] + list(args), check=True, capture_output=True,
                   env={"PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin", "HOME": str(folder), "GIT_CONFIG_NOSYSTEM": "1",
                        "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
                        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid"})


def make_scratch(folder):
    repo = Path(folder) / "repo.git"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    (repo / "dev").mkdir()
    (repo / "dev" / "run_tests.py").write_text(STUB, encoding="utf-8")
    (repo / "verdict.txt").write_text("pass", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "root")
    shas = {}
    for name, verdict in (("good", "pass"), ("bad", "fail"), ("later", "pass"), ("crash", "crash")):
        git(repo, "checkout", "-q", "-b", name, "main")
        (repo / "verdict.txt").write_text(verdict, encoding="utf-8")
        git(repo, "commit", "-q", "-a", "--allow-empty", "-m", name)
        shas[name] = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    git(repo, "checkout", "-q", "main")
    prs = [
        {"number": 11, "headRefOid": shas["good"], "headRefName": "good", "isDraft": False, "isCrossRepository": False},
        {"number": 12, "headRefOid": shas["bad"], "headRefName": "bad", "isDraft": False, "isCrossRepository": False},
        {"number": 13, "headRefOid": "c" * 40, "headRefName": "x", "isDraft": False, "isCrossRepository": False, "conflict": True},
        {"number": 14, "headRefOid": "d" * 40, "headRefName": "x", "isDraft": True, "isCrossRepository": False},
        {"number": 15, "headRefOid": "e" * 40, "headRefName": "x", "isDraft": False, "isCrossRepository": True},
    ]
    (Path(folder) / "prs.json").write_text(json.dumps(prs), encoding="utf-8")
    return shas


def args_for(folder, **extra):
    base = ["--repo", "example/scratch", "--once", "--local", str(folder), "--work", str(Path(folder) / "work"), "--state", str(Path(folder) / "state.json"),
            "--pythons", "%s,%s" % (sys.executable, sys.executable), "--jobs", "1"]
    return poller.parse_args(base + list(extra.pop("more", [])))


class Decisions(unittest.TestCase):
    PR = {"number": 1, "headRefOid": "a" * 40, "isDraft": False, "isCrossRepository": False}

    def test_a_fresh_pr_is_tested(self):
        self.assertEqual(poller.wants_test(self.PR, [], {}), (True, ""))

    def test_a_draft_a_fork_a_known_sha_and_a_finished_status_are_not(self):
        self.assertFalse(poller.wants_test(dict(self.PR, isDraft=True), [], {})[0])
        self.assertFalse(poller.wants_test(dict(self.PR, isCrossRepository=True), [], {})[0])
        self.assertFalse(poller.wants_test(self.PR, [], {"a" * 40: {"state": "success"}})[0])
        done = [{"context": poller.CONTEXT, "state": "failure", "created_at": "2026-10-30T00:00:00Z"}]
        self.assertFalse(poller.wants_test(self.PR, done, {})[0])

    def test_another_runners_pending_counts_until_it_is_old(self):
        stamp = poller.now().strftime("%Y-%m-%dT%H:%M:%SZ")
        fresh = [{"context": poller.CONTEXT, "state": "pending", "created_at": stamp}]
        self.assertFalse(poller.wants_test(self.PR, fresh, {})[0])
        later = poller.now() + timedelta(minutes=poller.CLAIM_MINUTES + 1)
        self.assertTrue(poller.wants_test(self.PR, fresh, {}, at=later)[0])

    def test_another_context_does_not_count(self):
        other = [{"context": "something/else", "state": "success", "created_at": "2026-10-30T00:00:00Z"}]
        self.assertTrue(poller.wants_test(self.PR, other, {})[0])

    def test_the_tests_get_no_token_and_their_own_home(self):
        import os
        old = os.environ.get("GH_TOKEN")
        os.environ["GH_TOKEN"] = "x"
        try:
            env = poller.clean_env("/tmp/h")
        finally:
            if old is None:
                del os.environ["GH_TOKEN"]
            else:
                os.environ["GH_TOKEN"] = old
        self.assertNotIn("GH_TOKEN", env)
        self.assertEqual(env["HOME"], "/tmp/h")

    def test_the_browser_reaches_the_tests(self):
        self.assertEqual(poller.clean_env("/tmp/h", "/opt/x/chrome")["CLARK_CHROME"], "/opt/x/chrome")
        self.assertNotIn("CLARK_CHROME", {k: v for k, v in poller.clean_env("/tmp/h", "").items() if k == "CLARK_CHROME" and not v})

    def test_a_retest_ignores_an_earlier_result_but_never_a_draft_or_a_fork(self):
        done = [{"context": poller.CONTEXT, "state": "failure", "created_at": "2026-10-30T00:00:00Z"}]
        self.assertTrue(poller.wants_test(self.PR, done, {"a" * 40: {"state": "failure"}}, retest=True)[0])
        self.assertFalse(poller.wants_test(dict(self.PR, isDraft=True), done, {}, retest=True)[0])
        self.assertFalse(poller.wants_test(dict(self.PR, isCrossRepository=True), done, {}, retest=True)[0])

    def test_the_status_line_fits(self):
        line = poller.describe([(False, {"version": "3.9", "tests": 3185, "seconds": 170.2, "files_failed": 2, "note": "x" * 300})])
        self.assertLessEqual(len(line), poller.DESC_MAX)


def no_real_lock(name, *rest, **kw):
    """`shutil.which` for a test: the real clark-one-suite wrapper is never found (#338), so the poller runs the stub suite itself.
    Inside a push suite the wrapper would queue this inner run behind the outer suite's own slot and stall the whole push."""
    return None if name == "clark-one-suite" else shutil.which(name, *rest, **kw)


class Rehearsal(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name)
        self.shas = make_scratch(self.folder)
        self.lines = []
        patch = mock.patch.object(poller.shutil, "which", side_effect=no_real_lock)
        self.which = patch.start()
        self.addCleanup(patch.stop)

    def tearDown(self):
        self.tmp.cleanup()

    def run_pass(self, post, **kw):
        args = args_for(self.folder, **kw)
        args.post = post
        forge = poller.LocalForge(self.folder)
        state = poller.load_state(args.state)
        tested = poller.one_pass(forge, args, state, self.lines.append)
        if post:
            poller.save_state(args.state, state)
        return tested, forge

    def test_the_rehearsal_never_reaches_the_real_suite_wrapper(self):
        """#338: a pass that tests a PR looks for the wrapper (so the guard is really exercised), is told there is none, and the stub suite
        runs directly: the pass finishes at once, however busy the suite slots are."""
        tested, _ = self.run_pass(True)
        self.assertGreater(tested, 0)
        self.assertIn(mock.call("clark-one-suite"), self.which.call_args_list)
        self.assertIsNone(no_real_lock("clark-one-suite"))

    def test_a_dry_run_posts_nothing_and_runs_nothing(self):
        tested, forge = self.run_pass(False)
        self.assertEqual(tested, 0)
        self.assertEqual(forge.posted, {"statuses": [], "comments": []})
        self.assertTrue(any("WOULD test" in line for line in self.lines))
        self.assertFalse((self.folder / "state.json").exists())

    def test_each_pr_gets_its_own_verdict_on_its_own_sha(self):
        tested, forge = self.run_pass(True)
        self.assertEqual(tested, 3)                              # the good one, the bad one, and the one that does not merge (a failure, nothing run)
        by_sha = {}
        for s in forge.posted["statuses"]:
            by_sha.setdefault(s["sha"], []).append(s["state"])
        self.assertEqual(by_sha[self.shas["good"]], ["pending", "success"])
        self.assertEqual(by_sha[self.shas["bad"]], ["pending", "failure"])
        self.assertEqual(by_sha["c" * 40], ["pending", "failure"])
        self.assertNotIn("d" * 40, by_sha)                       # the draft
        self.assertNotIn("e" * 40, by_sha)                       # the fork
        conflict = [s for s in forge.posted["statuses"] if s["sha"] == "c" * 40][-1]
        self.assertIn("merge", conflict["description"])
        comments = {c["number"]: c["text"] for c in forge.posted["comments"]}
        self.assertIn(self.shas["good"][:12], comments[11])
        self.assertIn("success", comments[11])
        self.assertIn("failure", comments[12])

    def test_a_runner_fault_is_an_error_and_never_a_failure(self):
        prs = json.loads((self.folder / "prs.json").read_text(encoding="utf-8"))
        prs.append({"number": 21, "headRefOid": self.shas["crash"], "headRefName": "crash", "isDraft": False, "isCrossRepository": False})
        prs.append({"number": 22, "headRefOid": "f" * 40, "headRefName": "x", "isDraft": False, "isCrossRepository": False, "fetch_error": True})
        (self.folder / "prs.json").write_text(json.dumps(prs), encoding="utf-8")
        _, forge = self.run_pass(True, more=["--only", "11,12,13,21,22"])
        final = {}
        for s in forge.posted["statuses"]:
            final[s["sha"]] = s["state"]
        self.assertEqual(final[self.shas["good"]], "success")
        self.assertEqual(final[self.shas["bad"]], "failure")            # the PR's tests failed
        self.assertEqual(final["c" * 40], "failure")                    # the PR does not merge: the PR's fault
        self.assertEqual(final[self.shas["crash"]], "error")            # the suite could not start: the runner's fault
        self.assertEqual(final["f" * 40], "error")                      # the fetch failed: the runner's fault
        text = {c["number"]: c["text"] for c in forge.posted["comments"]}
        self.assertIn("fault of the runner", text[21])
        self.assertNotIn("fault of the runner", text[12])

    def test_no_comment_posts_the_status_only(self):
        _, forge = self.run_pass(True, more=["--no-comment"])
        self.assertTrue(forge.posted["statuses"])
        self.assertEqual(forge.posted["comments"], [])

    def test_a_second_pass_tests_nothing_again(self):
        self.run_pass(True)
        tested, forge = self.run_pass(True)
        self.assertEqual(tested, 0)
        self.assertEqual(len(forge.posted["statuses"]), 6)       # 3 PRs x (pending, final), none new

    def test_a_pr_whose_head_moves_is_tested_again(self):
        self.run_pass(True)
        prs = json.loads((self.folder / "prs.json").read_text(encoding="utf-8"))
        for pr in prs:
            if pr["number"] == 12:
                pr["headRefOid"] = self.shas["later"]
                pr["headRefName"] = "later"
        (self.folder / "prs.json").write_text(json.dumps(prs), encoding="utf-8")
        tested, forge = self.run_pass(True)
        self.assertEqual(tested, 1)
        last = [s for s in forge.posted["statuses"] if s["sha"] == self.shas["later"]]
        self.assertEqual([s["state"] for s in last], ["pending", "success"])

    def test_an_old_pr_is_skipped_and_the_newest_is_tested_first(self):
        prs = json.loads((self.folder / "prs.json").read_text(encoding="utf-8"))
        prs[0]["updatedAt"] = "2020-01-01T00:00:00Z"                      # #11, long untouched
        prs[1]["updatedAt"] = poller.now().strftime("%Y-%m-%dT%H:%M:%SZ")   # #12, just pushed
        (self.folder / "prs.json").write_text(json.dumps(prs), encoding="utf-8")
        self.run_pass(False)
        text = "\n".join(self.lines)
        self.assertIn("#11", text)
        self.assertIn("not updated for 3 days", text)
        self.assertLess(text.index("#12"), text.index("#11") if "#11" in text else 10 ** 9)

    def test_the_max_limit_leaves_the_rest_for_the_next_pass(self):
        tested, forge = self.run_pass(True, more=["--max", "1"])
        self.assertEqual(tested, 1)
        self.assertTrue(any("max" in line for line in self.lines))

    def test_the_poller_only_ever_posts_statuses_and_comments(self):
        _, forge = self.run_pass(True)
        self.assertEqual(set(forge.posted), {"statuses", "comments"})
        self.assertTrue(all(s["state"] in ("pending", "success", "failure") for s in forge.posted["statuses"]))

    def test_the_work_folders_are_removed(self):
        self.run_pass(True)
        self.assertEqual(list((self.folder / "work").iterdir()), [])

    def test_fewer_than_two_pythons_is_refused(self):
        with self.assertRaises(SystemExit):
            poller.parse_args(["--repo", "example/scratch", "--once", "--pythons", "python3"])

    def test_a_pr_by_an_author_off_the_trusted_list_is_skipped(self):
        prs = json.loads((self.folder / "prs.json").read_text(encoding="utf-8"))
        prs[0]["author"] = {"login": "stranger"}
        prs[1]["author"] = {"login": "member-a"}
        (self.folder / "prs.json").write_text(json.dumps(prs), encoding="utf-8")
        tested, forge = self.run_pass(True, more=["--only", "11,12", "--trusted-authors", "member-a,member-b"])
        self.assertEqual(tested, 1)
        self.assertIn("#11 %s: skipped, author not on the trusted list" % self.shas["good"][:8], "\n".join(self.lines))
        self.assertEqual({s["sha"] for s in forge.posted["statuses"]}, {self.shas["bad"]})

    def test_a_pr_with_no_author_is_skipped_when_a_list_is_set(self):
        _, forge = self.run_pass(True, more=["--only", "11", "--trusted-authors", "member-a"])
        self.assertEqual(forge.posted["statuses"], [])

    def test_a_pr_by_a_trusted_author_is_wanted(self):
        prs = json.loads((self.folder / "prs.json").read_text(encoding="utf-8"))
        prs[0]["author"] = {"login": "member-a"}
        (self.folder / "prs.json").write_text(json.dumps(prs), encoding="utf-8")
        tested, forge = self.run_pass(True, more=["--only", "11", "--trusted-authors", "member-a"])
        self.assertEqual(tested, 1)
        self.assertEqual([s["state"] for s in forge.posted["statuses"]], ["pending", "success"])


class SuiteLock(unittest.TestCase):
    """#338: what the poller does with the lock, checked on a fake one (a script in a temp folder), never the real clark-one-suite."""

    def run_with(self, found):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(poller.shutil, "which", return_value=found), \
                mock.patch.object(poller.subprocess, "run") as run:
            run.return_value = subprocess.CompletedProcess([], 0, stdout=b"Python 3.9.1: pass, 3 tests in 0.1 s\n2 files passed, 0 failed.\n")
            poller.run_python("/x/python", tmp, 1, {})
        return run.call_args[0][0]

    def test_the_suite_goes_through_the_lock_when_there_is_one(self):
        self.assertEqual(self.run_with("/x/fake-lock"), ["/x/fake-lock", "/x/python", "dev/run_tests.py", "-j", "1"])

    def test_the_suite_runs_directly_when_there_is_no_lock(self):
        self.assertEqual(self.run_with(None), ["/x/python", "dev/run_tests.py", "-j", "1"])

    def test_the_poller_asks_for_the_lock_by_name_and_runs_it_low(self):
        self.assertEqual(poller.clean_env("/tmp/h")["CLARK_SUITE_LOW"], "1")


class Safety(unittest.TestCase):
    def test_a_real_repository_without_trusted_authors_exits_2(self):
        self.assertEqual(poller.main(["--repo", "example/scratch", "--once"]), 2)

    def test_the_repo_is_required(self):
        with self.assertRaises(SystemExit) as raised:
            poller.parse_args(["--once"])
        self.assertEqual(raised.exception.code, 2)

    def test_the_trusted_authors_are_split_on_commas(self):
        args = poller.parse_args(["--repo", "example/scratch", "--once", "--trusted-authors", "a,b,,c"])
        self.assertEqual(args.trusted_authors, {"a", "b", "c"})


class ChromeStartsUsesTheHelper(unittest.TestCase):
    def test_chrome_starts_builds_its_command_through_the_helper(self):
        from unittest import mock
        seen = {}

        class Proc:
            def wait(self, t):
                raise subprocess.TimeoutExpired("chrome", t)

        def fake_start(cmd, r, w):
            seen["cmd"] = cmd
            return Proc()

        with mock.patch.object(poller.run_support, "start_chrome", fake_start), \
                mock.patch.object(poller.run_support, "stop_chrome") as stop:
            self.assertTrue(poller.chrome_starts("/x/chrome", settle=0))
        stop.assert_called_once()
        for flag in poller.run_support.KEYCHAIN_FLAGS:
            self.assertIn(flag, seen["cmd"])

    def test_chrome_that_exits_by_itself_does_not_start(self):
        from unittest import mock

        class Dead:
            def wait(self, t):
                return 1

        with mock.patch.object(poller.run_support, "start_chrome", lambda c, r, w: Dead()), \
                mock.patch.object(poller.run_support, "stop_chrome"):
            self.assertFalse(poller.chrome_starts("/x/chrome", settle=0))


if __name__ == "__main__":
    unittest.main()
