"""#446: the Settings AI card, in a real browser against the real server with a fake provider: Claude's tile, OpenAI's Later tile and the
model, at 1400 and 900 px in light and dark. Chrome is required: fails, never skips.

Run: python3 dev/run_tests.py test_ai_connect_page
"""
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from _paths import SRC  # noqa: F401
from test_ai_connect import FakeChatGPT, FakeClaude
from test_page import DATA, navigate
from test_server import Running, chrome, wait

from clark import ai_connect, page, settings


class Card(unittest.TestCase):
    def setUp(self):
        self.s = Running(data_for=DATA.get, page_html=lambda: page.page_html(tempfile.mkdtemp()))
        self.addCleanup(self.s.close)
        self.d = Path(os.path.realpath(tempfile.mkdtemp(prefix="clark-test-")))
        self.addCleanup(shutil.rmtree, self.d, True)
        self.claude, self.chatgpt = FakeClaude(), FakeChatGPT()
        self.s.httpd.ai_connect = ai_connect.AiConnect(self.d, self.claude, self.chatgpt)

    def show(self, cdp):
        self.sid = navigate(cdp, self.s.port, "#settings&p=ABC")
        js = lambda e: cdp.js(e, self.sid)          # noqa: E731
        self.assertTrue(wait(lambda: js("!!document.querySelector('[data-ai-tile=claude]')"), 20), "the card is in Settings")
        return js

    def test_connected_shows_both_tiles_and_the_model(self):
        with chrome() as cdp:
            js = self.show(cdp)
            self.assertIn("Connected", js("document.querySelector('[data-ai-tile=claude] .tag').innerText"))
            self.assertEqual(js("document.querySelector('[data-ai-tile=chatgpt] .tag').innerText"), "Not connected")
            self.assertEqual(js("document.querySelector('[data-ai-intro]').innerText"), ai_connect.CARD_INTRO)
            self.assertEqual(js("document.querySelector('[data-ai-tile=claude] p.muted').innerText"),
                             "Through your Claude subscription, on this computer.", "row 544: plain words, no 'the Claude command'")
            self.assertEqual(js("document.querySelector('#ai-model').value"), "sonnet")
            self.assertIn("(recommended)", js("document.querySelector('#ai-model option[value=sonnet]').innerText"))

    def test_disconnect_then_connect(self):
        with chrome() as cdp:
            js = self.show(cdp)
            js("document.querySelector('[data-ai-disconnect=claude]').click()")
            self.assertTrue(wait(lambda: js("!!document.querySelector('[data-ai-connect=claude]')"), 10))
            self.assertIn("still signed in", js("document.querySelector('[data-ai-msg]').innerText"))
            self.assertEqual(js("document.querySelector('#ai-model').disabled"), True)
            self.assertEqual(js("document.querySelector('#ai-model').innerText"), "Connect Claude or ChatGPT first")
            js("document.querySelector('[data-ai-connect=claude]').click()")
            self.assertTrue(wait(lambda: js("!!document.querySelector('[data-ai-disconnect=claude]')"), 10))

    def test_connecting_chatgpt_offers_its_models_and_the_askings_words_follow_the_choice(self):
        with chrome() as cdp:
            js = self.show(cdp)
            self.assertIn("Claude, which Anthropic runs", js("document.querySelector('#ask-settings').innerText"))
            js("document.querySelector('[data-ai-connect=chatgpt]').click()")
            self.assertTrue(wait(lambda: js("!!document.querySelector('#ai-model option[value=\"gpt-6.1-sol\"]')"), 10))
            self.pick(js, "gpt-6.1-sol")
            self.assertTrue(wait(lambda: js("document.querySelector('#ai-model').value") == "gpt-6.1-sol", 10))
            self.assertEqual(settings.ai_read(self.d)["model"], "gpt-6.1-sol")
            self.assertTrue(wait(lambda: "ChatGPT, which OpenAI runs" in js("document.querySelector('#ask-settings').innerText"), 10))
            self.assertNotIn("Anthropic", js("document.querySelector('#ask-settings').innerText"))

    def test_not_signed_in_says_what_to_do(self):
        self.claude.signed_in = False
        with chrome() as cdp:
            js = self.show(cdp)
            self.assertIn("sign in", js("document.querySelector('[data-ai-tile=claude] [data-ai-why]').innerText"))
            js("document.querySelector('[data-ai-connect=claude]').click()")
            self.assertTrue(wait(lambda: "sign in" in js("document.querySelector('[data-ai-msg]').innerText"), 10))

    def pick(self, js, model):
        js(f"(() => {{ const s = document.querySelector('#ai-model'); s.value = '{model}'; s.dispatchEvent(new Event('change', {{bubbles: true}})); }})()")

    def test_a_smaller_model_asks_first_and_keeping_changes_nothing(self):
        with chrome() as cdp:
            js = self.show(cdp)
            self.pick(js, "haiku")
            self.assertTrue(wait(lambda: js("!!document.querySelector('[data-ai-weaker]')"), 10))
            self.assertEqual(js("document.querySelector('#ai-model').value"), "sonnet", "the drop-down goes back while it asks")
            js("document.querySelector('[data-ai-keep]').click()")
            self.assertTrue(wait(lambda: js("!document.querySelector('[data-ai-weaker]')"), 10))
            self.assertEqual(settings.ai_read(self.d)["model"], "")
            self.pick(js, "haiku")
            self.assertTrue(wait(lambda: js("!!document.querySelector('[data-ai-accept]')"), 10))
            js("document.querySelector('[data-ai-accept]').click()")
            self.assertTrue(wait(lambda: js("document.querySelector('#ai-model').value") == "haiku", 10))
            self.assertEqual(settings.ai_read(self.d)["model"], "haiku")

    def test_it_fits_and_reads_at_both_widths_in_light_and_dark(self):
        contrast = r"""(()=>{const lum=(c)=>{const m=c.match(/[\d.]+/g).map(Number).slice(0,3).map(v=>{v/=255;return v<=.03928?v/12.92:Math.pow((v+.055)/1.055,2.4);});return .2126*m[0]+.7152*m[1]+.0722*m[2];};
          const worst=[...document.querySelectorAll('[data-ai-tile] p, [data-ai-tile] h3, .ai-model label')].map(el=>{let bg=null;for(let e=el;e&&!bg;e=e.parentElement){const c=getComputedStyle(e).backgroundColor;if(!/rgba\(.*, 0\)|transparent/.test(c))bg=c;}
            const a=lum(getComputedStyle(el).color),b=lum(bg||'rgb(255,255,255)');return (Math.max(a,b)+.05)/(Math.min(a,b)+.05);});return Math.min(...worst);})()"""
        with chrome() as cdp:
            js = self.show(cdp)
            for theme in ("light", "dark"):
                js(f"document.documentElement.dataset.theme = '{theme}'")
                for w in (1400, 900):
                    with self.subTest(theme=theme, width=w):
                        cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, self.sid)
                        self.assertEqual(js("document.documentElement.scrollWidth <= window.innerWidth"), True, "no sideways scroll")
                        self.assertGreaterEqual(js(contrast), 4.5)

    def test_without_the_route_shows_no_card(self):
        self.s.httpd.ai_connect = None
        with chrome() as cdp:
            self.sid = navigate(cdp, self.s.port, "#settings&p=ABC")
            js = lambda e: cdp.js(e, self.sid)      # noqa: E731
            self.assertTrue(wait(lambda: js("!!document.querySelector('#ai-settings')"), 20))
            self.assertFalse(wait(lambda: js("!!document.querySelector('[data-ai-tile]')"), 1))


if __name__ == "__main__":
    unittest.main()
