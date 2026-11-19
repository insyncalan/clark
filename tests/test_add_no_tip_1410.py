"""Row 1410: in Classic the Add buttons whose words grow into the button (Add item, Add action, Add milestone, Add use case) carry no
tooltip (no title, no data-tip); the accessible name stays. A Work items list tile whose words never show keeps its tip; Cards is unchanged.

Run: python3 dev/run_tests.py test_add_no_tip_1410
Headless Chrome (required: fails, never skips, without it), at 1400 and 900 px.
"""
import json
import tempfile
import unittest

from _real_server import real_server
from clark import page
from test_server import chrome
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

    def test_source_gates_the_tip_on_classic_and_keeps_it_for_the_icon_only_tile(self):
        from pathlib import Path
        root = Path(page.__file__).parent / "src"
        tile = (root / "components" / "NewTile.jsx").read_text()
        self.assertIn("classicTheme() && !iconOnly ? undefined : word", tile)
        self.assertIn("iconOnly />", (root / "edit" / "templates" / "WorkItemsList.jsx").read_text())


if __name__ == "__main__":
    unittest.main()
