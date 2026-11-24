"""Row 1005: the Client wording of a report row (Risks and issues, Open actions, Decisions) in Edit is the one editor (RichField) on one line
and is saved as plain text, one change with one Undo, like the milestone's. Enter saves, Esc puts the old words back, a click away saves.
1400 and 900, light and dark; the row stays one line tall closed and the open editor stays inside its card. Fictional rows only.

Run: python3 dev/run_tests.py test_row_words_1005
"""
import json
import sys
import time
import unittest

from _demo import DemoStore
from _paths import TOOLS

sys.path.insert(0, str(TOOLS))
from test_item_rows import edit_server, fill, id_of  # noqa: E402
from test_report_editor import Pg  # noqa: E402
from test_server import chrome, wait  # noqa: E402

CASES = (("raid", "Supplier delivery may slip"), ("actions", "Cut-over plan to be agreed"), ("decisions", "Hosting region to be chosen"))
SPY = ("(function(){var f=window.fetch; window.__sent=[]; window.fetch=function(u,o){try{if(o&&o.body){window.__sent.push(String(o.body));}}catch(e){}"
       " return f.apply(this,arguments);};})()")
SHOWN = "[data-rich=client_message]"


def plain_only(test, p, where):
    """The focused one-line editor offers and makes no formatting: nothing is drawn but Undo and Redo, a selection has no bubble, Cmd+B and Cmd+I,
    the '/' menu and the markdown input rules ('# ', '- ', '> ') make nothing, and a paste of paragraphs with bold is its words on one line."""
    ed = "(document.activeElement.cxed.editor)"
    p.js(f"{ed}.commands.clearContent()")
    p.type("/")
    p.until(f"{ed}.getText() === '/'", f"{where}: the slash is typed")          # a positive signal first, then the negative checks
    test.assertFalse(p.js("!!document.querySelector('.rt-slash')"), f"{where}: no / menu")
    for typed, tag in (("# ", "h1"), ("- ", "ul"), ("> ", "blockquote"), ("1. ", "ol")):
        p.js(f"{ed}.commands.clearContent()")
        p.type(typed + "x")
        p.until(f"{ed}.getText().endsWith('x')", f"{where}: {typed!r} typed")
        test.assertEqual(p.js(f"{ed}.getText().slice(0, 1)"), typed[0], f"{where}: {typed!r} stays as typed")
        test.assertFalse(p.js(f"!!document.activeElement.querySelector({tag!r})"), f"{where}: {typed!r} makes no {tag}")
    p.js(f"{ed}.commands.setContent('<p>plain words</p>'); {ed}.commands.selectAll()")
    p.until(f"{ed}.state.selection.from !== {ed}.state.selection.to", f"{where}: all selected")
    for key, code, vk in (("b", "KeyB", 66), ("i", "KeyI", 73)):
        p.key(key, modifiers=4 if p.js("/Mac/.test(navigator.platform)") else 2, code=code, vk=vk)
    test.assertFalse(p.js("!!document.activeElement.querySelector('strong, b, em, i')"), f"{where}: Cmd+B and Cmd+I make nothing")
    test.assertFalse(p.js("!!document.querySelector('.rt-bubble')"), f"{where}: no bubble over a selection")
    names = p.js("[...document.querySelectorAll('.rt button')].map(b => b.getAttribute('aria-label')).filter(Boolean)")
    test.assertTrue(set(names) <= {"Undo", "Redo"}, f"{where}: only Undo and Redo are offered, got {names}")
    test.assertEqual(p.js("document.querySelectorAll('.rt-bar .rt-sep').length"), 0, f"{where}: no separators left over")
    p.js(f"{ed}.commands.clearContent()")
    p.js("(function(){var b = document.activeElement; var d = new DataTransfer(); d.setData('text/html', '<p>One <strong>bold</strong></p><ul><li>two</li></ul>'); d.setData('text/plain', 'One bold\\ntwo');"
         " b.dispatchEvent(new ClipboardEvent('paste', {clipboardData: d, bubbles: true, cancelable: true}));})()")
    p.until(f"{ed}.getText().includes('two')", f"{where}: pasted")
    test.assertEqual(p.js("document.activeElement.innerHTML.replace(/ class=\"[^\"]*\"/g, '')"), "<p>One bold two</p>", f"{where}: a paste is one plain line")
    p.js(f"{ed}.commands.clearContent()")
    p.js("(function(){var b = document.activeElement; var d = new DataTransfer(); d.setData('text/plain', 'first\\n\\nsecond   third');"
         " b.dispatchEvent(new ClipboardEvent('paste', {clipboardData: d, bubbles: true, cancelable: true}));})()")
    p.until(f"{ed}.getText().includes('third')", f"{where}: text-only pasted")
    test.assertEqual(p.js("document.activeElement.innerHTML.replace(/ class=\"[^\"]*\"/g, '')"), "<p>first second third</p>", f"{where}: a text-only paste is one plain line too")


