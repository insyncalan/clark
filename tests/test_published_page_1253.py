"""Row 1253: the Published reports page in Classic has no card and no cover band: the one slim bar is the only band, the sections are flat. Source tests, no browser.

Run: python3 dev/run_tests.py test_published_page_1253
"""
import re
import unittest

from _paths import SRC

PAGE_SRC = SRC / "clark" / "page" / "src"
JSX = (PAGE_SRC / "edit" / "PublishedPage.jsx").read_text(encoding="utf-8")
LIST = (PAGE_SRC / "edit" / "PublishedReports.jsx").read_text(encoding="utf-8")
CSS = (PAGE_SRC / "edit" / "edit.css").read_text(encoding="utf-8")
RULES2 = (SRC / "clark" / "themes" / "prototype-2.0" / "rules-2.css").read_text(encoding="utf-8")      # row 1253: the flat look is the Classic layer; the Cards page keeps edit.css as it was
WORDS = (PAGE_SRC / "logic" / "pastReports.js").read_text(encoding="utf-8")


def rule(sel):
    m = re.search(r"^" + re.escape(sel) + r" \{([^}]*)\}", RULES2, re.M) or re.search(r"^" + re.escape(sel) + r" \{([^}]*)\}", CSS, re.M)
    assert m, sel
    return m.group(1)


class PublishedPage1253(unittest.TestCase):
    def test_classic_has_no_card_no_cover_band_and_the_page_name_is_the_heading(self):
        classic = JSX[JSX.index("if (classicTheme())"):JSX.index('<div class="pp-page" id="pubs-page">')]
        self.assertRegex(classic, r'<div class="pp-page pp-flat" id="pubs-page">\s*<h1>\{L\.TITLE\}</h1>\s*<p class="pubs-intro">\{L\.INTRO\}</p>')
        self.assertNotIn("cover", classic)
        self.assertNotIn("pp-frame", classic)
        self.assertNotIn('class="frame', classic)

    def test_cards_keeps_its_card_and_cover_band_as_on_main(self):
        cards = JSX[JSX.index('<div class="pp-page" id="pubs-page">'):]
        self.assertIn('<section class="frame pp-frame">', cards)
        self.assertRegex(cards, r'<h1>\{L\.TITLE\}</h1>\s*<p class="cover-line"><b class="cover-kind">\{title\}</b></p>')

    def test_the_intro_is_muted_text_not_white_on_a_band(self):
        self.assertIn("var(--text-muted)", rule(".pp-flat .pubs-intro"))
        self.assertNotIn("var(--white)", rule(".pp-flat .pubs-intro"))

    def test_sections_come_in_the_order_where_saved_latest_earlier(self):
        a = JSX.index("pubs-where")
        self.assertIn("<PublishedReports", JSX[a:])
        b = LIST.index('id="pubs-latest"')
        c = LIST.index("L.PAGE.earlier")
        self.assertLess(b, c)
        self.assertLess(JSX.index("L.PAGE.saved"), JSX.index("<PublishedReports"))

    def test_sections_are_flat_and_line_divided_not_bordered_cards(self):
        r = rule(".pp-flat .pp-block")
        self.assertIn("border: 0", r)
        self.assertIn("border-bottom: 1px solid var(--grey-200)", r)
        self.assertIn("border-radius: 0", r)
        self.assertNotIn("radius-lg", r)
        self.assertIn("background: transparent", r)      # no card fill
        self.assertIn("margin: 0;", r)                   # no gap between sections
        self.assertIn("padding: var(--space-4) 0;", r)   # room above and below only, none at the sides
        self.assertIn("var(--grey-200)", rule(".pp-where"))

    def test_the_flat_sections_are_the_classic_layer_only_and_the_cards_page_keeps_its_cards(self):
        m = re.search(r"^\.pp-block \{([^}]*)\}", CSS, re.M)
        self.assertIn("radius-lg", m.group(1), "edit.css keeps the bordered card (Cards)")
        self.assertNotIn(".pp-block {", CSS.split(m.group(0))[1], "no second .pp-block rule in edit.css")

    def test_the_table_scrolls_inside_its_own_box(self):
        self.assertIn("overflow-x: auto", rule(".pp-flat .pp-earlier"))

    def test_css_added_uses_tokens_only(self):
        for sel in (".pp-flat .pp-block", ".pp-flat .pp-earlier"):
            r = rule(sel)
            self.assertNotRegex(r, r"#[0-9a-fA-F]{3,8}\b")
        self.assertEqual(re.findall(r"\d+px", rule(".pp-flat .pp-block")), ["1px"])  # the hairline only

    def test_no_new_words(self):
        for w in ("Published reports", "Where it is saved", "Latest", "Earlier reports", "Show archived", "Change in Settings", "Open", "Archive"):
            self.assertIn(f'"{w}"', WORDS)
        # every string literal in the page file that is shown is an L. word or an id/class
        shown = re.findall(r">\s*([A-Za-z][^<{}>]*?)\s*<", JSX)
        self.assertEqual([s for s in shown if s], [])

    def test_ids_and_hooks_are_kept(self):
        for k in ('id="pubs-settings"', 'id="pubs-where"', 'id="pubs-page"'):
            self.assertIn(k, JSX)
        for k in ('id="pubs-archived"', "data-pubopen", "data-pubarchive", "data-pubrestore", 'id="pubs-latest"'):
            self.assertIn(k, LIST)


if __name__ == "__main__":
    unittest.main()
