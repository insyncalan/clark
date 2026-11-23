"""Row 1273: Group by has eight choices in the code (logic/board.js GROUPS); on the Board "Nothing" is not offered, so 7 show.

Run: python3 dev/run_tests.py test_group_by_eight_items_1273
"""
import re
import unittest

import test_work_board_page as wb
from test_work_board_page import setUpModule, tearDownModule  # noqa: F401  (the one shared Chrome of the board file)
from test_server import chrome  # noqa: F401  (the harness: this file drives Chrome, so the tier reader sees it)
from test_work_filters import click, key
from _paths import ROOT

ICONS_JS = (ROOT / "src" / "clark" / "page" / "src" / "menuIcons.js").read_text(encoding="utf-8")
GROUP_ICON = dict(re.findall(r'(\w+): "(\w+)"', re.search(r"const GROUP_ICON = \{(.*?)\};", ICONS_JS, re.S).group(1)))

BOARD_JS = (ROOT / "src" / "clark" / "page" / "src" / "logic" / "board.js").read_text(encoding="utf-8")


class GroupByEight(wb.Base):
    def group_icons(self, cdp, sid):
        """The icon name drawn on each Group by item (data-icn of its svg), the View menu opened and closed again."""
        click(cdp, sid, "#viewMenu")
        self.until(cdp, sid, "!!document.querySelector('#viewMenuList')", "the View menu")
        got = cdp.js("Object.fromEntries([...document.querySelectorAll('#viewMenuList [role^=menuitem]')].filter(b => b.dataset.kind.startsWith('group:')).map(b => [b.dataset.kind, b.querySelector('svg.mi').dataset.icn]))", sid)
        key(cdp, sid, "Escape")
        self.until(cdp, sid, "!document.querySelector('#viewMenuList')", "the View menu closed")
        return got

    def test_group_by_eight_items_1273(self):
        """The code holds eight groups; the Table offers all eight, the Board offers seven (Nothing is filtered out), at 1400 and 900."""
        block = BOARD_JS[BOARD_JS.index("export const GROUPS"):BOARD_JS.index("export const LANE_GROUPS")]
        ids = re.findall(r'id: "(\w+)"', block)
        self.assertEqual(len(ids), 8, ids)
        self.assertIn("nothing", ids)
        for width in (1400, 900):
            with self.subTest(width=width), wb.shared.page() as cdp:
                sid = self.visit(cdp, width=width)
                table = [k for k, _, _ in self.view_items(cdp, sid) if k.startswith("group:")]
                self.assertEqual(len(table), 8, table)
                self.assertEqual(self.group_icons(cdp, sid), {f"group:{i}": GROUP_ICON[i] for i in ids}, "Table: each Group by item has its menuIcons.js icon")
                self.board(cdp, sid, "status")
                board = [k for k, _, _ in self.view_items(cdp, sid) if k.startswith("group:")]
                self.assertEqual(len(board), 7, board)
                self.assertNotIn("group:nothing", board)
                self.assertEqual(self.group_icons(cdp, sid), {f"group:{i}": GROUP_ICON[i] for i in ids if i != "nothing"}, "Board: each Group by item has its menuIcons.js icon")


if __name__ == "__main__":
    unittest.main()
