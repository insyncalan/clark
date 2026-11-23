"""Row 1492: Check again, in a real browser against the real server with fake providers. Classic theme: the tile says Signed in, not checked yet until a
check was answered, Check again (btn sm) and a re-read when the tab gets focus, the steps and a Cancel while a check runs. Cards: the tile is as it was
(markup pinned) with no Check again, no Cancel and no steps. Docker: none of it. At 1400 and 900 px, light and dark. Chrome is required: fails, never skips.

Run: python3 dev/run_tests.py test_ai_connect_page_1492
"""
import hashlib
import json
import os
import shutil
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from _paths import SRC  # noqa: F401
from test_ai_connect import FakeChatGPT, FakeClaude
from test_ai_connect_verify_1492 import Probe
from test_page import DATA, navigate
from test_server import Running, chrome, wait

from clark import ai_connect, ask, page, platform, settings, theme

PAGE_UP = 90
WIDTHS = (1400, 900)


def classic_html():
    return page.layer_theme(page.page_html(tempfile.mkdtemp()), theme.css("prototype-2.0"))


def cards_html():
    return page.page_html(tempfile.mkdtemp())


class Tile(unittest.TestCase):
    html = staticmethod(classic_html)

    def setUp(self):
        self.s = Running(data_for=lambda code, archived=None: DATA.get(code), page_html=self.html)
        self.addCleanup(self.s.close)
        self.d = Path(os.path.realpath(tempfile.mkdtemp(prefix="clark-test-")))
        self.addCleanup(shutil.rmtree, self.d, True)
        self.claude, self.chatgpt = Probe("claude"), Probe("chatgpt")
        self.s.httpd.ai_connect = ai_connect.AiConnect(self.d, self.claude, self.chatgpt)

    def show(self, cdp, width=1400):
        self.sid = navigate(cdp, self.s.port, "#settings&p=ABC&s=claude")
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, self.sid)
        js = lambda e: cdp.js(e, self.sid)          # noqa: E731
        self.assertTrue(wait(lambda: js("!!document.querySelector('[data-ask-tab=all]')"), PAGE_UP))
        js("document.querySelector('[data-ask-tab=all]').click()")
        self.assertTrue(wait(lambda: js("!!document.querySelector('[data-ai-tile=claude]')"), PAGE_UP), "the card is in Settings")
        return js

    def tag(self, js, who="claude"):
        return js(f"document.querySelector('[data-ai-tile={who}] .tag').innerText")


