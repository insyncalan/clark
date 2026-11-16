"""Row 1234: on paper a use case list with scroll on prints every row (no scroll box that cuts rows off).

Run: ~/ag/slot.sh with, inside tests/: PYTHONPATH=../src:../vendor:. python3 -m unittest test_uc_print_1234
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
    def show(self, cdp, text, tmp, width):
        path = Path(tmp) / "r.html"
        path.write_text(text, encoding="utf-8")
        sid = opened(cdp, path.as_uri())
        self.assertTrue(wait(lambda: cdp.js("document.documentElement.dataset.ready", sid) == "1"))
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1000, "deviceScaleFactor": 1, "mobile": False}, sid)
        self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.uc .ucrows')", sid)))
        return sid


    def test_scroll_on_prints_every_row(self):
        for width in (1400, 900):
            with self.subTest(width=width), tempfile.TemporaryDirectory() as tmp, chrome() as cdp:
                pub, text = made({"n": 2, "scroll": True, "tracker": "top"})
                sid = self.show(cdp, text, tmp, width)
                js = lambda s: cdp.js(s, sid)  # noqa: E731
                total = js("document.querySelectorAll('.ucrows > .ucrow').length")
                self.assertGreater(total, 2)
                cdp.call("Emulation.setEmulatedMedia", {"media": "print"}, sid)
                js("window.dispatchEvent(new Event('beforeprint'))")
                box = js("(u => ({ client: u.clientHeight, scroll: u.scrollHeight, rows: u.querySelectorAll(':scope > .ucrow').length }))(document.querySelector('.uc .ucrows'))")
                self.assertEqual(box["rows"], total)
                self.assertLessEqual(box["scroll"], box["client"] + 1, f"printed box cuts rows off: {box}")


if __name__ == "__main__":
    unittest.main()
