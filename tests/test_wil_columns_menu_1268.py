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


for _name in [n for n in dir(base.InThePage) if n.startswith("test_")]:
    setattr(ColumnsMenu, _name, None)       # the helpers of the list's page tests are reused; their tests are run by test_tpl_workitems


if __name__ == "__main__":
    unittest.main()