class Classic(Tile):
    def test_first_view_says_not_checked_yet_and_spends_nothing(self):
        for width in WIDTHS:
            with self.subTest(width=width), chrome() as cdp:
                js = self.show(cdp, width)
                self.assertEqual(self.tag(js), "Not connected")
                self.assertEqual(js("document.querySelector('[data-ai-tile=claude] [data-ai-status]').innerText"), "Signed in, not checked yet")
                self.assertEqual(self.claude.requests, [], "viewing spends nothing")
                self.assertEqual(js("document.documentElement.scrollWidth <= window.innerWidth"), True)

    def test_check_again_button_and_focus_reread(self):
        self.claude.signed_in, self.claude.failed, self.claude.why = False, "no_login", "x"
        for width in WIDTHS:
            with self.subTest(width=width), chrome() as cdp:
                self.claude.signed_in, self.claude.failed, self.claude.requests = False, "no_login", []
                js = self.show(cdp, width)
                self.assertEqual(self.tag(js), "Not connected")
                self.assertEqual(js("document.querySelector('[data-ai-check=claude]').className"), "btn sm")
                self.assertEqual(js("document.querySelector('[data-ai-check=claude]').innerText"), "Check again")
                # signed in in Terminal, back to the tab: the tile reads again with no press
                self.claude.signed_in, self.claude.failed = True, None
                js("window.dispatchEvent(new Event('focus'))")
                self.assertTrue(wait(lambda: js("!!document.querySelector('[data-ai-tile=claude] [data-ai-disconnect]')"), 10), "the re-read shows the sign-in")
                self.assertEqual(js("document.querySelector('[data-ai-tile=claude] [data-ai-status]').innerText"), "Signed in, not checked yet")
                self.assertEqual(self.claude.requests, [], "a re-read makes no request")
                # Check again: the one request, then Connected, and focus stays on a control of the tile
                js("document.querySelector('[data-ai-check=claude]').focus()")
                js("document.querySelector('[data-ai-check=claude]').click()")
                self.assertTrue(wait(lambda: self.tag(js) == "Connected", 10))
                self.assertRegex(js("document.querySelector('[data-ai-tile=claude] [data-ai-status]').innerText"), r"^Connected\. Claude answered in [0-9.]+ seconds\. Checked \d\d:\d\d\.$")
                self.assertEqual(len(self.claude.requests), 1)
                self.assertTrue(wait(lambda: js("!!document.querySelector('[data-ai-tile=claude] button:focus')"), 5), "focus stays on the tile's control")
                self.assertEqual(js("!!document.querySelector('[data-ai-check=claude]')"), False, "no Check again on a Connected tile")

    def test_a_failed_check_says_one_sentence_and_check_again_is_there(self):
        self.claude.reply = __import__("clark.ask", fromlist=["x"]).Failure("x")
        with chrome() as cdp:
            js = self.show(cdp)
            js("document.querySelector('[data-ai-check=claude]').click()")
            self.assertTrue(wait(lambda: "did not answer" in js("document.querySelector('[data-ai-tile=claude] [data-ai-why]') ? document.querySelector('[data-ai-tile=claude] [data-ai-why]').innerText : ''"), 10))
            self.assertEqual(self.tag(js), "Not connected")
            self.assertTrue(wait(lambda: js("!!document.querySelector('[data-ai-check=claude]:focus')"), 5), "focus is on Check again")

    def test_steps_and_cancel_at_both_widths(self):
        contrast = r"""(()=>{const lum=(c)=>{const m=c.match(/[\d.]+/g).map(Number).slice(0,3).map(v=>{v/=255;return v<=.03928?v/12.92:Math.pow((v+.055)/1.055,2.4);});return .2126*m[0]+.7152*m[1]+.0722*m[2];};
          const worst=[...document.querySelectorAll('[data-ai-step], [data-ai-cancel]')].map(el=>{let bg=null;for(let e=el;e&&!bg;e=e.parentElement){const c=getComputedStyle(e).backgroundColor;if(!/rgba\(.*, 0\)|transparent/.test(c))bg=c;}
            const a=lum(getComputedStyle(el).color),b=lum(bg||'rgb(255,255,255)');return (Math.max(a,b)+.05)/(Math.min(a,b)+.05);});return worst.length ? Math.min(...worst) : 0;})()"""
        for theme_name in ("light", "dark"):
            for width in WIDTHS:
                with self.subTest(theme=theme_name, width=width), chrome() as cdp:
                    hold = threading.Event()
                    self.claude.hold, self.claude.requests = hold, []
                    self.addCleanup(hold.set)
                    js = self.show(cdp, width)
                    js(f"document.documentElement.dataset.theme = '{theme_name}'")
                    js("document.querySelector('[data-ai-check=claude]').click()")
                    self.assertTrue(wait(lambda: js("!!document.querySelector('[data-ai-step=ask]')"), 10), "the steps show")
                    steps = js("[...document.querySelectorAll('[data-ai-tile=claude] [data-ai-step]')].map(e => e.innerText)")
                    self.assertEqual(steps, ["Checking the command…", "Checking you are signed in…", "Asking for one word…"])
                    self.assertEqual(js("document.querySelector('[data-ai-cancel=claude]').className"), "btn sm")
                    self.assertEqual(js("document.querySelector('[data-ai-cancel=claude]').innerText"), "Cancel")
                    self.assertTrue(js("!!document.querySelector('[data-ai-cancel=claude]:focus')"), "focus is on Cancel")
                    self.assertGreaterEqual(js(contrast), 4.5)
                    self.assertEqual(js("document.documentElement.scrollWidth <= window.innerWidth"), True)
                    js("document.querySelector('[data-ai-cancel=claude]').click()")
                    self.assertTrue(wait(lambda: not js("!!document.querySelector('[data-ai-step]')"), 10))
                    self.assertEqual(self.tag(js), "Not connected")
                    self.assertEqual(js("document.querySelector('[data-ai-tile=claude] [data-ai-why]').innerText"), "Cancelled. Claude is not connected.")
                    self.assertTrue(wait(lambda: js("!!document.querySelector('[data-ai-check=claude]:focus')"), 5), "focus is back on Check again")

    def test_a_lost_server_ends_in_could_not_be_reached(self):
        with chrome() as cdp:
            js = self.show(cdp)
            self.s.close()
            js("document.querySelector('[data-ai-check=claude]').click()")
            self.assertTrue(wait(lambda: "could not be reached" in js("(document.querySelector('[data-ai-tile=claude] [data-ai-why]')||{innerText:''}).innerText"), 15))
            self.assertEqual(js("document.querySelector('[data-ai-tile=claude] [data-ai-why]').innerText"), "Claude could not be reached. Check your internet connection, then press Check again.")


