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
import unittest

from _paths import ROOT
from test_report_editor import Base
from test_server import chrome

WORDS = (ROOT / "src" / "clark" / "page" / "src" / "edit" / "askWords.js").read_text(encoding="utf-8")
NEVER = re.compile(r"\w*(Error|Exception)\b|Traceback|JSON|Not allowed|Bad request|[Rr]eport editor|\bUC\b|!|\bAPI\b|\bHTTP\b")


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
        self.stopped = False

    def status(self, *_):
        self.calls.append(("status", None))
        self.status_hold.wait(20)
        body = {"ok": True, "ask_enabled": self.enabled, "connected": self.connected and self.enabled, "why": ""}
        if self.model:
            body["model"] = self.model
        return 200, body

    def ask(self, body):
        self.calls.append(("ask", body))
        self.hold.wait(30)
        if self.stopped:
            return 200, {"ok": False, "code": "no_answer", "message": "That was stopped before an answer came back."}
        return 200, {"ok": True, "answer": self.answer, "parsed": True, "cites": [], "sources": [], "flags": [], "changes": [], "notes": []}

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

    def opened(self, cdp, ready=True):
        p = self.visit(cdp)
        p.key("/", code="Slash", vk=191)
        p.until("!!document.querySelector('#ask-panel')", "the panel opened on /")
        if ready:
            p.until("!document.querySelector('#ask-box').disabled", "the panel is ready to take a question")
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

    def test_a_reply_that_looks_like_markup_is_inert_text(self):
        self.stub.answer = '<img src=x onerror="window.__pwn=1"><b>bold</b> & <script>window.__pwn=2</script>'
        with chrome() as cdp:
            p = self.opened(cdp)
            self.ask(p, "Anything?")
            p.until("document.querySelectorAll('.ask-turn').length === 2", "the answer")
            self.assertEqual(p.js("document.querySelectorAll('.ask-log img, .ask-log b, .ask-log script').length"), 0)
            self.assertEqual(p.js("document.querySelectorAll('.ask-turn')[1].querySelector('.ask-text').textContent"), self.stub.answer)
            self.assertEqual(p.js("typeof window.__pwn"), "undefined")

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
            p.until("document.querySelector('#ask-off') && document.querySelector('#ask-status').textContent === ''", "the off line")
            self.assertEqual(p.js("document.querySelector('#ask-off').firstChild.textContent.trim()"), "Asking is off. Turn it on in Settings.")
            self.assertTrue(p.js("document.querySelector('#ask-box').disabled"))
            self.assertTrue(p.js("document.querySelector('#ask-send').disabled"))
            p.js("document.querySelector('.ask-form').requestSubmit()")
            p.js("document.querySelector('#ask-box').value = 'hello'; document.querySelector('#ask-box').dispatchEvent(new Event('input'))")
            p.js("document.querySelector('.ask-form').requestSubmit()")
            p.js("document.querySelector('[data-ask-settings]').click()")
            p.until("document.querySelector('#ask-panel') === null && location.hash.indexOf('settings') === 1", "the link went to Settings and closed the panel")
            self.assertEqual(self.stub.count("ask"), 0, "no question reached the server")

    def test_it_reads_as_off_until_the_server_answers(self):
        self.stub.status_hold.clear()
        with chrome() as cdp:
            p = self.opened(cdp, ready=False)
            self.assertTrue(p.js("!!document.querySelector('#ask-off')"), "off while the answer is awaited")
            self.assertTrue(p.js("document.querySelector('#ask-box').disabled"))
            self.stub.status_hold.set()
            p.until("!document.querySelector('#ask-box').disabled", "ready once the server said so")
            self.assertTrue(p.js("document.querySelector('#ask-off') === null"))

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

    def test_the_panel_says_where_a_question_goes_and_who_pays(self):
        """#47a: the connect box says the passages go to Claude and are billed to the signed-in account; off, it says nothing of it."""
        sent = ("Your question and the passages it needs go to Claude, which Anthropic runs, "
                "and are billed to the Claude account signed in on this computer.")
        with chrome() as cdp:
            p = self.opened(cdp)
            self.assertEqual(p.js("document.querySelector('#ask-sent').textContent"), sent)
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
                    p.until("!document.querySelector('#ask-box').disabled", "ready")
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
        self.assertIn("billed to the Claude account", said["SENT_LINE"], "the connect box says who pays (#47a)")
        for name in ("SIGNED_OUT_LINE", "NO_ANSWER_LINE", "NOT_REACHED_LINE", "EMPTY_LINE"):
            self.assertRegex(said[name], r"(Sign in|Wait|Check|Type|then)", f"{name} has a next step")

    def test_the_published_page_has_no_panel(self):
        from clark import page
        html = (ROOT / "src" / "clark" / "page" / "page-view.html").read_text(encoding="utf-8")
        for needle in ("ask-panel", "/api/ask", "billed to the Claude account", "Claude is not signed in"):
            self.assertNotIn(needle, html)
        self.assertIn("ask-panel", (ROOT / "src" / "clark" / "page" / "page.html").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
