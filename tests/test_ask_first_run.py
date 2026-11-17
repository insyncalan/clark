"""#1292 slice 3: the first-run card in an empty ask clark chat, and the panel word "Send the waiting messages".

Run: python3 dev/run_tests.py test_ask_first_run
Headless Chrome, the real page, a stub for the server's ask. The card shows three plain lines (what it reads and that mail, Teams and
calendars are never read; nothing is saved until Apply and every change can be undone; where the question goes, with a link to Settings),
goes away with the first question, comes back in a new chat, and the old "A question sends..." line is not in the panel.
"""
import unittest

from _paths import ROOT
from test_ask_panel import Stub
from test_report_editor import Base
from test_server import chrome

WORDS = (ROOT / "src" / "clark" / "page" / "src" / "edit" / "askWords.js").read_text(encoding="utf-8")
SETTLE = "document.querySelector('#ask-box') && !document.querySelector('#ask-send').disabled"
CARD = "(document.querySelector('#ask-first') || {}).textContent"


class FirstRun(Base):
    def setUp(self):
        super().setUp()
        self.stub = Stub()
        self.s.httpd.ask = self.stub

    def open_panel(self, cdp, width):
        p = self.visit(cdp)
        cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-reduced-motion", "value": "reduce"}]}, p.sid)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
        p.key("/", code="Slash", vk=191)
        p.until("!!document.querySelector('#ask-panel')", "the panel opened on /")
        p.until(SETTLE, "the panel is ready to take a question")
        return p

    def test_card_in_an_empty_chat_goes_with_the_first_question_and_returns_in_a_new_chat(self):
        for width in (1400, 900):
            with chrome() as cdp:
                p = self.open_panel(cdp, width)
                text = p.js(CARD)
                self.assertIn("Ask about this project", text)
                self.assertIn("work items, milestones and use cases", text)
                self.assertIn("Mail, Teams and calendars are never read.", text)
                self.assertIn("Nothing is saved until you press Apply, and every change can be undone.", text)
                self.assertIn("Your question and what it needs go to Claude.", text)
                self.assertEqual(p.js("document.querySelectorAll('#ask-first li').length"), 3, f"{width}: three lines")
                self.assertEqual(p.js("document.querySelector('#ask-first a[data-ask-settings]').textContent"), "Open Settings")
                self.assertTrue(p.js("document.documentElement.scrollWidth <= document.documentElement.clientWidth"), f"{width}: no sideways scroll")
                self.assertGreaterEqual(p.js("Math.round(document.querySelector('#ask-first a').getBoundingClientRect().height)"), 24)
                self.assertEqual(p.js("document.body.textContent.indexOf('A question sends')"), -1, "the old line is gone (it moves to #1294)")
                p.js("document.querySelector('#ask-box').focus()")
                p.type("Summarise the risks")
                p.js("document.querySelector('#ask-send').click()")
                p.until("document.querySelectorAll('.ask-turn').length === 2 && !document.querySelector('#ask-stop')", "answered", 30)
                self.assertEqual(p.js("document.querySelector('#ask-first')"), None, f"{width}: gone once there is a chat")
                p.js("document.querySelector('#ask-new').click()")
                p.until("!!document.querySelector('#ask-first')", f"{width}: a new chat shows the card again")

    def test_card_is_gone_while_the_first_question_is_out(self):
        self.stub.hold.clear()
        with chrome() as cdp:
            p = self.open_panel(cdp, 1400)
            p.js("document.querySelector('#ask-box').focus()")
            p.type("Summarise the risks")
            p.js("document.querySelector('#ask-send').click()")
            p.until("!!document.querySelector('#ask-stop')", "the question is out")
            self.assertEqual(p.js("document.querySelector('#ask-first')"), None)
            self.stub.hold.set()

    def test_third_line_names_the_provider_in_use(self):
        self.stub.provider = "ChatGPT"
        with chrome() as cdp:
            p = self.open_panel(cdp, 1400)
            text = p.js(CARD)
            self.assertIn("Your question and what it needs go to ChatGPT.", text)
            self.assertNotIn("Claude", text)

    def test_words(self):
        self.assertIn('QUEUE_SEND = "Send the waiting messages"', WORDS)
        self.assertNotIn('"Send them"', WORDS)


if __name__ == "__main__":
    unittest.main()