class Killers(Tile):
    """Row 1492, the survivors of the diff-only sweep of AiSettings.jsx and publishApi.js: Classic, 1400 px only (900 is paused with the rest). The page's own
    fetch, setTimeout and clearTimeout are wrapped in the tab, to count what the page asks for, to answer as a broken server would, and to see the 35 second
    wait set and cleared."""

    HELPERS = r"""(()=>{ if (window.__rules) return; window.__rules = []; window.__log = []; window.__delays = []; window.__timers = []; window.__cleared = []; window.__shrink = false; window.__errors = [];
      window.addEventListener('error', (e) => window.__errors.push(String(e.message))); window.addEventListener('unhandledrejection', (e) => window.__errors.push(String(e.reason)));
      const real = window.fetch.bind(window);
      window.fetch = (u, i) => { i = i || {}; const m = i.method || 'GET'; const p = new URL(String(u), location.href).pathname; window.__log.push([m, p]);
        for (const r of window.__rules) if (r.m === m && r.p === p) return r.f(i); return real(u, i); };
      const st = window.setTimeout.bind(window), ct = window.clearTimeout.bind(window);
      window.setTimeout = (fn, ms, ...a) => { const big = ms === 35000; if (big && window.__shrink) ms = 300; const id = st(fn, ms, ...a); if (big) { window.__delays.push(35000); window.__timers.push(id); } return id; };
      window.clearTimeout = (id) => { window.__cleared.push(id); return ct(id); };
    })()"""

    def start(self, width=1400):
        js = self.show(self.cdp, width)
        js(self.HELPERS)
        return js

    def rule(self, js, method, path, body_js):
        """From now on the page's `method path` is answered by body_js (a JS function of the init, returning a promise)."""
        js(f"window.__rules.push({{m: {json.dumps(method)}, p: {json.dumps(path)}, f: {body_js}}})")

    def answer(self, js, method, path, status, body):
        text = body if isinstance(body, str) else json.dumps(body)
        self.rule(js, method, path, f"() => Promise.resolve(new Response({json.dumps(text)}, {{status: {status}}}))")

    def calls(self, js, method, path):
        return js(f"window.__log.filter(e => e[0] === {json.dumps(method)} && e[1] === {json.dumps(path)}).length")

    def why(self, js, who="claude"):
        return js(f"(document.querySelector('[data-ai-tile={who}] [data-ai-why]') || {{innerText: ''}}).innerText")

    def setUp(self):
        super().setUp()
        cm = chrome()
        self.cdp = cm.__enter__()
        self.addCleanup(cm.__exit__, None, None, None)

    def test_a_new_check_starts_at_the_first_step_and_clears_the_old_words(self):
        hold = threading.Event()
        self.claude.hold = hold
        self.addCleanup(hold.set)
        js = self.start()
        js("document.querySelector('[data-ai-check=claude]').click()")
        self.assertTrue(wait(lambda: js("!!document.querySelector('[data-ai-step=ask]')"), 10), "the first check reaches its last step")
        js("document.querySelector('[data-ai-cancel=claude]').click()")
        self.assertTrue(wait(lambda: "Cancelled" in self.why(js), 10))
        self.claude.hold = threading.Event()
        self.addCleanup(self.claude.hold.set)
        js("""window.__seen = []; new MutationObserver(() => { const n = document.querySelectorAll('[data-ai-step]').length;
            if (n) window.__seen.push([n, document.querySelectorAll('[data-ai-why]').length]); }).observe(document.body, {childList: true, subtree: true, characterData: true});""")
        js("document.querySelector('[data-ai-check=claude]').click()")
        self.assertTrue(wait(lambda: js("window.__seen.length > 0"), 10))
        self.assertEqual(js("window.__seen[0][0]"), 1, "the second check starts at the first step, not where the last one stopped")
        self.assertEqual(js("window.__seen.filter(e => e[1] > 0).length"), 0, "the last sentence is not shown while a check runs")
        self.claude.hold.set()

    def test_a_new_check_clears_the_message_and_the_smaller_model_question(self):
        self.claude.reply = ask.Failure("x")
        js = self.start()
        self.answer(js, "POST", "/api/providers/model", 409, {"ok": False, "code": "weaker", "message": "A smaller model asks first."})
        js("(() => { const s = document.querySelector('#ai-model'); s.value = [...s.options].find(o => o.value !== s.value).value; s.dispatchEvent(new Event('change', {bubbles: true})); })()")
        self.assertTrue(wait(lambda: js("!!document.querySelector('[data-ai-weaker]')"), 10))
        self.answer(js, "POST", "/api/providers/disconnect", 503, {"ok": False})
        js("document.querySelector('[data-ai-disconnect=claude]').click()")
        self.assertTrue(wait(lambda: js("document.querySelector('[data-ai-msg]').innerText") != "", 10))
        js("document.querySelector('[data-ai-check=claude]').click()")
        self.assertTrue(wait(lambda: "did not answer" in self.why(js), 10))
        self.assertEqual(js("document.querySelector('[data-ai-msg]').innerText"), "", "the old message is gone")
        self.assertFalse(js("!!document.querySelector('[data-ai-weaker]')"), "the old question is gone")

    def test_chatgpt_has_its_own_steps_its_own_cancel_and_a_check_again_after_a_failed_turn_on(self):
        hold = threading.Event()
        self.chatgpt.hold = hold
        self.addCleanup(hold.set)
        js = self.start()
        self.assertFalse(js("!!document.querySelector('[data-ai-check=chatgpt]')"), "off and with nothing to say: no Check again yet")
        self.assertEqual(js("document.querySelector('[data-ai-connect=chatgpt]').innerText"), "Turn on ChatGPT")
        self.assertEqual(js("document.querySelector('[data-ai-connect=chatgpt]').getAttribute('aria-pressed')"), "false")
        js("document.querySelector('[data-ai-connect=chatgpt]').click()")
        self.assertTrue(wait(lambda: js("!!document.querySelector('[data-ai-tile=chatgpt] [data-ai-step=ask]')"), 4), "ChatGPT's steps follow ChatGPT's check, within seconds")
        self.assertEqual(js("document.querySelectorAll('[data-ai-tile=claude] [data-ai-step]').length"), 0, "Claude's tile shows no check")
        js("document.querySelector('[data-ai-cancel=chatgpt]').click()")
        self.assertTrue(wait(lambda: self.why(js, "chatgpt") == "Cancelled. ChatGPT is not connected.", 10), "the Cancel on ChatGPT's tile cancels ChatGPT's check")
        self.assertTrue(js("!!document.querySelector('[data-ai-check=chatgpt]')"), "Check again is there after a failed Turn on")
        self.assertEqual(self.claude.requests, [])

    def test_a_failed_check_then_an_answered_one_leaves_no_old_sentence_and_the_tile_is_worded(self):
        self.claude.reply = ask.Failure("x")
        js = self.start()
        js("document.querySelector('[data-ai-check=claude]').click()")
        self.assertTrue(wait(lambda: "did not answer" in self.why(js), 10))
        self.claude.reply = None
        js("document.querySelector('[data-ai-check=claude]').click()")
        self.assertTrue(wait(lambda: self.tag(js) == "Connected", 10))
        self.assertEqual(self.why(js), "", "the sentence of the failed check is gone")
        self.assertTrue(js("document.querySelector('[data-ai-msg]').innerText").startswith("Connected."), "the server's note is shown")
        self.assertEqual(js("document.querySelector('[data-ai-disconnect=claude]').innerText"), "Turn off Claude")
        self.assertEqual(js("document.querySelector('[data-ai-disconnect=claude]').getAttribute('aria-pressed')"), "true")

    def test_the_sentence_of_the_check_wins_over_the_status_words(self):
        self.claude.signed_in, self.claude.failed, self.claude.why = False, "no_login", "x"
        js = self.start()
        js("document.querySelector('[data-ai-check=claude]').click()")
        self.assertTrue(wait(lambda: self.why(js).startswith("Claude is not signed in"), 10), self.why(js))
        self.assertEqual(self.why(js), "Claude is not signed in. Open Terminal, type claude, sign in, then press Check again.")

    def test_a_double_press_asks_once_and_the_check_stops_asking_for_progress_when_it_ends(self):
        self.claude.reply = ask.Failure("x")
        js = self.start()
        js("(() => { const b = document.querySelector('[data-ai-check=claude]'); b.click(); b.click(); })()")
        self.assertTrue(wait(lambda: "did not answer" in self.why(js), 10))
        self.assertEqual(self.calls(js, "POST", "/api/providers/verify"), 1, "the second press while a check starts is ignored")
        self.assertTrue(wait(lambda: not js("!!document.querySelector('[data-ai-step]')"), 5))
        js("window.__log.length = 0")
        self.assertFalse(wait(lambda: self.calls(js, "GET", "/api/providers/progress") > 0, 1.6), "no progress is asked for once the check has ended")

    def test_a_reread_that_is_not_the_card_leaves_the_card_and_the_listener_goes_with_the_card(self):
        js = self.start()
        self.answer(js, "GET", "/api/providers", 200, {"ok": True})
        js("window.dispatchEvent(new Event('focus'))")
        self.assertTrue(wait(lambda: self.calls(js, "GET", "/api/providers") == 1, 5))
        self.assertFalse(wait(lambda: js("window.__errors.length") > 0 or not js("!!document.querySelector('[data-ai-tile=claude]')"), 1.5), "an answer that is not the card's changes nothing and breaks nothing")
        js("document.querySelector('[data-ask-tab]:not([data-ask-tab=all])').click()")
        self.assertTrue(wait(lambda: not js("!!document.querySelector('[data-ai-tile=claude]')"), 10), "the card is gone")
        js("window.__log.length = 0")
        js("window.dispatchEvent(new Event('focus'))")
        self.assertFalse(wait(lambda: self.calls(js, "GET", "/api/providers") > 0, 1.5), "a card that is gone reads nothing")

    def test_an_answer_the_page_cannot_use_ends_in_words_not_in_a_fault(self):
        generic = "Something went wrong while this was working. Nothing was changed. If it happens again, restart clark."
        js = self.start()
        for n, (status, body) in enumerate(((200, {"ok": True, "message": "hello"}), (500, {"ok": False, "code": "X-Bad", "message": "Internal secret detail"}),
                                            (409, "<html>no</html>")), 1):
            with self.subTest(status=status):
                js("window.__rules.length = 0")
                self.answer(js, "POST", "/api/providers/verify", status, body)
                js("document.querySelector('[data-ai-check=claude]').click()")
                self.assertTrue(wait(lambda: self.calls(js, "POST", "/api/providers/verify") == n and not js("!!document.querySelector('[data-ai-step]')"), 10), "the check ends")
                self.assertEqual(self.why(js), generic)
                self.assertTrue(js("!!document.querySelector('[data-ai-tile=claude]')"))
                self.assertEqual(js("window.__errors"), [], "no fault in the page")

    def test_a_server_that_never_answers_is_given_up_after_35_seconds_and_the_wait_is_cleared_when_it_answers(self):
        js = self.start()
        js("window.__shrink = true")            # the 35 second wait runs as 0.3 seconds here; the delay it was asked for is recorded
        self.rule(js, "POST", "/api/providers/verify", "(i) => new Promise((res, rej) => { i.signal && i.signal.addEventListener('abort', () => rej(new DOMException('x', 'AbortError'))); })")
        js("document.querySelector('[data-ai-check=claude]').click()")
        self.assertTrue(wait(lambda: "could not be reached" in self.why(js), 10), "a hung server ends in words")
        self.assertEqual(js("window.__delays"), [35000])

    def test_the_35_second_wait_is_cleared_once_the_check_is_answered(self):
        js = self.start()
        js("document.querySelector('[data-ai-check=claude]').click()")
        self.assertTrue(wait(lambda: self.tag(js) == "Connected", 10))
        self.assertEqual(js("window.__delays"), [35000])
        self.assertTrue(js("window.__cleared.includes(window.__timers[0])"), "the wait set for the answer is cleared when the answer comes")


