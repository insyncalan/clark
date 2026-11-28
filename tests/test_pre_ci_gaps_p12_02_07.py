"""Pre-CI (dev/tools/pre_ci.py), rows P12-02..P12-07: pins of as-built behaviour that the first pre-CI tests leave open.
Each test names one thing the tool does: the over-target note, which exit-2 results are "not checked", the named-tests
output test, the narrowing rule at the cap, the affected-tests branches, the Python 3.9 lookup and fallback, the smoke list
parser, the log line. Tests only; the tool is unchanged. Most tests replace `run`, `git` or the clock inside pre_ci, so
nothing waits and nothing is spawned.

Run: python3 dev/run_tests.py test_pre_ci_gaps_p12_02_07   (quick tier)
"""
import contextlib
import io
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

from _paths import ROOT  # noqa: F401  (puts dev/tools on the path)

import pre_ci

TICKET = {"ticket": "9001", "files": ["src/clark/mod.py"], "named_tests": ["test_mod.ModTest.test_triple"]}


class Swap:
    """Replace attributes of pre_ci for one block and put the real ones back."""
    def __init__(self, **attrs):
        self.attrs, self.saved = attrs, {}

    def __enter__(self):
        for k, v in self.attrs.items():
            self.saved[k] = getattr(pre_ci, k)
            setattr(pre_ci, k, v)

    def __exit__(self, *exc):
        for k, v in self.saved.items():
            setattr(pre_ci, k, v)


class FakeClock:
    """Stands in for pre_ci.time: the first read is 0, every later read is `after`."""
    def __init__(self, after):
        self.after, self.reads = after, 0

    def time(self):
        self.reads += 1
        return 0.0 if self.reads == 1 else float(self.after)


def no_run(argv, stdin=None):
    """A run that must never happen: a broken tool that reaches it fails the test instead of launching dev/run_tests.py."""
    raise AssertionError("the real runner was launched: %r" % (argv,))


def fake_git(*args):
    return {"rev-parse": "abc123\n", "merge-base": "base123\n"}.get(args[0], "")


def main_with(run_all, seconds=1):
    """main() with git, the clock and the six checks replaced: (exit code, printed text, record, log lines)."""
    out = io.StringIO()
    with tempfile.TemporaryDirectory() as tmp:
        ticket = Path(tmp) / "ticket.json"
        ticket.write_text(json.dumps(TICKET), encoding="utf-8")
        with Swap(git=fake_git, time=FakeClock(seconds), run=no_run), unittest.mock.patch.object(pre_ci.PreCi, "run_all", run_all), \
                contextlib.redirect_stdout(out):
            code = pre_ci.main(["--ticket", str(ticket), "--record", str(Path(tmp) / "rec")])
        doc = json.loads((Path(tmp) / "rec" / "abc123.json").read_text(encoding="utf-8"))
        log = (Path(tmp) / "rec" / "log.jsonl").read_text(encoding="utf-8").splitlines()
    return code, out.getvalue(), doc, log


class OneRunTest(unittest.TestCase):
    """P12-02: one command, one record and one log line, the target note."""
    def test_a_run_over_the_target_prints_the_note_and_a_run_at_the_target_does_not(self):
        nothing = lambda self, t, c: None
        _, text, _, _ = main_with(nothing, seconds=pre_ci.TARGET_SECONDS + 1)
        self.assertIn("note: 301 s, over the 300 s target (logged, never blocks)", text)
        _, text, _, _ = main_with(nothing, seconds=pre_ci.TARGET_SECONDS)
        self.assertNotIn("over the 300 s target", text)
        self.assertNotIn("note:", text)

    def test_the_cap_and_the_target_are_40_files_and_300_seconds(self):
        self.assertEqual(pre_ci.AFFECTED_CAP, 40)
        self.assertEqual(pre_ci.TARGET_SECONDS, 300)

    def test_the_log_line_holds_the_seconds_of_the_run(self):
        _, _, doc, log = main_with(lambda self, t, c: None, seconds=42)
        self.assertEqual(json.loads(log[0])["seconds"], 42)
        self.assertEqual(doc["seconds"], 42)

    def test_the_log_line_holds_the_result_of_each_check_by_name_and_no_more_than_the_summary(self):
        def two(self, t, c):
            self.add(1, "scan", ["x"], 0, "", 0.0)
            self.add(3, "named tests", ["y"], 1, "bad", 0.0)
        code, text, doc, log = main_with(two)
        self.assertEqual(code, 1)
        self.assertEqual(len(log), 1)
        line = json.loads(log[0])
        self.assertEqual(sorted(line), ["base", "checks", "finished", "head", "result", "seconds", "ticket"])
        self.assertEqual(line["checks"], {"scan": "pass", "named tests": "fail"})
        self.assertEqual((line["head"], line["base"], line["ticket"], line["result"]), ("abc123", "base123", "9001", "fail"))
        self.assertIn("PRE-CI FAIL abc123", text)
        self.assertEqual(doc["result"], "fail")

    def test_one_failing_check_among_passes_fails_the_run(self):
        def mixed(self, t, c):
            self.add(1, "scan", ["x"], 0, "", 0.0)
            self.add(2, "scope", ["x"], 1, "", 0.0)
            self.add(3, "named tests", ["x"], 0, "", 0.0)
        code, text, doc, _ = main_with(mixed)
        self.assertEqual((code, doc["result"]), (1, "fail"))

    def test_the_run_runs_every_check_in_order_even_when_the_scan_fails(self):
        seen, ns = [], []

        def record(name, code):
            def f(self, *a, **k):
                seen.append(name)
                return self.add(1, name, ["x"], code, "", 0.0)
            return f
        with Swap(run=no_run), unittest.mock.patch.object(pre_ci.PreCi, "tool", lambda self, n, name, script, *a: seen.append(name) or ns.append(n) or self.add(n, name, ["x"], 1, "", 0.0)), \
                unittest.mock.patch.object(pre_ci.PreCi, "named", record("named", 0)), \
                unittest.mock.patch.object(pre_ci.PreCi, "affected", record("affected", 0)), \
                unittest.mock.patch.object(pre_ci.PreCi, "compile39", record("compile39", 0)), \
                unittest.mock.patch.object(pre_ci.PreCi, "smoke", record("smoke", 0)):
            pre_ci.PreCi("t.json", "base", "head").run_all({"named_tests": ["a"]}, [])
        self.assertEqual(seen, ["scan", "test honesty", "scope", "named", "affected", "compile39", "smoke"])
        self.assertEqual(ns, [1, 2, 2])

    def test_the_scripts_get_the_ticket_the_base_and_the_head(self):
        calls = []
        with Swap(run=lambda argv, stdin=None: calls.append(argv) or (0, "", 0.0)), \
                unittest.mock.patch.object(pre_ci.PreCi, "named", lambda self, t: None), \
                unittest.mock.patch.object(pre_ci.PreCi, "affected", lambda self, c: None), \
                unittest.mock.patch.object(pre_ci.PreCi, "compile39", lambda self: None), \
                unittest.mock.patch.object(pre_ci.PreCi, "smoke", lambda self: None):
            pre_ci.PreCi("/t/ticket.json", "BASE", "HEAD").run_all({}, [])
        self.assertEqual([c[1:] for c in calls], [
            ["dev/tools/ci_scan.py", "--repo", ".", "--base", "BASE", "--head", "HEAD"],
            ["dev/tools/honesty_check.py", "--repo", ".", "--base", "BASE", "--head", "HEAD"],
            ["dev/tools/scope_check.py", "--repo", ".", "--base", "BASE", "--head", "HEAD", "--ticket", "/t/ticket.json"]])


