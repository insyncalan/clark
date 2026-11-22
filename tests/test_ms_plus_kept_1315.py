"""Row 1315 (AP11, AP12, AP13): two things the Classic Milestones page keeps, pinned.

AP11: the dashed add-milestone button #addMs.newb stays, with a 1px dashed border in var(--status-blue-text).
AP12: the Plan / Movement switch stays: a group labelled "Milestones view" with two buttons.
AP13: at 900 px the same values hold as at 1400 px.

Run: python3 dev/run_tests.py test_ms_plus_kept_1315
Chrome at 1400 and 900 px, light and dark; the values are computed in Chrome.
"""
import unittest

from test_ms_timeline_classic_1315 import Base

PLUS = """(() => {
  const b = document.querySelector('#addMs.newb'); if (!b) return null;
  const cs = getComputedStyle(b), probe = document.createElement('i');
  probe.style.borderTop = '1px solid var(--status-blue-text)'; document.body.appendChild(probe);
  const want = getComputedStyle(probe).borderTopColor; probe.remove();
  return { tag: b.tagName, style: cs.borderTopStyle, width: cs.borderTopWidth, color: cs.borderTopColor, want: want,
           shown: b.getBoundingClientRect().width > 0 && cs.visibility !== 'hidden' && cs.display !== 'none' };
})()"""

SWITCH = """(() => {
  const g = document.querySelector('[data-mspage-switch] [role=group][aria-label="Milestones view"]'); if (!g) return null;
  const bs = [...g.querySelectorAll('button')];
  return { n: bs.length, words: bs.map((b) => b.textContent), keys: bs.map((b) => b.dataset.mspv), pressed: bs.map((b) => b.getAttribute('aria-pressed')),
           shown: g.getBoundingClientRect().width > 0 };
})()"""


class Classic(Base, unittest.TestCase):
    def test_classic_milestones_dashed_plus_present(self):
        for cdp, sid, w in self.every():
            g = cdp.js(PLUS, sid)
            self.assertIsNotNone(g, f"#addMs.newb is on the Milestones page at {w}")
            self.assertTrue(g["shown"], g)
            self.assertEqual((g["style"], g["width"]), ("dashed", "1px"), g)
            self.assertEqual(g["color"], g["want"], f"the dashed edge is var(--status-blue-text) at {w}: {g}")

    def test_classic_milestones_has_no_plan_movement_switch(self):
        """Row 1329 (ticket comment 18-11) supersedes the Row 1315 AP12 pin: Classic draws no Plan | Movement switch."""
        for cdp, sid, w in self.every():
            self.assertIsNone(cdp.js(SWITCH, sid), f"Classic has no 'Milestones view' group at {w}")

    def test_the_pins_hold_at_900(self):
        seen = {}
        for cdp, sid, w in self.every():
            g = cdp.js(PLUS, sid)
            self.assertIsNotNone(g)
            seen[w] = (g["style"], g["width"], g["color"] == g["want"])
        self.assertEqual(seen[900], seen[1400], "the 900 values equal the 1400 values")


if __name__ == "__main__":
    unittest.main()
