"""Row 1115, S1: one shared setting row (name, one help line, the control at the right, a thin rule between rows) in the Settings cards,
in a real browser at 1400 and 900 px, light and dark. Run: python3 dev/run_tests.py test_setting_row_1115

This first step moves the Freshness and Gantt cards onto the row. Chrome is required: these tests fail, never skip, without it."""
import unittest

from test_settings_head import Head
from test_server import chrome

WIDTHS = (1400, 900)
MODES = ("light", "dark")
CONTROLS = ("review-days", "gantt-editor", "gantt-client", "gantt-name")
PROBE = """(() => {
  const out = {};
  for (const id of %s) {
    const c = document.getElementById(id), row = c && c.closest('.set-row');
    if (!row) { out[id] = null; continue; }
    const text = row.querySelector('.set-row-text'), ctl = row.querySelector('.set-row-ctl'), name = text && text.querySelector('label'), help = text && text.querySelector('small');
    const r = row.getBoundingClientRect(), t = text.getBoundingClientRect(), k = ctl.getBoundingClientRect(), cr = c.getBoundingClientRect();
    const prev = row.previousElementSibling, ps = prev && prev.classList.contains('set-row') ? getComputedStyle(row) : null;
    out[id] = {inCtl: ctl.contains(c), nameFor: name ? name.htmlFor : null, helpText: help ? help.textContent : null,
      describedBy: c.getAttribute('aria-describedby') || '', helpId: help ? help.id : null,
      ctlRight: r.right - k.right, ctlAfterText: k.left >= t.right - 1, sameLine: Math.abs((t.top + t.bottom) / 2 - (k.top + k.bottom) / 2) < Math.max(t.height, k.height),
      ruleTop: ps ? ps.borderTopWidth : null, inside: cr.right <= r.right + 1 && cr.left >= r.left - 1};
  }
  return out; })()""" % list(CONTROLS)


class SettingRow(Head):
    def test_S1_freshness_and_gantt_use_the_shared_row_with_the_control_at_the_right(self):
        for w in WIDTHS:
            for mode in MODES:
                with self.subTest(width=w, mode=mode), chrome() as cdp:
                    p = self.page(cdp)
                    self.open_settings(p, w, mode)
                    p.until("!!document.querySelector('#gantt-name') && !!document.querySelector('#review-days')", "the cards drew")
                    got = p.js(PROBE)
                    for id in CONTROLS:
                        g = got[id]
                        self.assertIsNotNone(g, id + " sits in a .set-row")
                        self.assertTrue(g["inCtl"], id + ": the control is in the row's control cell")
                        self.assertEqual(g["nameFor"], id, id + ": the name is its label")
                        self.assertTrue(g["ctlAfterText"] and g["sameLine"], id + ": the control is at the right of the name, on its line")
                        self.assertTrue(g["inside"], id + ": the control stays inside the row")
                        self.assertLess(abs(g["ctlRight"]), 1.5, id + ": the control cell ends at the row's right edge")
                    self.assertTrue(got["review-days"]["helpText"], "Freshness keeps its help line")
                    self.assertIn(got["review-days"]["helpId"], got["review-days"]["describedBy"].split(), "the box is described by its help line")
                    self.assertIsNone(got["gantt-editor"]["ruleTop"], "the first row of a card has no row above it, so no rule")
                    self.assertEqual(got["gantt-client"]["ruleTop"], "1px", "a thin rule between rows")
                    self.assertEqual(got["gantt-name"]["ruleTop"], "1px", "a thin rule between rows")


if __name__ == "__main__":
    unittest.main()
