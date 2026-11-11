"""#66: there is one rich editor, clarkEditor(), and nothing else edits rich text on the page.

Run: python3 dev/run_tests.py test_one_editor_gate
Adapted from creaite's gate, not copied: creaite's file is a Markdown round trip and counts nothing. Here:
  - a source check: no other `new Editor`, `createEditor` or `contenteditable` in the page's source outside core/editor.js (the section
    title's plain-text field is the one named exception, below);
  - a page check: Edit opens every rich field (the seam in edit/richSave.js lists the text section's body, #220) and finds only
    clarkEditor() instances (a .ProseMirror with a handle); View has no rich field at all;
  - the editor adds no <style> element when it mounts, and the Edit page loads.
"""
import re
import shutil
import sys
import tempfile
import unittest
from _editor_checks import for_project
from unittest import mock

from _demo import USER, DemoStore
from _new_page import reload_to_new_page_cdp
from _real_server import real_server
from _paths import SRC, TOOLS

sys.path.insert(0, str(TOOLS))
import build_page  # noqa: E402

from clark import changes, order, page, sanitise, server as sv  # noqa: E402
from test_page import navigate  # noqa: E402
from test_server import chrome, wait  # noqa: E402

PAGE_SRC = SRC / "clark" / "page" / "src"
EMPTY_BRANDING = tempfile.mkdtemp(prefix="clark-no-brand-")
# Not a rich field: the section title is plain text on a contenteditable="plaintext-only" span (Title.jsx, #65), with an input as the
# fallback. It stays: the title is a one-line plain-text field whose tests belong to #65, and moving it onto the plain profile is a
# low-priority follow-up. Moving it onto clarkEditor's plain profile is a separate change (it would rewrite #65's tests of the title).
# The other: the Draft email preview is a plain editable box on purpose (its styled HTML and table are what Outlook pastes, as in creaite). It holds an email, not a report field. keys.js and help/helpStore.js only READ isContentEditable to leave typing alone.
# The tracker's status words (row 930) are the same kind of field as the title: one limited plain-text line on a contenteditable="plaintext-only" span (edit/TrackerWords.jsx), with no styled content and no AI place (test_ai_places leaves it out).
NAMED = {"edit/Title.jsx", "components/DraftEmail.jsx", "edit/TrackerWords.jsx"}
PATTERN = re.compile(r"new\s+Editor\b|createEditor\b|contenteditable(?!\w*\)?\s*\|\|)", re.I)


def tearDownModule():
    shutil.rmtree(EMPTY_BRANDING, ignore_errors=True)


class Source(unittest.TestCase):
    def test_no_other_editor_in_the_page_source(self):
        found = []
        for f in sorted(PAGE_SRC.rglob("*")):
            if f.suffix not in (".js", ".jsx") or f.name == "sanitiseTables.js":
                continue
            rel = f.relative_to(PAGE_SRC).as_posix()
            if rel == "core/editor.js" or rel in NAMED:
                continue
            for n, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
                if PATTERN.search(line.replace("isContentEditable", "")):
                    found.append(f"{rel}:{n}: {line.strip()[:80]}")
        self.assertEqual(found, [])

    def test_the_seam_lists_the_text_section_body_and_nothing_else_yet(self):
        text = (PAGE_SRC / "edit" / "richSave.js").read_text(encoding="utf-8")
        block = text.split("export const RICH_WRITES = {", 1)[1].split("};", 1)[0]
        self.assertEqual(re.findall(r"^\s*(\w+):", block, re.M), ["body"])

    def test_core_editor_is_the_only_importer_of_the_vendored_editor(self):
        importers = [f.relative_to(PAGE_SRC).as_posix() for f in PAGE_SRC.rglob("*.js*") if re.search(r"from\s+[\"']tiptap[\"']", f.read_text(encoding="utf-8"))]
        self.assertEqual(importers, ["core/editor.js"])

    def test_the_published_page_has_no_editor(self):
        page.ensure_built()          # #495: the pages are generated, so a fresh checkout builds them here
        view = (SRC / "clark" / "page" / "page-view.html").read_text(encoding="utf-8")
        scripts = "".join(re.findall(r"<script>(.*?)</script>", view, re.S))          # the stylesheet names the editor's classes; the script must not hold it
        self.assertGreater(len(scripts), 1000)
        for word in ("createEditor", "cxed", "prosemirror", "SanitiseError"):
            self.assertNotIn(word, scripts, word)

    def test_the_template_fields_have_no_plain_box_for_their_words(self):
        """Row 1005: the words on a Link preview card, under a One document file and in a Callout are the one editor (RichField)."""
        for rel in ("edit/templates/LinkCard.jsx", "edit/templates/OneDoc.jsx", "edit/templates/Callout.jsx"):
            text = (PAGE_SRC / rel).read_text(encoding="utf-8")
            self.assertNotIn("<textarea", text, rel)
            self.assertIn("<RichField", text, rel)
        note = (PAGE_SRC / "edit" / "templates" / "noteEdit.jsx").read_text(encoding="utf-8")
        self.assertNotIn("<textarea", note, "the typed notes' shared field is one line now; the words are RichField")

    def test_the_built_pages_are_current(self):
        self.assertEqual(build_page.main(["--check"]), 0)


