"""Row 1273 (Classic): the capital-letter head of the Group by panel and of the Move to panel is drawn in the Classic look.

Pins the COMPUTED style in the page with the Classic layer on (not a stylesheet text): caption size, .08em spacing, capitals, normal weight. 1400 and 900 px only.

Run: python3 dev/run_tests.py test_menu_caps_head_look_1273
"""
import tempfile
import unittest

import test_work_board_page as wb
from test_work_board_page import setUpModule, tearDownModule  # noqa: F401  (the one shared Chrome of the board file)
from test_work_filters import click
from test_server import chrome  # noqa: F401  (the harness: this file drives Chrome, so the tier reader sees it)
from clark import page, theme
from _real_server import real_server

LOOK = ("(sel) => { const e = document.querySelector(sel), c = getComputedStyle(e), p = document.createElement('i');"
        " p.style.fontSize = 'var(--size-caption)'; document.body.appendChild(p); const cap = getComputedStyle(p).fontSize; p.remove();"
        " return {size: c.fontSize, cap: cap, ls: c.letterSpacing, tt: c.textTransform, w: c.fontWeight, theme: !!document.getElementById('theme')}; }")


class CapsHead(wb.Base):
    def setUp(self):
        super().setUp()
        self.s.close()
        css = theme.css("prototype-2.0")
        self.s = real_server(self.store.path, self.store.data_for, page_html=lambda: page.layer_theme(page.page_html(tempfile.mkdtemp()), css), seam=lambda real, which: real)
        self.addCleanup(self.s.close)

    def check(self, cdp, sid, sel, what):
        got = cdp.js(f"({LOOK})({sel!r})", sid)
        self.assertTrue(got["theme"], "the Classic layer is not on")
        self.assertEqual(got["size"], got["cap"], f"{what} size {got}")
        self.assertAlmostEqual(float(got["ls"][:-2]), 0.08 * float(got["size"][:-2]), places=1, msg=f"{what} spacing {got}")
        self.assertEqual(got["tt"], "uppercase", f"{what} {got}")
        self.assertEqual(got["w"], "400", f"{what} weight {got}")

    def test_the_group_by_head_is_drawn_at_caption_size_with_point_08_spacing_in_capitals(self):
        for width in (1400, 900):
            with self.subTest(width=width), wb.shared.page() as cdp:
                sid = self.visit(cdp, width=width)
                self.board(cdp, sid, "status")
                click(cdp, sid, "#viewMenu")
                self.until(cdp, sid, "!!document.querySelector('#viewMenuList .lab')", "the View menu")
                self.check(cdp, sid, "#viewMenuList .lab", "Group by head")

    def test_the_move_to_head_is_drawn_the_same_way(self):
        for width in (1400, 900):
            with self.subTest(width=width), wb.shared.page() as cdp:
                sid = self.visit(cdp, width=width)
                self.board(cdp, sid, "status", lane="workstream")
                click(cdp, sid, f"[data-move='{self.id_of('Order the laptops')}']")
                self.until(cdp, sid, "!!document.querySelector('.ddmenu .mh.caps')", "the Move to menu")
                self.check(cdp, sid, ".ddmenu .mh.caps", "Move to head")


if __name__ == "__main__":
    unittest.main()
