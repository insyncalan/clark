"""Row 1230, mutation survivors of PR 1709: the scale separators, the Calendar's scale on the Milestones page, the heading row's room for the
tabs and the caption's lift above the strip's scroll bar.

Run: python3 dev/run_tests.py -j 1 test_ms_calendar_survivors_1230
Headless Chrome over the real server (fictional data), widths 1400 and 900 only. No new word: every string is one the page already had.
"""
import unittest

from test_ms_header_1230 import Base
from test_server import chrome, wait

SEC = "document.querySelector('.msv[data-place^=sec-]')"

BAR = """(() => {
  const box = %s, tl = box.querySelector('.mv-bar'), mt = tl && tl.querySelector('.mv-txt'), cal = box.querySelector('.cal-bar');
  const seps = (e) => e ? [...e.querySelectorAll(':scope > span')].map((s) => [s.textContent, s.getAttribute('aria-hidden')]) : null;
  return {tl: seps(mt), cal: seps(cal && cal.querySelector('.mv-txt'))};
})()""" % SEC

CAP = """(() => {
  const box = %s, mb = box.querySelector('.mv-box'), cap = box.querySelector('.mv-cap'), R = (e) => e.getBoundingClientRect();
  const sb = parseFloat(mb.style.getPropertyValue('--sb')), b = parseFloat(getComputedStyle(cap).bottom);
  return {sb, b, lift: R(mb).bottom - R(cap).bottom, bottomProp: getComputedStyle(cap).bottom, boxPos: getComputedStyle(mb).position};
})()""" % SEC

HEAD = """(() => {
  const box = %s, sec = box.closest('.sec'), head = sec.querySelector('.sec-head'), sw = box.querySelector('.msv-sw'), R = (e) => e.getBoundingClientRect();
  const cs = getComputedStyle(head);
  return {pad: parseFloat(cs.paddingRight), contentRight: R(head).right - parseFloat(cs.paddingRight) - parseFloat(cs.borderRightWidth || 0), swLeft: R(sw).left, swRight: R(sw).right, headRight: R(head).right};
})()""" % SEC

PAGE_CAL = """(() => {
  const box = document.querySelector('.msv[data-place=page]'), bar = box.querySelector('.cal-bar');
  return {cal: box.querySelectorAll('.cal').length, seg: !!bar.querySelector('.seg.cal-sc'), txt: !!bar.querySelector('.mv-txt'),
          words: [...bar.querySelectorAll('.cal-sc button')].map((b) => b.textContent.trim())};
})()"""


class Survivors(Base):
    def test_the_scale_text_tabs_have_a_dot_between_each_pair_timeline_and_calendar(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.visit(cdp, "#dashboard&p=ABC", width, False, ".msv .mv-wrap")
                got = cdp.js(BAR, sid)
                dot = ["·", "true"]
                self.assertEqual(got["tl"], [dot, dot], "Week . Month . Quarter on the Timeline: two dots")
                cdp.js(f"{SEC}.querySelector('[data-msvb=cal]').click()", sid)
                self.assertTrue(wait(lambda: cdp.js(f"{SEC}.querySelectorAll('.cal').length === 1", sid), 5))
                self.assertEqual(cdp.js(BAR, sid)["cal"], [dot, dot], "and on the Calendar")

    def test_the_caption_is_lifted_above_the_strip_by_the_amount_the_box_sets(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.visit(cdp, "#dashboard&p=ABC", width, False, ".msv .mv-wrap")
                got = cdp.js(CAP, sid)
                self.assertEqual(got["boxPos"], "relative")
                self.assertGreater(got["sb"], 0, f"the box sets a lift: {got}")
                self.assertAlmostEqual(got["b"], got["sb"] + 18, delta=1, msg=f"the caption sits that lift plus 18px (4px, and 14px for the height grip) above the box's bottom edge: {got}")
                self.assertAlmostEqual(got["lift"], got["sb"] + 18, delta=1.5, msg=str(got))

    def test_the_heading_row_leaves_room_for_the_tabs(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.visit(cdp, "#dashboard&p=ABC", width, False, ".msv .mv-wrap")
                got = cdp.js(HEAD, sid)
                self.assertLessEqual(got["contentRight"], got["swLeft"] + 1, f"the heading's text stops before the tabs: {got}")
                self.assertGreaterEqual(got["pad"], 200, str(got))

    def test_the_calendar_on_the_milestones_page_keeps_its_segmented_scale(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.visit(cdp, "#milestones&p=ABC", width, False, ".mv-wrap")
                cdp.js("document.querySelector('.msv[data-place=page] [data-msvb=cal]').click()", sid)
                self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('.msv[data-place=page] .cal').length === 1", sid), 5))
                got = cdp.js(PAGE_CAL, sid)
                self.assertTrue(got["seg"], "the page keeps the segmented control")
                self.assertFalse(got["txt"], "no text tabs on the page")
                self.assertEqual(got["words"], ["Week", "Month", "Quarter"])


if __name__ == "__main__":
    unittest.main()
