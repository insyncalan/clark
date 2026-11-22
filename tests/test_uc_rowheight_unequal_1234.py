"""Row 1234: the use case scroll box holds exactly n rows when the rows are not equal, and does not move when a row is opened.

Run: ~/ag/slot.sh with, inside tests/: PYTHONPATH=../src:../vendor:. python3 -m unittest test_uc_rowheight_unequal_1234
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

LONG = [True, False, True, True, False]       # four long rows and two short ones: the first three are long, short, long


def made(view):
    plant = fx.load()
    d = plant["data"]
    base = d["use_cases"][0]
    d["use_cases"] = []
    for i, long in enumerate(LONG):
        row = copy.deepcopy(base)
        row.update(id=f"PUB-U-1{i}", title=("LONGWORD" * 30 if long else "Short") + f" {i}", ref=f"7.{i}", sort_order=10 + i)
        row["headline"] = "headline words " * 40 if long else "Brief"
        d["use_cases"].append(row)
    for s in plant["sections"]:
        if s["type"] == "usecases":
            s["body"] = json.dumps(view)
    pub = publish.select(fx.inputs(plant))
    return publish.render(pub, page.page_html(EMPTY_BRANDING, view=True), plant["as_at"], pub["data"]["project"]["name"])


SIZES = ("(u => { const r = [...u.querySelectorAll(':scope > .ucrow')]; const b = u.getBoundingClientRect();"
         " return { box: b.height, top: b.top, rows: r.map(x => x.getBoundingClientRect().height), open: r.filter(x => x.classList.contains('open')).length }; })"
         "(document.querySelector('.uc .ucrows'))")


class Browser(unittest.TestCase):
    def draw(self, cdp, tmp, width):
        path = Path(tmp) / "r.html"
        path.write_text(made({"n": 3, "scroll": True, "tracker": "top"}), encoding="utf-8")
        sid = opened(cdp, path.as_uri())
        self.assertTrue(wait(lambda: cdp.js("document.documentElement.dataset.ready", sid) == "1"))
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1000, "deviceScaleFactor": 1, "mobile": False}, sid)
        self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.uc .ucrows')", sid)))
        return sid

    def test_box_is_the_first_n_rows_and_stays_when_a_row_opens(self):
        for width in (1400, 900):
            with self.subTest(width=width), tempfile.TemporaryDirectory() as tmp, chrome() as cdp:
                sid = self.draw(cdp, tmp, width)
                self.assertTrue(wait(lambda: (lambda z: abs(z["box"] - sum(z["rows"][:3])) <= 2)(cdp.js(SIZES, sid))), "the page refits the box to the first three rows (#1277)")       # wait for the page's own refit, not for the resize event
                shut = cdp.js(SIZES, sid)
                self.assertGreater(shut["rows"][0], 2 * shut["rows"][1], f"the first row is long and the second short: {shut}")
                self.assertAlmostEqual(shut["box"], sum(shut["rows"][:3]), delta=2, msg=f"the box is the first three rows tall, not three times one row: {shut}")
                for n in (0, 1, 2):
                    cdp.js(f"document.querySelectorAll('.uc .ucrows > .ucrow .ucbar')[{n}].click()", sid)
                    self.assertTrue(wait(lambda: cdp.js(SIZES, sid)["open"] == n + 1))
                    now = cdp.js(SIZES, sid)
                    self.assertAlmostEqual(now["box"], shut["box"], delta=2, msg=f"opening row {n} moved the box: {shut} then {now}")
                    self.assertAlmostEqual(now["top"], shut["top"], delta=2, msg=f"the box top moved: {shut} then {now}")


if __name__ == "__main__":
    unittest.main()
