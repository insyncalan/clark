"""Row 1615: the Work items footer in View AND Edit (Classic), at 1400 and 900, light and dark, for a pair (left: Most 2 so Show all items is drawn; right:
Most 10 so it is not). Review all N items is ONE line of 32 px, the count is never clipped (no ellipsis), and at 1400 Review all sits the same distance from
the top of its own foot on both cards; the feet are bottom-aligned, so the tops differ by exactly the difference of the foot heights (measured at run time).
Never asserts equal absolute tops in Edit. Run: CLARK_CHROME=/usr/local/bin/creaite-chrome python3 dev/run_tests.py test_wil_foot_one_line_1615.py"""
import json
import unittest

import test_wil_footer_one_row_1475 as F
from test_report_editor import tearDownModule  # noqa: F401
from test_server import chrome

VIS = """(ref => { const sec = document.querySelector('[data-id="' + ref + '"]'); const vis = (q) => [...sec.querySelectorAll(q)].find((e) => e.offsetParent !== null) || null;
  const foot = vis('[data-wil-foot]'); const r = (e) => { if (!e) return null; const b = e.getBoundingClientRect(); return {top: b.top, bottom: b.bottom, h: b.height}; };
  const count = foot && foot.querySelector('[data-wil-count]');
  return {foot: r(foot), all: r(foot && foot.querySelector('[data-wil-all]')), rev: r(foot && foot.querySelector('[data-wil-review]')),
    count: count ? {sw: count.scrollWidth, cw: count.clientWidth, to: getComputedStyle(count).textOverflow} : null}; })"""


def vis(p, ref):
    return p.js(f"({VIS})({json.dumps(ref)})")


class Foot(F.FooterOneRow):
    """The served Classic page; main's own tests live in test_wil_footer_one_row_1475.py, so they are switched off here."""

    def test_review_all_is_one_line_and_level_in_edit_and_view_at_1400_and_900(self):
        """Mutant: rules-2.css loses `white-space: nowrap; flex: none;` on `.wil-foot .wil-all-b, .wil-foot .wil-review` (Review all wraps to two lines), or
        `.wil-foot { align-items: flex-start; }` (Review all is no longer the same distance from its foot's top on both cards)."""
        a, b = self.pair(2, 10)
        for width in self.widths():
            for dark in (False, True):
                for edit in (False, True):
                    with self.subTest(width=width, dark=dark, edit=edit), chrome() as cdp:
                        p = self.show(cdp, width, dark)
                        self.drawn(p, a, b)
                        if edit:
                            p.edit()
                            p.until(f"!!document.querySelector('[data-id=\"{a}\"] [data-wil-review]')", "the footer is there in Edit")
                        ga, gb = vis(p, a), vis(p, b)
                        where = f"{width} dark={dark} edit={edit}: {ga} {gb}"
                        self.assertIsNotNone(ga["all"], where)
                        self.assertIsNone(gb["all"], where)
                        for g in (ga, gb):
                            self.assertEqual(round(g["rev"]["h"]), 32, f"Review all is one line, 32 high: {where}")
                            if g["count"]:
                                self.assertLessEqual(g["count"]["sw"], g["count"]["cw"], f"the count is not clipped: {where}")
                                self.assertNotEqual(g["count"]["to"], "ellipsis", where)
                        if width == 1400:
                            da, db = ga["rev"]["top"] - ga["foot"]["top"], gb["rev"]["top"] - gb["foot"]["top"]
                            self.assertAlmostEqual(da, db, delta=0.5, msg=f"Review all is the same distance from its own foot's top: {where}")
                            self.assertAlmostEqual(abs(ga["rev"]["top"] - gb["rev"]["top"]), abs(ga["foot"]["h"] - gb["foot"]["h"]), delta=1, msg=f"top diff = foot height diff: {where}")


for _name in [n for n in dir(F.FooterOneRow) if n.startswith("test_")]:
    setattr(Foot, _name, None)

if __name__ == "__main__":
    unittest.main()
