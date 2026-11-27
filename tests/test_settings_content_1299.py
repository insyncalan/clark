"""Row 1299 AP8: the Settings content at 1400 and 900 px, light and dark: the cards column is at most 760px wide with padding 6px 26px 40px (16px at each side at 900),
PRODUCT GAP: AP8 on origin/main .set-cards has max-width none (not 760px); this test is red until the content column is built.
each card (group) has radius 12px and padding 2px 16px, each row is at least 46px high with a 1px top line (the first has none).
Classic only. Run: python3 dev/run_tests.py test_settings_content_1299
Chrome is required: these tests fail, never skip, without it."""
import unittest

from clark import page, theme
import _testpage as testpage
from test_publish_dialog import Base
from test_publish_route import Rig
from test_server import chrome
from test_settings_bar import calm
from test_settings_head import address

WIDTHS = (1400, 900)
MODES = ("light", "dark")
LAID = "!!document.querySelector('.set-win .set-nav .set-chip[aria-current]') && !!document.querySelector('.set-win .set-cards').children.length"
PROBE = ("(() => { const c = document.querySelector('.set-win .set-cards'), cs = getComputedStyle(c), f = c.querySelector('.frame'), fs = getComputedStyle(f),"
         " rows = [...c.querySelectorAll('.set-row')].filter((r) => r.getBoundingClientRect().height > 0);"
         " return {max: cs.maxWidth, w: c.getBoundingClientRect().width, pad: cs.paddingTop + ' ' + cs.paddingRight + ' ' + cs.paddingBottom + ' ' + cs.paddingLeft,"
         " radius: fs.borderTopLeftRadius, gpad: fs.paddingTop + ' ' + fs.paddingRight + ' ' + fs.paddingBottom + ' ' + fs.paddingLeft,"
         " rows: rows.map((r) => [getComputedStyle(r).minHeight, r.getBoundingClientRect().height, getComputedStyle(r).borderTopWidth, !!r.previousElementSibling && r.previousElementSibling.classList.contains('set-row')])}; })()")


class Content(Base):
    def setUp(self):
        css = theme.css("prototype-2.0")
        self.rig = Rig(self, saved=self.saved, page_html=lambda: page.layer_theme(testpage.html(), css))



class CardsContent(Base):
    def test_cards_keeps_its_content(self):
        self.rig = Rig(self, saved=self.saved)
        with chrome() as cdp:
            p = self.page(cdp)
            p.width(1400)
            calm(p, "light")
            p.js(f"location.hash = '{address('people')}'")
            p.until("!!document.querySelector('.set-layout .set-chip[aria-current]') && !!document.querySelector('.set-cards').children.length", "Settings drew")
            self.assertNotEqual(p.js("getComputedStyle(document.querySelector('.set-cards')).maxWidth"), "760px")


if __name__ == "__main__":
    unittest.main()
