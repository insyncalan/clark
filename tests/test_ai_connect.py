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
from clark import ai_codex, ai_connect as ac, ai_providers, ask, ask_claude, settings


class FakeProvider:
    def __init__(self, name="claude", label="Claude", models=ask_claude.MODELS, signed_in=True):
        self.name, self.label, self._models, self.signed_in = name, label, models, signed_in
        self.asked, self.preferred, self.stops = [], [], []
        self.command = type("C", (), {"lock": threading.Lock()})()

    def models(self):
        return self._models

    def status(self):
        return {"connected": self.signed_in, "why": "" if self.signed_in else f"Open Terminal and sign in to {self.label}."}

    def ask(self, request, model=None, prefer=False):
        self.asked.append(model)
        self.preferred.append(prefer)
        return f"answer from {self.label}"

    def stop(self, owner=None):
        self.stops.append(owner)
        return False


def FakeClaude(signed_in=True):
    return FakeProvider(signed_in=signed_in)


def FakeChatGPT(signed_in=True):
    return FakeProvider("chatgpt", "ChatGPT", ai_codex.MODELS, signed_in)


class Base(unittest.TestCase):
    def setUp(self):
        self.d = Path(os.path.realpath(tempfile.mkdtemp(prefix="clark-test-")))
        self.addCleanup(shutil.rmtree, self.d, True)
        self.claude, self.chatgpt = FakeClaude(), FakeChatGPT()
        self.connect, self.chain = ac.chain(self.d, self.claude, self.chatgpt)

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
        self.assertFalse(b["chatgpt"]["connected"], "a second company is the person's own choice")
        self.assertEqual(b["active"], "Claude")

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
        self.assertEqual(self.claude.stops, [None], "a question running on it ends")
        self.assertIn("still signed in", b["message"])
        status, b = self.connect.connect({"provider": "claude"})
        self.assertEqual(status, 200)
        self.assertTrue(b["claude"]["connected"])

    def test_nothing_but_the_one_provider_and_the_one_field(self):
        for body in (None, [], {}, {"provider": "claude", "x": 1}, {"provider": 1}):
            self.assertEqual(self.connect.connect(body)[0], 400, body)
            self.assertEqual(self.connect.disconnect(body)[0], 400, body)
        self.assertEqual(self.connect.connect({"provider": "gemini"})[1]["code"], "no_provider")


class TheModel(Base):
    def test_a_model_is_saved_and_read_back_and_fable_does_not_ask(self):
        status, b = self.connect.choose({"model": "fable"})
        self.assertEqual((status, b["model"]), (200, "fable"))
        self.assertEqual(self.connect.pick()[1], "fable")

    def test_a_smaller_model_asks_first_and_the_answer_is_remembered(self):
        status, b = self.connect.choose({"model": "haiku"})
        self.assertEqual((status, b["code"]), (409, "weaker"))
        self.assertEqual(self.connect.pick()[1], "sonnet", "asking changes nothing")
        self.assertEqual(self.connect.choose({"model": "haiku", "accept": True})[0], 200)
        self.assertEqual(self.connect.pick()[1], "haiku")
        self.connect.choose({"model": "sonnet"})
        self.assertEqual(self.connect.choose({"model": "haiku"})[0], 200, "already said yes")

    def test_text_never_becomes_a_model(self):
        for body in ({"model": "--dangerous"}, {"model": "gpt"}, {"model": 1}, {"model": "opus", "accept": False}, {"model": "opus", "x": 1}, {}, None):
            self.assertEqual(self.connect.choose(body)[0], 400, body)
        self.assertFalse((self.d / settings.FILE).exists())

    def test_a_bad_value_in_the_file_reads_as_the_recommended_model(self):
        (self.d / settings.FILE).write_text(json.dumps({settings.AI_MODEL: "--evil", settings.AI_CLAUDE_OFF: "yes", settings.AI_ACCEPTED: "haiku"}), encoding="utf-8")
        self.assertEqual(self.connect.pick()[1], "sonnet")
        self.assertIs(self.connect.pick()[0], self.claude)
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
        self.assertEqual(self.chain.ask(self.request()), "answer from Claude")
        self.connect.choose({"model": "fable"})
        self.chain.ask(self.request())
        self.assertEqual(self.claude.asked, ["sonnet", "fable"])
        self.assertEqual(self.claude.preferred, [True, False], "the default is only preferred; a choice is not")

    def test_the_panels_line_for_disconnected_is_these_words(self):
        words = (Path(SRC) / "clark" / "page" / "src" / "edit" / "askWords.js").read_text(encoding="utf-8")
        self.assertIn(f'DISCONNECTED_LINE = "{ac.OFF_WORDS}"', words)

    def test_while_disconnected_nothing_is_asked_and_the_status_says_so(self):
        self.connect.disconnect({"provider": "claude"})
        self.assertEqual(self.chain.ask(self.request()), ask.Failure(ac.OFF_WORDS))
        self.assertEqual(self.claude.asked, [])
        self.assertEqual(self.chain.status(), {"connected": False, "why": ac.OFF_WORDS})

    def test_stop_reaches_every_provider_and_the_lock_is_the_active_ones(self):
        self.assertIs(self.chain.lock, self.claude.command.lock)
        self.chain.stop("me")
        self.assertEqual((self.claude.stops, self.chatgpt.stops), (["me"], ["me"]))

    def test_the_real_providers_fit_the_chain(self):
        self.assertTrue(issubclass(ai_providers.ClaudeSubscription, ai_providers.Provider))
        self.assertTrue(issubclass(ai_providers.ChatGPTSubscription, ai_providers.Provider))
        self.assertIsInstance(self.chain, ask.Provider)


