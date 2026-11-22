"""Row 1277: the UseCases.jsx wiring of watchRefit, killed from the browser (Linux headless Chrome runs ResizeObserver).

Two mutants of UseCases.jsx survived the three uc_rowh files and the node test of ucRefit.js:
  1. the resize/fonts callback without shut.current.clear(): after a width change an open row keeps the closed height it had at the old width;
  2. watchRefit(window, document, null, ...) instead of box.current: no ResizeObserver, so a row changing size with no resize event and no render is never refitted.
Widths 1400 and 900 px only. Fictional plant data.

Run: PYTHONPATH=../src:../vendor:. python3 -m unittest test_uc_refit_wiring_1277  (inside tests/)
"""
import tempfile
import unittest
from pathlib import Path

import test_server  # noqa: E402,F401
from test_publish import chrome, opened, wait  # noqa: E402
from test_uc_rowheight_unequal_1234 import made  # noqa: E402

STATE = ("(u => { const r = [...u.querySelectorAll(':scope > .ucrow')];"
         " return { box: u.getBoundingClientRect().height, rows: r.map(x => x.getBoundingClientRect().height),"
         " open: r.map(x => x.classList.contains('open')), h: parseFloat(u.style.getPropertyValue('--ucrow-h')) || 0 }; })"
         "(document.querySelector('.uc .ucrows'))")


class Browser(unittest.TestCase):
    def draw(self, cdp, tmp, width):
        path = Path(tmp) / "r.html"
        path.write_text(made({"n": 3, "scroll": True, "tracker": "top"}), encoding="utf-8")
        sid = opened(cdp, path.as_uri(), width)
        self.assertTrue(wait(lambda: cdp.js("document.documentElement.dataset.ready", sid) == "1"))
        self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.uc .ucrows')", sid)))
        self.assertTrue(wait(lambda: (lambda z: abs(z["box"] - sum(z["rows"][:3])) <= 2)(cdp.js(STATE, sid))), "first fit")
        return sid

    def test_a_width_change_drops_the_closed_height_an_open_row_remembered_at_the_old_width(self):
        # Mutant: the resize callback without shut.current.clear(). Row 0 is open, so only the memory holds its closed height; it was measured at 1400.
        with tempfile.TemporaryDirectory() as tmp, chrome() as cdp:
            sid = self.draw(cdp, tmp, 1400)
            cdp.js("document.querySelectorAll('.uc .ucrows > .ucrow .ucbar')[0].click()", sid)
            self.assertTrue(wait(lambda: cdp.js(STATE, sid)["open"][0]))
            cdp.call("Emulation.setDeviceMetricsOverride", {"width": 900, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)

            def settled():
                z = cdp.js(STATE, sid)
                shut = [h for h, o in zip(z["rows"][:3], z["open"][:3]) if not o]
                return z["open"][0] and len(shut) == 2 and abs(z["h"] - sum(shut) / 2) <= 1
            self.assertTrue(wait(settled), f"after 1400 -> 900 the row height is the mean of the closed rows measured now, no stale 1400 height of the open row: {cdp.js(STATE, sid)}")

    def test_a_row_changing_size_with_no_resize_and_no_render_refits_the_box(self):
        # Mutant: watchRefit(window, document, null, ...). Only the ResizeObserver sees an inline height change (the observer watches the content box, so padding would not do); no resize event, no render, fonts already loaded.
        for width in (1400, 900):
            with self.subTest(width=width), tempfile.TemporaryDirectory() as tmp, chrome() as cdp:
                sid = self.draw(cdp, tmp, width)
                before = cdp.js(STATE, sid)
                cdp.js("document.querySelectorAll('.uc .ucrows > .ucrow')[1].style.minHeight = '300px'", sid)
                self.assertTrue(wait(lambda: cdp.js(STATE, sid)["rows"][1] > before["rows"][1] + 100), "the second row grew")
                self.assertTrue(wait(lambda: (lambda z: abs(z["box"] - sum(z["rows"][:3])) <= 2)(cdp.js(STATE, sid))),
                                f"the box is refitted to the three rows as they are now: {before} -> {cdp.js(STATE, sid)}")


if __name__ == "__main__":
    unittest.main()
