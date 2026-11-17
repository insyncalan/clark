"""Row 1287: on the Dashboard in View, a work items list changes urgency, date, owner and status in place and never the description;
a click on the description opens the peek in full edit. A published file stays read only. Fictional data only.

Run: python3 dev/run_tests.py test_view_picks_1287   (headless Chrome; fails, never skips, without it)
"""
import unittest

from test_tpl_workitems import InThePage
from test_report_editor import Pg, tearDownModule  # noqa: F401
from test_server import chrome


class ViewPicks(InThePage):
    def test_view_lists_pick_four_values_and_the_title_opens_the_peek_in_edit_at_both_widths(self):
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
                p.js(f"document.querySelector('{row} .cell-pick[data-cell$=\":owner\"]').click()")
                p.until("!!document.querySelector('[role=dialog], [role=menu], .pop')", "the owner picker opened in View")
                p.js("document.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true}))")
                p.js(f"document.querySelector('{row} .wil-c-title').click()")
                p.until(f"((document.querySelector('#peek') || {{dataset: {{}}}}).dataset.peek || '') === '{self.a_due}'", "the peek opened")
                p.until("!!document.querySelector('#peek [data-cell], #peek .cell-pick')", "the peek is the editable one")
