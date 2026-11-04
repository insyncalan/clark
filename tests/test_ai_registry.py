"""#643 slice 2: the AI providers live in an ordered registry (ai_connect.REGISTRY), and every loop, dict and tile is driven by it. A fake third
provider is registered in a COPY of the registry and the card, the choice and the chain handle it. No real network, no process, no settings file
(the saved settings are an in-memory dict, because settings.py names only today's four keys).

Run: python3 dev/run_tests.py test_ai_registry
"""
import json
import os
import tempfile
import unittest
from unittest import mock

from _paths import SRC  # noqa: F401
from clark import ai_connect as ac, ai_providers, ask, ask_claude, settings
from test_ai_connect import FakeChatGPT, FakeClaude, FakeProvider

THIRD = "third"
THIRD_MODELS = ("t-big", "t-small")


def third_entry(**kw):
    args = dict(name=THIRD, key="third_on", inverted=False, recommended="t-big", labels={"t-big": "Third Big", "t-small": "Third Small"},
                smaller=("t-small",), make=lambda: FakeProvider(THIRD, "Third", THIRD_MODELS), route="key")
    args.update(kw)
    return ac.Entry(**args)


class Memory:
    """settings.ai_read / ai_write over a dict."""
    def __init__(self):
        self.saved = {"model": "", "claude_off": False, "chatgpt_on": False, "accepted": [], "third_on": False}

    def read(self, _dir):
        return {**self.saved, "accepted": list(self.saved["accepted"])}

    def write(self, _dir, changes):
        self.saved.update(changes)


class TheRealRegistry(unittest.TestCase):
    def test_the_order_and_the_names_are_today_s(self):
        self.assertEqual([e.name for e in ac.REGISTRY], ["claude", "chatgpt"])
        self.assertEqual([e.key for e in ac.REGISTRY], ["claude_off", "chatgpt_on"])
        self.assertEqual([e.route for e in ac.REGISTRY], ["subscription", "subscription"])
        self.assertEqual(ac.RECOMMENDED, {"claude": "sonnet", "chatgpt": ac.ai_codex.RECOMMENDED})
        self.assertEqual(ac.SMALLER, ("haiku", *ac.ai_codex.SMALLER))
        self.assertEqual(list(ac.LABELS), [*ask_claude.MODELS, *ac.ai_codex.MODEL_NAMES])

    def test_on_and_off_are_written_in_the_saved_settings_own_words(self):
        claude, chatgpt = ac.REGISTRY
        self.assertEqual(claude.setting(True), {"claude_off": False})
        self.assertEqual(claude.setting(False), {"claude_off": True})
        self.assertEqual(chatgpt.setting(True), {"chatgpt_on": True})
        self.assertEqual(chatgpt.setting(False), {"chatgpt_on": False})
        self.assertIs(claude.is_on({"claude_off": False}), True)
        self.assertIs(chatgpt.is_on({"chatgpt_on": False}), False)

    def test_the_provider_classes_are_found_by_name_through_one_table(self):
        self.assertEqual(list(ai_providers.KINDS), ["claude", "chatgpt"])
        with mock.patch.dict(ai_providers.KINDS, {THIRD: lambda **seams: ("third", seams)}):
            self.assertEqual(ai_providers.provider_for(THIRD, x=1), ("third", {"x": 1}))

    def test_a_provider_without_a_command_is_accepted_by_chosen(self):
        bare = type("Bare", (), {"label": "B", "stop": lambda self, owner=None: False})()
        chosen = ai_providers.Chosen((FakeClaude(), bare), lambda: None, "off")
        self.assertIs(chosen.status()["connected"], False)


