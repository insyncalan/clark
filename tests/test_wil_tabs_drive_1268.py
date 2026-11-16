"""Row 1268, saved-view tabs: in Edit the Work items list has the tabs row (five views, + New view); a tab puts its choices on the
saved filter, the dot shows once the list moves off it, an empty new-view name is refused; View mode draws no tabs row."""
import json
import unittest

import test_tpl_workitems as base
from test_report_editor import tearDownModule  # noqa: F401
from test_server import chrome, wait

NAMES = ["All work items", "Actions", "Risks and issues", "Decisions", "Overdue"]


class Tabs(base.InThePage):
    def setUp(self):
        super().setUp()
        self.ref = self.add({"mode": "all"})

    def tabs(self, p):
        return p.js(f"[...document.querySelectorAll('[data-id=\"{self.ref}\"] .wil-views .vtab > span:first-child')].map((e) => e.textContent)")

    def test_tabs_in_edit_apply_their_filter_show_the_dot_and_refuse_an_empty_name(self):
        with chrome() as cdp:
            p = self.show(cdp)
            p.edit()
            p.until(f"!!document.querySelector('[data-id=\"{self.ref}\"] .wil-views .vtab')", "the tabs drew")
            self.assertEqual(self.tabs(p), NAMES)
            p.js(f"document.querySelector('[data-id=\"{self.ref}\"] .vtab[data-view-id=\"risks-issues\"]').click()")
            p.until(f"document.querySelector('[data-id=\"{self.ref}\"] .vtab[data-view-id=\"risks-issues\"]').getAttribute('aria-pressed') === 'true'", "the tab is on")
            self.assertTrue(wait(lambda: json.loads(self.store.con.execute("SELECT body FROM report_sections WHERE id = ?", (self.ref,)).fetchone()[0])["kinds"] == ["risk", "issue"]),
                            "the section's saved filter took the view's kinds")
            p.until(f"!document.querySelector('[data-id=\"{self.ref}\"] [data-dot]') && !!document.querySelector('[data-id=\"{self.ref}\"] .fchip')", "no dot while the list is as the view says")
            p.js(f"document.querySelector('[data-id=\"{self.ref}\"] .fchip button').click()")
            p.until(f"!!document.querySelector('[data-id=\"{self.ref}\"] [data-dot]')", "the dot shows after the list moved off the view")
            p.js(f"document.querySelector('[data-id=\"{self.ref}\"] [data-wil-new]').click()")
            p.until("!!document.querySelector('#wil-vname')", "the name box opened")
            p.js("document.querySelector('#wil-vname').form.requestSubmit()")
            p.until("document.querySelector('.vmsg').textContent === 'Give the view a name.'", "an empty name is refused")
            self.assertEqual(self.tabs(p), NAMES)
            p.view()
            p.until(f"!document.querySelector('[data-id=\"{self.ref}\"] .wil-views')", "View mode has no tabs row")


if __name__ == "__main__":
    unittest.main()
