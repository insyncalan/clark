"""Row 840: the Settings fields are label-left rows, in a real browser at 1400 and 900 px,
light and dark, View and Edit. Run: python3 dev/run_tests.py test_settings_rows

Row 840: each field in a Settings card has its label in a column of 8 rem at the left and the control beside it on the same row, the
control is not capped at 420 px (it takes the rest of the card), and the hint stands under the control, in the control's column.
Chrome is required: these tests fail, never skip, without it."""
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
                for edit in (False, True):
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


if __name__ == "__main__":
    unittest.main()
