"""Shared by the typed notes' tests (#96 G5: tests/test_tpl_callout.py, test_tpl_quote.py, test_tpl_contacts.py,
test_tpl_table.py): the same checks for each template, given its own good body, hostile bodies and page words. Fictional data only.

DataChecks: the checker (limits, hostile input, unknown fields dropped), one change = one step = one Undo, the published file
(a filled section in, an empty one, a hidden one and a bad stored one out; nothing raw from a body). PageChecks: the page clark
serves (View draws the words as text and leaves an empty one out; Edit saves a field as one step with one Undo) and the file's
own page (the same words, from its data block alone).
"""
import json
import sqlite3
import unittest

from clark import publish, section_bodies as sb, store as store_module
from _publish_fixture import spellings
from test_changes import Api, KIND
from test_report_editor import Base as PageBase
from test_server import chrome

MARK = "ZQ-NOTE-MARK"
HOSTILE = "<script>alert('" + MARK + "')</script>"


def field_js(ref, label):
    """A field of section `ref` by its aria-label, as a JS expression."""
    return "document.querySelector(" + json.dumps(f"[data-id={json.dumps(ref)}] [aria-label={json.dumps(label)}]") + ")"


def fill(p, selector_js, text):
    """Type `text` in place of a field's words, as a person does (real key events, then leave the field in a call of its own: a
    focus and a blur in one script are not seen by a page that has no window focus)."""
    p.js(f"(function(){{ var el = {selector_js}; el.focus(); el.select(); }})()")
    p.until(f"document.activeElement === {selector_js}", "the field has focus")
    if text:
        p.type(text)
    else:
        p.key("Backspace", code="Backspace", vk=8)
    p.js("document.activeElement.blur()")


def slow_saves(test, seconds=1.0):
    """Make every save take `seconds` to land (the real change, late), so a person's next keystrokes arrive before it does."""
    import time
    test.failure = lambda req: (time.sleep(seconds), test.real_change(req))[1]


