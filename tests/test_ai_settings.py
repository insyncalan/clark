"""#72 slice 4: the AI status line in Settings, in a real browser against the real server and a FAKE provider (no sign-in, no model).
Desktop widths 1400 and 900, light and dark.

Run: python3 dev/run_tests.py test_ai_settings
The line is the server's own words (GET /api/ai/status) for each state: on, off, not signed in, busy; while the server has not
answered, or cannot, it says so and AI reads as off. The line is real text at 4.5 to 1. Chrome is required: fails, never skips.
"""
import os
import re
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import _ai_page
from _paths import SRC
from test_page import DATA, navigate
from test_server import Running, chrome, wait
from test_ai_route import Fake
from test_ask_settings import make_db

from clark import ai_menu, ai_service, ask_service, page

PAGE_SRC = Path(page.PAGE).parent / "src"
WIDTHS = (1400, 900)
CHECKING = "Checking whether AI suggestions are on…"
UNAVAILABLE = "AI suggestions are off, because clark could not check just now. Reload the page to try again."
CONTRAST = """(()=>{
  const lum=(c)=>{const m=c.match(/[\\d.]+/g).map(Number).slice(0,3).map(v=>{v/=255;return v<=.03928?v/12.92:Math.pow((v+.055)/1.055,2.4);});return .2126*m[0]+.7152*m[1]+.0722*m[2];};
  const el=document.querySelector('#ai-state'); let bg=null;
  for (let e=el; e && !bg; e=e.parentElement) { const c=getComputedStyle(e).backgroundColor; if (!/rgba\\(.*, 0\\)|transparent/.test(c)) bg=c; }
  const a=lum(getComputedStyle(el).color), b=lum(bg||'rgb(255,255,255)'); return (Math.max(a,b)+.05)/(Math.min(a,b)+.05);
})()"""


