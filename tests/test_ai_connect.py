"""#54, #446: Settings › AI's logic and the provider chain, with a fake provider. No sign-in, no model, no network.

Run: python3 dev/run_tests.py test_ai_connect
"""
import json
import os
import shutil
import tempfile
import threading
import unittest
from pathlib import Path

from _paths import SRC  # noqa: F401
from clark import ai_connect as ac, ai_providers, ask, ask_claude, settings


class FakeClaude:
    name = "claude"

    def __init__(self, signed_in=True):
        self.signed_in = signed_in
        self.asked = []
        self.stops = []
        self.command = type("C", (), {"lock": threading.Lock()})()

    def status(self):
        return {"connected": self.signed_in, "why": "" if self.signed_in else "Open Terminal, type claude and sign in."}

    def ask(self, request, model=None):
        self.asked.append(model)
        return "answer"

    def stop(self, owner=None):
        self.stops.append(owner)


class Base(unittest.TestCase):
    def setUp(self):
        self.d = Path(os.path.realpath(tempfile.mkdtemp(prefix="clark-test-")))
        self.addCleanup(shutil.rmtree, self.d, True)
        self.claude = FakeClaude()
        self.connect, self.chain = ac.chain(self.d, self.claude)

    def request(self):
        return ask.Request(text="q", question="q")


class TheCard(Base):
    def test_signed_in_is_connected_from_the_start_with_the_recommended_model(self):
        status, b = self.connect.get()
        self.assertEqual(status, 200)
        self.assertTrue(b["claude"]["connected"])
        self.assertEqual(b["model"], "sonnet")
        self.assertEqual([m["id"] for m in b["models"] if m["recommended"]], ["sonnet"])
        self.assertEqual({m["id"] for m in b["models"]}, set(ask_claude.MODELS))
        self.assertTrue(b["openai"]["later"])
        self.assertFalse(b["openai"]["connected"])

    def test_not_signed_in_lists_no_models_and_says_what_to_do(self):
        self.claude.signed_in = False
        _, b = self.connect.get()
        self.assertFalse(b["claude"]["connected"])
        self.assertEqual(b["models"], [])
        self.assertIn("sign in", b["claude"]["why"])
        status, got = self.connect.connect({"provider": "claude"})
        self.assertEqual((status, got["code"]), (409, "not_signed_in"))
        self.assertFalse((self.d / settings.FILE).exists(), "a refusal writes nothing")

    def test_disconnect_stops_clark_and_keeps_the_sign_in_and_connect_brings_it_back(self):
        status, b = self.connect.disconnect({"provider": "claude"})
        self.assertEqual(status, 200)
        self.assertFalse(b["claude"]["connected"])
        self.assertTrue(b["claude"]["signed_in"], "clark never signs the person out")
        self.assertIn("still signed in", b["message"])
        status, b = self.connect.connect({"provider": "claude"})
        self.assertEqual(status, 200)
        self.assertTrue(b["claude"]["connected"])

    def test_nothing_but_the_one_provider_and_the_one_field(self):
        for body in (None, [], {}, {"provider": "claude", "x": 1}, {"provider": 1}):
            self.assertEqual(self.connect.connect(body)[0], 400, body)
            self.assertEqual(self.connect.disconnect(body)[0], 400, body)
        self.assertEqual(self.connect.connect({"provider": "openai"})[1]["code"], "no_provider")


class TheModel(Base):
    def test_a_model_is_saved_and_read_back_and_fable_does_not_ask(self):
        status, b = self.connect.choose({"model": "fable"})
        self.assertEqual((status, b["model"]), (200, "fable"))
        self.assertEqual(self.connect.model(), "fable")

    def test_a_smaller_model_asks_first_and_the_answer_is_remembered(self):
        status, b = self.connect.choose({"model": "haiku"})
        self.assertEqual((status, b["code"]), (409, "weaker"))
        self.assertEqual(self.connect.model(), "sonnet", "asking changes nothing")
        self.assertEqual(self.connect.choose({"model": "haiku", "accept": True})[0], 200)
        self.assertEqual(self.connect.model(), "haiku")
        self.connect.choose({"model": "sonnet"})
        self.assertEqual(self.connect.choose({"model": "haiku"})[0], 200, "already said yes")

    def test_text_never_becomes_a_model(self):
        for body in ({"model": "--dangerous"}, {"model": "gpt"}, {"model": 1}, {"model": "opus", "accept": False}, {"model": "opus", "x": 1}, {}, None):
            self.assertEqual(self.connect.choose(body)[0], 400, body)
        self.assertFalse((self.d / settings.FILE).exists())

    def test_a_bad_value_in_the_file_reads_as_the_recommended_model(self):
        (self.d / settings.FILE).write_text(json.dumps({settings.AI_MODEL: "--evil", settings.AI_CLAUDE_OFF: "yes", settings.AI_ACCEPTED: "haiku"}), encoding="utf-8")
        self.assertEqual(self.connect.model(), "sonnet")
        self.assertTrue(self.connect.on())
        self.assertEqual(self.connect.choose({"model": "haiku"})[0], 409, "a bad list accepts nothing")

    def test_no_model_while_disconnected(self):
        self.connect.disconnect({"provider": "claude"})
        self.assertEqual(self.connect.choose({"model": "opus"})[1]["code"], "not_connected")

    def test_a_file_that_cannot_be_read_is_never_replaced(self):
        (self.d / settings.FILE).write_text("{not json", encoding="utf-8")
        status, b = self.connect.choose({"model": "fable"})
        self.assertEqual((status, b["code"]), (409, "unreadable"))
        self.assertEqual((self.d / settings.FILE).read_text(encoding="utf-8"), "{not json")

    def test_other_settings_are_kept(self):
        (self.d / settings.FILE).write_text(json.dumps({"profile_name": "Sam Lee"}), encoding="utf-8")
        self.connect.choose({"model": "fable"})
        self.assertEqual(json.loads((self.d / settings.FILE).read_text(encoding="utf-8"))["profile_name"], "Sam Lee")


class TheChain(Base):
    def test_every_question_uses_the_model_chosen_at_that_moment(self):
        self.assertEqual(self.chain.ask(self.request()), "answer")
        self.connect.choose({"model": "fable"})
        self.chain.ask(self.request())
        self.assertEqual(self.claude.asked, ["sonnet", "fable"])

    def test_while_disconnected_nothing_is_asked_and_the_status_says_so(self):
        self.connect.disconnect({"provider": "claude"})
        self.assertEqual(self.chain.ask(self.request()), ask.Failure(ac.OFF_WORDS))
        self.assertEqual(self.claude.asked, [])
        self.assertEqual(self.chain.status(), {"connected": False, "why": ac.OFF_WORDS})

    def test_it_shares_the_commands_lock_and_stop_and_name(self):
        self.assertIs(self.chain.lock, self.claude.command.lock)
        self.chain.stop("me")
        self.assertEqual(self.claude.stops, ["me"])
        self.assertEqual(self.chain.name, "claude")

    def test_the_real_provider_fits_the_chain(self):
        self.assertTrue(issubclass(ai_providers.ClaudeSubscription, ai_providers.Provider))
        self.assertIsInstance(self.chain, ask.Provider)


class Words(Base):
    def test_nothing_says_a_key_or_a_password_is_kept_and_no_answer_holds_one(self):
        self.assertNotIn("key", json.dumps(self.connect.get()[1]["claude"]))
        for line in (ac.DISCONNECTED, ac.CONNECTED, ac.USING, ac.WEAKER, ac.OFF_WORDS):
            self.assertNotIn("WORDING", line)


if __name__ == "__main__":
    unittest.main()
