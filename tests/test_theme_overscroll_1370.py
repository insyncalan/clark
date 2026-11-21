"""Row 1370: in the Classic Theme the page does not move when scrolling goes past its top or bottom (overscroll-behavior-y: none on the page),
and the colour behind the header is the page token, not white, in light and dark. Cards (no Theme) is the page byte for byte.

Run: python3 dev/run_tests.py test_theme_overscroll_1370
Chrome is required: the page parts fail, never skip, without it.
"""
import re
import unittest
from unittest import mock

from _paths import ROOT  # noqa: F401
from test_glance_page import Setup
from test_report_editor import tearDownModule  # noqa: F401
from test_server import chrome
from _publish import PublishedFile
import _testpage as testpage
from clark import page, theme

NAME = "prototype-2.0"
RULES = (ROOT / "src" / "clark" / "themes" / NAME / "rules.css").read_text(encoding="utf-8")
M1370, NEXT = "/* Row 1370", "/* Row 1393"
PART = RULES[RULES.index(M1370):RULES.index("/* Row 1305")]
HEADER = "document.querySelector('.top-hdr, .top-file')"
PAGE_PROBE = """(() => { const h = getComputedStyle(document.documentElement), b = getComputedStyle(document.body);
  return {overscroll: h.overscrollBehaviorY, bg: b.backgroundColor, top: %s.getBoundingClientRect().top, scrollTop: document.scrollingElement.scrollTop}; })()""" % HEADER

EDGE_PROBE = """(() => { const e = document.scrollingElement; return {overscroll: getComputedStyle(document.documentElement).overscrollBehaviorY,
  scrollTop: Math.round(e.scrollTop), max: e.scrollHeight - e.clientHeight, top: Math.round(document.querySelector('.top-hdr').getBoundingClientRect().top)}; })()"""


class Text(unittest.TestCase):
    def test_the_block_has_one_comment_and_one_rule_and_no_colour_or_path(self):
        comment = PART.split("\n")[0]
        self.assertTrue(comment.endswith("*/"))
        self.assertIn("row 1370", comment.lower())
        self.assertIsNone(re.search(r"#\d", comment))
        self.assertNotIn("/tmp", comment)
        self.assertEqual([l for l in PART.split("\n")[1:] if l.strip()], ["html { overscroll-behavior-y: none; }"])

    def test_the_file_stays_under_128_kib_and_the_block_is_above_row_1393_only(self):
        self.assertLess(len(RULES.encode("utf-8")), 131072)
        self.assertGreater(RULES.index(M1370), RULES.index("/* Row 1318"))

    def test_cards_has_none_of_it_and_classic_is_cards_plus_the_theme_style(self):
        cards = page.page_html(branding=page.NO_BRAND)
        self.assertNotIn("overscroll-behavior-y: none", cards)
        classic = page.page_html(branding=page.NO_BRAND, theme=NAME)
        self.assertIn("html { overscroll-behavior-y: none; }", classic)
        self.assertEqual(classic.replace('\n<style id="theme">\n' + theme.css(NAME) + "\n</style>", "", 1), cards)
        self.assertNotIn("html { overscroll-behavior-y: none; }", (ROOT / "src" / "clark" / "page" / "shell.css").read_text(encoding="utf-8"))


