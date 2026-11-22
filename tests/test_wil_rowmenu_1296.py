"""Row 1296: a half-width Work items list row (ul.wil-lines li) opens the same row menu as a list row (tr in the table): right click, and
Shift+F10 or the menu key on the focused row, in Edit and in View, at 1400 and 900. No new action. Fictional data only.

Run: python3 dev/run_tests.py test_wil_rowmenu_1296   (headless Chrome; fails, never skips, without it)
"""
import json
import unittest

from clark import changes

from test_report_editor import Base as PageBase, tearDownModule  # noqa: F401
from test_row_menu import key, right_click
from test_server import chrome, wait
from test_tpl_workitems import plant
from _demo import USER

ENTRIES = "[...document.querySelectorAll('.rowmenu [role=menuitem]')].map(b => [b.dataset.rm, b.querySelector('b').textContent, b.getAttribute('aria-disabled') === 'true'])"


class HalfWidthMenu(PageBase):
    def setUp(self):
        super().setUp()
        plant(self)
        with self.store.step("dashboard", USER) as st:
            text = st.create("report_sections", {"project": "ABC", "type": "text", "title": "Fictional notes", "sort_order": 1})
        self.full = self.add(after=None, beside=0)
        self.half = self.add(after=text, beside=1)

    def add(self, after, beside):
        req = {"project": "ABC", "kind": "report_sections", "op": changes.NEW, "values": {"type": "workitems", "title": "Due soon"}, "after": after}
        if beside:
            req["beside"] = 1
        status, got = self.real_change(req)
        self.assertEqual(status, 200, got)
        ref = got["ref"]
        status, got = self.real_change({"project": "ABC", "kind": "report_sections", "op": changes.UPDATE, "id": ref,
                                        "changes": {"body": json.dumps({"mode": "all", "columns": ["id", "owner"], "owner": ["Pat Demo", "Lee Demo"]})}})
        self.assertEqual(status, 200, got)
        return ref

    def menu(self, cdp, sid, selector):
        right_click(cdp, sid, selector)
        self.assertTrue(self.wait_for(cdp, sid, "!!document.querySelector('.rowmenu [role=menu]')"), "the menu opened")
        self.assertTrue(self.wait_for(cdp, sid, "document.querySelector('.rowmenu').getAnimations({subtree: true}).length === 0"), "the menu settled")
        return cdp.js(ENTRIES, sid)

    def wait_for(self, cdp, sid, expr):
        return wait(lambda: cdp.js(expr, sid), 10)

    def close(self, cdp, sid):
        key(cdp, sid, "Escape")
        self.assertTrue(self.wait_for(cdp, sid, "!document.querySelector('.rowmenu')"), "the menu closed")

    def run_at(self, width, edit):
        with chrome() as cdp:
            sid = self.visit(cdp).sid
            cdp.call("Emulation.setFocusEmulationEnabled", {"enabled": True}, sid)
            cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1100, "deviceScaleFactor": 1, "mobile": False}, sid)
            if edit:
                cdp.js("document.querySelector('[data-mode=edit]').click()", sid)
                self.assertTrue(self.wait_for(cdp, sid, "document.querySelector('#report').dataset.mode === 'edit'"), "Edit mode")
            table = f"[data-id=\"{self.full}\"] .wil-table tbody tr[data-id=\"{self.a_due}\"]"
            line = f"[data-id=\"{self.half}\"] .wil-lines li[data-id=\"{self.a_due}\"]"
            self.assertTrue(self.wait_for(cdp, sid, f"!!document.querySelector({json.dumps(line)}) && !!document.querySelector({json.dumps(table)})"), "both lists drew")
            self.assertTrue(cdp.js(f"!!document.querySelector({json.dumps(line)}).offsetParent", sid), "the half-width rows are the ones shown")
            want = self.menu(cdp, sid, table)
            self.close(cdp, sid)
            self.assertGreaterEqual(len(want), 10, "the list row's menu has its entries")
            got = self.menu(cdp, sid, line)
            self.assertEqual(got, want, "the half-width row has the list row's menu: same entries, same order, same state")
            self.close(cdp, sid)
            if edit:
                cdp.js(f"document.querySelector({json.dumps(line)}).focus()", sid)
                key(cdp, sid, "F10", shift=True)
                self.assertTrue(self.wait_for(cdp, sid, "!!document.querySelector('.rowmenu [role=menu]')"), "Shift+F10 opens it")
                self.close(cdp, sid)
                self.assertTrue(self.wait_for(cdp, sid, f"document.activeElement && document.activeElement.dataset.id === {json.dumps(self.a_due)} && !!document.activeElement.closest('.wil-lines')"),
                                "focus is back on the half-width row")

    def test_a_half_width_row_has_the_list_rows_menu_in_edit_at_1400_and_900(self):
        for width in (1400, 900):
            with self.subTest(width=width):
                self.run_at(width, True)

    def test_a_half_width_row_has_the_list_rows_menu_in_view_at_1400_and_900(self):
        for width in (1400, 900):
            with self.subTest(width=width):
                self.run_at(width, False)


if __name__ == "__main__":
    unittest.main()
