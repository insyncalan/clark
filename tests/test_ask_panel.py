"""#47a (the panel of ask clark): the panel in a real browser, against the real page and routes.

Run: python3 dev/run_tests.py test_ask_panel
Headless Chrome through the shared harness; the page is the real one with fictional demo data. The server's `ask` is a stub that
records every request, so "nothing was sent" is checked by what reached it. Covers: "/" opens the panel outside a field and not
inside one, Esc and a click outside close it and put focus back, the width is kept after a reload, Stop leaves the chat as it was,
the off state sends no request, a reply that looks like markup is inert text, the sign-in line, the status line's model name, the
rotating quip, 1400 and 900 px in light and dark, the published page has no panel, and every sentence the panel says.
"""
import json
import re
import threading
import time
import unittest

from _paths import ROOT
from test_report_editor import Base
from test_server import chrome

WORDS = (ROOT / "src" / "clark" / "page" / "src" / "edit" / "askWords.js").read_text(encoding="utf-8")
NEVER = re.compile(r"\w*(Error|Exception)\b|Traceback|JSON|Not allowed|Bad request|[Rr]eport editor|\bUC\b|!|\bAPI\b|\bHTTP\b")


from clark import ai_connect  # noqa: E402

W_DISCONNECTED = ai_connect.OFF_WORDS


class Stub:
    """What the server's `ask` is in these tests: answers as it is told, and keeps what it was asked."""

    def __init__(self, enabled=True, connected=True, model=""):
        self.enabled, self.connected, self.model = enabled, connected, model
        self.calls = []                          # ("status" | "ask" | "stop", body)
        self.hold = threading.Event()            # a question waits here while it is clear()ed
        self.hold.set()
        self.status_hold = threading.Event()
        self.status_hold.set()
        self.answer = "The pilot goes live in March."
        self.provider, self.why = "", ""         # #54: who the server says a question goes to, and its reason when nothing can answer
        self.stopped = False
        self.sources = []                        # row 890: [{"id", "label"}] the answer used

    def status(self, *_):
        self.calls.append(("status", None))
        self.status_hold.wait(20)
        body = {"ok": True, "ask_enabled": self.enabled, "connected": self.connected and self.enabled, "why": self.why}
        if self.provider:
            body["provider"] = self.provider
        if self.model:
            body["model"] = self.model
        return 200, body

    def ask(self, body):
        self.calls.append(("ask", body))
        self.hold.wait(30)
        if self.stopped:
            return 200, {"ok": False, "code": "no_answer", "message": "That was stopped before an answer came back."}
        return 200, {"ok": True, "answer": self.answer, "parsed": True, "cites": [], "sources": self.sources, "flags": [], "changes": [], "notes": []}

    def open_source(self, body):
        self.calls.append(("open_source", body))
        return 200, {"ok": True}

    def stop(self, body=None):
        self.calls.append(("stop", body))
        self.stopped = True
        self.hold.set()
        return 200, {"ok": True, "stopped": True, "message": "Stopping."}

    def count(self, which):
        return len([c for c in self.calls if c[0] == which])


