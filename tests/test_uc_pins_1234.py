"""Row 1234: four pins on the dashboard's Use case summary that had no test.

  a  "+ Add a use case from your project record (N)" shows in Edit only when N > 0 (none at N = 0, none in View)
  b  no "Add use case" button on the dashboard, in View or in Edit (the Add button is on the Use cases page only)
  c  "N more on the Use cases page": the link, its two wordings, the way it goes, and none when nothing is off the page
  d  an opened row has two columns, Where it stands and Next steps, side by side, with See all N work items under them

Run: python3 dev/run_tests.py test_uc_pins_1234
Same harness and fictional data as test_glance_page (two use cases on the dashboard), plus two that are off it. Widths 1400 and 900 px.
"""
import json
import unittest

from _demo import USER
from test_glance_page import Setup, tearDownModule  # noqa: F401
from test_server import chrome

BACK = "document.querySelectorAll('[data-uc-back]').length"
ADD_BUTTONS = """[...document.querySelectorAll('button, a, [role=button]')]
  .filter(e => /^\\+?\\s*Add (a )?use case$/i.test((e.textContent || '').trim()) || /^Add (a )?use case$/i.test(e.getAttribute('aria-label') || '')).length"""


class Pins(Setup):
    def off_page(self, n):
        with self.store.step("dashboard", USER) as st:
            for i in range(n):
                st.create("use_cases", {"project": "ABC", "title": f"Off {i}", "status": "On track", "ref": f"7.{i}", "client_visible": 0, "source": "demo"})

    def all_on(self):
        self.store.con.execute("UPDATE use_cases SET client_visible = 1")
        self.store.con.commit()

    def edit(self, p):
        p.js("document.querySelector('[data-mode=edit]').click()")
        p.until("!!document.querySelector('.uc [data-uc-status]')", "Edit shows the status buttons")

    def test_a_the_add_from_record_line_is_there_only_when_something_is_off_the_page(self):
        for width in (1400, 900):
            with self.subTest(width=width, off=0), chrome() as cdp:
                self.all_on()
                p = self.show(cdp, width)
                self.edit(p)
                self.assertEqual(p.js(BACK), 0, "N = 0: no line")
                self.assertNotIn("from your project record", p.js("document.querySelector('.uc').parentElement.innerText"))
            with self.subTest(width=width, off=2), chrome() as cdp:
                self.off_page(2)
                p = self.show(cdp, width)
                self.assertEqual(p.js(BACK), 0, "View has no line even with some off")
                self.edit(p)
                self.assertEqual(p.js("[...document.querySelectorAll('[data-uc-back]')].map(e => e.textContent)"), ["+ Add a use case from your project record (2)"])

    def test_b_the_dashboard_has_no_add_use_case_button_in_view_or_edit(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                self.off_page(1)
                p = self.show(cdp, width)
                self.assertEqual(p.js(ADD_BUTTONS), 0, "View")
                self.assertEqual(p.js("document.querySelectorAll('#ucAddPage, .uc [data-newtile], .uc .newb').length"), 0)
                self.edit(p)
                self.assertEqual(p.js(ADD_BUTTONS), 0, "Edit")
                self.assertEqual(p.js("document.querySelectorAll('#ucAddPage, .uc [data-newtile], .uc .newb').length"), 0)
                p.js("location.hash = '#usecases&p=ABC'")
                p.until("!!document.querySelector('#ucAddPage')", "the Use cases page has the button")
                self.assertEqual(p.js("document.querySelector('#ucAddPage').textContent.includes('Add use case')"), True)

    def more(self, n):
        for width in (1400, 900):
            with self.subTest(width=width, off=n), chrome() as cdp:
                p = self.show(cdp, width)
                return_ = p.js("[...document.querySelectorAll('[data-uc-more]')].map(e => [e.textContent, e.getAttribute('href')])")
                if not n:
                    self.assertEqual(return_, [], "nothing off the page: no line")
                    continue
                self.assertEqual(len(return_), 1)
                self.assertEqual(return_[0][0], "1 more on the Use cases page" if n == 1 else f"{n} more on the Use cases page")
                self.assertIn("usecases", return_[0][1])
                p.js("document.querySelector('[data-uc-more]').click()")
                p.until("location.hash === '#usecases&p=ABC'", "the line goes to the Use cases page")

    def test_c_one_more_reads_in_the_singular(self):
        self.off_page(1)
        self.more(1)

    def test_c_three_more_reads_in_the_plural(self):
        self.off_page(3)
        self.more(3)

    def test_c_with_every_use_case_on_the_page_there_is_no_line(self):
        self.all_on()
        self.more(0)

    def test_d_an_opened_row_has_two_columns_side_by_side_and_the_see_all_line_under_them(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.show(cdp, width)
                self.assertEqual(p.js("document.querySelectorAll('.ucdetail').length"), 0, "shut: no detail")
                p.js("document.querySelector('.ucrow .ucbar').click()")
                p.until("!!document.querySelector('.ucdetail')", "the row opened")
                self.assertEqual(p.js("[...document.querySelectorAll('.ucdetail .ucdcols > div > h3')].map(e => e.textContent)"), ["Where it stands", "Next steps · 3"])
                box = p.js("""(() => { const c = [...document.querySelectorAll('.ucdetail .ucdcols > div')].map(e => e.getBoundingClientRect());
                  const see = document.querySelector('.ucdetail [data-seeall]').getBoundingClientRect();
                  return {n: c.length, left: c.map(r => r.left), top: c.map(r => r.top), bottom: Math.max(...c.map(r => r.bottom)), seeTop: see.top}; })()""")
                self.assertEqual(box["n"], 2)
                self.assertGreater(box["left"][1] - box["left"][0], 100, "side by side")
                self.assertAlmostEqual(box["top"][0], box["top"][1], delta=2)
                self.assertGreaterEqual(box["seeTop"], box["bottom"] - 1, "See all sits under the columns")
                self.assertEqual(p.js("document.querySelector('.ucdetail [data-seeall]').textContent"), "See all 3 work items for 1.1")


if __name__ == "__main__":
    unittest.main()
