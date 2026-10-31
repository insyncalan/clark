"""#66: the one rich editor (clarkEditor) and its parts, in a real browser.

Run: python3 dev/run_tests.py test_rich_editor
The editor is bundled the way the page is (tests/_rich_page.py) and driven with real key events in headless Chrome
(test_server.chrome). Fictional text only. Desktop widths 1400 and 900, light and dark.
"""
import json
import sys
import time
import unittest

import _rich_page as rp
from test_server import chrome

sys.path.insert(0, str(rp.TOOLS))

CANON = {
    "words": "<p>Plain words in one paragraph.</p>",
    "marks": "<p><strong>Bold</strong> and <em>italic</em> and <s>struck</s>.</p>",
    "nested": "<p><strong><em>both</em></strong></p>",
    "headings": "<h1>One</h1><h2>Two</h2><h3>Three</h3><p>Body.</p>",
    "bullets": "<ul><li><p>First</p></li><li><p>Second</p></li></ul>",
    "numbers": "<ol><li><p>First</p></li><li><p>Second</p></li></ol>",
    "checklist": '<ul><li><input type="checkbox" checked><p>Done</p></li><li><input type="checkbox"><p>To do</p></li></ul>',
    "quote": "<blockquote><p>Quoted words.</p></blockquote>",
    "rule": "<p>Above</p><hr><p>Below</p>",
    "link": '<p>See <a href="https://example.com/a?x=1&amp;y=2" rel="noopener noreferrer">the page</a>.</p>',
    "break": "<p>Line one<br>Line two</p>",
    "escapes": "<p>Fish &amp; chips &lt;3 and a &gt; b</p>",
}


