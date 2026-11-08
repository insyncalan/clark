"""#679: pressing V or E (or the View | Edit switch) must not move the page. Run: python3 dev/run_tests.py test_mode_switch_no_shift

Real browser, the committed test page, the demo project (long: all sections, plus planted work items). At the top, the middle and
the bottom of the page, switch View to Edit and back and measure every section's top and height; the section being read (row 756: the first with 64 px of itself under the top bar, not a thin tail of the one before) must stay within
1 px of where it was. At 1400 and 900 px, light and dark, with a short page and a long one.
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
  let best = null, most = 0, below = null;
  for (const e of document.querySelectorAll('.secs > .sec:not(.is-hidden)')) {
    const r = e.getBoundingClientRect(); const seen = Math.min(r.bottom, innerHeight) - Math.max(r.top, line);
    if (seen >= 64) return [e.dataset.id, r.top];
    if (seen > most) { most = seen; best = [e.dataset.id, r.top]; }
    if (!below && r.top >= line) below = [e.dataset.id, r.top];
  }
  return best || below;
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

    def test_a_hidden_section_nearest_the_top_does_not_move_the_one_after_it(self):
        """Row 699: Edit draws a hidden section dimmed and View drops it. With one at the top of the screen, switching to View must hold
        the next section that stays in View where it was, not shift the page by the height of the dimmed one."""
        rows = self.store.read("report_sections", "ABC")
        with self.store.step("dashboard", "test") as st:
            for r in [r for r in rows if r["type"] != "glance"][1:4]:
                st.update("report_sections", r["id"], {"hidden": 1})
        with chrome() as cdp:
            p = self.show(cdp, 1400, False)
            cdp.call("Emulation.setDeviceMetricsOverride", {"width": 1400, "height": 700, "deviceScaleFactor": 1, "mobile": False}, p.sid)      # View keeps room to scroll
            p.edit()
            p.js("new Promise(r => setTimeout(r, 300))")
            ids = p.js("[...document.querySelectorAll('.secs > .sec.is-hidden')].map(e => e.dataset.id)")
            self.assertTrue(ids, "Edit draws a hidden section")
            for hid in ids:
                with self.subTest(hidden=hid):
                    p.js(f"(() => {{ const e = document.querySelector('.secs > .sec[data-id=\"{hid}\"]'); const bar = document.querySelector('.top').getBoundingClientRect().bottom; window.scrollBy(0, e.getBoundingClientRect().top - bar - 8); }})()")
                    p.js("new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")
                    near = p.js(NEAREST)
                    b4 = p.js(MEASURE)
                    self.assertNotIn(near[0], ids, "the section held is one that stays in View")
                    p.view()
                    p.js("new Promise(r => setTimeout(r, 300))")
                    m = p.js(MEASURE)
                    if os.environ.get("PROBE"):
                        print(hid, near, b4["y"], b4["h"], m["y"], m["h"])
                    after = dict((s[0], s[1]) for s in m["secs"])
                    if m["y"] == 0 and after[near[0]] < near[1]:
                        continue            # View is shorter and the page cannot scroll above its top: nothing can hold it
                    self.assertLessEqual(abs(after[near[0]] - near[1]), 1, f"{near[0]} moved with {hid} hidden at the top")
                    p.edit()
                    p.js("new Promise(r => setTimeout(r, 300))")


if __name__ == "__main__":
    unittest.main()
