"""Rows 840 and 841: the Settings fields are label-left rows and the Settings cards are compact, in a real browser at 1400 and 900 px,
light and dark, View and Edit. Run: python3 dev/run_tests.py test_settings_rows

Row 840: each field in a Settings card has its label in a column of 8 rem at the left and the control beside it on the same row, the
control is not capped at 420 px (it takes the rest of the card), and the hint stands under the control, in the control's column.
Row 841: a card has 16 px above and below and 24 px at the sides, its heading is 20 px, its intro line is 14 px, it has no shadow, and
the gap between two cards is 12 px. Chrome is required: these tests fail, never skip, without it."""
import unittest

from test_settings_head import Head
from test_server import chrome

WIDTHS = (1400, 900)
MODES = ("light", "dark")
FIELDS = """(() => [...document.querySelectorAll('.set-cards .fld')].map(f => {
  const l = f.querySelector('label'), i = f.querySelector('input'), h = f.querySelector('small');
  if (!l || !i) return null;
  const fr = f.getBoundingClientRect(), lr = l.getBoundingClientRect(), ir = i.getBoundingClientRect(), hr = h ? h.getBoundingClientRect() : null;
  return {id: i.id, label_w: lr.width, label_left: lr.left - fr.left, input_left: ir.left - fr.left, input_w: ir.width, card_w: fr.width,
          same_row: Math.abs((lr.top + lr.bottom) / 2 - (ir.top + ir.bottom) / 2) < ir.height, hint_left: hr ? hr.left - fr.left : null, hint_below: hr ? hr.top >= ir.bottom - 1 : true};
}).filter(Boolean))()"""
CARDS = """(() => { const cs = [...document.querySelectorAll('.set-cards > .frame')]; return cs.map((c, n) => {
  const s = getComputedStyle(c), h = c.querySelector('h2'), p = h && h.parentElement === c && h.nextElementSibling && h.nextElementSibling.tagName === 'P' ? h.nextElementSibling : null;
  const prev = n ? cs[n - 1].getBoundingClientRect().bottom : null;
  return {id: c.id, pad: [s.paddingTop, s.paddingRight, s.paddingBottom, s.paddingLeft], shadow: s.boxShadow, h2: h ? getComputedStyle(h).fontSize : null,
          intro: p ? getComputedStyle(p).fontSize : null, gap: prev === null ? null : Math.round(c.getBoundingClientRect().top - prev)}; }); })()"""


class Rows(Head):
    def drawn(self, p, w, mode, edit):
        self.open_settings(p, w, mode)
        if edit:
            p.js("document.querySelector('[data-mode=edit]').click()")
            p.until("document.querySelector('#report') ? document.querySelector('#report').dataset.mode === 'edit' : !!document.querySelector('[data-mode=edit][aria-pressed=true]')", "Edit mode")
            p.until("!!document.querySelector('.set-cards .fld')", "the fields are drawn")

    def across(self, check):
        for w in WIDTHS:
            for mode in MODES:
                for edit in (False,):          # row 826: Settings has no View|Edit switch, so there is no Edit variant of this page
                    with self.subTest(width=w, mode=mode, edit=edit), chrome() as cdp:
                        p = self.page(cdp)
                        self.drawn(p, w, mode, edit)
                        check(p)

    def test_C_row_840_the_label_is_at_the_left_and_the_control_is_beside_it_and_not_capped(self):
        def check(p):
            fields = p.js(FIELDS)
            self.assertGreaterEqual(len(fields), 3, "the Personal and Freshness fields are drawn")
            for f in fields:
                self.assertAlmostEqual(f["label_w"], 128, delta=1, msg=f["id"] + ": the label column is 8 rem")
                self.assertLess(f["label_left"], 1, "the label is at the left edge of the row")
                self.assertGreater(f["input_left"], f["label_w"], "the control is beside the label, not under it")
                self.assertTrue(f["same_row"], "the label and the control share a row")
                self.assertGreater(f["input_w"], 420, "the control is not capped at 420 px")
                self.assertGreater(f["input_w"], f["card_w"] * 0.6, "the control takes the rest of the row")
                self.assertAlmostEqual(f["input_left"], 140, delta=1, msg="a 12 px gap after the label column")
                if f["hint_left"] is not None:
                    self.assertAlmostEqual(f["hint_left"], f["input_left"], delta=1, msg="the hint is in the control's column")
                    self.assertTrue(f["hint_below"], "the hint is under the control")
        self.across(check)

    def test_C_row_841_the_cards_are_compact(self):
        def check(p):
            cards = p.js(CARDS)
            self.assertGreaterEqual(len(cards), 8)
            for n, c in enumerate(cards):
                self.assertEqual(c["pad"], ["16px", "24px", "16px", "24px"], c["id"] + ": card padding")
                self.assertEqual(c["shadow"], "none", c["id"] + ": no shadow")
                self.assertEqual(c["h2"], "20px", c["id"] + ": heading size")
                if c["intro"] is not None:
                    self.assertEqual(c["intro"], "14px", c["id"] + ": intro size")
                if n:
                    self.assertEqual(c["gap"], 12, c["id"] + ": the gap to the card above")
        self.across(check)


if __name__ == "__main__":
    unittest.main()
