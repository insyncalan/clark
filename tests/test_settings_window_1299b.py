"""Row 1299 slice 1b, part W4: the Settings page as a window (rounded, on its own ground), the sidebar with an icon tile on every entry, in a real browser
at 1400 and 900 px, light and dark. Run: python3 dev/run_tests.py test_settings_window_1299b

What is asserted: `.set-win` holds the sidebar (`.set-bar`) and the cards and is rounded, on its own ground, no wider than the screen, and it does not clip
(no overflow hidden, auto or clip: a focus ring or a sticky sidebar must survive); every sidebar entry has one `.set-tile` that is hidden from screen readers
(the entry's words are read once) and draws a glyph; the entry's words are unchanged (the tile has no text); the open page's entry has aria-current="page";
the sidebar stays under the top bar when the page scrolls; the glyph is 3:1 on its tile in light and dark (tokens, not fixed colours); the first and the last
entry keep room for their focus ring inside the sidebar. Not in this part (later parts of the same slice, and the regrouped menu of slice 1a): Back and Forward, the Affects label, the project tabs.
Widths 1400 and 900 only. Chrome is required: these tests fail, never skip, without it.
"""
import unittest

from clark import page, theme
import _testpage as testpage
from test_publish_dialog import Base
from test_publish_route import Rig
from test_server import chrome
from test_settings_bar import calm
from test_settings_head import PAGES, address, ratio, rgb

WIDTHS = (1400, 900)
MODES = ("light", "dark")
LAID = "!!document.querySelector('.set-win .set-nav .set-chip[aria-current]') && !!document.querySelector('.set-win .set-cards').children.length"


