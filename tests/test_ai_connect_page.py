"""#446: the Settings › AI card in a real browser against the real server, a FAKE keychain and a fake sign-in (nothing real is touched).
Desktop widths 1400 and 900, light and dark.

Run: python3 dev/run_tests.py test_ai_connect_page
The card matches the prototype (system/prototype/views.js, the AI card): a Claude tile with Connect or Disconnect, an OpenAI tile marked Later with
no button and no key box, and the "Model for ask clark" drop-down with the three models. The key is typed in a password box, is empty the
moment it is sent, and is nowhere on the page or in the browser's storage afterwards. Chrome is required: fails, never skips.
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
from test_ai_connect import KEY, FakeKeychain, Signed
from test_ai_route import Fake
from test_ask_settings import make_db

from clark import ai_connect, ai_service, ask_service, page

WIDTHS = (1400, 900)
INTRO = ("Sign in to Claude for ask clark and the AI menu: the passages they send go to Claude. OpenAI comes in a later version. "
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
        self.keys = FakeKeychain()
        self.signed = Signed()
        self.s.httpd.ask = self.service
        self.s.httpd.ai = ai_service.AiService(self.service)
        self.s.httpd.ai_connect = ai_connect.AiConnect(self.d, provider=self.signed, keychain=self.keys)

    def show(self, cdp):
        self.sid = navigate(cdp, self.s.port, "#settings&p=ABC")
        js = lambda e: cdp.js(e, self.sid)          # noqa: E731
        self.assertTrue(wait(lambda: js(f"!!{Q}('#ai-settings .ai-provs')"), 20), "the tiles are in Settings")
        return js

    def type_key(self, js, key):
        js(f"""const i = {Q}('#ai-key'); i.focus(); i.value = {json.dumps(key)}; i.dispatchEvent(new Event('input', {{bubbles: true}}))""")

    def connect_with_key(self, js, key=KEY):
        js(f"{Q}('[data-ai-connect]').click()")
        self.assertTrue(wait(lambda: js(f"!!{Q}('#ai-connect-dialog[open]')"), 10))
        js(f"{Q}('[data-how=key]').click()")
        self.assertTrue(wait(lambda: js(f"!!{Q}('#ai-key')"), 10))
        self.type_key(js, key)
        js(f"{Q}('[data-ai-go]').click()")

    def test_the_card_has_the_prototypes_words_tiles_and_model_box(self):
        with chrome() as cdp:
            js = self.show(cdp)
            self.assertEqual(js(f"{Q}('#ai-settings h2').innerText"), "AI")
            self.assertEqual(js(f"{Q}('#ai-settings > p.muted').innerText"), INTRO)
            tiles = js("Array.from(document.querySelectorAll('.ai-prov')).map(t => [t.querySelector('h3').childNodes[0].textContent.trim(), t.querySelector('.tag').innerText, t.querySelector('p').innerText])")
            self.assertEqual(tiles, [["Claude", "Not connected", "Through your Claude subscription (the Claude command) or an API key."],
                                     ["OpenAI", "Later", "Coming in a later version, with an API key or your ChatGPT sign-in."]])
            self.assertEqual(js(f"{Q}('[data-ai-connect]').innerText"), "Connect…")
            self.assertEqual(js(f"{Q}('[data-ai-tile=openai]').querySelectorAll('button, input, select, a').length"), 0, "no button and no key box on the OpenAI tile")
            self.assertEqual(js(f"{Q}('[data-ai-tile=openai]').getAttribute('aria-disabled')"), "true")
            self.assertEqual(js(f"{Q}('label[for=ai-model]').innerText"), "Model for ask clark")
            self.assertEqual(js(f"{Q}('#ai-model').innerText"), "Connect Claude first")
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
            self.assertTrue(wait(lambda: js(f"!!{Q}('[data-ai-disconnect]')"), 20), js(f"({Q}('#ai-connect-msg') || {{}}).innerText"))
            self.assertEqual(js("window.__sent.length"), 1)
            self.assertEqual(js("window.__sent[0].boxAtSend"), "", "the box is empty by the time the request is sent")
            self.assertIn(KEY, js("window.__sent[0].body"), "the key went to the server, once")
            self.assertEqual(self.keys.secret, KEY)
            self.assertEqual(js(f"{Q}('[data-ai-tile=claude] .tag').innerText"), "Connected")
            self.assertEqual(js(f"{Q}('.ai-how').innerText"), "API key · Claude Opus 5.5, Claude Sonnet 5.5, Claude Haiku 5.5")
            self.assertEqual(js(f"{Q}('#ai-connect-dialog')"), None, "the box is gone")
            # nowhere on the page, nowhere in the browser
            for piece in (KEY, KEY[-4:], KEY[:20]):
                self.assertFalse(js(f"document.documentElement.outerHTML.includes({json.dumps(piece)})"), piece)
                self.assertFalse(js(f"document.body.innerText.includes({json.dumps(piece)})"), piece)
                self.assertFalse(js(f"JSON.stringify([localStorage, sessionStorage]).includes({json.dumps(piece)})"), piece)
                self.assertFalse(js(f"Array.from(document.querySelectorAll('input, textarea')).some(i => i.value.includes({json.dumps(piece)}))"), piece)
            # the model
            self.assertEqual(js("Array.from(document.querySelectorAll('#ai-model option')).map(o => o.innerText)"),
                             ["Claude Opus 5.5 (recommended)", "Claude Sonnet 5.5", "Claude Haiku 5.5"])
            self.assertEqual(js(f"{Q}('#ai-model').value"), "claude-opus")
            js(f"const m = {Q}('#ai-model'); m.value = 'claude-sonnet'; m.dispatchEvent(new Event('change', {{bubbles: true}}))")
            self.assertTrue(wait(lambda: "Asking will use Claude Sonnet 5.5." in js(f"{Q}('#ai-settings .pub-msg').innerText"), 10))
            self.assertEqual(ai_connect.chosen_model(self.d), "claude-sonnet")
            js("location.reload()")
            self.assertTrue(wait(lambda: js(f"({Q}('#ai-model') || {{}}).value") == "claude-sonnet", 20), "it is kept")
            # disconnect
            js(f"{Q}('[data-ai-disconnect]').click()")
            self.assertTrue(wait(lambda: js(f"!!{Q}('[data-ai-connect]')"), 20))
            self.assertIsNone(self.keys.secret)
            self.assertEqual(js(f"{Q}('[data-ai-tile=claude] .tag').innerText"), "Not connected")
            self.assertEqual(js(f"{Q}('#ai-model').innerText"), "Connect Claude first")
            self.assertEqual(ai_connect.chosen_model(self.d), "")

    def test_a_key_that_cannot_be_kept_is_said_in_the_box_and_the_box_is_empty(self):
        self.keys.fail = True
        with chrome() as cdp:
            js = self.show(cdp)
            self.connect_with_key(js)
            self.assertTrue(wait(lambda: js(f"({Q}('#ai-connect-msg') || {{}}).innerText") == ai_connect.MESSAGES["keychain"], 20), js(f"{Q}('#ai-connect-msg').innerText"))
            self.assertEqual(js(f"{Q}('#ai-key').value"), "")
            self.assertEqual(js(f"{Q}('#ai-key').type"), "password")
            self.assertEqual(js(f"{Q}('#ai-key').getAttribute('autocomplete')"), "off")
            self.assertFalse(js(f"document.documentElement.outerHTML.includes({json.dumps(KEY)})"))

    def test_a_key_that_is_not_one_line_is_refused_in_the_box_in_the_servers_words(self):
        with chrome() as cdp:
            js = self.show(cdp)
            self.connect_with_key(js, KEY + " and more words")
            self.assertTrue(wait(lambda: js(f"({Q}('#ai-connect-msg') || {{}}).innerText") == ai_connect.MESSAGES["bad_key"], 20))
            self.assertIsNone(self.keys.secret)
            self.assertEqual(js(f"{Q}('#ai-key').value"), "")

    def test_the_subscription_needs_no_key_and_esc_and_cancel_close_the_box(self):
        with chrome() as cdp:
            js = self.show(cdp)
            js(f"{Q}('[data-ai-connect]').click()")
            self.assertTrue(wait(lambda: js(f"!!{Q}('#ai-connect-dialog[open]')"), 10))
            self.assertEqual(js(f"{Q}('#ai-key')"), None, "Claude subscription is the first choice and has no key box")
            self.assertEqual(js("Array.from(document.querySelectorAll('#ai-connect-dialog [data-how]')).map(b => b.innerText)"), ["Claude subscription", "API key"])
            js(f"{Q}('[data-ai-cancel]').click()")
            self.assertTrue(wait(lambda: js(f"!{Q}('#ai-connect-dialog')"), 10))
            self.assertEqual(self.keys.calls, [])
            self.signed.connected = False
            js(f"{Q}('[data-ai-connect]').click()")
            self.assertTrue(wait(lambda: js(f"!!{Q}('#ai-connect-dialog[open]')"), 10))
            js(f"{Q}('[data-ai-go]').click()")
            self.assertTrue(wait(lambda: "isn't signed in" in js(f"({Q}('#ai-connect-msg') || {{}}).innerText"), 20))
            self.signed.connected = True
            js(f"{Q}('[data-ai-go]').click()")
            self.assertTrue(wait(lambda: js(f"!!{Q}('[data-ai-disconnect]')"), 20))
            self.assertEqual(js(f"{Q}('.ai-how').innerText").split(" · ")[0], "Claude subscription")

    def test_it_fits_and_reads_at_both_widths_in_light_and_dark(self):
        with chrome() as cdp:
            js = self.show(cdp)
            for theme in ("light", "dark"):
                js(f"document.documentElement.dataset.theme = '{theme}'")
                for w in WIDTHS:
                    with self.subTest(theme=theme, width=w):
                        cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, self.sid)
                        self.assertEqual(js("document.documentElement.scrollWidth <= window.innerWidth"), True, "no sideways scroll")
                        self.assertEqual(js("Array.from(document.querySelectorAll('.ai-prov, #ai-model')).every(e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.left >= 0 && r.right <= window.innerWidth; })"), True)
                        self.assertEqual(js(f"{Q}('.ai-prov').getBoundingClientRect().height > 40"), True)


if __name__ == "__main__":
    unittest.main()
