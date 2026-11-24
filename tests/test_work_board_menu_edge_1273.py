"""Row 1273: the Move to panel stays inside the window for the right-most cards, and the ticked line does not light up on hover like a choice. 1400 and 900 px only.

Run: python3 dev/run_tests.py test_work_board_menu_edge_1273
"""
import unittest

import test_work_board_page as wb
from test_work_board_page import setUpModule, tearDownModule  # noqa: F401  (the one shared Chrome of the board file)
from test_work_filters import click, hover
from test_server import chrome  # noqa: F401

WIDTHS = (1400, 900)


class MenuEdge(wb.Base):
    def test_the_move_to_panel_stays_inside_the_window_for_the_last_column(self):
        """With the own-column line added the panel is longer; a card in the right-most column with a menu must still open it inside the window sideways."""
        for width in WIDTHS:
            with self.subTest(width=width), wb.shared.page() as cdp:
                sid = self.visit(cdp, width=width)
                self.board(cdp, sid, "status", lane="workstream")
                ids = cdp.js("[...document.querySelectorAll('section.col')].map(c => [...c.querySelectorAll('[data-move]')].map(b => b.getAttribute('data-move')))", sid)
                last = [i for col in ids for i in col][-3:]
                self.assertTrue(last, "no cards")
                for cid in last:
                    click(cdp, sid, f"[data-move='{cid}']")
                    self.until(cdp, sid, "!!document.querySelector('.ddmenu')", "the menu")
                    box = cdp.js("(() => { const r = document.querySelector('.ddmenu').getBoundingClientRect(); return [r.left, r.right, r.top, r.bottom, innerWidth, innerHeight]; })()", sid)
                    self.assertGreaterEqual(box[0], 0, f"{cid} {box}")
                    self.assertLessEqual(box[1], box[4], f"{cid} {box}")
                    self.assertGreaterEqual(box[2], 0, f"{cid} top {box}")
                    self.assertLessEqual(box[3], box[5], f"{cid} the panel runs past the bottom edge at height {box[5]}: {box}")
                    cdp.call("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Escape", "code": "Escape", "windowsVirtualKeyCode": 27}, sid)
                    self.until(cdp, sid, "!document.querySelector('.ddmenu')", "the menu shut")

    def test_the_move_to_panel_of_a_left_most_card_opens_to_the_right_of_its_button_inside_the_window(self):
        """The panel opens to the right where there is room: a card in the first column has its panel starting at its button, not pushed left of it."""
        for width in WIDTHS:
            with self.subTest(width=width), wb.shared.page() as cdp:
                sid = self.visit(cdp, width=width)
                self.board(cdp, sid, "status", lane="workstream")
                cid = cdp.js("document.querySelector('section.col [data-move]').getAttribute('data-move')", sid)
                click(cdp, sid, f"[data-move='{cid}']")
                self.until(cdp, sid, "!!document.querySelector('.ddmenu')", "the menu")
                got = cdp.js(f"(() => {{ const m = document.querySelector('.ddmenu').getBoundingClientRect(), b = document.querySelector(\"[data-move='{cid}']\").getBoundingClientRect(); return [m.left, m.right, b.left, innerWidth]; }})()", sid)
                self.assertGreaterEqual(got[0], 0, f"{cid} {got}")
                self.assertLessEqual(got[1], got[3], f"{cid} {got}")
                self.assertGreaterEqual(got[0], got[2] - 1, f"the panel starts at the button, not left of it: {cid} {got}")
                cdp.call("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Escape", "code": "Escape", "windowsVirtualKeyCode": 27}, sid)
                self.until(cdp, sid, "!document.querySelector('.ddmenu')", "the menu shut")

    def test_the_group_by_panel_stays_inside_the_window_sideways_and_at_the_bottom(self):
        """The View menu's Group by panel at 900 height: left, right, top and bottom all inside the window."""
        for width in WIDTHS:
            with self.subTest(width=width), wb.shared.page() as cdp:
                sid = self.visit(cdp, width=width, height=900)
                self.board(cdp, sid, "status")
                click(cdp, sid, "#viewMenu")
                self.until(cdp, sid, "!!document.querySelector('#viewMenuList')", "the View menu")
                box = cdp.js("(() => { const r = document.querySelector('#viewMenuList').getBoundingClientRect(); return [r.left, r.right, r.top, r.bottom, innerWidth, innerHeight]; })()", sid)
                self.assertGreaterEqual(box[0], 0, f"{box}")
                self.assertLessEqual(box[1], box[4], f"{box}")
                self.assertGreaterEqual(box[2], 0, f"{box}")
                self.assertLessEqual(box[3], box[5], f"the Group by panel runs past the bottom edge: {box}")

    def test_the_ticked_line_does_not_light_up_on_hover_like_a_choice(self):
        """aria-disabled and aria-current: the line is not a choice, so the mouse over it must not give it the choice fill (.ddmenu [role=menuitem]:hover)."""
        for width in WIDTHS:
            with self.subTest(width=width), wb.shared.page() as cdp:
                sid = self.visit(cdp, width=width)
                self.board(cdp, sid, "status")
                a = self.id_of("Order the laptops")
                click(cdp, sid, f"[data-move='{a}']")
                self.until(cdp, sid, "!!document.querySelector('.ddmenu')", "the menu")
                sel = ".ddmenu [aria-current='true']"
                cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": 2, "y": 2}, sid)
                bg0 = cdp.js(f"getComputedStyle(document.querySelector({sel!r})).backgroundColor", sid)
                hover(cdp, sid, sel)
                bg1 = cdp.js(f"getComputedStyle(document.querySelector({sel!r})).backgroundColor", sid)
                cur = cdp.js(f"getComputedStyle(document.querySelector({sel!r})).cursor", sid)
                self.assertEqual(bg0, bg1, f"a line that is not a choice takes the choice fill on hover ({bg0} -> {bg1}, cursor {cur})")


if __name__ == "__main__":
    unittest.main()
