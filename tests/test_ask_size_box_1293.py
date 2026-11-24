"""Row 1293 (AP2, DoD2): the "Size of one question" box in Settings. 10,000 to 500,000 tokens, saved when left, refused in the approved
sentence with the old value kept, "Use 300,000" only when changed, and the saved value is the one a question is cut to (a smaller model
window still wins). The logic tests need no browser; the page tests need Chrome (1400 and 900).

Run: python3 dev/run_tests.py test_ask_size_box_1293
Fictional data only. The command is a fake; nothing is sent anywhere.
"""
import datetime
import json
import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from _paths import SRC  # noqa: F401
from test_ai_connect import FakeChatGPT, FakeClaude
from test_page import DATA, navigate
from test_server import Running, chrome, wait

import _publish_fixture as plant
from clark import ai_connect as ac, ai_providers, ask, ask_passages, ask_service, page, settings

REFUSAL = "Size of one question must be a whole number from 10,000 to 500,000 tokens."
HELP = ("The most that one question sends to the model, counted in tokens (about 4 characters each). A higher number reads more of a big project "
        "and costs more. Each model has its own limit and the lower one applies.")
LINE = "Size of one question: about {t:,} tokens ({c:,} characters of passages)."


class Fake:
    """Stands in for a command: keeps what it was asked and answers."""
    def __init__(self, provider, models):
        self.provider, self.models, self.lock, self.sent = provider, models, None, []

    def status(self):
        return {"connected": True, "why": ""}

    def ask(self, request, model=None, prefer=False):
        self.sent.append(request)
        return "Fine.\nCITE: P1"


class Box(unittest.TestCase):
    def setUp(self):
        self.d = Path(os.path.realpath(tempfile.mkdtemp(prefix="clark-test-")))
        self.addCleanup(shutil.rmtree, self.d, True)
        self.connect = ac.AiConnect(self.d, FakeClaude(), FakeChatGPT())

    def test_the_size_box_limits_and_refusal_text(self):
        self.assertEqual(self.connect.get()[1]["size_value"], 300_000, "the default")
        for good in (10_000, 20_000, 300_000, 500_000):
            with self.subTest(good=good):
                status, got = self.connect.size({"size": good})
                self.assertEqual((status, got["size_value"], got["size"]), (200, good, LINE.format(t=good, c=good * 4)))
                self.assertEqual(settings.ask_size(self.d), good)
        self.connect.size({"size": 40_000})
        for bad in (5_000, 9_999, 500_001, 600_000, 0, -10_000, "abc", "20000", "", None, True, 12.5, 1e5, [], {"x": 1}):
            with self.subTest(bad=bad):
                status, got = self.connect.size({"size": bad})
                self.assertEqual((status, got["message"]), (400, REFUSAL))
                self.assertEqual(settings.ask_size(self.d), 40_000, "the old value stays, never clamped")
        for body in (None, [], {}, {"size": 20_000, "x": 1}):
            with self.subTest(body=body):
                self.assertEqual(self.connect.size(body)[0], 400)
        self.assertEqual(settings.ask_size(self.d), 40_000)
        view = self.connect.get()[1]
        self.assertEqual((view["size_default"], view["size_range"], view["size_step"], view["size_help"]), (300_000, [10_000, 500_000], 10_000, HELP))

    def test_a_settings_file_with_a_bad_size_reads_as_the_default_and_other_settings_stay(self):
        (self.d / settings.FILE).write_text(json.dumps({"ask_size_value": 7, "profile_name": "Pat"}), encoding="utf-8")
        self.assertEqual(settings.ask_size(self.d), 300_000)
        self.connect.size({"size": 50_000})
        self.assertEqual(json.loads((self.d / settings.FILE).read_text(encoding="utf-8"))["profile_name"], "Pat")


