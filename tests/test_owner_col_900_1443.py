"""Row 1443: the Work items owner column in Edit, at 900 and 1400 px, light and dark.

Run: python3 dev/run_tests.py test_owner_col_900_1443.py
Ruling (PM word 22-11 02:52): 130 px stays at 900 px; 170 px applies at full width only. The mock-up
(mockups/1195-work-items-template/work-items-mockup.html) has own:170 in its default S.w (line 1962) and no owner width for 900 px
(its only width rule is @media(max-width:640px), line 82, which hides the owner). The list is table.items (edit.css, the 900 px rule).
"""
import json
import unittest

from test_edit_cells_layout import Cells, chrome  # noqa: E402
from test_work_items import page_target  # noqa: E402

OWNER_PX_AT_900 = 130      # ruled: stays at 900 px
OWNER_PX_FULL = 170        # mock-up S.w.own, line 1962; shell.css `table.items .c-owner`
THEMES = ("light", "dark")

OWNER_WIDTH = r"""(() => { const th = document.querySelector('table.items th.c-owner') || document.querySelector('table.items .c-owner');
  return JSON.stringify({ w: th.getBoundingClientRect().width, css: getComputedStyle(th).width, sw: document.documentElement.scrollWidth, vw: innerWidth }); })()"""


class OwnerColumn(Cells):
    def width(self, cdp, width, theme):
        self.measure(cdp, width, theme)
        return json.loads(cdp.js(OWNER_WIDTH, self.sid))

    def measure(self, cdp, width, theme):
        got = super().measure(cdp, width, theme)
        self.sid = page_target(cdp)
        return got

    test_every_edit_cell_is_one_tidy_box_at_both_widths_in_both_looks = None   # inherited, run in its own file

    def test_owner_column_width_at_900_and_1400_light_and_dark(self):
        with chrome() as cdp:
            for width, want in ((900, OWNER_PX_AT_900), (1400, OWNER_PX_FULL)):
                for theme in THEMES:
                    got = self.width(cdp, width, theme)
                    print(f"owner column {width} px {theme}: {got['w']:.1f} px (computed {got['css']})")
                    self.assertAlmostEqual(got["w"], want, delta=1, msg=f"{width} px, {theme}")
                    self.assertLessEqual(got["sw"], got["vw"], f"{width} px, {theme}: no sideways scroll")

    def test_owner_column_is_pinned_at_900_and_not_at_1400(self):
        with chrome() as cdp:
            for theme in THEMES:
                at900 = self.width(cdp, 900, theme)["w"]
                at1400 = self.width(cdp, 1400, theme)["w"]
                self.assertAlmostEqual(at900, 130, delta=1, msg=f"{theme}: 900 px owner column is not 130 px")
                self.assertNotAlmostEqual(at1400, 130, delta=1, msg=f"{theme}: the 900 px rule reaches 1400 px")

    def test_owner_width_matches_the_ruled_value_at_900(self):
        # the mock-up's 170 px is the full-width value; at 900 px the ruled 130 px is kept (no 900 value in the mock-up)
        self.assertEqual(OWNER_PX_FULL, 170, "mock-up S.w.own")
        with chrome() as cdp:
            for theme in THEMES:
                got = self.width(cdp, 900, theme)["w"]
                self.assertAlmostEqual(got, OWNER_PX_AT_900, delta=1, msg=f"{theme}: owner column at 900 px")
                self.assertLess(got, OWNER_PX_FULL)


if __name__ == "__main__":
    unittest.main()
