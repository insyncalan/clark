"""Row 1287: on the Dashboard in View, a work items list changes urgency, date, owner and status in place and never the description;
a click on the description opens the peek in full edit. A published file stays read only. Fictional data only.

Run: python3 dev/run_tests.py test_view_picks_1287   (headless Chrome; fails, never skips, without it)
"""
import unittest

import test_tpl_workitems as T
from test_report_editor import Pg, tearDownModule  # noqa: F401
from test_server import chrome
from clark import page, theme
from _real_server import real_server
import _testpage as testpage


def classic(test):
    # Row 1287 (Classic only): the Cards page keeps the markup it had, so these tests serve the page with the Classic theme layered, as Classic serves it
    test.s.close()
    css = theme.css("prototype-2.0")
    test.s = real_server(test.store.path, test.store.data_for, page_html=lambda: page.layer_theme(testpage.html(), css), seam=test.seam)
    test.addCleanup(test.s.close)


class ViewPicks(T.InThePage):
    def test_view_lists_pick_four_values_and_the_title_opens_the_peek_in_edit_at_both_widths(self):
        classic(self)
        ref = self.add({"mode": "all", "columns": ["id", "owner", "due", "status", "priority"], "owner": ["Pat Demo", "Lee Demo"]})
        row = f"[data-id=\"{ref}\"] .wil-table tbody tr[data-id=\"{self.a_due}\"]"
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.show(cdp, width)
                p.until(f"!!document.querySelector('{row}')", "the list drew")
                self.assertEqual(p.js("document.querySelector('#report').dataset.mode"), "view")
                fields = p.js(f"[...document.querySelectorAll('{row} .cell-pick')].map(e => e.dataset.cell.split(':').pop())")
                for want in ("owner", "due", "status"):
                    self.assertIn(want, fields)
                self.assertEqual(p.js(f"document.querySelectorAll('{row} .wil-c-title .cell-pick, {row} .wil-c-title input, {row} .wil-c-title textarea').length"), 0, "the title is never a control")
                # a click that lands while the list is still drawing is lost: click again until the picker is open (never while it is open, so it cannot toggle shut)
                p.until(f"(() => {{ const o = () => !!document.querySelector('[data-cell$=\":owner\"][aria-expanded=true]'); if (!o()) {{ const b = document.querySelector('{row} .cell-pick[data-cell$=\":owner\"]'); if (b) b.click(); }} return o(); }})()", "the owner picker opened in View")
                p.js("(document.activeElement || document).dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true}))")
                p.until("!document.querySelector('[data-cell][aria-expanded=true]')", "the picker closed")
                p.js(f"document.querySelector('{row} .wil-c-title').click()")
                p.until(f"((document.querySelector('#peek') || {{dataset: {{}}}}).dataset.peek || '') === '{self.a_due}'", "the peek opened")
                p.until("!!document.querySelector('#peek [data-cell], #peek .cell-pick')", "the peek is the editable one")

    def test_a_list_set_beside_another_has_the_pickers_in_view_at_both_widths(self):
        # ruling 23-11 (A): half-width lists get the same View pickers as full-width ones, on both halves, at 1400 and 900
        classic(self)
        with self.store.step("dashboard", T.USER) as st:
            left = st.create("report_sections", {"project": "ABC", "type": "actions", "title": "Fictional actions", "sort_order": 1, "beside": 1})
            right = st.create("report_sections", {"project": "ABC", "type": "raid", "title": "Fictional risks", "sort_order": 2})
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.show(cdp, width)
                p.until(f"!!document.querySelector('[data-id=\"{left}\"].slot-left .wl-row') && !!document.querySelector('[data-id=\"{right}\"].slot-right .wl-row')", "the two lists are the two halves")
                for ref, want in ((left, {"owner", "due", "status"}), (right, {"owner", "due", "status", "priority"})):
                    got = set(p.js(f"[...document.querySelectorAll('[data-id=\"{ref}\"] .cell-pick')].map(e => e.dataset.cell.split(':').pop())"))
                    self.assertTrue(want <= got, f"half width: {want - got} missing in {ref}")
                    self.assertEqual(p.js(f"document.querySelectorAll('[data-id=\"{ref}\"] .c-title .cell-pick, [data-id=\"{ref}\"] .c-title input').length"), 0, "the description stays plain text")
                self.assertEqual(p.js("document.documentElement.scrollWidth <= document.documentElement.clientWidth"), True, "no sideways scroll")
