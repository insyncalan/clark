"""Row 1258 part 4: the peek's footer at the approved size (the mockup's footer): 43 px high, the key tag 30 x 19 in mono 13 / 600, the input
without a border. A real browser at 1400 and 900 px in Edit on the fictional demo project; no new words (the placeholder is unchanged).
Run: python3 dev/run_tests.py test_peek_footer_1258
"""
import json


import test_peek_latest  # noqa: E402
from test_peek_latest import OVERDUE  # noqa: E402
from test_server import chrome, wait  # noqa: E402



class Footer(test_peek_latest.Browser):
    def box(self, cdp, sid, selector):
        return cdp.js(f"(e => {{ const r = e.getBoundingClientRect(), c = getComputedStyle(e); return {{w: r.width, h: r.height, font: c.fontFamily, size: c.fontSize, weight: c.fontWeight, border: c.borderTopWidth + ' ' + c.borderLeftWidth}}; }})(document.querySelector({json.dumps(selector)}))", sid)

    def opened(self, cdp, width):
        sent, sid = self.load(cdp, width, OVERDUE)
        self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('[data-pk-foot]')", sid)), "the footer is drawn")
        return sid

    def test_the_footer_is_43_px_high(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.opened(cdp, width)
                self.assertEqual(self.box(cdp, sid, "[data-pk-foot]")["h"], 43)

    def test_the_key_tag_is_30_by_19_in_mono_12_semibold(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.opened(cdp, width)
                k = self.box(cdp, sid, "[data-pk-foot] kbd")
                self.assertEqual((k["w"], k["h"], k["size"], k["weight"]), (30, 19, "13px", "600"))
                self.assertRegex(k["font"].lower(), r"mono|menlo|consolas")

    def test_the_input_has_no_border_and_the_words_are_unchanged(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.opened(cdp, width)
                self.assertEqual(self.box(cdp, sid, "[data-pk-foot] [data-pk-ask]")["border"], "0px 0px")
                self.assertEqual(cdp.js("document.querySelector('[data-pk-foot] [data-pk-ask]').getAttribute('placeholder')", sid), "ask clark to update")
