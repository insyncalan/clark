"""Row 1492: the Claude command provider says which kind a failure was (src/clark/ask_claude.py, guarded).
failure_reason and reasoned pick "expired", "network" or nothing; a check that ran out of time is "slow", not "version_flags".
Nothing here runs the real `claude`: the run function is replaced by a fixed answer.

Run: python3 dev/run_tests.py test_ask_claude_reasons_1492
"""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _paths import SRC  # noqa: F401

from clark import ask, ask_claude as ac, platform


class FailureReason(unittest.TestCase):
    def test_expired_words(self):
        for said in (b"Error: token expired", b"Invalid API key", b"Please run /login", b"Not logged in", b"HTTP 401", b"Unauthorized"):
            self.assertEqual(ac.failure_reason(said), "expired", said)

    def test_network_words(self):
        for said in (b"getaddrinfo ENOTFOUND api", b"ECONNREFUSED", b"fetch failed", b"Could not resolve host", b"connection reset", b"offline"):
            self.assertEqual(ac.failure_reason(said), "network", said)

    def test_expired_wins_over_network(self):
        self.assertEqual(ac.failure_reason(b"network error: not logged in"), "expired")

    def test_unknown_and_empty_give_nothing(self):
        self.assertEqual(ac.failure_reason(b"something odd"), "")
        self.assertEqual(ac.failure_reason(b""), "")

    def test_not_bytes_gives_nothing(self):
        self.assertEqual(ac.failure_reason(None), "")

    def test_bad_utf8_is_read(self):
        self.assertEqual(ac.failure_reason(b"\xff\xfe ECONNRESET"), "network")


class Reasoned(unittest.TestCase):
    def test_with_a_reason(self):
        got = ac.reasoned("words", "expired")
        self.assertIsInstance(got, ac.Reasoned)
        self.assertEqual((got.reason, got.message), ("expired", "words"))

    def test_without_a_reason_is_a_plain_failure(self):
        got = ac.reasoned("words", "")
        self.assertIs(type(got), ask.Failure)
        self.assertEqual(got.message, "words")


class TimedOut(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.cmd = Path(self.dir.name) / "claude"
        self.cmd.write_text("x", encoding="utf-8")
        self.p = ac.ClaudeCommand(places=(str(self.cmd),), env={}, roots=(self.dir.name,))

    def command(self, results):
        with mock.patch.object(platform, "container_mode", return_value=False), \
             mock.patch.object(platform, "system", return_value=platform.MAC), \
             mock.patch.object(ac, "find_checked", return_value=(self.cmd, None, None)), \
             mock.patch.object(ac, "run", side_effect=results):
            return self.p.command()

    def test_version_check_out_of_time_is_slow_and_not_remembered(self):
        got = self.command([("slow", b"", None)])
        self.assertEqual(got, (None, ac.CANT_USE))
        self.assertEqual(self.p.failed, "slow")
        self.assertEqual(self.p.checked, {})

    def test_help_check_out_of_time_is_slow(self):
        self.command([("ok", b"2.1.0\n", 0), ("slow", b"", None)])
        self.assertEqual(self.p.failed, "slow")
        self.assertEqual(self.p.checked, {})

    def test_wrong_version_text_is_version_flags_and_remembered(self):
        self.command([("ok", b"not a version", 0)])
        self.assertEqual(self.p.failed, "version_flags")
        self.assertEqual(list(self.p.checked.values()), [False])

    def test_help_failing_without_timeout_is_version_flags(self):
        self.command([("ok", b"2.1.0\n", 0), ("failed", b"", 1)])
        self.assertEqual(self.p.failed, "version_flags")

    def test_login_check_out_of_time_is_slow(self):
        with mock.patch.object(ac, "run", return_value=("slow", b"", None)):
            why = self.p.login_problem(self.cmd)
        self.assertEqual(why, ac.CANT_USE)
        self.assertEqual(self.p.failed, "slow")

    def test_login_unreadable_is_not_slow(self):
        with mock.patch.object(ac, "run", return_value=("ok", b"not json", 0)):
            self.p.login_problem(self.cmd)
        self.assertEqual(self.p.failed, "login_unreadable")


if __name__ == "__main__":
    unittest.main()
