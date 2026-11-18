"""Row 1294 (mock-up A8, slice 2): Models on the All projects tab. Turning a model on connects it ("Connecting…", then "Connected. Asking can use its
models."); with no sign-in the switch stays off and says so in plain words; turning one off stops what runs on it and leaves the sign-in alone; Test the
connection asks each model that is on one short question and says how long it took; the size of one question is stated. No money anywhere.

Run: python3 dev/run_tests.py test_ask_models_1294
The logic tests need no browser; the page tests need Chrome (1400 and 900)."""
import json
import os
import re
import shutil
import tempfile
import threading
import unittest
from pathlib import Path

from _paths import SRC  # noqa: F401
from test_ai_connect import FakeChatGPT, FakeClaude
from test_page import DATA, navigate
from test_server import Running, chrome, wait

from clark import ai_connect as ac, ask, page, settings

MONEY = re.compile(r"[$£€]|cost|monthly|spend|\bprice\b|\bbudget\b|\bbilled\b", re.I)
NOT_SIGNED_IN = "ChatGPT is not signed in on this computer. Sign in to the Codex command, then turn it on again."
CONNECTED = "Connected. Asking can use its models."


class Clock:
    """A clock that moves 2.5 seconds each time it is read twice (the start and the end of one test)."""
    def __init__(self):
        self.now = 0.0
        self.reads = 0

    def __call__(self):
        self.reads += 1
        if self.reads % 2 == 0:
            self.now += 2.5
        return self.now


class Models(unittest.TestCase):
    def setUp(self):
        self.d = Path(os.path.realpath(tempfile.mkdtemp(prefix="clark-test-")))
        self.addCleanup(shutil.rmtree, self.d, True)
        self.claude, self.chatgpt = FakeClaude(), FakeChatGPT()
        self.connect = ac.AiConnect(self.d, self.claude, self.chatgpt)

    def test_claude_is_on_when_signed_in_and_chatgpt_is_off_until_connected(self):
        _, b = self.connect.get()
        self.assertTrue(b["claude"]["connected"])
        self.assertFalse(b["chatgpt"]["connected"])
        self.assertTrue(b["chatgpt"]["signed_in"], "signed in is not the same as turned on")

    def test_turning_a_model_on_says_connected_in_the_approved_words(self):
        status, b = self.connect.connect({"provider": "chatgpt"})
        self.assertEqual((status, b["message"]), (200, CONNECTED))
        self.assertTrue(b["chatgpt"]["connected"])

    def test_no_sign_in_leaves_it_off_with_the_plain_message_and_writes_nothing(self):
        self.chatgpt.signed_in = False
        status, b = self.connect.connect({"provider": "chatgpt"})
        self.assertEqual((status, b["code"], b["message"]), (409, "not_signed_in", NOT_SIGNED_IN))
        self.assertFalse(self.connect.get()[1]["chatgpt"]["connected"])
        self.assertFalse((self.d / settings.FILE).exists())

    def test_claude_without_a_sign_in_says_what_its_own_check_found(self):
        self.claude.signed_in = False
        status, b = self.connect.connect({"provider": "claude"})
        self.assertEqual((status, b["message"]), (409, "Open Terminal and sign in to Claude."))

    def test_turning_one_off_stops_what_runs_on_it_and_leaves_the_sign_in(self):
        self.connect.connect({"provider": "chatgpt"})
        status, b = self.connect.disconnect({"provider": "chatgpt"})
        self.assertEqual(status, 200)
        self.assertEqual(self.chatgpt.stops, [None])
        self.assertEqual(self.claude.stops, [])
        self.assertTrue(b["chatgpt"]["signed_in"])
        self.assertFalse(b["chatgpt"]["connected"])
        self.assertTrue(self.chatgpt.signed_in)

    def test_the_size_of_one_question_is_stated_with_the_lower_limit_rule(self):
        line = self.connect.get()[1]["size"]
        self.assertEqual(line, "Size of one question: 300,000 tokens. Each model has its own limit and the lower one applies.")


