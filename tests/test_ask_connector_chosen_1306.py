"""Row 1306: the Used line reaches the answer through the real provider the app uses (ai_providers.Chosen), not only through a bare command.
Real AskService + real Chosen + real ClaudeSubscription/ClaudeCommand; only the start of the command is faked. Nothing real is started.

Run: python3 dev/run_tests.py test_ask_connector_chosen_1306
"""
import os
import shutil
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

from _paths import SRC  # noqa: F401

import _publish_fixture as plant
from clark import ai_providers, ask, ask_claude as ac, ask_connectors, ask_service
from clark.store import open_store
from test_ask_connector_wiring import LIST_M365, P, PATH, final, got, stream, use

LINE = "Used: Mail"
MAIL = [use("1", f"{P}__outlook_email_search"), got("1", '[{"s": "a"}, {"s": "b"}, {"s": "c"}]')]


class Fake:
    """A provider-shaped stand-in with no command attributes at all (the ChatGPT case)."""
    def __init__(self):
        self.command = types.SimpleNamespace(provider="chatgpt")
        self.label = "ChatGPT"

    def status(self):
        return {"connected": True, "why": ""}

    def ask(self, request, model=None, prefer=False):
        return ask.Failure("no") if self.fail else "an answer"

    fail = False

    def stop(self, owner=None):
        return False


class Through(unittest.TestCase):
    def setUp(self):
        ask_connectors.clear_cache()
        self.d = Path(os.path.realpath(tempfile.mkdtemp(prefix="clark-test-")))
        self.addCleanup(shutil.rmtree, self.d, True)
        self.db = plant.build_db(self.d / "clark.db")
        self.command = ac.ClaudeCommand(places=(), env={}, limit=5)
        self.command.connector_runner = lambda: LIST_M365
        self.claude = ai_providers.ClaudeSubscription(self.command)
        self.chosen_is = self.claude
        self.chosen = ai_providers.Chosen((self.claude,), lambda: (self.chosen_is, None, True), "off")
        self.out = stream(*MAIL, final("The plan is on track.\nCITE: P1"))
        for p in (mock.patch.object(self.command, "usable", return_value=(PATH, None)),
                  mock.patch.object(ac, "run", side_effect=lambda *a, **k: ("ok", self.out, 0))):
            p.start()
            self.addCleanup(p.stop)
        self.service = ask_service.AskService(self.db, self.chosen, [])

    def turn_on(self, name="mail"):
        s = open_store(self.db, onedrive_roots=[])
        try:
            s.con.execute("UPDATE connector_switches SET is_on = 1 WHERE connector = ?", (name,))
            s.con.commit()
        finally:
            s.close()

    def ask(self):
        status, body = self.service.ask({"project": "PUB", "question": "What is the state of the plan?"})
        self.assertEqual(status, 200, body)
        return body

    def test_the_used_line_reaches_the_notes_through_chosen(self):
        self.turn_on()
        body = self.ask()
        self.assertTrue(body["ok"], body)
        self.assertEqual(body["used"]["line"], LINE)
        self.assertEqual(body["notes"][-1], LINE)
        self.assertEqual(self.chosen.last_line.text, LINE)

    def test_before_any_question_there_is_no_line(self):
        self.assertIsNone(self.chosen.last_line)

    def test_no_connector_on_means_no_line(self):
        body = self.ask()
        self.assertNotIn("used", body)
        self.assertIsNone(self.chosen.last_line)

    def test_the_line_of_the_last_question_is_not_kept_for_the_next(self):
        self.turn_on()
        self.ask()
        self.assertIsNotNone(self.chosen.last_line)
        self.out = stream(final("Fine.\nCITE: P1"))
        self.command.last_line = "stale"           # the command keeps it until its next run; Chosen must not serve an old one
        s = open_store(self.db, onedrive_roots=[])
        try:
            s.con.execute("UPDATE connector_switches SET is_on = 0")
            s.con.commit()
        finally:
            s.close()
        self.assertNotIn("used", self.ask())
        self.assertIsNone(self.chosen.last_line)

    def test_a_chatgpt_run_has_no_line_even_after_a_claude_run(self):
        self.turn_on()
        self.ask()
        other = Fake()
        self.chosen = ai_providers.Chosen((self.claude, other), lambda: (other, None, True), "off")
        self.service = ask_service.AskService(self.db, self.chosen, [])
        self.assertEqual(self.chosen.ask(ask.Request(text="Q", question="Q")), "an answer")
        self.assertIsNone(self.chosen.last_line)

    def test_a_failed_or_unconnected_ask_has_no_line(self):
        self.turn_on()
        self.ask()
        self.command.last_line = "stale"
        other = Fake()
        other.fail = True
        other.command.last_line = "stale"           # a failed run whose command still holds a line
        self.chosen_is = other
        self.chosen = ai_providers.Chosen((self.claude, other), lambda: (other, None, True), "off")
        self.assertIsInstance(self.chosen.ask(ask.Request(text="Q", question="Q")), ask.Failure)
        self.assertIsNone(self.chosen.last_line)
        self.chosen.last_line = "old"
        self.chosen_is = None
        self.chosen.pick = lambda: None
        self.assertIsInstance(self.chosen.ask(ask.Request(text="Q", question="Q")), ask.Failure)
        self.assertIsNone(self.chosen.last_line)


if __name__ == "__main__":
    unittest.main()