# Item 1005: plain multiline fields that moved onto the one editor, and the component each one draws (never a textarea or a contenteditable
# of its own). The pioneer fields (item and milestone Latest update) and the template fields are listed by their own PRs.
MOVED = {"edit/Movement.jsx": ("RichField", "the Movement Internal note"), "edit/GlanceEdit.jsx": ("RichField", "the At a glance Reason"),
         "edit/MilestonePeek.jsx": ("RichField", "the milestone Client wording and Description"), "edit/templates/pictureEdit.jsx": ("RichField", "the picture captions")}


class MovedFields(unittest.TestCase):
    def test_each_moved_field_draws_the_one_editor_and_no_textarea(self):
        for rel, (component, what) in MOVED.items():
            text = (PAGE_SRC / rel).read_text(encoding="utf-8")
            self.assertRegex(text, r"import \{ %s \} from" % component, what)
            self.assertNotIn("<textarea", text, what)
            self.assertNotIn("useGrow", text, what)
        self.assertNotIn("TEXTAREA", (PAGE_SRC / "edit" / "Movement.jsx").read_text(encoding="utf-8"))

    def test_a_moved_field_reads_what_is_stored_through_the_page_twin_never_raw(self):
        for rel in MOVED:
            self.assertIn("richOrPlain(", (PAGE_SRC / rel).read_text(encoding="utf-8"), rel)

    def test_plain_text_fields_on_the_editor_save_plain_text_never_markup(self):
        """Item 1005: Client wording and captions are stored, published and exported as plain text, so the editor's HTML is flattened before it is sent."""
        for rel in ("edit/MilestonePeek.jsx", "edit/templates/pictureEdit.jsx"):
            self.assertIn("plainFromEditor(", (PAGE_SRC / rel).read_text(encoding="utf-8"), rel)
        for rel in ("edit/templates/ImageCap.jsx", "edit/templates/TextImage.jsx"):
            text = (PAGE_SRC / rel).read_text(encoding="utf-8")
            self.assertIn('<CaptionField section={section} field="caption"', text, rel)
            self.assertNotIn('<LineField section={section} field="caption"', text, rel)
        self.assertIn("CaptionField", (PAGE_SRC / "edit" / "templates" / "Gallery.jsx").read_text(encoding="utf-8"))

    def test_the_move_form_and_the_raid_own_words_draw_the_one_editor_and_store_plain_text(self):
        """Row 1005: Who agreed it, Reason and Source (Movement) and a RAID card's Own words are RichField. What is sent and stored stays
        plain text on one line (the store refuses a line break there), so an older row and a new one read the same."""
        move = (PAGE_SRC / "edit" / "Movement.jsx").read_text(encoding="utf-8")
        self.assertNotRegex(move, r"<input[^>]*id=\"mv-(who|reason|source)\"")
        for k in ("who", "reason", "source"):
            self.assertIn('<FormField k="%s"' % k, move)
        self.assertGreaterEqual(move.count("<RichField"), 2, "the note and the form's fields")
        self.assertIn("plainLine(", move)
        raid = (PAGE_SRC / "edit" / "templates" / "raidEdit.jsx").read_text(encoding="utf-8")
        self.assertNotIn("<input", raid)
        self.assertNotIn("<textarea", raid)
        self.assertIn("<RichField", raid)
        self.assertIn("plainLine(", raid)

    def test_the_published_page_draws_the_reason_with_no_cleaner_of_its_own(self):
        glance = (PAGE_SRC / "components" / "Glance.jsx").read_text(encoding="utf-8")
        self.assertIn("HTML_START", glance)
        self.assertNotIn("cleanHtml", glance)
        self.assertNotIn("richOrPlain", glance, "the cleaner is the page's own `clean` prop; the published page has none")


