"""Row 1234: the use case scroll box is as tall as n real rows (--ucrow-h measured, not the 3.25rem fallback).

Run: ~/ag/slot.sh with, inside tests/: PYTHONPATH=../src:../vendor:. python3 -m unittest test_uc_rowh_1234
Widths 1400 and 900 px only. Fictional plant data.
"""
import copy
import json
import tempfile
import unittest
from pathlib import Path

import _publish_fixture as fx  # noqa: E402
from clark import page, publish  # noqa: E402
from test_publish import EMPTY_BRANDING, chrome, opened, wait  # noqa: E402
import test_server  # noqa: E402,F401


def made(view, extra=4, long=False):
    plant = fx.load()
    d = plant["data"]
    for i in range(extra):
        row = copy.deepcopy(d["use_cases"][0])
        row.update(id=f"PUB-U-1{i}", title=("LONGWORD" * 30 if long else "Extra") + f" {i}", ref=f"7.{i}", sort_order=10 + i)
        if long:
            row["headline"] = "headline words " * 40
        d["use_cases"].append(row)
    for s in plant["sections"]:
        if s["type"] == "usecases":
            s["body"] = json.dumps(view)
    pub = publish.select(fx.inputs(plant))
    return pub, publish.render(pub, page.page_html(EMPTY_BRANDING, view=True), plant["as_at"], pub["data"]["project"]["name"])



class Browser(unittest.TestCase):
    def draw(self, cdp, text, tmp, width):
        path = Path(tmp) / "r.html"
        path.write_text(text, encoding="utf-8")
        sid = opened(cdp, path.as_uri())
        self.assertTrue(wait(lambda: cdp.js("document.documentElement.dataset.ready", sid) == "1"))
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1000, "deviceScaleFactor": 1, "mobile": False}, sid)
        self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.uc .ucrows')", sid)))
        return sid


    def test_scroll_box_shows_n_rows(self):
        for width in (1400, 900):
            with self.subTest(width=width), tempfile.TemporaryDirectory() as tmp, chrome() as cdp:
                pub, text = made({"n": 3, "scroll": True, "tracker": "top"})
                sid = self.draw(cdp, text, tmp, width)
                got = cdp.js("(u => { const r = [...u.querySelectorAll(':scope > .ucrow')].map(l => l.getBoundingClientRect()); const b = u.getBoundingClientRect();"
                             " return { box: b.height, rows: r.map(x => x.height), fully: r.filter(x => x.bottom <= b.bottom + 1).length }; })(document.querySelector('.uc .ucrows'))", sid)
                self.assertEqual(got["fully"], 3, f"n=3 box shows {got['fully']} whole rows: {got}")
                self.assertAlmostEqual(got["box"], sum(got["rows"][:3]), delta=1, msg=f"the box is the first n measured rows tall, not the fallback: {got}")

    def test_the_measured_row_height_is_a_closed_row_even_when_the_first_row_is_open(self):
        for width in (1400, 900):
            with self.subTest(width=width), tempfile.TemporaryDirectory() as tmp, chrome() as cdp:
                pub, text = made({"n": 3, "scroll": True, "tracker": "top"})
                sid = self.draw(cdp, text, tmp, width)
                cdp.js("document.querySelector('.uc .ucrow:nth-child(1) .ucbar').click()", sid)
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.uc .ucrow.open')", sid)))
                got = cdp.js("(u => ({ open: u.querySelector(':scope > .ucrow:nth-child(1)').getBoundingClientRect().height, closed: u.querySelector(':scope > .ucrow:nth-child(2)').getBoundingClientRect().height,"
                             " v: parseFloat(u.style.getPropertyValue('--ucrow-h')) }))(document.querySelector('.uc .ucrows'))", sid)
                self.assertGreater(got["open"], got["closed"] + 1, f"an open row is taller, so the check can fail: {got}")
                self.assertAlmostEqual(got["v"], got["closed"], delta=1, msg=f"--ucrow-h is a closed row's height: {got}")


if __name__ == "__main__":
    unittest.main()
