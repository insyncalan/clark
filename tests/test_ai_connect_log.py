"""Item 1100, R2: a Connect that fails writes WHICH check failed to the debug log, in fixed plain words, one line, nothing from the
command or the computer in it. Fake commands only; no real sign-in, no network.

Run: python3 dev/run_tests.py test_ai_connect_log
"""
import json
import logging
import os
import shutil
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _paths import SRC  # noqa: F401
import test_ask_claude as tac
from clark import ai_codex, ai_connect as ac, ai_providers, ask_claude, log as clog, platform, settings

TERMINAL = "clark.ai_connect"


class Capture:
    """Routes the ai_connect logger through the real log bridge into a real log folder, at the Debug level."""

    def __init__(self, test):
        self.dir = Path(tempfile.mkdtemp(prefix="clark-r2-"))
        test.addCleanup(shutil.rmtree, self.dir, True)
        self.log = clog.Log(self.dir / "logs", data=self.dir / "data")
        (self.dir / "data").mkdir()
        self.log.set_level(clog.DEBUG)
        self.handler = clog.Bridge(self.log)
        logger = logging.getLogger(TERMINAL)
        logger.addHandler(self.handler)
        prior = logger.level
        logger.setLevel(logging.DEBUG)
        test.addCleanup(logger.removeHandler, self.handler)
        test.addCleanup(logger.setLevel, prior)

    def lines(self):
        out = []
        for p in sorted((self.dir / "logs").glob("clark-*.log")):
            out += p.read_text(encoding="utf-8").splitlines()
        return out

    def connect_lines(self):
        return [x for x in self.lines() if "connect failed" in x]


class Base(tac.Fake):
    def setUp(self):
        super().setUp()
        self.cap = Capture(self)
        self.data = Path(tempfile.mkdtemp(prefix="clark-r2-data-"))
        self.addCleanup(shutil.rmtree, self.data, True)

    def connect(self, provider=None, name="claude"):
        provider = provider or ai_providers.ClaudeSubscription(self.provider)
        other = ai_providers.ChatGPTSubscription(ai_codex.CodexCommand(places=("/nowhere/codex",), walled=False, roots=(str(self.d),)))
        svc = ac.AiConnect(self.data, provider, other) if name == "claude" else ac.AiConnect(self.data, ai_providers.ClaudeSubscription(self.provider), provider)
        return svc.connect({"provider": name})

    def one(self, words):
        got = self.cap.connect_lines()
        self.assertEqual(len(got), 1, got)
        self.assertIn(words, got[0])
        return got[0]


class ClaudeChecks(Base):
    def test_command_not_found(self):
        self.cmd.unlink()
        status, body = self.connect()
        self.assertEqual(status, 409)
        self.one("the command was not found")

    def test_not_a_mac_program_alone(self):
        with mock.patch.object(ask_claude, "native_reason", return_value="not_mac"), mock.patch.object(ask_claude, "native_problem", return_value=True):
            self.connect()
        self.one("the command is not a Mac program")

    def test_wrong_owner_or_writable_by_others(self):
        with mock.patch.object(ask_claude, "native_reason", return_value="owner"), mock.patch.object(ask_claude, "native_problem", return_value=True):
            self.connect()
        self.one("wrong owner or can be changed by others")

    def test_writable_by_others_for_real(self):
        self.cmd.chmod(0o777)
        with mock.patch.object(ask_claude, "native_problem", wraps=lambda real, roots: True if ask_claude.native_reason(real, roots) else None):
            self.connect()
        self.one("wrong owner or can be changed by others")

    def test_version_or_flags_unsupported(self):
        self.mode("badversion")
        self.connect()
        self.one("version or options are not supported")

    def test_not_signed_in_with_claude_ai(self):
        self.put("auth", json.dumps({"loggedIn": False, "authMethod": "none"}))
        self.connect()
        self.one("not signed in with the account clark can use")

    def test_signed_in_with_an_api_key(self):
        self.put("auth", json.dumps({"loggedIn": True, "authMethod": "api_key"}))
        self.connect()
        self.one("signed in with an API key")

    def test_running_in_a_container(self):
        with mock.patch.object(platform, "system", return_value="linux"), mock.patch.object(platform, "container_mode", return_value=True):
            self.connect()
        self.one("running in a container")

    def test_not_a_mac_and_not_a_container(self):
        with mock.patch.object(platform, "system", return_value="linux"), mock.patch.object(platform, "container_mode", return_value=False):
            self.connect()
        self.one("this computer is not a Mac")

    def test_a_successful_connect_writes_no_failure_line(self):
        status, _body = self.connect()
        self.assertEqual(status, 200)
        self.assertEqual(self.cap.connect_lines(), [])

    def test_normal_level_writes_nothing(self):
        self.cap.log.set_level(clog.NORMAL)
        self.cmd.unlink()
        self.connect()
        self.assertEqual(self.cap.connect_lines(), [])


