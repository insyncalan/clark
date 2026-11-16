"""Row 1258, step 3 (title and tabs), against peek-mockup.html layout A: the title is Inter 24/700 with letter-spacing -.015em (-0.36 px), and its
in-place box carries a 2 px brand ring with no border; the tabs are 14/600, 40 px high, with a 2 px ink underline on the open tab and a transparent
one on the others. Run: python3 dev/run_tests.py test_peek_title_tabs_1258. Widths 1400 and 900 only."""
import unittest

import test_peek_head_1180 as _h  # noqa: E402
from test_peek_head_1180 import WIDTHS  # noqa: E402
from test_server import chrome  # noqa: E402

INK = "rgb(14, 36, 48)"
RING = "rgb(91, 71, 216) 0px 0px 0px 2px"


class TitleTabs(unittest.TestCase):
    # the loader and the helpers of the head test, taken one by one so that its own tests are not run again here
    HOLD, fresh, action, toast, setUp = (_h.Head.HOLD, _h.Head.fresh, _h.Head.action, _h.Head.toast, _h.Head.setUp)
    load, calm, value, focused_box, open_by_click = (_h.Head.load, _h.Head.calm, _h.Head.value, _h.Head.focused_box, _h.Head.open_by_click)

    def test_the_title_is_inter_24_bold_with_tight_letters(self):
        for width in WIDTHS:
            with self.subTest(width=width), chrome() as cdp:
                _, sid = self.load(cdp, width)
                self.calm(cdp, sid)
                got = cdp.js("(s => [s.fontFamily.split(',')[0], s.fontSize, s.fontWeight, s.letterSpacing, s.lineHeight])(getComputedStyle(document.querySelector('#peek h2.pk-title')))", sid)
                self.assertEqual(got, ["Inter", "24px", "700", "-0.36px", "28.8px"])

    def test_the_title_box_has_a_two_pixel_ring_and_no_border_and_the_same_letters(self):
        for width in WIDTHS:
            with self.subTest(width=width), chrome() as cdp:
                _, sid = self.load(cdp, width)
                self.calm(cdp, sid)
                self.open_by_click(cdp, sid)
                got = cdp.js("(s => [s.boxShadow, s.borderTopWidth, s.outlineStyle, s.fontFamily.split(',')[0], s.fontSize, s.fontWeight, s.letterSpacing])"
                             "(getComputedStyle(document.querySelector('#peek textarea[data-pk-title-in]')))", sid)
                self.assertEqual(got, [RING, "0px", "none", "Inter", "24px", "700", "-0.36px"])

    def test_the_tabs_are_14_600_and_40_high_with_an_ink_underline_on_the_open_one(self):
        for width in WIDTHS:
            with self.subTest(width=width), chrome() as cdp:
                _, sid = self.load(cdp, width)
                self.calm(cdp, sid)
                rows = cdp.js("[...document.querySelectorAll('#peek .pk-tab')].map(t => { const s = getComputedStyle(t);"
                              " return [t.classList.contains('on'), s.fontSize, s.fontWeight, t.getBoundingClientRect().height, s.borderBottomWidth, s.borderBottomColor, s.paddingTop, s.paddingLeft]; })", sid)
                self.assertGreaterEqual(len(rows), 2, "the tabs are there")
                self.assertEqual(sum(1 for r in rows if r[0]), 1, "one tab is open")
                for on, size, weight, height, bw, bc, pt, pl in rows:
                    self.assertEqual((size, weight, height, bw, pt, pl), ("14px", "600", 40, "2px", "9px", "12px"))
                    self.assertEqual(bc, INK if on else "rgba(0, 0, 0, 0)")
                gap = cdp.js("(t => [getComputedStyle(t).columnGap, getComputedStyle(t).marginTop, getComputedStyle(t).marginBottom])(document.querySelector('#peek .pk-tabs'))", sid)
                self.assertEqual(gap, ["2px", "22px", "4px"])

    def test_clicking_another_tab_moves_the_ink_underline_to_it(self):
        for width in WIDTHS:
            with self.subTest(width=width), chrome() as cdp:
                _, sid = self.load(cdp, width)
                self.calm(cdp, sid)
                cdp.js("document.querySelectorAll('#peek .pk-tab')[1].click()", sid)
                got = cdp.js("[...document.querySelectorAll('#peek .pk-tab')].map(t => [t.classList.contains('on'), getComputedStyle(t).borderBottomColor])", sid)
                self.assertEqual([g[0] for g in got][:2], [False, True])
                self.assertEqual(got[1][1], INK)
                self.assertEqual(got[0][1], "rgba(0, 0, 0, 0)")


if __name__ == "__main__":
    unittest.main()
