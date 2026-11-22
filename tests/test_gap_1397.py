"""Row 1397: the Milestones timeline strip and switch text in the Classic theme (1400, light). Cards unchanged.

Run: python3 dev/run_tests.py test_gap_1397
Values are computed in Chrome over the demo data (fictional). The switch frame, radius 6 and padding are Row 1315's.
"""
import json
import unittest

from _paths import ROOT
from clark import page
from test_ms_timeline_classic_1315 import Base, HASH
from test_server import chrome, wait

RULES = ROOT / "src" / "clark" / "themes" / "prototype-2.0" / "rules.css"
READ = """(() => { const c = (s) => getComputedStyle(document.querySelector(s)), r = (s) => document.querySelector(s).getBoundingClientRect();
  const tok = (n) => { const d = document.createElement('i'); d.style.color = 'var(' + n + ')'; document.body.appendChild(d); const v = getComputedStyle(d).color; d.remove(); return v; };
  const mk = r('.mv-mk'), ic = r('.mv-mk .ms-i'), sw = document.querySelector('#milestones .msv-b'), fr = c('#milestones .msv-sw'), b2 = c('#milestones .msv-b + .msv-b');
  return JSON.stringify({ fill: c('.mv-wrap').backgroundColor, line: [c('.mv-line').height, c('.mv-line').backgroundColor], todayW: r('.mv-today').width, todayBg: c('.mv-today').backgroundColor,
    lab: [c('.mv-today b').fontSize, c('.mv-today b').fontWeight, c('.mv-today b').color, c('.mv-today b').backgroundColor],
    mk: [mk.width, mk.height], ic: [ic.width, ic.height], sw: getComputedStyle(sw).fontSize, swPad: getComputedStyle(sw).paddingLeft + ' ' + getComputedStyle(sw).paddingRight, swW: getComputedStyle(sw).fontWeight, frame: [fr.borderTopWidth, fr.borderTopColor, fr.borderTopLeftRadius], divider: [b2.borderLeftWidth, b2.borderLeftColor], grey500: tok('--grey-500'), blue: tok('--brand-blue') }); })()"""


class Source(unittest.TestCase):
    def test_1314_stays_the_last_row_line_and_the_rules_sit_before_it(self):
        t = RULES.read_text(encoding="utf-8")
        rows = [ln for ln in t.splitlines() if ln.startswith("/* Row ")]
        self.assertTrue(rows[-1].startswith("/* Row 1314"))
        self.assertLess(t.index("/* Row 1397"), t.index("/* Row 1314"))


class Computed(Base, unittest.TestCase):
    def read(self, theme):
        self.THEME = theme
        with chrome() as cdp:
            sid = self.show(cdp, 1400, "light")
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.mv-today b')", sid)))
            return json.loads(cdp.js(READ, sid))

    def test_classic(self):
        m = self.read("prototype-2.0")
        self.assertEqual(m["fill"], "rgba(0, 0, 0, 0)")
        self.assertEqual(m["line"], ["2px", m["grey500"]])
        self.assertEqual((m["todayW"], m["todayBg"]), (1.5, m["blue"]))
        self.assertEqual(m["lab"], ["13px", "600", m["blue"], "rgba(0, 0, 0, 0)"])
        self.assertEqual(m["mk"], [24, 24])
        self.assertEqual(m["ic"], [20, 20])
        self.assertEqual((m["sw"], m["swW"]), ("14px", "600"))
        self.assertEqual(m["frame"], ["1px", m["grey500"], "6px"])
        self.assertEqual(m["divider"], ["1px", m["grey500"]])
        self.assertEqual(m["swPad"], "14px 14px")      # padding 3px 14px (Row 1355, ruling 21-11), drawn in Classic

    def test_cards_keeps_its_strip_and_switch(self):
        m = self.read(None)
        self.assertNotEqual(m["fill"], "rgba(0, 0, 0, 0)")
        self.assertNotEqual(m["line"][1], m["grey500"])
        self.assertEqual(m["todayW"], 2)
        self.assertEqual(m["mk"], m["ic"])


if __name__ == "__main__":
    unittest.main()
