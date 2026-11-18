"""Row 1220: messages typed while ask clark works are queued above the box and sent one at a time, in order.

Run: python3 dev/run_tests.py test_ask_queue
Headless Chrome, the real page, a stub for the server's ask. Widths 1400 and 900 only. Covers: Enter queues what is typed (box emptied, the
question not sent), the lines are small, in send order, one line cut with an ellipsis, each with a bin named "Remove this message" that
Enter presses with no question asked, the next is sent by itself when the one before is answered and leaves the list, each is its own
question with its own answer, Stop leaves the queue waiting with "Send them" and "Clear", a failed answer does the same, five at most, the
panel closing or a new chat drops the queue only on the second press, screen reader lines, and at 900 only the first two with "and N more".
"""
import json
import unittest

from test_ask_panel import Stub
from test_report_editor import Base
from test_server import chrome

SETTLE = "document.querySelector('#ask-box') && !document.querySelector('#ask-send').disabled"
LINES = "JSON.stringify(Array.from(document.querySelectorAll('#ask-queue li[data-queued]')).map(function(l){return l.querySelector('.ask-queue-text').textContent}))"
SHOWN = ("JSON.stringify(Array.from(document.querySelectorAll('#ask-queue li')).filter(function(l){return l.getBoundingClientRect().height>0})"
         ".map(function(l){return l.textContent.trim()}))")
LONG = "Which of the open risks on the use cases that are not started yet have no owner and no due date set at all, and who should be asked about them first this week"


class FailingStub(Stub):
    """The questions named in `fail` come back with no answer."""
    fail = ()

    def ask(self, body):
        if body["question"] in self.fail:
            self.calls.append(("ask", body))
            self.hold.wait(30)
            return 200, {"ok": False, "code": "no_answer", "message": "No answer came back. Wait a moment and ask again."}
        return super().ask(body)


