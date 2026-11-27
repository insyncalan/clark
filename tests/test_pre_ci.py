"""Pre-CI (dev/tools/pre_ci.py): one command that runs the six checks on a head and records the result with the head sha.
(1) the scan, (2) the test-honesty and scope scripts, (3) the ticket's named tests, (4) the affected tests, (5) the Python 3.9
compile check, (6) the smoke suite. It runs inside a fixture pull request (tests/_pr_fixture.py), with the real runner and tools.

Run: python3 dev/run_tests.py test_pre_ci   (quick tier)
"""
import json
import subprocess
import sys
import unittest

from _paths import ROOT  # noqa: F401  (puts dev/tools on the path)
from _pr_fixture import PrFixture, TEST_MOD

import pre_ci

NAMES = ["scan", "test honesty", "scope", "named tests", "affected tests", "Python 3.9 compile", "smoke suite"]
TICKET = {"ticket": "9001", "files": ["src/clark/mod.py"], "named_tests": ["test_mod.ModTest.test_triple"]}
FEATURE = "def double(n):\n    return n * 2\n\n\ndef triple(n):\n    return n * 3\n"
FEATURE_TEST = TEST_MOD.replace("\n\nif __name__", "\n    def test_triple(self):\n        self.assertEqual(mod.triple(2), 6)\n\n\nif __name__")


class Fixture(PrFixture):
    """The fixture with the tools in it and a ticket file beside it (outside the repository, as Dum-E would hand it over)."""
    def __init__(self):
        super().__init__(with_tools=True)
        self.ticket = self.dir.parent / (self.dir.name + "-ticket.json")
        self.ticket.write_text(json.dumps(TICKET), encoding="utf-8")
        self.records = self.dir.parent / (self.dir.name + "-records")

    def __exit__(self, *exc):
        import shutil
        self.ticket.unlink()
        shutil.rmtree(self.records, ignore_errors=True)
        return super().__exit__(*exc)

    def feature(self):
        self.write("src/clark/mod.py", FEATURE)
        self.write("tests/test_mod.py", FEATURE_TEST)
        return self.commit("triple")

    def pre_ci(self, *more):
        env = dict(self.env)
        r = subprocess.run([sys.executable, "dev/tools/pre_ci.py", "--ticket", str(self.ticket), "--base", self.base,
                            "--record", str(self.records), *more], cwd=self.dir, env=env, capture_output=True, text=True)
        return r.returncode, r.stdout + r.stderr

    def record(self, head):
        return json.loads((self.records / (head + ".json")).read_text(encoding="utf-8"))


HAVE_39 = bool(pre_ci.python39())      # no Python 3.9 on the box: check 5 is "not checked" and the run cannot pass


def results(doc):
    return {c["name"]: c["result"] for c in doc["checks"]}


class GreenTest(unittest.TestCase):
    def test_the_six_checks_run_and_the_result_is_recorded_with_the_head_sha(self):
        with Fixture() as pr:
            head = pr.feature()
            code, out = pr.pre_ci()
            self.assertEqual(code, 0 if HAVE_39 else 1, out)
            self.assertIn("PRE-CI %s %s" % ("pass" if HAVE_39 else "FAIL", head), out)
            doc = pr.record(head)
            self.assertEqual(doc["head"], head)
            self.assertEqual(doc["base"], pr.base)
            self.assertEqual(doc["ticket"], "9001")
            self.assertEqual(doc["result"], "pass" if HAVE_39 else "fail")
            self.assertEqual([c["name"] for c in doc["checks"]], NAMES)
            self.assertEqual([c["n"] for c in doc["checks"]], [1, 2, 2, 3, 4, 5, 6])
            self.assertEqual({k: v for k, v in results(doc).items() if v != "pass"}, {} if HAVE_39 else {"Python 3.9 compile": "not checked"})
            for c in doc["checks"]:
                self.assertTrue(c["command"], c["name"])
                self.assertIn("seconds", c)
            # the size is logged, and is never a check
            self.assertEqual(doc["size"], {"files": 2, "additions": 7, "deletions": 0})
            self.assertRegex(doc["finished"], r"^\d\d-\d\d-\d{4} \d\d:\d\d:\d\d \+04$")
            # one line per run in the log beside the records
            log = (pr.records / "log.jsonl").read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(log), 1)
            self.assertEqual(json.loads(log[0])["head"], head)
            # the named tests, the affected tests and the smoke suite really ran
            by = {c["name"]: c for c in doc["checks"]}
            self.assertIn("test_mod.ModTest.test_triple", by["named tests"]["command"])
            self.assertIn("1 tests", by["named tests"]["tail"])
            self.assertIn("3 tests", by["smoke suite"]["tail"])
            self.assertIn("3 tests", by["affected tests"]["tail"])


