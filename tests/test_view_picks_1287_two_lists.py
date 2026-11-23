"""Row 1287: the same item shown in two lists on the Dashboard never shares one open picker. Opening a picker in one list leaves the same
cell of the other list shut. Classic layer, widths 1400 and 900. Fictional data only.

Run: python3 dev/run_tests.py test_view_picks_1287_two_lists   (headless Chrome; fails, never skips, without it)
"""
import unittest

import test_tpl_workitems as T
from test_view_picks_1287_more import classic
from test_report_editor import Pg, tearDownModule  # noqa: F401
from test_server import chrome


class ViewPickTwoLists(T.InThePage):
    def section(self, kind, title, order):
        with self.store.step("dashboard", T.USER) as st:
            return st.create("report_sections", {"project": "ABC", "type": kind, "title": title, "sort_order": order})

    def test_one_item_in_two_lists_opens_one_picker_at_a_time(self):
        classic(self)
        one = self.section("actions", "Fictional actions one", 1)
        two = self.section("actions", "Fictional actions two", 2)
        for width in (1400, 900):
            for field, cls in (("owner", "c-owner"), ("due", "c-date"), ("status", "c-ico")):
                with self.subTest(width=width, field=field), chrome() as cdp:
                    p = self.show(cdp, width)
                    a = f"[data-id=\"{one}\"] .wl-row[data-id=\"{self.a_due}\"] .{cls} .cell-pick"
                    b = f"[data-id=\"{two}\"] .wl-row[data-id=\"{self.a_due}\"] .{cls} .cell-pick"
                    p.until(f"!!document.querySelector('{a}') && !!document.querySelector('{b}')", "both lists drew")
                    p.js(f"document.querySelector('{a}').click()")
                    p.until(f"document.querySelector('{a}').getAttribute('aria-expanded') === 'true'", "the first list's picker opened")
                    self.assertEqual(p.js(f"document.querySelector('{b}').getAttribute('aria-expanded')"), "false", "the other list's picker stays shut")
                    self.assertEqual(p.js("document.querySelectorAll('[data-cell][aria-expanded=true]').length"), 1)
                    p.js(f"document.querySelector('{b}').click()")
                    p.until(f"document.querySelector('{b}').getAttribute('aria-expanded') === 'true'", "the second list's picker opened")
                    self.assertEqual(p.js(f"document.querySelector('{a}').getAttribute('aria-expanded')"), "false", "the first closed when the second opened")


if __name__ == "__main__":
    unittest.main()