ORIGINAL = "<p>Original words the programme manager wrote.</p>"


class PageGate(unittest.TestCase):
    """The real page and the real write kind: the seam lists the text section's body (#220)."""

    @classmethod
    def setUpClass(cls):
        cls.page_on = build_page.build()

    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.store = self.demo.store
        self.real = changes.make_change(self.store.path, [], USER)
        self.sent = []
        self.fail_reads = False
        quiet = mock.patch.object(sv.LOG, "disabled", True)
        quiet.start()
        self.addCleanup(quiet.stop)

    def data(self, code):
        if self.fail_reads:
            raise OSError("the data could not be read")
        return self.store.data_for(code)

    def serve(self, html):
        s = real_server(self.store.path, self.data, page_html=lambda: html, change=self.change)
        self.addCleanup(s.close)
        return s

    def change(self, req):
        self.sent.append(req)
        return self.real(req)

    def seed_body(self):
        """The demo project's first text section gets a body; returns nothing, sets self.sec."""
        rows = [r for r in self.store.read("report_sections", "ABC") if r["type"] == "text"]
        self.assertTrue(rows, "the demo project has a text section")
        self.sec = rows[0]["id"]
        with self.store.step("dashboard", USER) as st:
            st.update("report_sections", self.sec, {"body": ORIGINAL})

    def edit(self, cdp, s):
        sid = navigate(cdp, s.port, for_project("#dashboard&p=ABC"))
        js = lambda e: cdp.js(e, sid)  # noqa: E731
        self.assertTrue(wait(lambda: js("document.querySelectorAll('.sec').length > 0"), 15))
        js("document.querySelector('[data-mode=edit]').click()")
        self.assertTrue(wait(lambda: js("document.querySelector('#report').dataset.mode === 'edit'"), 10))
        return js, sid

    def test_only_the_three_text_sections_have_a_rich_field_and_only_in_edit(self):
        s = self.serve(self.page_on)
        with chrome() as cdp:
            sid = navigate(cdp, s.port, for_project("#dashboard&p=ABC"))
            js = lambda e: cdp.js(e, sid)  # noqa: E731
            self.assertTrue(wait(lambda: js("document.querySelectorAll('.sec').length > 0"), 15))
            self.assertEqual(js("document.querySelectorAll('.ProseMirror, [data-rich]').length"), 0, "View has no rich field")
            js("document.querySelector('[data-mode=edit]').click()")
            self.assertTrue(wait(lambda: js("document.querySelector('#report').dataset.mode === 'edit'"), 10))
            self.assertEqual(js("[...document.querySelectorAll('[data-rich]')].map(function(f){ return f.closest('.sec').dataset.id; })"),
                             ["ABC-S-005", "ABC-S-006", "ABC-S-007"])
            self.assertEqual(js("document.querySelectorAll('.sec[data-type=text] .quiet:not([data-rich] .quiet)').length"), 0)
            js("document.querySelector('[data-mode=view]').click()")
            self.assertTrue(wait(lambda: js("document.querySelector('#report').dataset.mode !== 'edit'"), 10))
            self.assertEqual(js("document.querySelectorAll('.ProseMirror, [data-rich]').length"), 0, "back in View there is no rich field again")

    def test_every_rich_field_opens_a_clark_editor_and_nothing_else(self):
        s = self.serve(self.page_on)
        with chrome() as cdp:
            # The test clicks every field in one go and expects every editor open at once. With page focus, each click blurs the editor
            # before it and closes it, so only one stays open: this test needs the unfocused page it was written for.
            cdp.FOCUS_EMULATION = False
            js, sid = self.edit(cdp, s)
            fields = js("document.querySelectorAll('[data-rich]').length")
            self.assertGreaterEqual(fields, 1, "the text sections show a rich field")
            before = js("document.querySelectorAll('style').length")
            js("document.querySelectorAll('[data-rich]').forEach(function(f){ f.click(); })")
            self.assertTrue(wait(lambda: js("document.querySelectorAll('.ProseMirror').length") == fields, 10))
            self.assertEqual(js("document.querySelectorAll('.ProseMirror').length"), js("document.querySelectorAll('.ProseMirror').length"))
            self.assertEqual(js("[...document.querySelectorAll('.ProseMirror')].every(function(e){ return !!e.cxed && typeof e.cxed.html === 'function'; })"), True)
            self.assertEqual(js("document.querySelectorAll('[contenteditable]').length"),
                             js("document.querySelectorAll('.ProseMirror').length + document.querySelectorAll('[contenteditable=plaintext-only]').length"),
                             "no contenteditable but the editors' own and the section titles")
            self.assertEqual(js("document.querySelectorAll('style').length"), before, "a mount adds no <style>")

    def test_every_template_field_opens_a_clark_editor_and_nothing_else(self):
        """Row 1005: the template fields' words (linkcard, onedoc, callout) open clarkEditor() in Edit, hold their old plain lines, and
        add no plain box and no contenteditable of their own."""
        import json
        from clark import store as store_module
        file = {"name": "Signed SOW.pdf", "rel": "Report files/Signed SOW.pdf", "bytes": 2048}
        content = {"linkcard": {"href": "https://example.org/x", "text": ["Old <b>card</b> line"]}, "onedoc": {"file": file, "text": ["Old <b>doc</b> line"]},
                   "callout": {"tone": "info", "title": "Fictional", "paras": ["Old <b>callout</b> line"]}}
        refs = {}
        for kind, value in content.items():
            with self.store.step("dashboard", USER) as st:
                refs[kind] = st.create("report_sections", {"project": "ABC", "type": kind, "title": "Fictional " + kind, "sort_order": 990})
            with self.store.step("dashboard", USER) as st:
                st.update("report_sections", refs[kind], {"body": store_module.check_section_body(kind, json.dumps({"v": 1, **value}))})
        s = self.serve(self.page_on)
        with chrome() as cdp:
            js, sid = self.edit(cdp, s)
            for kind, ref in refs.items():
                sec = f"[data-id=\"{ref}\"]"
                self.assertTrue(wait(lambda: js(f"!!document.querySelector('{sec} [data-rich={kind}]')"), 10), kind)
                self.assertEqual(js(f"document.querySelectorAll('{sec} textarea').length"), 0, kind)
                js(f"document.querySelector('{sec} [data-rich]').click()")
                self.assertTrue(wait(lambda: js(f"!!document.querySelector('{sec} .ProseMirror')"), 10), kind)
                self.assertEqual(js(f"typeof document.querySelector('{sec} .ProseMirror').cxed.html"), "function", kind)
                self.assertIn("Old <b>", js(f"document.querySelector('{sec} .ProseMirror').textContent"), "the old plain line opens as text")
                self.assertEqual(js(f"document.querySelectorAll('{sec} .ProseMirror [contenteditable], {sec} b').length"), 0, kind)

    def test_the_at_a_glance_reason_opens_the_one_editor_with_its_menu(self):          # item 1005
        with self.store.step("dashboard", USER) as st:
            st.update("projects", "ABC", {"health": "At risk", "health_reason": "Old plain words <b>kept</b>\nand a second line"})      # an old plain row
        s = self.serve(self.page_on)
        with chrome() as cdp:
            js, sid = self.edit(cdp, s)
            self.assertEqual(js("document.querySelector('[data-reason]').querySelector('.prose').innerHTML"),
                             "<p>Old plain words &lt;b&gt;kept&lt;/b&gt;</p><p>and a second line</p>", "an old plain reason reads as escaped paragraphs")
            js("document.querySelector('[data-reason]').click()")
            self.assertTrue(wait(lambda: js("!!document.querySelector('[data-reason] .ProseMirror')"), 10))
            self.assertEqual(js("!!document.querySelector('[data-reason] .ProseMirror').cxed && typeof document.querySelector('[data-reason] .ProseMirror').cxed.html"), "function")
            self.assertEqual(js("document.querySelectorAll('[data-reason] .rt-bar').length"), 1, "the toolbar")
            self.assertEqual(js("document.querySelectorAll('textarea[data-reason]').length"), 0)

    def test_a_save_that_the_server_refuses_says_so_in_plain_words_and_keeps_the_field_open(self):
        small = mock.patch.object(changes, "TEXT_BODY_MAX", 10)        # the server thread reads the same module: a body over 10 bytes is too long
        small.start()
        self.addCleanup(small.stop)
        s = self.serve(self.page_on)
        with chrome() as cdp:
            js, sid = self.edit(cdp, s)
            self.open_field(cdp, js, sid)             # waits until the editor has the focus: a key sent before that goes to the page (the hosted Mac is slow)
            js("document.querySelector('.ProseMirror').cxed.editor.commands.insertContent('New words'); true")
            self.key(cdp, sid, "Enter", "Enter", 13, self.mod(js))
            self.assertTrue(wait(lambda: any(r.get("changes", {}).get("body") for r in self.sent), 30), "the change was sent")  # a bounded poll: the hosted macOS runner can take longer than 10 s
            self.assertTrue(wait(lambda: js("!!document.querySelector('.toast')"), 30))
            self.assertTrue(js("!!document.querySelector('.ProseMirror')"), "the field stays open")
            toast = js("document.querySelector('.toast-text').textContent")
            self.assertNotIn("Traceback", toast)
            self.assertIn("too long to save", toast)
            self.assertIn("nothing was changed", toast)

    def stored(self):
        return next(r for r in self.store.read("report_sections", "ABC") if r["id"] == self.sec)["body"]

    def open_field(self, cdp, js, sid):
        js("document.querySelector('[data-rich]').click()")
        self.assertTrue(wait(lambda: js("!!document.querySelector('.ProseMirror')"), 10))
        self.assertTrue(wait(lambda: js("document.activeElement && document.activeElement.classList.contains('ProseMirror')"), 10),
                        "the editor has the focus when it opens")

    def mod(self, js):
        return 4 if js("/Mac/.test(navigator.platform)") else 2

    def key(self, cdp, sid, key, code, vk, modifiers=0):
        for kind in ("keyDown", "keyUp"):
            cdp.call("Input.dispatchKeyEvent", {"type": kind, "key": key, "code": code, "windowsVirtualKeyCode": vk, "modifiers": modifiers}, sid)

    def test_a_saved_body_is_still_there_when_the_field_is_opened_again_and_the_focus_comes_back(self):
        self.seed_body()
        s = self.serve(self.page_on)
        with chrome() as cdp:
            js, sid = self.edit(cdp, s)
            self.assertIn("Original words", js("document.querySelector('[data-rich]').textContent"))
            self.open_field(cdp, js, sid)
            js("document.querySelector('.ProseMirror').cxed.editor.commands.insertContent('Added words. '); true")
            self.key(cdp, sid, "Enter", "Enter", 13, self.mod(js))
            self.assertTrue(wait(lambda: any(r.get("changes", {}).get("body") for r in self.sent), 10), "the change was sent")
            self.assertTrue(wait(lambda: js("!document.querySelector('.ProseMirror')"), 10),
                            "the field closed after the save: " + str(js("(document.querySelector('.toast-text') || {}).textContent")))
            self.assertIn("Original words", self.sent[-1]["changes"]["body"])
            self.assertTrue(wait(lambda: js("document.activeElement && document.activeElement.matches('[data-rich]')"), 5),
                            "after a save the focus is on the field, not the page body")
            shown = js("document.querySelector('[data-rich]').textContent")
            self.assertIn("Original words", shown, "the saved section still has its text")
            self.assertIn("Added words", shown)
            self.assertNotIn("Click to write", shown)
            # open it again: the editor holds what was stored, so the next save does not overwrite it with only the new words
            self.open_field(cdp, js, sid)
            held = js("document.querySelector('.ProseMirror').textContent")
            self.assertIn("Original words", held)
            self.assertIn("Added words", held)
            js("document.querySelector('.ProseMirror').cxed.editor.commands.insertContent('Second edit. '); true")
            self.key(cdp, sid, "Enter", "Enter", 13, self.mod(js))
            self.assertTrue(wait(lambda: len([r for r in self.sent if r.get("changes", {}).get("body")]) == 2, 10))
            second = [r for r in self.sent if r.get("changes", {}).get("body")][-1]["changes"]["body"]
            self.assertIn("Original words", second)
            self.assertIn("Added words", second)
            self.assertIn("Second edit", second)
            self.assertIn("Original words", self.stored())

    def test_a_saved_body_is_clean_in_the_store_and_shows_in_view_after_a_reload(self):
        self.seed_body()
        s = self.serve(self.page_on)
        with chrome() as cdp:
            js, sid = self.edit(cdp, s)
            self.open_field(cdp, js, sid)
            js("document.querySelector('.ProseMirror').cxed.editor.commands.insertContent('<p>ZQ-SAVED <strong>bold</strong></p>'); true")
            self.key(cdp, sid, "Enter", "Enter", 13, self.mod(js))
            self.assertTrue(wait(lambda: "ZQ-SAVED" in self.stored(), 15), "the save reached the store")
            self.assertEqual(self.stored(), sanitise.clean_html(self.stored()), "what is stored is clean")
            self.assertIn("<strong>bold</strong>", self.stored())
            view = f"document.querySelector('[data-id=\"{self.sec}\"] [data-view-text]')"
            reload_to_new_page_cdp(cdp, sid, ready=f"!!{view}", what="View draws the body after a reload")
            self.assertIn("ZQ-SAVED", js(f"{view}.textContent"))
            self.assertIn("Original words", js(f"{view}.textContent"))
            self.assertEqual(js(f"{view}.querySelector('strong').textContent"), "bold")
            self.assertEqual(js("document.querySelectorAll('.ProseMirror, [data-rich], [contenteditable]').length"), 0, "nothing is editable in View")

    def test_esc_puts_the_focus_back_on_the_field_and_keeps_the_stored_text(self):
        self.seed_body()
        s = self.serve(self.page_on)
        with chrome() as cdp:
            js, sid = self.edit(cdp, s)
            self.open_field(cdp, js, sid)
            js("document.querySelector('.ProseMirror').cxed.editor.commands.insertContent('Words to throw away. '); true")
            self.key(cdp, sid, "Escape", "Escape", 27)
            self.assertTrue(wait(lambda: js("!document.querySelector('.ProseMirror')"), 10), "Esc closed the field")
            self.assertTrue(wait(lambda: js("document.activeElement && document.activeElement.matches('[data-rich]')"), 5),
                            "after Esc the focus is on the field, not the page body")
            self.assertEqual(self.stored(), ORIGINAL)
            self.assertEqual([r for r in self.sent if r.get("changes", {}).get("body")], [], "Esc saved nothing")

    def test_a_click_elsewhere_closes_the_field_and_leaves_the_focus_where_it_went(self):
        self.seed_body()
        s = self.serve(self.page_on)
        with chrome() as cdp:
            js, sid = self.edit(cdp, s)
            self.open_field(cdp, js, sid)
            x, y = js("(() => { const r = document.querySelector('.sec[data-type=milestones] h2, .sec h2').getBoundingClientRect(); return [r.x + 4, r.y + r.height / 2]; })()")
            for kind in ("mousePressed", "mouseReleased"):
                cdp.call("Input.dispatchMouseEvent", {"type": kind, "x": x, "y": y, "button": "left", "clickCount": 1}, sid)
            self.assertTrue(wait(lambda: js("!document.querySelector('.ProseMirror')"), 10), "leaving the field closed it")
            self.assertEqual(js("document.activeElement.matches('[data-rich]')"), False, "the focus stayed where the person put it")

    def test_space_opens_the_field_as_enter_does(self):
        self.seed_body()
        s = self.serve(self.page_on)
        with chrome() as cdp:
            js, sid = self.edit(cdp, s)
            js("(() => { const f = document.querySelector('[data-rich]'); f.focus(); "
               "f.dispatchEvent(new KeyboardEvent('keydown', { key: ' ', bubbles: true, cancelable: true })); })()")
            self.assertTrue(wait(lambda: js("!!document.querySelector('.ProseMirror')"), 10), "Space opened the editor")

    def test_when_the_page_cannot_read_again_the_section_keeps_its_text_and_the_toast_says_so(self):
        self.seed_body()
        s = self.serve(self.page_on)
        with chrome() as cdp:
            js, sid = self.edit(cdp, s)
            self.fail_reads = True
            self.open_field(cdp, js, sid)
            js("document.querySelector('.ProseMirror').cxed.editor.commands.insertContent('Added words. '); true")
            self.key(cdp, sid, "Enter", "Enter", 13, self.mod(js))
            self.assertTrue(wait(lambda: js("(document.querySelector('.toast-text') || {}).textContent || ''").endswith("Reload the page to see it."), 10))
            self.assertIn("could not be refreshed", js("document.querySelector('.toast-text').textContent"))
            shown = js("document.querySelector('[data-rich]').textContent")
            self.assertIn("Original words", shown, "the reply carried no body, so the section kept the one the page had")
            self.assertNotIn("Click to write", shown)

    def test_the_text_and_image_words_open_the_one_editor_and_old_lines_read_in_it(self):
        """Row 1005: the Text and image template's words are a RichField (the / menu), not a plain box; its old lines open in it."""
        with self.store.step("dashboard", USER) as st:
            ref = st.create("report_sections", {"project": "ABC", "type": "textimage", "title": "Fictional words", "sort_order": 999, "hidden": 0})
        with self.store.step("dashboard", USER) as st:
            st.update("report_sections", ref, {"body": '{"v":1,"words":["Old a < b & c","He said \\"yes\\""]}'})
        s = self.serve(self.page_on)
        with chrome() as cdp:
            js, sid = self.edit(cdp, s)
            sel = f"[data-id='{ref}']"
            self.assertTrue(wait(lambda: js(f"!!document.querySelector(\"{sel} [data-rich]\")"), 10), "the words are a rich field")
            self.assertEqual(js(f"document.querySelectorAll(\"{sel} textarea\").length"), 0, "no plain box for the words")
            self.assertEqual(js(f"[...document.querySelectorAll(\"{sel} [data-rich=textimage] p\")].map(function(e){{ return e.textContent; }})"),
                             ["Old a < b & c", 'He said "yes"'])
            js(f"document.querySelector(\"{sel} [data-rich]\").click()")
            self.assertTrue(wait(lambda: js(f"!!document.querySelector(\"{sel} .ProseMirror\")"), 10))
            self.assertEqual(js(f"typeof document.querySelector(\"{sel} .ProseMirror\").cxed.html"), "function", "it is clarkEditor")
            js(f"document.querySelector(\"{sel} .ProseMirror\").cxed.editor.commands.insertContent('<p>New words</p>'); true")
            self.key(cdp, sid, "Enter", "Enter", 13, self.mod(js))
            self.assertTrue(wait(lambda: '"html"' in next(r for r in self.store.read("report_sections", "ABC") if r["id"] == ref)["body"], 20))
            body = next(r for r in self.store.read("report_sections", "ABC") if r["id"] == ref)["body"]
            self.assertNotIn('"words"', body, "the editor saves html and takes the old lines out")
            self.assertIn("&lt; b &amp; c", body, "the old line came into the editor as text, and is stored escaped")


