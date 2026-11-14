"""Item 1170: Settings has a skip link, so Your name is two Tabs from the search box instead of seventeen, in a real browser at 1400 and 900 px.
Run: python3 dev/run_tests.py test_settings_skip_1170

The sixteen chips of the side list sit between the search box and the first card. The "Skip to settings" button comes right after the box; Enter on it
puts focus in the first card's heading, and the next Tab reaches Your name. Chrome is required: these tests fail, never skip, without it."""
import unittest

import test_settings_head
from test_server import chrome

WIDTHS = (1400, 900)
TAB = dict(code="Tab", vk=9)


class Skip(test_settings_head.Head):
    # Head's own tests belong to test_settings_head; this file borrows only its helpers
    test_C_the_title_the_help_line_and_a_chip_for_each_card_that_exists = test_C_a_click_scrolls_to_the_card_and_focuses_its_heading = None
    test_C_keyboard_tab_to_a_chip_and_enter = test_C_the_list_is_at_the_left_at_900_and_wider_and_a_row_of_chips_below_900 = test_C_text_size_and_contrast_in_light_and_dark = None

    def test_S_the_skip_link_is_the_next_tab_stop_after_the_search_box_and_reaches_your_name(self):
        for w in WIDTHS:
            with self.subTest(width=w), chrome() as cdp:
                p = self.page(cdp)
                self.open_settings(p, w)
                p.until("!!document.getElementById('ess-name')", "Essentials drew Your name")
                p.js("document.getElementById('set-search-box').focus()")
                p.key("Tab", **TAB)
                self.assertEqual(p.js("document.activeElement.className"), "skip skip-cards", "the first Tab from the search box lands on the skip link")
                self.assertEqual(p.js("document.activeElement.textContent"), "Skip to settings")
                self.assertTrue(p.js("(function(){var r = document.activeElement.getBoundingClientRect(); return r.top >= 0 && r.bottom > r.top && r.left >= 0 && r.right <= window.innerWidth;})()"),
                                "the link is on screen while it has focus")
                p.key("Enter", code="Enter", vk=13)
                self.assertEqual(p.js("document.activeElement.id"), "essentials-h", "Enter puts focus in the first card's heading")
                p.key("Tab", **TAB)
                self.assertEqual(p.js("document.activeElement.id"), "ess-name", "one more Tab reaches Your name: two Tabs from the search box, not seventeen")

    def test_S_the_skip_link_is_out_of_sight_until_it_has_focus_and_goes_while_searching(self):
        for w in WIDTHS:
            with self.subTest(width=w), chrome() as cdp:
                p = self.page(cdp)
                self.open_settings(p, w)
                p.until("!!document.querySelector('.skip-cards')", "the skip link is on the page")
                self.assertTrue(p.js("document.querySelector('.skip-cards').getBoundingClientRect().bottom <= 0"), "out of sight before it has focus")
                p.js("document.querySelector('.skip-cards').focus()")
                self.assertTrue(p.js("document.querySelector('.skip-cards').getBoundingClientRect().top >= 0"), "on screen with focus")
                p.js("var b = document.getElementById('set-search-box'); b.focus(); b.value = 'name'; b.dispatchEvent(new Event('input', { bubbles: true }))")
                p.until("!document.querySelector('.skip-cards') && !document.querySelector('.set-bar')", "the skip link goes with the chips while the box holds words")


if __name__ == "__main__":
    unittest.main()
