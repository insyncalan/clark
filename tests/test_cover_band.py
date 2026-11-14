"""A-D1 page side: the report's cover band, in a real browser. Item 1177: the editor's Dashboard has no cover band any more; its words and
picture are in the one slim header (.top-hdr). The Gantt page still draws header.cover (Cover.jsx), so the band cases that still apply run there.

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
from unittest import mock
from datetime import date, timedelta
from pathlib import Path

from _demo import USER
from test_glance_page import Published, Setup, Pg
from test_report_editor import tearDownModule  # noqa: F401
from test_server import chrome
import _testpage as testpage
from clark import page
from test_brand_picture import png

# item 1177: the editor's header (.top-hdr) holds the project name (.hdr-project), "Weekly report" (.hdr-kind) and the week (.hdr-date); no "for <client>".
BAND = """(() => {
  const c = document.querySelector('.top-hdr'); if (!c) return null;
  const h = c.querySelector('.hdr-project'), line = c.querySelector('.hdr-line');
  const r = c.getBoundingClientRect();
  return {name: h.textContent, line: line.textContent, kind: c.querySelector('.hdr-kind').textContent,
          bg: getComputedStyle(c).backgroundColor, top: r.top, left: r.left, right: window.innerWidth - r.right,
          covers: document.querySelectorAll('header.cover, #cover').length, headers: document.querySelectorAll('.top-hdr').length,
          wide: document.documentElement.scrollWidth <= window.innerWidth, crumbs: document.querySelectorAll('.report .crumbs').length,
          text: c.textContent};
})()"""
LUM = """(() => { const rgb = (c) => c.match(/[\\d.]+/g).slice(0, 3).map(Number);
  const l = ([r, g, b]) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }; return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
  const c = document.querySelector('@BAND@'), bg = l(rgb(getComputedStyle(c).backgroundColor));
  return ['@WORDS@'].flatMap((s) => s.split(',')).map((s) => { const x = l(rgb(getComputedStyle(c.querySelector(s.trim())).color)); return (Math.max(x, bg) + 0.05) / (Math.min(x, bg) + 0.05); }); })()"""
LUM_HDR = LUM.replace("@BAND@", ".top-hdr").replace("@WORDS@", ".hdr-project,.hdr-line,.hdr-kind")
LUM_COVER = LUM.replace("@BAND@", "header.cover").replace("@WORDS@", "h1,.cover-line,.cover-kind")


def gantt_page(test, cdp, width=1400, dark=False):
    """The Gantt page of the served app (it still draws header.cover, Cover.jsx), waited for by its cover."""
    p = Pg.at(test, cdp, test.s.port, "#gantt&p=ABC", section_style="slim")
    cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1100, "deviceScaleFactor": 1, "mobile": False}, p.sid)
    if dark:
        p.js("document.documentElement.dataset.theme = 'dark'")
    p.until("!!document.querySelector('header.cover')", "the Gantt page drew its cover")
    return p


class Served(Setup):
    def setUp(self):
        super().setUp()
        with self.store.step("dashboard", USER) as st:
            st.update("projects", "ABC", {"client_name": "Example Client", "week_ending": "2026-10-23"})

    def test_the_header_names_the_project_and_the_week_with_no_client_and_no_band(self):
        for width, dark in ((1400, False), (900, True), (1400, True)):
            with self.subTest(width=width, dark=dark), chrome() as cdp:
                p = self.show(cdp, width, dark)
                b = p.js(BAND)
                self.assertTrue(b["name"].strip())
                self.assertEqual(b["kind"].upper(), "WEEKLY REPORT")
                self.assertIn("Week ending 23-10-2026", b["line"])
                self.assertNotIn("for Example Client", b["text"], "item 1177: the editor's header has no 'for <client>'")
                self.assertEqual((b["headers"], b["covers"], b["crumbs"]), (1, 0, 0), "one header, no cover band under it, and no small client line")
                self.assertLessEqual(abs(b["left"]), 1.5, "full width of the window")
                self.assertLessEqual(abs(b["right"]), 1.5)
                self.assertTrue(b["wide"], "no sideways scroll")
                self.assertLessEqual(abs(b["top"]), 1.5, "the header is at the top of the window")
                self.assertGreaterEqual(min(p.js(LUM_HDR)), 4.5)


RADII = """(() => { const c = document.querySelector('@SEL@'), s = getComputedStyle(c);
  return {r: [s.borderTopLeftRadius, s.borderTopRightRadius, s.borderBottomRightRadius, s.borderBottomLeftRadius], shadow: s.boxShadow}; })()"""


class Corners(Setup):
    """Row 997 on the Gantt page's cover band: standing alone over separate section cards it has four round corners and the card shadow;
    as the top of the one-card frame (the Card style) it keeps the top two only and no shadow of its own. Item 1177: the editor's header
    is a square bar edge to edge in either style."""

    def test_the_gantt_band_is_rounded_all_round_with_a_shadow_when_the_sections_are_separate(self):
        with chrome() as cdp:
            p = gantt_page(self, cdp)
            p.js("document.documentElement.dataset.density = 'comfortable'")
            got = p.js(RADII.replace("@SEL@", "header.cover"))
            self.assertEqual(len(set(got["r"])), 1, got)
            self.assertNotEqual(got["r"][0], "0px", got)
            self.assertNotEqual(got["shadow"], "none", got)

    def test_the_gantt_band_keeps_its_top_corners_only_as_the_top_of_the_card_frame(self):
        with chrome() as cdp:
            p = gantt_page(self, cdp)
            p.js("document.documentElement.dataset.density = 'compact'")
            got = p.js(RADII.replace("@SEL@", "header.cover"))
            self.assertEqual(got["r"][2:], ["0px", "0px"], got)
            self.assertNotEqual(got["r"][0], "0px", got)
            self.assertEqual(got["shadow"], "none", got)

    def test_the_editor_header_is_a_square_bar_with_no_shadow_in_either_style(self):
        for density in ("comfortable", "compact"):
            with self.subTest(density=density), chrome() as cdp:
                p = self.show(cdp)
                p.js(f"document.documentElement.dataset.density = '{density}'")
                got = p.js(RADII.replace("@SEL@", ".top-hdr"))
                self.assertEqual(got["r"], ["0px"] * 4, got)
                self.assertEqual(got["shadow"], "none", got)


PICTURE = """(() => { const c = document.querySelector('@SEL@'), r = c.getBoundingClientRect(), s = getComputedStyle(c, '::before');
  return {band: [r.width, r.height], box: [parseFloat(s.width), parseFloat(s.height)], image: s.backgroundImage, size: s.backgroundSize,
          pos: s.backgroundPosition, repeat: s.backgroundRepeat, overflow: getComputedStyle(c).overflow, opacity: s.opacity}; })()"""


def artwork():
    """A real 650 by 245 picture of one fictional colour, as a CSS url(): the size the owner's artwork was drawn at (row 1003)."""
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    rows = b"".join(b"\0" + bytes((20, 60, 120)) * 650 for _ in range(245))
    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 650, 245, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(rows))
           + chunk(b"IEND", b""))
    return 'url("data:image/png;base64,' + base64.b64encode(png).decode() + '")'