class TestTheConnection(unittest.TestCase):
    def setUp(self):
        self.d = Path(os.path.realpath(tempfile.mkdtemp(prefix="clark-test-")))
        self.addCleanup(shutil.rmtree, self.d, True)
        self.claude, self.chatgpt = FakeClaude(), FakeChatGPT()
        self.connect = ac.AiConnect(self.d, self.claude, self.chatgpt)

    def test_it_asks_each_model_that_is_on_once_and_says_how_long(self):
        self.connect.connect({"provider": "chatgpt"})
        status, b = self.connect.test({}, clock=Clock())
        self.assertEqual(status, 200)
        self.assertEqual([(r["provider"], r["answered"], r["seconds"]) for r in b["results"]], [("claude", True, 2.5), ("chatgpt", True, 2.5)])
        self.assertEqual((self.claude.asked, self.chatgpt.asked), ([ac.RECOMMENDED["claude"]], [ac.RECOMMENDED["chatgpt"]]))

    def test_a_model_that_is_off_is_not_asked(self):
        status, b = self.connect.test({}, clock=Clock())
        self.assertEqual([r["provider"] for r in b["results"]], ["claude"])
        self.assertEqual(self.chatgpt.asked, [])

    def test_a_model_that_cannot_answer_says_so_in_its_own_words(self):
        self.claude.ask = lambda request, model=None, prefer=False: ask.Failure("Claude could not answer just now.")
        status, b = self.connect.test({}, clock=Clock())
        self.assertEqual((status, b["results"][0]["answered"], b["results"][0]["message"]), (200, False, "Claude could not answer just now."))

    def test_nothing_on_asks_nothing_and_says_so(self):
        self.connect.disconnect({"provider": "claude"})
        status, b = self.connect.test({}, clock=Clock())
        self.assertEqual((status, b["code"], b["message"]), (409, "nothing_on", ac.TEST_NOTHING))
        self.assertEqual(self.claude.asked, [])

    def test_it_takes_nothing_and_keeps_nothing(self):
        for body in (None, [], {"x": 1}, {"provider": "claude"}):
            self.assertEqual(self.connect.test(body)[0], 400, body)
        before = (self.d / settings.FILE).exists()
        self.connect.test({}, clock=Clock())
        self.assertEqual((self.d / settings.FILE).exists(), before, "a test writes no setting")
        self.assertEqual(self.claude.asked, [ac.RECOMMENDED["claude"]], "the bad bodies asked nothing")

    def test_no_money_in_any_word_of_the_card(self):
        self.connect.connect({"provider": "chatgpt"})
        _, view = self.connect.get()
        words = json.dumps({k: view[k] for k in ("size", "message")}) + json.dumps(self.connect.test({}, clock=Clock())[1])
        self.assertIsNone(MONEY.search(words), words)


class Hold:
    """A provider whose sign-in check waits until released, so the page can be looked at while it says Connecting…"""
    def __init__(self, inner):
        self.inner, self.go = inner, threading.Event()
        self.hold = False

    def __getattr__(self, name):
        return getattr(self.inner, name)

    def status(self):
        if self.hold:
            self.go.wait(15)
        return self.inner.status()


