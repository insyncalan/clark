"""Row 1293: a full question is cut to what the chosen model takes and said, never refused for the model's window.

Run: python3 dev/run_tests.py test_ask_budget_model_1293
Fictional data only. The command is a fake; nothing is sent anywhere.
"""
import datetime
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _paths import SRC  # noqa: F401

import _publish_fixture as plant
from clark import ai_codex, ai_providers, ask, ask_service, ask_passages, ask_data

DAY = datetime.date(2026, 11, 20)
FULL = 400      # passages of 4,000 characters: 1,600,000, more than the whole budget
BODY = {"project": "PUB", "question": "What is the state of the plan?"}


class Fake:
    """Stands in for a command: keeps what it was asked and answers."""
    def __init__(self, provider, models):
        self.provider, self.models, self.lock, self.sent = provider, models, None, []

    def status(self):
        return {"connected": True, "why": ""}

    def ask(self, request, model=None, prefer=False):
        self.sent.append(request)
        return "Fine.\nCITE: P1"


def many(question, budget):
    out = [ask.Passage(f"notes/f{i}.md", f"{i:04d} " + "x" * (ask.MAX_PASSAGE - 5)) for i in range(FULL)]
    chosen, left = ask_data.choose(out, question, budget)
    return chosen, left


class Cut(unittest.TestCase):
    def setUp(self):
        self.d = Path(os.path.realpath(tempfile.mkdtemp(prefix="clark-test-")))
        self.addCleanup(shutil.rmtree, self.d, True)
        self.db = plant.build_db(self.d / "clark.db")
        self.budgets = []

        def fake(folders, data_dir, question="", budget=ask.BUDGET, home=None, max_passages=ask.MAX_PASSAGES, leave_out=None):
            self.budgets.append(budget)
            chosen, left = many(question, budget)
            return ask_passages.FolderData(chosen[:max_passages], left + max(0, len(chosen) - max_passages))
        for patch in (mock.patch.object(ask_passages, "folder_data", fake), mock.patch.object(ask, "MAX_PASSAGES", 100000)):
            patch.start()
            self.addCleanup(patch.stop)

    def run_with(self, sub, model, body=BODY):
        service = ask_service.AskService(self.db, None, [])
        service.provider = ai_providers.Chosen([sub], lambda: (sub, model, False), "Not connected.")
        service.today = lambda: DAY
        service.enabled = lambda: True
        status, got = service.ask(dict(body))
        return status, got, sub.command.sent

    def claude(self, contexts=None):
        sub = ai_providers.ClaudeSubscription(Fake("claude", ("sonnet", "opus")))
        if contexts:
            sub.contexts = contexts
        return sub

    def codex(self):
        return ai_providers.ChatGPTSubscription(Fake("codex", tuple(ai_codex.CONTEXT_TOKENS)))

    def check(self, sub, model, cap_budget):
        status, got, sent = self.run_with(sub, model)
        self.assertEqual((status, got.get("ok")), (200, True), got)
        self.assertEqual(len(self.budgets), 1)
        self.assertTrue(cap_budget - ask_service.PROJECT_SHARE <= self.budgets[0] <= cap_budget, (self.budgets, cap_budget))      # the project's own data took its share first
        self.assertEqual(len(sent), 1, "sent once, not refused")
        text = sent[0].text
        self.assertLessEqual(len(text), sub.most_chars(model))
        return got, text

    def test_claude_one_million_tokens_is_cut_to_the_budget_as_before(self):
        got, text = self.check(self.claude(), "sonnet", ask.BUDGET)
        self.assertGreater(len(text), ask.BUDGET - 10000)
        self.assertIn(ask_service.left_out_note(1), got["notes"])

    def test_gpt_61_five_hundred_thousand_tokens_is_cut_to_970000(self):
        got, text = self.check(self.codex(), "gpt-6.1-sol", 970000)
        self.assertGreater(len(text), 960000)
        self.assertIn(ask_service.left_out_note(1), got["notes"])

    def test_gpt_6_two_seventy_two_thousand_tokens_is_cut_to_514000_and_said(self):
        got, text = self.check(self.codex(), "gpt-6-sol", 514000)
        self.assertGreater(len(text), 500000)
        self.assertLessEqual(len(text), 544000)
        self.assertIn(ask_service.left_out_note(1), got["notes"])
        self.assertTrue(all(n for n in got["notes"]))

    def test_nothing_connected_keeps_the_fixed_budget(self):
        service = ask_service.AskService(self.db, ask.StubProvider(reply="Fine.\nCITE: P1"), [])
        service.today = lambda: DAY
        status, got = service.ask(dict(BODY))
        self.assertEqual(status, 200)
        self.assertTrue(ask.BUDGET - ask_service.PROJECT_SHARE <= self.budgets[0] <= ask.BUDGET, self.budgets)

    def test_a_tiny_model_is_refused_only_for_a_question_that_cannot_fit(self):
        sub = self.claude({"sonnet": 1000, "opus": 1000})        # 2,000 characters in all
        status, got, sent = self.run_with(sub, "sonnet", {**BODY, "question": "Q" * 3000})
        self.assertEqual((status, got["ok"], got["message"], sent), (400, False, ask.TOO_MUCH, []))
        status, got, sent = self.run_with(sub, "sonnet", {**BODY, "question": "What is late?"})
        self.assertEqual((status, got["ok"], len(sent)), (200, True, 1), got)
        self.assertLessEqual(len(sent[0].text), 2000)

    def test_a_model_with_room_for_the_overhead_only_cuts_to_nothing_and_still_asks(self):
        sub = self.claude({"sonnet": 15000, "opus": 15000})      # 30,000 characters: the budget is 0
        status, got, sent = self.run_with(sub, "sonnet")
        self.assertEqual((status, got["ok"], self.budgets), (200, True, [0]), got)
        self.assertLessEqual(len(sent[0].text), 30000)


