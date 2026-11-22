"""Row 1492: Check again, in a real browser against the real server with fake providers. Classic theme: the tile says Signed in, not checked yet until a
check was answered, Check again (btn sm) and a re-read when the tab gets focus, the steps and a Cancel while a check runs. Cards: the tile is as it was
(markup pinned) with no Check again, no Cancel and no steps. Docker: none of it. At 1400 and 900 px, light and dark. Chrome is required: fails, never skips.

Run: python3 dev/run_tests.py test_ai_connect_page_1492
"""
import hashlib
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

from clark import ai_connect, page, platform, settings, theme

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