class Editor(Setup):
    def setUp(self):
        orig = testpage.html
        m = mock.patch.object(testpage, "html", lambda branding=None: page.layer_theme(orig(), theme.css(NAME)))
        m.start()
        self.addCleanup(m.stop)
        super().setUp()

    def measure(self, width, hash_, dark):
        with chrome() as cdp:
            p = self.show(cdp, width, False, hash_=hash_, settings=True)
            p.until("!!document.querySelector('.top-hdr .hdr-project') && document.documentElement.dataset.ready === '1'", "the header drew")
            if dark:
                p.js("document.documentElement.dataset.theme = 'dark'")
                p.until("getComputedStyle(document.documentElement).getPropertyValue('--page-bg').trim().toLowerCase() === '#121a2a'", "dark applied")
            before = p.js(PAGE_PROBE)
            cdp.call("Input.dispatchMouseEvent", {"type": "mouseWheel", "x": 200, "y": 300, "deltaX": 0, "deltaY": -400}, p.sid)
            return before, p.js(PAGE_PROBE)

    def test_the_page_does_not_move_at_its_top_at_1400_and_900(self):
        for width in (1400, 900):
            for hash_ in ("#dashboard&p=ABC", "#work&p=ABC"):
                with self.subTest(width=width, page=hash_):
                    before, after = self.measure(width, hash_, False)
                    self.assertEqual(before["overscroll"], "none")
                    self.assertEqual(after["top"], before["top"], "a wheel up at the top does not move the header")
                    self.assertEqual(after["scrollTop"], 0)

    def test_the_colour_behind_the_header_is_the_page_token_not_white_in_light_and_dark(self):
        for width in (1400, 900):
            for dark, want in ((False, "rgb(247, 249, 252)"), (True, "rgb(18, 26, 42)")):
                with self.subTest(width=width, dark=dark):
                    before = self.measure(width, "#dashboard&p=ABC", dark)[0]
                    self.assertEqual(before["bg"], want)
                    self.assertNotEqual(before["bg"], "rgb(255, 255, 255)")
                    self.assertEqual(before["overscroll"], "none")

    def edge(self, width, hash_, bottom):
        """A short window so the page scrolls; at the very bottom a wheel down, or at the very top a wheel up, on a fresh page."""
        with chrome() as cdp:
            p = self.show(cdp, width, False, hash_=hash_, settings=True)
            p.until("!!document.querySelector('.top-hdr .hdr-project') && document.documentElement.dataset.ready === '1'", "the header drew")
            cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 300, "deviceScaleFactor": 1, "mobile": False}, p.sid)
            to = "1e6" if bottom else "0"
            p.until("document.scrollingElement.clientHeight <= 300 && document.scrollingElement.scrollHeight > 300 && (document.scrollingElement.scrollTo(0, %s), Math.abs(document.scrollingElement.scrollTop - %s) < 2)"
                    % (to, "(document.scrollingElement.scrollHeight - document.scrollingElement.clientHeight)" if bottom else "0"), "the page is at its edge")
            before = p.js(EDGE_PROBE)
            cdp.call("Input.dispatchMouseEvent", {"type": "mouseWheel", "x": 200, "y": 150, "deltaX": 0, "deltaY": 600 if bottom else -600}, p.sid)
            return before, p.js(EDGE_PROBE)

    def test_a_wheel_at_the_bottom_and_at_the_top_does_not_move_the_page_on_every_page_at_1400_and_900(self):
        for width in (1400, 900):
            for hash_ in ("#dashboard&p=ABC", "#work&p=ABC", "#milestones&p=ABC", "#usecases&p=ABC", "#settings&p=ABC&s=appearance"):
                for bottom in (True, False):
                    with self.subTest(width=width, page=hash_, bottom=bottom):
                        before, after = self.edge(width, hash_, bottom)
                        self.assertEqual(before["overscroll"], "none")
                        self.assertGreater(before["max"], 0, "the page is taller than the window, so it has a bottom to test")
                        self.assertEqual(after["scrollTop"], before["scrollTop"], "a wheel past the edge does not move the page")
                        self.assertEqual(after["top"], before["top"])


class InTheFile(PublishedFile, Setup):
    theme = "classic"

    def test_the_published_report_has_no_page_bounce_and_the_page_token_at_1400_and_900(self):
        path = self.publish()
        for width in (1400, 900):
            for dark in (False, True):
                with self.subTest(width=width, dark=dark), chrome() as cdp:
                    p = self.draw(cdp, path, width, dark)
                    p.until("!!document.querySelector('.top-file .top-name')", "the bar drew")
                    got = p.js(PAGE_PROBE)
                    self.assertEqual(got["overscroll"], "none")
                    self.assertNotEqual(got["bg"], "rgb(255, 255, 255)")


if __name__ == "__main__":
    unittest.main()
