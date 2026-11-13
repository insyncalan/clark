"""Row 1119: an answer that comes back after the page was left must not land in the chat of the next page.

Run: python3 dev/run_tests.py test_ask_leave_page
A question is held at the server, the person goes to Settings, the answer is let go: the chat they open there is empty.
"""
import threading
import time

from test_ask_panel import Stub
from test_report_editor import Base
from test_server import chrome


class LeavePage(Base):
    def setUp(self):
        super().setUp()
        self.stub = Stub()
        self.s.httpd.ask = self.stub

    def test_an_answer_that_arrives_after_leaving_the_page_is_not_shown_in_the_next_chat(self):
        self.stub.hold.clear()
        with chrome() as cdp:
            p = self.visit(cdp)
            p.key("/", code="Slash", vk=191)
            p.until("!!document.querySelector('#ask-panel') && !document.querySelector('#ask-send').disabled", "the panel is ready")
            p.js("document.querySelector('#ask-box').focus()")
            p.type("When is go-live?")
            p.js("document.querySelector('#ask-send').click()")
            p.until("!!document.querySelector('#ask-stop')", "the question is out")
            p.js("location.hash = '#settings&p=ABC'")
            p.until("document.querySelector('#ask-panel') === null", "leaving the page closed the panel")
            self.stub.hold.set()
            time.sleep(1.5)
            time.sleep(0.5)
            p.key("/", code="Slash", vk=191)
            p.until("!!document.querySelector('#ask-panel')", "the panel opened again")
            n = p.js("document.querySelectorAll('.ask-turn').length")
            self.assertEqual(n, 0, f"the old answer did not land in the new chat (hash {p.js('location.hash')!r}, calls {[c[0] for c in self.stub.calls]})")


class HeldChanges(Stub):
    """An answer that suggests changes comes back at once; the dry run of them is held until let go."""

    def __init__(self):
        super().__init__()
        self.dry_hold = threading.Event()

    def ask(self, body):
        self.calls.append(("ask", body))
        return 200, {"ok": True, "answer": "Move go-live.", "parsed": True, "cites": [], "sources": [], "flags": [], "changes": [{"x": 1}], "notes": [], "reply": "r1"}

    def change_dry(self, body):
        self.calls.append(("change_dry", body))
        self.dry_hold.wait(30)
        return 200, {"ok": True, "plans": [], "from_source": False, "passages": []}


class LeavePageChanges(Base):
    def setUp(self):
        super().setUp()
        self.stub = HeldChanges()
        self.s.httpd.ask = self.stub

    def test_a_dry_run_that_arrives_after_leaving_the_page_is_not_shown_in_the_next_chat(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            p.key("/", code="Slash", vk=191)
            p.until("!!document.querySelector('#ask-panel') && !document.querySelector('#ask-send').disabled", "the panel is ready")
            p.js("document.querySelector('#ask-box').focus()")
            p.type("Move go-live")
            p.js("document.querySelector('#ask-send').click()")
            deadline = time.time() + 15
            while time.time() < deadline and not any(c[0] == "change_dry" for c in self.stub.calls):
                time.sleep(0.1)
            self.assertTrue(any(c[0] == "change_dry" for c in self.stub.calls), "the dry run was asked for")
            p.js("location.hash = '#settings&p=ABC'")
            p.until("document.querySelector('#ask-panel') === null", "leaving the page closed the panel")
            self.stub.dry_hold.set()
            time.sleep(2)
            p.key("/", code="Slash", vk=191)
            p.until("!!document.querySelector('#ask-panel')", "the panel opened again")
            n = p.js("document.querySelectorAll('.ask-turn').length")
            self.assertEqual(n, 0, "the old dry run did not land in the new chat")