class Core(unittest.TestCase):
    """clarkEditor on its own: what it holds, writes, refuses and adds to the page."""

    @classmethod
    def setUpClass(cls):
        cls.h = rp.Harness(chrome).__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.h.__exit__(None, None, None)

    def make(self, html, profile="rich"):
        """A detached editor, kept as window.ed."""
        return self.h.ev(f"(function(){{ var el = document.createElement('div'); document.body.appendChild(el); "
                         f"window.el = el; window.ed = CE.clarkEditor(el, {{profile: {json.dumps(profile)}, html: {json.dumps(html)}}}); return true; }})()")

    def drop(self):
        self.h.ev("(function(){ if (window.ed) window.ed.destroy(); if (window.el) window.el.remove(); window.ed = window.el = null; return true; })()")

    def test_an_untouched_field_comes_back_byte_for_byte(self):
        stored = ["", CANON["marks"], CANON["checklist"], "<p>a<b>unclean</b></p><script>1</script>", "<div>stray</div>",
                  "<p>x</p>" * 40, CANON["escapes"], "plain text with no tag"]
        for s in stored:
            with self.subTest(stored=s[:40]):
                self.make(s)
                self.assertEqual(self.h.ev("window.ed.html()"), s)
                self.assertFalse(self.h.ev("window.ed.dirty()"))
                self.drop()

    def test_what_it_writes_is_what_the_cleaner_returns(self):
        for name, clean in CANON.items():
            with self.subTest(name=name):
                self.make(clean)
                written = self.h.ev("window.ed.written()")
                self.assertEqual(written, self.h.ev(f"CE.cleanHtml({json.dumps(written)})"), "the cleaner changes nothing more")
                self.assertEqual(written, clean)
                self.drop()

    def test_editing_gives_cleaned_html(self):
        self.make(CANON["words"])
        self.h.ev("window.ed.editor.commands.focus('end'); window.ed.editor.commands.insertContent(' More <b>words</b> & <i>stuff</i>.'); true")
        out = self.h.ev("window.ed.html()")
        self.assertTrue(self.h.ev("window.ed.dirty()"))
        self.assertEqual(out, self.h.ev(f"CE.cleanHtml({json.dumps(out)})"))
        self.assertIn("&amp;", out)
        self.assertNotIn("<b>", out)
        self.drop()

    def test_a_link_is_written_with_a_rel_and_nothing_else(self):
        self.make("<p>Go there</p>")
        self.h.ev("window.ed.editor.commands.selectAll(); true")
        self.assertTrue(self.h.ev("window.ed.run('link', 'example.com/x')") is False, "no scheme: the editor box adds https, the command wants a whole address")
        self.assertTrue(self.h.ev("window.ed.run('link', 'https://example.com/x')"))
        out = self.h.ev("window.ed.html()")
        self.assertEqual(out, '<p><a href="https://example.com/x" rel="noopener noreferrer">Go there</a></p>')
        self.drop()

    def test_an_unsafe_link_address_is_refused(self):
        self.make("<p>Go there</p>")
        self.h.ev("window.ed.editor.commands.selectAll(); true")
        for bad in ("javascript:alert(1)", "data:text/html,x", "  JaVaScRiPt:1", "vbscript:x", "file:///etc", "//evil.example.com"):
            with self.subTest(address=bad):
                self.assertFalse(self.h.ev(f"window.ed.run('link', {json.dumps(bad)})"))
        self.assertFalse(self.h.ev("window.ed.dirty()"))
        self.drop()

    def test_a_paste_goes_through_the_cleaner(self):
        self.make("<p>Start</p>")
        hostile = ('<p>ok</p><script>window.pwned=1</script><img src=x onerror="window.pwned=1"><a href="javascript:window.pwned=1">bad</a>'
                   '<iframe src="https://example.com"></iframe><style>p{}</style><b onclick="1">kept</b>')
        self.h.ev(f"window.ed.editor.commands.focus('end'); window.ed.editor.view.pasteHTML({json.dumps(hostile)}); true")
        raw = self.h.ev("JSON.stringify(window.ed.editor.getJSON())")
        for bad in ("script", "img", "onerror", "javascript", "iframe", "style", "onclick"):
            self.assertNotIn(bad, raw, "the document itself is clean straight after the paste")
        out = self.h.ev("window.ed.written()")
        for bad in ("script", "<img", "onerror", "javascript", "iframe", "<style", "onclick"):
            self.assertNotIn(bad, out)
        self.assertIn("kept", out)
        self.assertIsNone(self.h.ev("window.pwned"))
        self.drop()

    def test_a_paste_too_long_for_a_field_is_refused_by_the_cleaner(self):
        """The editor's own schema already drops scripts and the like, so only a too-long paste shows that the cleaner runs at all."""
        self.make("<p>Start</p>")
        self.h.ev("window.ed.editor.commands.focus('end'); window.ed.editor.view.pasteHTML('<p>' + 'a'.repeat(200100) + '</p>'); true")
        raw = self.h.ev("JSON.stringify(window.ed.editor.getJSON())")
        self.assertNotIn("aaaa", raw, "straight after the paste, before html() is read")
        self.drop()

    def test_it_adds_no_style_element_to_the_page(self):
        before = self.h.ev("document.querySelectorAll('style').length")
        self.make(CANON["checklist"])
        self.assertEqual(self.h.ev("document.querySelectorAll('style').length"), before)
        self.drop()

    def test_every_editor_has_the_handle(self):
        self.make(CANON["words"])
        self.assertTrue(self.h.ev("window.el.querySelector('.ProseMirror').cxed === window.ed"))
        self.drop()

    def test_only_the_allowed_formats_exist(self):
        self.make("<p>x</p>")
        have = self.h.ev("Object.keys(window.ed.editor.schema.nodes).concat(Object.keys(window.ed.editor.schema.marks))")
        for gone in ("codeBlock", "image", "htmlBlock", "htmlInline", "literal", "code", "underline", "table"):
            self.assertNotIn(gone, have)
        self.drop()

    def test_the_plain_profile_holds_text_and_no_marks(self):
        self.make("Fish <&> chips", "plain")
        self.assertEqual(self.h.ev("window.ed.html()"), "Fish <&> chips")
        self.h.ev("window.ed.editor.commands.focus('end'); window.ed.editor.commands.insertContent(' <b>more</b>'); true")
        self.assertEqual(self.h.ev("window.ed.html()"), "Fish <&> chips <b>more</b>")
        self.assertEqual(self.h.ev("window.el.querySelectorAll('strong, b').length"), 0)
        self.drop()

    def test_too_long_is_a_cleaner_error(self):
        self.make("<p>x</p>")
        self.h.ev("window.ed.editor.commands.insertContent('y'.repeat(200001)); true")
        self.assertEqual(self.h.ev("(function(){ try { window.ed.html(); return 'no error'; } catch (e) { return e.name; } })()"), "SanitiseError")
        self.drop()