class Line(unittest.TestCase):
    def setUp(self):
        self.s = Running(data_for=DATA.get, page_html=lambda: page.page_html(tempfile.mkdtemp()))
        self.addCleanup(self.s.close)
        d = Path(os.path.realpath(tempfile.mkdtemp(prefix="clark-test-")))
        self.addCleanup(shutil.rmtree, d, True)
        self.db = make_db(d)
        self.provider = Fake()
        self.addCleanup(self.provider.release.set)
        self.service = ask_service.AskService(self.db, self.provider, [])
        self.s.httpd.app_settings = __import__("clark.app_settings", fromlist=["x"]).AppSettings(self.db, [], by_user=lambda: "tester")
        self.s.httpd.ask = self.service
        self.s.httpd.ai = ai_service.AiService(self.service)

    def show(self, cdp):
        self.sid = navigate(cdp, self.s.port, "#settings&p=ABC")
        js = lambda e: cdp.js(e, self.sid)          # noqa: E731
        self.assertTrue(wait(lambda: js("!!document.querySelector('#ai-state')"), 20), "the AI entry is in Settings")
        return js

    def line(self, js, words):
        self.assertTrue(wait(lambda: js("document.querySelector('#ai-state').innerText") == words, 20),
                        js("document.querySelector('#ai-state').innerText"))

    def test_each_state_has_its_line(self):
        with chrome() as cdp:
            js = self.show(cdp)
            self.line(js, ai_service.MESSAGES["ready"])
            self.assertEqual(js("document.querySelector('#ai-state').dataset.state"), "ready")
            self.assertEqual(js("document.querySelector('#ai-settings h2').innerText"), "AI")

            self.provider.connected = False
            js("location.reload()")
            self.line(js, ai_menu.why_off("not_signed_in", "Claude"))
            self.assertNotIn("private fault", js("document.querySelector('#ai-settings').innerText"))

            self.provider.connected = True
            with self.provider.lock:                       # a question is being answered: one run at a time
                js("location.reload()")
                self.line(js, ai_menu.why_off("busy"))
                self.assertEqual(js("document.querySelector('#ai-state').dataset.state"), "busy")

            js("document.querySelector('[data-ask-switch]').click()")          # the one switch, under Asking
            self.assertTrue(wait(lambda: js("document.querySelector('#ask-state').innerText") != "", 10))
            js("location.reload()")
            self.line(js, ai_menu.why_off("off"))
            self.assertEqual(js("document.querySelector('#ai-state').dataset.state"), "off")

    def test_without_the_route_the_line_says_it_could_not_check(self):
        self.s.httpd.ai = None
        with chrome() as cdp:
            js = self.show(cdp)
            self.line(js, UNAVAILABLE)

    def test_until_the_server_answers_the_line_says_so(self):
        with chrome() as cdp:
            sid = navigate(cdp, self.s.port, "#dashboard&p=ABC")
            js = lambda e: cdp.js(e, sid)          # noqa: E731
            self.assertTrue(wait(lambda: js("!!document.querySelector('#report')"), 20))
            js("""window.__held = null; const real = window.fetch;
                  window.fetch = function (url) { if (String(url).indexOf('/api/ai/status') >= 0) { const a = arguments; return new Promise((r) => { window.__held = () => r(real.apply(window, a)); }); }
                                                  return real.apply(this, arguments); };
                  location.hash = '#settings&p=ABC'""")
            self.assertTrue(wait(lambda: js("(document.querySelector('#ai-state') || {}).innerText") == CHECKING, 10))
            js("window.__held()")
            self.line(js, ai_service.MESSAGES["ready"])

    def test_the_line_fits_and_reads_at_4_5_to_1_at_both_widths_in_light_and_dark(self):
        with chrome() as cdp:
            js = self.show(cdp)
            self.line(js, ai_service.MESSAGES["ready"])
            for theme in ("light", "dark"):
                js(f"document.documentElement.dataset.theme = '{theme}'")
                for w in WIDTHS:
                    with self.subTest(theme=theme, width=w):
                        cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, self.sid)
                        self.assertEqual(js("document.documentElement.scrollWidth <= window.innerWidth"), True, "no sideways scroll")
                        self.assertEqual(js("var r=document.querySelector('#ai-state').getBoundingClientRect(); r.width > 0 && r.left >= 0 && r.right <= window.innerWidth"), True)
                        self.assertGreaterEqual(js(CONTRAST), 4.5)
                        self.assertEqual(js("getComputedStyle(document.querySelector('#ai-state')).fontSize"), js("getComputedStyle(document.querySelector('#ask-state')).fontSize"))

    def test_the_page_asks_only_the_status_route_and_keeps_nothing_in_the_browser(self):
        with chrome() as cdp:
            js = self.show(cdp)
            self.line(js, ai_service.MESSAGES["ready"])
            self.assertEqual(self.provider.requests, [], "opening Settings asks the provider for nothing")
            self.assertEqual(js("JSON.stringify([Object.keys(localStorage).filter(k => /ai/i.test(k)), Object.keys(sessionStorage).filter(k => /ai/i.test(k))])"), "[[],[]]")

    def test_the_sources_say_nothing_odd_and_the_published_page_has_none_of_it(self):
        text = "\n".join((PAGE_SRC / "edit" / n).read_text(encoding="utf-8") for n in ("AiSettings.jsx",))
        for a, b in re.findall(r'>([^<>{}]{6,})<|"([A-Z][^"]{20,})"', text):
            self.assertFalse(re.match(r"\s*(ask )?clark\b", a or b, re.I), a or b)
        view = (Path(page.PAGE).parent / "page-view.html").read_text(encoding="utf-8")
        for needle in ("/api/ai/", "ai-settings", "AI suggestions are"):
            self.assertNotIn(needle, view, "a published file has no Settings, so none of this")


CLIENT_ENTRY = """import { realAiClient, AI_FAILED_LINE } from %(client)s;
window.calls = [];
window.reply = () => ({status: 200, body: {ok: true, html: "<p>x</p>", notes: ["n"], changes: [{op: "add", text: "x"}]}});
const fetchFn = (url, init) => {
  window.calls.push({url, method: init.method, headers: init.headers, body: init.body ? JSON.parse(init.body) : null, signal: init.signal});
  return new Promise((resolve, reject) => {
    const r = window.reply(url, init);
    if (r === "hang") { init.signal && init.signal.addEventListener("abort", () => reject(Object.assign(new Error("x"), {name: "AbortError"}))); return; }
    if (r === "throw") return reject(new TypeError("Failed to fetch /Users/x/secret"));
    resolve({status: r.status, json: () => r.raw ? Promise.reject(new Error("bad")) : Promise.resolve(r.body)});
  });
};
window.make = () => { window.client = realAiClient({token: () => "T0KEN", fetchFn}); };
window.run = (signal) => { window.done = null; window.client.suggest({option: "rewrite", place: "plain", text: "Some words", instruction: "", extra: "no"}, signal)
  .then((v) => { window.done = {ok: v}; }, (e) => { window.done = {name: e.name, message: e.message}; }); };
window.make();
window.mount = () => {};
"""


