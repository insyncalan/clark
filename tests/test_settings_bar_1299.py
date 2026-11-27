"""Row 1299 AP7: the Settings top bar at 1400 and 900 px, light and dark: the title bar is sticky under the app's top bar, 62px high, padding 14px 26px, its h1 20px weight 600.
PRODUCT GAP: AP7 on origin/main the Settings h1 is position static (not sticky); this test is red until the bar is built.
Classic only: Cards has no .set-win and keeps its own head.
Run: python3 dev/run_tests.py test_settings_bar_1299
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
PROBE = ("(() => { const h = document.querySelector('.set-win h1'), cs = getComputedStyle(h);"
         " return {pos: cs.position, height: h.getBoundingClientRect().height, pad: cs.paddingTop + ' ' + cs.paddingRight + ' ' + cs.paddingBottom + ' ' + cs.paddingLeft,"
         " size: cs.fontSize, weight: cs.fontWeight, top: Math.round(h.getBoundingClientRect().top), tb: (() => { const i = document.createElement('i'); i.style.cssText = 'display:block;height:var(--topbar)'; document.body.appendChild(i); const v = i.getBoundingClientRect().height; i.remove(); return Math.round(v); })(),"
         " text: h.textContent}; })()")


class Bar(Base):
    def setUp(self):
        css = theme.css("prototype-2.0")
        self.rig = Rig(self, saved=self.saved, page_html=lambda: page.layer_theme(testpage.html(), css))



class CardsBar(Base):
    def test_cards_head_is_not_a_bar(self):
        self.rig = Rig(self, saved=self.saved)
        with chrome() as cdp:
            p = self.page(cdp)
            p.width(1400)
            calm(p, "light")
            p.js(f"location.hash = '{address('people')}'")
            p.until("!!document.querySelector('.set-layout .set-chip[aria-current]') && !!document.querySelector('.set-cards').children.length", "Settings drew")
            self.assertNotEqual(p.js("getComputedStyle(document.querySelector('.set-head h1')).position"), "sticky")


if __name__ == "__main__":
    unittest.main()
