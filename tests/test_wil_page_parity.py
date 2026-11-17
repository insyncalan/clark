"""Row 1268, item 12: the Work items list in the dashboard's Edit mode uses the Work items page's own in-place pickers (edit/cells/Cell.jsx)
and column widths (edit/colWidths.jsx), not copies. View has neither: the client's page and the editor's View stay read only."""
import json
import unittest

import test_tpl_workitems as base
from test_report_editor import tearDownModule  # noqa: F401
from test_server import chrome, wait


class Parity(base.InThePage):
    def setUp(self):
        super().setUp()
        self.ref = self.add({"mode": "all", "owner": ["Pat Demo", "Lee Demo"], "columns": ["owner", "due", "status", "priority"]})

    def q(self, p, sel):
        scoped = json.dumps('[data-id="%s"] ' % self.ref + sel)      # outside the f-string: Python 3.9 refuses a backslash inside {}
        return p.js(f"document.querySelectorAll({scoped}).length")

    def test_edit_rows_change_in_place_and_view_does_not(self):
        with chrome() as cdp:
            p = self.show(cdp)
            p.until(f"!!document.querySelector('[data-id=\"{self.ref}\"] .wil-table tbody tr')", "the list drew")
            self.assertEqual(self.q(p, "[data-cell]"), 0, "View has no picker")
            self.assertEqual(self.q(p, ".cgrip"), 0, "View has no width handle")
            p.edit()
            p.until(f"!!document.querySelector('[data-id=\"{self.ref}\"] .wil-table [data-cell]')", "Edit drew the pickers")
            for field in ("owner", "due", "status", "priority"):
                self.assertEqual(self.q(p, f".wil-table tr[data-id=\"{self.a_due}\"] [data-cell=\"{self.a_due}:{field}\"]"), 1, field)
            self.assertGreater(self.q(p, "th .cgrip"), 0, "each heading has the page's width handle")

    def test_a_pick_in_the_list_is_one_change_through_clark(self):
        with chrome() as cdp:
            p = self.show(cdp)
            p.edit()
            sel = f"[data-id=\"{self.ref}\"] [data-cell=\"{self.a_due}:priority\"]"
            p.until(f"!!document.querySelector({json.dumps(sel)})", "the priority picker drew")
            p.js(f"document.querySelector({json.dumps(sel)}).click()")
            p.until("!!document.querySelector('[role=menuitem], [role=menuitemradio], [role=option]')", "the picker opened")
            self.assertEqual(p.js("location.hash.includes('item=')"), False, "a press on a cell does not open the peek")

    def test_a_dragged_width_is_kept_for_the_list(self):
        with chrome() as cdp:
            p = self.show(cdp)
            p.edit()
            p.until(f"!!document.querySelector('[data-id=\"{self.ref}\"] .wil-table th .cgrip')", "handles drew")
            p.js(f"document.querySelector('[data-id=\"{self.ref}\"] .wil-table th[data-cw-head=owner]').dispatchEvent(new KeyboardEvent('keydown', {{key: 'ArrowRight', altKey: true, bubbles: true}}))")
            self.assertTrue(wait(lambda: p.js(f"document.querySelector('[data-id=\"{self.ref}\"] .wil-table th[data-cw-head=owner]').style.width") != ""),
                            "Alt with Right arrow sets the Owner width")

    def test_a_right_click_or_shift_f10_on_a_heading_opens_the_columns_menu_with_the_shown_ones_ticked(self):      # row 1268
        head = f"document.querySelector('[data-id=\"{self.ref}\"] .wil-table th[data-cw-head=owner]')"
        items = "[...document.querySelectorAll('[role=menu] [role=menuitemcheckbox]')].map(b => b.dataset.colName + ':' + b.getAttribute('aria-checked'))"
        with chrome() as cdp:
            p = self.show(cdp)
            p.edit()
            p.until(f"!!{head}", "the heading drew")
            p.js(f"{head}.dispatchEvent(new MouseEvent('contextmenu', {{bubbles: true, cancelable: true}}))")
            p.until("!!document.querySelector('[role=menuitemcheckbox]')", "the right click opened the columns menu")
            got = p.js(items)
            self.assertIn("Owner:true", got)
            self.assertIn("Status:true", got)
            self.assertTrue(any(g.endswith(":false") for g in got), "a column the list does not show is unticked")

    def test_shift_f10_on_a_heading_opens_the_columns_menu(self):      # row 1268
        head = f"document.querySelector('[data-id=\"{self.ref}\"] .wil-table th[data-cw-head=owner]')"
        with chrome() as cdp:
            p = self.show(cdp)
            p.edit()
            p.until(f"!!{head}", "the heading drew")
            p.js(f"{head}.dispatchEvent(new KeyboardEvent('keydown', {{key: 'F10', shiftKey: true, bubbles: true, cancelable: true}}))")
            p.until("!!document.querySelector('[role=menuitemcheckbox]')", "Shift+F10 opened the columns menu")


for _name in [n for n in dir(base.InThePage) if n.startswith("test_") and n not in vars(Parity)]:
    setattr(Parity, _name, None)


if __name__ == "__main__":
    unittest.main()
