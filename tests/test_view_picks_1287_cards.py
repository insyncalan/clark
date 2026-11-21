"""Row 1287, Cards pin: the Cards page (no Theme layered) keeps the markup it had. The built-in Actions, Risks and Decisions lists draw no picker in View,
a click on a title opens the peek read only, and the Work items list draws no picker either. Fictional data only.

Run: python3 dev/run_tests.py test_view_picks_1287_cards   (headless Chrome; fails, never skips, without it)
"""
import test_tpl_workitems as T
from test_report_editor import Pg, tearDownModule  # noqa: F401
from test_server import chrome


class CardsKeepTheirRows(T.InThePage):
    def section(self, kind, title):
        with self.store.step("dashboard", T.USER) as st:
            return st.create("report_sections", {"project": "ABC", "type": kind, "title": title, "sort_order": 1})

    def test_the_built_in_lists_have_no_pickers_in_view_on_cards(self):
        ref = self.section("actions", "Fictional actions")
        rref = self.section("raid", "Fictional risks")
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.show(cdp, width)
                row = f"[data-id=\"{ref}\"] .wl-row[data-id=\"{self.a_due}\"]"
                p.until(f"!!document.querySelector('{row}')", "the actions list drew")
                p.until(f"!!document.querySelector('[data-id=\"{rref}\"] .wl-row')", "the risks list drew")
                self.assertEqual(p.js("!!document.getElementById('theme')"), False, "this is the Cards page")
                self.assertEqual(p.js("document.querySelectorAll('.secs [data-cell], .secs .cell-pick').length"), 0, "no picker anywhere in the sections")

    def test_a_title_click_opens_the_peek_read_only_on_cards(self):
        ref = self.section("actions", "Fictional actions")
        row = f"[data-id=\"{ref}\"] .wl-row[data-id=\"{self.a_due}\"]"
        with chrome() as cdp:
            p = self.show(cdp, 1400)
            p.until(f"!!document.querySelector('{row}')", "the actions list drew")
            p.js(f"document.querySelector('{row} .c-title').click()")
            p.until("!!document.querySelector('#peek')", "the peek opened")
            self.assertEqual(p.js("!!document.querySelector('#peek [data-cell], #peek .cell-pick')"), False, "read only: no edit part")
