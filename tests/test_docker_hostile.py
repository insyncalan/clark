"""Item 1100, hostile inputs: the Docker and Terminal messages never leak a path, a raw error text or a traceback, and the
starter refuses odd port values. Quick tier: no Docker, no browser, no osascript.
Run: python3 dev/run_tests.py test_docker_hostile"""
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _paths import SRC  # noqa: F401

from clark import ai_codex, ask_claude, ask_folders, log_routes, platform as pl, updater
from test_docker_front import Script as Starter, TEMPLATE
from test_docker_words import WORDS, InDocker

SECRET = "/Users/someone/Library/Secret Folder/clark.db"
LEAKY = (SECRET, 'Traceback (most recent call last):\n  File "/x/y.py", line 3, in z\nNotBuiltYet: boom', "[Errno 13] Permission denied: '/Users/a/b'")


def clean(test, text):
    for bad in ("/Users/", "/home/", "/tmp/", "Traceback", "File \"", "Errno", "NotBuiltYet", "PlatformError", "OSError", "Permission denied"):
        test.assertNotIn(bad, text)


class Words(unittest.TestCase):
    def test_the_sentence_has_no_path_but_the_command(self):
        text = pl.needs_mac_words()
        self.assertEqual(WORDS, text)
        clean(self, text)
        self.assertEqual(text, text.strip())
        self.assertTrue(all(c.isprintable() for c in text))

    def test_only_the_exact_sentence_passes_refusal_words(self):
        for leaky in LEAKY + ("", " " + WORDS, WORDS + " " + SECRET, "‮" + WORDS, "x" * 100000):
            for kind in (pl.NotBuiltYet, pl.PlatformError):
                got = pl.refusal_words(kind(leaky), "plain fallback")
                self.assertEqual("plain fallback", got, (kind, leaky[:30]))
        for other in (OSError(SECRET), ValueError(SECRET), None, "text"):
            self.assertEqual("plain fallback", pl.refusal_words(other, "plain fallback"))
        self.assertEqual(WORDS, pl.refusal_words(pl.NotBuiltYet(WORDS), "plain fallback"))

    def test_a_non_container_linux_or_windows_refusal_is_not_the_docker_sentence(self):
        for on in ("windows", "linux"):
            with mock.patch.object(pl, "container_mode", return_value=False):
                with self.assertRaises(pl.NotBuiltYet) as said:
                    pl._only_mac("The Open dialog", on)
            self.assertNotEqual(WORDS, str(said.exception))
            self.assertEqual("plain fallback", pl.refusal_words(said.exception, "plain fallback"))


class Routes(InDocker):
    def test_a_dialog_that_fails_with_a_path_in_its_error_says_only_the_plain_words(self):
        for leaky in LEAKY:
            for kind in (pl.NotBuiltYet, pl.PlatformError):
                def boom(*_a, **_k):
                    raise kind(leaky)
                folders = ask_folders.AskFolders(self.dir / "a.db", [], data_dir=self.dir, choose_folder=boom)

                class Store:
                    def read(self, *_a, **_k):
                        return []
                status, body = folders.choose(Store(), "ABC")
                said = "no_window_docker" if kind is pl.NotBuiltYet else "dialog_failed"     # a window that can never open has its own typed-location words
                self.assertEqual(ask_folders.MESSAGES[said], body["message"])
                clean(self, repr(body))

                service = updater.Updater(self.dir, self.dir / "a.db", 8765, app_dir=self.dir, system="mac", version="1.0.0", schema=2,
                                          downloads=self.dir, choose=boom)
                with mock.patch.object(service, "_blocked", return_value=None):
                    status, body = service.review({"from": "file"})
                self.assertEqual(updater.MESSAGES["dialog"], body["message"], (status, body))
                clean(self, repr(body))

    def test_the_log_folder_never_shows_an_os_error_text(self):
        for leaky in LEAKY:
            class Log:
                folder = self.dir / "logs"
            routes = log_routes.Logs(Log(), opener=mock.Mock(side_effect=OSError(leaky)))
            status, body = routes.open_folder()
            self.assertEqual(200, status)            # item 632: in Docker the folder is told, never opened, so the opener's error is never reached
            self.assertEqual(log_routes.container_log_words(), body["shown"])
            clean(self, repr(body))

    def test_the_ask_commands_in_docker_say_the_sentence_whatever_the_environment_holds(self):
        hostile = {"CLARK_PORT": "8766; rm -rf /", "CLARK_SERVER_PORT": "\x1b[2J" + "9" * 5000, "HOME": SECRET, "PATH": "",
                   "CLARK_DATA_DIR": "\n" + SECRET}
        for cls in (ask_claude.ClaudeCommand, ai_codex.CodexCommand):
            with mock.patch.dict("os.environ", hostile):
                command = cls()
                self.assertEqual((None, WORDS), command.command())
                got = command.status()
            self.assertFalse(got["connected"])
            self.assertEqual(WORDS, got["why"][:len(WORDS)])
            clean(self, repr(got))
            self.assertNotIn("rm -rf", repr(got))


