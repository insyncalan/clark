"""Row 1273 (Classic): Group by and Move to take the prototype's look, and no other menu does.

Reads rules.css and Board.jsx (no browser): the rules are scoped to the two menus by their ids and labels (the View menu by #viewMenuList, so the use case Group by menus are untouched); the Move to head holds the card id.
Run: python3 dev/run_tests.py test_menus_prototype_three_1273
"""
import re
import unittest

from _paths import ROOT

RULES = re.sub(r"/\*.*?\*/", "", (ROOT / "src" / "clark" / "themes" / "prototype-2.0" / "rules.css").read_text(encoding="utf-8") + (ROOT / "src" / "clark" / "themes" / "prototype-2.0" / "rules-2.css").read_text(encoding="utf-8"), flags=re.S)
BOARD = (ROOT / "src" / "clark" / "page" / "src" / "edit" / "Board.jsx").read_text(encoding="utf-8")
GROUP = "#viewMenuList.ddmenu"
MOVE = '.ddmenu[aria-label^="Move "][aria-label$=" to"]'


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
        # main's Row 1286 rule gives the three their width; the Row 1273 block does not repeat it
        self.assertRegex(RULES, r'#viewMenuList, #newBtnMenu, \.ddmenu\[aria-label\^="Add "\], \.ddmenu\[aria-label\^="Move "\]\[aria-label\$=" to"\] \{ min-width: 224px;')

    def test_item_text_15px(self):
        # main's Row 1286 rule gives the three their 15px; the Row 1273 block does not repeat it
        self.assertRegex(RULES, r'\.ddmenu\[aria-label\^="Move "\]\[aria-label\$=" to"\]\) :is\(\[role="menuitem"\], \[role="menuitemradio"\]:not\(\.hp\)\) \{[^}]*font-size: 15px')

    def test_icon_gap_10px_and_no_34(self):
        ten = "calc(var(--space-2) + 2px)"
        self.assertEqual(decls(GROUP + " .mi", "margin-right"), ten)
        self.assertEqual(decls(MOVE + ":not(#none) .mi", "margin-right"), ten)
        text = (ROOT / "src" / "clark" / "themes" / "prototype-2.0" / "rules-2.css").read_text(encoding="utf-8")      # row 1273 sits in rules-2.css (rules.css is at its size limit)
        start = text.index("/* Row 1273")
        self.assertNotIn("34px", text[start:text.index("/* Row 1314", start)])   # the 34px gap is gone from the Row 1273 block

    def test_item_padding_left_is_the_prototype_10px(self):
        self.assertEqual(decls(GROUP + ' [role="menuitemradio"]', "padding-left"), "calc(var(--space-2) + 2px)")   # the prototype's 7px 10px
        self.assertEqual(decls(MOVE + ':not(#none) [role="menuitem"]', "padding-left"), "calc(var(--space-2) + 2px)")

    def test_no_tick_slot_in_front_of_the_icon(self):
        # ruling 9A (DECISIONS-17-11 row 9): the tick is right of the word in every menu, so no slot is reserved before the icon
        text = (ROOT / "src" / "clark" / "themes" / "prototype-2.0" / "rules-2.css").read_text(encoding="utf-8")      # row 1273 sits in rules-2.css (rules.css is at its size limit)
        block = text[text.index("/* Row 1273"):text.index("/* Row 1314")]
        self.assertNotIn("::before", block)
        self.assertNotIn("order: -1", block)
        self.assertNotIn(".ck", re.sub(r"/\*.*?\*/", "", block, flags=re.S))

    def test_tick_is_right_of_the_word_in_group_by_and_move_to(self):
        # main's tick rule (order 1, margin-left auto) draws it after the word; the Row 1273 block must not move it
        self.assertEqual(decls('.ddmenu [role="menuitem"] > .ck', "order"), "1")
        self.assertEqual(decls('#viewMenuList [role="menuitemradio"] .ck', "order"), "1")
        self.assertEqual(decls('.ddmenu [role="menuitem"] > .ck', "margin-left"), "auto")

    def test_two_heads_are_in_capitals_and_no_other(self):
        for sel in ("#viewMenuList.ddmenu .lab.caps", MOVE + " .mh.caps.mh-card"):
            self.assertEqual(decls(sel, "text-transform"), "uppercase", sel)
        for sel, body in rules():
            if any("uppercase" in b for b in [body]) and any(s.startswith((GROUP, MOVE)) for s in sel):
                self.assertTrue(all(s in ("#viewMenuList.ddmenu .lab.caps", MOVE + " .mh.caps.mh-card") for s in sel if s.startswith((GROUP, MOVE))), sel)
        self.assertIn('class={it.card ? "mh caps mh-card" : "mh caps"}', BOARD)   # only the card's own head carries the mark, not the lane head
        self.assertIn("`Move to ${groupLabel(g)}`, card: true }", BOARD)

    def test_the_capitals_rule_sets_size_tracking_and_weight_on_both_heads(self):
        for sel in ("#viewMenuList.ddmenu .lab.caps", MOVE + " .mh.caps.mh-card"):
            self.assertEqual(decls(sel, "font-size"), "var(--size-caption)", sel)
            self.assertEqual(decls(sel, "letter-spacing"), ".08em", sel)   # the prototype .mh
            self.assertEqual(decls(sel, "font-weight"), "var(--weight-regular)", sel)   # .mh sets no weight: normal, not 600

    def test_move_to_items_centre_their_row(self):
        self.assertEqual(decls(MOVE + ' [role="menuitem"]', "display"), "flex")
        self.assertEqual(decls(MOVE + ' [role="menuitem"]', "align-items"), "center")

    def test_board_imports_classic_theme_from_contents(self):
        self.assertIn('import { classicTheme } from "../components/Contents.jsx"', BOARD)   # the Move head reads it

    def test_no_other_menu_is_named(self):
        """Every selector of the Row 1273 block names Group by or Move to, and none names the Add menu (row 1462)."""
        text = (ROOT / "src" / "clark" / "themes" / "prototype-2.0" / "rules-2.css").read_text(encoding="utf-8")      # row 1273 sits in rules-2.css (rules.css is at its size limit)
        start = text.index("/* Row 1273")
        block = text[start:text.index("/* Row", start + 2)]  # the Row 1273 comment and the rules after it, up to the next Row comment
        block = re.sub(r"/\*.*?\*/", "", block, flags=re.S)
        for sels, _ in [([" ".join(s.split()) for s in a.split(",")], b) for a, b in re.findall(r"([^{}]+)\{([^{}]*)\}", block)]:
            for s in sels:
                self.assertTrue(s.startswith((GROUP, MOVE)), f"the rule {s!r} is not scoped to Group by, Move to ")

    def test_the_move_to_head_holds_the_card_id(self):
        self.assertIn("classicTheme() ? `Move ${id} to` : `Move to ${groupLabel(g)}`", BOARD)   # Classic holds the id, Cards keeps Move to <group>


if __name__ == "__main__":
    unittest.main()
