"""A-D1 page side: the report's cover band (name, WEEKLY REPORT, week ending, for <client>), in a real browser.

Run: python3 dev/run_tests.py test_cover_band
Served page (View) and the published file, at 1400 and 900 px, light and dark. Fictional data.
"""
import base64
import json
import shutil
import struct
import tempfile
import zlib
import unittest
from datetime import date, timedelta
from pathlib import Path

from _demo import USER
from test_glance_page import Published, Setup
from test_report_editor import tearDownModule  # noqa: F401
from test_server import chrome

BAND = """(() => {
  const c = document.querySelector('header.cover'); if (!c) return null;
  const h = c.querySelector('h1'), line = c.querySelector('.cover-line');
  const f = document.querySelector('.frame').getBoundingClientRect(), r = c.getBoundingClientRect();
  return {name: h.textContent, line: line.textContent, kind: c.querySelector('.cover-kind').textContent,
          bg: getComputedStyle(c).backgroundColor, top: r.top - f.top, left: r.left - f.left, right: f.right - r.right,
          h1count: document.querySelectorAll('h1').length, wide: document.documentElement.scrollWidth <= window.innerWidth,
          fg: getComputedStyle(h).color, crumbs: document.querySelectorAll('.report .crumbs').length};
})()"""
LUM = """(() => { const rgb = (c) => c.match(/[\\d.]+/g).slice(0, 3).map(Number);
  const l = ([r, g, b]) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }; return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
  const c = document.querySelector('header.cover'), bg = l(rgb(getComputedStyle(c).backgroundColor));
  return ['h1', '.cover-line', '.cover-kind'].map((s) => { const x = l(rgb(getComputedStyle(c.querySelector(s)).color)); return (Math.max(x, bg) + 0.05) / (Math.min(x, bg) + 0.05); }); })()"""


class Served(Setup):
    def setUp(self):
        super().setUp()
        with self.store.step("dashboard", USER) as st:
            st.update("projects", "ABC", {"client_name": "Example Client", "week_ending": "2026-10-23"})

    def test_the_band_names_the_project_the_week_and_the_client(self):
        for width, dark in ((1400, False), (900, True), (1400, True)):
            with self.subTest(width=width, dark=dark), chrome() as cdp:
                p = self.show(cdp, width, dark)
                b = p.js(BAND)
                self.assertTrue(b["name"])
                self.assertEqual(b["kind"].upper(), "WEEKLY REPORT")
                self.assertIn("Week ending 23-10-2026", b["line"])
                self.assertIn("for Example Client", b["line"])
                self.assertEqual((b["h1count"], b["crumbs"]), (1, 0), "one heading, and the small client line is gone")
                self.assertLessEqual(abs(b["left"] - 1), 1.5, "full width of the frame, inside its border")
                self.assertLessEqual(abs(b["right"] - 1), 1.5)
                self.assertTrue(b["wide"], "no sideways scroll")
                self.assertGreaterEqual(b["top"], -1.5, "the band does not start above the frame")
                self.assertGreaterEqual(min(p.js(LUM)), 4.5)


RADII = """(() => { const c = document.querySelector('header.cover'), s = getComputedStyle(c);
  return {r: [s.borderTopLeftRadius, s.borderTopRightRadius, s.borderBottomRightRadius, s.borderBottomLeftRadius], shadow: s.boxShadow}; })()"""


class Corners(Setup):
    """Row 997: a band standing alone over separate section cards has four round corners and the card shadow; as the top of the
    one-card frame (the Card style) it keeps the top two only and no shadow of its own."""

    def test_the_band_is_rounded_all_round_with_a_shadow_when_the_sections_are_separate(self):
        for style in ("comfortable",):
            with self.subTest(style=style), chrome() as cdp:
                p = self.show(cdp)
                p.js(f"document.documentElement.dataset.density = '{style}'")
                got = p.js(RADII)
                self.assertEqual(len(set(got["r"])), 1, got)
                self.assertNotEqual(got["r"][0], "0px", got)
                self.assertNotEqual(got["shadow"], "none", got)

    def test_the_band_keeps_its_top_corners_only_as_the_top_of_the_card_frame(self):
        with chrome() as cdp:
            p = self.show(cdp)
            p.js("document.documentElement.dataset.density = 'compact'")
            got = p.js(RADII)
            self.assertEqual(got["r"][2:], ["0px", "0px"], got)
            self.assertNotEqual(got["r"][0], "0px", got)
            self.assertEqual(got["shadow"], "none", got)


