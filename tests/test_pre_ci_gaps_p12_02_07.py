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
        seen = []

        def record(name, code):
            def f(self, *a, **k):
                seen.append(name)
                return self.add(1, name, ["x"], code, "", 0.0)
            return f
        with Swap(run=no_run), unittest.mock.patch.object(pre_ci.PreCi, "tool", lambda self, n, name, script, *a: seen.append(name) or self.add(n, name, ["x"], 1, "", 0.0)), \
                unittest.mock.patch.object(pre_ci.PreCi, "named", record("named", 0)), \
                unittest.mock.patch.object(pre_ci.PreCi, "affected", record("affected", 0)), \
                unittest.mock.patch.object(pre_ci.PreCi, "compile39", record("compile39", 0)), \
                unittest.mock.patch.object(pre_ci.PreCi, "smoke", record("smoke", 0)):
            pre_ci.PreCi("t.json", "base", "head").run_all({"named_tests": ["a"]}, [])
        self.assertEqual(seen, ["scan", "test honesty", "scope", "named", "affected", "compile39", "smoke"])

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
            # a file with a null byte raises ValueError, which the probe also reports instead of crashing
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
        self.assertEqual(pre_ci.size_of(" 1 file changed, 7 deletions(-)"), {"files": 1, "additions": 0, "deletions": 7})
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
        self.assertIn("commit first", out.getvalue())

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


if __name__ == "__main__":
    unittest.main()
