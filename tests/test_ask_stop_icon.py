"""Row 1216: while ask clark works, a round Stop icon (a solid square) sits where the Ask arrow sits, in place of it.

Run: python3 dev/run_tests.py test_ask_stop_icon
Headless Chrome, the real page, a stub for the server's ask. Widths 1400 and 900 only. Covers: the square control replaces the
arrow and the old pill is gone, it is named Stop with a tooltip and is reached by Tab, the box keeps its full width, the next
question can be typed while the answer is made and Enter does not send it, pressing it by keyboard stops the answer and the
arrow comes back, and Esc is checked for what it does today.
"""
import json
import unittest

from test_ask_panel import Stub
from test_report_editor import Base
from test_server import chrome

SETTLE = "document.querySelector('#ask-box') && !document.querySelector('#ask-send').disabled"
LOOK = ("JSON.stringify((function(){var b=document.querySelector('#ask-stop'), r=b.getBoundingClientRect(), t=document.querySelector('#ask-box').getBoundingClientRect();"
        "return {w:r.width,h:r.height,radius:getComputedStyle(b).borderRadius,text:b.textContent.trim(),label:b.getAttribute('aria-label'),title:b.title,"
        "rect:!!b.querySelector('svg rect'),tab:b.tabIndex,disabled:b.disabled,type:b.type,boxRight:t.right,left:r.left,boxW:t.width,"
        "pills:document.querySelectorAll('.ask-actions .btn:not(.primary)').length,sends:document.querySelectorAll('#ask-send').length,"
        "buttons:document.querySelectorAll('.ask-actions button:not(#ask-attach)').length}})())")


class StopIcon(Base):
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

    def ask(self, p, text):
        p.js("document.querySelector('#ask-box').focus()")
        p.type(text)
        p.js("document.querySelector('#ask-send').click()")
        p.until("!!document.querySelector('#ask-stop')", "the question is out")

    def test_the_square_replaces_the_arrow_and_the_pill_is_gone(self):
        for width in (1400, 900):
            self.stub.hold.set()
            with chrome() as cdp:
                p = self.open_panel(cdp, width)
                idle = float(p.js("document.querySelector('#ask-box').getBoundingClientRect().width"))
                self.stub.hold.clear()
                self.ask(p, "Summarise the risks")
                m = json.loads(p.js(LOOK))
                self.assertEqual(m["sends"], 0, f"{width}: the arrow is replaced")
                self.assertEqual(m["pills"], 0, f"{width}: no separate Stop pill")
                self.assertEqual(m["buttons"], 1, f"{width}: one control at the right end")
                self.assertEqual(m["text"], "", f"{width}: an icon, no word")
                self.assertTrue(m["rect"], f"{width}: a solid square")
                self.assertEqual(m["label"], "Stop")
                self.assertEqual(m["title"], "Stop")
                self.assertEqual((m["w"], m["h"]), (36, 36), f"{width}: the size the arrow had")
                self.assertEqual(m["radius"], "50%", f"{width}: round")
                self.assertEqual(m["type"], "button", f"{width}: it must not submit the form")
                self.assertFalse(m["disabled"])
                self.assertGreaterEqual(m["tab"], 0, f"{width}: reachable by keyboard")
                self.assertLessEqual(m["boxRight"], m["left"], f"{width}: the control is at the right of the box")
                self.assertAlmostEqual(m["boxW"], idle, delta=1, msg=f"{width}: the box keeps the width it has when idle")
                self.stub.hold.set()

    def test_the_next_question_can_be_typed_and_sending_is_held(self):
        self.stub.hold.clear()
        with chrome() as cdp:
            p = self.open_panel(cdp, 1400)
            self.ask(p, "Summarise the risks")
            p.until("document.activeElement && document.activeElement.id === 'ask-box'", "the box has focus while it works")
            p.type("And the next question")
            p.key("Enter", code="Enter", vk=13)
            # Row 1220: Enter while it works queues what was typed (the box is emptied) and still sends nothing.
            p.until("document.querySelectorAll('#ask-queue li[data-queued]').length === 1", "the typed question waits above the box")
            self.assertEqual(p.js("document.querySelector('#ask-box').value"), "")
            self.assertEqual(self.stub.count("ask"), 1, "Enter did not send a second question while it works")
            self.stub.hold.set()
            p.until("document.querySelectorAll('.ask-turn').length === 4 && !document.querySelector('#ask-stop')", "the answer landed and the queued question was asked after it", 30)
            self.assertEqual(self.stub.count("ask"), 2)

    def test_the_keyboard_stops_it_and_the_arrow_comes_back(self):
        self.stub.hold.clear()
        with chrome() as cdp:
            p = self.open_panel(cdp, 900)
            self.ask(p, "Summarise the risks")
            p.js("document.querySelector('#ask-stop').focus()")
            for kind in ("keyDown", "keyUp"):   # a real Enter on a focused button carries its character, which is what presses it
                cdp.call("Input.dispatchKeyEvent", {"type": kind, "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13, **({"text": "\r"} if kind == "keyDown" else {})}, p.sid)
            p.until("!document.querySelector('#ask-stop') && !!document.querySelector('#ask-send')", "the arrow is back", 30)
            self.assertEqual(self.stub.count("stop"), 1)
            self.assertEqual(self.stub.count("ask"), 1, "pressing Stop did not send anything")
            p.until("document.querySelectorAll('.ask-turn').length === 2", "the question stayed and a line follows it")
            self.assertEqual(p.js("document.querySelector('.ask-turn .ask-text').textContent"), "Summarise the risks")

    def test_esc_does_not_stop_the_answer_today(self):
        self.stub.hold.clear()
        with chrome() as cdp:
            p = self.open_panel(cdp, 1400)
            self.ask(p, "Summarise the risks")
            p.key("Escape", code="Escape", vk=27)
            self.assertEqual(self.stub.count("stop"), 0, "Esc does not call stop (reported on the row)")
            self.stub.hold.set()


if __name__ == "__main__":
    unittest.main()
