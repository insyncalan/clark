"""Row 1475: in a Work items section the link "Show all items" and the link "Review all N items" are ONE footer row; the footers of two half-width
sections are level, whatever the lists' lengths; Classic only (the Cards page is untouched).

Run: python3 dev/run_tests.py test_one_footer_1475
"""
import json
import unittest

import test_tpl_workitems as T
from test_work_items_mockup_1195 import Look

OWNERS = (("Ann Foot", 6), ("Bob Foot", 7), ("Cy Foot", 3), ("Di Foot", 12))


class OneFooter(Look):
    def setUp(self):
        super().setUp()
        for owner, n in OWNERS:
            for k in range(n):
                self.demo.action(description=f"Footer step {owner} {k}", owner=owner, due_date="2030-02-01")

    def body(self, owner, most):
        return {"mode": "all", "max": most, "columns": ["id", "owner"], "owner": [owner]}

    def pair(self, left, right):
        """Two Work items sections side by side: left (owner, Most rows) and right."""
        with self.store.step("dashboard", T.USER) as st:
            text = st.create("report_sections", {"project": "ABC", "type": "text", "title": "Fictional notes", "sort_order": 1})
        a = self.add(self.body(*left), title="Left list", after=text, beside=0)
        b = self.add(self.body(*right), title="Right list", after=a, beside=1)
        return a, b

    def feet(self, p, ref):
        """Tops (px, rounded to the pixel) of the section's links, the foot box, and the number of rows its links make."""
        return json.loads(p.js("JSON.stringify((() => { const s = document.querySelector('[data-id=\"" + ref + "\"]'), q = (x) => s.querySelector(x);"
            "const r = (e) => e ? e.getBoundingClientRect() : null, all = r(q('.wil-all-b')), rev = r(q('.wil-review')), foot = r(q('.wil-foot'));"
            "return {all: all && all.top, allBottom: all && all.bottom, rev: rev && rev.top, revBottom: rev && rev.bottom, foot: foot && foot.top, footBottom: foot && foot.bottom,"
            "alone: !!q('p.wil-all'), feet: s.querySelectorAll('.wil-foot').length, slot: /slot-(\\w+)/.exec(s.className)[1], section: r(s).bottom,"
            "order: [...s.querySelectorAll('.wil-foot button')].map((b) => b.dataset.wilAll !== undefined ? 'all' : 'review')}; })())"))

    def load(self, cdp, a, b, width=1400, dark=False):
        p = self.show(cdp, width, dark=dark)
        for ref in (a, b):
            p.until(f"!!document.querySelector('[data-id=\"{ref}\"] .wil-review')", "the footer drew")
        return p

    def one_row(self, f, has_all):
        self.assertEqual(f["feet"], 1, "one footer per section")
        self.assertFalse(f["alone"], "no stand-alone Show all items paragraph")
        self.assertLessEqual(f["footBottom"] - f["foot"], f["revBottom"] - f["rev"] + 12, "the footer is one line high")
        if has_all:
            self.assertEqual(f["all"], f["rev"], "Show all items and Review all are level")
            self.assertEqual(f["order"], ["all", "review"], "reading and Tab order: Show all items, then Review all")
        else:
            self.assertIsNone(f["all"])
            self.assertEqual(f["order"], ["review"])

    def test_half_width_pair_both_with_show_all_items_one_row_each_and_level_across(self):
        a, b = self.pair(("Ann Foot", 3), ("Bob Foot", 3))
        for dark in (False, True):
            with self.subTest(dark=dark), T.chrome() as cdp:
                p = self.load(cdp, a, b, dark=dark)
                fa, fb = self.feet(p, a), self.feet(p, b)
                self.assertEqual((fa["slot"], fb["slot"]), ("left", "right"))
                self.one_row(fa, True)
                self.one_row(fb, True)
                self.assertEqual((fa["all"], fa["rev"]), (fb["all"], fb["rev"]), "the two sections' links share one top")
                p.js(f"document.querySelector('[data-id=\"{a}\"] .wil-all-b').click()")
                p.until(f"document.querySelector('[data-id=\"{a}\"] .wil-all-b').textContent === 'Show only 3'", "opened")
                self.assertEqual(self.feet(p, a)["order"], ["all", "review"], "open: the link stays in the footer")

    def test_a_section_without_show_all_items_keeps_review_all_at_the_right_level_with_the_neighbour(self):
        a, b = self.pair(("Cy Foot", 10), ("Bob Foot", 3))      # 3 rows, Most rows 10: no link on the left
        with T.chrome() as cdp:
            p = self.load(cdp, a, b)
            fa, fb = self.feet(p, a), self.feet(p, b)
            self.one_row(fa, False)
            self.one_row(fb, True)
            self.assertEqual(fa["rev"], fb["rev"], "Review all is level with the neighbour's footer")
            self.assertEqual(fa["rev"], fb["all"])
            right = p.js(f"(() => {{ const s = document.querySelector('[data-id=\"{a}\"]').getBoundingClientRect(), r = document.querySelector('[data-id=\"{a}\"] .wil-review').getBoundingClientRect(); return s.right - r.right; }})()")
            self.assertLess(right, 40, "Review all stays at the right edge")

    def test_lists_of_different_lengths_have_level_footers_at_the_bottom_of_the_section(self):
        a, b = self.pair(("Cy Foot", 10), ("Di Foot", 8))      # 3 rows against 8 drawn rows
        with T.chrome() as cdp:
            p = self.load(cdp, a, b)
            fa, fb = self.feet(p, a), self.feet(p, b)
            self.assertEqual(fa["rev"], fb["rev"], "Review all level")
            self.assertEqual(fa["rev"], fb["all"], "level with the neighbour's Show all items")
            self.assertEqual(fa["footBottom"], fb["footBottom"])
            heights = [p.js(f"document.querySelector('[data-id=\"{r}\"] .wil-scroll').getBoundingClientRect().height") for r in (a, b)]
            self.assertGreater(abs(heights[0] - heights[1]), 20, "the lists really differ in height")
            for f in (fa, fb):
                self.assertLess(f["section"] - f["footBottom"], 40, "the footer sits at the bottom of the section")

    def test_full_width_and_stacked_at_900_have_one_footer_row_per_section(self):
        for width in (1400, 900):
            a, b = self.pair(("Ann Foot", 3), ("Cy Foot", 10)) if width == 900 else (None, None)
            if a is None:
                with self.store.step("dashboard", T.USER) as st:
                    text = st.create("report_sections", {"project": "ABC", "type": "text", "title": "Fictional notes", "sort_order": 1})
                a = self.add(self.body("Ann Foot", 3), title="Full list", after=text)
                b = self.add(self.body("Cy Foot", 10), title="Full list two", after=a)
            with self.subTest(width=width), T.chrome() as cdp:
                p = self.load(cdp, a, b, width=width)
                fa, fb = self.feet(p, a), self.feet(p, b)
                self.one_row(fa, True)
                self.one_row(fb, False)
                if width == 900:
                    self.assertGreater(fb["foot"], fa["footBottom"], "stacked: the second section is below the first")

    def test_a_published_file_has_no_show_all_items_and_a_cards_page_keeps_its_link_block(self):
        a, b = self.pair(("Ann Foot", 3), ("Bob Foot", 3))
        self.assertEqual(self.classic, True)
        from test_work_items_mockup_1195 import ROWS_JSX
        self.assertIn("class=\"wil-all\"", ROWS_JSX, "the stand-alone link block stays for the page without a Foot (and Cards)")
        self.assertIn("classicTheme() && !fromFile.value", ROWS_JSX)


class CardsUnchanged(OneFooter):
    classic = False

    def test_cards_draw_no_footer_link_and_the_old_block(self):
        a, b = self.pair(("Ann Foot", 3), ("Bob Foot", 3))
        with T.chrome() as cdp:
            p = self.show(cdp, 1400)
            p.until(f"!!document.querySelector('[data-id=\"{a}\"] .wil-scroll')", "drew")
            self.assertEqual(p.js("document.querySelectorAll('.wil-foot [data-wil-all], .wil-foot-l').length"), 0)

    # the Classic tests do not run again for Cards
    test_half_width_pair_both_with_show_all_items_one_row_each_and_level_across = None
    test_a_section_without_show_all_items_keeps_review_all_at_the_right_level_with_the_neighbour = None
    test_lists_of_different_lengths_have_level_footers_at_the_bottom_of_the_section = None
    test_full_width_and_stacked_at_900_have_one_footer_row_per_section = None
    test_a_published_file_has_no_show_all_items_and_a_cards_page_keeps_its_link_block = None


if __name__ == "__main__":
    unittest.main()