def check_fills(test, got, has_picture, share, clipped):
    """share: the part of the band's width the picture's box covers (the Gantt cover 0.6, the editor header 0.45)."""
    if clipped:
        test.assertEqual(got["overflow"], "hidden", "the picture is clipped to the band's rounded shape")
    if not has_picture:
        test.assertEqual(got["image"], "none", "no brand picture: the plain band, nothing drawn")
        return
    test.assertIn("data:image/png", got["image"])
    test.assertEqual(got["size"], "cover", "the picture is scaled to fill, never drawn at its own size")
    test.assertEqual(got["repeat"], "no-repeat")
    test.assertAlmostEqual(got["box"][1], got["band"][1], delta=1.5, msg="the picture's box is as tall as the band: no empty band under it")
    test.assertAlmostEqual(got["box"][0], got["band"][0] * share, delta=1.5, msg="and reaches the band's right edge")


class Picture(Setup):
    """Row 1003: a brand picture fills the report band (no hard edge with an empty band under it), light and dark, at 1400 and 900;
    without a brand picture the band is plain. Item 1177: in the editor the picture is a wash on the header's right 45 percent
    (shell.css, .top-hdr::before, about 42 percent strength); the Gantt page's cover keeps the row 1003 band (its right 60 percent)."""

    def test_the_brand_picture_fills_the_gantt_band(self):
        for width, dark in ((1400, False), (900, True), (1400, True), (900, False)):
            with self.subTest(width=width, dark=dark), chrome() as cdp:
                p = gantt_page(self, cdp, width, dark)
                js = PICTURE.replace("@SEL@", "header.cover")
                check_fills(self, p.js(js), False, 0.6, True)
                p.js("document.documentElement.style.setProperty('--image-cover', %s)" % json.dumps(artwork()))
                check_fills(self, p.js(js), True, 0.6, True)

    def test_the_brand_picture_is_a_wash_over_the_right_of_the_editor_header(self):
        for width, dark in ((1400, False), (900, True), (1400, True), (900, False)):
            with self.subTest(width=width, dark=dark), chrome() as cdp:
                p = self.show(cdp, width, dark)
                js = PICTURE.replace("@SEL@", ".top-hdr")
                check_fills(self, p.js(js), False, 0.45, False)
                p.js("document.documentElement.style.setProperty('--image-cover', %s)" % json.dumps(artwork()))
                got = p.js(js)
                check_fills(self, got, True, 0.45, False)
                self.assertAlmostEqual(float(got["opacity"]), 0.42, delta=0.01, msg="a soft wash, not the full picture")


