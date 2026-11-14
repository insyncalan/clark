"""Row 1084 (moved by issue 1137): the List, Board and Group by icons sit on the filter box line, at its right end, beside the box and not inside it.
The saved-view tab row keeps only the tabs (each with its count and the current tab's chevron) and Save view / Discard changes.
Each icon button has a name and a target of 24 px or more. 1400 and 900 px, light and dark.

Run: python3 dev/run_tests.py test_view_icons_filter_line
"""
import json
import tempfile
import unittest
from pathlib import Path

from _demo import USER  # noqa: E402
from clark import publish  # noqa: E402
from _real_server import real_server  # noqa: E402
import _testpage  # noqa: E402

from test_server import chrome  # noqa: E402
from test_work_board_page import Base  # noqa: E402

ICONS = ("[...document.querySelectorAll('#work .fline-row .vicons button')].map(b => [b.getAttribute('aria-label'), b.title, "
         "b.getBoundingClientRect().width >= 24 && b.getBoundingClientRect().height >= 28, b.textContent.trim()])")


class IconsOnTheLine(Base):
    def test_three_named_icons_on_the_filter_line_and_none_on_the_tab_row(self):
        with chrome() as cdp:
            sid = self.visit(cdp)
            self.assertEqual(cdp.js(ICONS, sid), [["List", "List", True, ""], ["Board", "Board", True, ""], ["Group by: Workstream", "Group by", True, ""]],
                             "List, Board and Group by: icons, named, 24 px or more")
            self.assertEqual(cdp.js("document.querySelectorAll('.fvrow [data-lay], .fvrow #viewMenu').length", sid), 0, "none beside the tabs")
            self.assertEqual(cdp.js("document.querySelectorAll('#work .fline-row #viewMenu').length", sid), 1)
            self.assertEqual(cdp.js("document.querySelector('#viewMenu .nch') === null", sid), True, "icon only: no chevron, no word")

    def test_they_are_at_the_right_end_of_the_line_beside_the_box_on_one_line_with_it(self):
        for width in (1400, 900):
            for scheme in ("light", "dark"):
                with self.subTest(width=width, scheme=scheme), chrome() as cdp:
                    sid = self.visit(cdp, width=width)
                    cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme}]}, sid)
                    got = cdp.js("(() => { const f = document.querySelector('#work .fline').getBoundingClientRect(), r = document.querySelector('#work .fline-row').getBoundingClientRect(),"
                                 " i = document.querySelector('#work .fline-row #viewMenu').getBoundingClientRect(), x = document.querySelector('#fline-input').getBoundingClientRect();"
                                 " const ic = (i.top + i.bottom) / 2;"
                                 " return [r.right - i.right, i.left >= f.right, i.top >= r.top && i.bottom <= r.bottom, i.left > x.left, ic >= x.top && ic <= x.bottom]; })()", sid)
                    self.assertEqual(got[0], 11, "the last icon ends 11 px from the line's right edge: where it ended inside the box (1 px border, 10 px padding)")
                    self.assertEqual(got[1:], [True, True, True, True], "after the box, on the line, after the input, on the input's own line")
                    self.assertEqual(cdp.js("document.documentElement.scrollWidth <= innerWidth", sid), True)

    def test_group_by_is_named_with_the_current_grouping(self):
        with chrome() as cdp:
            sid = self.visit(cdp)
            lab = cdp.js("document.querySelector('#viewMenu').getAttribute('aria-label')", sid)
            self.assertTrue(lab and lab.startswith("Group by: "), f"the button is named Group by and the grouping ({lab!r})")
            self.assertEqual(cdp.js("document.querySelector('#viewMenu').getAttribute('aria-description')", sid), None)

    def test_the_try_chip_line_is_gone_and_add_stays(self):
        with chrome() as cdp:
            sid = self.visit(cdp)
            cdp.js("document.querySelector('#fline-input').focus()", sid)
            self.assertEqual(cdp.js("document.querySelectorAll('.fhint, .fhl').length", sid), 0, "no Try chips")
            self.assertNotIn("Try", cdp.js("document.querySelector('.fline-wrap').textContent", sid))
            self.assertEqual(cdp.js("document.querySelectorAll('#work .hacts .newb').length", sid), 1, "the + button stays")

    def test_count_x_and_three_icons_share_the_line_without_overlap(self):
        # The page's start line is text, so the x shows: count and x inside the box, then List, Board, Group by outside it, in that order, on one row (item 1142: no Import or Export between).
        parts = ["#fline-count", "#fline-x", "#work .fline-row .vicons [data-lay=table]", "#work .fline-row .vicons [data-lay=board]", "#viewMenu"]
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.visit(cdp, width=width)
                got = cdp.js("(() => { const f = document.querySelector('#work .fline').getBoundingClientRect(); return %s.map(q => { const e = document.querySelector(q);"
                             " if (!e) return null; const r = e.getBoundingClientRect(); return [r.left, r.right, r.top, r.bottom, f.left, f.right, f.top, f.bottom]; }); })()" % json.dumps(parts), sid)
                self.assertNotIn(None, got, "all five parts are on the line")
                for q, g in zip(parts, got):
                    if q in ("#fline-count", "#fline-x"):
                        self.assertTrue(g[0] >= g[4] - 0.5 and g[1] <= g[5] + 0.5 and g[2] >= g[6] - 0.5 and g[3] <= g[7] + 0.5, f"{q} is inside the box: {g}")
                    else:
                        self.assertGreaterEqual(g[0], g[5] - 0.5, f"{q} is outside the box, after it: {g}")
                for a, b, ga, gb in zip(parts, parts[1:], got, got[1:]):
                    self.assertLessEqual(ga[1], gb[0] + 0.5, f"{a} ends before {b} starts")
                for q, g in zip(parts[2:], got[2:]):
                    self.assertTrue(g[1] - g[0] >= 24 and g[3] - g[2] >= 24, f"{q} is 24 px or more: {g}")
                self.assertEqual(cdp.js("document.documentElement.scrollWidth <= innerWidth", sid), True)

    def test_the_icons_still_work_and_the_tabs_keep_their_counts(self):
        with chrome() as cdp:
            sid = self.visit(cdp)
            cdp.js("document.querySelector('#work .fline-row .vicons [data-lay=board]').click()", sid)
            self.until(cdp, sid, "!!document.querySelector('#work-board')", "the board")
            cdp.js("document.querySelector('#work .fline-row .vicons [data-lay=table]').click()", sid)
            self.until(cdp, sid, "!!document.querySelector('table.items')", "the list")
            tabs = cdp.js("[...document.querySelectorAll('.vt')].map(t => [t.querySelector('.vtab span').textContent, (t.querySelector('.vtab em.num') || {}).textContent, "
                          "t.querySelector('.vtab').getAttribute('aria-pressed'), t.querySelectorAll('.nch').length])", sid)
            self.assertEqual(tabs, [["Open items", "9", "true", 1], ["Actions", "4", "false", 0], ["Risks and issues", "2", "false", 0], ["Decisions", "2", "false", 0],
                                    ["All work items", "12", "false", 0], ["Overdue", "1", "false", 0], ["My actions", "0", "false", 0]],
                             "every tab keeps its count, and only the current tab has the light chevron for its menu")
            self.assertEqual(cdp.js("document.querySelectorAll('.vtabs .nch').length", sid), 1, "one chevron in the tab row: the current tab's")

    def test_group_by_has_its_own_picture_and_its_menu_still_regroups(self):
        with chrome() as cdp:
            sid = self.visit(cdp)
            same = cdp.js("document.querySelector('#viewMenu svg').innerHTML === document.querySelector('#work .fline-row .vicons [data-lay=table] svg').innerHTML", sid)
            self.assertEqual(same, False, "Group by is not drawn as the List icon")
            self.assertEqual(cdp.js("!!document.querySelector('#viewMenu svg rect')", sid), True, "the grouping picture (two stacked groups), as on main")
            cdp.js("document.querySelector('#viewMenu').click()", sid)
            self.until(cdp, sid, "!!document.querySelector('#viewMenuList [data-kind=\"group:status\"]')", "the Group by menu")
            cdp.js("document.querySelector('#viewMenuList [data-kind=\"group:status\"]').click()", sid)
            self.until(cdp, sid, "document.querySelector('#viewMenu').getAttribute('aria-label') === 'Group by: Status'", "picking a grouping from the icon regroups")

    def test_with_no_board_only_group_by_shows(self):
        self.s = real_server(self.store.path, self.store.data_for, page_html=_testpage.html)      # the test build of the page: it has the hook window.clarkPage
        self.addCleanup(self.s.close)
        with chrome() as cdp:
            sid = self.visit(cdp)
            self.assertEqual(cdp.js("document.querySelectorAll('#work .fline-row .vicons button').length", sid), 3, "with a board: List, Board, Group by")
            cdp.js("window.clarkPage.withoutBoard()", sid)
            self.until(cdp, sid, "document.querySelectorAll('#work .fline-row .vicons button').length === 1", "only Group by")
            self.assertEqual(cdp.js("[...document.querySelectorAll('.vicons button')].map(b => b.getAttribute('aria-label'))", sid), ["Group by: Workstream"])


