"""Row 1269, slice B, hostile checks: the served page drawn in a real browser under each Theme, 1400 and 900 px, light and dark.

Run: python3 dev/run_tests.py test_theme_host_1269b
Headless Chrome through the shared harness, the committed page with fictional demo data. Cards is the page as it was (no Theme
block); Classic layers the prototype-2.0 Theme block. Values are read from the drawn page, never written down from memory, except
the dark gradient stops of the ruling (Whisper, rows 1310 and 1311).
"""
import re
import tempfile
import unittest
from pathlib import Path

from _paths import ROOT  # noqa: F401
import _testpage as testpage  # noqa: F401
from _demo import DemoStore
from test_report_editor import Base, Pg, tearDownModule  # noqa: F401
from test_server import chrome

from clark import page, theme

NAME = "prototype-2.0"
SIZES = (1400, 900)
MODES = ("light", "dark")
GRAD_DARK = ("rgb(15, 21, 35)", "rgb(18, 26, 42)")       # Whisper (rows 1310, 1311)


def hex_rgb(h):
    return "rgb(%d, %d, %d)" % tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


class Host(Base):
    theme = None
    brand = page.NO_BRAND

    def setUp(self):
        super().setUp()
        self.s.close()
        from _real_server import real_server
        self.s = real_server(self.store.path, self.store.data_for, page_html=lambda: page.page_html(branding=self.brand, theme=self.theme), seam=self.seam)
        self.addCleanup(self.s.close)

    hash_ = "#dashboard&p=ABC"

    def look(self, cdp, width, mode, js):
        p = Pg.at(self, cdp, self.s.port, self.hash_)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
        p.js(f"document.documentElement.dataset.theme = '{mode}'")
        p.until("document.querySelectorAll('.sec, .cover').length > 0 || !!document.querySelector('#no-sections')", "the page drew")
        return p.js(js)

    def every(self, js):
        got = {}
        with chrome() as cdp:
            for w in SIZES:
                for m in MODES:
                    got[(w, m)] = self.look(cdp, w, m, js)
        return got


BODY = "(() => { const s = getComputedStyle(document.body); return [s.backgroundImage, s.backgroundColor]; })()"
SEC = ("(() => [...document.querySelectorAll('.secs > .sec')].map((e) => { const s = getComputedStyle(e); "
       "return [s.borderLeftWidth, s.borderTopWidth, s.boxShadow, s.borderLeftStyle, e.classList.contains('slot-right')]; }))()")
NUM = "getComputedStyle(document.querySelector('.secs .sec-head'), '::before').content"
COVER = "(() => { const c = document.querySelector('.cover'); if (!c) return null; const s = getComputedStyle(c); return [s.display, s.backgroundColor]; })()"
OVERFLOW = "[document.documentElement.scrollWidth, document.documentElement.clientWidth]"


