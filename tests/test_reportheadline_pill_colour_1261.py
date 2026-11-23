"""Row 1261: the Report headline's pill icon is 14px and its headline is in --text, as the approved mock-up draws them
(mockups/1261-headline-template/headline-approved.html:16-20), in the Classic look at 1400 and 900 (the 900 cases are skipped while
test_server.PAUSED_900 is set). The Cards look keeps main's 16px icon and --heading colour. Fictional data only.

Run: python3 dev/run_tests.py test_reportheadline_pill_colour_1261
"""
import unittest

import test_reportheadline_eye_1261 as base
from test_report_editor import tearDownModule  # noqa: F401
from test_server import chrome
import _testpage as testpage
from _real_server import real_server

PROBE = """(function(){ function tok(v){ var e = document.createElement('i'); e.style.color = 'var(' + v + ')'; document.body.appendChild(e); var c = getComputedStyle(e).color; e.remove(); return c; }
  var s = document.querySelector('[data-id="%s"] .tpl-rh-pill svg'), h = document.querySelector('[data-id="%s"] .tpl-rh-h');
  if (!s || !h) return null; var r = s.getBoundingClientRect();
  return {w: getComputedStyle(s).width, h: getComputedStyle(s).height, rw: r.width, rh: r.height, color: getComputedStyle(h).color, text: tok('--text'), heading: tok('--heading')}; })()"""


class PillColour(base.Eye):
    def test_classic_icon_is_14px_and_headline_is_the_text_colour_at_1400_and_900_in_light_and_dark(self):
        for width, theme in ((1400, "light"), (1400, "dark"), (900, "light"), (900, "dark")):
            with self.subTest(width=width, theme=theme), chrome() as cdp:
                p = self.sized(cdp, width, theme)
                p.until(f"!!document.querySelector('[data-id=\"{self.on}\"] .tpl-rh-pill svg')", "drew")
                m = p.js(PROBE % (self.on, self.on))
                self.assertEqual((m["w"], m["h"]), ("14px", "14px"), m)
                self.assertEqual((m["rw"], m["rh"]), (14, 14), m)
                self.assertEqual(m["color"], m["text"], m)
                self.assertNotEqual(m["text"], m["heading"], "the two tokens differ, so the pin tells them apart")

    def test_cards_keeps_the_16px_icon_and_the_heading_colour(self):
        self.s.close()
        self.s = real_server(self.store.path, self.store.data_for, page_html=lambda: testpage.html(), seam=self.seam)
        self.addCleanup(self.s.close)
        with chrome() as cdp:
            p = self.sized(cdp, 1400, "light")
            p.until(f"!!document.querySelector('[data-id=\"{self.on}\"] .tpl-rh-pill svg')", "drew")
            m = p.js(PROBE % (self.on, self.on))
            self.assertEqual((m["w"], m["h"]), ("16px", "16px"), m)
            self.assertEqual(m["color"], m["heading"], m)


# the Eye tests are run by their own module; only this module's two run here
for _n in [n for n in dir(base.Eye) if n.startswith("test_")]:
    setattr(PillColour, _n, None)

if __name__ == "__main__":
    unittest.main()