class OnThePage(unittest.TestCase):
    def setUp(self):
        self.s = Running(data_for=lambda code, archived=None: DATA.get(code), page_html=lambda: page.page_html(tempfile.mkdtemp()))
        self.addCleanup(self.s.close)
        self.d = Path(os.path.realpath(tempfile.mkdtemp(prefix="clark-test-")))
        self.addCleanup(shutil.rmtree, self.d, True)
        self.claude, self.chatgpt = FakeClaude(), Hold(FakeChatGPT())
        self.s.httpd.ai_connect = ac.AiConnect(self.d, self.claude, self.chatgpt)

    def show(self, cdp, width):
        self.sid = navigate(cdp, self.s.port, "#settings&p=ABC&s=claude")
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, self.sid)
        js = lambda e: cdp.js(e, self.sid)          # noqa: E731
        self.assertTrue(wait(lambda: js("!!document.querySelector('[data-ask-tab=all]')"), 90))
        js("document.querySelector('[data-ask-tab=all]').click()")
        self.assertTrue(wait(lambda: js("!!document.querySelector('[data-ai-tile=chatgpt]')"), 90))
        return js

    def test_the_switch_connects_says_connecting_then_connected_and_goes_off_again(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                self.chatgpt.go.clear()
                self.chatgpt.hold = True
                js = self.show(cdp, width)
                self.assertEqual(js("document.querySelector('[data-ai-connect=chatgpt]').getAttribute('aria-pressed')"), "false")
                self.assertEqual(js("document.querySelector('[data-ai-connect=chatgpt]').innerText"), "Turn on ChatGPT")
                js("document.querySelector('[data-ai-connect=chatgpt]').click()")
                self.assertTrue(wait(lambda: js("(document.querySelector('[data-ai-tile=chatgpt] [data-ai-status]') || {}).innerText") == "Connecting…", 10))
                self.chatgpt.hold = False
                self.chatgpt.go.set()
                self.assertTrue(wait(lambda: js("!!document.querySelector('[data-ai-disconnect=chatgpt]')"), 10))
                self.assertEqual(js("document.querySelector('[data-ai-tile=chatgpt] [data-ai-status]').innerText"), CONNECTED)
                self.assertEqual(js("document.querySelector('[data-ai-disconnect=chatgpt]').getAttribute('aria-pressed')"), "true")
                self.assertEqual(js("document.querySelector('[data-ai-disconnect=chatgpt]').innerText"), "Turn off ChatGPT")
                js("document.querySelector('[data-ai-disconnect=chatgpt]').click()")
                self.assertTrue(wait(lambda: js("!!document.querySelector('[data-ai-connect=chatgpt]')"), 10))
                self.assertTrue(self.chatgpt.signed_in, "the sign-in is left alone")
                self.assertTrue(js("document.documentElement.scrollWidth <= window.innerWidth"), "no sideways scroll")

    def test_with_no_sign_in_the_switch_stays_off_and_says_why(self):
        self.chatgpt.inner.signed_in = False
        with chrome() as cdp:
            js = self.show(cdp, 1400)
            js("document.querySelector('[data-ai-connect=chatgpt]').click()")
            self.assertTrue(wait(lambda: NOT_SIGNED_IN == js("document.querySelector('[data-ai-msg]').innerText"), 10))
            self.assertEqual(js("document.querySelector('[data-ai-connect=chatgpt]').getAttribute('aria-pressed')"), "false")
            self.assertFalse(js("!!document.querySelector('[data-ai-disconnect=chatgpt]')"))

    def test_test_the_connection_shows_the_seconds_for_each_model_on_and_the_size_line(self):
        with chrome() as cdp:
            js = self.show(cdp, 900)
            self.assertEqual(js("document.querySelector('[data-ai-size]').innerText"), "Size of one question: 300,000 tokens. Each model has its own limit and the lower one applies.")
            self.assertEqual(js("document.querySelector('[data-ai-test]').innerText"), "Test the connection")
            js("document.querySelector('[data-ai-test]').click()")
            self.assertTrue(wait(lambda: re.fullmatch(r"Claude answered in \d+(\.\d)? seconds\.", js("document.querySelector('[data-ai-test-out]').innerText") or ""), 15))
            self.assertNotIn("ChatGPT", js("document.querySelector('[data-ai-test-out]').innerText"), "a model that is off is not tested")
            self.assertIsNone(MONEY.search(js("document.querySelector('#ai-settings').innerText")))


if __name__ == "__main__":
    unittest.main()
