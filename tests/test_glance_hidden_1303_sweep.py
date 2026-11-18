"""Row 1303 sweep: killers for the operands of the Add a tile wiring that the first test file leaves alive. No Chrome.

Run: python3 dev/run_tests.py test_glance_hidden_1303_sweep
Each test names the mutation it kills. They read the sources, like `Wiring` in test_glance_hidden_1303.
"""
import unittest

from _paths import SRC

PAGE = SRC / "clark" / "page" / "src"


def read(*parts):
    return PAGE.joinpath(*parts).read_text(encoding="utf-8")


class AddTileWiring(unittest.TestCase):
    def test_the_live_menu_shows_the_tile_that_was_picked_not_the_first_hidden_one(self):     # kills: onShow always showing hidden[0]
        self.assertIn("onShow={(key) => tools.glance.show(key)}", read("components", "Glance.jsx"))

    def test_the_live_menu_line_says_the_tile_is_hidden_from_the_published_report(self):      # kills: the line emptied in the words or not used by the items
        s = read("edit", "GlanceEdit.jsx")
        self.assertIn('line: "Hidden from the published report. Show it." }', s)
        self.assertIn("line: ADD_WORDS.line }))", s)

    def test_the_live_menu_button_and_items_use_the_add_icon(self):                           # kills: the eye icon on the button or on an item
        s = read("edit", "GlanceEdit.jsx")
        self.assertIn('icon={actionIcon("add")} btnCls="sec-add tileadd"', s)
        self.assertIn('id: t.key, icon: actionIcon("add"), name:', s)

    def test_the_live_menu_opens_to_the_left_and_has_no_chevron(self):                        # kills: `left` or chevron={false} dropped
        self.assertIn("menuLabel={ADD_WORDS.add} left chevron={false}", read("edit", "GlanceEdit.jsx"))

    def test_the_live_menu_names_an_own_tile_by_its_label_and_a_built_in_one_by_its_title(self):   # kills: the own / built-in branches swapped or one dropped
        self.assertIn("name: t.own ? t.label : TILE_TITLES[t.key],", read("edit", "GlanceEdit.jsx"))

    def test_the_template_menu_names_an_own_tile_by_its_label_and_a_built_in_one_by_its_title(self):   # kills: the own / built-in branches swapped or one dropped
        self.assertIn("title: t.own ? t.label : TILE_TITLES[t.key] }))}", read("edit", "templates", "GlanceTemplate.jsx"))

    def test_the_template_menu_item_for_a_hidden_tile_has_the_hidden_words_and_the_add_icon(self):   # kills: hiddenLine emptied, own help used as the line, the name replaced, the eye icon
        s = read("edit", "templates", "glanceTileEditor.jsx")
        self.assertIn('hiddenLine: "Hidden from the published report. Show it."', s)
        self.assertIn('{ id: `show:${t.key}`, icon: actionIcon("add"), name: t.title, line: WORDS.hiddenLine }', s)


if __name__ == "__main__":
    unittest.main()
