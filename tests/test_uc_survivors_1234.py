"""Row 1234: tests that kill the mutants the three row 1234 test files let live.

U2 (the row height measured from an open row), U3 (a wrong --ucrow-h after the first render, hidden by the resize that
the row height test fires), U5 (the Enter key no longer opens a bar), H1 (the dash loses its muted colour).

Run: python3 dev/run_tests.py test_uc_survivors_1234
Widths 1400 and 900 px only. Fictional data.
"""
import tempfile
import unittest

from test_commit_dash_1234 import ROW2
from test_commitment_page import Flags, tearDownModule  # noqa: F401
from test_server import chrome
import test_uc_rowh_1234 as rowh


class RowHeightAfterARowOpens(rowh.Browser):
    def test_the_box_stays_n_closed_rows_tall_after_the_first_row_opens(self):
        for width in (1400, 900):
            with self.subTest(width=width), tempfile.TemporaryDirectory() as tmp, rowh.chrome() as cdp:
                pub, text = rowh.made({"n": 3, "scroll": True, "tracker": "top"})
                sid = self.draw(cdp, text, tmp, width)
                closed = cdp.js("document.querySelector('.uc .ucrows > .ucrow').getBoundingClientRect().height", sid)
                cdp.js("document.querySelector('.uc .ucrows > .ucrow .ucbar').click()", sid)
                self.assertTrue(rowh.wait(lambda: cdp.js("!!document.querySelector('.uc .ucrows > .ucrow .ucdetail')", sid)))
                box = cdp.js("document.querySelector('.uc .ucrows').getBoundingClientRect().height", sid)
                self.assertAlmostEqual(box, 3 * closed, delta=1, msg=f"n=3 closed rows are {closed} px each, the box is {box}")


class Bar(Flags):
    def test_enter_and_space_on_a_bar_open_and_close_it(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.show(cdp, width)
                bar = "document.querySelector('.ucrow .ucbar')"
                for key, then in (("Enter", "true"), (" ", "false")):
                    p.js(f"{bar}.dispatchEvent(new KeyboardEvent('keydown', {{key: {key!r}, bubbles: true, cancelable: true}}))")
                    p.until(f"{bar}.getAttribute('aria-expanded') === '{then}'", f"{key!r} made aria-expanded {then}")

    def test_the_dash_is_in_the_muted_colour_not_the_title_colour(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.show(cdp, width)
                dash = p.js(f"getComputedStyle(document.querySelector('{ROW2} [data-commit-none]')).color")
                muted = p.js("getComputedStyle(document.querySelector('.ucrow .uchead, .uc .ucsteps')).color")
                title = p.js("getComputedStyle(document.querySelector('.ucrow .uctitle')).color")
                self.assertNotEqual(muted, title, "the check can tell muted from title")
                self.assertEqual(dash, muted)


if __name__ == "__main__":
    unittest.main()
