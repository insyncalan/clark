"""Row 1273 (Classic): the first head of a card's Move to menu holds the card id ("Move <id> to"); Cards keeps "Move to Status".

Run: python3 dev/run_tests.py test_work_board_move_head_1273
The Cards words are pinned in test_work_board_page (Moves); here the same card is opened in the Classic layer, at 1400 and 900.
"""
import tempfile
import unittest

import test_work_board_page as wb
from test_work_board_page import setUpModule, tearDownModule  # noqa: F401  (the one shared Chrome of the board file)
from test_work_filters import click
from test_server import chrome  # noqa: F401  (the harness: this file drives Chrome, so the tier reader sees it)
from clark import page, theme
from _real_server import real_server


class MoveHead(wb.Base):
    def setUp(self):
        super().setUp()
        self.s.close()
        css = theme.css("prototype-2.0")
        self.s = real_server(self.store.path, self.store.data_for, page_html=lambda: page.layer_theme(page.page_html(tempfile.mkdtemp()), css), seam=lambda real, which: real)
        self.addCleanup(self.s.close)

    def test_the_classic_head_holds_the_card_id_and_the_lane_head_is_unchanged(self):
        for width in (1400, 900):
            with self.subTest(width=width), wb.shared.page() as cdp:
                sid = self.visit(cdp, width=width)
                self.board(cdp, sid, "status", lane="workstream")
                a = self.id_of("Order the laptops")
                click(cdp, sid, f"[data-move='{a}']")
                self.until(cdp, sid, "!!document.querySelector('.ddmenu')", "the menu")
                heads = cdp.js("[...document.querySelectorAll('.ddmenu .mh')].map(h => h.textContent)", sid)
                self.assertEqual(heads, [f"Move {a} to", "Move to Workstream"])


if __name__ == "__main__":
    unittest.main()
