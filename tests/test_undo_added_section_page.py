"""Row 994: Undo of an added Gantt section. The section must be gone from the page by the time the toast says "Undone." (and stay gone),
not drawn for about a second after it. The page is sampled in its own clock (requestAnimationFrame), from the press of Undo to 1.5 s after
the toast says "Undone.", so a late redraw cannot hide between two polls from the test.

Run: python3 dev/run_tests.py test_undo_added_section_page
The real page and a real server over the fictional demo report (the harness of tests/test_report_editor.py), headless Chrome at 1400 px.
"""
import os
import time
import unittest

from test_report_editor import Base  # noqa: E402
from test_server import chrome  # noqa: E402

RUNS = int(os.environ.get("RUNS", "3"))          # more runs to hunt a rare lag: RUNS=12

SAMPLE = """(function(){
  var out = window.__undo = {pressed: performance.now(), done: null, rows: []};
  function n(){ return document.querySelectorAll('.secs > .sec[data-type="gantt"]').length; }
  function say(){ var t = document.querySelector('.toast-text'); return t ? t.textContent : ''; }
  function tick(){
    var now = performance.now() - out.pressed, s = say();
    if (out.done === null && s === 'Undone.') out.done = now;
    out.rows.push([Math.round(now), n(), out.done === null ? 0 : 1]);
    if (out.done === null || now < out.done + 1500) requestAnimationFrame(tick); else out.finished = true;
  }
  requestAnimationFrame(tick);
  document.querySelector('[data-undo]').click();
})()"""


class UndoAddedSection(Base):
    def add_gantt(self, p):
        p.js("document.querySelector('[data-id=\"ABC-S-003\"] [data-options]').click()")
        p.until("!!document.querySelector('[data-id=\"ABC-S-003\"] .menu')", "the menu opened")
        p.js("document.querySelector('[data-id=\"ABC-S-003\"] [data-act=add]').click()")
        p.until("!!document.querySelector('[data-template=gantt] input')", "Add a section offers Gantt")
        p.js("document.querySelector('[data-template=gantt] input').click()")
        p.js("document.querySelector('button[data-place]').click()")
        p.until("document.querySelectorAll('.secs > .sec[data-type=\"gantt\"]').length === 1", "the Gantt section is drawn")
        p.until("!!document.querySelector('[data-undo]')", "the toast offers Undo")
        time.sleep(0.3)

    def test_an_undone_gantt_section_is_gone_when_the_toast_says_undone_and_stays_gone(self):
        for run in range(RUNS):
            with chrome() as cdp:
                p = self.visit(cdp)
                p.edit()
                self.add_gantt(p)
                p.js(SAMPLE)
                p.until("window.__undo.finished === true", "sampled", 15)
                got = p.js("window.__undo")
                self.assertIsNotNone(got["done"], "the toast said Undone.")
                late = [r for r in got["rows"] if r[2] == 1 and r[1] != 0]
                self.assertEqual(late, [], f"run {run}: the Gantt section was still drawn after 'Undone.' (ms, count, said): {late[:5]}")
                self.assertEqual(p.js("document.querySelectorAll('.secs > .sec[data-type=\"gantt\"]').length"), 0)


if __name__ == "__main__":
    unittest.main()
