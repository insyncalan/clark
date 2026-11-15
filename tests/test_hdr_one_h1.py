"""The editor Dashboard keeps exactly one level-1 heading, the project name in the slim header (item 1177 took the cover that
carried it; the Gantt page keeps the one in its own cover). It is the same button as before: same size, same click. Widths 1400 and 900 only. Chrome is required: these tests fail, never skip.

Run: python3 dev/run_tests.py test_hdr_one_h1
"""
import unittest

from test_inline_67 import size
from test_report_editor import Base
from test_server import chrome

COUNT = "document.querySelectorAll('h1').length"
HEAD = ("(function(){var h=document.querySelector('h1'); var b=h&&h.querySelector('button.hdr-project'); "
        "return [!!h, !!b, h ? h.closest('header.top') !== null : false, b ? b.getBoundingClientRect().height > 0 : false];})()")


class OneHeading(Base):
    def test_the_dashboard_has_one_h1_which_is_the_project_name_button_in_the_header(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            for w in (1400, 900):
                size(cdp, p, w, 800)
                self.assertEqual(p.js(COUNT), 1, f"{w}: one h1 on the Dashboard")
                self.assertEqual(p.js(HEAD), [True, True, True, True], f"{w}: the h1 is in the header and holds the drawn project button")

    def test_the_other_pages_keep_their_own_single_one(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            for view in ("work", "milestones"):
                p.js(f"location.hash = '#{view}&p=ABC'")
                p.until(f"document.querySelector('.tab[aria-selected=true]') && document.querySelector('.tab[aria-selected=true]').dataset.view === '{view}'", f"{view} open")
                p.until(f"{COUNT} >= 1", f"{view} drew a heading")
                self.assertEqual(p.js(COUNT), 1, f"{view}: exactly one h1")


if __name__ == "__main__":
    unittest.main()
