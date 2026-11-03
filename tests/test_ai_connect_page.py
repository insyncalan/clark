"""#446, #54: the Settings › AI card in a real browser against the real server, a FAKE key store, a FAKE provider caller and a fake sign-in
(nothing real is touched, nothing leaves this computer). Desktop widths 1400 and 900, light and dark.

Run: python3 dev/run_tests.py test_ai_connect_page
The card: a Claude tile (Claude subscription or API key) and an OpenAI tile (API key; ChatGPT sign-in later), each with Connect or
Disconnect; the "Model for ask clark" drop-down with the connected providers' models only, the recommended one marked; a weaker model asks
first. The key is typed in a password box, is empty the moment it is sent, and is nowhere on the page or in the browser's storage
afterwards. Chrome is required: fails, never skips.
"""
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from _paths import SRC  # noqa: F401
from test_page import DATA, navigate
from test_server import Running, chrome, wait
from test_ai_connect import KEY, OPENAI_KEY, FakeCaller, FakeStore, Signed
from test_ai_route import Fake
from test_ask_settings import make_db

from clark import ai_connect, ai_service, ask_service, page

WIDTHS = (1400, 900)
INTRO = ("Sign in to Claude or OpenAI for ask clark and the AI menu: the passages they send go to the provider you choose. "
         "Keys stay in this computer's keychain, never in clark's files.")
Q = "document.querySelector"


