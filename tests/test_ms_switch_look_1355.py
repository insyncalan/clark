"""Row 1355 (pin): the Timeline / Calendar switch in the Classic theme has a 1px border and cells 28px high and a 6px radius (ruling, ticket comment 7048064560); the Cards theme is unchanged.

Run: PYTHONPATH=../src python3 -m unittest test_ms_switch_look_1355
Chrome at 1400 and 900 px, light and dark; computed styles on .msv-sw and its cells.
"""
import time
import unittest

from test_ms_timeline_classic_1315 import Base

M = """(() => { const sw = document.querySelector('.msv-sw'), cs = getComputedStyle(sw), cells = [...sw.querySelectorAll('.msv-b')];
  return { bw: [cs.borderTopWidth, cs.borderRightWidth, cs.borderBottomWidth, cs.borderLeftWidth], bs: cs.borderTopStyle, rad: cs.borderTopLeftRadius + '|' + cs.borderBottomRightRadius,
    n: cells.length, hs: cells.map((c) => c.getBoundingClientRect().height), mh: cells.map((c) => getComputedStyle(c).minHeight),
    bc: cs.borderTopColor, sep: getComputedStyle(cells[1]).borderLeftColor, pad: cells.map((c) => getComputedStyle(c).paddingLeft + '|' + getComputedStyle(c).paddingRight),
    ui: (() => { const d = document.createElement('i'); d.style.color = 'var(--grey-500)'; sw.appendChild(d); const c = getComputedStyle(d).color; d.remove(); return c; })() }; })()"""


class Classic(Base, unittest.TestCase):
    def test_switch_has_1px_border_and_cells_28_high(self):
        for cdp, sid, w in self.every():
            time.sleep(0.8)
            g = cdp.js(M, sid)
            self.assertEqual(g["bw"], ["1px"] * 4, w)
            self.assertEqual(g["bs"], "solid")
            self.assertEqual(g["n"], 2)
            self.assertEqual(g["mh"], ["28px", "28px"], w)
            self.assertEqual(g["hs"], [28, 28], w)

    def test_switch_border_is_ui_colour_and_cells_pad_12(self):
        # prototype --ui is the Classic --grey-500 (rules.css row 1316d note); prototype padding 0 12px
        for cdp, sid, w in self.every():
            time.sleep(0.8)
            g = cdp.js(M, sid)
            self.assertEqual(g["bc"], g["sep"], w)
            self.assertEqual(g["pad"], ["12px|12px"] * 2, w)
            self.assertEqual(g["bc"], g["ui"], w)
            self.assertNotEqual(g["ui"], "rgb(0, 0, 0)", w)

    def test_switch_radius_is_6px(self):
        for cdp, sid, w in self.every():
            time.sleep(0.8)
            self.assertEqual(cdp.js(M, sid)["rad"], "6px|6px", w)


class Cards(Base, unittest.TestCase):
    THEME = None

    def test_cards_switch_is_not_the_classic_look(self):
        for cdp, sid, w in self.every():
            g = cdp.js(M, sid)
            self.assertNotEqual((g["bw"], g["mh"]), (["1px"] * 4, ["28px", "28px"]), w)

    def test_cards_radius_is_unchanged(self):
        for cdp, sid, w in self.every():
            self.assertEqual(cdp.js(M, sid)["rad"], "8px|8px", w)


if __name__ == "__main__":
    unittest.main()
