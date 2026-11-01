"""#50 (Draft email in the editor), the front-end parts: the editor's logic and the DraftEmail component. The wording itself is
built by src/clark/draft_email.py (tested in test_draft_email.py); drafts here come from that module so the two stay in step.

Run: python3 dev/run_tests.py test_draft_email_editor
The repo has no Node, so the logic runs inside headless Chrome (the #33 harness, as test_picker_minimap.py does): the logic and
the component are bundled with the pinned esbuild into a temporary folder and each case is evaluated on a page. Chrome is
required: these tests fail, never skip, without it. The component builds nothing and saves nothing; the route that builds a
draft and the history write wait for the server (see the report on #50), so the callbacks only receive what would be saved.
"""
import contextlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

from _paths import ROOT, SRC, TOOLS

sys.path.insert(0, str(TOOLS))
import build_page  # noqa: E402
import esbuild  # noqa: E402

from clark import draft_email  # noqa: E402
from test_server import Running, chrome, wait  # noqa: E402  (the #33 browser harness, shared)

PAGE_SRC = SRC / "clark" / "page" / "src"
DEMO = ROOT / "tests" / "fixtures" / "draft_email_demo.jsx"
HOSTILE = '<script>window.pwned = 1</script><img src=x onerror="window.pwned = 2">'
NOW = "2026-10-13 09:00"


def item(id_, text, due=None, **kw):
    base = {"id": id_, "project": "ABC", "kind": "actions", "text": text, "due": due, "priority": "Medium",
            "owner": "Dana Hart", "status": "Open", "client_visible": True}
    base.update(kw)
    return base


LATE = item("ABC-A-001", "Share the UAT plan", "2026-10-09", priority="High")
SOON = item("ABC-A-002", "Confirm the test dates", "2026-10-15")
INTERNAL = item("ABC-A-005", "Check the vendor margin", "2026-10-20", client_visible=False)
ITEMS = [LATE, SOON, INTERNAL]
OFFERED = [{"id": i["id"], "text": i["text"]} for i in ITEMS]


def draft(mode="update_request", picked=None, **kw):
    opts = {"mode": mode, "items": ITEMS, "picked": picked, "name": "Dana Hart", "email": "dana@example.org", "from": "Sam",
            "own_domains": ["example.com"], "now": NOW, "project_names": {"ABC": "Example Programme"}}
    opts.update(kw)
    return draft_email.build(opts)


def state(**kw):
    base = {"mode": "update_request", "picked": ["ABC-A-001", "ABC-A-002"], "replyBy": "", "unblocks": "", "includeUpdate": False}
    base.update(kw)
    return base


_PAGE = {}


def test_page_html():
    if "html" not in _PAGE:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "t.js"
            done = esbuild.run(["--bundle", "--format=iife", "--target=es2020", "--charset=utf8", "--tsconfig-raw={}",
                                *build_page.preact_flags(), f"--alias:@src={PAGE_SRC}", str(DEMO), f"--outfile={out}"],
                               cwd=tmp, capture_output=True, text=True)
            assert done.returncode == 0, done.stderr
            script = out.read_text(encoding="utf-8").replace("</script", "<\\/script")
        css = (build_page.TOKENS.read_text(encoding="utf-8") + (build_page.PAGE / "shell.css").read_text(encoding="utf-8"))
        css = css.replace("</style", "<\\/style")
        _PAGE["html"] = (f'<!doctype html>\n<html lang="en-GB"><head><meta charset="utf-8">'
                         f'<meta name="viewport" content="width=device-width, initial-scale=1"><title>t</title>'
                         f'<style>\n{css}</style></head>\n<body><div id="root"></div>\n'
                         f'<script>{script}</script>\n</body></html>\n')
    return _PAGE["html"]


def lit(x):
    return json.dumps(x)