class Panel(Base):
    def setUp(self):
        super().setUp()
        self.stub = Stub()
        self.s.httpd.ask = self.stub

    def opened(self, cdp, ready=True, before=None):
        p = self.visit(cdp)
        if before:
            p.js(before)
        p.key("/", code="Slash", vk=191)
        p.until("!!document.querySelector('#ask-panel')", "the panel opened on /")
        p.until("document.querySelector('#ask-panel').getAnimations().length === 0", "the panel has finished rising (row 885): its grip is where it is measured")
        if ready:
            p.until("!document.querySelector('#ask-send').disabled", "the panel is ready to take a question")
        return p

    def ask(self, p, text):
        p.js("document.querySelector('#ask-box').focus()")
        p.type(text)
        p.js("document.querySelector('#ask-send').click()")

    def test_slash_opens_outside_a_field_and_not_in_one(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            self.assertTrue(p.js("document.querySelector('#ask-panel') === null"))
            p.edit()
            p.js("document.querySelector('[data-id] [data-title]').focus()")
            p.key("/", code="Slash", vk=191)
            self.assertTrue(p.js("document.querySelector('#ask-panel') === null"), "a / typed in a title is just a character")
            p.js("document.activeElement.blur()")
            p.key("/", code="Slash", vk=191)
            p.until("!!document.querySelector('#ask-panel')", "opened on /")
            self.assertEqual(self.stub.count("status"), 1)

    def test_escape_and_a_click_outside_close_it_and_focus_returns(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            for how in ("escape", "click"):
                p.js("document.querySelector('[data-mode=edit]').focus()")
                p.key("/", code="Slash", vk=191)
                p.until("!!document.querySelector('#ask-panel')", "opened")
                if how == "escape":
                    p.key("Escape", code="Escape", vk=27)
                else:
                    p.mouse("mousePressed", 40, 400, 1)
                    p.mouse("mouseReleased", 40, 400, 0)
                p.until("document.querySelector('#ask-panel') === null", f"closed by {how}")
                p.until("document.activeElement && document.activeElement.dataset.mode === 'edit'", f"focus returned after {how}")

    def test_focus_that_moved_on_after_it_closed_stays_where_it_went(self):
        """Putting focus back waits a moment; if a peek or another control took focus in that moment, it is not pulled away."""
        with chrome() as cdp:
            p = self.visit(cdp)
            p.js("document.querySelector('[data-mode=edit]').focus()")
            p.key("/", code="Slash", vk=191)
            p.until("!!document.querySelector('#ask-panel')", "opened")
            p.until("document.activeElement && document.activeElement.id === 'ask-box'", "the panel is ready and has focus")
            p.js("(() => { document.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true}));"
                 " document.querySelector('[data-mode=view]').focus(); })()")
            p.until("document.querySelector('#ask-panel') === null", "closed")
            time.sleep(0.3)
            self.assertEqual(p.js("document.activeElement && document.activeElement.dataset.mode"), "view",
                             "the control that took focus keeps it")

    def test_a_click_inside_does_not_close_it(self):
        with chrome() as cdp:
            p = self.opened(cdp)
            x, y, _ = p.box("#ask-log")
            p.mouse("mousePressed", x, y, 1)
            p.mouse("mouseReleased", x, y, 0)
            self.assertTrue(p.js("!!document.querySelector('#ask-panel')"))

    def test_it_is_full_height_and_the_width_is_kept_after_a_reload(self):
        with chrome() as cdp:
            p = self.opened(cdp)
            self.assertEqual(p.js("document.querySelector('#ask-panel').getBoundingClientRect().height"), p.js("document.documentElement.clientHeight"))
            before = p.js("document.querySelector('#ask-panel').getBoundingClientRect().width")
            gx, gy, _ = p.box("#ask-grip")
            p.mouse("mousePressed", gx, gy, 1)
            for step in range(1, 7):
                p.mouse("mouseMoved", gx - 30 * step, gy, 1)
            p.mouse("mouseReleased", gx - 180, gy, 0)
            wide = p.js("document.querySelector('#ask-panel').getBoundingClientRect().width")
            self.assertGreater(wide, before + 100, "dragging left made it wider")
            p.reload()
            p.key("/", code="Slash", vk=191)
            p.until("!!document.querySelector('#ask-panel')", "opened again")
            self.assertEqual(p.js("document.querySelector('#ask-panel').getBoundingClientRect().width"), wide, "the width was kept")
            self.assertLessEqual(wide, p.js("document.documentElement.clientWidth"))

    def test_the_status_line_names_the_model_when_there_is_one(self):
        self.stub.model = "Sonnet"
        with chrome() as cdp:
            p = self.opened(cdp)
            self.assertEqual(p.js("document.querySelector('#ask-status').textContent"), "Answering with Sonnet.")
        self.stub.model = ""
        with chrome() as cdp:
            p = self.opened(cdp)
            self.assertEqual(p.js("document.querySelector('#ask-status').textContent"), "Ready. Ask about this project.")

    def test_the_panel_title_reads_ask_clark_and_the_ready_line_is_unchanged(self):
        # row 820: the title is the row's own words; the ready line is a separate sentence and stays
        self.stub.model = ""
        with chrome() as cdp:
            p = self.opened(cdp)
            self.assertEqual(p.js("document.querySelector('#ask-panel h2').textContent.trim()"), "ask clark")
            self.assertEqual(p.js("document.querySelector('#ask-panel').getAttribute('aria-label')"), "ask clark")
            self.assertIn("Ask about this project", p.js("document.querySelector('#ask-status').textContent"))

    def test_a_reply_is_shown_and_sent_with_the_project_and_the_earlier_turns(self):
        with chrome() as cdp:
            p = self.opened(cdp)
            self.ask(p, "When is go-live?")
            p.until("document.querySelectorAll('.ask-turn').length === 2", "the question and the answer")
            self.assertEqual(p.js("[...document.querySelectorAll('.ask-text')].map(e => e.textContent)"), ["When is go-live?", "The pilot goes live in March."])
            self.ask(p, "And after that?")
            p.until("document.querySelectorAll('.ask-turn').length === 4", "the second answer")
            sent = [c[1] for c in self.stub.calls if c[0] == "ask"]
            self.assertEqual(sent[0], {"project": "ABC", "question": "When is go-live?", "earlier": []})
            self.assertEqual(sent[1]["earlier"], [{"role": "user", "text": "When is go-live?"}, {"role": "assistant", "text": "The pilot goes live in March."}])

    def test_the_who_labels_are_for_a_reader_only_and_take_no_room(self):
        with chrome() as cdp:
            p = self.opened(cdp)
            self.ask(p, "When is go-live?")
            p.until("document.querySelectorAll('.ask-turn').length === 2", "the question and the answer")
            self.assertEqual(p.js("[...document.querySelectorAll('.ask-who')].map(e => e.textContent)"), ["You", "Answer"], "a reader still hears who spoke")
            self.assertEqual(p.js("[...document.querySelectorAll('.ask-who')].map(e => e.getBoundingClientRect().height <= 1)"), [True, True], "nothing is drawn above the bubble or the reply")

    def test_new_chat_drops_the_earlier_turns_so_a_refused_chat_can_start_again(self):
        with chrome() as cdp:
            p = self.opened(cdp)
            self.assertEqual(p.js("document.querySelector('#ask-new').textContent"), "New chat")
            self.ask(p, "When is go-live?")
            p.until("document.querySelectorAll('.ask-turn').length === 2", "the question and the answer")
            p.js("document.querySelector('#ask-new').click()")
            p.until("document.querySelectorAll('.ask-turn').length === 0", "the chat was cleared")
            self.ask(p, "And after that?")
            p.until("document.querySelectorAll('.ask-turn').length === 2", "the new chat's answer")
            sent = [c[1] for c in self.stub.calls if c[0] == "ask"]
            self.assertEqual(sent[1]["earlier"], [], "nothing from the old chat is sent again")

    def test_a_reply_that_looks_like_markup_is_inert_text(self):
        self.stub.answer = '<img src=x onerror="window.__pwn=1"><b>bold</b> & <script>window.__pwn=2</script>'
        with chrome() as cdp:
            p = self.opened(cdp)
            self.ask(p, "Anything?")
            p.until("document.querySelectorAll('.ask-turn').length === 2", "the answer")
            self.assertEqual(p.js("document.querySelectorAll('.ask-log img, .ask-log b, .ask-log script').length"), 0)
            self.assertEqual(p.js("document.querySelectorAll('.ask-turn')[1].querySelector('.ask-text').textContent"), self.stub.answer)
            self.assertEqual(p.js("typeof window.__pwn"), "undefined")

    # ----- row 890: the Sources disclosure under an answer -----
    def answered(self, p):
        self.ask(p, "Where did that come from?")
        p.until("document.querySelectorAll('.ask-turn').length === 2", "the answer")

    def test_sources_are_closed_by_default_and_list_the_files_the_answer_used(self):
        self.stub.sources = [{"id": "P1", "label": "plan.xlsx"}, {"id": "P2", "label": "notes.docx"}]
        with chrome() as cdp:
            p = self.opened(cdp)
            self.answered(p)
            self.assertEqual(p.js("document.querySelectorAll('.ask-sources').length"), 1)
            self.assertEqual(p.js("document.querySelector('.ask-sources summary').textContent.trim()"), "Sources")
            self.assertFalse(p.js("document.querySelector('.ask-sources').open"))
            self.assertEqual(p.js("[...document.querySelectorAll('.ask-sources li')].map((l) => l.textContent)"), ["plan.xlsx", "notes.docx"])
            self.assertFalse(p.js("document.querySelector('.ask-sources li').checkVisibility()"), "the names show only when it is opened")
            p.js("document.querySelector('.ask-sources summary').click()")
            self.assertTrue(p.js("document.querySelector('.ask-sources').open"))
            self.assertTrue(p.js("document.querySelector('.ask-sources li').checkVisibility()"))

    def test_a_pdf_source_opens_at_its_page(self):
        self.stub.sources = [{"id": "P1", "label": "Docs/a.pdf (part 2)", "file": "Docs/a.pdf", "page": 4}, {"id": "P2", "label": "plan.xlsx", "file": None, "page": None}]
        with chrome() as cdp:
            p = self.opened(cdp)
            self.answered(p)
            self.assertEqual(p.js("document.querySelectorAll('.ask-sources li button').length"), 1, "only the PDF is a button")
            self.assertEqual(p.js("document.querySelector('.ask-sources li button').textContent"), "Docs/a.pdf")
            p.js("document.querySelector('.ask-sources summary').click()")
            p.js("document.querySelector('.ask-sources li button').click()")
            deadline = time.time() + 10
            while not self.stub.count("open_source") and time.time() < deadline:
                time.sleep(0.1)
            got = [c[1] for c in self.stub.calls if c[0] == "open_source"]
            self.assertEqual([(b["file"], b["page"]) for b in got], [("Docs/a.pdf", 4)])

    def test_sources_open_and_close_on_enter_and_space(self):
        self.stub.sources = [{"id": "P1", "label": "plan.xlsx"}]
        with chrome() as cdp:
            p = self.opened(cdp)
            self.answered(p)
            for key, code, vk, text in (("Enter", "Enter", 13, "\r"), (" ", "Space", 32, " ")):
                p.js("document.querySelector('.ask-sources summary').focus()")
                for want in (True, False):
                    for kind in ("keyDown", "keyUp"):       # a real key press: the keyDown carries the character, as a keyboard's does
                        cdp.call("Input.dispatchKeyEvent", {"type": kind, "key": key, "code": code, "windowsVirtualKeyCode": vk,
                                                            **({"text": text} if kind == "keyDown" else {})}, p.sid)
                    p.until("document.querySelector('.ask-sources').open === %s" % ("true" if want else "false"), f"{code} {'opened' if want else 'closed'} it")

    def test_sources_drop_the_part_suffix_and_list_each_file_once(self):
        labels = ["x/a.md", "x/a.md (part 2)", "x/b.md (part 3)", "notes.xlsx", "the part two plan.md"]
        self.stub.sources = [{"id": "P%d" % i, "label": t} for i, t in enumerate(labels)]
        with chrome() as cdp:
            p = self.opened(cdp)
            self.answered(p)
            self.assertEqual(p.js("[...document.querySelectorAll('.ask-sources li')].map((l) => l.textContent)"),
                             ["x/a.md", "x/b.md", "notes.xlsx", "the part two plan.md"])

    def test_no_sources_control_when_the_answer_has_no_sources(self):
        with chrome() as cdp:
            p = self.opened(cdp)
            self.answered(p)
            self.assertEqual(p.js("document.querySelectorAll('.ask-sources').length"), 0)

    def test_stop_calls_the_route_and_leaves_the_chat_as_it_was(self):
        self.stub.hold.clear()
        with chrome() as cdp:
            p = self.opened(cdp)
            self.ask(p, "Summarise the risks")
            p.until("!!document.querySelector('#ask-stop')", "Stop appeared while the question was out")
            p.js("document.querySelector('#ask-stop').click()")
            p.until("document.querySelectorAll('.ask-turn').length === 2", "the question stayed and the stopped line followed")
            self.assertEqual(self.stub.count("stop"), 1)
            self.assertEqual(p.js("document.querySelector('.ask-turn .ask-text').textContent"), "Summarise the risks")
            self.assertEqual(p.js("document.querySelector('#ask-note').textContent"), "Stopping. Your question and the earlier answers stay here.")
            self.assertEqual(p.js("document.querySelector('#ask-stop')"), None)

    def test_off_sends_no_request_and_links_to_settings(self):
        self.stub.enabled = False
        with chrome() as cdp:
            p = self.opened(cdp, ready=False)
            p.until("document.querySelector('#ask-off') && document.querySelector('#ask-status').textContent !== ''", "the off line")
            self.assertEqual(p.js("document.querySelector('#ask-status').textContent"), "Ready. Ask about this project.", "row 795: the greeting stays while asking is off")
            self.assertTrue(p.js("document.querySelector('#ask-status').compareDocumentPosition(document.querySelector('#ask-off')) & Node.DOCUMENT_POSITION_FOLLOWING"), "the amber line sits under the status line")
            self.assertEqual(p.js("document.querySelector('#ask-off').firstChild.textContent.trim()"), "Asking is off. Turn it on in Settings.")
            self.assertTrue(p.js("document.querySelector('#ask-box').disabled"))
            self.assertTrue(p.js("document.querySelector('#ask-send').disabled"))
            # row 795: the panel keeps its suggestions with asking off, but they are disabled and send nothing
            self.assertEqual(p.js("document.querySelectorAll('#ask-pills button').length"), 6)
            self.assertTrue(p.js("[...document.querySelectorAll('#ask-pills button')].every(b => b.disabled && b.getAttribute('aria-disabled') === 'true')"))
            p.js("document.querySelector('#ask-pills button').click()")
            p.js("document.querySelector('#ask-pills button').dispatchEvent(new MouseEvent('click', {bubbles: true}))")
            self.assertEqual(p.js("document.querySelectorAll('.ask-turn').length"), 0, "a suggestion pressed with asking off adds nothing")
            p.js("document.querySelector('.ask-form').requestSubmit()")
            p.js("document.querySelector('#ask-box').value = 'hello'; document.querySelector('#ask-box').dispatchEvent(new Event('input'))")
            p.js("document.querySelector('.ask-form').requestSubmit()")
            p.js("document.querySelector('[data-ask-settings]').click()")
            p.until("document.querySelector('#ask-panel') === null && location.hash.indexOf('settings') === 1", "the link went to Settings and closed the panel")
            self.assertEqual(self.stub.count("ask"), 0, "no question reached the server")
            # row 795: turning Asking back on restores working suggestions, the box and the greeting
            self.stub.enabled = True
            p.key("/", code="Slash", vk=191)
            p.until("!!document.querySelector('#ask-panel')", "reopened")
            # row 872: the box is usable while the check is out (row 858), so "ready" is Send, not the box
            p.until("!document.querySelector('#ask-send').disabled", "ready again")
            self.assertEqual(p.js("document.querySelector('#ask-off')"), None)
            self.assertEqual(p.js("document.querySelectorAll('#ask-pills button').length"), 6)
            self.assertTrue(p.js("[...document.querySelectorAll('#ask-pills button')].every(b => !b.disabled && !b.hasAttribute('aria-disabled'))"))
            p.js("document.querySelector('#ask-pills button').click()")
            p.until("document.querySelectorAll('.ask-turn').length === 2", "a suggestion asks again")
            self.assertEqual(self.stub.count("ask"), 1)

    def test_it_says_nothing_of_off_or_signed_out_until_the_server_answers(self):
        self.stub.status_hold.clear()
        with chrome() as cdp:
            p = self.opened(cdp, ready=False)
            self.assertTrue(p.js("document.querySelector('#ask-off') === null && document.querySelector('#ask-signed-out') === null"), "no off or signed-out line while the answer is awaited")
            self.assertNotIn("Asking is off", p.js("document.querySelector('#ask-panel').innerText"))
            self.assertTrue(p.js("document.querySelector('#ask-send').disabled"), "Send waits for the answer (row 858: the box does not)")
            self.stub.status_hold.set()
            p.until("!document.querySelector('#ask-send').disabled", "ready once the server said so")
            self.assertTrue(p.js("document.querySelector('#ask-off') === null"))

    def test_row_858_the_box_keeps_its_words_and_the_panel_is_usable_while_it_checks(self):
        """Row 858: the first open's check can take ~15 s. The box takes words and focus at once, they survive the answer, and the
        panel says only the existing checking line meanwhile."""
        self.stub.status_hold.clear()
        with chrome() as cdp:
            p = self.opened(cdp, ready=False)
            t0 = time.time()
            p.until("document.activeElement && document.activeElement.id === 'ask-box'", "the box has focus while the check is out")
            self.assertFalse(p.js("document.querySelector('#ask-box').disabled"), "the box is usable at once")
            p.type("when is go-live")
            self.assertLess(time.time() - t0, 1.0, "the panel was usable within a second")
            self.assertEqual(p.js("document.querySelector('#ask-box').value"), "when is go-live")
            self.assertIn("Checking whether you can ask", p.js("document.querySelector('#ask-status').textContent"))
            self.assertTrue(p.js("document.querySelector('#ask-send').disabled"), "nothing is sent until the check answers")
            p.key("Enter", code="Enter", vk=13)
            self.assertEqual(self.stub.count("ask"), 0)
            self.stub.status_hold.set()
            p.until("!document.querySelector('#ask-send').disabled", "ready")
            self.assertEqual(p.js("document.querySelector('#ask-box').value"), "when is go-live", "the words survived the check")
            self.assertEqual(p.js("document.activeElement.id"), "ask-box", "and so did focus")

    def test_row_858_the_check_runs_once_for_two_opens_and_again_after_settings_changes_it(self):
        with chrome() as cdp:
            p = self.opened(cdp)
            self.assertEqual(self.stub.count("status"), 1)
            p.key("Escape", code="Escape", vk=27)
            p.until("document.querySelector('#ask-panel') === null", "closed")
            p.key("/", code="Slash", vk=191)
            p.until("!!document.querySelector('#ask-panel') && !document.querySelector('#ask-send').disabled", "reopened, ready at once")
            self.assertEqual(self.stub.count("status"), 1, "the second open did not ask again")
            p.key("Escape", code="Escape", vk=27)
            p.until("document.querySelector('#ask-panel') === null", "closed")
            start = p.js("location.hash")
            p.js("location.hash = '#settings&p=ABC'")
            # row 872: the switch can read ready from the earlier read before Settings asks again; the folders answer comes after that ask has started
            p.until("!!document.querySelector('[data-ask-switch]') && !document.querySelector('[data-ask-switch]').disabled && !!document.querySelector('#ask-folders, #ask-folders-none, #ask-folders-note')", "Settings has the asking switch")
            p.js("document.querySelector('[data-ask-switch]').click()")          # a change in Settings: the kept check is dropped
            p.until("document.querySelector('[data-ask-switch]').getAttribute('aria-pressed') === 'false'", "turned off")
            p.js("document.querySelector('[data-ask-switch]').click()")
            p.until("document.querySelector('[data-ask-switch]').getAttribute('aria-pressed') === 'true'", "turned on")
            p.js(f"location.hash = {json.dumps(start)}")
            p.until("!document.querySelector('[data-ask-switch]')", "left Settings")
            p.js("document.activeElement.blur()")
            p.key("/", code="Slash", vk=191)
            p.until("!!document.querySelector('#ask-panel') && !document.querySelector('#ask-send').disabled", "opened again after the change")
            self.assertEqual(self.stub.count("status"), 2, "asked afresh after Settings changed it")

    def test_a_slow_server_shows_no_off_line_until_it_answers_that_asking_is_off(self):
        self.stub.enabled = False
        self.stub.status_hold.clear()
        with chrome() as cdp:
            p = self.opened(cdp, ready=False)
            time.sleep(0.5)
            self.assertTrue(p.js("document.querySelector('#ask-off') === null"), "no off line while pending")
            self.assertNotIn("Asking is off", p.js("document.querySelector('#ask-panel').innerText"))
            self.stub.status_hold.set()
            p.until("!!document.querySelector('#ask-off')", "the off line once the server said off")
            self.assertIn("Asking is off", p.js("document.querySelector('#ask-panel').innerText"))

    def failed_check_claims_nothing(self, p):
        time.sleep(0.8)
        self.assertTrue(p.js("document.querySelector('#ask-off') === null && document.querySelector('#ask-signed-out') === null"), "no off or signed-out line")
        self.assertNotIn("Asking is off", p.js("document.querySelector('#ask-panel').innerText"))
        self.assertNotIn("Ready", p.js("document.querySelector('#ask-status').textContent"), "and it does not say ready")
        self.assertTrue(p.js("document.querySelector('#ask-box').disabled"), "nothing can be sent")
        self.assertTrue(p.js("document.querySelector('#ask-send').disabled"))
        self.assertEqual(self.stub.count("ask"), 0)

    def test_a_check_that_fails_does_not_say_asking_is_off_the_request_threw(self):
        with chrome() as cdp:
            p = self.opened(cdp, ready=False, before="const real = window.fetch; window.fetch = function (u) { if (String(u).indexOf('/api/ask/status') >= 0) return Promise.reject(new TypeError('network down')); return real.apply(this, arguments); };")
            self.failed_check_claims_nothing(p)

    def test_a_check_that_fails_does_not_say_asking_is_off_the_status_was_not_200(self):
        self.stub.status = lambda *_: (500, {"ok": False, "message": "That could not be done."})
        with chrome() as cdp:
            self.failed_check_claims_nothing(self.opened(cdp, ready=False))

    def test_a_check_that_fails_does_not_say_asking_is_off_the_body_was_not_a_good_answer(self):
        for body in ({"nonsense": 1}, {"ok": True, "ask_enabled": "yes"}, {"ok": True}):
            with self.subTest(body=body), chrome() as cdp:
                self.stub.status = lambda *_, b=body: (200, b)
                self.failed_check_claims_nothing(self.opened(cdp, ready=False))

    def test_a_panel_reopened_after_a_failed_check_reads_the_new_answer_and_works(self):
        for how in ("500", "threw"):
            for label, enabled, connected in (("ready", True, True), ("off", False, True), ("signed-out", True, False)):
                with self.subTest(failed=how, then=label), chrome() as cdp:
                    self.stub.calls.clear()
                    self.stub.enabled, self.stub.connected = enabled, connected
                    if how == "500":
                        self.stub.status = lambda *_: (500, {"ok": False, "message": "That could not be done."})
                        p = self.opened(cdp, ready=False)
                    else:
                        p = self.opened(cdp, ready=False, before="window.__realFetch = window.fetch; window.fetch = function (u) { if (String(u).indexOf('/api/ask/status') >= 0) return Promise.reject(new TypeError('network down')); return window.__realFetch.apply(this, arguments); };")
                    self.failed_check_claims_nothing(p)
                    p.key("Escape", code="Escape", vk=27)
                    p.until("document.querySelector('#ask-panel') === null", "closed")
                    self.stub.__dict__.pop("status", None)            # the server answers well again
                    p.js("if (window.__realFetch) window.fetch = window.__realFetch")
                    p.key("/", code="Slash", vk=191)
                    p.until("!!document.querySelector('#ask-panel')", "reopened")
                    if label == "ready":
                        p.until("!document.querySelector('#ask-send').disabled", "ready")
                        self.assertEqual(p.js("document.querySelector('#ask-status').textContent"), "Ready. Ask about this project.")
                        self.ask(p, "Hello")
                        p.until("document.querySelector('#ask-panel').innerText.indexOf('The pilot goes live in March.') >= 0", "the answer")
                        self.assertEqual(self.stub.count("ask"), 1)
                    elif label == "off":
                        p.until("!!document.querySelector('#ask-off')", "the off line")
                        self.assertTrue(p.js("document.querySelector('#ask-box').disabled"))
                    else:
                        p.until("!!document.querySelector('#ask-signed-out')", "the sign-in line")
                        self.assertTrue(p.js("document.querySelector('#ask-box').disabled"))
                    if label != "ready":
                        self.assertEqual(self.stub.count("ask"), 0)

    def test_a_good_answer_that_says_off_still_reads_as_off(self):
        self.stub.enabled = False
        with chrome() as cdp:
            p = self.opened(cdp, ready=False)
            p.until("!!document.querySelector('#ask-off')", "the off line once the server said off")

    def test_asking_that_the_server_turned_off_meanwhile_reads_as_off(self):
        with chrome() as cdp:
            p = self.opened(cdp)
            self.stub.ask = lambda body: (409, {"ok": False, "code": "asking_off", "message": "Asking is off, so nothing was sent. Turn it on in Settings to ask questions."})
            self.ask(p, "Hello")
            p.until("!!document.querySelector('#ask-off')", "the panel went to the off line")

    def test_not_signed_in_says_so_with_a_link_to_settings(self):
        self.stub.connected = False
        with chrome() as cdp:
            p = self.opened(cdp, ready=False)
            p.until("!!document.querySelector('#ask-signed-out')", "the sign-in line")
            self.assertTrue(p.js("document.querySelector('#ask-signed-out').textContent").startswith("Claude is not signed in on this computer"))
            self.assertTrue(p.js("document.querySelector('#ask-box').disabled"))
            self.assertEqual(p.js("document.querySelectorAll('#ask-signed-out a[data-ask-settings]').length"), 1)
            self.assertEqual(self.stub.count("ask"), 0)

    def test_with_chatgpt_in_use_the_panel_has_no_line_about_where_text_goes(self):
        """#54, #1062: that line lives in Settings now; the panel names neither Claude nor Anthropic nor billing."""
        self.stub.provider = "ChatGPT"
        with chrome() as cdp:
            p = self.opened(cdp)
            self.assertEqual(p.js("document.querySelector('#ask-sent')"), None)
            self.assertNotIn("Anthropic", p.js("document.querySelector('#ask-panel').textContent"))

    def test_chatgpt_not_signed_in_names_chatgpt(self):
        self.stub.provider, self.stub.connected = "ChatGPT", False
        with chrome() as cdp:
            p = self.opened(cdp, ready=False)
            p.until("!!document.querySelector('#ask-signed-out')", "the sign-in line")
            self.assertTrue(p.js("document.querySelector('#ask-signed-out').textContent").startswith("ChatGPT is not signed in on this computer"))

    def test_after_disconnect_it_says_nothing_is_connected_not_that_nobody_is_signed_in(self):
        self.stub.connected = False
        self.stub.why = W_DISCONNECTED
        with chrome() as cdp:
            p = self.opened(cdp, ready=False)
            p.until("!!document.querySelector('#ask-signed-out')", "the line")
            said = p.js("document.querySelector('#ask-signed-out').textContent")
            self.assertTrue(said.startswith(W_DISCONNECTED), said)
            self.assertNotIn("not signed in", said)
            self.assertEqual(p.js("document.querySelectorAll('#ask-signed-out a[data-ask-settings]').length"), 1)

    def test_the_panel_no_longer_carries_the_billing_sentence(self):
        """#1062: the sentence about where a question goes and who pays moved to Settings; the panel says none of it, on or off."""
        with chrome() as cdp:
            p = self.opened(cdp)
            self.assertEqual(p.js("document.querySelector('#ask-sent')"), None)
            self.assertNotIn("billed", p.js("document.querySelector('#ask-panel').textContent"))
            self.assertEqual(p.js("document.querySelector('#ask-log').getAttribute('role')"), "log", "answers are announced")
        self.stub.enabled = False
        with chrome() as cdp:
            p = self.opened(cdp, ready=False)
            p.until("!!document.querySelector('#ask-off')", "the off line")
            self.assertEqual(p.js("document.querySelector('#ask-sent')"), None)

    def test_the_quip_rotates_and_never_repeats(self):
        self.stub.hold.clear()
        with chrome() as cdp:
            p = self.opened(cdp)
            self.ask(p, "Anything?")
            p.until("!!document.querySelector('#ask-quip') && document.querySelector('#ask-quip').textContent !== ''", "a quip while waiting")
            seen = [p.js("document.querySelector('#ask-quip').textContent")]
            p.until("document.querySelector('#ask-quip').textContent !== " + json.dumps(seen[0]), "the quip changed within ten seconds", seconds=12)
            seen.append(p.js("document.querySelector('#ask-quip').textContent"))
            self.assertNotEqual(seen[0], seen[1])
            self.stub.hold.set()
            p.until("document.querySelector('#ask-quip') === null", "the quip went when the answer came")

    def test_there_are_enough_different_quips_to_never_repeat(self):
        quips = re.findall(r'^  "(.+)",$', WORDS[WORDS.index("QUIPS"):], re.M)
        self.assertGreaterEqual(len(quips), 5)
        self.assertEqual(len(set(quips)), len(quips))

    def test_laptop_widths_light_and_dark(self):
        self.stub.hold.clear()
        with chrome() as cdp:
            p = self.visit(cdp)
            for width in (1400, 900):
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                for theme in ("light", "dark"):
                    p.js(f"document.documentElement.dataset.theme = '{theme}'")
                    p.key("/", code="Slash", vk=191)
                    p.until("!!document.querySelector('#ask-panel')", f"opened at {width} {theme}")
                    p.until("!document.querySelector('#ask-send').disabled", "ready")
                    p.until("document.querySelector('#ask-panel').getAnimations().length === 0", "the panel has finished rising (row 885)")
                    r = p.js("(function(){var r=document.querySelector('#ask-panel').getBoundingClientRect();return {l:r.left,r:r.right,t:r.top,b:r.bottom,w:r.width}})()")
                    edge = p.js("document.documentElement.clientWidth")      # the window less a classic scroll bar (Linux shows one; a Mac hides it)
                    self.assertLessEqual(width - edge, 20)
                    self.assertAlmostEqual(r["r"], edge, delta=1)
                    self.assertAlmostEqual(r["t"], 0, delta=1)
                    self.assertAlmostEqual(r["b"], 900, delta=1)
                    self.assertGreaterEqual(r["l"], 0)
                    page = p.js("getComputedStyle(document.body).backgroundColor")
                    panel = p.js("getComputedStyle(document.querySelector('#ask-panel')).backgroundColor")
                    self.assertNotEqual(panel, "rgba(0, 0, 0, 0)")
                    self.assertEqual(p.js("document.querySelector('#ask-form, .ask-form').scrollWidth <= document.querySelector('.ask-form').clientWidth + 1"), True)
                    self.assertEqual(p.js("document.documentElement.scrollWidth <= document.documentElement.clientWidth"), True, "no sideways scroll")
                    if theme == "dark":
                        self.assertNotEqual(panel, "rgb(255, 255, 255)", "the panel follows dark mode")
                    p.key("Escape", code="Escape", vk=27)
                    p.until("document.querySelector('#ask-panel') === null", "closed")


class Words(unittest.TestCase):
    def test_every_sentence_is_plain_and_none_starts_with_the_product_name(self):
        lines = re.findall(r'export const ([A-Z_]+) = (?:"((?:[^"\\]|\\.)*)"|\(name\) => `([^`]*)`)', WORDS)
        self.assertGreaterEqual(len(lines), 15)
        for name, plain, tpl in lines:
            text = plain or tpl
            self.assertIsNone(NEVER.search(text), f"{name}: {text}")
            self.assertFalse(text.startswith("clark") or text.startswith("Clark"), f"{name} starts with the product name")
        for name, plain, tpl in lines:
            if name.endswith("_LINE") and name not in ("CHECKING_LINE", "READY_LINE", "MODEL_LINE"):
                self.assertRegex(plain or tpl, r"[.…]$", name)
        said = dict((n, p or t) for n, p, t in lines)
        self.assertEqual(said["OFF_LINE"], "Asking is off. Turn it on in Settings.")
        self.assertNotIn("SENT_LINE", said, "the panel has no billing line (#1062)")
        self.assertIn("billed to the Claude account", said["ASK_NOTICE_LINE"], "Settings says who pays (#1062)")
        for name in ("SIGNED_OUT_LINE", "NO_ANSWER_LINE", "NOT_REACHED_LINE", "EMPTY_LINE"):
            self.assertRegex(said[name], r"(Sign in|Wait|Check|Type|then)", f"{name} has a next step")

    def test_the_published_page_has_no_panel(self):
        from clark import page
        html = (ROOT / "src" / "clark" / "page" / "page-view.html").read_text(encoding="utf-8")
        for needle in ("ask-panel", "ask-sources", "/api/ask", "Claude is not signed in"):
            self.assertNotIn(needle, html)
        self.assertIn("ask-panel", (ROOT / "src" / "clark" / "page" / "page.html").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