class DataChecks(Api):
    TYPE = ""                # the store type
    GOOD = {}                # a filled body (the checker keeps it unchanged apart from field order and defaults)
    WORDS = ""               # words in GOOD that the file must carry
    BAD = ()                 # bodies (objects) the checker refuses
    HOSTILE_BODY = {}        # a body with HOSTILE as the text of every text field
    LIMIT_BODY = {}          # a body just over a field limit

    def section(self, **more):
        return self.ok("new", values={"type": self.TYPE, "title": f"Fictional {self.TYPE}"}, **more)["ref"]

    def write(self, ref, value):
        text = value if isinstance(value, str) else json.dumps(value)
        return self.change(self.req("update", id=ref, changes={"body": text}))

    def stored(self, ref):
        return self.s.read(KIND, ref=ref)["body"]

    def file_sections(self):
        return {s["id"]: s for s in publish.build(self.s, "ABC", now="2030-01-15")["published"]["sections"]}

    def raw(self, ref, text):
        con = sqlite3.connect(str(self.path))
        con.execute("UPDATE report_sections SET body = ? WHERE id = ?", (text, ref))
        con.commit()
        con.close()

    # ── the checker ──────────────────────────────────────────────────────────
    def test_the_template_is_ready_and_starts_empty(self):
        self.assertIs(sb.TEMPLATES[self.TYPE].READY, True)
        ref = self.section()
        self.assertEqual(self.stored(ref), "")

    def test_a_good_body_is_stored_canonical_and_saving_it_again_changes_nothing(self):
        ref = self.section()
        status, got = self.write(ref, self.GOOD)
        self.assertEqual(status, 200, got)
        text = self.stored(ref)
        self.assertEqual(json.loads(text)["v"], 1)
        self.assertEqual(text, sb.canonical(json.loads(text)))
        self.assertIn(self.WORDS, text)
        before = self.snapshot()
        status, got = self.write(ref, json.loads(text))
        self.assertEqual(status, 200, got)
        self.assertEqual(self.snapshot(), before, "the same content again is no step")

    def test_an_unknown_field_is_dropped_and_a_bare_body_is_accepted(self):
        ref = self.section()
        status, got = self.write(ref, {**self.GOOD, "words": ["ZQ-DROPPED"], "href": "javascript:alert(1)"})
        self.assertEqual(status, 200, got)
        self.assertNotIn("javascript", self.stored(ref))
        self.assertNotIn("ZQ-DROPPED", self.stored(ref))
        status, got = self.write(ref, {"v": 1})
        self.assertEqual(status, 200, got)

    def test_a_body_that_is_not_the_template_is_refused_in_plain_words_that_never_quote_it(self):
        ref = self.section()
        for bad in (*self.BAD, [], {"v": 2}, {}, "[1]", '{"v": 1, "x": '):
            with self.subTest(body=str(bad)[:40]):
                before = self.snapshot()
                status, got = self.write(ref, bad)
                self.assertEqual((status, got["ok"]), (400, False))
                self.assertNotIn(MARK, got["message"])
                self.assertTrue(got["message"].endswith((".", "?")), got["message"])
                self.assertEqual(self.snapshot(), before, "nothing was written")

    def test_a_field_over_its_limit_is_refused_and_a_hostile_text_is_only_text(self):
        ref = self.section()
        before = self.snapshot()
        status, got = self.write(ref, self.LIMIT_BODY)
        self.assertEqual((status, got["ok"]), (400, False), got)
        self.assertEqual(self.snapshot(), before)
        status, got = self.write(ref, self.HOSTILE_BODY)
        self.assertEqual(status, 200, got)
        self.assertEqual(json.loads(self.stored(ref)), json.loads(sb.canonical(json.loads(self.stored(ref)))))

    def test_a_line_break_or_invisible_character_in_a_field_is_refused(self):
        ref = self.section()
        for text in ("one\ntwo", "a‮b", "a\u0000b"):
            bad = json.dumps(self.GOOD).replace(self.WORDS, json.dumps(text)[1:-1])     # the text as JSON, so it parses and the checker sees the character
            status, got = self.write(ref, bad)
            self.assertEqual((status, got["ok"]), (400, False), repr(text))

    # ── one change, one step, one Undo ───────────────────────────────────────
    def test_a_save_is_one_step_with_one_undo(self):
        ref = self.section()
        status, got = self.write(ref, self.GOOD)
        self.assertEqual(status, 200)
        self.assertTrue(got.get("apply_id"))
        self.assertNotIn("body", json.dumps(got.get("sections")), "a reply never carries a body")
        status, back = self.undone(got["apply_id"])
        self.assertEqual(status, 200, back)
        self.assertEqual(self.stored(ref), "", "Undo put the empty content back")

    # ── the published file ───────────────────────────────────────────────────
    def test_a_filled_section_is_in_the_file_with_its_content_and_nothing_raw(self):
        ref = self.section()
        self.write(ref, self.GOOD)
        got = self.file_sections()[ref]
        self.assertEqual({"id", "type", "title", "beside", "content"}, set(got))
        self.assertIn(self.WORDS, json.dumps(got["content"]))
        self.write(ref, self.HOSTILE_BODY)
        built = publish.build(self.s, "ABC", now="2030-01-15")["body"].decode("utf-8")
        self.assertNotIn("<script>alert('" + MARK, built)
        self.assertNotIn("</script><script>", built)

    def test_an_empty_hidden_or_bad_section_is_not_in_the_file_and_its_words_never_are(self):
        ref = self.section()
        self.assertNotIn(ref, self.file_sections(), "empty (no content)")
        self.write(ref, {"v": 1})
        self.assertNotIn(ref, self.file_sections(), "a body with nothing to show")
        self.write(ref, json.loads(json.dumps(self.GOOD).replace(self.WORDS, MARK)))
        self.assertIn(ref, self.file_sections())
        status, got = self.change(self.req("update", id=ref, changes={"hidden": 1}))
        self.assertEqual(status, 200, got)
        self.assertNotIn(ref, self.file_sections(), "hidden")
        text = publish.build(self.s, "ABC", now="2030-01-15")["body"].decode("utf-8")
        for spelling in spellings(MARK):
            self.assertNotIn(spelling, text)
        self.change(self.req("update", id=ref, changes={"hidden": 0}))
        self.raw(ref, "not json" + MARK)
        self.assertNotIn(ref, self.file_sections(), "a bad stored body")
        self.raw(ref, json.dumps({"v": 1, "x": MARK}))
        self.assertNotIn(ref, self.file_sections(), "unknown fields only")


