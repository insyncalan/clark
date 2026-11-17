"""Row 1234: the published file draws the use case summary with the view setting {n, scroll, tracker} that sits in the publish entry.
Nine use cases are in the file, n 2, scrolling, tracker below: the list is two rows high and scrolls, and the count bar is under the rows. At 1400 and 900 px.

Run: python3 dev/run_tests.py test_uc_published_view_1234
Headless Chrome (required)."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

import _publish_fixture as fx  # noqa: E402
from clark import page, publish  # noqa: E402
from test_publish import EMPTY_BRANDING, chrome, opened, wait  # noqa: E402
import test_server  # noqa: E402,F401  (this file drives Chrome through test_publish: it is in the browser tier)

ROWS = 9
VIEW = {"n": 2, "scroll": True, "tracker": "bottom"}


def made(view):
    plant = fx.load()
    d = plant["data"]
    for k in range(8):
        row = copy.deepcopy(d["use_cases"][0])
        row.update(id=f"PUB-U-10{k}", title=f"ZQ-EXTRA-USECASE-{k}", ref=f"9.{k}", sort_order=10 + k)
        d["use_cases"].append(row)
    for s in plant["sections"]:
        if s["type"] == "usecases":
            s["body"] = "" if view is None else json.dumps(view)
    pub = publish.select(fx.inputs(plant))
    return pub, publish.render(pub, page.page_html(EMPTY_BRANDING, view=True), plant["as_at"], pub["data"]["project"]["name"])


MEASURE = """JSON.stringify((() => { const u = document.querySelector('[data-uc-section]'), ul = u.querySelector('.ucrows'), li = [...ul.children], strip = u.querySelector('.ucstrip');
  const r = ul.getBoundingClientRect(), s = strip && strip.getBoundingClientRect(), first = li[0].getBoundingClientRect();
  return { rows: li.length, high: Math.round(r.height), rowH: Math.round(first.height), visible: Math.round(r.height / first.height * 10) / 10, scrolls: ul.scrollHeight > ul.clientHeight + 1, overflowY: getComputedStyle(ul).overflowY,
    strip: !!strip, stripBelow: !!s && s.top >= r.bottom - 1, stripAbove: !!s && s.bottom <= r.top + 1, showAll: !!u.querySelector('[data-ucall]'), sideways: document.documentElement.scrollWidth > innerWidth }; })())"""


class Published(unittest.TestCase):
    def measure(self, view, width):
        pub, text = made(view)
        entry = [s for s in pub["sections"] if s["type"] == "usecases"][0]
        with tempfile.TemporaryDirectory() as tmp, chrome() as cdp:
            path = Path(tmp) / "r.html"
            path.write_text(text, encoding="utf-8")
            sid = opened(cdp, path.as_uri())
            cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1000, "deviceScaleFactor": 1, "mobile": False}, sid)
            self.assertTrue(wait(lambda: cdp.js("document.documentElement.dataset.ready", sid) == "1"))
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('[data-uc-section] .ucrows li')", sid)))
            m = json.loads(cdp.js(MEASURE, sid))
        print(f"\nMEASURED width={width} view={view} entry={ {k: entry.get(k) for k in ('n', 'scroll', 'tracker')} } {m}")
        return entry, m

    def test_the_entry_carries_the_view_and_the_file_draws_it(self):
        for width in (1400, 900):
            with self.subTest(width=width):
                entry, m = self.measure(VIEW, width)
                self.assertEqual((entry.get("n"), entry.get("scroll"), entry.get("tracker")), (2, True, "bottom"))
                self.assertEqual(m["rows"], ROWS, "scrolling keeps every row in the list")
                self.assertEqual(m["high"], 2 * m["rowH"], "the list is n rows of the measured row height")
                self.assertEqual(m["visible"], 2.0, "n rows show, no part of a third or a cut second")
                self.assertTrue(m["scrolls"])
                self.assertEqual(m["overflowY"], "auto")
                self.assertFalse(m["showAll"], "a scrolling list has no Show all")
                self.assertTrue(m["stripBelow"], "the count bar is under the rows")
                self.assertFalse(m["stripAbove"])
                self.assertFalse(m["sideways"])

    def test_no_setting_is_the_defaults(self):
        for width in (1400, 900):
            with self.subTest(width=width):
                entry, m = self.measure(None, width)
                self.assertEqual(m["rows"], 5, "five rows then Show all")
                self.assertFalse(m["scrolls"])
                self.assertTrue(m["showAll"])
                self.assertTrue(m["stripAbove"], "the count bar is above the rows")


if __name__ == "__main__":
    unittest.main()
