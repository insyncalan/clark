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
        self.add_says, self.add_stores = "", True     # what `security -i` prints after an add, and whether the item really lands

    def __call__(self, args, stdin=None):
        self.calls.append((list(args), stdin))
        if self.fail is not None:
            return self.fail, "", ""
        if args == ["-i"]:
            words = stdin.strip().split(" ")
            account, secret = words[words.index("-a") + 1], words[words.index("-w") + 1]
            if self.add_stores:
                self.items[(words[words.index("-s") + 1], account)] = secret       # -U: the second save replaces
            return 0, "", self.add_says                                            # exit 0 whatever the add did, as the real tool does
        verb, account = args[0], args[args.index("-a") + 1]
        item = (args[args.index("-s") + 1], account)
        if item not in self.items:
            return 44, "", ""
        if verb == "delete-generic-password":
            del self.items[item]
            return 0, "", ""
        return 0, (self.items[item] + "\n") if "-w" in args else "", ""


class OnTheMac(unittest.TestCase):
    def setUp(self):
        self.fake = FakeKeychain()
        for patch in (mock.patch.object(k, "run_security", self.fake), mock.patch.object(platform, "system", return_value=platform.MAC),
                      mock.patch.object(platform, "container_mode", return_value=False)):
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
    # label -> (name in k.REFUSAL_CODES, provider, key)
    CASES = {
        "empty": ("empty", "claude", ""),
        "space": ("bad_character", "claude", "sk-ant-" + "a" * 20 + " b"),
        "newline": ("bad_character", "claude", "sk-ant-" + "a" * 20 + "\n"),
        "tab": ("bad_character", "claude", "sk-ant-" + "a" * 20 + "\t"),
        "nul": ("bad_character", "claude", "sk-ant-" + "a" * 20 + "\x00"),
        "del": ("bad_character", "claude", "sk-ant-" + "a" * 20 + "\x7f"),
        "single quote": ("bad_character", "claude", "sk-ant-" + "a" * 20 + "'"),
        "double quote": ("bad_character", "openai", 'sk-' + "a" * 20 + '"'),
        "not_ascii": ("not_ascii", "openai", "sk-" + "a" * 20 + "\u00e9"),
        "too_short": ("too_short", "claude", "sk-ant-abc"),
        "too_long": ("too_long", "openai", "sk-" + "a" * 400),
        "wrong_prefix": ("wrong_prefix", "claude", "sk-" + "a" * 30),
        "wrong_prefix2": ("wrong_prefix", "openai", "pk-" + "a" * 30),
        "provider": ("provider", "gemini", "sk-" + "a" * 30),
    }
    # every ASCII printable character that is not a letter, digit, `-` or `_` is refused where the tail of a key goes
    for _ch in (c for c in map(chr, range(33, 127)) if not (c.isalnum() or c in "-_")):
        CASES["excluded " + repr(_ch)] = ("bad_character", "claude", "sk-ant-" + "a" * 20 + _ch + "b")
        CASES["excluded openai " + repr(_ch)] = ("bad_character", "openai", "sk-" + "a" * 20 + _ch + "b")
    del _ch

    def test_every_refusal_has_a_short_code_and_never_echoes_the_key(self):
        for label, (name, provider, key) in self.CASES.items():
            with self.subTest(label):
                code = k.valid_shape(provider, key)
                self.assertEqual(code, k.REFUSAL_CODES[name])
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

    def test_real_key_shapes_are_accepted(self):
        self.assertIsNone(k.valid_shape("claude", "sk-" + "ant-api03-AbC_dE-" + "1234567890abcdefghij"))
        self.assertIsNone(k.valid_shape("openai", "sk-" + "proj-AbC_dE-" + "1234567890abcdefghijkl"))

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
        with mock.patch.object(platform, "system", return_value=platform.MAC), mock.patch.object(platform, "container_mode", return_value=True), \
                mock.patch.object(k, "run_security") as run:
            for call in self.calls():
                with self.assertRaises(platform.NotBuiltYet):
                    call()
            run.assert_not_called()


