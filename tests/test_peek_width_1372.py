"""Row 1372 (v1.3, Classic only): the item peek is 62% of the window wide, at least 300px, as the approved peek mock-up draws it (production was 640px).

Run: python3 dev/run_tests.py test_peek_width_1372
Part 1 reads the stylesheets: the Classic rule is in rules.css before the Row 1314 block, Cards (shell.css) has none of it, the peek marks a dragged width.
Part 2 is Chrome at 1400 (the pinned width: 62% of the page area, 868px with no scrollbar) and 900 (a note: under 1000px the peek fills the window, as before), Classic and Cards.
"""
import re
import unittest

from _paths import ROOT
from test_server import chrome
from clark import page, theme
from _real_server import real_server
from test_work_board_page import Base

RULES = ((ROOT / "src" / "clark" / "themes" / "prototype-2.0" / "rules.css").read_text(encoding="utf-8") + (ROOT / "src" / "clark" / "themes" / "prototype-2.0" / "rules-2.css").read_text(encoding="utf-8"))
SHELL = (ROOT / "src" / "clark" / "page" / "shell.css").read_text(encoding="utf-8")
PEEK = (ROOT / "src" / "clark" / "page" / "src" / "components" / "Peek.jsx").read_text(encoding="utf-8")

PROBE = ("(() => { const p = document.querySelector('#peek'); if (!p) return null; const s = getComputedStyle(p), r = p.getBoundingClientRect(); "
         "return {w: r.width, left: r.left, right: r.right, vw: document.documentElement.clientWidth, min: s.minWidth, sized: p.hasAttribute('data-sized')}; })()")


class Sheets(unittest.TestCase):
    def test_the_rule_is_in_rules_css_before_row_1314_and_has_no_hex(self):
        i, j = RULES.index("/* Row 1372"), RULES.index("/* Row 1314")
        self.assertLess(i, j)
        own = RULES[i:j]
        self.assertIn("@media (min-width: 1000px) { .peek:not(.hpk):not(.wide):not([data-sized]) { width: 62% !important; min-width: min(300px, 100vw); } }", own)
        self.assertNotRegex(own, r"#[0-9a-fA-F]{3,6}\b")

    def test_cards_stylesheet_has_none_of_it(self):
        self.assertNotIn("Row 1372", SHELL)
        self.assertNotIn("62%", re.search(r"^\.peek \{[^}]*\}", SHELL, re.M).group(0))

    def test_a_dragged_width_is_marked_so_the_rule_leaves_it(self):
        self.assertIn('data-sized={width.value !== DEFAULT ? "" : undefined}', PEEK)


class Look(Base):
    """The Work items page in Chrome with the Classic theme layered (classic True) or not (Cards)."""
    classic = True

    def setUp(self):
        super().setUp()
        self.s.close()
        css = theme.css("prototype-2.0") if self.classic else None
        self.s = real_server(self.store.path, self.store.data_for,
                             page_html=lambda: page.layer_theme(page.page_html(__import__("tempfile").mkdtemp()), css), seam=lambda real, which: real)
        self.addCleanup(self.s.close)

    def open_at(self, cdp, width):
        ref = self.id_of("Order the laptops")
        sid = self.visit(cdp, width=width, hash_=f"#work&p=ABC&item={ref}", wait_for="#peek")
        self.until(cdp, sid, "!!document.querySelector('#peek')", "the peek")
        return sid


class ClassicBrowser(Look):

    def test_at_1400_the_peek_is_62_percent_of_the_window(self):
        with chrome() as cdp:
            sid = self.open_at(cdp, 1400)
            self.until(cdp, sid, "document.querySelector('#peek').getBoundingClientRect().width > 800", "the peek at its width")
            got = cdp.js(PROBE, sid)
            # the page area is the 1400 window less the 15px scrollbar the test browser draws (clientWidth 1385): 62% of it is 858.7px; with no scrollbar it is 868px
            self.assertIn(got["vw"], (1385, 1400), got)
            self.assertAlmostEqual(got["w"], 0.62 * got["vw"], delta=1, msg=got)
            self.assertEqual(got["min"], "300px", got)

    def test_a_dragged_width_is_kept(self):
        with chrome() as cdp:
            sid = self.open_at(cdp, 1400)
            cdp.js("document.querySelector('#peek').style.width = '700px'; document.querySelector('#peek').setAttribute('data-sized', '')", sid)
            self.assertAlmostEqual(cdp.js(PROBE, sid)["w"], 700, delta=1)

    def test_at_900_the_peek_fills_the_window_as_before(self):
        with chrome() as cdp:
            sid = self.open_at(cdp, 900)
            got = cdp.js(PROBE, sid)
            self.assertAlmostEqual(got["w"], got["vw"], delta=1, msg=got)


class CardsBrowser(Look):
    classic = False

    def test_cards_keeps_640_at_1400(self):
        with chrome() as cdp:
            sid = self.open_at(cdp, 1400)
            self.assertAlmostEqual(cdp.js(PROBE, sid)["w"], 640, delta=1)


if __name__ == "__main__":
    unittest.main()
