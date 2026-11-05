"""#679: pressing V or E (or the View | Edit switch) must not move the page. Run: python3 dev/run_tests.py test_mode_switch_no_shift

Real browser, the committed test page, the demo project (long: all sections, plus planted work items). At the top, the middle and
the bottom of the page, switch View to Edit and back and measure every section's top and height; the section nearest the top of the
screen must stay within 1 px of where it was. At 1400 and 900 px, light and dark, with a short page and a long one.
"""
import json
import os
import unittest

from test_glance_page import Setup, plant  # noqa: F401
from test_report_editor import tearDownModule  # noqa: F401
from test_server import chrome

MEASURE = """(() => {
  const q = (s) => document.querySelector(s);
  const bar = q('.top');
  return {y: window.scrollY, h: document.documentElement.scrollHeight, bar: bar ? Math.round(bar.getBoundingClientRect().height * 10) / 10 : null,
          secs: [...document.querySelectorAll('.secs > .sec')].map(e => { const r = e.getBoundingClientRect(); return [e.dataset.id, Math.round(r.top * 10) / 10, Math.round(r.height * 10) / 10]; })};
})()"""

NEAREST = """(() => {
  const line = document.querySelector('.top').getBoundingClientRect().bottom;
  for (const e of document.querySelectorAll('.secs > .sec:not(.is-hidden)')) { const r = e.getBoundingClientRect(); if (r.bottom > line + 1) return [e.dataset.id, r.top]; }
  return null;
})()"""


class NoShift(Setup):
    def where(self, p, frac):
        """Scroll to a place: 0 top, 1 bottom."""
        p.js(f"window.scrollTo(0, Math.round((document.documentElement.scrollHeight - innerHeight) * {frac}))")
        p.js("new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")

    def one(self, width, dark, frac, via_key=False, tall=1100):
        out = []
        with chrome() as cdp:
            p = self.show(cdp, width, dark)
            cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": tall, "deviceScaleFactor": 1, "mobile": False}, p.sid)
            p.js("document.fonts && document.fonts.ready")
            self.where(p, frac)
            for step in ("edit", "view"):
                before = p.js(MEASURE)
                near = p.js(NEAREST)
                if via_key:
                    p.js("document.activeElement && document.activeElement.blur()")
                    p.key("e" if step == "edit" else "v")
                    p.until(f"document.querySelector('#report').dataset.mode === '{step}'", step)
                else:
                    getattr(p, step)()
                p.js("new Promise(r => setTimeout(r, 300))")
                after = p.js(MEASURE)
                now = dict((s[0], s[1]) for s in after["secs"])
                moved = abs(now[near[0]] - near[1]) if near else 0
                out.append((step, near, moved, before, after))
        return out

    def test_the_nearest_section_does_not_move(self):
        for width in (1400, 900):
            for dark in (False, True):
                for frac in (0, 0.5, 1):
                    with self.subTest(width=width, dark=dark, at=frac):
                        for step, near, moved, before, after in self.one(width, dark, frac):
                            if os.environ.get("PROBE"):
                                deltas = [(b[0], round(a[1] - b[1], 1), round(a[2] - b[2], 1)) for b, a in zip(before["secs"], after["secs"]) if abs(a[1] - b[1]) > 0.5 or abs(a[2] - b[2]) > 0.5]
                                print(f"{width} {'dark' if dark else 'light'} at {frac} -> {step}: y {before['y']}->{after['y']} h {before['h']}->{after['h']} bar {before['bar']}->{after['bar']} nearest {near} moved {moved:.1f} changed {deltas}")
                            self.assertLessEqual(moved, 1, f"{step}: {near} moved {moved}px")

    def test_the_keys_v_and_e_do_not_move_it_either_and_a_short_page_stays_put(self):
        for tall, label in ((1100, "long page"), (4000, "short page")):
            for frac in (0, 0.5, 1):
                with self.subTest(page=label, at=frac):
                    for step, near, moved, before, after in self.one(1400, False, frac, via_key=True, tall=tall):
                        self.assertLessEqual(moved, 1, f"{step} by key: {near} moved {moved}px")


if __name__ == "__main__":
    unittest.main()
