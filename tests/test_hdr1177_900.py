"""Item 1177: at 900 px search and ask clark leave the header row and are the first two entries of the profile menu; at 1400 px they stay in the header.

Run: python3 dev/run_tests.py test_hdr1177_900
Chrome is required: these tests fail, never skip, without it.
"""
import unittest

from test_inline_67 import size
from test_report_editor import Base
from test_server import chrome

IN_HEADER = "!!document.querySelector('.top %s')"
ITEMS = "[].slice.call(document.querySelectorAll('#profile-menu [role=menuitem]'))"
SEARCH, ASK = "#pal-btn", "#ask-btn"


def shown(sel):      # a button is in the header row when it is in .top and takes room there
    return ("(function(){var e=document.querySelector('.top %s'); return !!e && e.getClientRects().length > 0 && e.getBoundingClientRect().width > 0;})()" % sel)


class HeaderAt900(Base):
    def at(self, cdp, width):
        p = self.visit(cdp)
        size(cdp, p, width, 700)
        p.until(f"window.innerWidth === {width}", f"the window is {width} wide")
        p.until("!!document.querySelector('.top #profile-btn')", "the profile circle is drawn")
        return p

    def open_menu(self, p):
        p.js("document.querySelector('#profile-btn').focus()")
        p.until("(() => { if (document.querySelector('#profile-menu')) return true; "
                "if (Date.now() - (window.__menuTried || 0) > 1000) { window.__menuTried = Date.now(); document.querySelector('#profile-btn').click(); } "
                "return !!document.querySelector('#profile-menu'); })()", "the menu opened")

    def test_at_900_search_and_ask_are_not_in_the_header_row(self):
        with chrome() as cdp:
            p = self.at(cdp, 900)
            self.assertFalse(p.js(shown(SEARCH)), "item 1177: at 900 the search button is still in the header row")
            self.assertFalse(p.js(shown(ASK)), "item 1177: at 900 the ask clark button is still in the header row")

    def test_at_900_the_profile_menu_has_search_first_and_ask_second(self):
        with chrome() as cdp:
            p = self.at(cdp, 900)
            self.open_menu(p)
            got = p.js(f"{ITEMS}.slice(0, 2).map(function(e){{return [e.dataset.kind || '', e.textContent.trim().toLowerCase()];}})")
            self.assertEqual(len(got), 2, "item 1177: the open profile menu at 900 has fewer than two entries")
            self.assertEqual(got[0][0], "search", "item 1177: the first entry of the profile menu at 900 is not search")
            self.assertEqual(got[1][0], "ask", "item 1177: the second entry of the profile menu at 900 is not ask clark")
            self.assertIn("ask clark", got[1][1], "item 1177: the second entry's words are not ask clark")

    def test_at_900_the_rest_of_the_menu_follows_search_and_ask(self):
        with chrome() as cdp:
            p = self.at(cdp, 900)
            self.open_menu(p)
            kinds = p.js(f"{ITEMS}.map(function(e){{return e.dataset.kind || '';}})")
            self.assertTrue(len(kinds) > 2, "item 1177: the menu at 900 has nothing after search and ask clark")
            self.assertEqual(kinds[:2], ["search", "ask"], "item 1177: search and ask clark are not the first two entries")
            self.assertEqual(kinds.count("search"), 1, "item 1177: search is in the menu more than once")
            self.assertEqual(kinds.count("ask"), 1, "item 1177: ask clark is in the menu more than once")
            words = p.js(f"{ITEMS}.map(function(e){{return e.textContent;}}).join('|')")
            self.assertIn("Settings", words, "item 1177: Settings is missing from the menu at 900")
            self.assertIn("Help", words, "item 1177: Help is missing from the menu at 900")

    def test_at_1400_search_and_ask_are_in_the_header(self):
        with chrome() as cdp:
            p = self.at(cdp, 1400)
            self.assertTrue(p.js(shown(SEARCH)), "item 1177: at 1400 the search button is not in the header")
            self.assertTrue(p.js(shown(ASK)), "item 1177: at 1400 the ask clark button is not in the header")

    def test_at_1400_the_profile_menu_does_not_repeat_search_and_ask(self):
        with chrome() as cdp:
            p = self.at(cdp, 1400)
            self.open_menu(p)
            kinds = p.js(f"{ITEMS}.map(function(e){{return e.dataset.kind || '';}})")
            self.assertNotIn("search", kinds, "item 1177: at 1400 the menu repeats search")
            self.assertNotIn("ask", kinds, "item 1177: at 1400 the menu repeats ask clark")

    def test_the_header_is_one_row_at_900_with_the_profile_circle_inside_it(self):
        with chrome() as cdp:
            p = self.at(cdp, 900)
            got = p.js("(function(){var h=document.querySelector('.top').getBoundingClientRect(), b=document.querySelector('.top #profile-btn').getBoundingClientRect();"
                       "return [Math.round(h.height), b.top >= h.top - 1 && b.bottom <= h.bottom + 1];})()")
            self.assertEqual(got, [129, True], "item 1177: the 900 header is not 129 px tall with the profile circle inside it")


if __name__ == "__main__":
    unittest.main()
