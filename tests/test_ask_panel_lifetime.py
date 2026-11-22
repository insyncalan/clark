"""#1292 slice 1: the ask panel's lifetime. A click outside, a page change and Esc never end a chat or stop an answer, and the
top-bar button shows dots while an answer is made and "ask clark, N answer ready" when one landed while the panel was closed.

Run: python3 dev/run_tests.py test_ask_panel_lifetime
Headless Chrome, the real page, a stub for the server's ask.
"""
import unittest

from test_ask_panel import Stub
from test_report_editor import Base
from test_server import chrome

READY = "!!document.querySelector('#ask-panel') && !document.querySelector('#ask-send').disabled"


class Lifetime(Base):
    def setUp(self):
        super().setUp()
        self.stub = Stub()
        self.s.httpd.ask = self.stub

    def start(self, cdp, question="When is go-live?"):
        p = self.visit(cdp)
        p.key("/", code="Slash", vk=191)
        p.until(READY, "the panel is ready")
        p.js("document.querySelector('#ask-box').focus()")
        p.type(question)
        p.js("document.querySelector('#ask-send').click()")
        return p

    def test_a_click_outside_keeps_the_panel_and_the_question(self):
        self.stub.hold.clear()
        with chrome() as cdp:
            p = self.start(cdp)
            p.until("!!document.querySelector('#ask-stop')", "the question is out")
            p.js("document.body.dispatchEvent(new MouseEvent('mousedown', {bubbles: true}))")
            self.assertTrue(p.js("!!document.querySelector('#ask-panel') && !!document.querySelector('#ask-stop')"))
            self.stub.hold.set()
            p.until("document.querySelectorAll('.ask-turn').length === 2", "the answer landed")

    def test_leaving_the_page_keeps_the_chat_and_the_panel(self):
        with chrome() as cdp:
            p = self.start(cdp)
            p.until("document.querySelectorAll('.ask-turn').length === 2", "the answer landed")
            p.js("location.hash = '#settings&p=ABC'")
            p.until("location.hash.indexOf('settings') > 0", "on the next page")
            self.assertTrue(p.js("!!document.querySelector('#ask-panel')"), "the panel is still open")
            self.assertEqual(p.js("document.querySelectorAll('.ask-turn').length"), 2, "the chat is kept")

    def test_closed_while_out_shows_dots_then_one_answer_ready(self):
        self.stub.hold.clear()
        with chrome() as cdp:
            p = self.start(cdp)
            p.until("!!document.querySelector('#ask-stop')", "the question is out")
            self.assertEqual(p.js("document.querySelectorAll('#ask-btn .tb-ask-dots').length"), 0, "no dots while the panel is open")
            p.key("Escape", code="Escape", vk=27)
            p.until("document.querySelector('#ask-panel') === null", "Esc closed the panel")
            self.assertEqual(self.stub.count("stop"), 0, "closing does not stop the answer")
            self.assertEqual(p.js("document.querySelectorAll('#ask-btn .tb-ask-dots').length"), 1, "dots on the button")
            self.assertEqual(p.js("document.querySelector('#ask-btn').getAttribute('aria-label')"), "ask clark, working")
            look = p.js("""(() => { const d = document.querySelector('#ask-btn .tb-ask-dots'), i = [...d.children].map((e) => getComputedStyle(e));
              return JSON.stringify({disp: getComputedStyle(d).display, n: i.length, name: i.map((s) => s.animationName), op: i.map((s) => s.opacity)}); })()""")
            import json
            look = json.loads(look)
            self.assertNotEqual(look["disp"], "none", "the dots are drawn")
            self.assertEqual(look["n"], 3, "three dots")
            self.assertEqual(look["name"], ["none"] * 3, "nothing loops: the dots are still")
            self.assertEqual(look["op"], ["0.8"] * 3, "the dots are drawn at one steady strength")
            self.stub.hold.set()
            p.until("document.querySelector('#ask-btn').getAttribute('aria-label') === 'ask clark, 1 answer ready'", "one answer ready")
            self.assertEqual(p.js("document.querySelectorAll('#ask-btn .tb-ask-dots').length"), 0, "the dots are gone")
            self.assertEqual(p.js("document.querySelectorAll('#ask-btn .tb-ask-ready').length"), 1)
            p.js("document.querySelector('#ask-btn').click()")
            p.until("document.querySelectorAll('.ask-turn').length === 2", "the answer is in the chat that opened")
            self.assertEqual(p.js("document.querySelector('#ask-btn').getAttribute('aria-label')"), "ask clark")
            self.assertEqual(p.js("document.querySelectorAll('#ask-btn .tb-ask-ready').length"), 0)

    def test_an_answer_that_lands_with_the_panel_open_marks_nothing(self):
        with chrome() as cdp:
            p = self.start(cdp)
            p.until("document.querySelectorAll('.ask-turn').length === 2", "the answer landed")
            p.key("Escape", code="Escape", vk=27)
            p.until("document.querySelector('#ask-panel') === null", "closed")
            self.assertEqual(p.js("document.querySelector('#ask-btn').getAttribute('aria-label')"), "ask clark")

    def test_a_fresh_page_marks_nothing_before_any_answer(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            p.until("!!document.querySelector('#ask-btn')", "the ask button is there")
            self.assertEqual(p.js("document.querySelector('#ask-btn').getAttribute('aria-label')"), "ask clark")
            self.assertEqual(p.js("document.querySelectorAll('#ask-btn .tb-ask-ready').length"), 0)

    def test_the_ready_mark_is_cleared_for_good_when_the_panel_is_opened(self):
        """Opening resets the count: closing again must not bring the old mark back. The badge shows the number."""
        self.stub.hold.clear()
        with chrome() as cdp:
            p = self.start(cdp)
            p.until("!!document.querySelector('#ask-stop')", "the question is out")
            p.js("document.querySelector('#ask-btn').click()")
            p.until("document.querySelector('#ask-panel') === null", "the ask button closed the panel")
            self.assertEqual(self.stub.count("stop"), 0, "closing with the ask button does not stop the answer")
            self.stub.hold.set()
            p.until("document.querySelector('#ask-btn').getAttribute('aria-label') === 'ask clark, 1 answer ready'", "one answer ready")
            self.assertEqual(p.js("document.querySelector('#ask-btn .tb-ask-ready').textContent"), "1", "the badge shows the number")
            badge = p.js("(() => { const s = getComputedStyle(document.querySelector('#ask-btn .tb-ask-ready')); return s.height + '|' + (s.backgroundColor === s.color ? 'same' : 'differ'); })()")
            self.assertEqual(badge, "16px|differ", "the badge is 16px high and its number can be read")
            p.js("document.querySelector('#ask-btn').click()")
            p.until("!!document.querySelector('#ask-panel')", "opened")
            p.key("Escape", code="Escape", vk=27)
            p.until("document.querySelector('#ask-panel') === null", "closed again")
            self.assertEqual(p.js("document.querySelector('#ask-btn').getAttribute('aria-label')"), "ask clark", "nothing is marked after the count was cleared")
            self.assertEqual(p.js("document.querySelectorAll('#ask-btn .tb-ask-ready').length"), 0)


if __name__ == "__main__":
    unittest.main()
