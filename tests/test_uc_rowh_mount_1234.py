"""Row 1234: the use case scroll box is n measured rows tall from the first draw and after a row opens, with no window resize.

The width is set before the page loads (opened(width=...)), so no resize event reaches the page: only the per-render layout
effect in UseCases.jsx can measure --ucrow-h. The first row is 41 px (1400) or 58 px (900) against the 3.25rem = 52 px fallback, so the fallback
cannot pass for a measured row. Widths 1400 and 900 px only. Fictional plant data.

Run: PYTHONPATH=../src:../vendor:. python3 -m unittest test_uc_rowh_mount_1234  (inside tests/)
"""
import tempfile
import unittest
from pathlib import Path

import test_server  # noqa: E402,F401  (marks this file as a browser test for the tiers)
from test_publish import chrome, opened, wait  # noqa: E402
from test_uc_rowh_1234 import made  # noqa: E402

BOX = "document.querySelector('.uc .ucrows')"
ROWS = ("(u => { const r = [...u.querySelectorAll(':scope > .ucrow')]; const b = u.getBoundingClientRect();"
        " return { box: b.height, closed: r.filter(l => !l.classList.contains('open')).map(l => l.getBoundingClientRect().height),"
        " fully: r.filter(l => l.getBoundingClientRect().bottom <= b.bottom + 1).length, client: u.clientHeight, scroll: u.scrollHeight,"
        " overflowY: getComputedStyle(u).overflowY, fallback: parseFloat(getComputedStyle(document.documentElement).fontSize) * 3.25 };"
        f" }})({BOX})")


class Browser(unittest.TestCase):
    def draw(self, cdp, tmp, width, long=True):
        pub, text = made({"n": 3, "scroll": True, "tracker": "top"}, long=long)
        path = Path(tmp) / "r.html"
        path.write_text(text, encoding="utf-8")
        sid = opened(cdp, path.as_uri(), width)
        self.assertTrue(wait(lambda: cdp.js("document.documentElement.dataset.ready", sid) == "1"))
        self.assertTrue(wait(lambda: cdp.js(f"!!{BOX}", sid)))
        return sid

    def test_first_draw_is_n_measured_rows_without_a_resize(self):
        for width in (1400, 900):
            with self.subTest(width=width), tempfile.TemporaryDirectory() as tmp, chrome() as cdp:
                sid = self.draw(cdp, tmp, width)
                got = cdp.js(ROWS, sid)
                self.assertGreater(abs(got["closed"][0] - got["fallback"]), 4, f"the long rows must differ from the fallback for this test to mean anything: {got}")
                self.assertAlmostEqual(got["box"], sum(got["closed"][:3]), delta=1, msg=f"first draw: the box is the first 3 measured rows tall: {got}")

    def test_the_box_scrolls_and_measures_a_closed_row_when_the_first_row_opens(self):
        for width in (1400, 900):
            with self.subTest(width=width), tempfile.TemporaryDirectory() as tmp, chrome() as cdp:
                sid = self.draw(cdp, tmp, width)
                before = cdp.js(ROWS, sid)
                self.assertEqual(before["overflowY"], "auto", before)
                self.assertGreater(before["scroll"], before["client"] + 1, f"more rows than fit must scroll: {before}")
                cdp.js("document.querySelector('.uc .ucrows > .ucrow button, .uc .ucrows > .ucrow [role=button], .uc .ucrows > .ucrow summary').click()", sid)
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.uc .ucrows > .ucrow.open')", sid)))
                after = cdp.js(ROWS, sid)
                self.assertAlmostEqual(after["box"], sum(before["closed"][:3]), delta=1, msg=f"the box stays the first 3 rows as they were closed (before is all closed), never moved by the open one: {before} -> {after}")

    def test_a_resize_event_that_arrives_after_the_first_row_opens_leaves_the_box_alone(self):
        # Row 1551: the macOS shard saw the box grow by one open row's share (789 vs 585). A resize event that comes late (ucRefit.js says slow on macOS) must not drop the open row from the fit when the width did not change.
        for width in (1400, 900):
            with self.subTest(width=width), tempfile.TemporaryDirectory() as tmp, chrome() as cdp:
                sid = self.draw(cdp, tmp, width)
                before = cdp.js(ROWS, sid)
                cdp.js("document.querySelector('.uc .ucrows > .ucrow [role=button]').click()", sid)
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.uc .ucrows > .ucrow.open')", sid)))
                cdp.js("window.dispatchEvent(new Event('resize'))", sid)
                after = cdp.js(ROWS, sid)
                self.assertAlmostEqual(after["box"], sum(before["closed"][:3]), delta=1, msg=f"a late resize event with the same width moved the box: {before} -> {after}")


if __name__ == "__main__":
    unittest.main()
