"""Row 1340: in Edit, the Work items filter line fills its section's inner width at 1400 and 900, in Classic (Cards is frozen and not tested here).

Run: python3 dev/run_tests.py test_work_items_line_width_1340
Source of the rule: the ticket comment "Correction" (the 1130 px figure is withdrawn: a full-width section's line fills the section's inner
width; measured 948 px in a 1012 px section at 1400 and 789 in 853 at 900) and the mock-up's block .fline-wrap (work-items-mockup.html:35).
Nothing here pins a pixel number: the line is compared with the section's own inner width, so a fixed or capped width fails at once.
A half-width card is by design narrower (the ticket: out of scope), so no half-width case is tested here: only a full-width section is measured.
Chrome is required: the browser tests fail, never skip, without it.
"""
import json
import unittest

import test_server  # noqa: F401  (this file drives Chrome through the template harness; the browser tier reads this line)

import test_tpl_workitems as T
from test_work_items_mockup_1195 import Look

LIST = {"mode": "all", "columns": ["id", "owner", "due", "priority"], "owner": ["Pat Demo", "Lee Demo"]}
# the section's content box (its width less its own padding and border) against the filter line's box and its wrapper's box
MEASURE = """JSON.stringify((() => {
  const sec = document.querySelector(%r), box = sec.querySelector('.wil-edit');
  const cs = getComputedStyle(box), w = box.getBoundingClientRect();
  const inner = [w.left + parseFloat(cs.paddingLeft) + parseFloat(cs.borderLeftWidth), w.right - parseFloat(cs.paddingRight) - parseFloat(cs.borderRightWidth)];
  const wrap = sec.querySelector('[data-wil-line]').getBoundingClientRect(), line = sec.querySelector('[data-wil-line] .fline').getBoundingClientRect();
  return {inner: inner, wrap: [wrap.left, wrap.right], line: [line.left, line.right], sec: sec.getBoundingClientRect().width};
})())"""


class Width(object):
    """The checks; the two classes below say which page they run on."""

    def measure(self, ref, width):
        with T.chrome() as cdp:
            p = self.show(cdp, width)
            sec = f'[data-id="{ref}"]'
            p.edit()
            p.until(f"!!document.querySelector('{sec} [data-wil-line] .fline')", "the Edit filter line drew")
            return json.loads(p.js(MEASURE % sec))

    def test_a_full_width_section_has_the_line_across_its_whole_inner_width_at_1400_and_900(self):
        ref = self.add(LIST)
        for width in (1400, 900):
            with self.subTest(width=width):
                got = self.measure(ref, width)
                (il, ir), (wl, wr), (ll, lr) = got["inner"], got["wrap"], got["line"]
                self.assertGreater(ir - il, 400, f"the section has an inner width to fill: {got}")
                self.assertAlmostEqual(wl, il, delta=1, msg=f"the wrapper starts at the inner left edge: {got}")
                self.assertAlmostEqual(wr, ir, delta=1, msg=f"the wrapper ends at the inner right edge: {got}")
                self.assertGreaterEqual(ll, il - 1, f"the line stays inside on the left: {got}")
                self.assertLessEqual(lr, ir + 1, f"the line stays inside on the right: {got}")
                # the line is exactly the section's inner width (measured: 985 px at 1400), so a fixed or capped width fails at once
                self.assertAlmostEqual(lr - ll, ir - il, delta=2, msg=f"the line fills the inner width, not a fixed or capped width: {got}")


class Classic(Width, Look):
    classic = True


if __name__ == "__main__":
    unittest.main()
