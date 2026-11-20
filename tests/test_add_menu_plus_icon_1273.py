"""Row 1273 item 4: the Add menu of a Work items list shows the "+" icon on each line, not a letter chip, in Classic; Cards is unchanged.

Reads the theme CSS and the page (no browser): the Classic theme holds no rule that hides the menu line's icon or draws a letter in its place,
every Add line is still given the plus icon, and the Cards page carries no rule for the Add menu. The look in a browser is not run here.
"""
import re
import unittest

from _paths import ROOT

from clark import page, theme

NAME = "prototype-2.0"
SRC = ROOT / "src" / "clark" / "page" / "src"


def rules(css):
    return re.findall(r"([^{}]+)\{([^{}]*)\}", re.sub(r"/\*.*?\*/", "", css, flags=re.S))


class AddMenuPlusIcon(unittest.TestCase):
    def test_classic_keeps_the_menu_lines_and_hides_no_icon(self):
        css = theme.css(NAME)
        add = [(s, b) for s, b in rules(css) if ".wil-add .ddmenu" in s]
        self.assertTrue(any('[role="menuitem"]' in s and "display: flex" in b for s, b in add), "the Add menu lines are still laid out")
        for s, b in add:
            self.assertFalse(re.search(r"\.mi\b", s) and "display: none" in b, f"an Add menu rule hides the icon: {s.strip()}")

    def test_classic_draws_no_letter_chip_in_the_add_menu(self):
        for s, b in rules(theme.css(NAME)):
            if ".wil-add .ddmenu" in s:
                self.assertNotIn("::before", s, s.strip())
                self.assertNotIn("data-kind", s, s.strip())
                self.assertNotIn("content:", b, s.strip())

    def test_each_add_line_is_given_the_plus_icon(self):
        self.assertIn('icon: actionIcon("add")', (SRC / "components" / "NewTile.jsx").read_text(encoding="utf-8"))
        self.assertIn('add: "plus"', re.sub(r"\s+", " ", (SRC / "menuIcons.js").read_text(encoding="utf-8")))

    def test_cards_has_no_rule_for_the_add_menu(self):
        cards = page.page_html(branding=page.NO_BRAND, theme=None)
        self.assertNotIn(".wil-add .ddmenu", cards)
        self.assertIn(".wil-add .ddmenu", page.page_html(branding=page.NO_BRAND, theme=NAME))


if __name__ == "__main__":
    unittest.main()