class Both(Base):
    def test_chatgpt_is_off_until_connected_then_its_models_are_offered_and_the_model_chooses_the_provider(self):
        self.assertEqual(self.connect.choose({"model": "gpt-6.1-sol"})[1]["code"], "not_connected")
        status, b = self.connect.connect({"provider": "chatgpt"})
        self.assertEqual(status, 200)
        self.assertTrue(b["chatgpt"]["connected"])
        self.assertIn("gpt-6.1-sol", [m["id"] for m in b["models"]])
        self.assertEqual(b["active"], "Claude", "connecting one doesn't move asking to it")
        self.chain.ask(self.request())
        self.assertEqual(self.claude.asked, ["sonnet"])
        self.connect.choose({"model": "gpt-6.1-sol"})
        self.chain.ask(self.request())
        self.assertEqual(self.chatgpt.asked, ["gpt-6.1-sol"])
        self.assertEqual(self.chain.label, "ChatGPT")

    def test_with_claude_not_signed_in_connecting_chatgpt_makes_it_the_one_asked(self):
        self.claude.signed_in = False
        _, b = self.connect.connect({"provider": "chatgpt"})
        self.assertEqual(b["model"], "gpt-6.1-sol")
        self.assertIn("GPT-6.1 Sol", b["message"])
        self.chain.ask(self.request())
        self.assertEqual(self.chatgpt.asked, ["gpt-6.1-sol"])

    def test_disconnecting_the_one_in_use_never_moves_to_the_other_silently_only_to_what_is_connected(self):
        self.connect.connect({"provider": "chatgpt"})
        self.connect.choose({"model": "gpt-6.1-sol"})
        _, b = self.connect.disconnect({"provider": "chatgpt"})
        self.assertEqual(self.chatgpt.stops, [None])
        self.assertEqual(settings.ai_read(self.d)["model"], "")
        self.assertIn("still signed in to ChatGPT", b["message"])
        self.chain.ask(self.request())
        self.assertEqual((self.claude.asked, self.chatgpt.asked), (["sonnet"], []))

    def test_with_both_disconnected_nothing_is_asked(self):
        self.connect.disconnect({"provider": "claude"})
        self.assertEqual(self.chain.ask(self.request()), ask.Failure(ac.OFF_WORDS))
        self.assertEqual(self.chain.status(), {"connected": False, "why": ac.OFF_WORDS})
        self.assertEqual(self.connect.view()["active"], "")

    def test_chatgpts_smaller_models_ask_first(self):
        self.connect.connect({"provider": "chatgpt"})
        for model in ("gpt-6-luna", "gpt-6.1-terra"):
            self.assertEqual(self.connect.choose({"model": model})[1]["code"], "weaker", model)
        self.assertEqual(self.connect.choose({"model": "gpt-6-astra"})[0], 200)


class TheFileLock(Base):
    def test_every_setter_takes_the_one_lock_so_none_is_lost(self):
        for setter in (settings.set_backups_kept, settings.set_profile, settings.set_backup_copy_folder, settings.ai_write):
            self.assertTrue(hasattr(setter, "__wrapped__"), setter.__name__)
        source = Path(settings.__file__).read_text(encoding="utf-8")
        self.assertEqual(source.count("platform.write_file("), 4, "a new writer needs the lock too")

    def test_two_at_once_keep_both(self):
        threads = [threading.Thread(target=settings.ai_write, args=(self.d, {"model": "fable"})), threading.Thread(target=settings.set_profile, args=(self.d, "Sam Lee", ""))]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(settings.ai_read(self.d)["model"], "fable")
        self.assertEqual(settings.read(self.d)["profile_name"], "Sam Lee")


class TheSizes(unittest.TestCase):
    def test_chatgpt_has_its_own_limit_per_model(self):
        prov = ai_providers.ChatGPTSubscription(command=FakeProviderCommand())
        self.assertEqual(prov.most_chars("gpt-6.1-sol"), 250000)
        self.assertEqual(prov.most_chars("gpt-6-luna"), 136000)
        got = prov.ask(ask.Request(text="x" * 136001, question="q"), "gpt-6-luna")
        self.assertEqual(got, ask.Failure(ai_providers.TOO_BIG.format(model="GPT-6 Luna")))


class FakeProviderCommand:
    provider, models = "chatgpt", ai_codex.MODELS


class Words(Base):
    def test_the_card_says_where_the_passages_go_and_what_they_cost(self):
        intro = self.connect.get()[1]["intro"]
        self.assertEqual(intro, ac.CARD_INTRO)
        for words in ("leave this computer", "go to the one you choose", "count against that plan", "No password or key is kept"):
            self.assertIn(words, intro)

    def test_nothing_says_a_key_or_a_password_is_kept_and_no_answer_holds_one(self):
        self.assertNotIn("key", json.dumps(self.connect.get()[1]["claude"]))
        for line in (ac.DISCONNECTED, ac.CONNECTED, ac.USING, ac.WEAKER, ac.OFF_WORDS):
            self.assertNotIn("WORDING", line)


if __name__ == "__main__":
    unittest.main()