class Hostile(Base):
    def test_a_path_with_newlines_and_a_long_path_never_reaches_the_log(self):
        evil = str(self.d / "bin" / ("x\nINJECTED line\n" + "y" * 5000) / "claude")
        self.provider = self.make(places=(evil, str(self.d / "gone" / "claude")))
        self.connect(ai_providers.ClaudeSubscription(self.provider))
        lines = self.cap.lines()
        self.assertEqual(len(self.cap.connect_lines()), 1)
        self.assertFalse(any("INJECTED" in x or "yyyy" in x or str(self.d) in x for x in lines))
        self.assertTrue(all(len(x) < 400 for x in lines))

    def test_huge_multiline_command_output_never_reaches_the_log(self):
        self.put("auth", "secret-token-abcdef0123456789abcdef\n" * 5000)
        self.connect()
        lines = self.cap.lines()
        self.assertEqual(len(self.cap.connect_lines()), 1)
        self.assertFalse(any("secret-token" in x for x in lines))
        self.assertTrue(all(len(x) < 400 for x in lines))

    def test_a_provider_that_raises_or_says_nonsense_logs_nothing_and_still_refuses(self):
        class Odd(ai_providers.ClaudeSubscription):
            def failed_check(self):
                raise RuntimeError("boom\nline two")

        self.cmd.unlink()
        provider = Odd(self.provider)
        status, _ = self.connect(provider)
        self.assertEqual(status, 409)
        self.assertEqual(self.cap.connect_lines(), [])

    def test_every_failure_line_is_fixed_words_only_whatever_the_command_or_the_login_says(self):
        """Item 1100 hostile pass: for each failing check, with a command path carrying a newline and markup, the one line is plain words
        (letters, spaces and an apostrophe), so no path, format marker, markup or output can ride in it."""
        import re
        evil = "<b>%s %r\nINJECTED"
        scenarios = [
            lambda: self.cmd.unlink(),
            lambda: self.mode("badversion"),
            lambda: self.put("auth", json.dumps({"loggedIn": True, "authMethod": "api_key", "email": evil})),
            lambda: self.put("auth", json.dumps({"loggedIn": False, "authMethod": evil})),
        ]
        for i, arrange in enumerate(scenarios):
            with self.subTest(i):
                if i:
                    self.setUp()                    # a fresh fake command and log for each failing check
                arrange()
                self.provider = self.make(places=(str(self.cmd), str(self.d / evil / "claude")))
                self.connect(ai_providers.ClaudeSubscription(self.provider))
                got = self.cap.connect_lines()
                self.assertEqual(len(got), 1, got)
                said = re.search(r"ai: connect failed, (.*)$", got[0]).group(1)
                self.assertRegex(said, r"^[A-Za-z' ]+$")
                self.assertFalse(any("INJECTED" in x or "<b>" in x for x in self.cap.lines()))

    def test_the_home_folder_never_appears_unshortened(self):
        self.cmd.unlink()
        self.connect()
        home = str(Path.home())
        self.assertFalse(any(home in x for x in self.cap.lines()))


class CodexChecks(Base):
    FAKE_CODEX = (
        "#!" + sys.executable + " -B\n"
        "import sys\n"
        "a = sys.argv[1:]\n"
        "if a == ['--version']:\n"
        "    print('codex-cli ' + open(__file__.replace('codex', 'version')).read().strip())\n"
        "elif a == ['exec', '--help']:\n"
        "    print('\\n'.join('  ' + f + ' <x>  something' for f in " + repr(ai_codex.NEEDED_FLAGS) + "))\n"
        "elif a == ['login', 'status']:\n"
        "    sys.stderr.write(open(__file__.replace('codex', 'login')).read())\n"
        "    sys.exit(int(open(__file__.replace('codex', 'logincode')).read()))\n")

    def codex(self, version="0.166.1", login="Logged in using ChatGPT", code="0"):
        path = self.bin / "codex"
        path.write_text(self.FAKE_CODEX, encoding="utf-8")
        path.chmod(0o755)
        (self.bin / "version").write_text(version, encoding="utf-8")
        (self.bin / "login").write_text(login, encoding="utf-8")
        (self.bin / "logincode").write_text(code, encoding="utf-8")
        mock.patch.object(ai_codex.ask_claude, "native_problem", return_value=None).start()
        self.addCleanup(mock.patch.stopall)
        return ai_providers.ChatGPTSubscription(ai_codex.CodexCommand(places=(str(path),), env=self.provider.env, roots=(str(self.d),), walled=False))

    def test_the_fake_signed_in_passes(self):
        status, _ = self.connect(self.codex(), "chatgpt")
        self.assertEqual(status, 200)
        self.assertEqual(self.cap.connect_lines(), [])

    def test_codex_not_found(self):
        provider = ai_providers.ChatGPTSubscription(ai_codex.CodexCommand(places=(str(self.bin / "nope"),), walled=False, roots=(str(self.d),)))
        self.connect(provider, "chatgpt")
        self.one("the command was not found")

    def test_codex_not_signed_in_with_chatgpt(self):
        self.connect(self.codex(login="Not logged in", code="1"), "chatgpt")
        self.one("not signed in with the account clark can use")

    def test_codex_version_not_tested(self):
        self.connect(self.codex(version="9.0.0"), "chatgpt")
        self.one("version has not been tested")

    def test_codex_api_key(self):
        self.connect(self.codex(login="Logged in using an API key", code="0"), "chatgpt")
        self.one("signed in with an API key")

    def test_codex_in_a_container(self):
        provider = self.codex()
        with mock.patch.object(platform, "system", return_value="linux"), mock.patch.object(platform, "container_mode", return_value=True):
            self.connect(provider, "chatgpt")
        self.one("running in a container")


if __name__ == "__main__":
    unittest.main()