PICTURE = """(() => { const c = document.querySelector('header.cover'), r = c.getBoundingClientRect(), s = getComputedStyle(c, '::before');
  return {band: [r.width, r.height], box: [parseFloat(s.width), parseFloat(s.height)], image: s.backgroundImage, size: s.backgroundSize,
          pos: s.backgroundPosition, repeat: s.backgroundRepeat, overflow: getComputedStyle(c).overflow}; })()"""


def artwork():
    """A real 650 by 245 picture of one fictional colour, as a CSS url(): the size the owner's artwork was drawn at (row 1003)."""
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    rows = b"".join(b"\0" + bytes((20, 60, 120)) * 650 for _ in range(245))
    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 650, 245, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(rows))
           + chunk(b"IEND", b""))
    return 'url("data:image/png;base64,' + base64.b64encode(png).decode() + '")'


def check_fills(test, got, has_picture):
    test.assertEqual(got["overflow"], "hidden", "the picture is clipped to the band's rounded shape")
    if not has_picture:
        test.assertEqual(got["image"], "none", "no brand picture: the plain band, nothing drawn")
        return
    test.assertIn("data:image/png", got["image"])
    test.assertEqual(got["size"], "cover", "the picture is scaled to fill, never drawn at its own size")
    test.assertEqual(got["repeat"], "no-repeat")
    test.assertAlmostEqual(got["box"][1], got["band"][1], delta=1.5, msg="the picture's box is as tall as the band: no empty band under it")
    test.assertAlmostEqual(got["box"][0], got["band"][0] * 0.6, delta=1.5, msg="and reaches the band's right edge")


class Picture(Setup):
    """Row 1003: a brand picture fills the report band (no hard edge with an empty band under it), in the editor's page, light
    and dark, at 1400 and 900; without a brand picture the band is plain."""

    def test_the_brand_picture_fills_the_band(self):
        for width, dark in ((1400, False), (900, True), (1400, True), (900, False)):
            with self.subTest(width=width, dark=dark), chrome() as cdp:
                p = self.show(cdp, width, dark)
                check_fills(self, p.js(PICTURE), False)
                p.js("document.documentElement.style.setProperty('--image-cover', %s)" % json.dumps(artwork()))
                check_fills(self, p.js(PICTURE), True)


class TheWeek(Setup):
    def coming_friday(self):
        d = date.today()
        return (d + timedelta(days=(4 - d.weekday()) % 7))

    def test_row_34_a_project_with_no_week_shows_the_coming_friday_on_the_cover(self):
        with self.store.step("dashboard", USER) as st:
            st.update("projects", "ABC", {"week_ending": None})
        with chrome() as cdp:
            line = self.show(cdp).js("document.querySelector('.cover-line').textContent")
        self.assertIn("Week ending " + self.coming_friday().strftime("%d-%m-%Y"), line)


class InTheFile(Published):
    def setUp(self):
        super().setUp()
        with self.store.step("dashboard", USER) as st:
            st.update("projects", "ABC", {"client_name": "Example Client", "week_ending": "2026-10-23"})

    def test_the_published_file_draws_the_words_in_its_bar_from_its_own_data(self):
        """Issue 1146: the banner's words sit under the project name in the file's one bar (test_published_one_bar.py draws the rest)."""
        path = self.publish()
        for width, dark in ((1400, False), (900, True)):
            with self.subTest(width=width, dark=dark), chrome() as cdp:
                p = self.draw(cdp, path, width, dark)
                got = p.js("({kind: document.querySelector('header.top .cover-kind').textContent, line: document.querySelector('header.top .cover-line').textContent, h1: document.querySelectorAll('h1').length, cover: document.querySelectorAll('header.cover').length})")
                self.assertEqual(got["kind"].upper(), "WEEKLY REPORT")
                self.assertIn("Week ending 23-10-2026", got["line"])
                self.assertIn("for Example Client", got["line"])
                self.assertEqual((got["h1"], got["cover"]), (1, 0))

    def test_a_missing_week_and_client_leave_those_parts_out(self):
        with self.store.step("dashboard", USER) as st:
            st.update("projects", "ABC", {"client_name": None, "week_ending": None})
        path = self.publish()
        with chrome() as cdp:
            line = self.draw(cdp, path).js("document.querySelector('.cover-line').textContent")
        self.assertEqual(line.strip(), "Weekly report")


if __name__ == "__main__":
    unittest.main()
