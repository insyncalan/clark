"""The first-time section handle hint does not cover a heading at 360 and 420 px, and sits at or below the section top from 421 to 640 px.

Run: python3 dev/run_tests.py test_section_hint_phone

In a real browser, light and dark, Edit mode, the Dashboard: while the hint beside the first section handle shows, its box does not overlap
any section heading (the Title field in Edit), and it stays inside the window; from 421 to 640 px (and at 900 and 1400) its top is at or below the top of its section.
No new words: the test reads no text.
"""
import json
import time
import unittest

from _paths import ROOT

import test_peek as tp  # noqa: E402
from test_server import chrome, wait  # noqa: E402

BOXES = r"""(() => {
  const box = (e) => { const r = e.getBoundingClientRect(); return [r.left, r.top, r.right, r.bottom]; };
  const hint = document.querySelector('.sec-hint');
  if (!hint) return null;
  const heads = [...document.querySelectorAll('.secs .sec-title, .secs .sec-h')].filter((h) => h.getBoundingClientRect().width > 0);
  const sec = hint.closest('.sec');
  return { hint: box(hint), sec: sec ? box(sec) : null, heads: heads.map(box), width: document.documentElement.clientWidth };
})()"""


def overlap(a, b):
    return min(a[2], b[2]) - max(a[0], b[0]) > 0 and min(a[3], b[3]) - max(a[1], b[1]) > 0


class PhoneHint(unittest.TestCase):
    setUpClass = tp.Browser.__dict__["setUpClass"]
    tearDownClass = tp.Browser.__dict__["tearDownClass"]
    load_page = tp.Browser.load_page
    edit_mode = tp.Browser.edit_mode

    def test_the_hint_does_not_cover_a_heading_at_360_and_420(self):
        for width in (360, 420):
            with chrome() as cdp:
                s, sid = self.load_page(cdp, width)
                self.edit_mode(cdp, sid)
                cdp.js("document.querySelector('[data-view=dashboard]').click()", sid)
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.sec-hint')", sid)), f"the hint shows at {width}")
                for theme in ("light", "dark"):
                    cdp.js(f"document.documentElement.dataset.theme = {json.dumps(theme)}", sid)
                    time.sleep(0.4)
                    m = cdp.js(BOXES, sid)
                    where = f"{width} {theme}"
                    self.assertTrue(m["heads"], where)
                    for h in m["heads"]:
                        self.assertFalse(overlap(m["hint"], h), f"the hint covers a heading, {where}: {m['hint']} {h}")
                    self.assertGreaterEqual(m["hint"][0], 0, where)
                    self.assertLessEqual(m["hint"][2], m["width"], where)

    def test_the_hint_is_not_above_the_section_top(self):
        for width in (360, 420, 421, 480, 560, 640, 900, 1400):
            with chrome() as cdp:
                s, sid = self.load_page(cdp, width)
                self.edit_mode(cdp, sid)
                cdp.js("document.querySelector('[data-view=dashboard]').click()", sid)
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.sec-hint')", sid)), f"the hint shows at {width}")
                m = cdp.js(BOXES, sid)
                self.assertIsNotNone(m["sec"], width)
                self.assertGreaterEqual(m["hint"][1], m["sec"][1], f"the hint is above the section top at {width}: {m['hint']} {m['sec']}")
                for h in m["heads"] if width <= 640 else []:
                    self.assertFalse(overlap(m["hint"], h), f"the hint covers a heading at {width}: {m['hint']} {h}")


if __name__ == "__main__":
    unittest.main()
