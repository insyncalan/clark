"""Row 1315 fill (ruling 19-11): the Milestones switches (Timeline / Calendar, Week / Month / Quarter) take the navy chosen half with white text,
radius 6, buttons 28 high with padding 0 12 and weight 600, a 1px --ui (--grey-500) rule between the halves. Light, 1400 px (900 is a note).

Run: python3 dev/run_tests.py test_gap_1315b
"""
import unittest

from test_server import chrome
from test_ms_timeline_classic_1315 import Base

M = """(() => { const cs = (e, p) => getComputedStyle(e)[p], q = (s) => [...document.querySelectorAll(s)];
  const g = (sel) => { const bs = q(sel + ' button'), box = document.querySelector(sel), on = bs.find((b) => b.getAttribute('aria-current') === 'true'), off = bs.find((b) => b !== on);
    return { rad: cs(box, 'borderTopLeftRadius'), border: cs(box, 'borderTopWidth'), bc: cs(box, 'borderTopColor'), h: Math.round(on.getBoundingClientRect().height), pad: cs(on, 'paddingLeft') + ' ' + cs(on, 'paddingRight'),
      w: cs(on, 'fontWeight'), bg: cs(on, 'backgroundColor'), fg: cs(on, 'color'), offbg: cs(off, 'backgroundColor'), div: bs.length > 1 ? [cs(bs[1], 'borderLeftWidth'), cs(bs[1], 'borderLeftColor')] : null }; };
  const sw = document.querySelector('.msv-sw').getBoundingClientRect();
  return { sw: g('#milestones .msv-sw'), sc: g('#milestones .cal-sc'), swPos: [Math.round(sw.left), Math.round(sw.top)],
    navy: getComputedStyle(document.documentElement).getPropertyValue('--brand-navy').trim(), ui: getComputedStyle(document.documentElement).getPropertyValue('--grey-500').trim() }; })()"""


class Gap1315b(Base, unittest.TestCase):
    def test_navy_fill_radius_6_buttons_28_600_divider_1px_at_1400(self):
        with chrome() as cdp:
            sid = self.show(cdp, 1400, "light")
            m = cdp.js(M, sid)
            print("row 1315 fill 1400", m)
            for k in ("sw", "sc"):
                g = m[k]
                self.assertEqual(g["bg"], "rgb(6, 47, 58)", (k, m))
                self.assertEqual(g["fg"], "rgb(255, 255, 255)", (k, m))
                self.assertEqual(g["rad"], "6px", (k, m))
                self.assertEqual((g["h"], g["pad"], g["w"]), (28, "12px 12px", "600"), (k, m))
                self.assertEqual(g["border"], "1px", (k, m))
                self.assertEqual(g["bc"], "rgb(135, 148, 179)", (k, m))
                self.assertNotEqual(g["offbg"], g["bg"], (k, m))
            self.assertEqual(m["sw"]["div"], ["1px", "rgb(135, 148, 179)"], m)


if __name__ == "__main__":
    unittest.main()
