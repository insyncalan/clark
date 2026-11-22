"""Row 1492: the Codex command says a check that ran out of time was slow (src/clark/ai_codex.py, guarded), and an answer that failed says which kind it was.
Nothing here runs the real `codex`: the run functions are replaced by fixed answers.

Run: python3 dev/run_tests.py test_ai_codex_reasons_1492
"""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _paths import SRC  # noqa: F401

from clark import ai_codex as cx, ask, ask_claude, platform

VERSION_OK = b"codex-cli 0.166.1\n"
HELP_OK = b"--model --json\n"


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.cmd = Path(self.dir.name) / "codex"
        self.cmd.write_text("x", encoding="utf-8")
        self.p = cx.CodexCommand(places=(str(self.cmd),), env={}, roots=(self.dir.name,), walled=False)


class TimedOut(Base):
    def command(self, results):
        with mock.patch.object(platform, "container_mode", return_value=False), \
             mock.patch.object(platform, "system", return_value=platform.MAC), \
             mock.patch.object(ask_claude, "find_checked", return_value=(self.cmd, None, None)), \
             mock.patch.object(cx, "run", side_effect=results):
            return self.p.command()

    def test_version_check_out_of_time_is_slow_and_not_remembered(self):
        got = self.command([("slow", b"", None)])
        self.assertEqual(got[0], None)
        self.assertEqual(self.p.failed, "slow")
        self.assertEqual(self.p.checked, {})

    def test_help_check_out_of_time_is_slow(self):
        self.command([("ok", VERSION_OK, 0), ("slow", b"", None)])
        self.assertEqual(self.p.failed, "slow")
        self.assertEqual(self.p.checked, {})

    def test_a_version_that_is_not_read_is_version_flags_and_remembered(self):
        self.command([("ok", b"not a version", 0)])
        self.assertEqual(self.p.failed, "version_flags")
        self.assertEqual(list(self.p.checked.values()), [False])

    def test_help_failing_without_timeout_is_version_flags(self):
        self.command([("ok", VERSION_OK, 0), ("failed", b"", 1)])
        self.assertEqual(self.p.failed, "version_flags")
        self.assertEqual(list(self.p.checked.values()), [False])

    def test_a_version_not_tested_is_untested_not_slow(self):
        self.command([("ok", b"codex-cli 9.0.0\n", 0)])
        self.assertEqual(self.p.failed, "untested")


class Login(Base):
    def login(self, status, out=b"", code=None):
        with mock.patch.object(platform, "run_stoppable", return_value=(status, out, code)):
            return self.p.login_problem(self.cmd)

    def test_a_sign_in_check_out_of_time_is_slow(self):
        self.assertEqual(self.login("slow"), cx.CANT_USE)
        self.assertEqual(self.p.failed, "slow")

    def test_a_sign_in_check_that_gave_no_usable_answer_is_not_slow(self):
        self.assertEqual(self.login("too_much"), cx.CANT_USE)
        self.assertEqual(self.p.failed, "login_unreadable")

    def test_a_slow_check_is_forgotten_by_the_next_one(self):
        self.login("slow")
        self.assertIsNone(self.login("ok", cx.SIGNED_IN.encode("utf-8"), 0))
        self.assertIsNone(self.p.failed)
        self.login("ok", b"Not logged in", 1)
        self.assertEqual(self.p.failed, "no_login")


class Answer(Base):
    def answer(self, status, out):
        with mock.patch.object(cx, "run", return_value=(status, out, 0)):
            return self.p.answer(self.cmd, "q")

    def test_an_answer_that_failed_says_which_kind_it_was(self):
        for said, kind in ((b"getaddrinfo ENOTFOUND api", "network"), (b"token expired", "expired")):
            got = self.answer("ok", said)
            self.assertIsInstance(got, ask_claude.Reasoned)
            self.assertEqual((got.message, got.reason), (cx.NO_ANSWER, kind))

    def test_an_answer_that_failed_in_no_known_way_is_a_plain_failure(self):
        got = self.answer("ok", b"something odd")
        self.assertIs(type(got), ask.Failure)
        self.assertEqual(got.message, cx.NO_ANSWER)


if __name__ == "__main__":
    unittest.main()
