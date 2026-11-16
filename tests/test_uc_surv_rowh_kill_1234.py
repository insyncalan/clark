"""Row 1234: the use case scroll box measures its rows again when the window is resized and again after a later draw.

Run: ~/ag/slot.sh with, inside tests/: PYTHONPATH=../src:../vendor:. python3 -m unittest test_uc_surv_rowh_kill_1234
Widths 1400 and 900 px only. Fictional plant data. Kills two mutants of the measuring code in UseCases.jsx:
the resize handler that no longer clears the saved row heights, and the layout effect that runs once instead of after every draw.
"""
import tempfile
import unittest
from pathlib import Path

from test_publish import chrome, opened, wait  # noqa: E402
from test_uc_rowheight_unequal_1234 import SIZES, made  # noqa: E402
import test_server  # noqa: E402,F401

VIEW = {"n": 3, "scroll": True, "tracker": "top"}
FIRST3 = "(r => r.slice(0, 3).reduce((a, b) => a + b, 0))"


class Remeasure(unittest.TestCase):
    def draw(self, cdp, tmp, width):
        path = Path(tmp) / "r.html"
        path.write_text(made(VIEW), encoding="utf-8")
        sid = opened(cdp, path.as_uri())
        self.assertTrue(wait(lambda: cdp.js("document.documentElement.dataset.ready", sid) == "1"))
        self.size(cdp, sid, width)
        self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.uc .ucrows')", sid)))
        return sid

    def size(self, cdp, sid, width):
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1000, "deviceScaleFactor": 1, "mobile": False}, sid)

    def fits(self, cdp, sid):
        got = cdp.js(SIZES, sid)
        return abs(got["box"] - sum(got["rows"][:3])) <= 2 and got["open"] == 0

    def test_the_box_is_the_first_three_rows_again_after_the_window_changes_width(self):
        for first, then in ((1400, 900), (900, 1400)):
            with self.subTest(first=first, then=then), tempfile.TemporaryDirectory() as tmp, chrome() as cdp:
                sid = self.draw(cdp, tmp, first)
                self.assertTrue(wait(lambda: self.fits(cdp, sid)), f"the box fits at {first}: {cdp.js(SIZES, sid)}")
                before = cdp.js(SIZES, sid)
                self.size(cdp, sid, then)
                self.assertTrue(wait(lambda: abs(cdp.js(SIZES, sid)["rows"][0] - before["rows"][0]) > 2), "the rows changed height with the width")
                self.assertTrue(wait(lambda: self.fits(cdp, sid)), f"the box is the first three rows tall at {then}, not at the old height {before['box']}: {cdp.js(SIZES, sid)}")

    def test_a_row_that_is_open_when_the_window_changes_width_leaves_no_old_height_in_the_box(self):
        for first, then in ((1400, 900), (900, 1400)):
            with self.subTest(first=first, then=then), tempfile.TemporaryDirectory() as tmp, chrome() as cdp:
                sid = self.draw(cdp, tmp, first)
                self.assertTrue(wait(lambda: self.fits(cdp, sid)))
                before = cdp.js(SIZES, sid)
                cdp.js("document.querySelectorAll('.uc .ucrows > .ucrow .ucbar')[0].click()", sid)
                self.assertTrue(wait(lambda: cdp.js(SIZES, sid)["open"] == 1))
                self.size(cdp, sid, then)
                self.assertTrue(wait(lambda: abs(cdp.js(SIZES, sid)["rows"][1] - before["rows"][1]) > 2 or abs(cdp.js(SIZES, sid)["rows"][2] - before["rows"][2]) > 2), "the closed rows changed height")
                # the open row has no measure at the new width, so the box is three times the mean of the two closed rows of the first three, not of a height kept from the old width
                self.assertTrue(wait(lambda: abs(cdp.js(SIZES, sid)["box"] - 1.5 * (cdp.js(SIZES, sid)["rows"][1] + cdp.js(SIZES, sid)["rows"][2])) <= 3),
                                f"the box is three times the mean of the closed rows at {then}: {cdp.js(SIZES, sid)}")

    def test_the_box_is_the_first_three_rows_again_after_a_row_opens_when_the_closed_rows_changed_height(self):
        for width in (1400, 900):
            with self.subTest(width=width), tempfile.TemporaryDirectory() as tmp, chrome() as cdp:
                sid = self.draw(cdp, tmp, width)
                self.assertTrue(wait(lambda: self.fits(cdp, sid)))
                before = cdp.js(SIZES, sid)
                cdp.js("document.querySelectorAll('.uc .ucrows > .ucrow > .ucbar').forEach(b => { b.style.paddingTop = '60px'; })", sid)
                self.assertTrue(wait(lambda: cdp.js(SIZES, sid)["rows"][1] > before["rows"][1] + 40), "the rows grew")
                cdp.js("document.querySelectorAll('.uc .ucrows > .ucrow .ucbar')[4].click()", sid)
                self.assertTrue(wait(lambda: cdp.js(SIZES, sid)["open"] == 1))
                self.assertTrue(wait(lambda: abs(cdp.js(SIZES, sid)["box"] - cdp.js(f"{FIRST3}({SIZES}.rows)", sid)) <= 2),
                                f"the box follows the first three rows after the draw: {cdp.js(SIZES, sid)}")


if __name__ == "__main__":
    unittest.main()
