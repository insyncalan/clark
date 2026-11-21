"""Row 1285, the ruling of 20-11 (Classic only), measured at 1400 and 900 px.
Run: python3 dev/run_tests.py test_peek_ruling_1285

3. Settings at 900: the chips are 15px, the open page is the brand colour on the tile fill (the 1401 chip), and no chip is clipped.
4. The milestone peek's tiles keep their full text: wraps at words, grows in height, no ellipsis, scrollHeight not above clientHeight.
5. Show history is a row: the word at the left, a chevron at the right, 36px high.
6. The client line is a row with a 40 x 22 switch at the right (the words are Shown to the client and Hidden from the client).
8. A Details value that is a picker carries the mock-up's .val look.
9. The chips row has 6px under it; a decision's small words are the mock-up's pill.
"""
import unittest
from unittest import mock

import _testpage
from clark import page, theme as themes

import test_peek_latest
import test_server  # noqa: F401
from test_server import chrome, wait
import test_milestone_peek_1078 as _m
import test_theme_classic_1317 as t

_B = test_peek_latest.Browser
del test_peek_latest


def classic():
    real = _testpage.html
    return mock.patch.object(_testpage, "html", lambda branding=None: page.layer_theme(real(), themes.css("prototype-2.0")))


class Peek(unittest.TestCase):
    load, fresh, refused = _B.load, _B.fresh, _B.refused
    _base_setup = _B.setUp

    def setUp(self):
        self._base_setup()
        p = classic()
        p.start()
        self.addCleanup(p.stop)

    def test_show_history_is_a_row_with_the_word_left_and_a_chevron_right(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sent, sid = self.load(cdp, width, "TUL-A-002", edit=True)
                g = cdp.js("(() => { const b = document.querySelector('#peek [data-pk-lh-btn]'), r = b.getBoundingClientRect(), w = b.querySelector('span').getBoundingClientRect(), c = b.querySelector('.pk-lh-car').getBoundingClientRect();"
                           " return {word: b.textContent.trim(), h: Math.round(r.height), wordLeft: w.left - r.left, chevRight: r.right - c.right, chevW: Math.round(c.width), full: Math.round(r.width)}; })()", sid)
                self.assertEqual(g["word"], "Show history")
                self.assertGreaterEqual(g["h"], 36, g)
                self.assertLess(g["wordLeft"], 4, g)
                self.assertLess(g["chevRight"], 4, g)
                self.assertGreater(g["chevW"], 8, g)
                self.assertGreater(g["full"], 200, "a full-width row, not a link at the right")

    def test_the_client_line_is_a_row_with_a_40_by_22_switch(self):
        for width in (1400, 900):
            for ref in ("TUL-A-002", "TUL-D-016"):
                with self.subTest(width=width, ref=ref), chrome() as cdp:
                    sent, sid = self.load(cdp, width, ref, edit=True)
                    cdp.js("(() => { const h = document.querySelector('#peek [data-pk-details]'); if (h && h.getAttribute('aria-expanded') === 'false') h.click(); })()", sid)
                    g = cdp.js("(() => { const b = document.querySelector('#peek [data-pk-client]'), s = b.querySelector('.pk-sw'), r = b.getBoundingClientRect(), x = s.getBoundingClientRect(), c = getComputedStyle(s);"
                               " return {w: Math.round(x.width), h: Math.round(x.height), right: Math.round(r.right - x.right), rowH: Math.round(r.height), bg: c.backgroundColor, words: b.textContent.trim(), on: b.getAttribute('aria-pressed')}; })()", sid)
                    self.assertEqual((g["w"], g["h"]), (40, 22), g)
                    self.assertLess(g["right"], 3, g)
                    self.assertGreaterEqual(g["rowH"], 36, g)
                    self.assertEqual(g["words"], "Shown to the client" if g["on"] == "true" else "Hidden from the client", "the labels are the approved pair")
                    self.assertNotIn("Client visible", g["words"])
                    self.assertNotIn("Client not visible", g["words"])
                    want = "Hidden from the client" if g["on"] == "true" else "Shown to the client"
                    cdp.js("document.querySelector('#peek [data-pk-client]').click()", sid)
                    self.assertTrue(wait(lambda: cdp.js("document.querySelector('#peek [data-pk-client]').textContent.trim()", sid) == want), "one click flips the pair: " + want)
                    self.assertNotIn("Client not visible", cdp.js("document.querySelector('#peek').textContent", sid), "Classic never says Client not visible")

    def test_an_empty_use_case_button_says_select_use_case_and_a_set_one_its_name(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sent, sid = self.load(cdp, width, "TUL-007", edit=True)
                cdp.js("(() => { const h = document.querySelector('#peek [data-pk-details]'); if (h && h.getAttribute('aria-expanded') === 'false') h.click(); })()", sid)
                js = "(() => { const b = document.querySelector('#peek [data-pk-pick=use_case]'); return b ? b.textContent.trim() : null; })()"
                got = cdp.js(js, sid)
                self.assertTrue(got and got.startswith("Use case "), "a set use case shows its own name: %r" % got)
                cdp.js("document.querySelector('#peek [data-pk-pick=use_case]').click()", sid)
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('[role=menu]')", sid)))
                self.assertEqual(cdp.js("document.querySelector(\"[role=menu] [data-value='']\").textContent.trim()", sid), "No use case", "the clearing entry keeps its words")
                cdp.js("document.querySelector(\"[role=menu] [data-value='']\").click()", sid)
                self.assertTrue(wait(lambda: cdp.js(js, sid) == "Select use case"), cdp.js(js, sid))

    def test_a_details_picker_has_the_mockup_val_look(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sent, sid = self.load(cdp, width, "TUL-A-002", edit=True)
                cdp.js("(() => { const h = document.querySelector('#peek [data-pk-details]'); if (h && h.getAttribute('aria-expanded') === 'false') h.click(); })()", sid)
                g = cdp.js("[...document.querySelectorAll('#peek .pk-details-body .pk-pick')].map(e => { const c = getComputedStyle(e); return [c.paddingTop, c.paddingLeft, c.marginLeft, c.borderTopLeftRadius, c.fontWeight, c.borderTopWidth]; })", sid)
                self.assertTrue(g, "the details have pickers")
                for row in g:
                    self.assertEqual(row, ["4px", "8px", "-8px", "8px", "500", "0px"])

    def test_the_chips_row_has_six_under_it_and_a_decisions_words_are_the_pill(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sent, sid = self.load(cdp, width, "TUL-D-016", edit=True)
                g = cdp.js("(() => { const row = document.querySelector('#peek .pk-chips'), s = [...document.querySelectorAll('#peek .pk-chips .pkc-sub')].map(e => { const c = getComputedStyle(e); return [e.textContent.trim(), c.fontSize, c.fontWeight, c.paddingLeft, c.borderTopLeftRadius]; });"
                           " return {mb: getComputedStyle(row).marginBottom, subs: s}; })()", sid)
                self.assertEqual(g["mb"], "6px")
                self.assertEqual([x[0] for x in g["subs"]], ["made by", "needed by"])
                for x in g["subs"]:
                    self.assertEqual(x[1:], ["11px", "700", "8px", "999px"])


class PromptsCards(unittest.TestCase):
    load, fresh, refused = _B.load, _B.fresh, _B.refused
    _base_setup = _B.setUp
    classic_on = False

    def setUp(self):
        self._base_setup()
        if self.classic_on:
            p = classic()
            p.start()
            self.addCleanup(p.stop)

    def test_the_edit_prompts_on_an_empty_decision_are_classic_only(self):
        for width in (1400, 900):
            with self.subTest(width=width, classic=self.classic_on), chrome() as cdp:
                sent, sid = self.load(cdp, width, "TUL-D-016", edit=True)
                got = cdp.js("[...document.querySelectorAll('#peek [data-pk-prompt]')].map(e => e.textContent.trim())", sid)
                if self.classic_on:
                    self.assertTrue(got, "Classic shows the prompts")
                    self.assertTrue(any(w.startswith("Add ") for w in got), got)
                else:
                    self.assertEqual(got, [], "Cards draws no prompt: its text is as on main")


class PromptsClassic(PromptsCards):
    classic_on = True


class Milestone(_m.Base):
    cur = _m.GO_LIVE
    visit_peek = _m.Fields.visit_peek

    def setUp(self):
        real = page.page_html
        p = mock.patch.object(page, "page_html", lambda *a, **k: real(*a, **({"theme": "prototype-2.0"} if not k.get("view") else {}), **k))
        p.start()
        self.addCleanup(p.stop)
        super().setUp()
        with self.store.step("dashboard", "Demo User") as st:
            st.update("milestones", self.cur, {"owner": "Alexandria Montgomery-Featherstonehaugh"})

    def test_the_tiles_keep_their_full_text_wrapped_at_words(self):
        for width in (1400, 900):
            for view in ("milestones",):
                with self.subTest(width=width, view=view), chrome() as cdp:
                    p = self.visit_peek(cdp, width=width, view=view)
                    got = p.js("[...document.querySelectorAll('#peek .pk-chips.ms .pkc')].map(e => { const v = e.querySelector('.pkc-v'), c = getComputedStyle(v);"
                               " return {k: e.dataset.row, ws: c.whiteSpace, ell: c.textOverflow, vcut: v.scrollWidth > v.clientWidth + 1, tileCut: e.scrollHeight > e.clientHeight + 1, text: v.textContent, h: e.getBoundingClientRect().height}; })")
                    self.assertEqual(len(got), 4, got)
                    for g in got:
                        self.assertNotEqual(g["ell"], "ellipsis", g)
                        self.assertEqual(g["ws"], "normal", g)
                        self.assertFalse(g["vcut"], g)
                        self.assertFalse(g["tileCut"], g)
                    owner = [g for g in got if g["k"] == "owner"][0]
                    self.assertIn("Featherstonehaugh", owner["text"], "the full name is in the tile")


    def test_the_milestone_client_line_says_shown_to_the_client_and_hidden_from_the_client(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.visit_peek(cdp, width=width, view="milestones")
                p.js("(() => { const h = document.querySelector('#peek [data-pk-details]'); if (h && h.getAttribute('aria-expanded') === 'false') h.click(); })()")
                self.assertEqual(p.js("document.querySelector('#peek [data-pk-client]').textContent.trim()"), "Shown to the client")
                p.js("document.querySelector('#peek [data-pk-client]').click()")
                p.until("document.querySelector('#peek [data-pk-client]').textContent.trim() === 'Hidden from the client'", "the off word is the approved one")
                self.assertNotIn("Client not visible", p.js("document.querySelector('#peek').textContent"))
                p.js("document.querySelector('#peek [data-pk-client]').click()")           # back on for the next width
                p.until("document.querySelector('#peek [data-pk-client]').textContent.trim() === 'Shown to the client'", "on again")


class Settings900(unittest.TestCase):
    setUpClass = classmethod(t.RealSettings.setUpClass.__func__)
    tearDownClass = classmethod(t.RealSettings.tearDownClass.__func__)
    serve, look = t.RealSettings.serve, t.RealSettings.look

    def test_the_chips_at_900_are_the_1401_chip_and_not_clipped(self):
        s = self.serve(t.NAME)
        for scheme in ("light", "dark"):
            with self.subTest(scheme=scheme), chrome() as cdp:
                self.look(cdp, s.port, 900, scheme)
                sid = t.page_target(cdp)
                g = cdp.js("(() => { const tok = (v) => { const i = document.createElement('i'); i.style.color = v; document.body.append(i); const c = getComputedStyle(i).color; i.remove(); return c; };"
                           " const cs = [...document.querySelectorAll('.set-chip')], cur = document.querySelector('.set-chip[aria-current]'), k = getComputedStyle(cur);"
                           " const tile = document.createElement('i'); tile.style.backgroundColor = 'var(--tile-on-bg)'; document.body.append(tile); const tb = getComputedStyle(tile).backgroundColor; tile.remove();"
                           " const dk = document.createElement('i'); dk.style.backgroundColor = 'var(--brand-blue-tint)'; document.body.append(dk); const db = getComputedStyle(dk).backgroundColor; dk.remove();"
                           " return {n: cs.length, sizes: [...new Set(cs.map(e => getComputedStyle(e).fontSize))], cut: cs.filter(e => e.scrollWidth > e.clientWidth + 1 || e.scrollHeight > e.clientHeight + 1).map(e => e.textContent), bg: k.backgroundColor, fg: k.color, tb, tf: tok('var(--tile-on-fg)'), db, df: tok('var(--status-blue-text)')}; })()", sid)
                self.assertGreater(g["n"], 5)
                self.assertEqual(g["sizes"], ["15px"], g)
                self.assertEqual(g["cut"], [], g)
                # light: the Work items tile tokens (the 1285 ruling); dark: the row 1401 chip keeps its own dark tokens (test_settings_sidebar_1401)
                want = (g["tb"], g["tf"]) if scheme == "light" else (g["db"], g["df"])
                self.assertEqual((g["bg"], g["fg"]), want, g)
                if scheme == "light":
                    self.assertEqual(g["tb"], "rgb(236, 233, 251)")
                    self.assertEqual(g["tf"], "rgb(91, 71, 216)")


if __name__ == "__main__":
    unittest.main()