class TextImageSource(unittest.TestCase):
    def test_the_text_and_image_words_use_the_rich_field_and_no_plain_box(self):
        edit = (PAGE_SRC / "edit" / "templates" / "TextImage.jsx").read_text(encoding="utf-8")
        self.assertIn("RichField", edit)
        self.assertNotIn("WordsField", edit)
        self.assertNotIn("<textarea", edit)


# Item 1005: the plain multiline fields that moved onto the one editor, one entry per field (LATEST_MOVED; the Movement note and the Reason are MOVED, above): (file, the RichField line's field name, the
# column it writes). A field joins this list when its plain box is replaced; a plain box left in its file is not allowed to come back.
LATEST_MOVED = (("edit/PeekLatest.jsx", "latest_update", "actions.latest_update"),
         ("edit/MilestonePeek.jsx", "description", "milestones.description"))


class MovedLatestFields(unittest.TestCase):
    """Each moved field draws through RichField (so through clarkEditor and the / menu), stores through the server's cleaner, and keeps no plain box."""

    def test_each_moved_field_is_a_rich_field_and_its_file_has_no_plain_box_for_it(self):
        for rel, field, column in LATEST_MOVED:
            with self.subTest(column):
                text = (PAGE_SRC / rel).read_text(encoding="utf-8")
                self.assertRegex(text, r'<RichField[^>]*field="%s"' % field)
                self.assertIn("richOrPlain(", text, "an old plain value is read through the one legacy rule, never drawn as stored")
                if rel.endswith("PeekLatest.jsx"):
                    self.assertNotIn("<textarea", text)
                else:
                    self.assertNotRegex(text, r'<Text [^>]*field="description"')

    def test_each_moved_field_is_cleaned_by_the_server_and_again_when_published(self):
        from clark import publish
        for table, field in (("actions", "latest_update"), ("milestones", "description")):
            with self.subTest(field):
                self.assertIn(field, publish.RICH.get(table, ()), "published through clean_html")
                self.assertIn((table, field), publish.LEGACY_RICH, "an old plain row reads as escaped paragraphs")
        from clark import excel
        self.assertEqual(excel.RICH_WORDS, publish.LEGACY_RICH + (("milestones", "internal_note"), ("use_cases", "standing")), "the workbook carries the words of the same fields, of the Movement note (never published, so not in the published list) and, row 1060, of a use case's Where it stands (HTML from the start, so not legacy)")
        src = (SRC / "clark" / "changes.py").read_text(encoding="utf-8")
        self.assertEqual(src.count("_rich_field("), 4, "the definition and the three fields' writes (latest update, Internal note, description)")

    def test_the_published_page_carries_no_editor_for_them(self):
        page.ensure_built()
        view = (SRC / "clark" / "page" / "page-view.html").read_text(encoding="utf-8")
        for word in ("richOrPlain", "legacyToHtml"):
            self.assertNotIn(word, view, word)


if __name__ == "__main__":
    unittest.main()