class RowWords(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.store = self.demo.store
        fill(self.store)
        self.demo.plant_builtin_sections()      # the rows are in the built-in sections, which a new project no longer has (row 1193)
        self.s = edit_server(self, self.store)

    def stored(self, table, ident):
        return next(r for r in self.store.read(table, "ABC") if r["id"] == ident)["client_message"]

    def row(self, table, ident):
        return f"[data-type={table}] .wl-row[data-id={ident!r}]"

    def height(self, p, row):
        return p.js(f"document.querySelector({row!r}).getBoundingClientRect().height")

    def open_editor(self, p, row):
        focused = "document.activeElement.classList.contains('ProseMirror')"
        for _ in range(3):      # a click that lands while the row is still drawing is lost on a busy box: click again only while the words are still shown
            p.js(f"(() => {{ const e = document.querySelector({row!r} + ' {SHOWN}'); if (e) e.click(); }})()")
            if wait(lambda: p.js(focused), 4):
                return
        p.until(focused, "the one editor opens with the focus in it")

    def type(self, p, text):
        p.js(f"(() => {{ const e = document.activeElement.cxed.editor; e.commands.selectAll(); e.commands.insertContent({json.dumps(text)}); }})()")

    def each(self, p):
        for theme in ("light", "dark"):
            p.js("document.documentElement.setAttribute('data-theme', %r)" % theme)
            for w in (1400, 900):
                p.cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                yield theme, w

    def put(self, p, html):
        p.js(f"(() => {{ const e = document.activeElement.cxed.editor; e.commands.setContent({json.dumps(html)}); }})()")

    def save(self, p):
        p.key("Enter", modifiers=2, code="Enter", vk=13)      # Ctrl with Enter saves the Full editor (Enter alone is a new paragraph)

    def test_ctrl_enter_saves_the_html_and_one_undo_puts_the_old_words_back(self):
        """Row 1288: the Client wording is the Full editor; what is sent is its HTML and what is stored is the cleaned HTML; an older plain value is
        shown as the same words and one Undo puts it back as it was (plain)."""
        html = "<p>Plain <strong>words</strong></p><p>a client can read</p>"
        with chrome() as cdp:
            p = Pg.at(self, cdp, self.s.port)
            p.ready()
            p.edit()
            for theme, w in self.each(p):
                for table, words in CASES:
                    where = f"{theme} {w} {table}"
                    ident = id_of(self.store, words) if any(r["client_message"] == words for r in self.store.read(table, "ABC")) else None
                    self.assertTrue(ident, where)
                    row = self.row(table, ident)
                    self.assertEqual(p.js(f"document.querySelectorAll({row!r} + ' [contenteditable]:not(.ProseMirror)').length"), 0, f"{where}: no plain box of its own")
                    self.assertLess(self.height(p, row), 52, f"{where}: one line tall closed")
                    p.js(SPY)
                    self.open_editor(p, row)
                    self.assertTrue(p.js("!!document.querySelector('.rt-bar [aria-label=\"Bold\"]')"), f"{where}: the Full editor's toolbar is there")
                    self.assertEqual(p.js("document.activeElement.innerText.trim()"), words, f"{where}: the older plain words are shown as they were")
                    self.put(p, html)
                    self.save(p)
                    p.toast_is(f"Wording of {ident} changed.")
                    sent = [json.loads(b) for b in p.js("window.__sent") if "client_message" in b]
                    self.assertEqual(sent[-1]["changes"], {"client_message": html}, where)
                    self.assertEqual(self.stored(table, ident), html, where)
                    p.until(f"!document.querySelector({row!r} + ' .ProseMirror') && document.querySelector({row!r} + ' {SHOWN}').textContent.includes('a client can read')", f"{where}: closed and drawn")
                    p.until("!!document.querySelector('.toast [data-undo]')", f"{where}: the Undo is offered")
                    p.js("document.querySelector('.toast [data-undo]').click()")
                    p.until(f"document.querySelector({row!r} + ' {SHOWN}').textContent.includes({json.dumps(words)})", f"{where}: one Undo puts the old words back")
                    self.assertEqual(self.stored(table, ident), words, where)

    def test_opening_and_leaving_an_older_wording_changes_nothing(self):
        with chrome() as cdp:
            p = Pg.at(self, cdp, self.s.port)
            p.ready()
            p.edit()
            for table, words in CASES:
                ident = id_of(self.store, words)
                row = self.row(table, ident)
                p.js(SPY)
                self.open_editor(p, row)
                self.save(p)
                p.until(f"!document.querySelector({row!r} + ' .ProseMirror')", f"{table}: closed")
                self.assertEqual([b for b in p.js("window.__sent") if "client_message" in b], [], f"{table}: nothing sent")
                self.assertEqual(self.stored(table, ident), words, f"{table}: still the older plain value")

    def test_escape_keeps_the_old_words_and_a_click_away_saves(self):
        with chrome() as cdp:
            p = Pg.at(self, cdp, self.s.port)
            p.ready()
            p.edit()
            ident = id_of(self.store, "Cut-over plan to be agreed")
            row = self.row("actions", ident)
            for theme, w in self.each(p):
                where = f"{theme} {w}"
                p.js(SPY)
                self.open_editor(p, row)
                self.type(p, "Typed and abandoned")
                p.key("Escape", code="Escape", vk=27)
                p.until(f"!document.querySelector({row!r} + ' .ProseMirror') && document.querySelector({row!r} + ' {SHOWN}') && document.querySelector({row!r} + ' {SHOWN}').textContent.includes('Cut-over plan')", f"{where}: Esc closes the editor")
                self.assertEqual(self.stored("actions", ident), "Cut-over plan to be agreed", where)
                self.assertEqual([b for b in p.js("window.__sent") if "client_message" in b], [], where)
                self.open_editor(p, row)
                p.until("document.hasFocus() && document.activeElement.classList.contains('ProseMirror') && !!document.activeElement.cxed", f"{where}: the editor is focused and ready")
                time.sleep(0.3)
                self.type(p, "Saved by leaving")
                gone = f"!document.querySelector({row!r} + ' .ProseMirror')"
                end = time.time() + 15
                while time.time() < end and not p.js(gone):
                    p.js("(function(){var a = document.activeElement; if (a && a.classList.contains('ProseMirror')) { a.blur(); } document.body.focus();})()")
                    time.sleep(0.3)
                self.assertTrue(wait(lambda: self.stored("actions", ident) == "<p>Saved by leaving</p>"), f"{where}: leaving the field saves")
                p.until("!!document.querySelector('.toast [data-undo]')", f"{where}: the Undo is offered")
                p.js("document.querySelector('.toast [data-undo]').click()")
                self.assertTrue(wait(lambda: self.stored("actions", ident) == "Cut-over plan to be agreed"), f"{where}: Undo")

    def test_a_wording_over_the_limit_is_refused_in_the_field_and_nothing_is_saved(self):
        with chrome() as cdp:
            p = Pg.at(self, cdp, self.s.port)
            p.ready()
            p.edit()
            ident = id_of(self.store, "Cut-over plan to be agreed")
            row = self.row("actions", ident)
            p.js(SPY)
            self.open_editor(p, row)
            self.type(p, "x" * 600)
            self.save(p)
            p.until(f"!!document.querySelector({row!r} + ' .rt-problem')", "the field says why and stays open")
            self.assertEqual(self.stored("actions", ident), "Cut-over plan to be agreed")

    def test_a_blank_wording_clears_it_and_the_row_shows_its_title(self):
        with chrome() as cdp:
            p = Pg.at(self, cdp, self.s.port)
            p.ready()
            p.edit()
            ident = id_of(self.store, "Cut-over plan to be agreed")
            row = self.row("actions", ident)
            self.open_editor(p, row)
            self.type(p, "")
            self.save(p)
            p.toast_is(f"Wording of {ident} changed.")
            self.assertEqual(self.stored("actions", ident), "")
            p.until(f"document.querySelector({row!r} + ' {SHOWN}').textContent.includes('Agree the cut-over plan')", "the title shows")


if __name__ == "__main__":
    unittest.main()