class TheRealClient(unittest.TestCase):
    """The page's real client in a browser with a fake fetch: one request with the token and exactly the four fields, a stop signal that
    also asks the server to stop, and one fixed line for any failure."""

    @classmethod
    def setUpClass(cls):
        with mock.patch.object(_ai_page, "ENTRY", CLIENT_ENTRY):
            cls.h = _ai_page.AiHarness(chrome).__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.h.__exit__(None, None, None)

    def setUp(self):
        self.h.ev("window.make(); window.calls.length = 0; window.done = null; "
                  "window.reply = () => ({status: 200, body: {ok: true, html: '<p>x</p>', notes: ['n', 5], changes: [{op: 'add', text: 'x'}]}})")

    def done(self):
        self.assertTrue(self.h.until("window.done !== null"))
        return self.h.ev("window.done")

    def test_one_request_with_the_token_and_the_four_fields_only(self):
        self.h.ev("window.run(new AbortController().signal)")
        got = self.done()
        self.assertEqual(got, {"ok": {"html": "<p>x</p>", "notes": ["n"], "changes": [{"op": "add", "text": "x"}]}})
        self.assertEqual(self.h.ev("window.calls.length"), 1)
        self.assertEqual(self.h.ev("[window.calls[0].url, window.calls[0].method, window.calls[0].headers['X-Clark-Token']]"), ["/api/ai/suggest", "POST", "T0KEN"])
        self.assertEqual(self.h.ev("window.calls[0].body"), {"option": "rewrite", "place": "plain", "text": "Some words", "instruction": ""})

    def test_stop_aborts_the_fetch_and_asks_the_server_to_stop(self):
        self.h.ev("window.reply = (url) => url === '/api/ai/stop' ? {status: 200, body: {ok: true}} : 'hang'; window.ctl = new AbortController(); window.run(window.ctl.signal)")
        self.assertTrue(self.h.until("window.calls.length === 1"))
        self.h.ev("window.ctl.abort()")
        self.assertEqual(self.done()["name"], "AbortError")
        self.assertTrue(self.h.until("window.calls.length === 2"))
        self.assertEqual(self.h.ev("[window.calls[1].url, window.calls[1].method, window.calls[1].headers['X-Clark-Token']]"), ["/api/ai/stop", "POST", "T0KEN"])
        self.assertEqual(self.h.ev("window.calls[0].signal.aborted"), True)

    def test_an_already_stopped_signal_sends_nothing(self):
        self.h.ev("const c = new AbortController(); c.abort(); window.run(c.signal)")
        self.assertEqual(self.done()["name"], "AbortError")
        self.assertEqual(self.h.ev("window.calls.length"), 0)

    def test_any_failure_is_the_one_fixed_line(self):
        for name, reply in (("network", "'throw'"), ("fault", "{status: 500, body: null}"), ("unreadable", "{status: 200, raw: true}"),
                            ("refused", "{status: 409, body: {ok: false, code: 'busy', message: 'Another AI request is running.'}}"),
                            ("failed", "{status: 200, body: {ok: false, code: 'failed', message: 'private words /Users/x'}}"),
                            ("not html", "{status: 200, body: {ok: true}}")):
            with self.subTest(name):
                self.h.ev(f"window.reply = () => ({reply}); window.run(new AbortController().signal)")
                self.assertEqual(self.done(), {"name": "Error", "message": "No suggestion came back. Try again."})

    def test_status_reads_as_off_until_the_server_says_and_follows_it(self):
        self.assertEqual(self.h.ev("window.client.status()"), "off")
        for state in ("ready", "busy", "not_signed_in", "off"):
            self.h.ev(f"window.done = null; window.reply = () => ({{status: 200, body: {{ok: true, state: '{state}', line: 'Words for {state}.'}}}}); "
                      "window.client.refresh().then((s) => { window.done = s; })")
            self.assertEqual(self.done(), state)
            self.assertEqual(self.h.ev("[window.client.status(), window.client.line(), window.calls[window.calls.length-1].url]"),
                             [state, f"Words for {state}.", "/api/ai/status"])
        for bad in ("{status: 403, body: null}", "'throw'", "{status: 200, body: {ok: true, state: 'odd', line: 'x'}}"):
            self.h.ev("window.reply = () => ({status: 200, body: {ok: true, state: 'ready', line: 'Words.'}}); window.client.refresh()")
            self.assertTrue(self.h.until("window.client.status() === 'ready'"))
            self.h.ev(f"window.reply = () => ({bad}); window.client.refresh()")
            self.assertTrue(self.h.until("window.client.status() === 'off' && window.client.line() === ''"), bad)


if __name__ == "__main__":
    unittest.main()
