"""Row 773: the Dashboard in Edit, against the prototype: the note in the bar is a blue chip and a hidden tile is dashed with no tint.

Run: python3 dev/run_tests.py test_dashboard_edit_look
1400 and 900 px, light and dark. (Start from last week's report, the Since the last report card and the Suggested line are features
and wording the build does not have; they are not part of this row.)
"""
import unittest

from test_glance_page import Setup
from test_report_editor import tearDownModule  # noqa: F401
from test_server import chrome


class EditLook(Setup):
    def test_the_note_is_a_chip_and_a_hidden_tile_is_dashed_and_untinted(self):
        for width in (1400, 900):
            for dark in (False, True):
                with self.subTest(width=width, dark=dark), chrome() as cdp:
                    p = self.show(cdp, width, dark)
                    p.edit()
                    p.until("!!document.querySelector('#report-hint') && !!document.querySelector('[data-tile=decisions].is-hidden')", "Edit drew")
                    hint = "getComputedStyle(document.querySelector('#report-hint'))"
                    self.assertNotIn(p.js(hint + ".backgroundColor"), ("rgba(0, 0, 0, 0)", "transparent"), "the note is a tinted chip")
                    self.assertGreater(float(p.js(hint + ".borderTopLeftRadius").replace("px", "")), 0)
                    self.assertGreater(float(p.js(hint + ".paddingLeft").replace("px", "")), 0)
                    fig = "getComputedStyle(document.querySelector('[data-tile=decisions] .fig'))"
                    self.assertEqual(p.js(fig + ".borderTopStyle"), "dashed")
                    self.assertEqual(p.js(fig + ".backgroundColor"), "rgba(0, 0, 0, 0)", "a hidden tile is not tinted")


if __name__ == "__main__":
    unittest.main()
