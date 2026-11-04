"""#643 slice 1: the Keychain store for the AI keys. No real Keychain: `run_security` is replaced by an in-memory fake that records every call.

Run: python3 dev/run_tests.py test_ai_keychain
"""
import io
import logging
import os
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

from _paths import SRC  # noqa: F401
from clark import ai_keychain as k, platform

CLAUDE = "sk-ant-api03-" + "A1b2C3d4" * 4
OPENAI = "sk-proj-" + "Z9y8X7w6" * 4


class FakeKeychain:
    """Stands in for run_security: keeps items by (service, account) and records (args, stdin) for every call. `fail` makes every call exit with that code."""

    def __init__(self, fail=None):
        self.items, self.calls, self.fail = {}, [], fail

    def __call__(self, args, stdin=None):
        self.calls.append((list(args), stdin))
        if self.fail is not None:
            return self.fail, ""
        if args == ["-i"]:
            words = stdin.strip().split(" ")
            account, secret = words[words.index("-a") + 1], words[words.index("-w") + 1]
            self.items[(words[words.index("-s") + 1], account)] = secret       # -U: the second save replaces
            return 0, ""
        verb, account = args[0], args[args.index("-a") + 1]
        item = (args[args.index("-s") + 1], account)
        if item not in self.items:
            return 44, ""
        if verb == "delete-generic-password":
            del self.items[item]
            return 0, ""
        return 0, (self.items[item] + "\n") if "-w" in args else ""


class OnTheMac(unittest.TestCase):
    def setUp(self):
        self.fake = FakeKeychain()
        for patch in (mock.patch.object(k, "run_security", self.fake), mock.patch.object(platform, "system", return_value=platform.MAC),
                      mock.patch.object(platform, "container_mode", create=True, return_value=False)):
            patch.start()
            self.addCleanup(patch.stop)

    def everything_seen(self, key):
        """Every place the key could leak to, as one text: argv of every call, the environment, and any text a test captured."""
        argv = " ".join(" ".join(a) for a, _ in self.fake.calls)
        return argv + " " + " ".join(os.environ.values())


class TheKeyIsOnlyOnStdin(OnTheMac):
    def test_save_sends_the_key_on_stdin_and_nowhere_else(self):
        k.save_key("claude", CLAUDE)
        args, stdin = self.fake.calls[0]
        self.assertEqual(args, ["-i"])
        self.assertIn(CLAUDE, stdin)
        self.assertNotIn(CLAUDE, self.everything_seen(CLAUDE))
        self.assertIn('-T ""', stdin)
        self.assertIn("-U", stdin)

    def test_read_has_and_delete_never_put_a_key_in_argv_and_only_read_returns_it(self):
        k.save_key("openai", OPENAI)
        self.assertIs(k.has_key("openai"), True)
        self.assertEqual(k.read_key("openai"), OPENAI)
        self.assertIsNone(k.delete_key("openai"))
        self.assertIsNone(k.save_key("openai", OPENAI))
        self.assertNotIn(OPENAI, self.everything_seen(OPENAI))

    def test_has_key_does_not_ask_for_the_secret(self):
        k.save_key("claude", CLAUDE)
        k.has_key("claude")
        self.assertNotIn("-w", self.fake.calls[-1][0])

    def test_nothing_is_logged_printed_or_in_the_environment(self):
        out, err = io.StringIO(), io.StringIO()
        with self.assertLogs(level="DEBUG") as logs, redirect_stdout(out), redirect_stderr(err):
            logging.getLogger("clark").debug("start")                # assertLogs needs one line to exist
            k.save_key("claude", CLAUDE)
            k.has_key("claude")
            k.read_key("claude")
            k.delete_key("claude")
            with self.assertRaises(k.KeychainError):
                k.save_key("claude", "sk-ant-short")
        self.assertNotIn(CLAUDE, "\n".join(logs.output) + out.getvalue() + err.getvalue())
        self.assertNotIn(CLAUDE, " ".join(os.environ.values()))


class SaveReplacesAndDeleteRemoves(OnTheMac):
    def test_a_second_save_replaces(self):
        k.save_key("claude", CLAUDE)
        newer = "sk-ant-api03-" + "Q" * 30
        k.save_key("claude", newer)
        self.assertEqual(len(self.fake.items), 1)
        self.assertEqual(k.read_key("claude"), newer)

    def test_the_two_providers_are_kept_apart(self):
        k.save_key("claude", CLAUDE)
        self.assertIs(k.has_key("openai"), False)
        self.assertIsNone(k.read_key("openai"))

    def test_delete_removes_and_a_second_delete_is_fine(self):
        k.save_key("claude", CLAUDE)
        k.delete_key("claude")
        self.assertIs(k.has_key("claude"), False)
        self.assertIsNone(k.read_key("claude"))
        k.delete_key("claude")
        self.assertEqual(self.fake.items, {})