class Cards(Tile):
    html = staticmethod(cards_html)
    PINNED = "f0f0127eeee8abe4966a4e9c99b316dd"

    def test_cards_tile_unchanged_and_no_new_buttons(self):
        for width in WIDTHS:
            with self.subTest(width=width), chrome() as cdp:
                js = self.show(cdp, width)
                self.assertFalse(js("!!document.getElementById('theme')"), "this is Cards")
                html = js("document.querySelector('[data-ai-tile=claude]').outerHTML")
                self.assertEqual(hashlib.md5(html.encode("utf-8")).hexdigest(), self.PINNED, html)
                self.assertEqual(self.tag(js), "Connected", "as today: signed in and on")
                for word in ("Check again", "Cancel", "Signed in, not checked yet", "Checking the command"):
                    self.assertNotIn(word, js("document.querySelector('#ai-settings').innerText"))
                self.assertEqual(js("document.querySelectorAll('[data-ai-check], [data-ai-cancel], [data-ai-step]').length"), 0)


class CardsDocker(Tile):
    html = staticmethod(cards_html)

    def test_cards_in_a_container_keeps_its_tiles_as_today(self):
        with mock.patch.object(platform, "container_mode", return_value=True), chrome() as cdp:
            self.sid = navigate(cdp, self.s.port, "#settings&p=ABC&s=claude")
            js = lambda e: cdp.js(e, self.sid)      # noqa: E731
            self.assertTrue(wait(lambda: js("!!document.querySelector('[data-ask-tab=all]')"), PAGE_UP))
            js("document.querySelector('[data-ask-tab=all]').click()")
            self.assertTrue(wait(lambda: js("!!document.querySelector('[data-ai-tile=claude]')"), PAGE_UP), "the Cards tile is as it was, in a container too")


class Docker(Tile):
    def test_docker_flag_hides_the_connect_panel(self):
        with mock.patch.object(platform, "container_mode", return_value=True), chrome() as cdp:
            self.sid = navigate(cdp, self.s.port, "#settings&p=ABC&s=claude")
            js = lambda e: cdp.js(e, self.sid)      # noqa: E731
            self.assertTrue(wait(lambda: js("!!document.querySelector('[data-ask-tab=all]')"), PAGE_UP))
            js("document.querySelector('[data-ask-tab=all]').click()")
            self.assertTrue(wait(lambda: js("!!document.querySelector('#ai-settings')"), PAGE_UP))
            self.assertFalse(wait(lambda: js("!!document.querySelector('[data-ai-tile]')"), 3), "the connect panel is not shown")
            text = js("document.querySelector('#ai-settings').innerText")
            for word in ("Check again", "Cancel", "Signed in, not checked yet", "Checking the command", "Open Terminal"):
                self.assertNotIn(word, text)
            self.assertEqual(self.claude.requests, [])


if __name__ == "__main__":
    unittest.main()
