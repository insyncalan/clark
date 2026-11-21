"""Row 1346: the Draft sheet stays on the screen. Its width is the room left of the ask panel less 24 px, never wider than 560, at 1400 and 900.

Run: flock <lock> ~/bin/clark-chrome-slot env CLARK_CHROME=/usr/local/bin/clark-chrome python3 dev/run_tests.py test_ask_draft_width_1346
"""
import tempfile
import unittest

import test_ask_draft
from _real_server import real_server
from clark import page, theme
from test_server import chrome


class DraftWidth(test_ask_draft.Draft):
    """The Classic page (the Classic theme layered); Cards keeps its own width."""

    def setUp(self):
        super().setUp()
        self.s.close()
        css = theme.css("prototype-2.0")
        self.s = real_server(self.store.path, self.store.data_for, page_html=lambda: page.layer_theme(page.page_html(tempfile.mkdtemp()), css), seam=lambda real, which: real)
        self.s.httpd.ask = self.stub
        self.addCleanup(self.s.close)

    def test_the_sheet_fits_on_the_screen_with_24_px_to_spare_at_1400_and_900(self):
        for width in (1400, 900):
            with self.subTest(width=width):
                with chrome() as cdp:
                    p = self.drafted(cdp)
                    cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                    p.until("document.documentElement.clientWidth <= %d && document.documentElement.clientWidth > %d" % (width, width - 40), "the page is %d wide" % width)
                    p.until("document.querySelector('#ask-draft').getAnimations().length === 0", "the sheet has finished sliding in")
                    box = p.js("(() => { const r = document.querySelector('#ask-draft').getBoundingClientRect(); const q = document.querySelector('#ask-panel').getBoundingClientRect(); return [r.left, r.width, r.right, q.left]; })()")
                    left, w, right, panel = box
                    self.assertGreaterEqual(left, 23.5, "the sheet starts on the screen, with 24 px to spare when it is squeezed")
                    self.assertLessEqual(w, 560.5)
                    self.assertAlmostEqual(right, panel, delta=2)
                    self.assertAlmostEqual(w, min(560, panel - 24), delta=2)


_mine = DraftWidth.test_the_sheet_fits_on_the_screen_with_24_px_to_spare_at_1400_and_900
for _n in [n for n in dir(test_ask_draft.Draft) if n.startswith("test_")]:     # the inherited Draft tests run in their own module
    setattr(DraftWidth, _n, None)
DraftWidth.test_the_sheet_fits_on_the_screen_with_24_px_to_spare_at_1400_and_900 = _mine


if __name__ == "__main__":
    unittest.main()
