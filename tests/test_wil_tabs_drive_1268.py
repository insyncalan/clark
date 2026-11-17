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


    def test_review_all_opens_the_work_items_page_on_the_type_of_the_lists_kinds(self):      # row 1268: killer for the link's target, per page state
        from test_tpl_workitems import USER
        with self.store.step("dashboard", USER) as st:
            st.create("raid", {"project": "ABC", "type": "Issue", "description": "Vendor is late", "raised": "2026-10-01", "source": "demo",
                               "impact": "High", "likelihood": "High", "owner": "Pat Demo"})
            st.create("decisions", {"project": "ABC", "decision": "Pick the vendor", "date": "2026-10-01", "made_by": "Pat Demo", "source": "demo"})
        want = {"all": [], "action": ["action"], "risk": ["risk"], "issue": ["issue"], "decision": ["decision"]}
        got = {}
        for name, kinds in want.items():
            ref = self.add({"mode": "all", "kinds": kinds}, title=f"List {name}")
            with chrome() as cdp:
                p = self.show(cdp)
                sel = f"[data-id=\"{ref}\"] [data-wil-review]"
                p.until(f"!!document.querySelector({json.dumps(sel)})", "the link drew")
                p.js(f"document.querySelector({json.dumps(sel)}).click()")
                p.until("location.hash.includes('work')", "the Work items page opened")
                got[name] = p.js("location.hash")
        self.assertEqual(got, {"all": "#work&p=ABC&f=mode:all", "action": "#work&p=ABC&f=mode:all;type:action", "risk": "#work&p=ABC&f=mode:all;type:risk",
                               "issue": "#work&p=ABC&f=mode:all;type:risk", "decision": "#work&p=ABC&f=mode:all;type:decision"})


if __name__ == "__main__":
    unittest.main()
