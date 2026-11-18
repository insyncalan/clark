"""Row 1303 part 1, in a real browser (written, not run by the author): a tile hidden with the eye leaves Edit view and Add a tile brings it back.
Tests at 1400 and 900 px only.

Run: python3 dev/run_tests.py test_glance_hidden_1303_browser
"""
import unittest

from test_glance_page import Setup, tearDownModule  # noqa: F401
from test_server import chrome

ADD = "document.querySelector('[data-glance-add] .tileadd')"
ITEMS = "[...document.querySelectorAll('#glance-add-menu [role^=menuitem]')]"


class HiddenLeavesEdit(Setup):
    def test_a_hidden_tile_is_not_drawn_in_edit_and_add_a_tile_lists_it_and_shows_it_again(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.show(cdp, width)
                p.edit()
                self.assertEqual(self.tiles(p), ["health", "overdue", "risks"], "Decisions needed is hidden by default and is not drawn")
                self.assertEqual(p.js("document.querySelectorAll('.tcell.is-hidden, .thid').length"), 0, "no dashed hidden tile and no tag")
                p.js("document.querySelector('[data-tile=overdue] [data-tile-eye]').click()")
                p.saved()
                self.assertEqual(self.tiles(p), ["health", "risks"], "the eye took Overdue actions out of Edit")
                p.js(ADD + ".click()")
                names = p.js(f"{ITEMS}.map(b => b.textContent)")
                self.assertTrue(any("Overdue actions" in n for n in names) and any("Decisions needed" in n for n in names), names)
                self.assertFalse(any("Project health" in n for n in names), "Project health is never listed")
                p.js(f"{ITEMS}.find(b => b.textContent.includes('Overdue actions')).click()")
                p.saved()
                p.until("JSON.stringify([...document.querySelectorAll('.glance > .tcell')].map(e => e.dataset.tile)) === JSON.stringify(['health','overdue','risks'])", "it is back, in its old place")
                self.assertEqual(self.rows()["overdue"]["hidden"], 0)

    def test_with_nothing_hidden_there_is_no_add_a_tile_on_the_live_section(self):
        with chrome() as cdp:
            p = self.show(cdp)
            p.edit()
            p.js(ADD + ".click()")
            p.js(f"{ITEMS}.find(b => b.textContent.includes('Decisions needed')).click()")
            p.saved()
            self.assertEqual(p.js("document.querySelectorAll('[data-glance-add]').length"), 0)

    def test_one_undo_of_the_hide_puts_the_tile_back_in_edit(self):
        with chrome() as cdp:
            p = self.show(cdp)
            p.edit()
            p.js("document.querySelector('[data-tile=risks] [data-tile-eye]').click()")
            p.saved()
            self.assertEqual(self.tiles(p), ["health", "overdue"])
            self.undo(p)
            self.assertEqual(self.tiles(p), ["health", "overdue", "risks"])


if __name__ == "__main__":
    unittest.main()
