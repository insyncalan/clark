"""item 629: the Windows host flag. docker/compose.windows.yaml passes CLARK_HOST=windows; clark then shows Windows path forms and
says "ask clark is not available on Windows yet" where ask clark would be. With the setting off nothing changes.

Run: python3 tests/test_windows_host_629.py
Nothing real is read or started: the environment is faked and the commands are never found.
"""
import os
import unittest
from pathlib import Path
from unittest import mock

from _paths import SRC  # noqa: F401

from clark import ai_codex, ask, ask_claude, doctor, platform as pl

ROOT = Path(__file__).resolve().parents[1]
ON = {"CLARK_HOST": "windows"}
SAYS = "ask clark is not available on Windows yet"


def env(values):
    return mock.patch.dict(os.environ, values, clear=True)


class Reader(unittest.TestCase):
    def test_only_the_exact_setting_says_windows(self):
        self.assertEqual(pl.host(ON), "windows")
        self.assertTrue(pl.windows_host(ON))
        for other in ({}, {"CLARK_HOST": ""}, {"CLARK_HOST": "mac"}, {"CLARK_HOST": "Windows"}, {"CLARK_HOST": "127.0.0.1"},
                      {"OTHER": "windows"}):
            self.assertIsNone(pl.host(other), other)
            self.assertFalse(pl.windows_host(other), other)

    def test_it_reads_the_real_environment_by_default(self):
        with env(ON):
            self.assertTrue(pl.windows_host())
        with env({}):
            self.assertFalse(pl.windows_host())

    def test_the_sentence_is_the_issues(self):
        self.assertEqual(pl.ASK_OFF_ON_WINDOWS, SAYS)


class Paths(unittest.TestCase):
    def test_off_nothing_changes(self):
        with env({}):
            self.assertEqual(pl.shown("/home/ann/Reports/a.pdf", home="/home/ann"), "~/Reports/a.pdf")
            self.assertEqual(pl.shown("/srv/x", home="/home/ann"), "/srv/x")
            self.assertEqual(pl.shown("/srv/x", home="/"), "/srv/x")
            self.assertEqual(pl.with_tilde("/home/ann/Reports", home="/home/ann"), "~/Reports")
            self.assertEqual(pl.with_tilde("/srv/x", home="/home/ann"), "/srv/x")

    def test_on_paths_are_in_the_windows_form(self):
        with env(ON):
            self.assertEqual(pl.shown("/home/ann/Reports/a.pdf", home="/home/ann"), "~\\Reports\\a.pdf")
            self.assertEqual(pl.shown("/home/ann", home="/home/ann"), "~")
            self.assertEqual(pl.with_tilde("/home/ann/Reports", home="/home/ann"), "~\\Reports")

    def test_on_container_paths_outside_the_home_keep_their_slashes(self):
        with env(ON):
            self.assertEqual(pl.shown("/data", home="/home/ann"), "/data")
            self.assertEqual(pl.shown("/data/x", home="/"), "/data/x")
            self.assertEqual(pl.with_tilde("/data/x", home="/home/ann"), "/data/x")

    def test_with_tilde_with_a_home_of_slash_writes_no_tilde(self):
        for setting in ({}, ON):
            with env(setting):
                self.assertEqual(pl.with_tilde("/data/x", home="/"), "/data/x")
                self.assertEqual(pl.with_tilde("/", home="/"), "/")

    def test_folder_phrase_is_the_same_on_and_off_for_a_container_path(self):
        """item 629: folder_phrase names the last folder and does not go through the host form."""
        for setting in ({}, ON):
            with env(setting):
                self.assertEqual(pl.folder_phrase("/data/Reports"), "the folder “Reports”")


class AskClark(unittest.TestCase):
    def test_find_claude_says_so_when_on_and_is_unchanged_when_off(self):
        with env(ON):
            with self.assertRaises(pl.PlatformError) as caught:
                pl.find_claude(lambda name: "/usr/bin/claude")
            self.assertEqual(str(caught.exception), SAYS)
        with env({}):
            self.assertEqual(pl.find_claude(lambda name: "/usr/bin/claude"), "/usr/bin/claude")
            self.assertIsNone(pl.find_claude(lambda name: None))

    def test_the_doctor_says_so(self):
        seen = mock.Mock(find_claude=lambda: pl.find_claude(lambda name: "/usr/bin/claude"))
        with env(ON):
            line = doctor.check_claude(seen)
        self.assertEqual(line.words, SAYS)
        self.assertEqual(line.kind, doctor.ADVICE)
        with env({}):
            self.assertEqual(doctor.check_claude(seen).kind, doctor.READY)

    def test_the_claude_command_is_off_and_says_so_even_on_a_mac(self):
        for system in ("linux", "darwin"):
            with mock.patch.object(pl, "system", return_value=system), env(ON):
                provider = ask_claude.ClaudeCommand(places=("/nowhere/claude",), env={})
                self.assertEqual(provider.command(), (None, SAYS))
                self.assertEqual(provider.failed, "windows_host")
                self.assertEqual(provider.status(), {"connected": False, "why": SAYS})
                self.assertEqual(provider.ask(ask.build_request("q", [])), ask.Failure(SAYS))

    def test_the_chatgpt_command_is_off_and_says_so(self):
        with env(ON):
            provider = ai_codex.CodexCommand(places=("/nowhere/codex",), env={})
            self.assertEqual(provider.command(), (None, SAYS))
            self.assertEqual(provider.failed, "windows_host")

    def test_off_the_old_sentences_stay(self):
        with mock.patch.object(pl, "system", return_value="linux"), env({"CLARK_HOST": "mac"}):
            provider = ask_claude.ClaudeCommand(places=("/nowhere/claude",), env={})
            self.assertEqual(provider.command(), (None, ask_claude.MAC_ONLY))
            self.assertEqual(provider.failed, "not_mac_os")


class Compose(unittest.TestCase):
    def text(self, name):
        return (ROOT / "docker" / name).read_text(encoding="utf-8")

    def test_the_windows_file_passes_the_setting(self):
        self.assertRegex(self.text("compose.windows.yaml"), r'(?m)^      CLARK_HOST: "windows"$')

    def test_the_main_file_does_not(self):
        self.assertNotIn("CLARK_HOST", self.text("compose.yaml"))


if __name__ == "__main__":
    unittest.main()