class StarterPorts(Starter):
    test_with_the_server_running_it_starts_the_front_on_the_default_ports = None

    def test_a_port_with_a_zero_in_front_is_refused_because_the_browser_never_spells_it_so(self):
        for name in ("CLARK_PORT", "CLARK_SERVER_PORT"):
            for bad in ("08766", "01024", "0", "00000"):
                r = self.run_script(**{name: bad})
                self.assertEqual(1, r.returncode, (name, bad))
                self.assertIn(f"{name} must be a number from 1024 to 65535", r.stderr)
                self.assertEqual([], self.calls(), (name, bad))

    def test_the_refusal_does_not_repeat_what_was_typed(self):
        for name in ("CLARK_PORT", "CLARK_SERVER_PORT"):
            for bad in ("\x1b[2J\x07", "9" * 5000, "a\nb", "$(id)", "`id`", "'; echo hi; '", "ö‮8766", "8766 ", " "):
                r = self.run_script(**{name: bad})
                self.assertEqual(1, r.returncode, (name, bad[:10]))
                self.assertEqual(f"{name} must be a number from 1024 to 65535.\n", r.stderr, (name, bad[:10]))
                self.assertEqual("", r.stdout)
                self.assertEqual([], self.calls())

    def test_the_boundaries(self):
        for good, code in (("1024", 0), ("65535", 0), ("1023", 1), ("65536", 1)):
            self.assertEqual(code, self.run_script(CLARK_PORT=good).returncode, good)
            self.log.unlink() if self.log.exists() else None

    def test_every_failure_says_a_next_step_and_never_a_traceback(self):
        cases = [dict(health=False), dict(CLARK_PORT="x"), dict(CLARK_PORT="8800", CLARK_SERVER_PORT="8800")]
        for kw in cases:
            r = self.run_script(**kw)
            self.assertEqual(1, r.returncode, kw)
            clean(self, r.stderr + r.stdout)
            self.assertTrue(r.stderr.strip(), kw)
            self.log.unlink() if self.log.exists() else None

    def test_a_missing_docker_does_not_blame_a_path(self):
        (self.bin / "docker").unlink()
        r = self.run_script()
        if shutil_which_docker():
            self.skipTest("a real docker is on the path")
        self.assertEqual(1, r.returncode)
        self.assertIn("bash clark.command", r.stderr)
        clean(self, r.stderr)


def shutil_which_docker():
    import shutil
    return shutil.which("docker", path="/usr/bin:/bin")


class Proxy(unittest.TestCase):
    def test_the_template_takes_only_the_two_ports_from_outside(self):
        self.assertEqual({"CLARK_PORT", "CLARK_SERVER_PORT"}, set(re.findall(r"\$\{(\w+)\}", TEMPLATE)))

    def test_the_down_page_leaks_nothing_and_is_not_built_from_the_request(self):
        page = re.search(r'return 502 "(.*?)";', TEMPLATE, re.S).group(1)
        clean(self, page)
        for var in ("$http_", "$request", "$uri", "$args", "$host", "$remote", "$upstream"):
            self.assertNotIn(var, page)
        self.assertIn("bash docker/front.command server", page)


if __name__ == "__main__":
    unittest.main()
