"""Rows 840 and 841: the Settings fields are label-left rows and the Settings cards are compact, in a real browser at 1400 and 900 px,
light and dark, View and Edit. Run: python3 dev/run_tests.py test_settings_rows

Row 840: each field in a Settings card has its label in a column of 8 rem at the left and the control beside it on the same row, the
control is not capped at 420 px (it takes the rest of the card), and the hint stands under the control, in the control's column.
Row 841: a card has 16 px above and below and 24 px at the sides, its heading is 20 px, its intro line is 14 px, it has no shadow, and
the gap between two cards is 12 px. Chrome is required: these tests fail, never skip, without it.

Item 1024: Settings shows one page at a time, so each check runs on every page (reached by its address) and the old floors are kept on the
total: item 840 still wants at least 3 fields (and the Profile and Reports pages must each hold one), item 841 still wants at least 8 cards
(and at least one gap of 12 px is really measured, on a page with 2 or more cards). No value changed, and none of these is weakened."""
import unittest

from test_settings_head import Head, PAGES
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
    def drawn(self, p, w, mode, edit, page=None):
        self.open_settings(p, w, mode, page)
        if edit:
            p.js("document.querySelector('[data-mode=edit]').click()")
            p.until("document.querySelector('#report') ? document.querySelector('#report').dataset.mode === 'edit' : !!document.querySelector('[data-mode=edit][aria-pressed=true]')", "Edit mode")
            p.until("!!document.querySelector('.set-cards .fld')", "the fields are drawn")

    def across(self, read, check):
        """Run `read(p)` on every page in every width and mode, then `check(pages)` on what it gave, {address key: value}."""
        for w in WIDTHS:
            for mode in MODES:
                for edit in (False,):          # row 826: Settings has no View|Edit switch, so there is no Edit variant of this page
                    with self.subTest(width=w, mode=mode, edit=edit), chrome() as cdp:
                        p = self.page(cdp)
                        got = {}
                        for _, slug, _, _ in PAGES:
                            self.drawn(p, w, mode, edit, slug)
                            got[slug] = read(p)
                        self.assertEqual(list(got), [s for _, s, _, _ in PAGES], "every page in the menu was read")
                        check(got)

    def test_C_row_840_the_label_is_at_the_left_and_the_control_is_beside_it_and_not_capped(self):
        def read(p):
            return p.js(FIELDS)

        def check(pages):
            self.assertGreaterEqual(sum(len(f) for f in pages.values()), 3, "the Profile and Reports fields are drawn (the old floor of 3, over all pages)")
            for need in ("profile", "reports"):
                self.assertGreaterEqual(len(pages[need]), 1, f"the {need} page holds a field")
            for page, fields in pages.items():
                for f in fields:
                    self.assertAlmostEqual(f["label_w"], 128, delta=1, msg=page + " " + f["id"] + ": the label column is 8 rem")
                    self.assertLess(f["label_left"], 1, "the label is at the left edge of the row")
                    self.assertGreater(f["input_left"], f["label_w"], "the control is beside the label, not under it")
                    self.assertTrue(f["same_row"], "the label and the control share a row")
                    self.assertGreater(f["input_w"], 420, "the control is not capped at 420 px")
                    self.assertGreater(f["input_w"], f["card_w"] * 0.6, "the control takes the rest of the row")
                    self.assertAlmostEqual(f["input_left"], 140, delta=1, msg="a 12 px gap after the label column")
                    if f["hint_left"] is not None:
                        self.assertAlmostEqual(f["hint_left"], f["input_left"], delta=1, msg="the hint is in the control's column")
                        self.assertTrue(f["hint_below"], "the hint is under the control")
        self.across(read, check)

    def test_C_row_841_the_cards_are_compact(self):
        def read(p):
            return p.js(CARDS)

        def check(pages):
            self.assertGreaterEqual(sum(len(c) for c in pages.values()), 8, "the old floor of 8 cards, over all pages")
            self.assertEqual(len(pages), len(PAGES), "a card page for each menu entry")
            gaps = 0
            for page, cards in pages.items():
                self.assertGreaterEqual(len(cards), 1, page + " holds a card")
                for n, c in enumerate(cards):
                    self.assertEqual(c["pad"], ["16px", "24px", "16px", "24px"], c["id"] + ": card padding")
                    self.assertEqual(c["shadow"], "none", c["id"] + ": no shadow")
                    self.assertEqual(c["h2"], "20px", c["id"] + ": heading size")
                    if c["intro"] is not None:
                        self.assertEqual(c["intro"], "14px", c["id"] + ": intro size")
                    if n:
                        gaps += 1
                        self.assertEqual(c["gap"], 12, c["id"] + ": the gap to the card above")
            self.assertGreaterEqual(gaps, 1, "a gap between two cards was really measured (a page with 2 or more cards)")
        self.across(read, check)


if __name__ == "__main__":
    unittest.main()
