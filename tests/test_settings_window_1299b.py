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
from test_settings_head import CLASSIC_GROUPS as GROUPS, CLASSIC_PAGES as PAGES, address, ratio, rgb

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

    def token(self, p, css):
        """What a CSS value (a token) resolves to on this page, as the browser computes it: a probe element takes it as its ground and its width."""
        return p.js("(() => { const e = document.createElement('i'); e.style.cssText = 'position:absolute;background:%s;width:%s'; document.body.appendChild(e);"
                    " const cs = getComputedStyle(e), out = {bg: cs.backgroundColor, w: cs.width}; e.remove(); return out; })()" % (css, css))

    def test_W4_each_tile_carries_its_page_class_and_each_page_has_one_icon_of_its_own(self):
        slugs = [slug for _, pages in GROUPS for slug, _, _ in pages]      # the fill per page is pinned in test_settings_window_1299 (ruling Q1)
        for w in WIDTHS:
            for mode in MODES:
                with self.subTest(width=w, mode=mode), chrome() as cdp:
                    p = self.page(cdp)
                    self.open_settings(p, w, mode)
                    got = p.js("[...document.querySelectorAll('.set-win .set-chip')].map(b => { const t = b.querySelector('.set-tile');"
                               " return {cls: t.className, svgs: t.querySelectorAll('svg').length, art: t.querySelector('svg').innerHTML}; })")
                    self.assertEqual(len(got), len(slugs))
                    for g, slug in zip(got, slugs):
                        self.assertEqual(g["cls"], f"set-tile set-tile-{slug}", slug + ": the tile carries its page's class")
                        self.assertEqual(g["svgs"], 1, slug + ": one icon in the tile")
                    self.assertEqual(len({g["art"] for g in got}), len(got), "every page has an icon of its own (no two tiles draw the same glyph)")

    def test_W4_the_window_is_eighteen_pixels_round_with_a_one_pixel_ring_a_drop_shadow_and_its_own_padding(self):
        for w in WIDTHS:
            for mode in MODES:
                with self.subTest(width=w, mode=mode), chrome() as cdp:
                    p = self.page(cdp)
                    self.open_settings(p, w, mode)
                    r = p.js("(() => { const cs = getComputedStyle(document.querySelector('.set-win')); return {radius: cs.borderTopLeftRadius, shadow: cs.boxShadow, bg: cs.backgroundColor,"
                             " pt: cs.paddingTop, pr: cs.paddingRight, pb: cs.paddingBottom, pl: cs.paddingLeft, border: cs.borderTopWidth,"
                             " card: getComputedStyle(document.querySelector('.set-win .set-cards .frame')).backgroundColor}; })()")
                    self.assertEqual(r["radius"], "18px", "the radius is the mock-up's 18px (row 1299 ruling): 12px and 14px both fail here")
                    self.assertNotIn(r["radius"], ("12px", "14px"), "neither the large-radius token nor 14")
                    ring = {"light": "rgb(233, 237, 246)", "dark": "rgb(43, 56, 80)"}[mode]      # the mock-up's --line (#e9edf6, dark #2b3850), the row 1299 ruling
                    drop = {"light": "rgba(6, 47, 58, 0.18)", "dark": "rgba(6, 47, 58, 0.18)"}[mode]      # the mock-up's 0 12px 36px rgba(6,47,58,.18) (row 1299 ruling, mock pin 20-11); dark is the same (ruling 23-11, mock-up A7:7, no dark override); was the --shadow token's own colour
                    self.assertEqual(r["shadow"], f"{ring} 0px 0px 0px 1px, {drop} 0px 12px 36px 0px", "a one pixel ring in the mock-up line colour drawn as a shadow (it takes no room), then the ruled 0 12px 36px drop shadow")
                    ground = {"light": "rgb(241, 243, 249)", "dark": "rgb(21, 31, 44)"}[mode]      # the mock-up's --win (#f1f3f9, dark #151f2c)
                    self.assertEqual(r["bg"], ground, "the window ground is the mock-up's --win in " + mode)
                    self.assertEqual(r["card"], self.token(p, "var(--surface)")["bg"], "the cards inside stay on the surface token (white in light) in " + mode)
                    self.assertNotEqual(r["card"], r["bg"], "the cards read against the window ground")
                    self.assertEqual(r["border"], "0px", "the ring is not a border")
                    self.assertEqual((r["pt"], r["pr"], r["pb"]), (self.token(p, "var(--space-4)")["w"], self.token(p, "var(--space-4)")["w"], self.token(p, "var(--space-5)")["w"]), "padding: space-4 above and right, space-5 below")
                    self.assertEqual(r["pl"], "20px", "on screen the left padding is Row 1312's 20px gutter")

    def test_W4_the_heading_is_flat_inside_the_window(self):
        for w in WIDTHS:
            with self.subTest(width=w), chrome() as cdp:
                p = self.page(cdp)
                self.open_settings(p, w)
                r = p.js("(() => { const cs = getComputedStyle(document.querySelector('.set-win > .set-head')); return {border: cs.borderTopWidth + cs.borderBottomWidth + cs.borderLeftWidth + cs.borderRightWidth,"
                         " shadow: cs.boxShadow, bg: cs.backgroundColor, pt: cs.paddingTop, pl: cs.paddingLeft, pr: cs.paddingRight}; })()")
                self.assertEqual(r["border"], "0px0px0px0px", "no border on the heading")
                self.assertEqual(r["shadow"], "none", "no shadow on the heading")
                self.assertEqual(r["bg"], "rgba(0, 0, 0, 0)", "no ground on the heading: the window is the frame")
                self.assertEqual((r["pt"], r["pl"], r["pr"]), ("0px", "0px", "0px"), "the heading has no padding above or at the sides")

    def test_W4_between_900_and_1099_the_menu_column_is_164px_and_at_1400_it_is_not(self):
        for w, want in ((900, "164px"), (1400, None)):
            with self.subTest(width=w), chrome() as cdp:
                p = self.page(cdp)
                self.open_settings(p, w)
                col = p.js("getComputedStyle(document.querySelector('.set-win')).gridTemplateColumns.split(' ')[0]")
                if want:
                    self.assertEqual(col, want, "the menu column")
                else:
                    self.assertNotEqual(col, "164px", "164px is for 900 to 1099 only")
                    self.assertEqual(col, "270px", "at 1400 the sidebar column is the mock-up's 270px (row 1299 ruling)")

    def test_W4_print_drops_the_left_gutter_padding(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_settings(p, 1400)
            self.assertEqual(p.js("getComputedStyle(document.querySelector('.set-win')).paddingLeft"), "20px")
            cdp.call("Emulation.setEmulatedMedia", {"media": "print"}, p.sid)
            p.until("getComputedStyle(document.querySelector('.set-win')).paddingLeft === '0px'", "print has no left padding")


class CardsWindow(Base):
    """The Cards file draws the Settings page it drew: no window and no tiles (those are Classic only)."""

    def test_W4_cards_has_no_window_and_no_tiles(self):
        self.rig = Rig(self, saved=self.saved)
        for w in WIDTHS:
            with self.subTest(width=w), chrome() as cdp:
                p = self.page(cdp)
                p.width(w)
                calm(p, "light")
                p.js(f"location.hash = '{address('people')}'")
                p.until("!!document.querySelector('.set-layout .set-chip[aria-current]') && !!document.querySelector('.set-cards').children.length", "Settings drew")
                self.assertEqual(p.js("document.querySelectorAll('.set-win').length"), 0, "no .set-win")
                self.assertEqual(p.js("document.querySelectorAll('.set-tile, [class*=\"set-tile-\"]').length"), 0, "no .set-tile")
                self.assertGreater(p.js("document.querySelectorAll('.set-chip').length"), 0, "the menu itself is there")


if __name__ == "__main__":
    unittest.main()