class Ui(unittest.TestCase):
    """RichText: the keys, the toolbar, the bubble and the / menu."""

    @classmethod
    def setUpClass(cls):
        cls.h = rp.Harness(chrome).__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.h.__exit__(None, None, None)

    def setUp(self):
        self.h.ev("window.saveResult = true; true")

    def tearDown(self):
        self.h.ev("window.unmount(); true")                                  # leaves nothing open for the next test

    def saves(self):
        return self.h.ev("window.saves")

    def test_cmd_enter_saves_and_closes(self):
        self.h.mount("<p>Start</p>")
        self.h.type(" more")
        self.h.key("Enter", self.h.mod, "Enter", 13)
        self.assertTrue(self.h.until("window.saves.length === 1"))
        self.assertEqual(self.saves(), ["<p>Start more</p>"])
        self.assertTrue(self.h.until("window.ended === 1 && !document.querySelector('.rt')"))

    def test_esc_cancels_without_saving(self):
        self.h.mount("<p>Start</p>")
        self.h.type(" never kept")
        self.h.key("Escape", 0, "Escape", 27)
        self.assertTrue(self.h.until("window.ended === 1"))
        self.assertEqual(self.saves(), [])

    def test_leaving_the_field_saves_an_edit_and_an_untouched_field_just_closes(self):
        self.h.mount("<p>Start</p>")
        self.h.type(" more")
        self.h.ev("document.getElementById('outside').focus(); true")
        self.assertTrue(self.h.until("window.ended === 1"))
        self.assertEqual(self.saves(), ["<p>Start more</p>"])
        self.h.mount("<p>Start</p>")
        self.h.ev("document.getElementById('outside').focus(); true")
        self.assertTrue(self.h.until("window.ended === 1"))
        self.assertEqual(self.saves(), [])

    def test_a_save_that_fails_keeps_the_field_open(self):
        self.h.ev("window.saveResult = null; true")
        self.h.mount("<p>Start</p>")
        self.h.type(" more")
        self.h.key("Enter", self.h.mod, "Enter", 13)
        self.assertTrue(self.h.until("window.saves.length === 1"))
        self.assertEqual(self.h.ev("window.ended"), 0)
        self.assertTrue(self.h.ev("!!document.querySelector('.rt .ProseMirror')"))
        self.assertIn("More", self.h.ev("document.querySelector('.ProseMirror').textContent").title())

    def test_too_long_says_so_in_plain_words_and_stays_open(self):
        self.h.mount("<p>Start</p>")
        self.h.ev("document.querySelector('.ProseMirror').cxed.editor.commands.insertContent('y'.repeat(200001)); true")
        self.h.key("Enter", self.h.mod, "Enter", 13)
        self.assertTrue(self.h.until("!!document.querySelector('.rt-problem')"))
        self.assertIn("too long", self.h.ev("document.querySelector('.rt-problem').textContent"))
        self.assertEqual(self.saves(), [])

    def test_one_undo_undoes_one_edit(self):
        self.h.mount("<p>Start</p>")
        self.h.type(" one")
        time.sleep(0.9)                                                    # past the history's grouping delay: a second edit
        self.h.type(" two")
        self.assertEqual(self.h.ev("document.querySelector('.ProseMirror').textContent"), "Start one two")
        self.h.key("z", self.h.mod, "KeyZ", 90)
        self.assertTrue(self.h.until("document.querySelector('.ProseMirror').textContent === 'Start one'"))

    def test_the_toolbar_formats_a_selection(self):
        self.h.mount("<p>Some words</p>")
        self.h.select_all()
        for name, tag in (("Bold", "strong"), ("Italic", "em"), ("Strikethrough", "s")):
            self.h.ev(f"document.querySelector('.rt-bar [aria-label=\"{name}\"]').click(); true")
            self.assertTrue(self.h.until(f"!!document.querySelector('.ProseMirror {tag}')"), name)
        self.h.key("Enter", self.h.mod, "Enter", 13)
        self.assertTrue(self.h.until("window.saves.length === 1"))
        self.assertEqual(self.saves(), ["<p><strong><em><s>Some words</s></em></strong></p>"])

    def test_the_toolbar_makes_lists_a_checklist_and_a_quote(self):
        for name, want in (("Bulleted list", "<ul><li><p>Item</p></li></ul>"), ("Numbered list", "<ol><li><p>Item</p></li></ol>"),
                           ("Checklist", '<ul><li><input type="checkbox"><p>Item</p></li></ul>'), ("Quote", "<blockquote><p>Item</p></blockquote>")):
            with self.subTest(name=name):
                self.h.mount("<p>Item</p>")
                self.h.ev(f"document.querySelector('.rt-bar [aria-label=\"{name}\"]').click(); true")
                self.h.key("Enter", self.h.mod, "Enter", 13)
                self.assertTrue(self.h.until("window.saves.length === 1"))
                self.assertEqual(self.saves(), [want])

    def test_the_style_menu_sets_a_heading(self):
        self.h.mount("<p>Title</p>")
        self.h.ev("document.querySelector('.rt-bar .rt-style').click(); true")
        self.assertTrue(self.h.until("!!document.querySelector('.rt-bar [role=menu]')"))
        self.h.ev("document.querySelector('.rt-bar [role=menuitem][data-kind=h2]').click(); true")
        self.assertTrue(self.h.until("!!document.querySelector('.ProseMirror h2')"), "the heading was made")
        self.assertTrue(self.h.until("!!document.activeElement && document.activeElement.classList.contains('ProseMirror')"),
                        f"focus is back in the text: {self.h.ev('document.activeElement.outerHTML.slice(0, 80)')}")
        self.h.key("Enter", self.h.mod, "Enter", 13)
        self.assertTrue(self.h.until("window.saves.length === 1"))
        self.assertEqual(self.saves(), ["<h2>Title</h2>"])

    def test_the_bubble_shows_over_a_selection_and_only_then(self):
        self.h.mount("<p>Some words to pick from</p>")
        self.assertFalse(self.h.ev("!!document.querySelector('.rt-bubble')"))
        self.h.select_all()
        self.assertTrue(self.h.until("!!document.querySelector('.rt-bubble')"))
        self.h.ev("document.querySelector('.rt-bubble [aria-label=Bold]').click(); true")
        self.assertTrue(self.h.until("!!document.querySelector('.ProseMirror strong')"))
        self.h.key("ArrowRight", 0, "ArrowRight", 39)
        self.assertTrue(self.h.until("!document.querySelector('.rt-bubble')"))

    def test_the_slash_menu_inserts_a_block(self):
        self.h.mount("")
        self.h.type("/")
        self.assertTrue(self.h.until("!!document.querySelector('.rt-slash')"))
        self.assertGreaterEqual(self.h.ev("document.querySelectorAll('.rt-slash [role=option]').length"), 6)
        self.h.type("head")                                                  # narrows to the three headings
        self.assertTrue(self.h.until("document.querySelectorAll('.rt-slash [role=option]').length === 3"))
        self.h.key("ArrowDown", 0, "ArrowDown", 40)
        self.h.key("Enter", 0, "Enter", 13)                                   # Heading 2
        self.assertTrue(self.h.until("!document.querySelector('.rt-slash') && !!document.querySelector('.ProseMirror h2')"))
        self.assertEqual(self.h.ev("document.querySelector('.ProseMirror').textContent"), "")
        self.assertEqual(self.saves(), [])                                    # Enter inside the menu did not save

    def test_esc_in_the_slash_menu_closes_the_menu_not_the_field(self):
        self.h.mount("")
        self.h.type("/")
        self.assertTrue(self.h.until("!!document.querySelector('.rt-slash')"))
        self.h.key("Escape", 0, "Escape", 27)
        self.assertTrue(self.h.until("!document.querySelector('.rt-slash')"))
        self.assertEqual(self.h.ev("window.ended"), 0)

    def test_the_link_box_refuses_an_unsafe_address_and_applies_a_good_one(self):
        self.h.mount("<p>Go there</p>")
        self.h.select_all()
        self.h.ev("document.querySelector('.rt-bar [aria-label=Link]').click(); true")
        self.assertTrue(self.h.until("!!(document.activeElement && document.activeElement.closest('.rt-link'))"))
        self.h.type("javascript:alert(1)")
        self.h.key("Enter", 0, "Enter", 13)
        self.assertTrue(self.h.until("!!document.querySelector('.rt-problem')"))
        self.assertIn("can't be used", self.h.ev("document.querySelector('.rt-problem').textContent"))
        self.assertFalse(self.h.ev("!!document.querySelector('.ProseMirror a')"))
        self.h.ev("(function(){ var i = document.querySelector('.rt-link input'); i.select(); return true; })()")
        self.h.type("example.com/page")
        self.h.key("Enter", 0, "Enter", 13)
        self.assertTrue(self.h.until("!!document.querySelector('.ProseMirror a') && !!document.activeElement && document.activeElement.classList.contains('ProseMirror')"))
        self.h.key("Enter", self.h.mod, "Enter", 13)
        self.assertTrue(self.h.until("window.saves.length === 1"))
        self.assertEqual(self.saves(), ['<p><a href="https://example.com/page" rel="noopener noreferrer">Go there</a></p>'])

    def test_a_script_in_a_stored_field_does_not_run_when_it_is_opened(self):
        self.h.mount('<p>Hello</p><script>window.pwned = 1</script><img src=x onerror="window.pwned = 1">')
        self.assertIsNone(self.h.ev("window.pwned"))
        self.assertEqual(self.h.ev("document.querySelectorAll('.ProseMirror script, .ProseMirror img').length"), 0)

    def measure(self):
        return self.h.ev("""(function(){
          var bar = document.querySelector('.rt-bar'), r = bar.getBoundingClientRect(), ys = {};
          bar.querySelectorAll('button').forEach(function(b){ ys[Math.round(b.getBoundingClientRect().top)] = 1; });
          return { rows: Object.keys(ys).length, barRight: r.right, wide: document.documentElement.scrollWidth, win: window.innerWidth,
                   scrollbar: document.documentElement.scrollWidth > window.innerWidth };
        })()""")

    def inside(self, selector):
        return self.h.ev(f"""(function(){{ var r = document.querySelector({json.dumps(selector)}).getBoundingClientRect();
          return r.left >= 0 && r.top >= 0 && r.right <= window.innerWidth && r.bottom <= window.innerHeight; }})()""")

    def test_layout_at_both_widths_in_light_and_dark(self):
        for width in (1400, 900):
            for theme in ("light", "dark"):
                with self.subTest(width=width, theme=theme):
                    self.h.resize(width)
                    self.h.theme(theme)
                    self.h.mount("<p>Some words to pick from in a field</p>")
                    m = self.measure()
                    self.assertEqual(m["rows"], 1, "the toolbar fits one line")
                    self.assertFalse(m["scrollbar"], "no sideways scroll")
                    self.h.select_all()
                    self.assertTrue(self.h.until("!!document.querySelector('.rt-bubble')"))
                    self.assertTrue(self.inside(".rt-bubble"), "the bubble is inside the window")
                    self.h.ev("(function(){ var e = document.querySelector('.ProseMirror').cxed.editor; e.commands.setContent('<p></p>'); e.commands.focus('end'); return true; })()")
                    self.h.type("/")
                    self.assertTrue(self.h.until("!!document.querySelector('.rt-slash')"))
                    self.assertTrue(self.inside(".rt-slash"), "the / menu is inside the window")
                    self.assertFalse(self.measure()["scrollbar"])
                    self.h.ev("window.unmount(); true")
        self.h.resize(1400)
        self.h.theme("light")


if __name__ == "__main__":
    unittest.main()
