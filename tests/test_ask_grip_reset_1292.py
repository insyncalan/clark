"""Row 1292, rule 1: a double-click on the ask panel's grip puts the panel back to its usual width and forgets the kept width.

Run: python3 dev/run_tests.py test_ask_grip_reset_1292
Headless Chrome, the real page, the stub of test_ask_panel for the server's ask. Widths 1400 and 900 only. The drag is real mouse input.
"""
import unittest

import _testpage as testpage
from _real_server import real_server
from clark import page, theme as themes
from test_ask_panel import Stub
from test_report_editor import Base
from test_server import chrome

WIDTH = "Math.round(document.querySelector('#ask-panel').getBoundingClientRect().width)"
KEPT = "(function(){try{return localStorage.getItem('clark.askWidth')}catch(e){return 'x'}})()"


class GripReset(Base):
    THEME = "prototype-2.0"                                 # Classic; the Cards class below serves the page without a Theme

    def setUp(self):
        super().setUp()
        self.s.close()
        css = themes.css(self.THEME) if self.THEME else None
        self.s = real_server(self.store.path, self.store.data_for, page_html=lambda: page.layer_theme(testpage.html(), css) if css else testpage.html(), seam=self.seam)
        self.addCleanup(self.s.close)
        self.stub = Stub()
        self.s.httpd.ask = self.stub

    def open_panel(self, cdp, width):
        p = self.visit(cdp)
        cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-reduced-motion", "value": "reduce"}]}, p.sid)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
        p.key("/", code="Slash", vk=191)
        p.until("!!document.querySelector('#ask-panel')", "the panel opened on /")
        p.until("document.querySelector('#ask-panel').getAnimations().length === 0", "risen")
        p.until("document.querySelector('#ask-box') && !document.querySelector('#ask-send').disabled", "ready")
        return p

    def widen(self, p):
        gx, gy, _ = p.box("#ask-grip")
        p.mouse("mousePressed", gx, gy, 1)
        for step in range(1, 5):
            p.mouse("mouseMoved", gx - 20 * step, gy, 1)
        p.mouse("mouseReleased", gx - 80, gy, 0)

    def double_click(self, p):
        gx, gy, _ = p.box("#ask-grip")
        for n in (1, 2):
            p.cdp.call("Input.dispatchMouseEvent", {"type": "mousePressed", "x": gx, "y": gy, "button": "left", "buttons": 1, "clickCount": n}, p.sid)
            p.cdp.call("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": gx, "y": gy, "button": "left", "buttons": 0, "clickCount": n}, p.sid)

    def check(self, size):
        with chrome() as cdp:
            p = self.open_panel(cdp, size)
            usual = p.js(WIDTH)
            self.widen(p)
            wide = p.js(WIDTH)
            self.assertGreater(wide, usual + 40, "the drag made it wider")
            self.assertEqual(str(wide), p.js(KEPT), "the dragged width is kept")
            self.double_click(p)
            p.until(f"{WIDTH} === {usual}", "a double-click on the grip brings back the usual width")
            self.assertIsNone(p.js(KEPT), "the kept width is forgotten")
            self.assertEqual(p.js("document.documentElement.style.getPropertyValue('--ask-w')"), f"{usual}px", "the page follows the panel")
            p.reload()
            p.key("/", code="Slash", vk=191)
            p.until("!!document.querySelector('#ask-panel')", "opened again")
            self.assertEqual(p.js(WIDTH), usual, "the next visit opens at the usual width")

    def test_double_click_resets_at_1400(self):
        self.check(1400)

    def test_double_click_resets_at_900(self):
        self.check(900)


class GripResetCards(GripReset):
    THEME = None

    def check(self, size):
        """Row 1292 rule 1 is Classic only: in Cards a double-click on the grip does nothing (the width stays, and is kept)."""
        with chrome() as cdp:
            p = self.open_panel(cdp, size)
            self.widen(p)
            wide = p.js(WIDTH)
            self.double_click(p)
            p.js("new Promise(r => setTimeout(r, 300))")
            self.assertEqual(p.js(WIDTH), wide, "Cards: the width stays")
            self.assertEqual(p.js(KEPT), str(wide), "Cards: the kept width stays")


if __name__ == "__main__":
    unittest.main()