LOGO = """(() => { const c = document.querySelector('header.cover'), r = c.getBoundingClientRect(), s = getComputedStyle(c, '::after');
  return {band: [r.width, r.height], display: s.display, image: s.backgroundImage, size: s.backgroundSize, repeat: s.backgroundRepeat,
          pos: s.backgroundPosition, abs: s.position, w: parseFloat(s.width), h: parseFloat(s.height), top: parseFloat(s.top), right: parseFloat(s.right)}; })()"""
# item 1177 (option c): the installed brand's logo (item 1154's --image-logo) is drawn small at the RIGHT of the editor's header, before the icons: .hdr-end::before.
HDR_LOGO = """(() => { const c = document.querySelector('.top-hdr'), e = c.querySelector('.hdr-end'), s = getComputedStyle(e, '::before'),
  b = c.getBoundingClientRect(), r = e.getBoundingClientRect(), clark = c.querySelector('.logo').getBoundingClientRect(),
  edge = (el) => { const g = document.createRange(); g.selectNodeContents(el); return Math.max(...[...g.getClientRects()].map((x) => x.right)); },
  kids = [...e.children].filter((k) => k.getBoundingClientRect().width > 0), first = kids.length ? Math.min(...kids.map((k) => k.getBoundingClientRect().left)) : null,
  last = kids.length ? Math.max(...kids.map((k) => k.getBoundingClientRect().right)) : null;
  const left = r.left + parseFloat(s.left || 0);
  return {bar: [b.left, b.right, b.top, b.bottom], image: s.backgroundImage, size: s.backgroundSize, repeat: s.backgroundRepeat, pos: s.backgroundPosition,
          abs: s.position, display: s.display, w: parseFloat(s.width), h: parseFloat(s.height), left: left, right: left + parseFloat(s.width),
          mid: r.top + r.height / 2, endLeft: r.left, first: first, last: last, clarkRight: clark.right, clarkLeft: clark.left,
          name: edge(c.querySelector('.hdr-project')), line: edge(c.querySelector('.hdr-line')), pad: getComputedStyle(e).paddingLeft,
          var: getComputedStyle(document.documentElement).getPropertyValue('--image-logo').trim(),
          wide: document.documentElement.scrollWidth <= window.innerWidth, vw: window.innerWidth,
          covers: document.querySelectorAll('header.cover').length}; })()"""