class InBrowser(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stack = contextlib.ExitStack()
        cls.server = Running(page_html=test_page_html)
        cls.stack.callback(cls.server.close)
        cls.cdp = cls.stack.enter_context(chrome())
        tid = next(t["targetId"] for t in cls.cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
        cls.sid = cls.cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
        cls.cdp.call("Emulation.setFocusEmulationEnabled", {"enabled": True}, cls.sid)

    @classmethod
    def tearDownClass(cls):
        cls.stack.close()

    def setUp(self):
        self.load()

    def load(self, width=1400, height=900):
        self.cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": height, "deviceScaleFactor": 1, "mobile": False}, self.sid)
        self.cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{self.server.port}/"}, self.sid)
        self.assertTrue(wait(lambda: self.cdp.js("!!(window.T && window.T.logic)", self.sid)), "the test bundle ran")

    def js(self, expr):
        return self.cdp.js(expr, self.sid)

    def val(self, expr):
        got = self.js(f"(function(){{ try {{ return JSON.stringify({expr}); }} catch (e) {{ return 'ERROR ' + e.message; }} }})()")
        self.assertIsNotNone(got, expr)
        self.assertFalse(got.startswith("ERROR"), f"{expr}: {got}")
        return json.loads(got)

    def error(self, expr):
        got = self.js(f"(function(){{ try {{ {expr}; return 'NO ERROR'; }} catch (e) {{ return e.message; }} }})()")
        self.assertNotEqual(got, "NO ERROR", expr)
        return got

    def settle(self):
        self.cdp.call("Runtime.evaluate", {"expression": "new Promise(r => setTimeout(r, 150))", "awaitPromise": True}, self.sid)

    def mount(self, st=None, d=None, items=OFFERED):
        st = st or state()
        d = draft(picked=st["picked"], mode=st["mode"]) if d is None else d
        self.js(f"T.mountEditor({lit(items)}, {lit(st)}, {lit(d)}, '2026-10-13')")
        self.settle()

    def click(self, selector):
        self.js(f"document.querySelector({lit(selector)}).click()")
        self.settle()

    def text(self, selector):
        return self.js(f"(document.querySelector({lit(selector)}) || {{}}).textContent || ''")


class Logic(InBrowser):
    def test_the_three_kinds_have_plain_labels_and_an_unknown_one_says_what_to_choose(self):
        self.assertEqual(self.val("T.logic.MODES.map((m) => m.label)"), ["Update request", "Chase", "Decision"])
        msg = self.error("T.logic.buildOptions({mode: 'remind'})")
        self.assertEqual(msg, "That kind of email isn't available. Choose Update request, Chase or Decision.")
        self.assertEqual(self.error("T.logic.sentEntry(['ABC-A-001'], 'remind', '2026-10-13')"), msg)

    def test_toggling_keeps_the_order_of_the_offered_items(self):
        got = self.val(f"T.logic.togglePick({lit(OFFERED)}, ['ABC-A-005'], 'ABC-A-001')")
        self.assertEqual(got, ["ABC-A-001", "ABC-A-005"])
        self.assertEqual(self.val(f"T.logic.togglePick({lit(OFFERED)}, ['ABC-A-001'], 'ABC-A-001')"), [])
        self.assertEqual(self.val(f"T.logic.startPicks({lit(OFFERED)}, ['ABC-A-002', 'NOPE'])"), ["ABC-A-002"])
        self.assertEqual(self.val(f"T.logic.startPicks({lit(OFFERED)}, null)"), ["ABC-A-001", "ABC-A-002", "ABC-A-005"])

    def test_the_options_for_the_builder_hold_only_the_editors_own_inputs(self):
        got = self.val("T.logic.buildOptions({mode: 'decision', picked: ['ABC-D-001'], replyBy: '2026-10-15', unblocks: ' the plan ', includeUpdate: 1, secret: 'x'})")
        self.assertEqual(got, {"mode": "decision", "picked": ["ABC-D-001"], "reply_by": "2026-10-15", "unblocks": "the plan", "include_update": True})

    def test_the_tick_count_reads_as_a_sentence(self):
        got = self.val("[[0, 3], [1, 3], [2, 3], [3, 3], [1, 1], [2, 2], [0, 0]].map(([n, of]) => T.logic.pickWords(n, of))")
        self.assertEqual(got, ["0 of 3 items ticked", "1 of 3 items ticked", "2 of 3 items ticked", "3 items ticked", "1 item ticked",
                               "2 items ticked", ""])
        self.assertEqual(self.val("T.logic.NO_OPEN_ITEMS"), draft_email.NO_OPEN_ITEMS)

    def test_the_internal_note_names_the_items_and_the_next_step(self):
        self.assertEqual(self.val("T.logic.internalNote([])"), "")
        one = self.val("T.logic.internalNote(['ABC-A-005'])")
        self.assertEqual(one, "Marked internal: ABC-A-005. It is in this email, so untick it before you copy if the recipient should not see it.")
        many = self.val("T.logic.internalNote(['ABC-A-005', 'ABC-A-006', 'ABC-A-005'])")
        self.assertIn("ABC-A-005, ABC-A-006.", many)
        self.assertIn("They are in this email, so untick them", many)

    def test_the_html_is_cleaned_before_it_is_drawn(self):
        dirty = '<div style="color:red" onclick="x()"><p>Hi</p>' + HOSTILE + '<a href="javascript:x()">link</a></div>'
        got = self.val(f"T.logic.safeHtml({lit(dirty)})")
        self.assertNotIn("script", got.lower())
        self.assertNotIn("<img", got)
        self.assertNotIn("pwned", got, "the words of a script go with it")
        self.assertNotIn("onclick", got)
        self.assertNotIn("href", got)
        self.assertIn('style="color:red"', got)
        self.assertIn("<p>Hi</p>", got)
        self.assertIn("link", got, "the words of a dropped link stay")
        self.assertNotIn("url(", self.val("T.logic.safeHtml('<p style=\"background:url(http://x/y)\">a</p>')"))

    def test_the_builders_own_email_survives_the_cleaning_unchanged_in_content(self):
        d = draft(picked=["ABC-A-001", "ABC-A-002"])
        cleaned = self.val(f"T.logic.safeHtml({lit(d['html'])})")
        for word in ("Share the UAT plan", "Confirm the test dates", "ABC-A-001", "overdue", "Kind regards,"):
            self.assertIn(word, cleaned)
        self.assertIn("<table", cleaned)

    def test_the_two_copies_put_the_right_types_on_the_clipboard(self):
        d = draft(picked=["ABC-A-001"])
        out = self.val(f"T.logic.copyPayload('outlook', {lit(d)}, null)")
        self.assertEqual(sorted(out), ["text/html", "text/plain"])
        self.assertEqual(out["text/html"], d["html"])
        self.assertEqual(out["text/plain"], d["text"])
        txt = self.val(f"T.logic.copyPayload('text', {lit(d)}, null)")
        self.assertEqual(list(txt), ["text/plain"])
        self.assertTrue(txt["text/plain"].startswith(f"Subject: {d['subject']}\n\n"))
        self.assertTrue(txt["text/plain"].endswith(d["text"]))
        edited = self.val(f"T.logic.copyPayload('outlook', {lit(d)}, {{html: '<p>Mine</p>', text: 'Mine'}})")
        self.assertEqual((edited["text/html"], edited["text/plain"]), ("<p>Mine</p>", "Mine"))

    def test_edited_wording_is_cleaned_before_it_is_copied(self):
        d = draft(picked=["ABC-A-001"])
        hostile = '<p style="color:red">Mine</p><img src="https://evil.example/p.gif" onerror="x()"><script>alert(1)</script><a href="javascript:x()" onclick="y()">link</a>'
        out = self.val(f"T.logic.copyPayload('outlook', {lit(d)}, {{html: {lit(hostile)}, text: 'Mine'}})")
        for bad in ("<img", "<script", "onerror", "onclick", "href", "javascript", "evil.example"):
            self.assertNotIn(bad, out["text/html"])
        self.assertIn('<p style="color:red">Mine</p>', out["text/html"])
        self.assertIn("link", out["text/html"])

    def test_a_draft_with_a_problem_cannot_be_copied(self):
        d = draft(picked=[])
        self.assertEqual(d["problems"][0], "No items are ticked. Tick at least one to draft the email.")
        self.assertEqual(self.error(f"T.logic.copyPayload('outlook', {lit(d)}, null)"), d["problems"][0])
        self.assertEqual(self.val(f"T.logic.blocked({lit(d)})"), d["problems"][0])
        self.assertEqual(self.val(f"T.logic.mailLink({lit(d)})")["href"], "")

    def test_a_refused_clipboard_gives_the_fallback_and_never_fails_silently(self):
        d = draft(picked=["ABC-A-001"])
        got = self.cdp.call("Runtime.evaluate", {"expression": f"T.logic.copyNow('outlook', {lit(d)}, null, () => Promise.reject(new Error('no'))).then(JSON.stringify)",
                                                  "awaitPromise": True, "returnByValue": True}, self.sid)["result"]["value"]
        self.assertEqual(json.loads(got), {"ok": False, "blocked": False, "message": "The browser did not copy it. Press ⌘C to copy the selected text."})
        ok = self.cdp.call("Runtime.evaluate", {"expression": f"T.logic.copyNow('text', {lit(d)}, null, () => Promise.resolve()).then(JSON.stringify)",
                                                 "awaitPromise": True, "returnByValue": True}, self.sid)["result"]["value"]
        self.assertEqual(json.loads(ok), {"ok": True, "message": "Copied"})

    def test_the_mail_link_is_offered_only_when_the_text_fits(self):
        d = draft(picked=["ABC-A-001"])
        link = self.val(f"T.logic.mailLink({lit(d)})")
        self.assertTrue(link["href"].startswith("mailto:dana%40example.org?subject="))
        long = dict(d, text="x" * 2000)
        got = self.val(f"T.logic.mailLink({lit(long)})")
        self.assertEqual(got["href"], "")
        self.assertIn("Use Copy for Outlook or Copy as text", got["message"])

    def test_the_mail_limit_is_on_the_finished_link_and_agrees_with_the_builder(self):
        self.assertEqual(self.val("T.logic.MAILTO_LIMIT"), draft_email.MAILTO_LIMIT)
        # 1,700 characters of text, under the old limit of 1,800, is about 2,700 as a link: not offered.
        spaced = dict(draft(picked=["ABC-A-001"]), text="word " * 340)
        self.assertEqual(len(spaced["text"]), 1700)
        self.assertEqual(self.val(f"T.logic.mailLink({lit(spaced)})")["href"], "")
        self.assertFalse(draft_email.mailto_offered(spaced))
        # Both sides build the same link, so they agree at the edge too.
        for text in ("x" * 1800, "word " * 100 + "it's (a) test!*", "caf\u00e9 \u2014 \u2713\nnext line"):
            d = dict(draft(picked=["ABC-A-001"]), text=text)
            self.assertEqual(self.val(f"T.logic.mailLink({lit(d)})")["href"], draft_email.mailto_link(d))

    def test_a_line_break_cannot_reach_the_subject_or_recipient_of_the_link(self):
        d = dict(draft(picked=["ABC-A-001"]), subject="Prog\r\nBcc: evil@x.example", to="a@b.test\r\nBcc: e@x.test")
        head = self.val(f"T.logic.mailLink({lit(d)})")["href"].split("&body=")[0]
        self.assertNotIn("%0D", head)
        self.assertNotIn("%0A", head)

    def test_i_sent_it_records_ids_day_and_kind_never_the_text(self):
        got = self.val("T.logic.sentEntry(['ABC-A-001', 'ABC-A-001', 'ABC-A-002', ''], 'chase', '2026-10-13')")
        self.assertEqual(got, {"kind": "email_sent", "ids": ["ABC-A-001", "ABC-A-002"], "date": "2026-10-13", "mode": "chase"})
        self.assertEqual(self.error("T.logic.sentEntry([], 'chase', '2026-10-13')"), "Tick at least one item before you press I sent it.")
        self.assertEqual(self.error("T.logic.sentEntry(['ABC-A-001'], 'chase', 'today')"),
                         "The date for this record is missing. Reload the page and try again.")
        # The same shape as the Python module's own entry, so the store can take either.
        py = draft_email.sent_entry(["ABC-A-001", "ABC-A-002"], "chase", "2026-10-13")
        self.assertEqual(py, {"kind": "email_sent", "ids": ["ABC-A-001", "ABC-A-002"], "date": "2026-10-13", "mode": "chase"})


class Component(InBrowser):
    def test_it_shows_the_kinds_the_subject_the_items_and_the_email(self):
        self.mount()
        labels = self.val("Array.from(document.querySelectorAll('.de-kinds label')).map((l) => l.textContent.trim())")
        self.assertEqual(labels, ["Update request", "Chase", "Decision"])
        self.assertEqual(self.val("document.querySelector('input[name=de-kind]:checked').value"), "update_request")
        self.assertIn("Example Programme", self.text(".de-meta"))
        self.assertEqual(self.val("document.querySelectorAll('.pick input').length"), 3)
        self.assertEqual(self.val("document.querySelectorAll('.pick input:checked').length"), 2)
        self.assertIn("2 of 3 items ticked", self.text(".de-count"))
        self.assertIn("Share the UAT plan", self.text(".de-preview"))
        self.assertIn("Good morning, Dana", self.text(".de-preview"))

    def test_choosing_a_kind_and_ticking_an_item_hand_the_new_state_to_the_caller(self):
        self.mount()
        self.click("input[value=chase]")
        self.click("input[value=ABC-A-005]")
        got = self.val("T.changed")
        self.assertEqual(got[0]["mode"], "chase")
        self.assertEqual(got[1]["picked"], ["ABC-A-001", "ABC-A-002", "ABC-A-005"])

    def test_a_decision_and_a_chase_ask_what_it_holds_up_and_an_update_request_does_not(self):
        self.mount()
        self.assertEqual(self.val("document.querySelectorAll('.de-opts input[type=text]').length"), 0)
        self.mount(state(mode="decision"), draft(mode="decision", picked=["ABC-A-001"]))
        self.assertIn("What is this holding up? (optional)", self.text(".de-opts"))
        self.mount(state(mode="chase"), draft(mode="chase", picked=["ABC-A-001"]))
        self.assertIn("What is this holding up? (optional)", self.text(".de-opts"))

    def test_over_the_mail_limit_the_button_gives_way_to_the_too_long_message(self):
        self.mount()
        self.assertEqual(self.val("document.querySelectorAll('.pk-foot a').length"), 1)
        self.assertEqual(self.text(".de-mail"), "")
        long = dict(draft(picked=["ABC-A-001"]), text="word " * 340)
        self.mount(state(picked=["ABC-A-001"]), long)
        self.assertEqual(self.val("document.querySelectorAll('.pk-foot a').length"), 0)
        self.assertEqual(self.text(".de-mail"), "This email is too long for a mail link. Use Copy for Outlook or Copy as text.")
        self.assertEqual(self.val("document.querySelectorAll('.pk-foot button:disabled').length"), 0, "the copies still work")

    def test_no_item_offered_gives_one_clear_empty_state(self):
        self.mount(state(picked=[]), draft(picked=[], items=[]), [])
        shown = self.js("document.querySelector('.de').innerText")
        self.assertEqual(shown.count("There are no open items to put in an email."), 1)
        self.assertNotIn("No items are ticked", shown)
        self.assertNotIn("Tick at least one", shown)
        self.assertEqual(self.val("document.querySelectorAll('.pick, .de-count').length"), 0)
        self.assertEqual(self.val("document.querySelectorAll('.pk-foot button:disabled').length"), 3)
        # Even a draft that says it is ready cannot be copied when the page offers nothing.
        self.mount(state(picked=[]), draft(picked=["ABC-A-001"]), [])
        self.assertEqual(self.text(".de-problem"), "There are no open items to put in an email.")

    def test_items_offered_but_none_ticked_says_it_once(self):
        self.mount(state(picked=[]))
        shown = self.js("document.querySelector('.de').innerText")
        self.assertEqual(shown.count("No items are ticked."), 1)
        self.assertEqual(shown.count("Tick at least one"), 1)
        self.assertEqual(self.text(".de-count"), "0 of 3 items ticked")

    def test_i_sent_it_says_what_was_recorded(self):
        self.mount(state(mode="chase"), draft(mode="chase", picked=["ABC-A-001", "ABC-A-002"]))
        self.js("Array.from(document.querySelectorAll('.pk-foot button')).find((b) => b.textContent === 'I sent it').click()")
        self.settle()
        self.assertEqual(self.text(".de-note"), "Marked as sent for 2 items on 13-10-2026. It is not saved to the history yet.")
        self.mount(state(mode="chase", picked=["ABC-A-001"]), draft(mode="chase", picked=["ABC-A-001"]))
        self.js("Array.from(document.querySelectorAll('.pk-foot button')).find((b) => b.textContent === 'I sent it').click()")
        self.settle()
        self.assertEqual(self.text(".de-note"), "Marked as sent for 1 item on 13-10-2026. It is not saved to the history yet.")

    def test_i_sent_it_with_no_day_given_records_the_computers_own_day_not_the_utc_day(self):
        # Near midnight the computer's day and the UTC day differ; the record must carry the computer's day.
        self.js("""Object.assign(Date.prototype, {
            getFullYear() { return 2026; }, getMonth() { return 9; }, getDate() { return 14; },
            toISOString() { return '2026-10-13T23:30:00.000Z'; } })""")
        st = state(mode="chase", picked=["ABC-A-001"])
        d = draft(mode="chase", picked=["ABC-A-001"])
        self.js(f"T.mountEditor({lit(OFFERED)}, {lit(st)}, {lit(d)})")
        self.settle()
        self.js("Array.from(document.querySelectorAll('.pk-foot button')).find((b) => b.textContent === 'I sent it').click()")
        self.settle()
        self.assertEqual(self.val("T.sent[0].date"), "2026-10-14")

    def test_i_sent_it_says_it_is_saved_when_the_history_has_it_and_marks_nothing_when_it_could_not(self):
        click = "Array.from(document.querySelectorAll('.pk-foot button')).find((b) => b.textContent === 'I sent it').click()"
        self.mount(state(mode="chase"), draft(mode="chase", picked=["ABC-A-001", "ABC-A-002"]))
        self.js("T.reply = {ok: true}")
        self.js(click)
        self.settle()
        self.assertEqual(self.text(".de-note"), "Recorded: 2 items marked as sent on 13-10-2026. It is in the history.")
        self.mount(state(mode="chase"), draft(mode="chase", picked=["ABC-A-001"]))
        self.js("T.reply = {ok: false, message: 'One of the ticked items is not in this project. Reload the page and tick again.'}")
        self.js(click)
        self.settle()
        self.assertEqual(self.text(".de-note"), "One of the ticked items is not in this project. Reload the page and tick again.")
        self.js("T.reply = {ok: false}")
        self.js(click)
        self.settle()
        self.assertEqual(self.text(".de-note"), "That could not be saved to the history, so nothing was marked as sent. Try again.")

    def test_i_sent_it_pressed_twice_while_one_is_in_flight_sends_one_and_is_disabled_until_the_reply(self):
        # #258: a second press does nothing until the reply
        click = "Array.from(document.querySelectorAll('.pk-foot button')).find((b) => b.textContent === 'I sent it').click()"
        disabled = "Array.from(document.querySelectorAll('.pk-foot button')).find((b) => b.textContent === 'I sent it').disabled"
        self.mount(state(mode="chase"), draft(mode="chase", picked=["ABC-A-001", "ABC-A-002"]))
        self.js("T.reply = new Promise((ok) => { T.finish = () => ok({ok: true}); })")
        self.js(click)
        self.js(click)
        self.settle()
        self.assertEqual(self.val("T.sent.length"), 1)
        self.assertTrue(self.val(disabled))
        self.js(click)
        self.settle()
        self.assertEqual(self.val("T.sent.length"), 1)
        self.js("T.finish()")
        self.settle()
        self.assertFalse(self.val(disabled))
        self.assertEqual(self.text(".de-note"), "Recorded: 2 items marked as sent on 13-10-2026. It is in the history.")

    def test_no_address_says_what_to_do_not_a_dash(self):
        self.mount(state(), draft(picked=["ABC-A-001"], email=""))
        self.assertIn("No address yet. Add one in your mail app.", self.text(".de-meta"))
        self.assertNotIn("\u2014", self.text(".de-meta"))

    def test_nothing_ticked_shows_the_next_step_and_blocks_every_copy(self):
        self.mount(state(picked=[]))
        self.assertEqual(self.text(".de-problem"), "No items are ticked. Tick at least one to draft the email.")
        self.assertEqual(self.val("Array.from(document.querySelectorAll('.pk-foot button')).filter((b) => b.disabled).map((b) => b.textContent)"),
                         ["Copy for Outlook", "Copy as text", "I sent it"])
        self.assertEqual(self.val("document.querySelectorAll('.pk-foot a').length"), 0, "no mail link while blocked")

    def test_a_missing_sender_name_blocks_copying_with_its_next_step(self):
        self.mount(state(), draft(picked=["ABC-A-001"], **{"from": ""}))
        self.assertEqual(self.text(".de-problem"), "Add your name in Settings › Profile so it signs the email.")

    def test_copy_for_outlook_puts_html_and_text_on_the_clipboard_and_says_copied(self):
        self.mount()
        self.click(".pk-foot .pri")
        clips = self.val("T.clips")
        self.assertEqual(len(clips), 1)
        self.assertEqual(sorted(clips[0]), ["text/html", "text/plain"])
        self.assertEqual(self.text(".de-note"), "Copied")

    def test_copy_as_text_adds_the_subject_line(self):
        self.mount()
        self.click(".pk-foot button:nth-child(2)")
        clip = self.val("T.clips[0]")
        self.assertEqual(list(clip), ["text/plain"])
        self.assertTrue(clip["text/plain"].startswith("Subject: Example Programme"))

    def test_a_refused_clipboard_says_what_to_press_and_selects_the_preview(self):
        self.js("T.refuse = true")
        self.mount()
        self.click(".pk-foot .pri")
        self.assertEqual(self.text(".de-note"), "The browser did not copy it. Press ⌘C to copy the selected text.")
        sel = self.js("window.getSelection().toString()")
        self.assertIn("Share the UAT plan", sel)

    def test_wording_changed_in_the_preview_is_what_gets_copied(self):
        self.mount()
        self.js("""(() => { const p = document.querySelector('.de-preview'); p.firstChild.firstChild.textContent = 'Hello Dana, my own words';
            p.dispatchEvent(new Event('input', {bubbles: true})); })()""")
        self.click(".pk-foot .pri")
        clip = self.val("T.clips[0]")
        self.assertIn("my own words", clip["text/html"])
        self.assertIn("my own words", clip["text/plain"])

    def test_a_redraw_with_the_same_email_keeps_the_edit(self):
        self.mount()
        self.js("""(() => { const p = document.querySelector('.de-preview'); p.firstChild.firstChild.textContent = 'Kept words';
            p.dispatchEvent(new Event('input', {bubbles: true})); })()""")
        self.click("input[value=ABC-A-001]")      # the caller has not rebuilt: the same draft is drawn again
        self.assertIn("Kept words", self.text(".de-preview"))

    def test_i_sent_it_hands_over_the_entry_for_the_ticked_items_only(self):
        self.mount(state(mode="chase"), draft(mode="chase", picked=["ABC-A-001", "ABC-A-002"]))
        self.js("Array.from(document.querySelectorAll('.pk-foot button')).find((b) => b.textContent === 'I sent it').click()")
        self.settle()
        self.assertEqual(self.val("T.sent"), [{"kind": "email_sent", "ids": ["ABC-A-001", "ABC-A-002"], "date": "2026-10-13", "mode": "chase"}])

    def test_an_internal_item_gets_a_note_under_the_preview_and_no_tag_in_the_email(self):
        d = draft(picked=["ABC-A-001", "ABC-A-005"])
        self.assertEqual(d["internal_ids"], ["ABC-A-005"])
        self.mount(state(picked=["ABC-A-001", "ABC-A-005"]), d)
        self.assertIn("Marked internal: ABC-A-005.", self.text(".de-internal"))
        self.assertNotIn("(internal)", self.text(".de-preview"))
        self.assertEqual(self.val("document.querySelectorAll('.de-preview .de-internal').length"), 0)

    def test_hostile_words_in_an_item_are_text_not_markup(self):
        items = [dict(LATE, text=HOSTILE)]
        d = draft(picked=["ABC-A-001"], items=items)
        self.mount(state(picked=["ABC-A-001"]), d, [{"id": "ABC-A-001", "text": HOSTILE}])
        self.assertIsNone(self.js("window.pwned"))
        self.assertEqual(self.val("document.querySelectorAll('.de img, .de script').length"), 0)
        self.assertIn("<script>", self.text(".pk-text"))

    def test_a_draft_that_cannot_be_built_says_what_to_do(self):
        self.js(f"T.mountEditor({lit(OFFERED)}, {lit(state())}, null, '2026-10-13')")
        self.assertEqual(self.text(".de"), "The email could not be drafted. Close this and open it again.Close")

    def test_escape_closes_it(self):
        self.mount()
        self.js("document.querySelector('.de-kinds input').focus()")
        self.cdp.call("Input.dispatchKeyEvent", {"type": "rawKeyDown", "key": "Escape", "code": "Escape", "windowsVirtualKeyCode": 27}, self.sid)
        self.settle()
        self.assertEqual(self.val("T.closed"), 1)

    def test_nothing_scrolls_sideways_at_900(self):
        self.load(900, 700)
        self.mount()
        self.assertTrue(self.js("document.documentElement.scrollWidth <= document.documentElement.clientWidth"))

    def test_every_word_it_shows_is_plain_and_none_starts_with_the_product_name(self):
        self.mount()
        shown = self.js("document.querySelector('.de').innerText")
        for banned in ("sweep", "proposal", "stage", "vault", "tracker", "refused"):
            self.assertNotIn(banned, shown.lower())
        for line in shown.splitlines():
            self.assertFalse(line.strip().lower().startswith("clark"), line)


if __name__ == "__main__":
    unittest.main()