class Card(unittest.TestCase):
    def setUp(self):
        self.s = Running(data_for=DATA.get, page_html=lambda: page.page_html(tempfile.mkdtemp()))
        self.addCleanup(self.s.close)
        self.d = Path(os.path.realpath(tempfile.mkdtemp(prefix="clark-test-")))
        self.addCleanup(shutil.rmtree, self.d, True)
        self.db = make_db(self.d)
        self.provider = Fake()
        self.addCleanup(self.provider.release.set)
        self.service = ask_service.AskService(self.db, self.provider, [])
        self.keys = FakeStore()
        self.caller = FakeCaller()
        self.signed = Signed()
        self.s.httpd.ask = self.service
        self.s.httpd.ai = ai_service.AiService(self.service)
        self.s.httpd.ai_connect = ai_connect.AiConnect(self.d, provider=self.signed, store=self.keys, https=self.caller)

    def show(self, cdp):
        self.sid = navigate(cdp, self.s.port, "#settings&p=ABC")
        js = lambda e: cdp.js(e, self.sid)          # noqa: E731
        self.assertTrue(wait(lambda: js(f"!!{Q}('#ai-settings .ai-provs')"), 20), "the tiles are in Settings")
        return js

    def type_key(self, js, key):
        js(f"""(() => {{ const i = {Q}('#ai-key'); i.focus(); i.value = {json.dumps(key)}; i.dispatchEvent(new Event('input', {{bubbles: true}})); }})()""")
        self.assertEqual(js(f"{Q}('#ai-key').value"), key, "typed")

    def pick_model(self, js, model):
        js(f"(() => {{ const m = {Q}('#ai-model'); m.value = {json.dumps(model)}; m.dispatchEvent(new Event('change', {{bubbles: true}})); }})()")

    def connect_with_key(self, js, provider="claude", key=KEY):
        js(f"{Q}('[data-ai-connect={provider}]').click()")
        self.assertTrue(wait(lambda: js(f"!!{Q}('#ai-connect-dialog[open]')"), 10))
        if provider == "claude":
            js(f"{Q}('[data-how=key]').click()")
        self.assertTrue(wait(lambda: js(f"!!{Q}('#ai-key')"), 10))
        self.type_key(js, key)
        js(f"{Q}('[data-ai-go]').click()")

    def no_key_anywhere(self, js, keys=(KEY, OPENAI_KEY)):
        for key in keys:
            for piece in (key, key[-14:], key[:20]):      # long enough not to be a chance run of letters in the page's own script
                self.assertFalse(js(f"document.documentElement.outerHTML.includes({json.dumps(piece)})"), piece)
                self.assertFalse(js(f"document.body.innerText.includes({json.dumps(piece)})"), piece)
                self.assertFalse(js(f"JSON.stringify([localStorage, sessionStorage]).includes({json.dumps(piece)})"), piece)
                self.assertFalse(js(f"Array.from(document.querySelectorAll('input, textarea')).some(i => i.value.includes({json.dumps(piece)}))"), piece)

    def test_the_card_has_two_tiles_the_words_and_the_model_box(self):
        with chrome() as cdp:
            js = self.show(cdp)
            self.assertEqual(js(f"{Q}('#ai-settings h2').innerText"), "AI")
            self.assertEqual(js(f"{Q}('#ai-settings > p.muted').innerText"), INTRO)
            tiles = js("Array.from(document.querySelectorAll('.ai-prov')).map(t => [t.querySelector('h3').childNodes[0].textContent.trim(), t.querySelector('.tag').innerText, t.querySelector('p').innerText])")
            self.assertEqual(tiles, [["Claude", "Not connected", "Through your Claude subscription (the Claude command) or an API key."],
                                     ["OpenAI", "Not connected", "Through an API key. ChatGPT sign-in comes in a later version."]])
            self.assertEqual(js("Array.from(document.querySelectorAll('[data-ai-connect]')).map(b => b.innerText)"), ["Connect…", "Connect…"])
            self.assertEqual(js(f"{Q}('label[for=ai-model]').innerText"), "Model for ask clark")
            self.assertEqual(js(f"{Q}('#ai-model').innerText"), "Connect Claude or OpenAI first")
            self.assertEqual(js(f"{Q}('#ai-model').disabled"), True)
            self.assertEqual(js(f"{Q}('#ai-key')"), None, "no key box until Connect is chosen")

    def test_connect_with_a_key_then_the_models_then_disconnect(self):
        with chrome() as cdp:
            js = self.show(cdp)
            js("""window.__sent = []; const real = window.fetch;
                 window.fetch = function (url, init) { if (String(url).indexOf('/api/ai-connect') >= 0 && init && init.method === 'POST') {
                   const box = document.querySelector('#ai-key');
                   window.__sent.push({ boxAtSend: box ? box.value : null, body: init.body }); }
                   return real.apply(this, arguments); };""")
            self.connect_with_key(js)
            self.assertTrue(wait(lambda: js(f"!!{Q}('[data-ai-tile=claude] [data-ai-disconnect]')"), 20), js(f"({Q}('#ai-connect-msg') || {{}}).innerText"))
            self.assertEqual(js("window.__sent.length"), 1)
            self.assertEqual(js("window.__sent[0].boxAtSend"), "", "the box is empty by the time the request is sent")
            self.assertIn(KEY, js("window.__sent[0].body"), "the key went to the server, once")
            self.assertEqual(self.caller.listed, ["claude"], "it was tested before it was kept")
            self.assertEqual(self.keys.secret, KEY)
            self.assertEqual(js(f"{Q}('[data-ai-tile=claude] .tag').innerText"), "Connected")
            self.assertEqual(js(f"{Q}('[data-ai-tile=claude] .ai-how').innerText"), "API key · Claude Opus 5.5, Claude Sonnet 5.5, Claude Haiku 5.5")
            self.assertEqual(js(f"{Q}('#ai-connect-dialog')"), None, "the box is gone")
            self.no_key_anywhere(js)
            # OpenAI too: its models join the list
            self.connect_with_key(js, "openai", OPENAI_KEY)
            self.assertTrue(wait(lambda: js(f"!!{Q}('[data-ai-tile=openai] [data-ai-disconnect]')"), 20), js(f"({Q}('#ai-connect-msg') || {{}}).innerText"))
            self.assertEqual(js("Array.from(document.querySelectorAll('#ai-model option')).map(o => o.innerText)"),
                             ["Claude Opus 5.5 (recommended)", "Claude Sonnet 5.5", "Claude Haiku 5.5", "OpenAI gpt-fake-large", "OpenAI gpt-fake-small"])
            self.assertEqual(js(f"{Q}('#ai-model').value"), "claude-opus")
            self.no_key_anywhere(js)
            # a weaker model asks first; Keep changes nothing, Use it anyway keeps it
            self.pick_model(js, 'claude-sonnet')
            self.assertTrue(wait(lambda: js(f"!!{Q}('#ai-weaker-dialog[open]')"), 10))
            self.assertTrue(js(f"{Q}('#ai-weaker-text').innerText").startswith("Claude Sonnet 5.5 isn't the recommended model."))
            js(f"{Q}('[data-ai-keep]').click()")
            self.assertTrue(wait(lambda: js(f"!{Q}('#ai-weaker-dialog')"), 10))
            self.assertEqual(ai_connect.chosen_model(self.d), "claude-opus")
            self.pick_model(js, 'claude-sonnet')
            self.assertTrue(wait(lambda: js(f"!!{Q}('#ai-weaker-dialog[open]')"), 10))
            js(f"{Q}('[data-ai-anyway]').click()")
            self.assertTrue(wait(lambda: "Asking will use Claude Sonnet 5.5." in js(f"{Q}('#ai-settings .pub-msg').innerText"), 10))
            self.assertEqual(ai_connect.chosen_model(self.d), "claude-sonnet")
            js("location.reload()")
            self.assertTrue(wait(lambda: js(f"({Q}('#ai-model') || {{}}).value") == "claude-sonnet", 20), "it is kept")
            # disconnect Claude: its models go, and the choice goes back to what is left
            js(f"{Q}('[data-ai-tile=claude] [data-ai-disconnect]').click()")
            self.assertTrue(wait(lambda: js(f"!!{Q}('[data-ai-connect=claude]')"), 20))
            self.assertIsNone(self.keys.secret)
            self.assertEqual(js(f"{Q}('[data-ai-tile=claude] .tag').innerText"), "Not connected")
            self.assertEqual(js("Array.from(document.querySelectorAll('#ai-model option')).map(o => o.value)"), ["openai:gpt-fake-large", "openai:gpt-fake-small"])
            self.assertEqual(ai_connect.chosen_model(self.d), "openai:gpt-fake-large")

    def test_a_refused_key_says_why_in_the_box_and_the_box_is_empty(self):
        self.caller.status = 401
        with chrome() as cdp:
            js = self.show(cdp)
            self.connect_with_key(js, "openai", OPENAI_KEY)
            self.assertTrue(wait(lambda: js(f"({Q}('#ai-connect-msg') || {{}}).innerText").startswith("OpenAI did not accept this key (401)."), 20),
                            js(f"{Q}('#ai-connect-msg').innerText"))
            self.assertEqual(js(f"{Q}('#ai-key').value"), "")
            self.assertEqual(js(f"{Q}('#ai-key').type"), "password")
            self.assertEqual(js(f"{Q}('#ai-key').getAttribute('autocomplete')"), "off")
            self.assertEqual(self.keys.keys, {})
            self.no_key_anywhere(js)

    def test_a_key_that_cannot_be_kept_is_said_in_the_box(self):
        self.keys.fail = True
        with chrome() as cdp:
            js = self.show(cdp)
            self.connect_with_key(js)
            self.assertTrue(wait(lambda: js(f"({Q}('#ai-connect-msg') || {{}}).innerText") == ai_connect.MESSAGES["keychain"], 20), js(f"{Q}('#ai-connect-msg').innerText"))
            self.no_key_anywhere(js)

    def test_a_key_that_is_not_one_line_is_refused_in_the_box_in_the_servers_words(self):
        with chrome() as cdp:
            js = self.show(cdp)
            self.connect_with_key(js, key=KEY + " and more words")
            self.assertTrue(wait(lambda: js(f"({Q}('#ai-connect-msg') || {{}}).innerText") == ai_connect.MESSAGES["bad_key"], 20))
            self.assertIsNone(self.keys.secret)
            self.assertEqual(js(f"{Q}('#ai-key').value"), "")

    def test_the_subscription_needs_no_key_and_the_box_says_where_passages_go(self):
        with chrome() as cdp:
            js = self.show(cdp)
            js(f"{Q}('[data-ai-connect=claude]').click()")
            self.assertTrue(wait(lambda: js(f"!!{Q}('#ai-connect-dialog[open]')"), 10))
            self.assertEqual(js(f"{Q}('[data-ai-note]').innerText"), ai_connect.CONNECT_NOTE)
            self.assertEqual(js(f"{Q}('#ai-key')"), None, "Claude subscription is the first choice and has no key box")
            self.assertEqual(js("Array.from(document.querySelectorAll('#ai-connect-dialog [data-how]')).map(b => b.innerText)"), ["Claude subscription", "API key"])
            js(f"{Q}('[data-ai-cancel]').click()")
            self.assertTrue(wait(lambda: js(f"!{Q}('#ai-connect-dialog')"), 10))
            self.assertEqual(self.keys.calls, [])
            js(f"{Q}('[data-ai-connect=openai]').click()")
            self.assertTrue(wait(lambda: js(f"!!{Q}('#ai-connect-dialog[open]')"), 10))
            self.assertEqual(js(f"{Q}('#ai-connect-dialog [data-how]')"), None, "OpenAI has one way: a key")
            self.assertTrue(js(f"!!{Q}('#ai-key')"))
            js(f"{Q}('[data-ai-cancel]').click()")
            self.signed.connected = False
            js(f"{Q}('[data-ai-connect=claude]').click()")
            self.assertTrue(wait(lambda: js(f"!!{Q}('#ai-connect-dialog[open]')"), 10))
            js(f"{Q}('[data-ai-go]').click()")
            self.assertTrue(wait(lambda: "isn't signed in" in js(f"({Q}('#ai-connect-msg') || {{}}).innerText"), 20))
            self.signed.connected = True
            js(f"{Q}('[data-ai-go]').click()")
            self.assertTrue(wait(lambda: js(f"!!{Q}('[data-ai-tile=claude] [data-ai-disconnect]')"), 20))
            self.assertEqual(js(f"{Q}('[data-ai-tile=claude] .ai-how').innerText").split(" · ")[0], "Claude subscription")

    def test_it_fits_and_reads_at_both_widths_in_light_and_dark(self):
        self.keys.put("openai", OPENAI_KEY)
        ai_connect.settings.set_ai_choice(self.d, {ai_connect.settings.AI_OPENAI_HOW: "key", ai_connect.settings.AI_OPENAI_MODELS: "gpt-fake-large"}, ai_connect.ALLOWED)
        with chrome() as cdp:
            js = self.show(cdp)
            for theme in ("light", "dark"):
                js(f"document.documentElement.dataset.theme = '{theme}'")
                for w in WIDTHS:
                    with self.subTest(theme=theme, width=w):
                        cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, self.sid)
                        self.assertEqual(js("document.documentElement.scrollWidth <= window.innerWidth"), True, "no sideways scroll")
                        self.assertEqual(js("Array.from(document.querySelectorAll('.ai-prov, #ai-model')).every(e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.left >= 0 && r.right <= window.innerWidth; })"), True)
                        self.assertEqual(js("Array.from(document.querySelectorAll('.ai-prov')).every(t => t.getBoundingClientRect().height > 40)"), True)
                        # the words read against their ground in both themes: text colour differs from the tile's background
                        self.assertEqual(js("Array.from(document.querySelectorAll('.ai-prov h3, .ai-prov p')).every(e => getComputedStyle(e).color !== getComputedStyle(e.closest('.ai-prov')).backgroundColor)"), True)
                js(f"{Q}('[data-ai-connect=claude]').click()")
                self.assertTrue(wait(lambda: js(f"!!{Q}('#ai-connect-dialog[open]')"), 10))
                self.assertEqual(js(f"(() => {{ const r = {Q}('#ai-connect-dialog').getBoundingClientRect(); return r.left >= 0 && r.right <= window.innerWidth; }})()"), True)
                js(f"{Q}('[data-ai-cancel]').click()")
                self.assertTrue(wait(lambda: js(f"!{Q}('#ai-connect-dialog')"), 10))


if __name__ == "__main__":
    unittest.main()