class Queue(Base):
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

    def working(self, p, text="Summarise the risks"):
        self.stub.calls.clear()
        self.stub.stopped = False
        self.stub.hold.clear()
        p.js("document.querySelector('#ask-box').focus()")
        p.type(text)
        p.js("document.querySelector('#ask-send').click()")
        p.until("!!document.querySelector('#ask-stop')", "the question is out")

    def queue(self, p, text):
        n = len(json.loads(p.js(LINES)))
        p.js("document.querySelector('#ask-box').focus()")
        p.type(text)
        p.key("Enter", code="Enter", vk=13)
        p.until(f"document.querySelectorAll('#ask-queue li[data-queued]').length === {n + 1}", f"{text!r} was queued")

    def lines(self, p):
        return json.loads(p.js(LINES))

    def press(self, cdp, p, selector):
        p.js(f"document.querySelector({json.dumps(selector)}).focus()")
        for kind in ("keyDown", "keyUp"):   # a real Enter on a focused button carries its character, which is what presses it
            cdp.call("Input.dispatchKeyEvent", {"type": kind, "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13, **({"text": "\r"} if kind == "keyDown" else {})}, p.sid)

    def asked(self):
        return [c[1]["question"] for c in self.stub.calls if c[0] == "ask"]

    def test_enter_queues_in_send_order_and_the_box_is_emptied(self):
        for width in (1400, 900):
            with chrome() as cdp:
                p = self.open_panel(cdp, width)
                self.working(p)
                self.queue(p, "Second question")
                self.queue(p, "Third question")
                self.assertEqual(self.lines(p), ["Second question", "Third question"], f"{width}: in the order they will be sent")
                self.assertEqual(p.js("document.querySelector('#ask-box').value"), "", f"{width}: the box is empty again")
                self.assertEqual(self.asked(), ["Summarise the risks"], f"{width}: nothing was sent while it works")
                self.assertEqual(p.js("document.activeElement.id"), "ask-box", f"{width}: focus stays in the box")
                self.assertEqual(p.js("document.querySelector('#ask-queue').getAttribute('aria-label')"), "Messages waiting to be sent")
                self.assertEqual(p.js("document.querySelector('#ask-queue-say').textContent"), "Message queued. 2 waiting")
                above = p.js("document.querySelector('#ask-queue').getBoundingClientRect().bottom <= document.querySelector('#ask-box').getBoundingClientRect().top")
                self.assertTrue(above, f"{width}: above the typing space")
                size = p.js("parseFloat(getComputedStyle(document.querySelector('#ask-queue li')).fontSize) < parseFloat(getComputedStyle(document.querySelector('#ask-box')).fontSize)")
                self.assertTrue(size, f"{width}: smaller than what is typed")
                self.stub.hold.set()

    def test_a_long_message_is_one_line_cut_with_an_ellipsis(self):
        for width in (1400, 900):
            with chrome() as cdp:
                p = self.open_panel(cdp, width)
                self.working(p)
                self.queue(p, LONG)
                m = json.loads(p.js("JSON.stringify((function(){var l=document.querySelector('#ask-queue li'),t=l.querySelector('.ask-queue-text'),c=getComputedStyle(t);"
                                    "return {h:l.getBoundingClientRect().height,ell:c.textOverflow,ws:c.whiteSpace,cut:t.scrollWidth>t.clientWidth,"
                                    "right:l.getBoundingClientRect().right,panel:document.querySelector('#ask-panel').getBoundingClientRect().right,vw:innerWidth}})())"))
                self.assertLessEqual(m["h"], 28, f"{width}: one line")
                self.assertEqual((m["ell"], m["ws"]), ("ellipsis", "nowrap"), f"{width}: cut with an ellipsis")
                self.assertTrue(m["cut"], f"{width}: it is long enough to be cut")
                self.assertLessEqual(m["panel"], m["vw"], f"{width}: the panel stays on the screen")
                self.stub.hold.set()

    def test_the_bin_is_named_reached_by_tab_and_removes_with_enter(self):
        for width in (1400, 900):
            with chrome() as cdp:
                p = self.open_panel(cdp, width)
                self.working(p)
                self.queue(p, "Second question")
                self.queue(p, "Third question")
                self.assertEqual(p.js("document.querySelector('.ask-queue-del').getAttribute('aria-label')"), "Remove this message")
                self.assertEqual(p.js("document.querySelectorAll('.ask-queue-del').length"), 2)
                p.js("document.querySelector('#ask-box').focus()")
                p.key("Tab", modifiers=8, code="Tab", vk=9)     # Shift+Tab from the box lands on the last bin
                self.assertEqual(p.js("document.activeElement.classList.contains('ask-queue-del') && document.activeElement.closest('li').textContent"), "Third question", f"{width}")
                p.key("Tab", modifiers=8, code="Tab", vk=9)
                self.assertEqual(p.js("document.activeElement.closest('li').textContent"), "Second question", f"{width}: the bins are in Tab order, the first one first")
                for kind in ("keyDown", "keyUp"):
                    cdp.call("Input.dispatchKeyEvent", {"type": kind, "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13, **({"text": "\r"} if kind == "keyDown" else {})}, p.sid)
                p.until("document.querySelectorAll('#ask-queue li[data-queued]').length === 1", "the line left")
                self.assertEqual(self.lines(p), ["Third question"], f"{width}: only the one pressed went; no question was asked")
                p.until("document.activeElement.classList.contains('ask-queue-del')", f"{width}: focus went to the next bin")
                p.until("document.querySelector('#ask-queue-say').textContent === 'Message removed. 1 waiting'", "a screen reader is told")
                self.stub.hold.set()
                p.until("!document.querySelector('#ask-stop')", "all answered", 30)
                self.assertEqual(self.asked(), ["Summarise the risks", "Third question"], f"{width}: the removed one was never sent")

    def test_the_next_is_sent_by_itself_and_each_has_its_own_answer(self):
        for width in (1400, 900):
            with chrome() as cdp:
                p = self.open_panel(cdp, width)
                self.working(p)
                self.queue(p, "Second question")
                self.queue(p, "Third question")
                self.stub.hold.set()
                p.until("document.querySelectorAll('.ask-turn').length === 6 && !document.querySelector('#ask-stop')", "three questions and three answers", 30)
                self.assertEqual(self.asked(), ["Summarise the risks", "Second question", "Third question"], f"{width}: one at a time, in order")
                self.assertEqual(self.lines(p), [], f"{width}: the list is empty")
                self.assertEqual(p.js("document.querySelectorAll('#ask-queue').length"), 0)
                roles = p.js("Array.from(document.querySelectorAll('.ask-turn')).map(function(t){return t.dataset.role}).join()")
                self.assertEqual(roles, "user,assistant,user,assistant,user,assistant", f"{width}: each question has its own answer")
                earlier = [c[1]["earlier"] for c in self.stub.calls if c[0] == "ask"]
                self.assertEqual([len(e) for e in earlier], [0, 2, 4], f"{width}: each is asked after the one before it, with it as the earlier chat")

    def test_stop_leaves_the_queue_waiting_and_send_them_and_clear_work(self):
        for width in (1400, 900):
            with chrome() as cdp:
                p = self.open_panel(cdp, width)
                self.working(p)
                self.queue(p, "Second question")
                self.queue(p, "Third question")
                p.js("document.querySelector('#ask-stop').click()")
                p.until("!document.querySelector('#ask-stop') && !!document.querySelector('#ask-queue-held')", "stopped, the queue waits", 30)
                self.assertEqual(p.js("document.querySelector('#ask-queue-held span').textContent"), "Stopped. 2 messages are waiting")
                self.assertEqual(p.js("document.querySelector('#ask-queue-send').textContent"), "Send the waiting messages")
                self.assertEqual(p.js("document.querySelector('#ask-queue-clear').textContent"), "Clear")
                self.assertEqual(self.asked(), ["Summarise the risks"], f"{width}: the next did not fire at once")
                self.assertEqual(self.lines(p), ["Second question", "Third question"])
                self.stub.stopped = False
                p.js("document.querySelector('#ask-queue-send').click()")
                p.until("document.querySelectorAll('.ask-turn').length === 6 && !document.querySelector('#ask-stop')", "Send them sent both", 30)
                self.assertEqual(self.asked(), ["Summarise the risks", "Second question", "Third question"], f"{width}")
                self.assertEqual(self.lines(p), [])

    def test_clear_drops_what_waits_and_one_waiting_is_said_in_the_singular(self):
        with chrome() as cdp:
            p = self.open_panel(cdp, 1400)
            self.working(p)
            self.queue(p, "Second question")
            p.js("document.querySelector('#ask-stop').click()")
            p.until("!!document.querySelector('#ask-queue-held')", "stopped, the queue waits", 30)
            self.assertEqual(p.js("document.querySelector('#ask-queue-held span').textContent"), "Stopped. 1 message is waiting")
            p.js("document.querySelector('#ask-queue-clear').click()")
            p.until("!document.querySelector('#ask-queue-box')", "cleared")
            self.assertEqual(self.asked(), ["Summarise the risks"], "Clear sent nothing")
            self.assertEqual(p.js("document.activeElement.id"), "ask-box")

    def test_a_question_with_no_answer_leaves_the_queue_waiting(self):
        self.stub = FailingStub()
        self.stub.fail = ("Summarise the risks",)
        self.s.httpd.ask = self.stub
        with chrome() as cdp:
            p = self.open_panel(cdp, 1400)
            self.working(p)
            self.queue(p, "Second question")
            self.stub.hold.set()
            p.until("!document.querySelector('#ask-stop') && !!document.querySelector('#ask-queue-held')", "no answer: the queue waits", 30)
            self.assertEqual(p.js("document.querySelector('#ask-queue-held span').textContent"), "1 message is waiting")
            self.assertEqual(self.asked(), ["Summarise the risks"], "the next did not fire")

    def test_a_queued_question_with_no_answer_goes_back_to_the_front(self):
        self.stub = FailingStub()
        self.stub.fail = ("Second question",)
        self.s.httpd.ask = self.stub
        with chrome() as cdp:
            p = self.open_panel(cdp, 1400)
            self.working(p)
            self.queue(p, "Second question")
            self.queue(p, "Third question")
            self.stub.hold.set()
            p.until("!document.querySelector('#ask-stop') && !!document.querySelector('#ask-queue-held')", "the queue waits", 30)
            self.assertEqual(self.lines(p), ["Second question", "Third question"], "nothing typed was lost, and the order is kept")

    def test_at_most_five_wait_and_a_plain_line_says_so(self):
        for width in (1400, 900):
            with chrome() as cdp:
                p = self.open_panel(cdp, width)
                self.working(p)
                for n in range(1, 6):
                    self.queue(p, f"Message {n}")
                p.js("document.querySelector('#ask-box').focus()")
                p.type("Message 6")
                p.key("Enter", code="Enter", vk=13)
                p.until("document.querySelector('#ask-note').textContent !== ''", "the line appeared")
                self.assertEqual(p.js("document.querySelector('#ask-note').textContent"), "5 messages are already waiting. Wait for one to be sent, or remove one.")
                self.assertEqual(len(self.lines(p)), 5, f"{width}")
                self.assertEqual(p.js("document.querySelector('#ask-box').value"), "Message 6", f"{width}: what was typed stays")
                self.stub.hold.set()

    def test_closing_or_a_new_chat_drops_the_queue_only_on_the_second_press(self):
        with chrome() as cdp:
            p = self.open_panel(cdp, 1400)
            self.working(p)
            self.queue(p, "Second question")
            self.queue(p, "Third question")
            p.js("document.querySelector('#ask-close').click()")
            p.until("!!document.querySelector('#ask-queue-drop')", "told first")
            self.assertEqual(p.js("document.querySelector('#ask-queue-drop').textContent"), "2 messages are waiting and would be dropped. Press again to go on.")
            self.assertEqual(p.js("!!document.querySelector('#ask-panel')"), True, "the first press did not close it")
            self.assertEqual(len(self.lines(p)), 2)
            p.js("document.querySelector('#ask-close').click()")
            p.until("!document.querySelector('#ask-panel')", "the second press closed it")
            self.stub.hold.set()
            p.key("/", code="Slash", vk=191)
            p.until("!!document.querySelector('#ask-panel')", "reopened")
            p.until(SETTLE, "ready")
            self.assertEqual(p.js("document.querySelectorAll('#ask-queue li').length"), 0, "the queue was not kept")
            self.assertEqual(self.asked(), ["Summarise the risks"], "the dropped ones were never sent")

    def test_a_new_chat_with_a_queue_waiting_says_so_first(self):
        with chrome() as cdp:
            p = self.open_panel(cdp, 1400)
            self.working(p)
            self.queue(p, "Second question")
            p.js("document.querySelector('#ask-stop').click()")
            p.until("!!document.querySelector('#ask-queue-held')", "stopped", 30)
            p.js("document.querySelector('#ask-new').click()")
            p.until("!!document.querySelector('#ask-queue-drop')", "told first")
            self.assertEqual(p.js("document.querySelectorAll('.ask-turn').length"), 2, "the chat was not cleared by the first press")
            p.js("document.querySelector('#ask-new').click()")
            p.until("document.querySelectorAll('.ask-turn').length === 0", "the second press began a new chat")
            self.assertEqual(p.js("document.querySelectorAll('#ask-queue li').length"), 0)
            self.assertEqual(p.js("!!document.querySelector('#ask-queue-drop')"), False)

    def test_at_900_the_first_two_show_and_the_rest_are_counted(self):
        with chrome() as cdp:
            p = self.open_panel(cdp, 900)
            self.working(p)
            for n in range(1, 6):
                self.queue(p, f"Message {n}")
            self.assertEqual(json.loads(p.js(SHOWN)), ["Message 1", "Message 2", "and 3 more"])
            self.assertEqual(p.js("document.querySelector('#ask-box').getBoundingClientRect().right <= innerWidth"), True, "the box is on the screen")
            self.stub.hold.set()
        with chrome() as cdp:
            p = self.open_panel(cdp, 1400)
            self.working(p)
            for n in range(1, 4):
                self.queue(p, f"Message {n}")
            self.assertEqual(len(json.loads(p.js(SHOWN))), 3, "at 1400 all are shown and there is no count")
            self.stub.hold.set()


if __name__ == "__main__":
    unittest.main()
