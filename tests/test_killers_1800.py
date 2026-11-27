"""Killer for a surviving mutant of the peek footer (row 1258): giving .pk-foot padding 2px 0 still left a 43 px box because min-height wins.
The footer has no padding, so the 43 px is the content box. A real browser at 1400 and 900 px.
Run: python3 dev/run_tests.py -j 1 test_killers_1800
"""
import test_peek_footer_1258 as _test_peek_footer_1258
from test_server import chrome


class FootPadding(_test_peek_footer_1258.Footer):
    def test_the_footer_has_no_padding_so_the_43_px_is_the_content_box(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.opened(cdp, width)
                pad = cdp.js("(c => [c.paddingTop, c.paddingBottom, c.paddingLeft, c.paddingRight].join(' '))(getComputedStyle(document.querySelector('[data-pk-foot]')))", sid)
                self.assertEqual(pad, "0px 0px 0px 0px")


for _name in [n for n in dir(FootPadding) if n.startswith("test_") and n != "test_the_footer_has_no_padding_so_the_43_px_is_the_content_box"]:
    setattr(FootPadding, _name, None)
