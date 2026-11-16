"""Row 1258 parts 3 and 4, the approved mockup: the history icon sits in a 30 px tile with an 8 px corner; the footer is 43 px high, its key tag 30 x 19, its input without a border. At 1400 and 900 px.
Run: python3 dev/run_tests.py test_peek_hist_foot_1258
"""
import unittest

import test_peek_body_1180 as B
from test_peek_latest import OVERDUE
from test_server import chrome, wait


class HistFoot(B.Body):
    def test_the_history_icon_is_a_30_px_tile_with_an_8_px_corner(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sent, sid = self.load(cdp, width, OVERDUE)
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('[data-pk-hrow] .pk-hicon')", sid)))
                got = cdp.js("(e => { const r = e.getBoundingClientRect(); return [r.width, r.height, getComputedStyle(e).borderTopLeftRadius]; })(document.querySelector('[data-pk-hrow] .pk-hicon'))", sid)
                self.assertEqual(got, [30, 30, "8px"])

    def test_the_footer_is_43_px_with_a_30_by_19_key_and_a_borderless_input(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sent, sid = self.load(cdp, width, OVERDUE)
                got = cdp.js("(r => [r('[data-pk-foot]'), r('.pk-foot-key'), getComputedStyle(document.querySelector('.pk-foot-in')).borderTopWidth])(s => { const b = document.querySelector(s).getBoundingClientRect(); return [b.width, b.height]; })", sid)
                self.assertEqual(got[0][1], 43)
                self.assertEqual(got[1], [30, 19])
                self.assertEqual(got[2], "0px")


for _n in [n for n in dir(HistFoot) if n.startswith("test_") and n not in ("test_the_history_icon_is_a_30_px_tile_with_an_8_px_corner", "test_the_footer_is_43_px_with_a_30_by_19_key_and_a_borderless_input")]:
    setattr(HistFoot, _n, None)

if __name__ == "__main__":
    unittest.main()
