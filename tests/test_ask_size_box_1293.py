"""Row 1293 AP2: the "Size of one question" box. The size is a whole number of tokens from 10,000 to 500,000 (default 300,000, step 10,000 in the
box), saved in settings.json (settings.ask_size); anything else is refused with the ticket's sentence and the saved value stays (never clamped).
The one reader sets the budget of every question: a smaller model window still wins.

Run: python3 dev/run_tests.py test_ask_size_box_1293
Quick tier: no browser. Fictional data only.
"""
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from _paths import SRC  # noqa: F401
from test_ai_connect import FakeChatGPT, FakeClaude

import test_ask_models_1294 as models
from test_server import chrome, wait

from clark import ai_connect as ac, ask, settings

REFUSAL = "Size of one question must be a whole number from 10,000 to 500,000 tokens."


class SizeBox(unittest.TestCase):
    def setUp(self):
        self.d = Path(os.path.realpath(tempfile.mkdtemp(prefix="clark-test-")))
        self.addCleanup(shutil.rmtree, self.d, True)
        self.connect = ac.AiConnect(self.d, FakeClaude(), FakeChatGPT())

    def test_the_size_box_limits_and_refusal_text(self):
        box = self.connect.get()[1]["size_box"]
        self.assertEqual({k: box[k] for k in ("value", "default", "min", "max", "step")},
                         {"value": 300_000, "default": 300_000, "min": 10_000, "max": 500_000, "step": 10_000})
        for good in (10_000, 500_000, 120_000):                       # both ends are in
            status, body = self.connect.set_size({"tokens": good})
            self.assertEqual((status, body["size_box"]["value"], settings.ask_size(self.d)), (200, good, good))
        for bad in (9_999, 500_001, 0, -10_000, 1.5, 20_000.0, "300000", "abc", None, True, [300_000]):      # the hostile entries: all refused, none clamped
            status, body = self.connect.set_size({"tokens": bad})
            self.assertEqual((status, body["ok"], body["message"]), (400, False, REFUSAL), bad)
            self.assertEqual(settings.ask_size(self.d), 120_000, f"{bad!r} must leave the saved value")
        self.assertEqual(self.connect.set_size({"tokens": 20_000, "more": 1})[0], 400)     # a body with another field is refused
        self.assertEqual(self.connect.set_size({})[0], 400)
        self.assertEqual(self.connect.set_size("300000")[0], 400)

    def test_a_hand_edited_file_with_a_wrong_size_reads_as_the_default(self):
        for bad in (5_000, 600_000, "big", True):
            (self.d / settings.FILE).write_text(f'{{"ask_size": {str(bad).lower() if bad is True else repr(bad).replace(chr(39), chr(34))}}}', encoding="utf-8")
            self.assertEqual(settings.ask_size(self.d), 300_000)

    def test_the_readout_follows_the_saved_size(self):
        self.connect.set_size({"tokens": 50_000})
        self.assertIn("about 50,000 tokens (200,000 characters of passages)", self.connect.get()[1]["size"])

    def test_the_size_cuts_the_passages_and_a_smaller_model_window_still_wins(self):
        passages = [("Item %d" % i, ("word%d " % i) * 150) for i in range(55)]      # 55 passages of about 1,000 characters: 55,000 in all
        small = ask.build_request("What is open?", passages, budget=ask.size_chars(10_000))
        big = ask.build_request("What is open?", passages, budget=ask.size_chars(500_000))
        self.assertGreater(small.left_out, 0)
        self.assertEqual(big.left_out, 0)
        self.assertLessEqual(len(small.text), ask.size_chars(10_000) + ask.REQUEST_OVERHEAD)
        self.assertEqual(ask.budget_for(None, ask.size_chars(500_000)), 2_000_000)
        self.assertEqual(ask.budget_for(1_000_000, ask.size_chars(500_000)), 1_000_000 - ask.REQUEST_OVERHEAD)      # the lower limit applies
        self.assertEqual(ask.request_cap(None, ask.size_chars(500_000)), 2_000_000 + ask.REQUEST_OVERHEAD)
        self.assertEqual(ask.request_cap(1_000_000, ask.size_chars(500_000)), 1_000_000)


class OnThePage(unittest.TestCase):
    """The box in Settings, at 1400 and 900: it shows 300,000, saves a good value on Enter, refuses 5,000, 600,000 and abc with the sentence and keeps the old value."""
    setUp, show = models.OnThePage.setUp, models.OnThePage.show

    def test_the_box_at_1400_and_900(self):
        calls, real = [], self.s.httpd.ai_connect.set_size
        self.s.httpd.ai_connect.set_size = lambda body, *_: (calls.append(body), real(body))[1]
        with chrome() as cdp:
            for width in (1400, 900):
                js = self.show(cdp, width)
                box, say = "document.querySelector('[data-ai-size-box]')", "document.querySelector('[data-ai-msg]').innerText"
                self.assertEqual(js(box + ".value"), "300,000")
                self.assertFalse(js("!!document.querySelector('[data-ai-size-default]')"), "Use 300,000 shows only when the value is changed")
                for bad in ("5,000", "600,000", "abc"):
                    before = len(calls)
                    js(f"(() => {{ const b = {box}; b.focus(); b.value = '{bad}'; b.dispatchEvent(new Event('input', {{bubbles: true}})); b.blur(); }})()")
                    self.assertTrue(wait(lambda: len(calls) > before, 10), bad)       # the server was asked, and refused
                    self.assertTrue(wait(lambda: js(say) == REFUSAL and js(box + ".value") == "300,000", 10), (bad, js(say), js(box + ".value")))
                    self.assertEqual(settings.ask_size(self.d), 300_000)
                js(f"(() => {{ const b = {box}; b.focus(); b.value = '120,000'; b.dispatchEvent(new Event('input', {{bubbles: true}})); b.blur(); }})()")
                self.assertTrue(wait(lambda: settings.ask_size(self.d) == 120_000, 10))
                self.assertTrue(wait(lambda: js("!!document.querySelector('[data-ai-size-default]')"), 10))
                self.assertIn("about 120,000 tokens", js("document.querySelector('[data-ai-size]').innerText"))
                js("document.querySelector('[data-ai-size-default]').click()")
                self.assertTrue(wait(lambda: settings.ask_size(self.d) == 300_000, 10))
                self.assertTrue(js("document.documentElement.scrollWidth <= window.innerWidth"), "no sideways scroll")


if __name__ == "__main__":
    unittest.main()