class SecurityExitsZeroEvenWhenTheAddFails(OnTheMac):
    """Confirmed on a real Mac: `security -i` exits 0 when the add inside it fails, printing `add-generic-password: returned -25299`."""

    def test_a_returned_error_line_on_stderr_or_stdout_is_a_failure(self):
        for text in ("add-generic-password: returned -25299\n", "returned 1", "noise\nadd-generic-password: returned -25293\nmore"):
            self.fake.add_says = text
            with self.assertRaises(k.KeychainError) as caught:
                k.save_key("claude", CLAUDE)
            self.assertEqual(str(caught.exception), k.KEYCHAIN_SAID_NO)
            self.assertNotIn(CLAUDE, repr(caught.exception))

    def test_silence_but_no_item_afterwards_is_a_failure(self):
        self.fake.add_stores = False
        with self.assertRaises(k.KeychainError) as caught:
            k.save_key("claude", CLAUDE)
        self.assertEqual(str(caught.exception), k.KEYCHAIN_SAID_NO)

    def test_the_happy_path_still_works_and_checks_the_item(self):
        self.assertIsNone(k.save_key("claude", CLAUDE))
        self.assertEqual(self.fake.calls[-1][0][0], "find-generic-password")
        self.assertNotIn("-w", self.fake.calls[-1][0])
        self.assertEqual(k.read_key("claude"), CLAUDE)


class TheKeyIsNotLeftInFramesATracebackCanReach(OnTheMac):
    def frames_text(self, exc):
        found, tb = [], exc.__traceback__
        while tb:
            if os.path.basename(tb.tb_frame.f_code.co_filename) == "ai_keychain.py":
                found += [(tb.tb_frame.f_code.co_name, v) for v in tb.tb_frame.f_locals.values()]
            tb = tb.tb_next
        return found

    def raised_frames(self, patch, provider, key, error):
        """Call save_key and walk the traceback inside a plain try: assertRaises would clear the frames' locals and make the walk empty."""
        with patch:
            try:
                k.save_key(provider, key)
            except error as caught:
                return self.frames_text(caught)
        self.fail("save_key did not raise")

    def test_no_ai_keychain_frame_in_the_traceback_holds_the_key(self):
        for cause in ("add_fails", "start_fails"):
            if cause == "add_fails":
                self.fake.add_says = "returned -25299"
                patch = mock.patch.object(k, "run_security", self.fake)
            else:
                patch = mock.patch.object(k, "run_security", side_effect=OSError("x"))
            frames = self.raised_frames(patch, "claude", CLAUDE, k.KeychainError)
            self.assertTrue(frames)                                   # the walk found ai_keychain frames
            for name, value in frames:
                self.assertNotIn(CLAUDE, str(value), name)
                self.assertNotIn(CLAUDE, repr(value), name)

    def test_a_refused_shape_leaves_no_key_in_the_frame_either(self):
        bad = "sk-ant-" + "a" * 20 + " b"
        frames = self.raised_frames(mock.patch.object(k, "run_security", self.fake), "claude", bad, k.KeyRefused)
        self.assertTrue(frames)
        for name, value in frames:
            self.assertNotIn(bad, repr(value), name)


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
        done = mock.Mock(returncode=0, stdout="x", stderr="e")
        with mock.patch.object(platform.subprocess, "run", return_value=done) as run:
            self.assertEqual(k.run_security(["-i"], stdin="add\n"), (0, "x", "e"))
        self.assertEqual(run.call_args.args[0], ["/usr/bin/security", "-i"])
        self.assertEqual(run.call_args.kwargs["input"], "add\n")
        self.assertIn("timeout", run.call_args.kwargs)

    def test_no_other_code_in_the_module_starts_a_program(self):
        text = open(k.__file__, encoding="utf-8").read()
        self.assertEqual(text.count("platform.run_program("), 1)
        self.assertNotIn("import subprocess", text)


if __name__ == "__main__":
    unittest.main()