class ImportExportPlace(Base):
    def test_no_page_has_import_or_export_icons(self):
        """Item 1142: Work items (with items and with none), Use cases and Gantt carry no Import or Export icon, at 1400 and 900."""
        for width in (1400, 900):
            with self.subTest(width=width, page="work"), chrome() as cdp:
                sid = self.visit(cdp, width=width, wait_for="#work h1")
                self.assertEqual(cdp.js("document.querySelectorAll('#impBtn, #expBtn, #work .fio').length", sid), 0, "none on the filter line")
        with self.store.step("dashboard", USER) as st:
            for k in ("actions", "raid", "decisions"):
                for r in self.data[k]:
                    st.archive(k, r["id"])
        for width in (1400, 900):
            with self.subTest(width=width, page="empty work"), chrome() as cdp:
                sid = self.visit(cdp, width=width, wait_for="#work h1")
                self.until(cdp, sid, "/no work items yet/.test(document.querySelector('#work').textContent)", "the empty project")
                self.assertEqual(cdp.js("document.querySelectorAll('#impBtn, #expBtn').length", sid), 0, "none in the top bar either")

    def test_the_sources_hold_no_page_import_or_export_icon(self):
        src = Path(__file__).resolve().parent.parent / "src" / "clark" / "page" / "src"
        for gone in ("edit/ImportBtn.jsx", "edit/ExportBtn.jsx", "components/ImportExport.jsx"):
            self.assertFalse((src / gone).exists(), gone)
        for page in ("edit/UseCasesPage.jsx", "gantt/components/GanttPage.jsx", "components/WorkItems.jsx", "components/FilterLine.jsx"):
            text = (src / page).read_text(encoding="utf-8")
            for word in ("ImportBtn", "ExportBtn", "ImportExport", "data-gp-import", "data-gp-export"):
                self.assertNotIn(word, text, f"{page} still has {word}")

    def test_a_published_file_has_no_import_or_export_anywhere(self):
        out = Path(publish.publish(self.store, "ABC", tempfile.mkdtemp(prefix="clark-pub-"), by_user=USER, now="2026-10-29", branding=tempfile.mkdtemp())["path"])
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                from test_work_items import page_target
                sid = page_target(cdp)
                cdp.call("Page.enable", {}, sid)
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
                cdp.call("Page.navigate", {"url": out.as_uri()}, sid)
                self.until(cdp, sid, "!!document.querySelector('.tab')", "the file")
                cdp.js("[...document.querySelectorAll('.tab')].find(t => /Work items/.test(t.textContent)).click()", sid)
                self.until(cdp, sid, "!!document.querySelector('#work h1')", "Work items")
                self.assertEqual(cdp.js("document.querySelectorAll('#impBtn, #expBtn').length", sid), 0)
                self.assertEqual(cdp.js("document.querySelectorAll('#work .vicons, #work .fline').length", sid), 0)


if __name__ == "__main__":
    unittest.main()