class Handed(Cut):
    """What the service hands on: the project data's budget, the folders' budget and the request cap, exactly."""
    def spy(self, window_tokens):
        seen = {}
        real_data, real_build = ask_data.project_data, ask.build_request

        def data(store, code, question="", budget=ask.BUDGET, as_at=None, limit=None):
            seen["project"] = budget
            return real_data(store, code, question, budget, as_at, limit)

        def build(*a, **k):
            seen["cap"] = k.get("max_request")
            return real_build(*a, **k)
        for patch in (mock.patch.object(ask_data, "project_data", data), mock.patch.object(ask, "build_request", build)):
            patch.start()
            self.addCleanup(patch.stop)
        sub = self.claude({"sonnet": window_tokens, "opus": window_tokens})
        self.run_with(sub, "sonnet")
        return seen

    def test_the_project_data_takes_no_more_than_the_budget_and_the_cap_is_the_window(self):
        seen = self.spy(15005)                       # 30,010 characters: a budget of 10
        self.assertEqual((seen["project"], seen["cap"]), (10, 30010))
        self.assertLessEqual(self.budgets[0], 10)

    def test_a_big_window_hands_on_the_share_and_max_request(self):
        seen = self.spy(1000000)                     # 2,000,000 characters
        self.assertEqual((seen["project"], seen["cap"]), (ask_service.PROJECT_SHARE, ask.MAX_REQUEST))


class Edges(unittest.TestCase):
    def test_the_budget_for_a_window_is_the_window_less_the_overhead_never_more_than_the_budget(self):
        self.assertEqual(ask.REQUEST_OVERHEAD, 30000)
        self.assertEqual(ask.budget_for(None), ask.BUDGET)
        self.assertEqual(ask.budget_for(544000), 514000)
        self.assertEqual(ask.budget_for(1000000), 970000)
        self.assertEqual(ask.budget_for(2000000), ask.BUDGET)
        self.assertEqual(ask.budget_for(ask.MAX_REQUEST), ask.BUDGET)
        self.assertEqual(ask.budget_for(ask.MAX_REQUEST - 1), ask.BUDGET - 1)
        self.assertEqual(ask.budget_for(ask.MAX_REQUEST + 1), ask.BUDGET)
        self.assertEqual(ask.budget_for(30000), 0)
        self.assertEqual(ask.budget_for(30001), 1)
        self.assertEqual(ask.budget_for(10), 0)
        self.assertEqual(ask.budget_for(0), 0)

    def test_the_request_cap_is_the_window_up_to_max_request(self):
        self.assertEqual(ask.request_cap(None), ask.MAX_REQUEST)
        self.assertEqual(ask.request_cap(544000), 544000)
        self.assertEqual(ask.request_cap(ask.MAX_REQUEST), ask.MAX_REQUEST)
        self.assertEqual(ask.request_cap(ask.MAX_REQUEST + 1), ask.MAX_REQUEST)
        self.assertEqual(ask.request_cap(ask.MAX_REQUEST - 1), ask.MAX_REQUEST - 1)

    def test_no_cap_given_means_max_request_as_it_stands(self):
        with mock.patch.object(ask, "MAX_REQUEST", 1200):
            with self.assertRaises(ask.AskRefused):
                ask.build_request("Q?", [ask.Passage("a.md", "x" * 4000)])

    def test_a_request_of_exactly_the_cap_is_built_and_one_more_gives_up_turns_then_is_refused(self):
        size = len(ask.build_request("Q?", []).text)
        self.assertEqual(len(ask.build_request("Q?", [], max_request=size).text), size)
        with self.assertRaises(ask.AskRefused):
            ask.build_request("Q?", [], max_request=size - 1)
        turns = [("user", "a" * 100), ("assistant", "b" * 100)]
        full = ask.build_request("Q?", [], turns)
        self.assertEqual(full.dropped_turns, 0)
        cut = ask.build_request("Q?", [], turns, max_request=len(full.text) - 1)
        self.assertEqual(cut.dropped_turns, 1)
        self.assertEqual(ask.build_request("Q?", [], turns, max_request=len(full.text)).dropped_turns, 0)

    def test_the_provider_still_refuses_a_text_longer_than_the_window_at_exactly_one_over(self):
        sub = ai_providers.ClaudeSubscription(Fake("claude", ("sonnet",)))
        for model, chars in (("sonnet", 2000000),):
            ok = ask.Request(text="a" * chars, question="q", passages=(), hidden={})
            self.assertEqual(sub.most_chars(model), chars)
            self.assertNotEqual(getattr(sub.ask(ok, model), "message", ""), ai_providers.TOO_BIG.format(model="Sonnet"))
            over = ask.Request(text="a" * (chars + 1), question="q", passages=(), hidden={})
            self.assertIn("too much text", sub.ask(over, model).message)

    def test_chosen_gives_the_window_of_the_chosen_model_and_none_when_nothing_is_connected(self):
        sub = ai_providers.ChatGPTSubscription(Fake("codex", tuple(ai_codex.CONTEXT_TOKENS)))
        self.assertEqual(ai_providers.Chosen([sub], lambda: (sub, "gpt-6-sol", False), "off").most_chars(), 544000)
        self.assertEqual(ai_providers.Chosen([sub], lambda: (sub, "gpt-6.1-terra", False), "off").most_chars(), 1000000)
        self.assertEqual(ai_providers.Chosen([sub], lambda: (sub, None, True), "off").most_chars(), 544000)
        self.assertIsNone(ai_providers.Chosen([sub], lambda: None, "off").most_chars())


if __name__ == "__main__":
    unittest.main()
