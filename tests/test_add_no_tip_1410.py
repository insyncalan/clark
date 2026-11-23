"""Row 1410: in Classic the Add buttons whose words grow into the button (Add item, Add action, Add milestone, Add use case, Add project) carry no
tooltip (no title, no data-tip); the accessible name stays. A Work items list tile whose words never show keeps its tip; Cards is unchanged.

Run: python3 dev/run_tests.py test_add_no_tip_1410
Headless Chrome (required: fails, never skips, without it), at 1400 and 900 px.
"""
import json
import tempfile
import unittest

from _real_server import real_server
from clark import page, theme
from test_server import chrome
import test_tpl_workitems as base
from test_work_board_page import Base, setUpModule, tearDownModule  # noqa: F401

ATTRS = "(() => { const b = document.getElementById(%s); return JSON.stringify(b ? {title: b.getAttribute('title'), tip: b.getAttribute('data-tip'), name: b.getAttribute('aria-label')} : null); })()"


class AddNoTip(Base):
    theme = "prototype-2.0"

    def setUp(self):
        super().setUp()
        self.s.close()
        self.s = real_server(self.store.path, self.store.data_for, page_html=lambda: page.page_html(tempfile.mkdtemp(), theme=self.theme))
        self.addCleanup(self.s.close)

    def attrs(self, cdp, sid, tid):
        return json.loads(cdp.js(ATTRS % json.dumps(tid), sid))

    def check(self, hash_, wait_for, tid, name):
        for width in (1400, 900):
            with self.subTest(width=width, tile=tid), chrome() as cdp:
                sid = self.visit(cdp, width=width, hash_=hash_, wait_for=wait_for)
                self.until(cdp, sid, f"!!document.getElementById({json.dumps(tid)})", "the tile drew")
                got = self.attrs(cdp, sid, tid)
                self.assertIsNone(got["title"], got)
                self.assertIsNone(got["tip"], got)
                self.assertEqual(got["name"], name, got)

    def test_work_items_add_item_has_no_tip_and_keeps_its_name(self):
        self.check("#work&p=ABC", "#work-list", "newBtn", "Add item")

    def test_use_cases_add_use_case_has_no_tip_and_keeps_its_name(self):
        self.check("#usecases&p=ABC", "#usecases", "ucAddPage", "Add use case")

    def test_milestones_add_milestone_has_no_tip_and_keeps_its_name(self):
        self.check("#milestones&p=ABC", "#milestones", "addMs", "Add milestone")

    def test_work_items_add_action_has_no_tip_and_keeps_its_name(self):
        """With the filter line on actions, the button says Add action (filters.js addPlan) and carries no tip."""
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.visit(cdp, width=width)
                self.line(cdp, sid, "type:action")
                self.until(cdp, sid, "document.getElementById('newBtn') && document.getElementById('newBtn').getAttribute('aria-label') === 'Add action'", "the button says Add action")
                got = self.attrs(cdp, sid, "newBtn")
                self.assertIsNone(got["title"], got)
                self.assertIsNone(got["tip"], got)

    def test_projects_add_project_has_no_tip_and_keeps_its_name(self):
        self.check("#settings&p=ABC", "#projects-table", "npBtn", "Add project")


class IconOnlyKeepsItsTip(base.PageBase):
    """The Work items list tile in Edit shows only a "+" (its words never show), so in Classic its tip stays."""
    add, show = base.InThePage.add, base.InThePage.show

    def setUp(self):
        super().setUp()
        self.s.close()
        css = theme.css("prototype-2.0")
        self.s = real_server(self.store.path, self.store.data_for, page_html=lambda: page.layer_theme(page.page_html(tempfile.mkdtemp()), css), seam=self.seam)
        self.addCleanup(self.s.close)
        base.plant(self)

    def test_the_list_plus_keeps_title_and_tip_in_classic_at_1400_and_900(self):
        ref = self.add({"mode": "all", "owner": ["Pat Demo"]})
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.show(cdp, width)
                p.edit()
                btn = f"[data-id=\"{ref}\"] [data-wil-add] button"
                p.until(f"!!document.querySelector({json.dumps(btn)})", "the + is drawn")
                self.assertTrue(p.js("!!document.getElementById('theme')"), "the Classic layer is on")
                got = json.loads(p.js(f"(() => {{ const b = document.querySelector({json.dumps(btn)}); return JSON.stringify({{title: b.getAttribute('title'), tip: b.getAttribute('data-tip')}}); }})()"))
                self.assertTrue(got["title"] and got["tip"], got)


if __name__ == "__main__":
    unittest.main()
