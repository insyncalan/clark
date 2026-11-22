"""Row 1299 (ticket DoD3 to DoD6), slice 1b: the Settings window, the sidebar column, the sidebar row with its icon tile, and the tile fill, in a real browser at
1400 and 900 px, light and dark. Run: python3 dev/run_tests.py test_settings_window_1299

These four tests carry the names the ticket gives its DoD3 to DoD6. They measure the computed style, one thing each; the longer W4 tests of
test_settings_window_1299b stay as they are.
Pinned: the tile is 26px, radius 7px, glyph 16px (mock-up FINAL-settings-A7.html:13 .ti; ruling, ticket AP5 and DoD5). NOT pinned, open (ticket Open question 1):
the mock-up row (padding 5px 8px, radius 9px) is not built, the row is as shell.css draws it; the tile fill is
per group today and the ticket asks per page (colour values not given).
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


class WindowDoD(Base):
    """Under the Classic theme layer (the window and the tiles are Classic only)."""

    def setUp(self):
        css = theme.css("prototype-2.0")
        self.rig = Rig(self, saved=self.saved, page_html=lambda: page.layer_theme(testpage.html(), css))

    def open_settings(self, p, w, mode="light", page="people"):
        p.width(w)
        calm(p, mode)
        p.js(f"location.hash = '{address(page)}'")
        p.until(LAID, "Settings drew inside its window with a marked entry")

    def test_window_ring_shadow_and_ground_light_and_dark(self):
        ring = {"light": "rgb(233, 237, 246)", "dark": "rgb(43, 56, 80)"}      # the mock-up's --line (#e9edf6, dark #2b3850)
        drop = {"light": "rgba(6, 47, 58, 0.18)", "dark": "rgba(0, 0, 0, 0.6)"}      # 0 12px 36px rgba(6,47,58,.18); dark keeps the --shadow token's colour
        ground = {"light": "rgb(241, 243, 249)", "dark": "rgb(21, 31, 44)"}      # the mock-up's --win (#f1f3f9, dark #151f2c)
        for w in WIDTHS:
            for mode in MODES:
                with self.subTest(width=w, mode=mode), chrome() as cdp:
                    p = self.page(cdp)
                    self.open_settings(p, w, mode)
                    r = p.js("(() => { const cs = getComputedStyle(document.querySelector('.set-win')); return {radius: cs.borderTopLeftRadius, shadow: cs.boxShadow, bg: cs.backgroundColor,"
                             " border: cs.borderTopWidth, card: getComputedStyle(document.querySelector('.set-win .set-cards .frame')).backgroundColor}; })()")
                    self.assertEqual(r["radius"], "18px")
                    self.assertEqual(r["shadow"], f"{ring[mode]} 0px 0px 0px 1px, {drop[mode]} 0px 12px 36px 0px", "1px ring in the line colour, then the drop shadow, in " + mode)
                    self.assertEqual(r["bg"], ground[mode], "the window ground in " + mode)
                    self.assertEqual(r["border"], "0px", "the ring is a shadow, not a border")
                    self.assertNotEqual(r["card"], r["bg"], "the cards (surface colour) read against the ground in " + mode)

    def test_sidebar_column_270_and_164(self):
        for w, want in ((1400, "270px"), (900, "164px")):
            for mode in MODES:
                with self.subTest(width=w, mode=mode), chrome() as cdp:
                    p = self.page(cdp)
                    self.open_settings(p, w, mode)
                    self.assertEqual(p.js("getComputedStyle(document.querySelector('.set-win')).gridTemplateColumns.split(' ')[0]"), want, "the sidebar column")
                    self.assertAlmostEqual(p.js("document.querySelector('.set-win .set-bar').getBoundingClientRect().width"), float(want[:-2]), delta=1, msg="the sidebar box fills its column")

    def test_sidebar_row_and_icon_tile_size(self):
        for w in WIDTHS:
            with self.subTest(width=w), chrome() as cdp:
                p = self.page(cdp)
                self.open_settings(p, w)
                got = p.js("[...document.querySelectorAll('.set-win .set-chip')].map(b => { const t = b.querySelector('.set-tile'), tb = t.getBoundingClientRect(), bb = b.getBoundingClientRect(),"
                           " cs = getComputedStyle(t), g = t.querySelector('svg').getBoundingClientRect();"
                           " return {name: b.textContent, w: tb.width, h: tb.height, radius: cs.borderTopLeftRadius, glyph: [g.width, g.height], rowH: bb.height, inside: tb.top >= bb.top && tb.bottom <= bb.bottom,"
                           " mid: Math.abs((tb.top + tb.bottom) / 2 - (bb.top + bb.bottom) / 2)}; })")
                self.assertEqual(len(got), len(PAGES))
                for g in got:
                    self.assertEqual((g["w"], g["h"]), (26, 26), g["name"] + ": the tile is 26px by 26px (mock-up FINAL-settings-A7.html:13 .ti, ticket AP5 and DoD5)")
                    self.assertEqual(g["radius"], "7px", g["name"] + ": tile corners")
                    self.assertEqual(g["glyph"], [16, 16], g["name"] + ": glyph 16px, as the mock-up's .ti svg")
                    self.assertTrue(g["inside"], g["name"] + ": the tile sits inside its row")
                    self.assertLess(g["mid"], 1, g["name"] + ": the tile is centred in the row")

    def test_tile_fill_per_page_holds_contrast_3_to_1(self):
        for w in WIDTHS:
            for mode in MODES:
                with self.subTest(width=w, mode=mode), chrome() as cdp:
                    p = self.page(cdp)
                    self.open_settings(p, w, mode)
                    got = p.js("[...document.querySelectorAll('.set-win .set-chip')].map(b => { const t = b.querySelector('.set-tile');"
                               " return {name: b.textContent, fill: getComputedStyle(t).backgroundColor, glyph: getComputedStyle(t.querySelector('svg')).color}; })")
                    self.assertEqual([g["name"] for g in got], [name for _, name, _ in PAGES], "one tile per page")
                    for g in got:
                        self.assertNotEqual(g["fill"], "rgba(0, 0, 0, 0)", g["name"] + ": the tile has a fill")
                        self.assertNotEqual(g["glyph"], g["fill"], g["name"] + ": the glyph is not the fill colour")
                        self.assertGreaterEqual(ratio(rgb(g["glyph"]), rgb(g["fill"])), 3.0, "%s: glyph %s on fill %s in %s" % (g["name"], g["glyph"], g["fill"], mode))


if __name__ == "__main__":
    unittest.main()
