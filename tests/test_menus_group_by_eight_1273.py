"""Row 1273 (AP8 and AP10): the Group by menu has its 8 items each with an icon, and the three changed menus (Group by, Add, Move to) stay inside a 900 px high window.

Real browser, 1400 and 900 px wide (the 900 cases are paused in test_server.PAUSED_900 and run when it is switched off).
AP11 (the three menus match the prototype pictures by eye, light and dark) has no automated test.
Run: python3 dev/run_tests.py test_menus_group_by_eight_1273
"""
import unittest

import test_work_board_page as wb
from test_work_board_page import setUpModule, tearDownModule  # noqa: F401  (the one shared Chrome of the board file)
from test_work_filters import click, key
from test_server import chrome  # noqa: F401

WIDTHS = (1400, 900)
HEIGHT = 900
EIGHT = ["Workstream", "Status", "Due", "Owner", "Priority", "Milestone", "Type", "Nothing"]
BOTTOM = "(() => { const r = document.querySelector(%r).getBoundingClientRect(); return [r.top, r.bottom, innerHeight]; })()"


class GroupByEight(wb.Base):
    def test_group_by_eight_items_1273(self):
        """On the list the Group by menu holds Workstream, Status, Due, Owner, Priority, Milestone, Type, Nothing, in that order, each line with an icon."""
        for width in WIDTHS:
            with self.subTest(width=width), wb.shared.page() as cdp:
                sid = self.visit(cdp, width=width, height=HEIGHT)
                click(cdp, sid, "#viewMenu")
                self.until(cdp, sid, "!!document.querySelector('#viewMenuList')", "the View menu")
                got = cdp.js("[...document.querySelectorAll('#viewMenuList [data-kind^=\"group:\"]')].map(b => [b.textContent.replace('\\u2713', '').trim(), b.dataset.kind, b.querySelectorAll('svg.mi').length])", sid)
                self.assertEqual([g[0] for g in got], EIGHT, got)
                self.assertEqual([g[1] for g in got], ["group:" + w.lower() for w in EIGHT], got)
                for g in got:
                    self.assertGreaterEqual(g[2], 1, f"no icon on {g[0]}: {got}")
                key(cdp, sid, "Escape")
                self.until(cdp, sid, "!document.querySelector('#viewMenuList')", "the View menu closed")


class MenusInsideTheWindow(wb.Base):
    def test_group_by_menu_bottom_edge_is_inside_the_window_1273(self):
        for width in WIDTHS:
            with self.subTest(width=width), wb.shared.page() as cdp:
                sid = self.visit(cdp, width=width, height=HEIGHT)
                click(cdp, sid, "#viewMenu")
                self.until(cdp, sid, "!!document.querySelector('#viewMenuList')", "the View menu")
                top, bottom, h = cdp.js(BOTTOM % "#viewMenuList", sid)
                self.assertEqual(h, HEIGHT)
                self.assertGreaterEqual(top, 0, f"{width}: {top}")
                self.assertLessEqual(bottom, h, f"Group by runs past the bottom at {width}: {bottom} > {h}")

    def test_add_menu_bottom_edge_is_inside_the_window_1273(self):
        for width in WIDTHS:
            with self.subTest(width=width), wb.shared.page() as cdp:
                sid = self.visit(cdp, width=width, height=HEIGHT)
                click(cdp, sid, "#newBtn")
                self.until(cdp, sid, "!!document.querySelector('#newBtnMenu')", "the Add menu")
                top, bottom, h = cdp.js(BOTTOM % "#newBtnMenu", sid)
                self.assertEqual(h, HEIGHT)
                self.assertGreaterEqual(top, 0, f"{width}: {top}")
                self.assertLessEqual(bottom, h, f"Add runs past the bottom at {width}: {bottom} > {h}")

    def test_move_to_menu_bottom_edge_is_inside_the_window_1273(self):
        """The Move to panel of the first and of the last cards of the board."""
        for width in WIDTHS:
            with self.subTest(width=width), wb.shared.page() as cdp:
                sid = self.visit(cdp, width=width, height=HEIGHT)
                self.board(cdp, sid, "status", lane="workstream")
                ids = cdp.js("[...document.querySelectorAll('[data-move]')].map(b => b.getAttribute('data-move'))", sid)
                self.assertTrue(ids, "no cards")
                for cid in [ids[0]] + ids[-3:]:
                    cdp.js(f"document.querySelector(\"[data-move='{cid}']\").scrollIntoView({{block: 'center'}})", sid)
                    click(cdp, sid, f"[data-move='{cid}']")
                    self.until(cdp, sid, "!!document.querySelector('.ddmenu')", "the menu")
                    top, bottom, h = cdp.js(BOTTOM % ".ddmenu", sid)
                    self.assertEqual(h, HEIGHT)
                    self.assertGreaterEqual(top, 0, f"{cid} {width}: {top}")
                    self.assertLessEqual(bottom, h, f"Move to of {cid} runs past the bottom at {width}: {bottom} > {h}")
                    key(cdp, sid, "Escape")
                    self.until(cdp, sid, "!document.querySelector('.ddmenu')", "the menu shut")


if __name__ == "__main__":
    unittest.main()