class RedTest(unittest.TestCase):
    def failing(self, pr, head):
        return sorted(k for k, v in results(pr.record(head)).items() if v == "fail")

    def test_a_line_python_3_9_cannot_parse_fails_the_compile_check(self):
        with Fixture() as pr:
            pr.write("src/clark/mod.py", FEATURE + "\n\ndef kind(n):\n    match n:\n        case 1:\n            return 'one'\n    return 'many'\n")
            pr.write("tests/test_mod.py", FEATURE_TEST)
            head = pr.commit("match statement")
            code, out = pr.pre_ci()
            self.assertEqual(code, 1, out)
            self.assertIn("PRE-CI FAIL " + head, out)
            self.assertEqual(self.failing(pr, head), ["Python 3.9 compile"])
            self.assertIn("src/clark/mod.py", {c["name"]: c for c in pr.record(head)["checks"]}["Python 3.9 compile"]["tail"])
            self.assertEqual(pr.record(head)["result"], "fail")

    def test_a_deleted_test_fails_test_honesty_alone(self):
        with Fixture() as pr:
            pr.write("src/clark/mod.py", FEATURE)
            pr.write("tests/test_mod.py", FEATURE_TEST.replace(
                "    def test_double_negative(self):\n        self.assertEqual(mod.double(-1), -2)\n",
                "    def helper(self):\n        self.assertEqual(mod.double(-1), -2)\n"))
            head = pr.commit("drop a test")
            code, _ = pr.pre_ci()
            self.assertEqual(code, 1)
            self.assertEqual(self.failing(pr, head), ["test honesty"])

    def test_an_added_skip_fails_test_honesty_alone(self):
        with Fixture() as pr:
            pr.write("src/clark/mod.py", FEATURE)
            pr.write("tests/test_mod.py", FEATURE_TEST.replace(
                "    def test_double_negative", "    @unittest.skip('later')\n    def test_double_negative"))
            head = pr.commit("skip one")
            self.assertEqual(pr.pre_ci()[0], 1)
            self.assertEqual(self.failing(pr, head), ["test honesty"])

    def test_fewer_asserts_fails_test_honesty_alone(self):
        with Fixture() as pr:
            pr.write("src/clark/mod.py", FEATURE)
            pr.write("tests/test_mod.py", FEATURE_TEST.replace("        self.assertEqual(mod.double(0), 0)\n", "")
                     .replace("self.assertEqual(mod.triple(2), 6)", "mod.triple(2)"))
            head = pr.commit("fewer asserts")
            self.assertEqual(pr.pre_ci()[0], 1)
            self.assertEqual(self.failing(pr, head), ["test honesty"])

    def test_an_extra_file_fails_scope_alone(self):
        with Fixture() as pr:
            pr.write("src/clark/mod.py", FEATURE)
            pr.write("tests/test_mod.py", FEATURE_TEST)
            pr.write("src/clark/extra.py", "X = 1\n")
            head = pr.commit("one file too many")
            code, out = pr.pre_ci()
            self.assertEqual(code, 1)
            self.assertEqual(self.failing(pr, head), ["scope"])
            self.assertIn("src/clark/extra.py", out)

    def test_uncommitted_work_is_refused_because_the_record_names_a_head(self):
        with Fixture() as pr:
            pr.feature()
            pr.write("src/clark/mod.py", FEATURE + "\n# not committed\n")
            code, out = pr.pre_ci()
            self.assertEqual(code, 2)
            self.assertIn("commit first", out)
            self.assertFalse(pr.records.exists())

    def test_a_base_git_cannot_find_is_did_not_start_exit_2_not_a_failed_check(self):
        with Fixture() as pr:
            pr.feature()
            code, out = pr.pre_ci("--base", "origin/does-not-exist")
            self.assertEqual(code, 2)
            self.assertIn("did not start", out)
            self.assertFalse(pr.records.exists())


class PartsTest(unittest.TestCase):
    def test_without_a_real_python_3_9_the_compile_check_is_not_checked_never_a_pass(self):
        """Found in the read of 0e8947b8: with no Python 3.9 the grammar switch of a newer Python recorded pass, and it accepts
        syntax 3.9 refuses (a parenthesised with, for one). It can still prove a fail; it can never prove a pass."""
        real = pre_ci.python39
        pre_ci.python39 = lambda: ""
        try:
            check = pre_ci.PreCi("", "", "").compile39()
        finally:
            pre_ci.python39 = real
        self.assertEqual((check["result"], check["exit"]), ("not checked", None))
        self.assertIn("no Python 3.9", check["tail"])

    def test_the_real_smoke_list_names_files_that_exist(self):
        names = pre_ci.smoke_names((ROOT / "dev" / "tools" / "pre_ci_smoke.txt").read_text(encoding="utf-8"))
        self.assertTrue(names)
        for n in names:
            self.assertTrue((ROOT / "tests" / (n + ".py")).is_file(), n)

    def test_a_name_every_test_file_holds_is_not_followed_but_its_own_test_file_runs(self):
        listed = ["test_a.py", "test_b.py", "test_c.py", "test_d.py", "test_run_tests.py"]
        chosen, capped = pre_ci.narrow(listed, ["dev/run_tests.py"], lambda f: "Run: python3 dev/run_tests.py", cap=3)
        self.assertEqual((chosen, capped), (["test_run_tests.py"], True))


if __name__ == "__main__":
    unittest.main()