class Logo(Setup):
    """item 1154: the brand's logo at the right of the report band, 64 px tall, 24 px from the top and 36 px from the right (the
    prototype's .cover .mark), at 1400 and 900, light and dark; nothing is drawn without a brand logo. Item 1177 (option c): the Gantt page's
    cover still has it, and the editor's header draws it small at the right, before the icons (.hdr-end::before), clark logo at the left."""

    def test_the_brand_logo_sits_at_the_right_of_the_gantt_band(self):
        for width, dark in ((1400, False), (900, True), (1400, True), (900, False)):
            with self.subTest(width=width, dark=dark), chrome() as cdp:
                p = gantt_page(self, cdp, width, dark)
                plain = p.js(LOGO)
                self.assertEqual(plain["image"], "none", "no brand logo: nothing is drawn")
                p.js("document.documentElement.style.setProperty('--image-logo', %s)" % json.dumps(artwork()))
                got = p.js(LOGO)
                self.assertIn("data:image/png", got["image"])
                self.assertEqual((got["abs"], got["display"]), ("absolute", "block"))
                self.assertEqual((got["h"], got["top"], got["right"]), (64, 24, 36))
                self.assertEqual(got["size"], "contain", "the logo is scaled to fit, never stretched or cropped")
                self.assertEqual(got["repeat"], "no-repeat")
                self.assertTrue(got["pos"].startswith("100%"), "against the right edge of its box")
                self.assertLessEqual(got["w"] + got["right"], got["band"][0], "inside the band")
                self.assertTrue(p.js("document.documentElement.scrollWidth <= window.innerWidth"), "no sideways scroll")
                self.assertGreaterEqual(min(p.js(LUM_COVER)), 4.5, "the text keeps its contrast")

    def test_the_brand_logo_sits_small_at_the_right_of_the_editor_header_before_the_icons(self):
        for width, dark in ((1400, False), (900, True), (1400, True), (900, False)):
            with self.subTest(width=width, dark=dark), chrome() as cdp:
                p = self.show(cdp, width, dark)
                plain = p.js(HDR_LOGO)
                self.assertEqual(plain["image"], "none", "no brand logo: nothing is drawn")
                self.assertEqual(plain["image"], "none", "no brand logo: nothing is painted; the box is out of the flow (item 1177) and the room kept is checked below")
                p.js("document.documentElement.style.setProperty('--image-logo', %s); document.documentElement.style.setProperty('--cover-logo-room', '192px')" % json.dumps(artwork()))
                got = p.js(HDR_LOGO)
                self.assertIn("data:image/png", got["image"])
                self.assertEqual((got["abs"], got["display"]), ("absolute", "block"))
                self.assertEqual((got["w"], got["h"]), (128, 32) if width == 1400 else (96, 24), "small: 128 x 32 at 1400, 96 x 24 at 900")
                self.assertEqual(got["size"], "contain", "the logo is scaled to fit, never stretched or cropped")
                self.assertEqual(got["repeat"], "no-repeat")
                self.assertTrue(got["pos"].startswith("100%"), "against the right edge of its box")
                self.assertGreaterEqual(got["left"], got["bar"][0], "inside the bar")
                self.assertLessEqual(got["right"], got["bar"][1], "inside the bar")
                self.assertTrue(got["bar"][2] <= got["mid"] <= got["bar"][3], "in the bar's height")
                self.assertLessEqual(got["right"], got["first"] + 0.5, "before the icons: the logo ends at or left of the first icon")
                self.assertLessEqual(got["last"], got["vw"] + 0.5, "the profile circle stays on the row")
                self.assertLessEqual(got["clarkRight"], got["left"], "the clark logo stays at the left, the brand logo is right of it")
                self.assertTrue(got["wide"], "no sideways scroll")
                self.assertGreaterEqual(min(p.js(LUM_HDR)), 4.5, "the text keeps its contrast")

    def test_the_clark_logo_stays_at_the_left_and_the_brand_logo_sits_left_of_the_icon_group(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.show(cdp, width)
                p.js("document.documentElement.style.setProperty('--image-logo', %s); document.documentElement.style.setProperty('--cover-logo-room', '192px')" % json.dumps(artwork()))
                got = p.js(HDR_LOGO)
                self.assertLessEqual(got["clarkLeft"] - got["bar"][0], 40, "the clark logo is at the left edge of the header")
                self.assertLess(got["clarkRight"], got["endLeft"], "the clark logo is left of the .hdr-end group")
                self.assertGreaterEqual(got["left"], got["endLeft"], "the brand logo is in .hdr-end, at its left, before the icons")
                self.assertEqual(got["covers"], 0, "still no cover band under the header")


class BrandLogo(Setup):
    """item 1154: the logo comes from the installed brand's assets/logo.png, through the real wiring (the page text the brand layer
    builds and the picture route), not from a variable set by hand: at 1400 and 900 it is drawn in the Gantt page's band (item 1177: and small at the right of the editor's header, before the icons); a brand with no logo draws nothing."""

    def serve(self, with_logo):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        folder = Path(tmp.name)
        (folder / "assets").mkdir()
        (folder / "tokens.css").write_text(":root { --brand-navy: #123456; }", encoding="utf-8")
        if with_logo:
            (folder / "assets" / "logo.png").write_bytes(png(40, 12, (200, 30, 120)))
        hook = mock.patch.object(page, "PAGE", mock.Mock(read_text=lambda **kw: testpage.html()))
        hook.start()
        self.addCleanup(hook.stop)
        self.s.httpd.page_html = lambda: page.page_html(branding=folder, brand_id="one-brand")
        self.s.httpd.brand_picture = lambda name, brand_id=None: page.brand_picture(name, folder) if brand_id == "one-brand" else None

    def test_the_installed_brand_logo_reaches_the_band(self):
        self.serve(True)
        for width, dark in ((1400, False), (900, True)):
            with self.subTest(width=width, dark=dark), chrome() as cdp:
                p = gantt_page(self, cdp, width, dark)
                got = p.js(LOGO)
                self.assertIn("/assets/one-brand/logo.png", got["image"])
                self.assertEqual((got["display"], got["h"], got["top"], got["right"]), ("block", 64, 24, 36))
                p.js("window.__logo = 0; const i = new Image(); i.onload = () => { window.__logo = i.naturalWidth; }; i.src = '/assets/one-brand/logo.png';")
                p.until("window.__logo === 40", "the logo picture loaded from the route")
                self.assertGreaterEqual(min(p.js(LUM_COVER)), 4.5)

    def test_the_installed_brand_logo_reaches_the_editor_header(self):
        self.serve(True)
        for width, dark in ((1400, False), (900, True)):
            with self.subTest(width=width, dark=dark), chrome() as cdp:
                p = self.show(cdp, width, dark)
                got = p.js(HDR_LOGO)
                self.assertIn("/assets/one-brand/logo.png", got["image"], "the brand's own logo is drawn in the header")
                self.assertIn("/assets/one-brand/logo.png", got["var"])
                self.assertEqual((got["display"], got["abs"]), ("block", "absolute"))
                self.assertEqual((got["w"], got["h"]), (128, 32) if width == 1400 else (96, 24))
                self.assertLessEqual(got["right"], got["first"] + 0.5, "before the icons")
                self.assertTrue(got["wide"])
                p.js("window.__logo = 0; const i = new Image(); i.onload = () => { window.__logo = i.naturalWidth; }; i.src = '/assets/one-brand/logo.png';")
                p.until("window.__logo === 40", "the logo picture loaded from the route")
                self.assertGreaterEqual(min(p.js(LUM_HDR)), 4.5)

    def test_a_brand_without_a_logo_draws_nothing(self):
        self.serve(False)
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                self.assertEqual(gantt_page(self, cdp, width).js(LOGO)["image"], "none")
                got = self.show(cdp, width).js(HDR_LOGO)
                self.assertEqual((got["var"], got["image"], got["w"]), ("none", "none", 0))


ROOM = """(() => { const c = document.querySelector('header.cover'), h = c.querySelector('h1'), l = c.querySelector('.cover-line'),
  a = getComputedStyle(c, '::after'), r = c.getBoundingClientRect();
  const edge = (e) => { const g = document.createRange(); g.selectNodeContents(e); return Math.max(...[...g.getClientRects()].map((x) => x.right)); };
  return {h1: edge(h), line: edge(l), logoLeft: r.right - parseFloat(a.right) - parseFloat(a.width), pad: getComputedStyle(c).paddingRight,
          lines: Math.round(h.getBoundingClientRect().height / parseFloat(getComputedStyle(h).lineHeight))}; })()"""


class LogoRoom(Setup):
    """item 1154: a long project title and cover line wrap before the logo box when a brand logo is set (at 1400 and 900), and
    the band's padding is what it was with no logo. Item 1177: on the Gantt page's cover, the only band left."""
    serve = BrandLogo.serve

    def setUp(self):
        super().setUp()
        with self.store.step("dashboard", USER) as st:
            st.update("projects", "ABC", {"name": "Example Programme of a very long name that goes on and on " * 3,
                                          "client_name": "Example Client of a very long name that goes on and on " * 3, "week_ending": "2026-10-23"})

    def test_a_long_title_and_cover_line_stop_before_the_logo(self):
        self.serve(True)
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                got = gantt_page(self, cdp, width).js(ROOM)
                self.assertGreater(got["lines"], 1, "the title is long enough to wrap")
                self.assertLessEqual(got["h1"], got["logoLeft"], "the title ends at or left of the logo box")
                self.assertLessEqual(got["line"], got["logoLeft"], "the cover line ends at or left of the logo box")

    def test_with_no_logo_the_band_padding_is_unchanged(self):
        self.serve(False)
        for width, pad in ((1400, "28px"), (900, "16px")):
            with self.subTest(width=width), chrome() as cdp:
                self.assertEqual(gantt_page(self, cdp, width).js(ROOM)["pad"], pad)

    def test_a_long_title_and_line_stop_before_the_logo_in_the_editor_header(self):
        self.serve(True)
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                got = self.show(cdp, width).js(HDR_LOGO)
                self.assertGreater(got["w"], 0, "the logo has its box")
                self.assertLessEqual(got["name"], got["left"] + 0.5, "the project name ends at or left of the logo box")
                self.assertLessEqual(got["line"], got["left"] + 0.5, "the header line ends at or left of the logo box")

    def test_with_no_logo_the_editor_header_end_padding_is_unchanged(self):
        self.serve(False)
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.show(cdp, width)
                got = p.js(HDR_LOGO)
                self.assertEqual(got["pad"], "0px", "no room kept without a logo")
                self.assertEqual(got["w"], 0)


class BrandLogoPage(unittest.TestCase):
    def folder(self, logo):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        d = Path(tmp.name)
        (d / "assets").mkdir()
        (d / "tokens.css").write_text(":root { --brand-navy: #123456; }", encoding="utf-8")
        if logo:
            (d / "assets" / "logo.png").write_bytes(png())
        return d

    def test_only_a_served_page_of_a_brand_with_a_logo_names_it(self):
        html = '<html><head><style id="brand-demo"></style></head><body></body></html>'
        with mock.patch.object(page, "PAGE", mock.Mock(read_text=lambda **kw: html)), mock.patch.object(page, "VIEW_PAGE", mock.Mock(read_text=lambda **kw: html)):
            self.assertIn('--image-logo: url("/assets/b-1/logo.png")', page.page_html(self.folder(True), brand_id="b-1"))
            self.assertIn('--image-logo: url("/assets/logo.png")', page.page_html(self.folder(True)))
            self.assertNotIn("--image-logo", page.page_html(self.folder(False), brand_id="b-1"))
            self.assertNotIn("--image-logo", page.page_html(self.folder(True), view=True, brand_id="b-1"), "the published file carries no address")
            self.assertNotIn("--image-logo", page.page_html(page.NO_BRAND))


class TheWeek(Setup):
    def coming_friday(self):
        d = date.today()
        return (d + timedelta(days=(4 - d.weekday()) % 7))

    def test_row_34_a_project_with_no_week_shows_the_coming_friday_in_the_header(self):
        with self.store.step("dashboard", USER) as st:
            st.update("projects", "ABC", {"week_ending": None})
        with chrome() as cdp:
            line = self.show(cdp).js("document.querySelector('.top-hdr .hdr-date').textContent")
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
