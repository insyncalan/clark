"""Row 1273 (Classic): Group by, Move to and the Add menu take the prototype's look, and no other menu does.

Reads rules.css and Board.jsx (no browser): the rules are scoped to the three menus by their labels; the Move to head holds the card id.
Run: python3 dev/run_tests.py test_menus_prototype_three_1273
"""
import re
import unittest

from _paths import ROOT

RULES = re.sub(r"/\*.*?\*/", "", (ROOT / "src" / "clark" / "themes" / "prototype-2.0" / "rules.css").read_text(encoding="utf-8"), flags=re.S)
BOARD = (ROOT / "src" / "clark" / "page" / "src" / "edit" / "Board.jsx").read_text(encoding="utf-8")
GROUP = '.ddmenu[aria-label="Group by"]'
GROUP_ID = '#viewMenuList.ddmenu[aria-label="Group by"]'
MOVE = '.ddmenu[aria-label^="Move "][aria-label$=" to"]'
ADD = ".wil-add .ddmenu"
ADD_ALL = "#newBtnMenu.ddmenu"


def rules():
    out = []
    for sel, body in re.findall(r"([^{}@]+)\{([^{}]*)\}", RULES):
        out.append(([" ".join(s.split()) for s in sel.split(",")], " ".join(body.split())))
    return out


def decls(selector, prop):
    """The value of `prop` in the last rule that names `selector`, or None."""
    found = None
    for sels, body in rules():
        if selector in sels:
            m = re.search(rf"(?:^|; ){prop}\s*:\s*([^;]+)", body)
            if m:
                found = m.group(1).strip()
    return found


class ThreeMenus(unittest.TestCase):
    def test_width_224_for_the_three(self):
        for sel in (GROUP, MOVE, ADD, ADD_ALL):
            self.assertEqual(decls(sel, "min-width"), "224px", sel)

    def test_item_text_15px(self):
        for sel in (GROUP + ' [role="menuitemradio"]', MOVE + ' [role="menuitem"]', ADD + ' [role="menuitem"]', ADD_ALL + ' [role="menuitem"]'):
            self.assertEqual(decls(sel, "font-size"), "calc(var(--size-body) + 1px)", sel)  # 15px in Chrome (the Classic body is 14px); the 1195 pin forbids a bare px size

    def test_icon_gap_34px(self):
        self.assertEqual(decls(GROUP + " .mi", "margin-right"), "34px")
        self.assertEqual(decls(MOVE + " .mi", "margin-right"), "34px")
        self.assertEqual(decls(ADD + ' [role="menuitem"]', "gap"), "34px")
        self.assertEqual(decls(ADD_ALL + ' [role="menuitem"]', "gap"), "34px")

    def test_tick_before_the_icon_in_group_by_and_move_to(self):
        self.assertEqual(decls(GROUP + ' [role="menuitemradio"] .ck', "order"), "-1")
        self.assertEqual(decls(MOVE + ' [role="menuitem"] > .ck', "order"), "-1")
        self.assertEqual(decls(MOVE + ' [role="menuitem"]:not(:has(> .ck))::before', "order"), "-1", "the items without a tick keep the tick's column free")

    def test_move_to_head_is_in_capitals(self):
        self.assertEqual(decls(MOVE + " .mh.caps", "text-transform"), "uppercase")

    def test_no_other_menu_is_named(self):
        """Every selector of the Row 1273 block names one of the three menus."""
        text = (ROOT / "src" / "clark" / "themes" / "prototype-2.0" / "rules.css").read_text(encoding="utf-8")
        start = text.index("/* Row 1273")
        block = text[start:text.index("/*", start + 2)]  # the one Row 1273 comment and the rules after it, up to the next comment
        block = re.sub(r"/\*.*?\*/", "", block, flags=re.S)
        for sels, _ in [([" ".join(s.split()) for s in a.split(",")], b) for a, b in re.findall(r"([^{}]+)\{([^{}]*)\}", block)]:
            for s in sels:
                self.assertTrue(s.startswith((GROUP, GROUP_ID, MOVE, ADD, ADD_ALL)), f"the rule {s!r} is not scoped to Group by, Move to or Add")

    def test_the_move_to_head_holds_the_card_id(self):
        self.assertIn("head: `Move ${id} to`", BOARD)
        self.assertNotIn("head: `Move to ${groupLabel(g)}`", BOARD)


if __name__ == "__main__":
    unittest.main()
