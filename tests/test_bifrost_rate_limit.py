"""Bifrost: the GitHub reads survive the Actions installation rate limit without more calls and without a false FAIL.

Run: python3 dev/run_tests.py test_bifrost_rate_limit   (quick tier, standard library only)

A 403/429 that says rate limit is retried after 5, 15, 45 seconds, then the job fails with NOT CHECKED ... rerun (a required check never passes unchecked); a 403 that is not a rate
limit is not retried. On a pull_request run the pull request comes from the event payload (no call); the test files of a head come
from ONE tarball call (not one call per blob). Nothing here talks to GitHub: subprocess.run and time.sleep are replaced.
"""
import contextlib
import importlib.util
import io
import json
import os
import sys
import tarfile
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

from _paths import ROOT

BIFROST = ROOT / ".github" / "bifrost"


def load(name):
    sys.path.insert(0, str(BIFROST))
    try:
        spec = importlib.util.spec_from_file_location(name + "_under_test", BIFROST / (name + ".py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    finally:
        sys.path.remove(str(BIFROST))
    return mod


def done(rc=0, out="", err=""):
    return SimpleNamespace(returncode=rc, stdout=out, stderr=err)


LIMIT = "gh: API rate limit exceeded for installation. (HTTP 403)"


class Retry(unittest.TestCase):
    def setUp(self):
        self.P = load("pr_checks_report")

    def test_rate_limit_then_success_is_retried_with_growing_waits(self):
        with mock.patch.object(self.P.subprocess, "run", side_effect=[done(1, err=LIMIT), done(1, err="HTTP 429"), done(0, '{"a": 1}')]) as run, \
                mock.patch.object(self.P.time, "sleep") as sleep:
            self.assertEqual(self.P.gh_json("repos/x/y/pulls/1"), {"a": 1})
        self.assertEqual(run.call_count, 3)
        self.assertEqual([c.args[0] for c in sleep.call_args_list], [5, 15])

    def test_rate_limit_every_time_raises_rate_limited_after_four_calls(self):
        with mock.patch.object(self.P.subprocess, "run", return_value=done(1, err=LIMIT)) as run, \
                mock.patch.object(self.P.time, "sleep") as sleep:
            with self.assertRaises(self.P.RateLimited):
                self.P.gh_json("repos/x/y/pulls/1")
        self.assertEqual(run.call_count, 4)
        self.assertEqual([c.args[0] for c in sleep.call_args_list], [5, 15, 45])

    def test_a_403_that_is_not_a_rate_limit_is_not_retried(self):
        with mock.patch.object(self.P.subprocess, "run", return_value=done(1, err="HTTP 403: Resource not accessible by integration")) as run, \
                mock.patch.object(self.P.time, "sleep") as sleep:
            with self.assertRaises(RuntimeError) as cm:
                self.P.gh_json("repos/x/y/issues/1")
        self.assertNotIsInstance(cm.exception, self.P.RateLimited)
        self.assertEqual(run.call_count, 1)
        sleep.assert_not_called()

    def test_checks_do_not_turn_a_rate_limit_into_a_fail(self):
        body = ("Part of x/y#5\n\n## Point map\n\n| AP | Status | Where (file:line at this head) | Test (name) |\n|---|---|---|---|\n"
                "| AP1 | Covered | a.py:1 | test_a |\n\npoints_version: 0123abcd\n\n## Out of scope\n\nnone\n")

        def boom(*a):
            raise self.P.RateLimited("limit")
        with self.assertRaises(self.P.RateLimited):
            self.P.check_point_map(body, boom)
        with self.assertRaises(self.P.RateLimited):
            self.P.check_test_exists(body, lambda: boom())


class TestFilesOneCall(unittest.TestCase):
    def test_the_test_files_come_from_one_tarball_call(self):
        P = load("pr_checks_report")
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as tf:
            for name, text in (("o-r-abc/tests/test_a.py", "def test_a():\n    pass\n"), ("o-r-abc/src/app.py", "x = 1\n"),
                               ("o-r-abc/web/__tests__/b.js", "it('b', () => 1)\n"), ("o-r-abc/tests/data.json", "{}")):
                data = text.encode()
                ti = tarfile.TarInfo(name)
                ti.size = len(data)
                tf.addfile(ti, io.BytesIO(data))
        with mock.patch.object(P.subprocess, "run", return_value=done(0, out=buf.getvalue())) as run:
            files = P.GH("o/r", "").test_files("abc")
        self.assertEqual(run.call_count, 1)
        self.assertEqual(run.call_args.args[0], ["gh", "api", "repos/o/r/tarball/abc"])
        self.assertEqual(sorted(files), ["tests/test_a.py", "web/__tests__/b.js"])
        self.assertIn("def test_a", files["tests/test_a.py"])


class CiRun(unittest.TestCase):
    def setUp(self):
        self.C = load("ci_run")

    def payload(self, d, number=7):
        path = os.path.join(d, "event.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"pull_request": {"number": number, "title": "T", "body": "B", "head": {"sha": "abc12345"}}}, f)
        return path

    def test_the_pull_request_comes_from_the_event_payload_with_no_call(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, {"GITHUB_EVENT_PATH": self.payload(d), "GITHUB_RUN_ATTEMPT": "1"}), \
                mock.patch.object(self.C.P, "gh_json", side_effect=AssertionError("API call")):
            pr = self.C.CI("o/r", "").pr(7)
        self.assertEqual(pr["head"]["sha"], "abc12345")

    def test_a_rerun_ignores_the_payload_and_makes_one_api_call(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, {"GITHUB_EVENT_PATH": self.payload(d), "GITHUB_RUN_ATTEMPT": "2"}), \
                mock.patch.object(self.C.P, "gh_json", return_value={"number": 7, "title": "fresh"}) as g:
            pr = self.C.CI("o/r", "").pr(7)
        self.assertEqual(pr["title"], "fresh")
        g.assert_called_once_with("repos/o/r/pulls/7")

    def test_attempt_one_uses_the_payload_with_no_api_call(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, {"GITHUB_EVENT_PATH": self.payload(d), "GITHUB_RUN_ATTEMPT": "1"}), \
                mock.patch.object(self.C.P, "gh_json") as g:
            pr = self.C.CI("o/r", "").pr(7)
        self.assertEqual(pr["title"], "T")
        g.assert_not_called()

    def test_another_number_or_no_payload_is_one_api_call(self):
        with tempfile.TemporaryDirectory() as d:
            for env in ({"GITHUB_EVENT_PATH": self.payload(d)}, {"GITHUB_EVENT_PATH": os.path.join(d, "none.json")}):
                with mock.patch.dict(os.environ, env), mock.patch.object(self.C.P, "gh_json", return_value={"number": 8}) as g:
                    self.assertEqual(self.C.CI("o/r", "").pr(8), {"number": 8})
                g.assert_called_once_with("repos/o/r/pulls/8")

    def test_a_rate_limit_after_retries_fails_the_job_enforced_or_not(self):
        for check in self.C.P.CHECKS:
            for enforce in ("1", "0"):
                out = io.StringIO()
                with mock.patch.object(self.C.CI, "pr", side_effect=self.C.P.RateLimited("limit")), \
                        mock.patch.dict(os.environ, {"BIFROST_ENFORCE": enforce}), contextlib.redirect_stdout(out):
                    rc = self.C.main(["--check", check, "--pr", "7"])
                self.assertEqual(rc, 1)
                self.assertIn(f"bifrost-{check}: NOT CHECKED: GitHub rate limit after retries, rerun", out.getvalue())

    def test_a_rate_limit_inside_run_pr_fails_too(self):
        out = io.StringIO()
        with mock.patch.object(self.C.CI, "pr", return_value={}), mock.patch.object(self.C.P, "run_pr", side_effect=self.C.P.RateLimited("l")), \
                mock.patch.dict(os.environ, {"BIFROST_ENFORCE": "0"}), contextlib.redirect_stdout(out):
            self.assertEqual(self.C.main(["--check", "test-exists", "--pr", "7"]), 1)
        self.assertIn("NOT CHECKED", out.getvalue())


if __name__ == "__main__":
    unittest.main()
