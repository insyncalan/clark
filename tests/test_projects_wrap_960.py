"""Item 1162 (pin for item 842): the Projects table's Open, Edit, Archive buttons may wrap onto a second line at 960 px and narrower,
so the page never scrolls sideways when the Settings links are a list down the left at 900 px.

Run: python3 dev/run_tests.py test_projects_wrap_960
Part 1 reads the CSS source for the 960 px rule (the widths a real browser may be sized to here are 1400 and 900 only, so 960 itself is pinned
by its source text, and the behaviour either side of it is measured at 1400 and 900). Part 2 loads the committed page from the real server at
1400 and 900: the buttons' cell stays on one line at 1400, may wrap at 900, and the page has no sideways scroll at 900. Chrome is required:
the browser part fails, never skips, without it.
"""
import re
import tempfile
import unittest

from _editor_checks import for_url
from _paths import SRC

from clark import page
from test_server import Running, chrome, wait
from test_work_items import FIXED_DATE, page_target

CSS = SRC / "clark" / "page" / "src" / "edit" / "edit.css"
NAMES = {"FAB": "Fabrikam Customer Portal Rebuild Programme", "FAC": "Fabrikam Warehouse Rollout Phase Two Delivery"}
CELL = "document.querySelector('#projects-table td.acts')"


class Source(unittest.TestCase):
    def test_C_the_960_rule_lets_the_buttons_wrap(self):
        text = CSS.read_text(encoding="utf-8")
        m = re.search(r"@media \(max-width: 960px\) \{([^@]*)\}\s*\n", text)
        self.assertTrue(m, "edit.css holds a max-width 960px rule for the Projects buttons")
        body = m.group(1)
        self.assertRegex(body, r"\.projects table\.proj-table td\.acts \{ white-space: normal; \}")
        self.assertRegex(body, r"\.projects table\.proj-table td\.acts \.btn \{ margin: 2px 0 2px 8px; \}")
        self.assertRegex(text, r"\.projects table\.proj-table td\.acts \{ text-align: right; white-space: nowrap; \}", "above 960 px the buttons stay on one line")


class Browser(unittest.TestCase):
    def test_C_buttons_stay_in_a_line_at_1400_and_may_wrap_without_sideways_scroll_at_900(self):
        data = {c: {"project": {"code": c, "name": n, "client_name": "Fabrikam"}, "workstreams": [], "items": []} for c, n in NAMES.items()}
        s = Running(data_for=lambda code, **kw: data.get(code), projects=lambda archived=False: [] if archived else [{"code": c, "name": n} for c, n in NAMES.items()],
                    page_html=lambda: page.page_html(tempfile.mkdtemp()))
        self.addCleanup(s.close)
        with chrome() as cdp:
            sid = page_target(cdp)
            cdp.call("Page.enable", {}, sid)
            cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE}, sid)
            for width, white in ((1400, "nowrap"), (900, "normal")):
                with self.subTest(width=width):
                    cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
                    cdp.call("Page.navigate", {"url": "about:blank"}, sid)
                    cdp.call("Page.navigate", {"url": for_url(f"http://127.0.0.1:{s.httpd.server_port}/#settings&p=FAB")}, sid)
                    self.assertTrue(wait(lambda: bool(cdp.js(f"!!{CELL}", sid)), 30), "the projects table drew")
                    self.assertEqual(cdp.js(f"getComputedStyle({CELL}).whiteSpace", sid), white)
                    if width == 900:
                        self.assertLessEqual(cdp.js("document.documentElement.scrollWidth - window.innerWidth", sid), 0, "no sideways scroll at 900")
                        self.assertEqual(cdp.js(f"getComputedStyle({CELL}.querySelector('.btn')).marginTop", sid), "2px")
                    else:
                        self.assertEqual(cdp.js(f"{CELL}.getClientRects().length && new Set([...{CELL}.querySelectorAll('.btn')].map(b => Math.round(b.getBoundingClientRect().top))).size", sid), 1,
                                         "one line of buttons at 1400")


if __name__ == "__main__":
    unittest.main()
