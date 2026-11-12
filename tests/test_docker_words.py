"""Item 1100: every route that needs the Mac says so in one set of words when clark runs in Docker, and never shows a class name.

Run: python3 dev/run_tests.py test_docker_words
The words come from platform.needs_mac_words(). Each test drives a real route object with the real platform call (nothing stubbed
but "this is a Docker container on Linux"), so a route that makes up its own words, or lets the refusal become a generic fault,
fails here. No osascript is run and nothing is opened.
"""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _paths import SRC  # noqa: F401

from clark import ai_codex, ai_connect, ask, ask_claude, ask_folders, log_routes, platform as pl, updater

WORDS = "This needs clark to run on the Mac itself; start it from Terminal: bash clark.command"


class InDocker(unittest.TestCase):
    def setUp(self):
        for patch in (mock.patch.object(sys, "platform", "linux"), mock.patch.object(pl, "container_mode", return_value=True)):
            patch.start()
            self.addCleanup(patch.stop)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def no_class_name(self, text):
        for bad in ("NotBuiltYet", "PlatformError", "Traceback", "server_error"):
            self.assertNotIn(bad, text)


class TheWords(InDocker):
    def test_the_sentence_is_exact(self):
        self.assertEqual(WORDS, pl.needs_mac_words())

    def test_a_mac_only_call_raises_it(self):
        for call in (lambda: pl.choose_folder("x"), lambda: pl.choose_zip_file("x"), lambda: pl.choose_save_file("x", "a.docx"),
                     lambda: pl.choose_open_file("x"), lambda: pl.reveal_file(__file__), lambda: pl.open_file(__file__),
                     lambda: pl.downloads_dir()):
            with self.assertRaises(pl.NotBuiltYet) as said:
                call()
            self.assertEqual(WORDS, str(said.exception))

    def test_refusal_words_pass_only_the_needs_mac_sentence(self):
        self.assertEqual(WORDS, pl.refusal_words(pl.NotBuiltYet(WORDS), "generic"))
        self.assertEqual("generic", pl.refusal_words(pl.PlatformError("the system's own text"), "generic"))


class Connect(InDocker):
    def test_settings_connect_claude_and_codex(self):
        connect, _chosen = ai_connect.chain(self.dir)
        for name in ("claude", "chatgpt"):
            status, body = connect.connect({"provider": name})
            self.assertEqual(409, status)
            self.assertEqual(WORDS, body["message"], name)
            self.no_class_name(body["message"])

    def test_the_provider_list_says_it_too(self):
        connect, _chosen = ai_connect.chain(self.dir)
        status, body = connect.get()
        self.assertEqual(200, status)
        self.assertIn(WORDS, repr(body))

    def test_codex_says_it_before_its_own_home_check(self):
        with mock.patch.object(ai_codex, "home_problem", return_value=ai_codex.ODD_HOME):
            self.assertEqual((None, WORDS), ai_codex.CodexCommand().command())

    def test_ask_clark(self):
        request = ask.build_request("How is the plan?", [ask.Passage("report: actions", "ABC-A-001 Send the plan")])
        for command in (ask_claude.ClaudeCommand(), ai_codex.CodexCommand()):
            self.assertEqual(ask.Failure(WORDS), command.ask(request))
            got = command.status()
            self.assertFalse(got["connected"])
            self.assertTrue(got["why"].startswith(WORDS), got)


class Dialogs(InDocker):
    def test_choose_an_ask_folder(self):
        class Store:
            def read(self, *_a, **_k):
                return []
        folders = ask_folders.AskFolders(self.dir / "a.db", [], data_dir=self.dir)
        status, body = folders.choose(Store(), "ABC")
        self.assertEqual(409, status)
        self.assertEqual(ask_folders.MESSAGES["no_window_docker"], body["message"])
        self.assertIn("The folder window needs the Mac, so it can't open when clark runs in Docker.", body["message"])

    def test_show_the_log_folder_in_finder(self):
        class Log:
            folder = self.dir / "logs"
        status, body = log_routes.Logs(Log()).open_folder()
        self.assertEqual(503, status)
        self.assertEqual(WORDS, body["message"])

    def test_choose_the_update_file(self):
        service = updater.Updater(self.dir, self.dir / "a.db", 8765, app_dir=self.dir, system="mac", version="1.0.0", schema=2,
                                  downloads=self.dir)
        with mock.patch.object(service, "_blocked", return_value=None):
            status, body = service.review({"from": "file"})
        self.assertEqual(WORDS, body["message"], (status, body))

    def test_the_old_generic_words_stay_when_it_is_not_docker(self):
        self.assertEqual(updater.MESSAGES["dialog"], pl.refusal_words(pl.PlatformError("x"), updater.MESSAGES["dialog"]))


class Help(unittest.TestCase):
    def test_the_connect_and_docker_guides_quote_the_sentence_and_the_command(self):
        import json
        raw = json.loads((SRC.parent / "src" / "clark" / "page" / "src" / "help" / "helpContent.json").read_text(encoding="utf-8"))
        found = {}

        def walk(node):
            if isinstance(node, dict):
                if node.get("id") in ("connect-claude-or-chatgpt", "run-clark-with-docker"):
                    found[node["id"]] = " ".join(node["s"])
                for v in node.values():
                    walk(v)
            elif isinstance(node, list):
                for v in node:
                    walk(v)
        walk(raw)
        self.assertEqual(2, len(found))
        for text in found.values():
            self.assertIn(WORDS, text)


if __name__ == "__main__":
    unittest.main()
