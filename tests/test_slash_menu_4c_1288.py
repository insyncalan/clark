"""Row 1288 (slice "/" menu 4C): the Classic "/" menu has a filter box on top and an "Ask AI..." line at the bottom (computed style, 1400 and 900).

Run: python3 dev/run_tests.py test_slash_menu_4c_1288
Values are the ticket's (the measured values comment): panel radius 12, padding 4, min-width 180; row padding 4px 10px, gap 10, 13.5px, radius 6;
filter box margin 1px 3px 4px, padding 5px 9px, 1px border, radius 8, 13px. "Ask AI..." opens the same AI menu as the right-click.
Cards (no #theme layer) keeps the old menu: no filter box, no Ask line. Chrome is required: the test fails, never skips, without it.
"""
import json
import unittest

import _rich_page as rp  # noqa: E402
from clark import theme  # noqa: E402
from test_server import chrome  # noqa: E402

CSS = theme.css("prototype-2.0")
WIDTHS = (1400, 900)
BOX = ("(b => { const c = getComputedStyle(b); return {r: c.borderTopLeftRadius, p: c.paddingTop + ' ' + c.paddingRight + ' ' + c.paddingBottom + ' ' + c.paddingLeft,"
       " m: c.marginTop + ' ' + c.marginRight + ' ' + c.marginBottom + ' ' + c.marginLeft, f: c.fontSize, g: c.columnGap, w: c.minWidth, bw: c.borderTopWidth}; })(%s)")


def layer(h, on):
    h.ev("var o = document.getElementById('theme'); if (o) o.remove(); true")
    if on:
        h.ev(f"var s = document.createElement('style'); s.id = 'theme'; s.textContent = {json.dumps(CSS)}; document.head.appendChild(s); true")