class ResultMappingTest(unittest.TestCase):
    """P12-03: exit 0 is pass, a check that could not start is not checked, and only the scan and the scripts (checks 1 and 2)
    read their own exit 2 as not checked; any other non-zero exit, exit 2 of a test run included, is a fail."""
    def result(self, n, code):
        return pre_ci.PreCi("", "", "").add(n, "x", ["x"], code, "", 0.0)["result"]

    def test_exit_0_is_a_pass_for_every_check(self):
        self.assertEqual([self.result(n, 0) for n in range(1, 7)], ["pass"] * 6)

    def test_exit_1_is_a_fail_for_every_check(self):
        self.assertEqual([self.result(n, 1) for n in range(1, 7)], ["fail"] * 6)

    def test_exit_2_is_not_checked_for_the_scan_and_the_scripts_only(self):
        self.assertEqual([self.result(n, 2) for n in range(1, 7)],
                         ["not checked", "not checked", "fail", "fail", "fail", "fail"])

    def test_a_check_that_could_not_start_is_not_checked_for_every_check(self):
        self.assertEqual([self.result(n, None) for n in range(1, 7)], ["not checked"] * 6)

    def test_a_failed_check_prints_its_tail_and_a_pass_does_not(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            pre_ci.PreCi("", "", "").add(2, "scope", ["x"], 1, "one\ntwo", 0.0)
            pre_ci.PreCi("", "", "").add(1, "scan", ["x"], 0, "hidden", 0.0)
        self.assertIn("    one\n    two\n", out.getvalue())
        self.assertNotIn("hidden", out.getvalue())

    def test_the_tail_is_the_last_12_non_blank_lines(self):
        text = "\n".join("l%d" % i for i in range(20)).replace("l5", "")
        self.assertEqual(pre_ci.tail(text).splitlines(), ["l%d" % i for i in range(8, 20)])
        self.assertEqual(pre_ci.TAIL_LINES, 12)

    def test_the_tail_drops_lines_that_hold_only_white_space(self):
        self.assertEqual(pre_ci.tail("a\n   \n\t\nb\n  \n"), "a\nb")

    def test_a_check_prints_one_progress_line_with_its_number_name_result_and_seconds(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            pre_ci.PreCi("", "", "").add(3, "named tests", ["x"], 0, "", 2.0)
        self.assertRegex(out.getvalue(), r"^3 named tests\s+pass\s+2\.0 s\n$")

    def test_a_check_that_could_not_start_prints_its_tail_too(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            pre_ci.PreCi("", "", "").add(1, "scan", ["x"], None, "could not start: OSError", 0.0)
        self.assertIn("    could not start: OSError\n", out.getvalue())

    def test_the_seconds_are_recorded_rounded_to_one_decimal(self):
        check = pre_ci.PreCi("", "", "").add(1, "scan", ["x"], 0, "", 1.26)
        self.assertEqual(check["seconds"], 1.3)

    def test_the_record_holds_only_the_last_12_lines_of_the_output(self):
        check = pre_ci.PreCi("", "", "").add(1, "scan", ["x"], 0, "\n".join("l%d" % i for i in range(20)), 0.0)
        self.assertEqual(check["tail"].splitlines(), ["l%d" % i for i in range(8, 20)])

    def test_a_tool_that_cannot_start_is_not_checked(self):
        with Swap(run=lambda argv, stdin=None: (None, "could not start: FileNotFoundError", 0.0)):
            check = pre_ci.PreCi("", "", "").tool(1, "scan", pre_ci.TOOLS / "ci_scan.py")
        self.assertEqual((check["result"], check["exit"]), ("not checked", None))


class NamedTestsTest(unittest.TestCase):
    """P12-04: the ticket's named tests go to the runner as they are, and the output must say that tests ran."""
    def test_the_names_are_handed_to_the_runner_in_order(self):
        calls = []
        with Swap(run=lambda argv, stdin=None: calls.append(argv) or (0, "pass, 2 tests in 0.1 s\n", 0.1)):
            check = pre_ci.PreCi("", "", "").named(["test_a.A.test_one", "test_b"])
        self.assertEqual(calls, [[sys.executable, "dev/run_tests.py", "test_a.A.test_one", "test_b"]])
        self.assertEqual((check["n"], check["result"]), (3, "pass"))

    def test_output_that_counts_tests_without_the_words_tests_in_is_not_proof_that_they_ran(self):
        with Swap(run=lambda argv, stdin=None: (0, "pass, 5 tests\n", 0.1)):
            check = pre_ci.PreCi("", "", "").named(["test_a"])
        self.assertEqual((check["result"], check["exit"]), ("fail", 1))
        self.assertIn("no named test ran", check["tail"])

    def test_a_failing_run_stays_a_fail_with_its_own_exit_code(self):
        with Swap(run=lambda argv, stdin=None: (1, "FAIL\nFAILED test_a\n", 0.1)):
            check = pre_ci.PreCi("", "", "").named(["test_a"])
        self.assertEqual((check["result"], check["exit"]), ("fail", 1))
        self.assertNotIn("no named test ran", check["tail"])

    def test_a_test_run_that_exits_2_is_a_fail_with_exit_2_and_no_missing_tests_note(self):
        with Swap(run=lambda argv, stdin=None: (2, "usage error\n", 0.1)):
            check = pre_ci.PreCi("", "", "").named(["test_a"])
        self.assertEqual((check["result"], check["exit"]), ("fail", 2))
        self.assertNotIn("no named test ran", check["tail"])

    def test_run_all_hands_the_named_tests_of_the_ticket_to_check_3(self):
        got = []
        with Swap(run=lambda argv, stdin=None: (0, "", 0.0)), \
                unittest.mock.patch.object(pre_ci.PreCi, "named", lambda self, t: got.append(t)), \
                unittest.mock.patch.object(pre_ci.PreCi, "affected", lambda self, c: None), \
                unittest.mock.patch.object(pre_ci.PreCi, "compile39", lambda self: None), \
                unittest.mock.patch.object(pre_ci.PreCi, "smoke", lambda self: None):
            pre_ci.PreCi("t", "b", "h").run_all({"named_tests": ["x.y", "z"]}, [])
            pre_ci.PreCi("t", "b", "h").run_all({"named_tests": None}, [])
            pre_ci.PreCi("t", "b", "h").run_all({}, [])
        self.assertEqual(got, [["x.y", "z"], [], []])


class NarrowTest(unittest.TestCase):
    """P12-05: narrowing at the cap."""
    def test_up_to_the_cap_the_whole_list_runs_uncapped(self):
        listed = ["test_a.py", "test_b.py", "test_c.py"]
        self.assertEqual(pre_ci.narrow(listed, ["x.py"], lambda f: "", cap=3), (listed, False))
        self.assertEqual(pre_ci.narrow(listed, ["x.py"], lambda f: "", cap=4), (listed, False))

    def test_files_that_name_a_changed_file_are_followed_when_no_more_than_the_cap_hold_it(self):
        listed = ["test_a.py", "test_b.py", "test_c.py", "test_d.py", "test_e.py", "test_f.py"]
        holds = {"test_b.py", "test_d.py", "test_f.py"}
        chosen, capped = pre_ci.narrow(listed, ["src/x.py"], lambda f: "see x.py" if f in holds else "", cap=3)
        self.assertEqual((chosen, capped), (["test_b.py", "test_d.py", "test_f.py"], True))

    def test_a_name_held_by_more_files_than_the_cap_is_not_followed(self):
        listed = ["test_a.py", "test_b.py", "test_c.py", "test_d.py", "test_e.py", "test_f.py"]
        holds = {"test_a.py", "test_b.py", "test_c.py", "test_d.py"}
        chosen, capped = pre_ci.narrow(listed, ["src/x.py"], lambda f: "see x.py" if f in holds else "", cap=3)
        self.assertEqual((chosen, capped), ([], True))

    def test_the_close_files_are_a_changed_test_file_and_test_name_for_a_changed_name(self):
        listed = ["test_a.py", "test_b.py", "test_c.py", "test_d.py", "test_e.py"]
        chosen, capped = pre_ci.narrow(listed, ["tests/test_d.py", "src/clark/c.py", "src/clark/other.py"], lambda f: "", cap=3)
        self.assertEqual((chosen, capped), (["test_c.py", "test_d.py"], True))

    def test_a_text_that_cannot_be_read_names_nothing(self):
        listed = ["test_a.py", "test_b.py", "test_c.py", "test_d.py"]
        self.assertEqual(pre_ci.narrow(listed, ["x.py"], lambda f: None, cap=3), ([], True))

    def test_a_text_that_cannot_be_read_names_nothing_even_beside_files_that_are_read(self):
        listed = ["test_a.py", "test_b.py", "test_c.py", "test_d.py", "test_e.py"]
        unread = {"test_a.py", "test_b.py"}
        chosen, capped = pre_ci.narrow(listed, ["x"], lambda f: None if f in unread else "other", cap=3)
        self.assertEqual((chosen, capped), ([], True))

    def test_the_close_files_are_cut_at_the_cap_in_name_order(self):
        listed = ["test_%s.py" % c for c in "edcba"] + ["test_f.py"]
        chosen, capped = pre_ci.narrow(listed, ["a.py", "b.py", "c.py", "d.py", "e.py"], lambda f: "", cap=3)
        self.assertEqual((chosen, capped), (["test_a.py", "test_b.py", "test_c.py"], True))


class AffectedTest(unittest.TestCase):
    """P12-05: what check 4 asks the runner for."""
    def run_affected(self, listing, changed, tests=None, base="BASE"):
        """(check, the commands run). `listing` is what `run_tests.py --changed BASE --list` prints."""
        calls = []

        def fake_run(argv, stdin=None):
            calls.append(argv)
            if "--list" in argv:
                return listing
            return 0, "pass, 3 tests in 0.1 s\n", 0.5
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "tests").mkdir()
            for name, text in (tests or {}).items():
                (Path(tmp) / "tests" / name).write_text(text, encoding="utf-8")
            with Swap(run=fake_run, ROOT=Path(tmp)):
                check = pre_ci.PreCi("", base, "").affected(changed)
        return check, calls

    def test_up_to_the_cap_the_runner_is_asked_for_the_changed_files_of_the_base(self):
        out = "test_a.py  (quick)\nnoise line\ntest_b.py  (quick)\n"
        check, calls = self.run_affected((0, out, 0.1), ["src/x.py"])
        self.assertEqual(calls[1], [sys.executable, "dev/run_tests.py", "--changed", "BASE"])
        self.assertEqual((check["result"], check["files"], check["reached"], check["capped"]), ("pass", 2, 2, False))
        self.assertEqual(calls[0], [sys.executable, "dev/run_tests.py", "--changed", "BASE", "--list"])

    def test_only_lines_that_start_test_and_hold_py_are_test_files(self):
        out = "test_a.py\ntest_b\nnot_test_c.py\n  test_d.py\ntest_e.py  extra words\n"
        check, calls = self.run_affected((0, out, 0.1), ["src/x.py"])
        self.assertEqual((check["files"], check["reached"]), (2, 2))

    def test_over_the_cap_only_the_close_files_run_and_the_record_says_capped(self):
        names = ["test_f%02d.py" % i for i in range(41)]
        out = "".join(n + "  (quick)\n" for n in names)
        tests = {n: "" for n in names}
        tests["test_f07.py"] = "x = 'src/clark/thing.py'\n"
        check, calls = self.run_affected((0, out, 0.1), ["src/clark/thing.py"], tests)
        self.assertEqual(calls[1], [sys.executable, "dev/run_tests.py", "test_f07.py"])
        self.assertEqual((check["result"], check["files"], check["reached"], check["capped"]), ("pass", 1, 41, True))

    def test_over_the_cap_with_no_close_file_nothing_runs_and_it_is_a_pass_that_says_so(self):
        names = ["test_f%02d.py" % i for i in range(41)]
        out = "".join(n + "\n" for n in names)
        check, calls = self.run_affected((0, out, 0.1), ["src/clark/thing.py"], {n: "" for n in names})
        self.assertEqual(len(calls), 1)
        self.assertEqual((check["result"], check["exit"], check["files"], check["reached"], check["capped"]), ("pass", 0, 0, 41, True))
        self.assertIn("41 test files reach this change; none names a changed file, none run here (capped)", check["tail"])

    def test_no_affected_test_file_is_a_pass_that_says_so_and_runs_nothing_more(self):
        check, calls = self.run_affected((0, "nothing to run\n", 0.1), ["README.md"])
        self.assertEqual(len(calls), 1)
        self.assertEqual((check["result"], check["exit"], check["files"], check["capped"]), ("pass", 0, 0, False))
        self.assertIn("no test file is affected", check["tail"])

    def test_a_listing_that_fails_is_a_fail_and_nothing_else_runs(self):
        check, calls = self.run_affected((1, "test_a.py\n", 0.1), ["src/x.py"])
        self.assertEqual(len(calls), 1)
        self.assertEqual((check["result"], check["exit"]), ("fail", 1))

    def test_a_listing_that_cannot_start_is_not_checked(self):
        check, calls = self.run_affected((None, "could not start: OSError", 0.0), ["src/x.py"])
        self.assertEqual((check["result"], check["exit"], len(calls)), ("not checked", None, 1))

    def test_a_failing_affected_run_fails_the_check(self):
        calls = []

        def fake_run(argv, stdin=None):
            calls.append(argv)
            return (0, "test_a.py\n", 0.1) if "--list" in argv else (1, "FAILED\n", 0.5)
        with Swap(run=fake_run):
            check = pre_ci.PreCi("", "BASE", "").affected(["src/x.py"])
        self.assertEqual((check["result"], check["exit"]), ("fail", 1))
        self.assertAlmostEqual(check["seconds"], 0.6, places=1)


class Python39Test(unittest.TestCase):
    """P12-06: the lookup of a Python 3.9 and the fallback."""
    def script(self, tmp, name, version):
        path = Path(tmp) / name
        path.write_text("#!/bin/sh\necho %s\n" % version, encoding="utf-8")
        path.chmod(path.stat().st_mode | stat.S_IXUSR)
        return str(path)

    def lookup(self, env, which):
        with unittest.mock.patch.dict(os.environ, {"CLARK_PY39": env} if env is not None else {}), \
                unittest.mock.patch.object(pre_ci.shutil, "which", lambda n: which):
            if env is None:
                os.environ.pop("CLARK_PY39", None)
            return pre_ci.python39()

    def test_the_env_variable_wins_over_the_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            env, path = self.script(tmp, "env39", "3.9"), self.script(tmp, "path39", "3.9")
            self.assertEqual(self.lookup(env, path), env)

    def test_the_path_is_used_when_the_env_variable_is_unset_or_unusable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.script(tmp, "path39", "3.9")
            self.assertEqual(self.lookup(None, path), path)
            self.assertEqual(self.lookup("", path), path)
            self.assertEqual(self.lookup(str(Path(tmp) / "missing"), path), path)

    def test_an_interpreter_that_is_not_3_9_is_never_taken(self):
        with tempfile.TemporaryDirectory() as tmp:
            other = self.script(tmp, "other", "3.12")
            self.assertEqual(self.lookup(other, other), sys.executable if sys.version_info[:2] == (3, 9) else "")

    def test_an_interpreter_that_prints_3_9_but_exits_1_is_never_taken(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fail39"
            path.write_text("#!/bin/sh\necho 3.9\nexit 1\n", encoding="utf-8")
            path.chmod(path.stat().st_mode | stat.S_IXUSR)
            self.assertEqual(self.lookup(str(path), str(path)), sys.executable if sys.version_info[:2] == (3, 9) else "")

    def test_this_python_counts_when_it_is_3_9_and_never_when_it_is_not(self):
        self.assertEqual(self.lookup(None, None), sys.executable if sys.version_info[:2] == (3, 9) else "")

    def compile_without_39(self, files):
        """check 5 with no Python 3.9 on the box, over `files` ({name: source})."""
        with tempfile.TemporaryDirectory() as tmp:
            for name, text in files.items():
                (Path(tmp) / name).write_text(text, encoding="utf-8")
            listing = "\0".join(files) + "\0"
            with Swap(python39=lambda: "", ROOT=Path(tmp), git=lambda *a: listing, run=no_run):
                return pre_ci.PreCi("", "", "").compile39()

    def test_without_a_3_9_a_file_the_grammar_switch_refuses_is_a_fail_naming_the_file_and_line(self):
        check = self.compile_without_39({"ok.py": "x = 1\n", "bad.py": "x = 1\nmatch x:\n    case 1:\n        pass\n"})
        self.assertEqual((check["result"], check["exit"]), ("fail", 1))
        self.assertRegex(check["tail"], r"^bad\.py: line \d+: ")
        self.assertNotIn("ok.py", check["tail"])
        self.assertEqual(check["files"], 2)

    def test_without_a_3_9_clean_files_are_not_checked_and_the_record_counts_them(self):
        check = self.compile_without_39({"a.py": "x = 1\n", "b.py": "y = 2\n"})
        self.assertEqual((check["result"], check["exit"], check["files"]), ("not checked", None, 2))
        self.assertIn("2 files pass the grammar switch only", check["tail"])
        self.assertIn("grammar switch", check["interpreter"])

    def test_cannot_parse_39_lists_files_in_name_order_with_the_line(self):
        bad = pre_ci.cannot_parse_39({"b.py": b"match 1:\n    case 1:\n        pass\n", "a.py": b"x = (\n", "c.py": b"x = 1\n"})
        self.assertEqual([p for p, _ in bad], ["a.py", "b.py"])
        self.assertRegex(bad[1][1], r"^line \d+: ")

    def test_with_a_real_3_9_the_files_go_to_the_probe_on_stdin_and_the_record_names_it(self):
        calls = []

        def fake_run(argv, stdin=None):
            calls.append((argv, stdin))
            return 0, "", 0.2
        with Swap(python39=lambda: "/x/python3.9", run=fake_run, git=lambda *a: "a.py\0b/c.py\0"):
            check = pre_ci.PreCi("", "", "").compile39()
        self.assertEqual(calls, [(["/x/python3.9", "-c", pre_ci.PY39_PROBE], "a.py\0b/c.py")])
        self.assertEqual((check["result"], check["files"], check["interpreter"]), ("pass", 2, "python3.9"))
        self.assertEqual(check["tail"], "2 files compile")
        self.assertEqual(check["command"], "/x/python3.9 -c <compile every tracked .py file>")

    def test_with_a_real_3_9_a_probe_that_exits_1_is_a_fail_with_its_output(self):
        with Swap(python39=lambda: "/x/python3.9", run=lambda argv, stdin=None: (1, "a.py: line 3: invalid syntax", 0.2),
                  git=lambda *a: "a.py\0"):
            check = pre_ci.PreCi("", "", "").compile39()
        self.assertEqual((check["result"], check["exit"]), ("fail", 1))
        self.assertIn("a.py: line 3: invalid syntax", check["tail"])

    def test_the_probe_reports_a_file_it_cannot_compile_and_exits_1_and_exits_0_on_clean_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            good, bad = Path(tmp) / "good.py", Path(tmp) / "bad.py"
            good.write_text("x = 1\n", encoding="utf-8")
            bad.write_text("x = (\n", encoding="utf-8")
            code, out, _ = pre_ci.run([sys.executable, "-c", pre_ci.PY39_PROBE], stdin=str(good) + "\0")
            self.assertEqual((code, out), (0, ""))
            code, out, _ = pre_ci.run([sys.executable, "-c", pre_ci.PY39_PROBE], stdin="%s\0%s\0" % (good, bad))
            self.assertEqual(code, 1)
            self.assertIn("%s: line 1:" % bad, out)
            self.assertNotIn(str(good), out)
            # a file with a null byte makes the parser raise ValueError (below Python 3.12) or SyntaxError (3.12 and up);
            # the probe reports either one instead of crashing
            bad.write_bytes(b"x = 1\0\n")
            code, out, _ = pre_ci.run([sys.executable, "-c", pre_ci.PY39_PROBE], stdin=str(bad) + "\0")
            self.assertEqual(code, 1)
            self.assertIn(str(bad), out)


class SmokeListTest(unittest.TestCase):
    """P12-07: the smoke list file and how it is read."""
    def test_smoke_names_keeps_one_clean_name_a_line_and_drops_comments_and_blank_lines(self):
        text = "# header\n\ntest_a\n   test_b   # why\ntest_c#glued\n  # indented comment\n\t\n"
        self.assertEqual(pre_ci.smoke_names(text), ["test_a", "test_b", "test_c"])

    def test_the_real_smoke_list_has_no_name_twice_and_each_name_matches_exactly_one_file(self):
        names = pre_ci.smoke_names((ROOT / "dev" / "tools" / "pre_ci_smoke.txt").read_text(encoding="utf-8"))
        self.assertEqual(len(names), len(set(names)))
        for n in names:
            holding = [p.name for p in (ROOT / "tests").glob("*.py") if n in p.name]
            self.assertEqual(holding, [n + ".py"], n)

    def test_the_smoke_list_is_the_file_beside_the_tool(self):
        self.assertEqual(pre_ci.SMOKE, ROOT / "dev" / "tools" / "pre_ci_smoke.txt")
        self.assertTrue(pre_ci.SMOKE.is_file())

    def test_a_failing_smoke_run_fails_the_check_and_a_passing_one_passes_with_the_runner_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "smoke.txt"
            path.write_text("test_a\n", encoding="utf-8")
            with Swap(SMOKE=path, run=lambda argv, stdin=None: (1, "FAILED test_a\n", 0.1)):
                check = pre_ci.PreCi("", "", "").smoke()
            self.assertEqual((check["n"], check["result"], check["exit"]), (6, "fail", 1))
            with Swap(SMOKE=path, run=lambda argv, stdin=None: (0, "pass, 1 tests in 0.1 s\n", 0.1)):
                check = pre_ci.PreCi("", "", "").smoke()
            self.assertEqual((check["result"], check["command"]), ("pass", "%s dev/run_tests.py test_a" % sys.executable))


class StartTest(unittest.TestCase):
    """P12-02: how the run starts, what it asks git for and how it reads the size of the change."""
    def test_size_of_reads_files_insertions_and_deletions_each_alone(self):
        self.assertEqual(pre_ci.size_of(" 3 files changed, 10 insertions(+), 4 deletions(-)"), {"files": 3, "additions": 10, "deletions": 4})
        self.assertEqual(pre_ci.size_of(" 1 file changed, 2 insertions(+)"), {"files": 1, "additions": 2, "deletions": 0})
        self.assertEqual(pre_ci.size_of(" 1 file changed, 1 insertion(+), 1 deletion(-)"), {"files": 1, "additions": 1, "deletions": 1})
        self.assertEqual(pre_ci.size_of(" 1 file changed, 7 deletions(-)"), {"files": 1, "additions": 0, "deletions": 7})
        self.assertEqual(pre_ci.size_of(" 1 file changed, 10insertions(+)"), {"files": 1, "additions": 0, "deletions": 0})
        self.assertEqual(pre_ci.size_of(""), {"files": 0, "additions": 0, "deletions": 0})

    def test_the_changed_files_are_asked_without_renames_between_the_merge_base_and_the_head(self):
        calls = []

        def spy(*args):
            calls.append(args)
            return fake_git(*args)
        out = io.StringIO()
        with tempfile.TemporaryDirectory() as tmp:
            ticket = Path(tmp) / "ticket.json"
            ticket.write_text(json.dumps(TICKET), encoding="utf-8")
            with Swap(git=spy, time=FakeClock(1), run=no_run), unittest.mock.patch.object(pre_ci.PreCi, "run_all", lambda self, t, c: None), \
                    contextlib.redirect_stdout(out):
                pre_ci.main(["--ticket", str(ticket), "--record", str(Path(tmp) / "rec"), "--base", "origin/x"])
        self.assertIn(("merge-base", "origin/x", "abc123"), calls)
        self.assertIn(("diff", "--name-only", "--no-renames", "-z", "base123", "abc123"), calls)
        self.assertIn(("diff", "--shortstat", "base123", "abc123"), calls)

    def test_uncommitted_work_exits_2_before_any_check_and_writes_no_record(self):
        out = io.StringIO()
        with tempfile.TemporaryDirectory() as tmp:
            ticket = Path(tmp) / "ticket.json"
            ticket.write_text(json.dumps(TICKET), encoding="utf-8")
            ran = []
            with Swap(git=lambda *a: " M x.py\n" if a[0] == "status" else fake_git(*a), run=no_run), \
                    unittest.mock.patch.object(pre_ci.PreCi, "run_all", lambda self, t, c: ran.append(1)), \
                    contextlib.redirect_stdout(out):
                code = pre_ci.main(["--ticket", str(ticket), "--record", str(Path(tmp) / "rec")])
            self.assertFalse((Path(tmp) / "rec").exists())
        self.assertEqual((code, ran), (2, []))
        self.assertIn("pre-CI did not start: there is uncommitted work. The record names a head, so commit first.", out.getvalue())

    def test_a_missing_or_bad_ticket_file_exits_2_with_did_not_start(self):
        out = io.StringIO()
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.json"
            bad.write_text("not json", encoding="utf-8")
            for ticket in (Path(tmp) / "missing.json", bad):
                out.truncate(0)
                out.seek(0)
                with Swap(git=fake_git, run=no_run), contextlib.redirect_stdout(out):
                    code = pre_ci.main(["--ticket", str(ticket), "--record", str(Path(tmp) / "rec")])
                self.assertEqual(code, 2, ticket.name)
                self.assertIn("pre-CI did not start: ", out.getvalue())
            self.assertFalse((Path(tmp) / "rec").exists())

    def test_the_compile_flag_runs_check_5_alone_and_exits_0_only_on_a_pass(self):
        for result, code in (("pass", 0), ("fail", 1), ("not checked", 1)):
            with unittest.mock.patch.object(pre_ci.PreCi, "compile39", lambda self, r=result: {"result": r}):
                self.assertEqual(pre_ci.main(["--compile39"]), code, result)

    def test_check_5_asks_git_for_the_tracked_py_files(self):
        calls = []
        with Swap(python39=lambda: "", ROOT=Path("/nonexistent"), git=lambda *a: calls.append(a) or "", run=no_run):
            pre_ci.PreCi("", "", "").compile39()
        self.assertEqual(calls, [("ls-files", "-z", "--", "*.py")])

    def test_a_command_that_cannot_start_returns_no_exit_code(self):
        code, out, secs = pre_ci.run(["/nonexistent/clark-tool"])
        self.assertIsNone(code)
        self.assertEqual(out, "could not start: FileNotFoundError")

    def test_the_run_returns_the_exit_code_and_both_outputs_and_feeds_stdin(self):
        code, out, secs = pre_ci.run([sys.executable, "-c", "import sys; print(sys.stdin.read()); print('e', file=sys.stderr); sys.exit(3)"],
                                     stdin="in")
        self.assertEqual(code, 3)
        self.assertEqual(out, "in\ne\n")

    def test_a_run_exactly_at_the_target_is_not_over_it(self):
        _, _, doc, _ = main_with(lambda self, t, c: None, seconds=pre_ci.TARGET_SECONDS)
        self.assertIs(doc["over_target"], False)
        _, _, doc, _ = main_with(lambda self, t, c: None, seconds=pre_ci.TARGET_SECONDS + 1)
        self.assertIs(doc["over_target"], True)
        self.assertEqual(doc["result"], "pass")

    def test_an_empty_named_tests_list_fails_check_3_and_runs_nothing(self):
        ran = []
        with Swap(run=lambda *a, **k: ran.append(a) or (0, "", 0.0)):
            check = pre_ci.PreCi("", "", "").named([])
        self.assertEqual((check["result"], check["exit"], ran), ("fail", 1, []))

    def test_an_empty_or_missing_smoke_list_is_not_checked_and_runs_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            for text in ("", "# only a comment\n"):
                path = Path(tmp) / "smoke.txt"
                path.write_text(text, encoding="utf-8")
                ran = []
                with Swap(SMOKE=path, run=lambda *a, **k: ran.append(a) or (0, "", 0.0)):
                    check = pre_ci.PreCi("", "", "").smoke()
                self.assertEqual((check["result"], check["exit"], ran), ("not checked", None, []))
            ran = []
            with Swap(SMOKE=Path(tmp) / "missing.txt", run=lambda *a, **k: ran.append(a) or (0, "", 0.0)):
                check = pre_ci.PreCi("", "", "").smoke()
            self.assertEqual((check["result"], ran), ("not checked", []))

    def test_a_run_with_an_empty_smoke_list_exits_1_and_records_a_fail_with_smoke_not_checked(self):
        with tempfile.TemporaryDirectory() as tmp:
            empty = Path(tmp) / "smoke.txt"
            empty.write_text("", encoding="utf-8")
            with Swap(SMOKE=empty, run=no_run):
                code, _, doc, log = main_with(lambda self, t, c: self.smoke())
        self.assertEqual((code, doc["result"]), (1, "fail"))
        self.assertEqual({c["name"]: c["result"] for c in doc["checks"]}, {"smoke suite": "not checked"})
        self.assertEqual(json.loads(log[0])["checks"], {"smoke suite": "not checked"})


class Flushed(io.StringIO):
    """A stream that counts flush() calls."""
    flushes = 0

    def flush(self):
        self.flushes += 1
        super().flush()


def stub(tmp, name, body):
    path = Path(tmp) / name
    path.write_text("#!/bin/sh\n" + body, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return str(path)


def full_git(record_dir=""):
    """A git stand-in with a real-looking answer for every question main() asks."""
    def g(*args):
        if args[0] == "rev-parse" and "--git-common-dir" in args:
            return record_dir + "\n"
        return {"rev-parse": "0123456789abcdef\n", "merge-base": "fedcba9876543210\n", "status": "",
                "diff": "a.py\0b.py\0" if "--name-only" in args else " 2 files changed, 5 insertions(+), 1 deletion(-)\n"}.get(args[0], "")
    return g


class FieldsTest(unittest.TestCase):
    """The names, numbers and texts of each check's record, the helper functions and the files main() writes."""
    def test_the_runner_constant_is_the_test_runner(self):
        self.assertEqual(pre_ci.RUNNER, ROOT / "dev" / "run_tests.py")

    def test_dubai_now_is_day_month_year_and_clock_at_plus_4(self):
        from datetime import datetime, timedelta, timezone
        text = pre_ci.dubai_now()
        self.assertRegex(text, r"^\d\d-\d\d-\d{4} \d\d:\d\d:\d\d \+04$")
        then = datetime.strptime(text[:-4], "%d-%m-%Y %H:%M:%S")
        now = datetime.now(timezone(timedelta(hours=4))).replace(tzinfo=None)
        self.assertLess(abs((now - then).total_seconds()), 60)

    def test_git_returns_the_text_of_the_command_and_a_failing_command_exits_2_saying_so(self):
        self.assertIsInstance(pre_ci.git("rev-parse", "--show-toplevel"), str)
        self.assertTrue(pre_ci.git("rev-parse", "--show-toplevel").strip())
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            with self.assertRaises(SystemExit) as caught:
                pre_ci.git("no-such-git-command-xyz")
        self.assertEqual(caught.exception.code, 2)
        self.assertRegex(out.getvalue(), r"^pre-CI did not start: git no-such-git-command-xyz failed: \S")

    def test_run_gives_seconds_that_are_the_time_the_command_took(self):
        _, _, secs = pre_ci.run([sys.executable, "-c", "pass"])
        self.assertTrue(0 <= secs < 60, secs)
        _, _, secs = pre_ci.run(["/nonexistent/clark-tool"])
        self.assertTrue(0 <= secs < 60, secs)

    def test_cannot_parse_39_parses_with_the_3_9_grammar_and_words_the_line(self):
        seen = []
        real = pre_ci.ast.parse
        with unittest.mock.patch.object(pre_ci.ast, "parse", lambda *a, **k: seen.append(k) or real(*a, **k)):
            self.assertEqual(pre_ci.cannot_parse_39({"a.py": b"x = 1\n"}), [])
        self.assertEqual(seen[0]["feature_version"], (3, 9))
        self.assertEqual(seen[0]["filename"], "a.py")
        with self.assertRaises(SyntaxError) as caught:
            real("x = (\n", feature_version=(3, 9))
        self.assertEqual(pre_ci.cannot_parse_39({"a.py": b"x = (\n"}),
                         [("a.py", "line %s: %s" % (caught.exception.lineno, caught.exception.msg))])

        def boom(*a, **k):
            raise ValueError("boom")
        with unittest.mock.patch.object(pre_ci.ast, "parse", boom):
            self.assertEqual(pre_ci.cannot_parse_39({"a.py": b""}), [("a.py", "line ?: boom")])

    def test_the_probe_is_asked_what_version_it_is_with_the_version_print(self):
        calls = []
        with Swap(run=lambda argv, stdin=None: calls.append(argv) or (0, "3.9\n", 0.0)):
            with unittest.mock.patch.dict(os.environ, {"CLARK_PY39": "/x/py"}):
                self.assertEqual(pre_ci.python39(), "/x/py")
        self.assertEqual(calls, [["/x/py", "-c", "import sys; print('%d.%d' % sys.version_info[:2])"]])

    def test_the_lookup_asks_the_path_for_python3_9_by_that_name(self):
        asked = []
        with unittest.mock.patch.dict(os.environ, {}), unittest.mock.patch.object(pre_ci.shutil, "which", lambda n: asked.append(n)):
            os.environ.pop("CLARK_PY39", None)
            pre_ci.python39()
        self.assertEqual(asked, ["python3.9"])

    def test_this_python_is_taken_exactly_when_its_version_is_3_9(self):
        with tempfile.TemporaryDirectory() as tmp:
            ok = stub(tmp, "ok39", "echo 3.9\n")
            for version, want in (((3, 9, 1), ok), ((3, 10, 0), ""), ((3, 8, 5), ""), ((3, 9), ok)):
                with unittest.mock.patch.object(pre_ci.sys, "version_info", version), unittest.mock.patch.object(pre_ci.sys, "executable", ok):
                    self.assertEqual(self.lookup_none(), want, version)

    def lookup_none(self):
        with unittest.mock.patch.dict(os.environ, {}), unittest.mock.patch.object(pre_ci.shutil, "which", lambda n: None):
            os.environ.pop("CLARK_PY39", None)
            return pre_ci.python39()

    def test_the_progress_and_tail_lines_are_flushed(self):
        out = Flushed()
        with contextlib.redirect_stdout(out):
            pre_ci.PreCi("", "", "").add(1, "scan", ["x"], 1, "bad", 0.0)
        self.assertEqual(out.flushes, 2)

    def test_the_named_check_is_check_3_named_tests_with_its_fields(self):
        check = pre_ci.PreCi("", "", "").named([])
        self.assertEqual((check["n"], check["name"], check["tail"], check["seconds"]), (3, "named tests", "the ticket names no test", 0.0))
        self.assertEqual(check["command"], "%s dev/run_tests.py" % sys.executable)
        with Swap(run=lambda argv, stdin=None: (0, "pass, 2 tests in 0.1 s\n", 0.1)):
            check = pre_ci.PreCi("", "", "").named(["test_a"])
        self.assertEqual((check["n"], check["name"], check["tail"], check["seconds"]), (3, "named tests", "pass, 2 tests in 0.1 s", 0.1))

    def test_the_affected_check_is_check_4_affected_tests_with_its_fields_on_every_path(self):
        t = AffectedTest()
        check, _ = t.run_affected((1, "boom\n", 0.1), ["x.py"])
        self.assertEqual((check["n"], check["name"], check["tail"]), (4, "affected tests", "boom"))
        check, _ = t.run_affected((0, "nothing\n", 0.1), ["x.py"])
        self.assertEqual((check["n"], check["name"], check["tail"]), (4, "affected tests", "nothing\nno test file is affected"))
        names = ["test_f%02d.py" % i for i in range(41)]
        check, _ = t.run_affected((0, "".join(n + "\n" for n in names), 0.1), ["x.py"], {n: "" for n in names})
        self.assertEqual((check["n"], check["name"]), (4, "affected tests"))
        check, _ = t.run_affected((0, "test_a.py\n", 0.1), ["x.py"])
        self.assertEqual((check["n"], check["name"], check["tail"]), (4, "affected tests", "pass, 3 tests in 0.1 s"))
        self.assertAlmostEqual(check["seconds"], 0.6, places=1)

    def test_a_test_file_with_bytes_that_are_not_utf8_is_still_read_for_the_changed_name(self):
        names = ["test_f%02d.py" % i for i in range(41)]
        calls = []

        def fake_run(argv, stdin=None):
            calls.append(argv)
            return (0, "".join(n + "\n" for n in names), 0.1) if "--list" in argv else (0, "pass, 1 tests in 0.1 s\n", 0.1)
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "tests").mkdir()
            for n in names:
                (Path(tmp) / "tests" / n).write_bytes(b"")
            (Path(tmp) / "tests" / "test_f03.py").write_bytes(b"\xff\xfe thing.py \xff\n")
            with Swap(run=fake_run, ROOT=Path(tmp)):
                check = pre_ci.PreCi("", "BASE", "").affected(["src/thing.py"])
        self.assertEqual(calls[1], [sys.executable, "dev/run_tests.py", "test_f03.py"])
        self.assertEqual(check["files"], 1)

    def test_check_5_with_a_real_3_9_is_check_5_python_3_9_compile_and_the_fallback_names_its_command(self):
        with Swap(python39=lambda: "/x/python3.9", run=lambda argv, stdin=None: (0, "", 0.2), git=lambda *a: "a.py\0"):
            check = pre_ci.PreCi("", "", "").compile39()
        self.assertEqual((check["n"], check["name"]), (5, "Python 3.9 compile"))
        t = Python39Test()
        check = t.compile_without_39({"a.py": "x = 1\n"})
        self.assertEqual((check["n"], check["name"], check["command"]), (5, "Python 3.9 compile", "ast.parse(feature_version=(3, 9))"))
        self.assertEqual(check["tail"], "no Python 3.9 on this box (set CLARK_PY39 or put python3.9 on the PATH): "
                                        "1 files pass the grammar switch only, which is not a compile")
        self.assertEqual(check["interpreter"], "this Python with the 3.9 grammar switch (LIMIT: misses some newer syntax)")
        self.assertTrue(0 <= check["seconds"] < 60, check["seconds"])
        check = t.compile_without_39({"a.py": "x = (\n", "b.py": "y = (\n"})
        self.assertEqual(check["tail"].count("\n"), 1)
        self.assertRegex(check["tail"], r"^a\.py: line 1: .*\nb\.py: line 1: ")

    def test_the_smoke_check_is_check_6_smoke_suite_with_its_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "smoke.txt"
            path.write_text("", encoding="utf-8")
            with Swap(SMOKE=path, run=no_run):
                check = pre_ci.PreCi("", "", "").smoke()
            self.assertEqual((check["n"], check["name"], check["tail"], check["seconds"]),
                             (6, "smoke suite", "dev/tools/pre_ci_smoke.txt lists no test file", 0.0))
            path.write_text("test_a\n", encoding="utf-8")
            with Swap(SMOKE=path, run=lambda argv, stdin=None: (0, "pass, 1 tests in 0.1 s\n", 0.1)):
                check = pre_ci.PreCi("", "", "").smoke()
            self.assertEqual((check["n"], check["name"], check["tail"], check["seconds"]), (6, "smoke suite", "pass, 1 tests in 0.1 s", 0.1))

    def main_in(self, tmp, argv, git=None, run_all=None, seconds=1.26, content=TICKET, clock=None):
        out = Flushed()
        ticket = Path(tmp) / "ticket.json"
        ticket.write_text(json.dumps(content), encoding="utf-8")
        run_all = run_all or (lambda self, t, c: self.add(1, "scan", ["x"], 0, "", 0.0))
        with Swap(git=git or full_git(str(Path(tmp) / "gitdir")), time=clock or FakeClock(seconds), run=no_run), \
                unittest.mock.patch.object(pre_ci.PreCi, "run_all", run_all), contextlib.redirect_stdout(out):
            code = pre_ci.main(["--ticket", str(ticket)] + argv)
        return code, out

    def test_a_passing_run_exits_0_and_writes_a_record_with_every_field_and_the_lines_printed(self):
        with tempfile.TemporaryDirectory() as tmp:
            rec = Path(tmp) / "deep" / "rec"
            code, out = self.main_in(tmp, ["--record", str(rec)])
            self.assertEqual(code, 0)
            text = (rec / "0123456789abcdef.json").read_text(encoding="utf-8")
            self.assertTrue(text.startswith('{\n "head": "0123456789abcdef"'))
            self.assertTrue(text.endswith("}\n"))
            doc = json.loads(text)
            self.assertEqual(sorted(doc), ["base", "checks", "finished", "head", "over_target", "result", "seconds", "size", "started", "ticket"])
            self.assertEqual((doc["result"], doc["base"], doc["ticket"], doc["seconds"]), ("pass", "fedcba9876543210", "9001", 1.3))
            self.assertEqual(doc["size"], {"files": 2, "additions": 5, "deletions": 1})
            self.assertRegex(doc["started"], r"^\d\d-\d\d-\d{4} \d\d:\d\d:\d\d \+04$")
            self.assertRegex(doc["finished"], r"^\d\d-\d\d-\d{4} \d\d:\d\d:\d\d \+04$")
            lines = out.getvalue().splitlines()
            self.assertEqual(lines[0], "pre-CI on 01234567 (base fedcba98, ticket 9001, 2 files, +5 -1)")
            self.assertEqual(lines[-2:], ["record: %s" % (rec / "0123456789abcdef.json"), "PRE-CI pass 0123456789abcdef"])
            self.assertEqual(out.flushes, 2)

    def test_the_seconds_are_the_end_clock_minus_the_start_clock(self):
        class Clock:
            reads = 0

            def time(self):
                self.reads += 1
                return 1000.0 if self.reads == 1 else 1001.26
        with tempfile.TemporaryDirectory() as tmp:
            self.main_in(tmp, ["--record", str(Path(tmp) / "r")], clock=Clock())
            doc = json.loads((Path(tmp) / "r" / "0123456789abcdef.json").read_text(encoding="utf-8"))
        self.assertEqual(doc["seconds"], 1.3)

    def test_a_ticket_without_a_number_prints_not_given_on_the_start_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, out = self.main_in(tmp, ["--record", str(Path(tmp) / "r")], content={"files": [], "named_tests": []})
        self.assertEqual(out.getvalue().splitlines()[0], "pre-CI on 01234567 (base fedcba98, ticket not given, 2 files, +5 -1)")

    def test_the_log_gets_one_line_a_run_and_the_record_folder_is_made_when_it_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            rec = Path(tmp) / "rec"
            self.main_in(tmp, ["--record", str(rec)])
            self.main_in(tmp, ["--record", str(rec)])
            log = (rec / "log.jsonl").read_text(encoding="utf-8")
            self.assertEqual(len(log.splitlines()), 2)
            self.assertTrue(log.endswith("}\n"))
            self.assertEqual(log.count("\n"), 2)

    def test_without_record_the_folder_is_pre_ci_in_the_git_common_dir_and_the_base_defaults_to_origin_main(self):
        calls = []
        inner = full_git()

        def spy(*args):
            calls.append(args)
            return inner(*args) if "--git-common-dir" not in args else str(Path(tmp) / "common") + "\n"
        with tempfile.TemporaryDirectory() as tmp:
            self.main_in(tmp, [], git=spy)
            self.assertTrue((Path(tmp) / "common" / "pre-ci" / "0123456789abcdef.json").is_file())
        self.assertIn(("rev-parse", "--path-format=absolute", "--git-common-dir"), calls)
        self.assertIn(("merge-base", "origin/main", "0123456789abcdef"), calls)
        self.assertIn(("status", "--porcelain"), calls)
        self.assertIn(("rev-parse", "HEAD"), calls)

    def test_run_all_gets_the_ticket_and_the_changed_files_split_on_nul(self):
        got = []
        with tempfile.TemporaryDirectory() as tmp:
            self.main_in(tmp, ["--record", str(Path(tmp) / "r")], run_all=lambda self, t, c: got.append((t, c)))
        self.assertEqual(got[0][1], ["a.py", "b.py"])
        self.assertEqual(got[0][0]["named_tests"], TICKET["named_tests"])

    def test_a_run_with_a_failing_check_exits_1_and_prints_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, out = self.main_in(tmp, ["--record", str(Path(tmp) / "r")], run_all=lambda self, t, c: self.add(1, "scan", ["x"], 1, "", 0.0))
        self.assertEqual(code, 1)
        self.assertIn("PRE-CI FAIL 0123456789abcdef", out.getvalue())

    def test_the_note_line_is_the_seconds_to_the_whole_number(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, out = self.main_in(tmp, ["--record", str(Path(tmp) / "r")], seconds=300.6)
        self.assertIn("note: 301 s, over the 300 s target (logged, never blocks)\n", out.getvalue())

    def test_main_reads_sys_argv_when_it_is_given_none(self):
        with unittest.mock.patch.object(sys, "argv", ["pre_ci.py", "--compile39"]), \
                unittest.mock.patch.object(pre_ci.PreCi, "compile39", lambda self: {"result": "pass"}):
            self.assertEqual(pre_ci.main(), 0)

    def test_help_and_usage_texts(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), self.assertRaises(SystemExit) as caught:
            pre_ci.main(["--help"])
        self.assertEqual(caught.exception.code, 0)
        flat = " ".join(out.getvalue().split())
        for text in (pre_ci.__doc__.split("\n")[0], "the ticket file: {ticket, files, named_tests}",
                     "only check 5, the Python 3.9 compile check (CI runs this on 3.9)", "--base BASE", "--record DIR"):
            self.assertIn(" ".join(text.split()), flat)
        err = io.StringIO()
        with contextlib.redirect_stderr(err), self.assertRaises(SystemExit) as caught:
            pre_ci.main([])
        self.assertEqual(caught.exception.code, 2)
        self.assertIn("--ticket is needed (or --compile39 for the compile check alone)", err.getvalue())

    def test_the_script_runs_main_when_started_as_a_file(self):
        r = subprocess.run([sys.executable, str(ROOT / "dev" / "tools" / "pre_ci.py"), "--help"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0)
        self.assertIn("usage:", r.stdout)


if __name__ == "__main__":
    unittest.main()
