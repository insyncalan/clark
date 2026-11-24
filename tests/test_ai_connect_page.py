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


# #543: how long a page may take to show Settings. The wait polls and returns the moment the page is there, so a long ceiling costs a
# passing run nothing; it only stops a loaded runner (load about 33 flaked 20 s once) from failing a test that is not about speed.
PAGE_UP = 90


class Card(unittest.TestCase):
    def setUp(self):
        self.s = Running(data_for=lambda code, archived=None: DATA.get(code), page_html=lambda: page.page_html(tempfile.mkdtemp()))
        self.addCleanup(self.s.close)
        self.d = Path(os.path.realpath(tempfile.mkdtemp(prefix="clark-test-")))
        self.addCleanup(shutil.rmtree, self.d, True)
        self.claude, self.chatgpt = FakeClaude(), FakeChatGPT()
        self.s.httpd.ai_connect = ai_connect.AiConnect(self.d, self.claude, self.chatgpt)

    def show(self, cdp):
        self.sid = navigate(cdp, self.s.port, "#settings&p=ABC&s=claude")
        js = lambda e: cdp.js(e, self.sid)          # noqa: E731
        self.assertTrue(wait(lambda: js("!!document.querySelector('[data-ask-tab=all]')"), PAGE_UP), "the All projects tab is on the page")
        js("document.querySelector('[data-ask-tab=all]').click()")      # row 1294: the connections are on the All projects tab
        self.assertTrue(wait(lambda: js("!!document.querySelector('[data-ai-tile=claude]')"), PAGE_UP), "the card is in Settings")
        return js

    def tab(self, js, name):
        """Row 1294: the connections are on the All projects tab, the asking switch and its words on the project's."""
        js(f"document.querySelector('[data-ask-tab={name}]').click()")
        self.assertTrue(wait(lambda: js("!!document.querySelector('%s')" % ("[data-ai-tile=claude]" if name == "all" else "#ask-notice")), 10))

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

    def test_the_profile_line_shows_at_1400_and_900_only_with_a_saved_name(self):
        for name in ("", "Sam Lee"):
            settings.set_profile(self.d, name, "")
            with chrome() as cdp:
                js = self.show(cdp)
                for width in (1400, 900):
                    cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, self.sid)
                    got = js("(document.querySelector('[data-ai-profile]')||{}).innerText || ''")
                    self.assertEqual(got, ai_connect.PROFILE_LINE if name else "", (width, name))
                    if name:
                        self.assertTrue(js("document.querySelector('[data-ai-profile]').getBoundingClientRect().right <= innerWidth"), width)

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

    def test_focus_stays_on_the_button_pressed_and_lands_on_the_one_that_replaces_it(self):
        with chrome() as cdp:
            js = self.show(cdp)
            act = "(document.activeElement.getAttribute('data-ai-connect') || document.activeElement.getAttribute('data-ai-disconnect') || document.activeElement.id || document.activeElement.tagName)"
            js("document.querySelector('[data-ai-disconnect=claude]').focus()")
            js("document.querySelector('[data-ai-disconnect=claude]').click()")
            self.assertTrue(wait(lambda: js("!!document.querySelector('[data-ai-connect=claude]')"), 10))
            self.assertTrue(wait(lambda: js(act + "==='claude' && !!document.querySelector('[data-ai-connect=claude]:focus')"), 5),
                            "focus is on Connect, not dropped to the page")
            js("document.querySelector('[data-ai-connect=claude]').click()")
            self.assertTrue(wait(lambda: js("!!document.querySelector('[data-ai-disconnect=claude]')"), 10))
            self.assertTrue(wait(lambda: js("!!document.querySelector('[data-ai-disconnect=claude]:focus')"), 5))

    def test_connecting_chatgpt_offers_its_models_and_the_askings_words_follow_the_choice(self):
        with chrome() as cdp:
            js = self.show(cdp)
            self.tab(js, "project")
            self.assertIn("Claude, which Anthropic runs", js("document.querySelector('#ask-settings').innerText"))
            self.assertIn("are billed to the Claude account signed in on this computer", js("document.querySelector('#ask-notice').innerText"), "#1062")
            self.assertGreater(js("document.querySelector('#ask-notice').offsetHeight"), 0, "the notice is on show, not hidden (#1062)")
            self.tab(js, "all")
            js("document.querySelector('[data-ai-connect=chatgpt]').click()")
            self.assertTrue(wait(lambda: js("!!document.querySelector('#ai-model option[value=\"gpt-6.1-sol\"]')"), 10), "ChatGPT offers gpt-6.1-sol after Connect")
            self.pick(js, "gpt-6.1-sol")
            self.assertTrue(wait(lambda: js("document.querySelector('#ai-model').value") == "gpt-6.1-sol", 10), "the drop-down shows gpt-6.1-sol")
            self.assertEqual(settings.ai_read(self.d)["model"], "gpt-6.1-sol")
            self.tab(js, "project")
            self.assertTrue(wait(lambda: "ChatGPT, which OpenAI runs" in js("document.querySelector('#ask-settings').innerText"), 10), "the project tab's asking words name ChatGPT")
            self.assertNotIn("Anthropic", js("document.querySelector('#ask-settings').innerText"))
            self.assertIn("billed to the ChatGPT account", js("document.querySelector('#ask-notice').innerText"))

    def test_focus_stays_on_the_model_and_on_connect_while_it_saves(self):
        with chrome() as cdp:
            js = self.show(cdp)
            js("document.querySelector('#ai-model').focus()")
            self.pick(js, "opus")
            self.assertTrue(wait(lambda: settings.ai_read(self.d)["model"] == "opus", 10))
            self.assertEqual(js("document.activeElement && document.activeElement.id"), "ai-model", "the drop-down keeps focus after saving")
            js("document.querySelector('[data-ai-disconnect=claude]').focus()")
            js("document.querySelector('[data-ai-disconnect=claude]').click()")
            self.assertTrue(wait(lambda: js("!!document.querySelector('[data-ai-connect=claude]')"), 10))
            self.assertEqual(js("document.activeElement && document.activeElement.hasAttribute('data-ai-connect')"), True, "focus stays on the button")

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
            self.sid = navigate(cdp, self.s.port, "#settings&p=ABC&s=claude")
            js = lambda e: cdp.js(e, self.sid)      # noqa: E731
            self.assertTrue(wait(lambda: js("!!document.querySelector('[data-ask-tab=all]')"), PAGE_UP))
            js("document.querySelector('[data-ask-tab=all]').click()")
            self.assertTrue(wait(lambda: js("!!document.querySelector('#ai-settings')"), PAGE_UP))
            self.assertFalse(wait(lambda: js("!!document.querySelector('[data-ai-tile]')"), 1))


if __name__ == "__main__":
    unittest.main()
