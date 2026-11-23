"""Row 1281, Classic theme only: the profile menu lists Preview, Export to Excel, Export to Word, Publish..., and the circle's tooltip says
"Your menu: Preview, Export, Publish". The Cards theme (no theme layer) keeps the old order; that is pinned by test_profile_menu. 1400 and 900."""
import sys
import unittest

sys.path.insert(0, "tests")
import _testpage as testpage
from test_publish_dialog import Base, WIDTHS
from test_publish_route import Rig
from test_server import chrome
from clark import page, theme

TIP = "Your menu: Preview, Export, Publish"
ITEMS = ["Preview the page in a new tab", "Export to Excel", "Export to Word", "Publish…", "Published reports", "Settings", "Help"]


def classic_html():
    return page.layer_theme(testpage.html(), theme.css("prototype-2.0"))


class ClassicOrder(Base):
    def setUp(self):
        self.rig = Rig(self, saved=True, page_html=classic_html)

    def test_C_the_classic_page_is_the_themed_one(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.assertTrue(p.js("!!document.getElementById('theme')"))

    def test_C_the_classic_tooltip_follows_the_new_order(self):
        for w in WIDTHS:
            with self.subTest(width=w), chrome() as cdp:
                p = self.page(cdp)
                p.width(w, 700)
                self.assertEqual(p.js("document.querySelector('#profile-btn').title"), TIP)

    def test_C_the_classic_menu_lists_the_commands_in_the_new_order(self):
        for w in WIDTHS:
            with self.subTest(width=w), chrome() as cdp:
                p = self.page(cdp)
                p.width(w, 700)
                p.js("document.querySelector('#profile-btn').click()")
                p.until("!!document.querySelector('#profile-menu')", "the menu opened")
                got = p.js("[].map.call(document.querySelectorAll('#profile-menu [role=menuitem]'), function(e){return e.textContent})")
                self.assertEqual([g for g in got if g in ITEMS], ITEMS)


if __name__ == "__main__":
    unittest.main()
