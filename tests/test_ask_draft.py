"""Row 1292 (S12): the Draft beside the ask panel, in a real browser against the real page and routes.

Run: flock <lock> ~/bin/clark-chrome-slot env CLARK_CHROME=/usr/local/bin/clark-chrome python3 dev/run_tests.py test_ask_draft
The server's `ask` is the stub of test_ask_panel, here with a draft in its answer. Covers: the answer shows "Draft ready" and the Draft opens
beside the panel with the words of the mock-up and an editable body; nothing is in the report until "Add to the report"; the menu offers each Text
section and a new one; a replace and an add are each one step that Undo takes back; Esc and the close button leave the report as it was; closing
the panel closes the draft. Fictional text only.
"""
import json
import time
import unittest

from clark import theme
from test_ask_panel import Panel, Stub
from test_server import chrome

DRAFT = {"html": "<p>The pilot is on track.</p><p>Two actions are overdue.</p>", "title": "This week's summary", "sec": ""}
SECTIONS = "document.querySelectorAll('.secs > .sec[data-id]').length"


class DraftStub(Stub):
    def ask(self, body):
        status, out = super().ask(body)
        if out.get("ok"):
            out["draft"] = dict(DRAFT)
        return status, out


class Draft(Panel):
    def setUp(self):
        super().setUp()
        self.stub = DraftStub()
        self.s.httpd.ask = self.stub

    def drafted(self, cdp):
        p = self.opened(cdp, before="document.querySelector('[data-mode=edit]').click()")
        self.ask(p, "Summarise this week")
        p.until("!!document.querySelector('#ask-draft')", "the draft opened beside the panel")
        return p

    def test_the_answer_offers_the_draft_and_it_opens_beside_the_panel_with_its_words(self):
        with chrome() as cdp:
            p = self.drafted(cdp)
            self.assertIn("Draft ready", p.js("document.querySelector('[data-ask-draftcard]').textContent"))
            self.assertEqual(p.js("document.querySelector('#ask-draft h2').textContent"), "Draft")
            self.assertEqual(p.js("document.querySelector('#ask-draft .ad-hint').textContent"), "Edit it freely. Nothing is in the report yet.")
            self.assertIn("The pilot is on track.", p.js("document.querySelector('#ask-draft-doc').innerText"))
            self.assertEqual(p.js("document.querySelector('#ask-draft-doc').getAttribute('contenteditable')"), "true")
            self.assertEqual(p.js("document.querySelector('#ask-draft-add').textContent"), "Add to the report")
            self.assertEqual(p.js("document.querySelector('#ask-draft-copy').textContent"), "Copy")
            left = p.js("document.querySelector('#ask-draft').getBoundingClientRect().right")
            panel = p.js("document.querySelector('#ask-panel').getBoundingClientRect().left")
            self.assertAlmostEqual(left, panel, delta=2, msg="the draft's right edge is the panel's left edge")

    def test_the_draft_stays_inside_the_window_at_1400_and_900(self):
        """Ticket 1346 (Classic): at 900 the Draft was at x=-80 (width 560); it is at x=24, width 456 now, and 560 wide beside the panel at 1400."""
        with chrome() as cdp:
            p = self.visit(cdp)
            p.js("document.querySelector('[data-mode=edit]').click()")
            p.js("(function(){var s=new CSSStyleSheet();s.replaceSync(" + json.dumps(theme.css("prototype-2.0")) + ");document.adoptedStyleSheets=[s]})()")      # the Classic theme layer (a constructed sheet: the page's policy lets no inline style element in)
            for width, want_w in ((1400, 560), (900, None)):
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                p.key("/", code="Slash", vk=191)
                p.until("!!document.querySelector('#ask-panel')", f"opened at {width}")
                p.until("document.querySelector('#ask-panel').getAnimations().length === 0", "risen")
                p.until("!document.querySelector('#ask-send').disabled", "ready")
                self.ask(p, "Summarise this week")
                p.until("!!document.querySelector('#ask-draft')", f"the draft opened at {width}")
                r = p.js("(function(){var r=document.querySelector('#ask-draft').getBoundingClientRect();return {l:r.left,w:r.width,r:r.right}})()")
                panel = p.js("document.querySelector('#ask-panel').getBoundingClientRect().left")
                self.assertGreaterEqual(r["l"], 0, f"{width}: the draft starts inside the window")
                edge = p.js("document.documentElement.clientWidth")      # the window less a classic scroll bar (Linux shows one; a Mac hides it)
                pw = edge - panel
                if want_w is None:       # 900: the sheet leaves a 24 px gap at the left
                    self.assertAlmostEqual(r["l"], 24, delta=2)
                    self.assertAlmostEqual(r["w"], edge - pw - 24, delta=2)
                else:                    # 1400: the full 560 beside the panel
                    self.assertAlmostEqual(r["w"], want_w, delta=2)
                self.assertAlmostEqual(r["r"], panel, delta=2)
                p.key("Escape", code="Escape", vk=27)
                p.until("document.querySelector('#ask-panel') === null", "closed")

    def test_closing_it_leaves_the_report_as_it_was(self):
        with chrome() as cdp:
            p = self.drafted(cdp)
            before = p.js(SECTIONS)
            p.js("document.querySelector('#ask-draft-close').click()")
            p.until("document.querySelector('#ask-draft') === null", "closed by its button")
            self.assertEqual(p.js(SECTIONS), before)
            p.js("document.querySelector('[data-ask-draftcard] button').click()")
            p.until("!!document.querySelector('#ask-draft')", "the card opens it again")
            p.js("document.querySelector('#ask-draft-doc').focus()")
            p.key("Escape", code="Escape", vk=27)
            p.until("document.querySelector('#ask-draft') === null", "closed by Esc")
            self.assertTrue(p.js("!!document.querySelector('#ask-panel')"), "Esc in the draft does not close the panel")
            self.assertEqual(p.js(SECTIONS), before)

    def test_a_real_mouse_press_inside_the_draft_keeps_the_panel_and_the_draft(self):      # the outside-press rule of the panel must not count the Draft as outside
        with chrome() as cdp:
            p = self.drafted(cdp)
            r = p.js("(() => { const b = document.querySelector('#ask-draft-doc').getBoundingClientRect(); return [b.left + b.width / 2, b.top + 20]; })()")
            for kind in ("mousePressed", "mouseReleased"):
                cdp.call("Input.dispatchMouseEvent", {"type": kind, "x": r[0], "y": r[1], "button": "left", "buttons": 1 if kind == "mousePressed" else 0, "clickCount": 1}, p.sid)
            self.assertTrue(p.js("!!document.querySelector('#ask-panel') && !!document.querySelector('#ask-draft')"), "the panel and the draft stay")

    def test_closing_the_panel_closes_the_draft(self):
        with chrome() as cdp:
            p = self.drafted(cdp)
            p.js("document.querySelector('#ask-close').click()")
            p.until("document.querySelector('#ask-draft') === null", "the draft went with the panel")

    def test_the_menu_offers_each_text_section_and_a_new_one(self):
        with chrome() as cdp:
            p = self.drafted(cdp)
            p.js("document.querySelector('#ask-draft-add').click()")
            p.until("!!document.querySelector('#ask-draft-menu')", "the menu opened")
            labels = p.js("[...document.querySelectorAll('#ask-draft-menu [role=menuitem]')].map(b => b.textContent)")
            self.assertTrue(any(x.startswith("Replace the text of ") and x.endswith(" now)") for x in labels), labels)
            self.assertEqual(labels[-1], "Add as a new Text section at the end")

    def test_add_as_a_new_section_is_one_step_and_undo_takes_it_back(self):
        with chrome() as cdp:
            p = self.drafted(cdp)
            before = p.js(SECTIONS)
            p.js("document.querySelector('#ask-draft-doc').innerHTML = '<p>Edited by hand.</p>'")
            p.js("document.querySelector('#ask-draft-add').click()")
            p.js("[...document.querySelectorAll('#ask-draft-menu [role=menuitem]')].pop().click()")
            p.until(f"{SECTIONS} === {before + 1}", "the new Text section is in the report")
            p.until("document.querySelector('.secs').innerText.includes('Edited by hand.')", "the new section shows the edited draft")
            p.until("document.querySelector('#ask-draft') === null", "the sheet is done")
            p.js("document.querySelector('[data-undo]').click()")
            p.until(f"{SECTIONS} === {before}", "Undo took the one step back")

    def test_replace_writes_the_edited_text_into_the_section(self):
        with chrome() as cdp:
            p = self.drafted(cdp)
            p.js("document.querySelector('#ask-draft-doc').innerHTML = '<p>Replaced words zebra.</p>'")
            p.js("document.querySelector('#ask-draft-add').click()")
            p.js("document.querySelector('#ask-draft-menu [data-kind=replace]').click()")
            p.until("document.querySelector('.secs').innerText.includes('Replaced words zebra.')", "the section has the edited draft")
            time.sleep(0.2)
            self.assertEqual(p.js("document.querySelector('#ask-draft') === null"), True)


    # The sweep's killers: the parts of the sheet the first tests did not look at.
    CLIP = ("window.__clip = null; window.ClipboardItem = function (o) { this.o = o; };"
            "Object.defineProperty(navigator, 'clipboard', {configurable: true, value: {"
            "write: async (items) => { window.__clip = {types: Object.keys(items[0].o), html: await items[0].o['text/html'].text(), plain: await items[0].o['text/plain'].text()}; },"
            "writeText: async (t) => { window.__clip = {text: t}; } }});")
    NOTE = "document.querySelector('#ask-draft-note').textContent"

    def test_copy_puts_formatted_and_plain_text_on_the_clipboard_and_says_so(self):
        with chrome() as cdp:
            p = self.drafted(cdp)
            p.js(self.CLIP)
            p.js("document.querySelector('#ask-draft-copy').click()")
            p.until("window.__clip !== null", "the clipboard was written")
            self.assertEqual(p.js("window.__clip.types"), ["text/html", "text/plain"])
            self.assertIn("<p>The pilot is on track.</p>", p.js("window.__clip.html"))
            self.assertIn("The pilot is on track.", p.js("window.__clip.plain"))
            self.assertNotIn("<p>", p.js("window.__clip.plain"))
            p.until(self.NOTE + " === 'Draft copied.'", "the note says so")

    def test_copy_without_formatted_clipboard_items_puts_the_plain_text(self):
        with chrome() as cdp:
            p = self.drafted(cdp)
            p.js(self.CLIP + "window.ClipboardItem = undefined;")
            p.js("document.querySelector('#ask-draft-copy').click()")
            p.until("window.__clip !== null", "the plain text was written")
            self.assertIn("The pilot is on track.", p.js("window.__clip.text"))
            self.assertNotIn("<p>", p.js("window.__clip.text"))
            p.until(self.NOTE + " === 'Draft copied.'", "the note says so")

    def test_a_copy_that_fails_says_so(self):
        with chrome() as cdp:
            p = self.drafted(cdp)
            p.js("Object.defineProperty(navigator, 'clipboard', {configurable: true, value: {write: async () => { throw new Error('no'); }, writeText: async () => { throw new Error('no'); }}});")
            p.js("document.querySelector('#ask-draft-copy').click()")
            p.until(self.NOTE + " === 'The draft could not be copied. Select the text and copy it yourself.'", "the note says it failed")

    def test_the_add_button_opens_and_closes_the_menu_and_says_which(self):
        with chrome() as cdp:
            p = self.drafted(cdp)
            self.assertEqual(p.js("document.querySelector('#ask-draft-add').getAttribute('aria-expanded')"), "false")
            p.js("document.querySelector('#ask-draft-add').click()")
            p.until("!!document.querySelector('#ask-draft-menu')", "opened")
            self.assertEqual(p.js("document.querySelector('#ask-draft-add').getAttribute('aria-expanded')"), "true")
            p.js("document.querySelector('#ask-draft-add').click()")
            p.until("document.querySelector('#ask-draft-menu') === null", "a second press closes it")
            self.assertEqual(p.js("document.querySelector('#ask-draft-add').getAttribute('aria-expanded')"), "false")

    def test_the_menu_items_say_what_they_are(self):
        with chrome() as cdp:
            p = self.drafted(cdp)
            p.js("document.querySelector('#ask-draft-add').click()")
            p.until("!!document.querySelector('#ask-draft-menu')", "opened")
            self.assertTrue(p.js("document.querySelector('#ask-draft-menu [data-kind=replace]').getAttribute('data-id')"))
            last = "[...document.querySelectorAll('#ask-draft-menu [role=menuitem]')].pop()"
            self.assertEqual(p.js(last + ".getAttribute('data-kind')"), "add")
            self.assertIsNone(p.js(last + ".getAttribute('data-id')"))
            self.assertIsNone(p.js(last + ".getAttribute('data-after')"))

    def test_esc_closes_the_menu_first_and_only_in_the_draft(self):
        with chrome() as cdp:
            p = self.drafted(cdp)
            p.js("document.addEventListener('keydown', e => { if (e.key === 'Escape') window.__esc = (window.__esc || 0) + 1; })")
            p.js("document.querySelector('#ask-draft-add').click()")
            p.until("!!document.querySelector('#ask-draft-menu')", "opened")
            p.js("document.querySelector('#ask-draft-menu [role=menuitem]').focus()")
            p.key("Escape", code="Escape", vk=27)
            p.until("document.querySelector('#ask-draft-menu') === null", "Esc closed the menu")
            self.assertTrue(p.js("!!document.querySelector('#ask-draft')"), "the draft stays")
            self.assertEqual(p.js("document.activeElement.id"), "ask-draft-add", "focus goes back to the button")
            time.sleep(0.8)
            self.assertTrue(p.js("!!document.querySelector('#ask-panel')"), "the panel stays (a closing panel is gone after its animation)")
            p.js("document.querySelector('#ask-draft-doc').focus()")
            p.key("a", code="KeyA", vk=65)
            self.assertTrue(p.js("!!document.querySelector('#ask-draft')"), "another key does not close it")
            p.key("Escape", code="Escape", vk=27)
            p.until("document.querySelector('#ask-draft') === null", "Esc closed the draft")
            self.assertEqual(p.js("document.activeElement.id"), "ask-box", "focus goes back to the question box")
            time.sleep(0.8)
            self.assertTrue(p.js("!!document.querySelector('#ask-panel')"), "the panel stays")
            self.assertFalse(p.js("window.__esc || 0"), "the Esc that closed the menu and the draft went no further")

    def test_a_new_draft_starts_with_the_menu_shut_and_the_note_empty(self):
        with chrome() as cdp:
            p = self.drafted(cdp)
            p.js(self.CLIP)
            p.js("document.querySelector('#ask-draft-copy').click()")
            p.until(self.NOTE + " === 'Draft copied.'", "a note")
            p.js("document.querySelector('#ask-draft-add').click()")
            p.until("!!document.querySelector('#ask-draft-menu')", "opened")
            self.ask(p, "And next week?")
            p.until("document.querySelectorAll('[data-ask-draftcard]').length === 2", "the second answer is in")
            p.until("document.querySelector('#ask-draft-menu') === null", "the menu is shut")
            self.assertEqual(p.js(self.NOTE), "")

    def test_a_refused_change_shuts_the_menu_and_keeps_the_draft(self):
        with chrome() as cdp:
            p = self.drafted(cdp)
            before = p.js(SECTIONS)
            p.js("const real = window.fetch; window.fetch = function (u) { if (/section-body|api\\/change/.test(String(u))) return Promise.reject(new TypeError('network down')); return real.apply(this, arguments); };")
            p.js("document.querySelector('#ask-draft-add').click()")
            p.until("!!document.querySelector('#ask-draft-menu')", "opened")
            p.js("document.querySelector('#ask-draft-menu [data-kind=replace]').click()")
            p.until("document.querySelector('#ask-draft-menu') === null", "the menu is shut")
            time.sleep(0.3)
            self.assertTrue(p.js("!!document.querySelector('#ask-draft')"), "the draft stays")
            self.assertEqual(p.js(SECTIONS), before)

    def test_text_too_long_to_save_says_the_draft_is_empty_and_stays(self):
        with chrome() as cdp:
            p = self.drafted(cdp)
            p.js("document.querySelector('#ask-draft-doc').innerHTML = '<p>' + 'a'.repeat(200001) + '</p>'")
            p.js("document.querySelector('#ask-draft-add').click()")
            p.until("!!document.querySelector('#ask-draft-menu')", "opened")
            p.js("[...document.querySelectorAll('#ask-draft-menu [role=menuitem]')].pop().click()")
            p.until(self.NOTE + " === 'The draft is empty. Write something, or close it.'", "the note")
            self.assertTrue(p.js("!!document.querySelector('#ask-draft')"))

    def test_the_card_names_the_draft(self):
        with chrome() as cdp:
            p = self.drafted(cdp)
            self.assertIn("This week's summary. Nothing is in the report yet.", p.js("document.querySelector('[data-ask-draftcard]').textContent"))

    def test_a_new_chat_closes_the_draft(self):
        with chrome() as cdp:
            p = self.drafted(cdp)
            p.until("!document.querySelector('#ask-new').disabled", "the chat is idle")
            p.js("document.querySelector('#ask-new').click()")
            p.until("document.querySelector('#ask-draft') === null", "the draft went with the chat")

    def test_closing_the_panel_and_opening_it_again_shows_no_draft(self):
        with chrome() as cdp:
            p = self.drafted(cdp)
            p.js("document.querySelector('#ask-close').click()")
            p.until("document.querySelector('#ask-panel') === null", "closed")
            p.key("/", code="Slash", vk=191)
            p.until("!!document.querySelector('#ask-panel')", "opened again")
            time.sleep(0.3)
            self.assertTrue(p.js("document.querySelector('#ask-draft') === null"))

    def test_leaving_the_page_keeps_the_panel_and_the_draft(self):
        """Row 1292 slice 1: a change of page no longer closes the panel or drops the chat, so the Draft beside it stays too."""
        with chrome() as cdp:
            p = self.drafted(cdp)
            p.js("location.hash = '#settings&p=ABC'")
            time.sleep(0.5)
            self.assertTrue(p.js("!!document.querySelector('#ask-panel')"), "the panel stays open")
            self.assertTrue(p.js("!!document.querySelector('#ask-draft')"), "the Draft stays beside it")


def _icons_test(self):
    """Row 1292: every line of the Add to the report menu draws an icon (the menu icon rule of row 1138)."""
    with chrome() as cdp:
        p = self.drafted(cdp)
        p.js("document.querySelector('#ask-draft-add').click()")
        p.until("document.querySelectorAll('#ask-draft-menu [role=menuitem]').length >= 2", "the menu drew its lines")
        got = p.js("[...document.querySelectorAll('#ask-draft-menu [role=menuitem]')].map(b => { const s = b.querySelector('svg'); return [b.textContent, !!s, s ? s.getBoundingClientRect().width : 0]; })")
        for words, has, w in got:
            self.assertTrue(has and w >= 15, f"the line {words!r} draws no icon")


Draft.test_the_add_menu_gives_every_line_an_icon = _icons_test

for _n in dir(Panel):      # the panel's own tests are not run again here (they use the plain stub)
    if _n.startswith("test_") and _n not in Draft.__dict__:
        setattr(Draft, _n, None)


if __name__ == "__main__":
    unittest.main()