class AThirdProviderIsHandledWithoutTouchingTheFunctions(unittest.TestCase):
    def setUp(self):
        self.mem = Memory()
        for patch in (mock.patch.object(settings, "ai_read", self.mem.read), mock.patch.object(settings, "ai_write", self.mem.write)):
            patch.start()
            self.addCleanup(patch.stop)
        self.registry = ac.REGISTRY + (third_entry(),)
        self.claude, self.chatgpt, self.third = FakeClaude(), FakeChatGPT(), FakeProvider(THIRD, "Third", THIRD_MODELS)
        self.connect, self.chain = ac.chain("unused", self.claude, self.chatgpt, self.registry, {THIRD: self.third})

    def test_the_real_registry_is_not_changed_by_the_copy(self):
        self.assertEqual(len(ac.REGISTRY), 2)
        self.assertEqual(len(self.registry), 3)

    def test_the_chain_holds_all_three_and_they_share_one_lock(self):
        self.assertEqual(len(self.chain.providers), 3)
        self.assertIs(self.third.command.lock, self.chain.lock)
        self.assertIs(self.claude.command.lock, self.chain.lock)

    def test_the_tile_is_added_last_and_the_other_two_keep_their_place(self):
        body = self.connect.get()[1]
        self.assertEqual([k for k in body if k in ("claude", "chatgpt", THIRD)], ["claude", "chatgpt", THIRD])
        self.assertEqual(body[THIRD], {"connected": False, "signed_in": True, "why": ""})
        self.assertEqual([m["provider"] for m in body["models"]], ["claude"] * len(ask_claude.MODELS))

    def test_is_on_reads_the_third_entry_s_own_setting(self):
        self.assertIs(self.connect.is_on(THIRD), False)
        self.mem.saved["third_on"] = True
        self.assertIs(self.connect.is_on(THIRD), True)

    def test_connect_turns_it_on_and_chooses_its_recommended_model_with_its_label(self):
        self.mem.saved["claude_off"] = True               # nothing else is on, so it answers alone
        status, body = self.connect.connect({"provider": THIRD})
        self.assertEqual(status, 200)
        self.assertEqual(self.mem.saved["third_on"], True)
        self.assertEqual(self.mem.saved["model"], "t-big")
        self.assertEqual(body["message"], ac.CONNECTED.format(model="Third Big"))
        self.assertEqual([(m["id"], m["label"], m["recommended"]) for m in body["models"]], [("t-big", "Third Big", True), ("t-small", "Third Small", False)])
        self.assertEqual(body["active"], "Third")

    def test_connect_refuses_a_third_that_is_not_signed_in(self):
        self.third.signed_in = False
        status, body = self.connect.connect({"provider": THIRD})
        self.assertEqual((status, body["code"]), (409, "not_signed_in"))
        self.assertIs(self.mem.saved["third_on"], False)

    def test_pick_uses_the_chosen_model_s_owner_and_then_the_registry_order(self):
        self.mem.saved.update(third_on=True, model="t-big")
        provider, model, prefer = self.connect.pick()
        self.assertEqual((provider, model, prefer), (self.third, "t-big", False))
        self.mem.saved.update(model="", claude_off=True)
        self.assertEqual(self.connect.pick(), (self.third, "t-big", True))          # the fallback is the registry's order: Claude is off, ChatGPT off, the third is next
        self.mem.saved.update(third_on=False)
        self.assertIsNone(self.connect.pick())

    def test_a_smaller_model_of_the_third_asks_first_and_is_remembered(self):
        self.mem.saved["third_on"] = True
        status, body = self.connect.choose({"model": "t-small"})
        self.assertEqual((status, body["code"]), (409, "weaker"))
        self.assertEqual(body["message"], ac.WEAKER.format(model="Third Small"))
        status, body = self.connect.choose({"model": "t-small", "accept": True})
        self.assertEqual(status, 200)
        self.assertEqual((self.mem.saved["model"], self.mem.saved["accepted"]), ("t-small", ["t-small"]))

    def test_choose_refuses_a_model_of_a_third_that_is_off(self):
        status, body = self.connect.choose({"model": "t-big"})
        self.assertEqual((status, body["code"]), (409, "not_connected"))

    def test_disconnect_turns_it_off_clears_its_model_and_ends_its_run(self):
        self.mem.saved.update(third_on=True, model="t-big")
        status, body = self.connect.disconnect({"provider": THIRD})
        self.assertEqual(status, 200)
        self.assertEqual((self.mem.saved["third_on"], self.mem.saved["model"]), (False, ""))
        self.assertEqual(self.third.stops, [None])
        self.assertEqual(body["message"], ac.DISCONNECTED.format(name="Third"))

    def test_the_third_answers_a_question_through_the_chain(self):
        self.mem.saved.update(third_on=True, model="t-big")
        self.assertEqual(self.chain.ask(ask.Request(text="q", question="q")), "answer from Third")
        self.assertEqual(self.third.asked, ["t-big"])
        self.chain.stop("me")
        self.assertEqual(self.third.stops, ["me"])

    def test_an_unregistered_name_is_still_refused(self):
        plain, _ = ac.chain("unused", self.claude, self.chatgpt)
        self.assertEqual(plain.connect({"provider": THIRD})[1]["code"], "no_provider")
        self.assertEqual(list(plain.providers), ["claude", "chatgpt"])

    def test_a_hook_on_the_entry_changes_what_connecting_needs(self):
        calls = []
        entry = third_entry()
        entry.check = lambda provider: calls.append(provider) or {"connected": False, "why": "needs a key"}
        connect, _ = ac.chain("unused", self.claude, self.chatgpt, ac.REGISTRY + (entry,), {THIRD: self.third})
        status, body = connect.connect({"provider": THIRD})
        self.assertEqual((status, body["code"], body["message"]), (409, "not_signed_in", "needs a key"))
        self.assertEqual(calls, [self.third])


class WhatDidNotChange(unittest.TestCase):
    """The card's answer for the two real providers: the same keys in the same order, and the saved setting names."""
    def test_the_card_json_keys_and_their_order(self):
        mem = Memory()
        with mock.patch.object(settings, "ai_read", mem.read), mock.patch.object(settings, "ai_write", mem.write):
            connect, _ = ac.chain("unused", FakeClaude(), FakeChatGPT())
            body = connect.get()[1]
        self.assertEqual(list(body), ["ok", "claude", "chatgpt", "model", "models", "active", "intro", "message"])
        self.assertEqual(list(body["claude"]), ["connected", "signed_in", "why"])
        self.assertEqual(list(body["models"][0]), ["id", "label", "provider", "recommended"])
        json.dumps(body)

    def test_the_saved_setting_names_are_the_same(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual({*settings.ai_read(d)}, {"model", "claude_off", "chatgpt_on", "accepted"})
            settings.ai_write(d, {"claude_off": True, "chatgpt_on": True})
            self.assertEqual(sorted(json.loads(open(os.path.join(d, "settings.json"), encoding="utf-8").read())), ["ai_chatgpt_on", "ai_claude_off"])


if __name__ == "__main__":
    unittest.main()
