"""Row 1299: in Cards the Settings content keeps its width: .set-cards max-width is not 760px.
Run: python3 dev/run_tests.py test_settings_content_1299
Chrome is required: these tests fail, never skip, without it."""
import unittest

from test_publish_dialog import Base
from test_publish_route import Rig
from test_server import chrome
from test_settings_bar import calm
from test_settings_head import address


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