class Cut(unittest.TestCase):
    """The saved size is what a question is cut to; the lower of it and the model's window wins."""
    def setUp(self):
        self.d = Path(os.path.realpath(tempfile.mkdtemp(prefix="clark-test-")))
        self.addCleanup(shutil.rmtree, self.d, True)
        self.db = plant.build_db(self.d / "clark.db")
        self.budgets = []

        def fake(folders, data_dir, question="", budget=ask.BUDGET, home=None, max_passages=ask.MAX_PASSAGES):
            self.budgets.append(budget)
            return ask_passages.FolderData([], 0)
        patch = mock.patch.object(ask_passages, "folder_data", fake)
        patch.start()
        self.addCleanup(patch.stop)

    def ask(self, window_tokens=None):
        sub = ai_providers.ClaudeSubscription(Fake("claude", ("sonnet", "opus")))
        if window_tokens:
            sub.contexts = {"sonnet": window_tokens, "opus": window_tokens}
        service = ask_service.AskService(self.db, None, [])
        service.data_dir = self.d
        service.provider = ai_providers.Chosen([sub], lambda: (sub, "sonnet", False), "Not connected.")
        service.today = lambda: datetime.date(2026, 11, 20)
        service.enabled = lambda: True
        status, got = service.ask({"project": "PUB", "question": "What is the state of the plan?"})
        self.assertEqual((status, got.get("ok")), (200, True), got)

    def test_the_saved_size_is_what_the_question_is_cut_to(self):
        self.ask()
        self.assertTrue(ask.BUDGET - ask_service.PROJECT_SHARE <= self.budgets[-1] <= ask.BUDGET, self.budgets)
        settings.ai_write(self.d, {"size": 10_000})
        self.ask()
        self.assertTrue(0 < self.budgets[-1] <= 40_000, self.budgets)
        settings.ai_write(self.d, {"size": 500_000})
        self.ask()
        self.assertTrue(1_000_000 < self.budgets[-1] <= 2_000_000, self.budgets)

    def test_a_smaller_model_window_beats_a_larger_setting(self):
        settings.ai_write(self.d, {"size": 500_000})
        self.ask(window_tokens=100_000)               # 400,000 characters in all
        self.assertLessEqual(self.budgets[-1], 400_000 - ask.REQUEST_OVERHEAD)
        self.assertEqual(ask.budget_for(400_000, 2_000_000), 400_000 - ask.REQUEST_OVERHEAD)
        self.assertEqual(ask.request_cap(400_000, 2_000_000), 400_000)
        self.assertEqual(ask.request_cap(None, 2_000_000), 2_000_000 + ask.REQUEST_OVERHEAD)
        self.assertEqual((ask.budget_for(None), ask.request_cap(None)), (ask.BUDGET, ask.MAX_REQUEST), "no setting: the fixed budget")


class OnThePage(unittest.TestCase):
    def setUp(self):
        self.s = Running(data_for=lambda code, archived=None: DATA.get(code), page_html=lambda: page.page_html(tempfile.mkdtemp()))
        self.addCleanup(self.s.close)
        self.d = Path(os.path.realpath(tempfile.mkdtemp(prefix="clark-test-")))
        self.addCleanup(shutil.rmtree, self.d, True)
        self.s.httpd.ai_connect = ac.AiConnect(self.d, FakeClaude(), FakeChatGPT())

    def show(self, cdp, width):
        sid = navigate(cdp, self.s.port, "#settings&p=ABC&s=claude")
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
        js = lambda e: cdp.js(e, sid)          # noqa: E731
        self.assertTrue(wait(lambda: js("!!document.querySelector('[data-ask-tab=all]')"), 90))
        js("document.querySelector('[data-ask-tab=all]').click()")
        self.assertTrue(wait(lambda: js("!!document.querySelector('#ai-size')"), 90))
        return js

    def type_into(self, js, text):
        js(f"(() => {{ const e = document.querySelector('#ai-size'); e.focus(); e.value = {text!r}; }})()")
        time.sleep(0.2)
        js("document.querySelector('#ai-size').blur()")

    def test_the_box_shows_saves_refuses_and_offers_the_default_at_1400_and_900(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                settings.ai_write(self.d, {"size": 300_000})
                js = self.show(cdp, width)
                self.assertEqual(js("document.querySelector('label[for=ai-size]').innerText"), "Size of one question")
                self.assertEqual(js("document.querySelector('#ai-size').value"), "300000")
                self.assertEqual(js("document.querySelector('[data-ai-size-help]').innerText"), HELP)
                self.assertFalse(js("!!document.querySelector('[data-ai-size-default]')"), "no Use 300,000 while it is 300,000")
                for bad in ("5000", "600000", "abc"):
                    self.type_into(js, bad)
                    self.assertTrue(wait(lambda: js("document.querySelector('[data-ai-msg]').innerText") == REFUSAL, 10), bad)
                    self.assertTrue(wait(lambda: js("document.querySelector('#ai-size').value") == "300000", 10), "the old value is put back")
                    self.assertEqual(settings.ask_size(self.d), 300_000)
                self.type_into(js, "20000")
                self.assertTrue(wait(lambda: settings.ask_size(self.d) == 20_000, 10))
                self.assertTrue(wait(lambda: js("document.querySelector('[data-ai-size]').innerText") == LINE.format(t=20_000, c=80_000), 10))
                self.assertEqual(js("document.querySelector('[data-ai-size-default]').innerText"), "Use 300,000")
                self.assertTrue(js("document.documentElement.scrollWidth <= window.innerWidth"), "no sideways scroll")
                js("document.querySelector('[data-ai-size-default]').click()")
                self.assertTrue(wait(lambda: settings.ask_size(self.d) == 300_000, 10))
                self.assertTrue(wait(lambda: not js("!!document.querySelector('[data-ai-size-default]')"), 10))


if __name__ == "__main__":
    unittest.main()
