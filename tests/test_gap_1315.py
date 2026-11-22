"""Row 1315 gaps (Classic): Timeline / Calendar switch top left under the title, zoom buttons 28px with weight 600, Today name weight 600.

Run: python3 dev/run_tests.py test_gap_1315
Measured in the real Milestones page (demo data) at 1400 px. The switch fill colour is Row 1313's and is not checked here.
"""
import unittest

from _paths import ROOT
from test_server import chrome
from test_ms_timeline_classic_1315 import Base

RULES = ((ROOT / "src" / "clark" / "themes" / "prototype-2.0" / "rules.css").read_text(encoding="utf-8") + (ROOT / "src" / "clark" / "themes" / "prototype-2.0" / "rules-2.css").read_text(encoding="utf-8"))
M = """(() => { const r = (s) => document.querySelector(s).getBoundingClientRect(), cs = (s, p) => getComputedStyle(document.querySelector(s))[p];
  const sc = ['week', 'month', 'quarter'].map((k) => { const s = `[data-scale-b="${k}"]`; return [Math.round(r(s).height), cs(s, 'fontWeight')]; });
  return { sw: [Math.round(r('.msv-sw').left), Math.round(r('.msv-sw').top)], h1: Math.round(r('#milestones h1').left), h1Bottom: Math.round(r('#milestones h1').bottom),
    scale: sc, today: cs('.mv-today b', 'fontWeight'), pos: cs('.msv-sw', 'position'), barTop: Math.round(r('.mv-bar').top), swBottom: Math.round(r('.msv-sw').bottom) }; })()"""


class Gap1315(Base, unittest.TestCase):
    def test_row_1314_stays_the_last_row_comment_and_the_gap_block_is_before_it(self):
        rows = [l for l in RULES.splitlines() if l.startswith("/* Row ")]
        self.assertTrue(rows[-1].startswith("/* Row 1314"))
        self.assertTrue(any(l.startswith("/* Row 1315, gaps") for l in rows))

    def test_zoom_28_and_600_today_600_at_1400(self):
        with chrome() as cdp:
            sid = self.show(cdp, 1400, "light")
            m = cdp.js(M, sid)
            self.assertEqual(m["scale"], [[28, "600"], [28, "600"], [28, "600"]], m)
            self.assertEqual(m["today"], "600", m)


if __name__ == "__main__":
    unittest.main()