class Slash(unittest.TestCase):
    def open(self, h, classic, w=1400, value="<p>Some words here</p>"):
        layer(h, classic)
        h.resize(w)
        h.mount(value, ai="current")
        h.key("End", 0, "End", 35)
        h.type("/")
        self.assertTrue(h.until("!!document.querySelector('.rt-slash')"))

    def test_classic_menu_has_the_filter_box_first_and_ask_ai_last_with_the_ticket_values(self):
        with rp.Harness(chrome) as h:
            for w in WIDTHS:
                self.open(h, True, w, "")
                where = f"{w}"
                kids = h.ev("[...document.querySelector('.rt-slash').children].map(n => n.className + '|' + n.textContent.trim())")
                self.assertTrue(kids[0].startswith("rt-slash-filter"), f"{where}: {kids}")
                self.assertEqual(kids[-1], "rt-opt rt-ask|Ask AI…", f"{where}: {kids}")
                self.assertEqual(h.ev("document.querySelectorAll('.rt-slash [role=option]').length"), 9, where)   # 8 blocks + the Ask line
                panel = h.ev(BOX % "document.querySelector('.rt-slash')")
                self.assertEqual((panel["r"], panel["p"], panel["bw"]), ("12px", "4px 4px 4px 4px", "1px"), where)
                self.assertGreaterEqual(float(panel["w"][:-2]), 180, where)
                box = h.ev(BOX % "document.querySelector('.rt-slash-filter')")
                self.assertEqual((box["r"], box["p"], box["m"], box["f"], box["bw"]), ("8px", "5px 9px 5px 9px", "1px 3px 4px 3px", "13px", "1px"), f"{where}: {box}")
                row = h.ev(BOX % "document.querySelector('.rt-slash .rt-opt')")
                self.assertEqual((row["r"], row["p"], row["f"], row["g"]), ("6px", "4px 10px 4px 10px", "13.5px", "10px"), f"{where}: {row}")
                ask = h.ev(BOX % "document.querySelector('.rt-slash .rt-ask')")
                self.assertEqual((ask["r"], ask["p"], ask["f"]), ("6px", "4px 10px 4px 10px", "13.5px"), f"{where}: {ask}")

    def test_cards_keeps_the_old_menu(self):
        with rp.Harness(chrome) as h:
            self.open(h, False, 1400, "")
            self.assertFalse(h.ev("!!document.querySelector('.rt-slash-filter')"))
            self.assertFalse(h.ev("!!document.querySelector('.rt-slash .rt-ask')"))
            self.assertEqual(h.ev("document.querySelectorAll('.rt-slash [role=option]').length"), 8)

    def test_the_filter_box_shows_what_was_typed_and_the_rows_narrow(self):
        with rp.Harness(chrome) as h:
            self.open(h, True, 1400, "")
            self.assertEqual(h.ev("document.querySelector('.rt-slash-filter').textContent"), "")
            self.assertEqual(h.ev("document.querySelector('.rt-slash-filter').getAttribute('data-ph')"), "Filter blocks\u2026")   # the ruled placeholder, not "Filter"
            self.assertEqual(h.ev("getComputedStyle(document.querySelector('.rt-slash-filter'), '::before').content"), '"Filter blocks\u2026"')
            h.type("head")
            self.assertTrue(h.until("document.querySelectorAll('.rt-slash [role=option]').length === 4"))   # 3 headings + Ask
            self.assertEqual(h.ev("document.querySelector('.rt-slash-filter').textContent"), "head")

    def test_ask_ai_opens_the_same_menu_as_the_right_click_and_closes_the_slash_menu(self):
        with rp.Harness(chrome) as h:
            self.open(h, True, 1400, "<p>Some words here</p><p></p>")
            h.ev("document.querySelector('.rt-slash .rt-ask').click(); true")
            self.assertTrue(h.until("!!document.querySelector('.rt-ai [data-ai-menu]')"))
            self.assertFalse(h.ev("!!document.querySelector('.rt-slash')"))
            self.assertEqual(h.ev("document.querySelector('.rt-ai [data-ai-menu]').getAttribute('aria-label')"), "Draft with AI")
            self.assertTrue(h.until("!!document.activeElement.closest('[data-ai-menu]')"))                  # the menu has the focus, so Esc closes the menu only
            h.key("Escape", 0, "Escape", 27)
            self.assertTrue(h.until("!document.querySelector('.rt-ai')"))
            self.assertEqual(h.ev("window.ended"), 0)

    def test_the_keyboard_reaches_ask_ai_with_arrow_up_and_enter(self):
        with rp.Harness(chrome) as h:
            self.open(h, True, 1400, "<p>Some words here</p><p></p>")
            h.key("ArrowUp", 0, "ArrowUp", 38)
            self.assertTrue(h.until("document.querySelector('.rt-slash .rt-ask').classList.contains('on')"))
            h.key("Enter", 0, "Enter", 13)
            self.assertTrue(h.until("!!document.querySelector('.rt-ai [data-ai-menu]')"))

    def test_ask_ai_sends_the_text_around_the_slash_and_accept_replaces_the_slash_words(self):    # kills s.to in the text line and to: s.from in setAiAt
        with rp.Harness(chrome) as h:
            for w in WIDTHS:
                layer(h, True)
                h.resize(w)
                h.ev("window.sent = []; window.fetch = (url, init) => { const ok = (b) => Promise.resolve({ status: 200, json: () => Promise.resolve(b) });"
                     " if (String(url).includes('/api/ai/status')) return ok({ ok: true, state: 'ready', line: '' });"
                     " if (String(url).includes('/api/ai/suggest')) { window.sent.push(JSON.parse(init.body).text); return ok({ ok: true, html: '<p>Fresh words</p>', notes: [], changes: [] }); }"
                     " return ok({ ok: true }); }; true")
                h.mount("<p>Alpha beta</p><p></p><p>Omega tail</p>", ai="current")
                h.key("ArrowUp", 0, "ArrowUp", 38)
                h.type("/head")
                self.assertTrue(h.until("!!document.querySelector('.rt-slash .rt-ask')"), w)
                h.ev("document.querySelector('.rt-slash .rt-ask').click(); true")
                self.assertTrue(h.until("!!document.querySelector('.rt-ai [data-ai-option]')"), w)
                h.ev("document.querySelector('.rt-ai [data-ai-option]').click(); true")
                self.assertTrue(h.until("[...document.querySelectorAll('.rt-ai button')].some(b => b.textContent.trim() === 'Accept')"), w)
                self.assertEqual(h.ev("window.sent"), ["Alpha beta\n\n\nOmega tail"], f"{w}: the text sent is the words before and after the '/' words, not them")
                h.ev("[...document.querySelectorAll('.rt-ai button')].find(b => b.textContent.trim() === 'Accept').click(); true")
                self.assertTrue(h.until("document.querySelector('.ProseMirror').textContent.includes('Fresh words')"), w)
                self.assertEqual(h.ev("[...document.querySelectorAll('.ProseMirror p')].map(p => p.textContent)"), ["Alpha beta", "Fresh words", "Omega tail"], f"{w}: Accept replaces the '/' words")

    def test_no_ask_line_without_an_ai_place(self):
        with rp.Harness(chrome) as h:
            layer(h, True)
            h.mount("", ai=None)
            h.type("/")
            self.assertTrue(h.until("!!document.querySelector('.rt-slash')"))
            self.assertTrue(h.until("!!document.querySelector('.rt-slash-filter')"))
            self.assertFalse(h.ev("!!document.querySelector('.rt-slash .rt-ask')"))


if __name__ == "__main__":
    unittest.main()