class ShapeRefusals(OnTheMac):
    CASES = {
        "empty": ("claude", ""),
        "bad_character": ("claude", "sk-ant-" + "a" * 20 + " b"),
        "bad_character ": ("claude", "sk-ant-" + "a" * 20 + "\n"),
        "bad_character\t": ("claude", "sk-ant-" + "a" * 20 + "\t"),
        "bad_character\x00": ("claude", "sk-ant-" + "a" * 20 + "\x00"),
        "bad_character\x7f": ("claude", "sk-ant-" + "a" * 20 + "\x7f"),
        "bad_character'": ("claude", "sk-ant-" + "a" * 20 + "'"),
        'bad_character"': ("openai", 'sk-' + "a" * 20 + '"'),
        "not_ascii": ("openai", "sk-" + "a" * 20 + "é"),
        "too_short": ("claude", "sk-ant-abc"),
        "too_long": ("openai", "sk-" + "a" * 400),
        "wrong_prefix": ("claude", "sk-" + "a" * 30),
        "wrong_prefix2": ("openai", "pk-" + "a" * 30),
        "provider": ("gemini", "sk-" + "a" * 30),
    }

    def test_every_refusal_has_a_short_code_and_never_echoes_the_key(self):
        for name, (provider, key) in self.CASES.items():
            with self.subTest(name):
                code = k.valid_shape(provider, key)
                self.assertEqual(code, name.rstrip("\t\n\x00\x7f '\"").rstrip("2").rstrip(" ") if name != "empty" else "empty")
                self.assertLessEqual(len(code), 20)
                if key:
                    self.assertNotIn(key, code)
                with self.assertRaises(k.KeychainError) as caught:
                    k.save_key(provider, key)
                if key.strip():
                    self.assertNotIn(key, str(caught.exception))
        self.assertEqual(self.fake.calls, [])               # nothing reached the Keychain

    def test_good_keys_pass_and_the_limits_are_exact(self):
        self.assertIsNone(k.valid_shape("claude", CLAUDE))
        self.assertIsNone(k.valid_shape("openai", OPENAI))
        self.assertIsNone(k.valid_shape("openai", "sk-" + "a" * 17))      # 20 characters
        self.assertEqual(k.valid_shape("openai", "sk-" + "a" * 16), "too_short")
        self.assertIsNone(k.valid_shape("openai", "sk-" + "a" * 397))     # 400 characters
        self.assertEqual(k.valid_shape("openai", "sk-" + "a" * 398), "too_long")

    def test_a_non_string_is_refused(self):
        self.assertEqual(k.valid_shape("claude", None), "empty")
        self.assertEqual(k.valid_shape("claude", b"sk-ant-" + b"a" * 30), "empty")


class OffTheMacAndInTheContainer(unittest.TestCase):
    def calls(self):
        return (lambda: k.has_key("claude"), lambda: k.save_key("claude", CLAUDE), lambda: k.read_key("claude"), lambda: k.delete_key("claude"))

    def test_other_systems_refuse_before_security_is_called(self):
        for system in ("win32", "linux"):
            with mock.patch.object(platform, "system", return_value=system), mock.patch.object(k, "run_security") as run:
                for call in self.calls():
                    with self.subTest(system=system), self.assertRaises(platform.NotBuiltYet) as caught:
                        call()
                    self.assertNotIn(CLAUDE, str(caught.exception))
                run.assert_not_called()

    def test_container_mode_refuses_even_on_a_mac_system_value(self):
        with mock.patch.object(platform, "system", return_value=platform.MAC), mock.patch.object(platform, "container_mode", create=True, return_value=True), \
                mock.patch.object(k, "run_security") as run:
            for call in self.calls():
                with self.assertRaises(platform.NotBuiltYet):
                    call()
            run.assert_not_called()


class ALockedKeychain(OnTheMac):
    def test_a_nonzero_exit_gives_the_fixed_sentence_and_nothing_more(self):
        self.fake.fail = 36                                  # security's "user interaction is not allowed" (locked)
        for call in (lambda: k.has_key("claude"), lambda: k.save_key("claude", CLAUDE), lambda: k.read_key("claude"), lambda: k.delete_key("claude")):
            with self.assertRaises(k.KeychainError) as caught:
                call()
            self.assertEqual(str(caught.exception), k.KEYCHAIN_SAID_NO)
            self.assertNotIn(CLAUDE, str(caught.exception))

    def test_security_failing_to_start_gives_the_same_sentence_and_hides_its_text(self):
        with mock.patch.object(k, "run_security", side_effect=OSError("secret path " + CLAUDE)):
            with self.assertRaises(k.KeychainError) as caught:
                k.save_key("claude", CLAUDE)
        self.assertEqual(str(caught.exception), k.KEYCHAIN_SAID_NO)
        self.assertTrue(caught.exception.__suppress_context__)


class TheRealRunSecurityIsOneFunction(unittest.TestCase):
    def test_it_starts_only_usr_bin_security_with_stdin_and_a_timeout(self):
        done = mock.Mock(returncode=0, stdout="x")
        with mock.patch.object(platform.subprocess, "run", return_value=done) as run:
            self.assertEqual(k.run_security(["-i"], stdin="add\n"), (0, "x"))
        self.assertEqual(run.call_args.args[0], ["/usr/bin/security", "-i"])
        self.assertEqual(run.call_args.kwargs["input"], "add\n")
        self.assertIn("timeout", run.call_args.kwargs)

    def test_no_other_code_in_the_module_starts_a_program(self):
        text = open(k.__file__, encoding="utf-8").read()
        self.assertEqual(text.count("platform.run_program("), 1)
        self.assertNotIn("import subprocess", text)


if __name__ == "__main__":
    unittest.main()
