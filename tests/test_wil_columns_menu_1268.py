"""Row 1268: the Work items list's Columns menu (a right click on a column heading) ticks each column with aria-checked: "true" for a
column the list shows and "false" for one it does not, and the tick follows a press."""
import json
import unittest

import test_tpl_workitems as base
from test_report_editor import tearDownModule  # noqa: F401
from test_server import chrome


class ColumnsMenu(base.InThePage):
    def checked(self, p):
        return p.js("Object.fromEntries([...document.querySelectorAll('.cols-menu [role=menuitemcheckbox]')].map(b => [b.dataset.colName, b.getAttribute('aria-checked')]))")

    def test_aria_checked_is_true_for_a_shown_column_and_false_for_a_hidden_one_and_follows_a_press(self):
        ref = self.add({"mode": "all", "columns": ["id", "owner"], "owner": ["Pat Demo", "Lee Demo"]})
        with chrome() as cdp:
            p = self.show(cdp)
            p.edit()
            head = f"[data-id=\"{ref}\"] [data-wil-edit] .wil-table th.wil-c-owner"
            p.until(f"!!document.querySelector({json.dumps(head)})", "the list drew in Edit")
            p.js(f"document.querySelector({json.dumps(head)}).dispatchEvent(new MouseEvent('contextmenu', {{bubbles: true, cancelable: true}}))")
            p.until("!!document.querySelector('.cols-menu')", "the menu opened")
            got = self.checked(p)
            self.assertEqual(got["ID"], "true")
            self.assertEqual(got["Owner"], "true")
            for off in ("Type", "Due", "Status", "Priority", "Workstream", "Milestone"):
                self.assertEqual(got[off], "false", off)
            p.js("document.querySelector('.cols-menu [data-col-name=Due]').click()")
            p.until(f"!!document.querySelector('[data-id=\"{ref}\"] [data-wil-edit] .wil-table th.wil-c-due')", "Due was added")
            p.js(f"document.querySelector({json.dumps(head)}).dispatchEvent(new MouseEvent('contextmenu', {{bubbles: true, cancelable: true}}))")
            p.until("!!document.querySelector('.cols-menu')", "the menu opened again")
            self.assertEqual(self.checked(p)["Due"], "true", "a column the press added is ticked")

    def open_menu(self, p, ref):
        head = f"[data-id=\"{ref}\"] [data-wil-edit] .wil-table th.wil-c-owner"
        p.until(f"!!document.querySelector({json.dumps(head)})", "the list drew in Edit")
        return head

    def test_plain_f10_does_not_open_the_menu_and_shift_f10_does_and_the_menu_is_named_columns(self):
        ref = self.add({"mode": "all", "columns": ["id", "owner"], "owner": ["Pat Demo", "Lee Demo"]})
        with chrome() as cdp:
            p = self.show(cdp)
            p.edit()
            head = self.open_menu(p, ref)
            key = "new KeyboardEvent('keydown', {key: 'F10', shiftKey: %s, bubbles: true, cancelable: true})"
            p.js(f"document.querySelector({json.dumps(head)}).dispatchEvent({key % 'false'})")
            self.assertFalse(p.js("!!document.querySelector('.cols-menu')"), "F10 alone is not the menu key")
            p.js(f"document.querySelector({json.dumps(head)}).dispatchEvent({key % 'true'})")
            p.until("!!document.querySelector('.cols-menu')", "Shift+F10 opened the menu")
            self.assertEqual(p.js("document.querySelector('.cols-menu').getAttribute('aria-label')"), "Columns")
            self.assertEqual(p.js("[...document.querySelectorAll('.cols-menu .ck')].every(e => e.getAttribute('aria-hidden') === 'true')"), True, "the tick glyph is hidden from readers")

    def test_headings_are_column_headers_and_rows_show_a_pointer_in_edit(self):
        ref = self.add({"mode": "all", "columns": ["id", "owner"], "owner": ["Pat Demo", "Lee Demo"]})
        with chrome() as cdp:
            p = self.show(cdp)
            p.edit()
            self.open_menu(p, ref)
            sel = f"[data-id=\"{ref}\"] [data-wil-edit] .wil-table"
            self.assertEqual(p.js(f"[...document.querySelectorAll({json.dumps(sel + ' th')})].every(t => t.getAttribute('scope') === 'col')"), True)
            p.until(f"!!document.querySelector({json.dumps(sel + ' tbody tr')})", "a row drew")
            self.assertEqual(p.js(f"getComputedStyle(document.querySelector({json.dumps(sel + ' tbody tr')})).cursor"), "pointer")


for _name in [n for n in dir(base.InThePage) if n.startswith("test_")]:
    setattr(ColumnsMenu, _name, None)       # the helpers of the list's page tests are reused; their tests are run by test_tpl_workitems


if __name__ == "__main__":
    unittest.main()
