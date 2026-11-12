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
from clark import publish
from _paths import TOOLS

sys.path.insert(0, str(TOOLS))
from test_item_rows import edit_server, fill, id_of  # noqa: E402
from test_report_editor import Pg  # noqa: E402
from test_server import chrome, wait  # noqa: E402

CASES = (("raid", "Supplier delivery may slip"), ("actions", "Cut-over plan to be agreed"), ("decisions", "Hosting region to be chosen"))
SPY = ("(function(){var f=window.fetch; window.__sent=[]; window.fetch=function(u,o){try{if(o&&o.body){window.__sent.push(String(o.body));}}catch(e){}"
       " return f.apply(this,arguments);};})()")
SHOWN = "[data-rich=client_message]"


class RowWords(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.store = self.demo.store
        fill(self.store)
        self.s = edit_server(self, self.store)

    def stored(self, table, ident):
        return next(r for r in self.store.read(table, "ABC") if r["id"] == ident)["client_message"]

    def row(self, table, ident):
        return f"[data-type={table}] .wl-row[data-id={ident!r}]"

    def height(self, p, row):
        return p.js(f"document.querySelector({row!r}).getBoundingClientRect().height")

    def open_editor(self, p, row):
        p.js(f"document.querySelector({row!r} + ' {SHOWN}').click()")
        p.until("document.activeElement.classList.contains('ProseMirror')", "the one editor opens with the focus in it")

    def type(self, p, text):
        p.js(f"(() => {{ const e = document.activeElement.cxed.editor; e.commands.selectAll(); e.commands.insertContent({json.dumps(text)}); }})()")

    def each(self, p):
        for theme in ("light", "dark"):
            p.js("document.documentElement.setAttribute('data-theme', %r)" % theme)
            for w in (1400, 900):
                p.cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                yield theme, w

    def test_enter_saves_one_plain_line_and_one_undo_puts_the_old_words_back(self):
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
                    shut = self.height(p, row)
                    self.assertLess(shut, 52, f"{where}: one line tall")
                    p.js(SPY)
                    self.open_editor(p, row)
                    self.assertLess(self.height(p, row), 60, f"{where}: the row stays one line tall with the editor open")
                    self.assertTrue(p.js(f"(r => {{ const e = r.querySelector('.ProseMirror').getBoundingClientRect(), c = r.closest('.wl').getBoundingClientRect(); return e.left >= c.left - 1 && e.right <= c.right + 1; }})(document.querySelector({row!r}))"), f"{where}: the editor stays inside its card")
                    self.type(p, "Plain words\na client can read")
                    p.key("Enter", code="Enter", vk=13)
                    p.toast_is(f"Wording of {ident} changed.")
                    sent = [json.loads(b) for b in p.js("window.__sent") if "client_message" in b]
                    self.assertEqual(sent[-1]["changes"], {"client_message": "Plain words a client can read"}, where)
                    self.assertEqual(self.stored(table, ident), "Plain words a client can read", where)
                    p.until(f"!document.querySelector({row!r} + ' .ProseMirror') && document.querySelector({row!r} + ' {SHOWN}').textContent.includes('Plain words a client can read')", f"{where}: closed and drawn")
                    self.assertLess(abs(self.height(p, row) - shut), 2, f"{where}: the row keeps its height")
                    p.js("document.querySelector('.toast [data-undo]').click()")
                    p.until(f"document.querySelector({row!r} + ' {SHOWN}').textContent.includes({json.dumps(words)})", f"{where}: one Undo puts the old words back")
                    self.assertEqual(self.stored(table, ident), words, where)

    def test_typed_text_that_looks_like_tags_comes_back_as_the_same_text_after_a_reload_and_in_the_file(self):
        literal = "<p>use <b>x</b></p>"
        ident = id_of(self.store, "Cut-over plan to be agreed")
        row = self.row("actions", ident)
        with chrome() as cdp:
            p = Pg.at(self, cdp, self.s.port)
            p.ready()
            p.edit()
            for theme, w in self.each(p):
                where = f"{theme} {w}"
                self.open_editor(p, row)
                p.js(f"(() => {{ const e = document.activeElement.cxed.editor; e.commands.selectAll(); e.commands.insertContent({{ type: 'text', text: {json.dumps(literal)} }}); }})()")
                p.key("Enter", code="Enter", vk=13)
                self.assertTrue(wait(lambda: self.stored("actions", ident) == literal), f"{where}: the typed text is stored as typed")
                p.js("location.reload()")
                p.ready()
                p.edit()
                p.until(f"document.querySelector({row!r} + ' {SHOWN}') && document.querySelector({row!r} + ' {SHOWN}').textContent.includes('use')", f"{where}: drawn after a reload")
                self.assertEqual(p.js(f"document.querySelector({row!r} + ' {SHOWN}').textContent.trim()"), literal, f"{where}: the card shows the typed text after a reload")
                self.open_editor(p, row)
                self.assertEqual(p.js("document.activeElement.textContent"), literal, f"{where}: the editor holds the typed text after a reload")
                p.key("Escape", code="Escape", vk=27)
                self.assertEqual(self.stored("actions", ident), literal, f"{where}: leaving it unchanged writes nothing back")
        body = publish.build(self.store, "ABC", now="2026-10-29")["body"].decode("utf-8").replace("\\u003c", "<").replace("\\u003e", ">")
        self.assertIn(literal, body, "the published file carries the typed text")

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
                # A slow runner can drop the first blur: re-issue it until the editor box is gone, for up to 15 s.
                gone = f"!document.querySelector({row!r} + ' .ProseMirror')"
                end = time.time() + 15
                while time.time() < end and not p.js(gone):
                    p.js("(function(){var a = document.activeElement; if (a && a.classList.contains('ProseMirror')) { a.blur(); } document.body.focus();})()")
                    time.sleep(0.3)
                self.assertTrue(wait(lambda: self.stored("actions", ident) == "Saved by leaving"), f"{where}: leaving the field saves")
                p.until("!!document.querySelector('.toast [data-undo]')", f"{where}: the Undo is offered")
                p.js("document.querySelector('.toast [data-undo]').click()")
                self.assertTrue(wait(lambda: self.stored("actions", ident) == "Cut-over plan to be agreed"), f"{where}: Undo")

    def test_long_words_are_cut_on_one_line_with_an_ellipsis_and_the_open_editor_has_no_toolbar(self):
        long = " ".join(["wording"] * 22)
        with chrome() as cdp:
            p = Pg.at(self, cdp, self.s.port)
            p.ready()
            p.edit()
            ident = id_of(self.store, "Cut-over plan to be agreed")
            row = self.row("actions", ident)
            view = f"{row} {SHOWN}"
            for theme, w in self.each(p):
                where = f"{theme} {w}"
                self.open_editor(p, row)
                bar = p.js("(r => ['.rt-bar', '.rt-keys'].map(q => { const e = r.querySelector(q); return e ? getComputedStyle(e).display : 'none'; }))(document.querySelector(%s))" % json.dumps(row))
                self.assertEqual(bar, ["none", "none"], f"{where}: the open one-line editor shows no toolbar")
                self.type(p, long)
                p.key("Enter", code="Enter", vk=13)
                p.until(f"!document.querySelector({row!r} + ' .ProseMirror') && document.querySelector({view!r}) && document.querySelector({view!r}).textContent.includes('wording wording')", f"{where}: closed and drawn")
                st = p.js(f"(e => {{ const c = getComputedStyle(e); return [c.textOverflow, c.whiteSpace, c.overflowX, e.scrollWidth > e.clientWidth, e.getBoundingClientRect().height]; }})(document.querySelector({view!r}))")
                self.assertEqual(st[:4], ["ellipsis", "nowrap", "hidden", True], f"{where}: one line cut with an ellipsis")
                self.assertLess(st[4], 52, f"{where}: one line tall")
                p.js("document.querySelector('.toast [data-undo]').click()")
                self.assertTrue(wait(lambda: self.stored("actions", ident) == "Cut-over plan to be agreed"), f"{where}: Undo")
                p.until(f"document.querySelector({view!r}) && document.querySelector({view!r}).textContent.includes('Cut-over plan')", f"{where}: old words drawn")

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
            p.key("Enter", code="Enter", vk=13)
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
            p.key("Enter", code="Enter", vk=13)
            p.toast_is(f"Wording of {ident} changed.")
            self.assertEqual(self.stored("actions", ident), "")
            p.until(f"document.querySelector({row!r} + ' {SHOWN}').textContent.includes('Agree the cut-over plan')", "the title shows")


if __name__ == "__main__":
    unittest.main()
