"""Row 1315 fill (ruling 19-11): the Milestones switches (Timeline / Calendar, Week / Month / Quarter) take a 1px --ui frame,
a 1px --ui (--grey-500) rule between the halves. Light, 1400 px (900 is a note).

Run: python3 dev/run_tests.py test_gap_1315b
"""
import unittest

from _paths import ROOT

from test_server import chrome
from test_ms_timeline_classic_1315 import Base

M = """(() => { const cs = (e, p) => getComputedStyle(e)[p], q = (s) => [...document.querySelectorAll(s)];
  const g = (sel) => { const bs = q(sel + ' button'), box = document.querySelector(sel), on = bs.find((b) => b.getAttribute('aria-current') === 'true'), off = bs.find((b) => b !== on);
    return { rad: cs(box, 'borderTopLeftRadius'), border: cs(box, 'borderTopWidth'), bc: cs(box, 'borderTopColor'), h: Math.round(on.getBoundingClientRect().height), pad: cs(on, 'paddingLeft') + ' ' + cs(on, 'paddingRight'),
      w: cs(on, 'fontWeight'), bg: cs(on, 'backgroundColor'), fg: cs(on, 'color'), offbg: cs(off, 'backgroundColor'), div: bs.length > 1 ? [cs(bs[1], 'borderLeftWidth'), cs(bs[1], 'borderLeftColor')] : null }; };
  const sw = document.querySelector('.msv-sw').getBoundingClientRect();
  return { sw: g('#milestones .msv-sw'), sc: g('#milestones .cal-sc'), swPos: [Math.round(sw.left), Math.round(sw.top)],
    navy: getComputedStyle(document.documentElement).getPropertyValue('--brand-navy').trim(), ui: getComputedStyle(document.documentElement).getPropertyValue('--grey-500').trim() }; })()"""


RULES = (ROOT / "src" / "clark" / "themes" / "prototype-2.0" / "rules.css").read_text(encoding="utf-8")


class Gap1315b(Base, unittest.TestCase):
    def test_fill_block_is_before_row_1393_with_no_literal_weight_and_no_shared_pieces(self):
        rows = [l for l in RULES.splitlines() if l.startswith("/* Row ")]
        i = next(n for n, l in enumerate(rows) if l.startswith("/* Row 1315 fill"))
        self.assertLess(i, next(n for n, l in enumerate(rows) if l.startswith("/* Row 1393")))      # before Row 1393, other rows may sit between
        block = RULES.split("/* Row 1315 fill", 1)[1].split("\n/*", 1)[0]      # up to the next comment of any kind
        rules = {l.split(" {", 1)[0]: l for l in block.splitlines() if " {" in l}      # found by selector, never by position or count of other rules
        self.assertEqual(rules["#milestones .msv-sw .msv-b"].split("{", 1)[1].strip(), "min-height: 28px; padding: 3px 14px; font-weight: var(--weight-medium); }")      # ruling 21-11 03:2x on 1315 / 1319: padding 3px 14px, 28px, weight 600 on the Timeline / Calendar buttons, which are not .seg
        self.assertNotIn("#milestones .cal-sc button", rules)      # the Week / Month / Quarter buttons are .seg: Row 1319 reaches them
        self.assertIn("border: 1px solid var(--grey-500);", rules["#milestones .msv-sw, #milestones .cal-sc"])
        self.assertIn("border-left: 1px solid var(--grey-500);", rules["#milestones .msv-b + .msv-b, #milestones .cal-sc button + button"])
        for l in rules.values():
            self.assertNotIn("font-weight: 600", l)
            self.assertNotIn("border-radius", l)      # the radius is the Row 1316 pin's, not this block's
            self.assertNotIn("background", l)
            self.assertNotIn("mv-today", l)      # the Today name is the Row 1316 PR's line

    def test_frame_padding_14_sides_divider_1px_at_1400(self):
        with chrome() as cdp:
            sid = self.show(cdp, 1400, "light")
            m = cdp.js(M, sid)
            print("row 1315 fill 1400", m)
            for k in ("sw", "sc"):
                g = m[k]
                self.assertEqual(g["pad"], "14px 14px", (k, m))      # all five buttons: 3px 14px (ruling 21-11 03:2x; sc is the Row 1319 .seg button)
                self.assertEqual(g["border"], "1px", (k, m))
                self.assertEqual(g["bc"], "rgb(135, 148, 179)", (k, m))
            self.assertEqual((m["sw"]["h"], m["sw"]["w"]), (28, "600"), m)      # Timeline / Calendar; Week / Month / Quarter height and weight are the Row 1316 PR's rule
            self.assertEqual(m["sw"]["div"], ["1px", "rgb(135, 148, 179)"], m)
            self.assertEqual(m["sc"]["div"], ["1px", "rgb(135, 148, 179)"], m)

    def test_frame_padding_divider_hold_at_900_by_source_and_by_look(self):
        # 900 px: the three rules sit at the top level, in no media query, and no max-width 900 rule changes the Milestones switch buttons.
        block = RULES.split("/* Row 1315 fill", 1)[1].split("\n/*", 1)[0]
        for l in block.splitlines()[1:]:
            self.assertTrue(l.startswith("#milestones "), l)      # column 0, so not nested in an @media block
        wide = RULES.split("/* Row 1315 fill", 1)[0] + RULES.split("/* Row 1315 fill", 1)[1].split("\n/*", 1)[1]
        for chunk in wide.split("@media (max-width: 900px)")[1:]:
            inner = chunk.split("\n", 1)[0]
            self.assertNotIn("#milestones .msv-b", inner)
            self.assertNotIn("#milestones .cal-sc", inner)
        with chrome() as cdp:
            sid = self.show(cdp, 900, "light")      # skipped with the stated reason while test_server.PAUSED_900 is set; runs when it is switched off
            m = cdp.js(M, sid)
            for k in ("sw", "sc"):
                self.assertEqual(m[k]["pad"], "14px 14px", (k, m))
                self.assertEqual(m[k]["border"], "1px", (k, m))
            self.assertEqual(m["sw"]["div"], ["1px", "rgb(135, 148, 179)"], m)


if __name__ == "__main__":
    unittest.main()