class PageChecks(PageBase):
    TYPE = ""
    GOOD = {}                  # a filled body
    HOSTILE_BODY = {}          # HOSTILE as every text
    SHOWS = ()                 # words View must show for GOOD
    FIELD = ""                 # aria-label of a field in Edit
    TYPED = ""                 # words typed into it
    CHANGED = lambda self, body: False           # True when the stored body holds TYPED

    def make(self, body):
        from _demo import USER
        with self.store.step("dashboard", USER) as st:
            ref = st.create("report_sections", {"project": "ABC", "type": self.TYPE, "title": f"Fictional {self.TYPE}", "sort_order": 999})
        if body is not None:
            status, got = self.real_change({"project": "ABC", "kind": KIND, "op": "update", "id": ref, "changes": {"body": json.dumps(body)}})
            assert status == 200, got
        return ref

    def body_of(self, ref):
        return self.store.read(KIND, ref=ref)["body"]

    def test_view_draws_the_words_as_text_and_leaves_an_empty_section_out(self):
        full, empty = self.make(self.GOOD), self.make(None)
        with chrome() as cdp:
            p = self.visit(cdp)
            sec = f"document.querySelector('[data-id={json.dumps(full)}]')"
            self.assertTrue(p.js(f"!!{sec}"))
            shown = p.js(f"{sec}.textContent")
            for w in self.SHOWS:
                self.assertIn(w, shown)
            self.assertFalse(p.js(f"!!document.querySelector('[data-id={json.dumps(empty)}]')"), "View: an empty template is not shown")
            self.assertFalse(p.js(f"!!{sec}.querySelector('input, textarea, select, button, [contenteditable]')"), "View has no field")

    def test_view_never_draws_a_body_as_markup(self):
        ref = self.make(self.HOSTILE_BODY)
        with chrome() as cdp:
            p = self.visit(cdp)
            sec = f"document.querySelector('[data-id={json.dumps(ref)}]')"
            self.assertTrue(p.js(f"{sec}.textContent.indexOf('<script>') >= 0"), "the markup is shown as letters")
            self.assertFalse(p.js(f"!!{sec}.querySelector('script, img, iframe')"))

    def test_edit_saves_a_field_as_one_step_and_undo_puts_it_back(self):
        ref = self.make(self.GOOD)
        before = self.body_of(ref)
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            sel = f"document.querySelector('[data-id={json.dumps(ref)}] [aria-label={json.dumps(self.FIELD)}]')"
            p.until(f"!!{sel}", "the field is there")
            fill(p, sel, self.TYPED)
            p.saved()
            self.assertTrue(self.CHANGED(self.body_of(ref)), self.body_of(ref))
            sent = [r for which, r in self.sent if which == "change" and r.get("op") == "update"]
            self.assertEqual(len(sent), 1, "one save, one request")
            self.assertEqual(sent[0]["place"], "report")
            p.js("document.querySelector('[data-undo]').click()")
            p.until("document.querySelector('.toast-text').textContent === 'Undone.'", "Undo")
            self.assertEqual(self.body_of(ref), before)

    def test_edit_leaving_a_field_alone_saves_nothing(self):
        ref = self.make(self.GOOD)
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            sel = f"document.querySelector('[data-id={json.dumps(ref)}] [aria-label={json.dumps(self.FIELD)}]')"
            p.until(f"!!{sel}", "the field is there")
            p.js(f"(function(){{ var e = {sel}; e.focus(); e.blur(); }})()")
            p.js("new Promise(r => setTimeout(r, 300))")
            self.assertEqual([r for which, r in self.sent if which == "change" and r.get("op") == "update"], [])

    def test_edit_shows_an_empty_one_with_words_and_a_next_step(self):
        ref = self.make(None)
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            p.until(f"!!document.querySelector('[data-id={json.dumps(ref)}] .tpl-edit')", "Edit shows the fields")
            quiet = p.js(f"[...document.querySelectorAll('[data-id={json.dumps(ref)}] .tpl-edit .quiet')].map(e => e.textContent).join(' ')")
            self.assertIn("Empty for now", quiet)
            self.assertIn("stays out of the published page", quiet)