class Window(Base):
    """Under the Classic theme layer: the window and the tiles are Classic only (Cards draws the Settings page it drew, pinned by its own tests)."""

    def setUp(self):
        css = theme.css("prototype-2.0")
        self.rig = Rig(self, saved=self.saved, page_html=lambda: page.layer_theme(testpage.html(), css))

    def open_settings(self, p, w, mode="light", page="people"):
        p.width(w)
        calm(p, mode)
        p.js(f"location.hash = '{address(page)}'")
        p.until(LAID, "Settings drew inside its window with a marked entry")

    def test_W4_the_sidebar_and_the_cards_sit_in_one_rounded_window_on_its_own_ground(self):
        for w in WIDTHS:
            for mode in MODES:
                with self.subTest(width=w, mode=mode), chrome() as cdp:
                    p = self.page(cdp)
                    self.open_settings(p, w, mode)
                    self.assertTrue(p.js("!!document.querySelector('.set-win .set-bar') && !!document.querySelector('.set-win .set-cards')"), "sidebar and cards are in .set-win")
                    r = p.js("(() => { const e = document.querySelector('.set-win'), b = e.getBoundingClientRect(), cs = getComputedStyle(e);"
                             " return {radius: parseFloat(cs.borderTopLeftRadius), w: b.width, bg: cs.backgroundColor, ox: cs.overflowX, oy: cs.overflowY}; })()")
                    self.assertGreaterEqual(r["radius"], 8, "the window has rounded corners")
                    self.assertLessEqual(r["w"], w, "the window fits the width")
                    self.assertNotEqual(r["bg"], "rgba(0, 0, 0, 0)", "the window has its own ground")
                    self.assertEqual((r["ox"], r["oy"]), ("visible", "visible"), "the window clips nothing (a sticky sidebar and a focus ring need it)")
                    self.assertTrue(p.js("document.documentElement.scrollWidth <= window.innerWidth"), "no sideways scroll")

    def test_W4_every_sidebar_entry_has_a_hidden_icon_tile_with_a_glyph_and_its_words_are_unchanged(self):
        for w in WIDTHS:
            with self.subTest(width=w), chrome() as cdp:
                p = self.page(cdp)
                self.open_settings(p, w)
                got = p.js("[...document.querySelectorAll('.set-win .set-nav .set-chip')].map(b => ({name: b.textContent, tiles: b.querySelectorAll('.set-tile').length,"
                           " hidden: (b.querySelector('.set-tile') || document.body).getAttribute('aria-hidden'), shapes: b.querySelectorAll('.set-tile svg *').length,"
                           " tileText: (b.querySelector('.set-tile') || {}).textContent}))")
                self.assertEqual([g["name"] for g in got], [name for _, name, _ in PAGES], "one entry per page, the words unchanged (the tile adds none)")
                for g in got:
                    self.assertEqual(g["tiles"], 1, g["name"] + ": one tile")
                    self.assertEqual(g["hidden"], "true", g["name"] + ": the tile is hidden from screen readers, so the name is read once")
                    self.assertGreater(g["shapes"], 0, g["name"] + ": the tile draws a glyph")
                    self.assertEqual(g["tileText"], "", g["name"] + ": the tile has no words")

    def test_W4_the_open_page_is_the_one_entry_marked_current(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_settings(p, 1400, page="backups")
            self.assertEqual(p.js("[...document.querySelectorAll('.set-win .set-chip[aria-current]')].map(b => b.textContent + '=' + b.getAttribute('aria-current')).join()"), "Backups=page")

    def test_W4_the_sidebar_stays_under_the_top_bar_when_the_page_scrolls(self):
        for w in WIDTHS:
            for mode in MODES:
                with self.subTest(width=w, mode=mode), chrome() as cdp:
                    p = self.page(cdp)
                    self.open_settings(p, w, mode, page="version")
                    self.assertEqual(p.js("getComputedStyle(document.querySelector('.set-win .set-bar')).position"), "sticky")
                    p.js("(() => { const s = new CSSStyleSheet(); s.replaceSync('.set-cards { min-height: 4000px; }'); document.adoptedStyleSheets = [...document.adoptedStyleSheets, s]; })()")      # a constructed sheet survives a redraw of the cards (a node or a style="" attribute on them does not) and the page's policy allows it (a <style> element it blocks: style-src-elem 'self'); the height goes on the cards, not the window: the window is a grid and would stretch the heading row instead
                    p.until("document.documentElement.scrollHeight > 3000", "the page grew")
                    p.js("window.dispatchEvent(new Event('wheel'))")      # the router holds a new screen at the top for up to 120 frames until the person scrolls (router.js restore): a wheel ends that hold, as a person's would
                    p.js("window.scrollTo({top: 1500, behavior: 'instant'})")
                    p.until("window.scrollY > 1000", "the page scrolled (scrollY %s, height %s)" % (p.js("window.scrollY"), p.js("document.documentElement.scrollHeight")))
                    p.settled("the scroll finished")
                    gap = p.js("document.querySelector('.set-win .set-bar').getBoundingClientRect().top - document.querySelector('.top').getBoundingClientRect().bottom")
                    self.assertLess(abs(gap), 2, "the sidebar holds under the top bar (gap %s)" % gap)

    def test_W4_the_glyph_is_three_to_one_on_its_tile_in_light_and_dark(self):
        for w in WIDTHS:
            for mode in MODES:
                with self.subTest(width=w, mode=mode), chrome() as cdp:
                    p = self.page(cdp)
                    self.open_settings(p, w, mode)
                    got = p.js("[...document.querySelectorAll('.set-win .set-chip')].map(b => { const t = b.querySelector('.set-tile'), cs = getComputedStyle(t);"
                               " return {name: b.textContent, fill: cs.backgroundColor, glyph: getComputedStyle(t.querySelector('svg')).color}; })")
                    self.assertEqual(len(got), len(PAGES))
                    for g in got:
                        self.assertNotEqual(g["fill"], "rgba(0, 0, 0, 0)", g["name"] + ": the tile has a fill")
                        self.assertGreaterEqual(ratio(rgb(g["glyph"]), rgb(g["fill"])), 3.0, "%s: glyph %s on tile %s in %s" % (g["name"], g["glyph"], g["fill"], mode))

    def test_W4_the_first_and_last_entries_keep_room_for_their_focus_ring_inside_the_sidebar(self):
        for w in WIDTHS:
            for mode in MODES:
                with self.subTest(width=w, mode=mode), chrome() as cdp:
                    p = self.page(cdp)
                    self.open_settings(p, w, mode)
                    r = p.js("(() => { const bar = document.querySelector('.set-win .set-bar'), c = [...bar.querySelectorAll('.set-chip')], a = bar.getBoundingClientRect(),"
                             " f = c[0].getBoundingClientRect(), l = c[c.length - 1].getBoundingClientRect();"
                             " return {left: f.left - a.left, top: f.top - a.top, right: a.right - f.right, rightL: a.right - l.right}; })()")
                    ring = 4      # the ring is 2 px wide at an offset of 2 px (shell.css .set-chip:focus-visible)
                    self.assertGreaterEqual(r["left"], ring, "room at the left of the first entry for the ring")
                    self.assertGreaterEqual(r["top"], ring, "room above the first entry for the ring")
                    self.assertGreaterEqual(r["right"], ring, "room at the right of the first entry for the ring")
                    self.assertGreaterEqual(r["rightL"], ring, "room at the right of the last entry for the ring")


if __name__ == "__main__":
    unittest.main()