class Classic(Host):
    theme = NAME

    def test_1_one_theme_block_between_tokens_and_brand_in_the_drawn_page(self):
        html = page.page_html(branding=self.brand, theme=NAME)
        ids = re.findall(r'<style\b[^>]*?\bid="([^"]*)"', html)
        self.assertEqual(ids.count("theme"), 1)
        self.assertLess(ids.index("brand-demo"), ids.index("theme"))
        with chrome() as cdp:
            p = Pg.at(self, cdp, self.s.port, "#dashboard&p=ABC")
            p.ready()
            self.assertEqual(p.js("document.querySelectorAll('style#theme').length"), 1)

    def test_2_the_page_ground_is_the_theme_gradient_in_light_and_dark(self):
        got = self.every(BODY)
        for (w, m), (img, _c) in got.items():
            self.assertIn("linear-gradient", img, f"{w} {m}: a gradient ground")
        light = re.findall(r"rgb\([^)]*\)", got[(1400, "light")][0])
        self.assertEqual(light, [hex_rgb("#fcfdfe"), hex_rgb("#f7f9fc")])

    def test_3_the_dark_gradient_is_the_ruled_one(self):
        got = self.every(BODY)
        for w in SIZES:
            self.assertEqual(re.findall(r"rgb\([^)]*\)", got[(w, "dark")][0]), list(GRAD_DARK), f"{w}: dark ruling e")

    def test_4_a_section_has_the_gutter_rule_and_no_card_in_every_size_and_mode(self):
        for (w, m), rows in self.every(SEC).items():
            self.assertTrue(rows, f"{w} {m}: sections")
            row = -1
            for i, (lw, tw, shadow, style, right) in enumerate(rows):
                if w == 900 or not right:      # row 1335: from 901 px the two halves of a pair share one row (one band colour); stacked at 900, each section is its own row
                    row += 1
                want = ("0px", "0px", "none") if row % 2 == 0 else ("2px", "0px", "solid")      # row 1311: the 1st, 3rd... rows are bands with no gutter rule
                self.assertEqual((lw, tw, style), want, f"{w} {m} section {i + 1}")
                self.assertEqual(shadow, "none", f"{w} {m}")

    def test_4b_the_two_halves_of_a_pair_share_one_band_colour_and_rows_alternate(self):
        js = ("(() => [...document.querySelectorAll('.secs > .sec:not(.is-hidden)')].map((e) => [getComputedStyle(e).backgroundColor, e.classList.contains('slot-right'), e.dataset.band || null]))()")
        for (w, m), rows in self.every(js).items():
            seen_pair, prev_row = False, None
            for i, (bg, right, band) in enumerate(rows):
                if right and w == 1400:
                    seen_pair = True
                    self.assertEqual(bg, rows[i - 1][0], f"{w} {m}: the right half has the left half's colour (section {i + 1})")
                    self.assertEqual(band, rows[i - 1][2], f"{w} {m}: one data-band per row")
                elif prev_row is not None and w == 1400:
                    self.assertNotEqual(bg == "rgba(0, 0, 0, 0)", prev_row, f"{w} {m}: the next row has the other colour (section {i + 1})")
                if not right or w == 900:
                    prev_row = bg == "rgba(0, 0, 0, 0)"
            if w == 1400:
                self.assertTrue(seen_pair, "the demo report has a pair of half-width sections")

    def test_5_sections_are_numbered_and_nothing_overflows_sideways(self):
        for (w, m), c in self.every(NUM).items():
            self.assertRegex(c, r"counter\(secn\)|^\"?\d+", f"{w} {m}: a section number")
        for (w, m), (sw, cw) in self.every(OVERFLOW).items():
            self.assertLessEqual(sw, cw, f"{w} {m}: no sideways scroll")

    def test_6_a_brand_that_sets_no_gradient_wins_over_the_theme(self):
        d = Path(tempfile.mkdtemp())
        (d / "tokens.css").write_text(":root, :root[data-theme=dark] { --page-grad: none; }", encoding="utf-8")
        self.brand = d
        got = self.every(BODY)
        for (w, m), (img, _c) in got.items():
            self.assertEqual(img, "none", f"{w} {m}: Brand over Theme")


class Cards(Host):
    theme = None

    def test_8_cards_sections_carry_no_band_mark(self):
        js = "(() => [document.querySelectorAll('.secs > .sec').length, document.querySelectorAll('[data-band]').length])()"      # row 1335: Classic only
        for (w, m), (n, marked) in self.every(js).items():
            self.assertGreater(n, 0, f"{w} {m}: sections")
            self.assertEqual(marked, 0, f"{w} {m}: Cards DOM has no data-band")

    def test_7_cards_is_the_page_as_it_was_drawn(self):
        self.assertNotIn('id="theme"', page.page_html(branding=self.brand, theme=None))
        for (w, m), (img, _c) in self.every(BODY).items():
            self.assertEqual(img, "none", f"{w} {m}: no gradient ground in Cards")
        for (w, m), rows in self.every(SEC).items():
            for lw, tw, shadow, style, _right in rows:
                self.assertNotEqual((lw, style), ("2px", "solid"), f"{w} {m}: no gutter rule in Cards")
            self.assertEqual(self.every_one(OVERFLOW, w, m)[0] <= self.every_one(OVERFLOW, w, m)[1], True)

    def every_one(self, js, w, m):
        with chrome() as cdp:
            return self.look(cdp, w, m, js)


class Dropped(Host):
    def test_8_the_cover_band_is_dropped_in_classic_only(self):
        """Ruling: the cover band is dropped in Classic only. The Theme must carry a rule that drops .cover; Cards must not."""
        rules = theme.css(NAME)
        drop = re.search(r"(^|\})\s*[^{}]*\.cover\b[^{}]*\{[^}]*display:\s*none", rules)
        self.assertTrue(drop, "the Classic Theme CSS has no rule that drops .cover")
        self.assertNotIn('html[data-mode="view"] .cover', page.page_html(branding=self.brand, theme=None))      # the committed look has its own .cover::after rule, so only the Theme's view-mode rule is looked for


if __name__ == "__main__":
    unittest.main()
