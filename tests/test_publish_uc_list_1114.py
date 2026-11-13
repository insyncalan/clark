"""Row 1114: the published Use cases tab draws the editor's list read only: tabs with counts (no On the dashboard tab), sort,
Group by with groups that shut, a count line and the filtered-empty state with Clear.

Run: python3 dev/run_tests.py test_publish_uc_list_1114
"""
import copy
import tempfile
import unittest
from pathlib import Path

import _publish_fixture as fx  # noqa: E402
from clark import page, publish  # noqa: E402
from test_publish import EMPTY_BRANDING, chrome, opened, wait  # noqa: E402
import test_server  # noqa: E402,F401  (this file drives Chrome through test_publish: it is in the browser tier)


def made(extra=True):
    plant = fx.load()
    d = plant["data"]
    if extra:
        row = copy.deepcopy(d["use_cases"][0])
        row.update(id="PUB-U-006", title="ZQ-SECOND-USECASE", status="High risk", ref="9.9", sort_order=6)
        d["use_cases"].append(row)
    pub = publish.select(fx.inputs(plant))
    return publish.render(pub, page.page_html(EMPTY_BRANDING, view=True), plant["as_at"], pub["data"]["project"]["name"])


class RealBrowser(unittest.TestCase):
    def go(self, cdp, text, tmp):
        path = Path(tmp) / "r.html"
        path.write_text(text, encoding="utf-8")
        sid = opened(cdp, path.as_uri())
        self.assertTrue(wait(lambda: cdp.js("document.documentElement.dataset.ready", sid) == "1"))
        cdp.js("document.querySelector('[data-view=usecases]').click()", sid)
        self.assertTrue(wait(lambda: cdp.js("document.querySelector('h1').textContent", sid) == "Use cases"))
        return sid

    def test_tabs_sort_group_count_and_empty(self):
        with tempfile.TemporaryDirectory() as tmp, chrome() as cdp:
            sid = self.go(cdp, made(), tmp)
            js = lambda s: cdp.js(s, sid)  # noqa: E731
            self.assertEqual(js("[...document.querySelectorAll('[data-tab]')].map(t => t.dataset.tab).join()"), "all,committed,risk")
            self.assertEqual(js("document.querySelector('[data-tab=all] em').textContent"), "2")
            self.assertEqual(js("document.querySelector('[data-tab=risk] em').textContent"), "1")
            self.assertEqual(js("document.querySelector('#ucp-count').textContent"), "2 use cases")
            self.assertFalse(js("/On the dashboard/i.test(document.body.innerText)"), "no On the dashboard word is drawn in a published file")
            self.assertEqual(js("[...document.querySelectorAll('.ucp .ucref')].pop().textContent"), "UC 9.9")   # Ref order: the planted 9.9 is last,
            self.assertNotEqual(js("document.querySelector('.ucp-title').textContent"), "ZQ-SECOND-USECASE")   # so it is not first yet
            js("document.querySelector('[aria-label^=\"Sort by\"]').click()")
            self.assertTrue(wait(lambda: js("!![...document.querySelectorAll('[role^=menuitem]')].find(e => e.textContent.replace('✓', '').trim() === 'Status')")))
            self.assertEqual(js("[...document.querySelectorAll('[role^=menuitem]')].map(e => e.textContent.replace('✓', '').trim()).join()").split(",")[:2], ["Reference", "Status"])
            js("[...document.querySelectorAll('[role^=menuitem]')].find(e => e.textContent.replace('✓', '').trim() === 'Status').click()")
            self.assertEqual(js("document.querySelector('.ucp-title').textContent"), "ZQ-SECOND-USECASE")  # Status order puts High risk first: the order changed
            js("document.querySelector('[data-tab=risk]').click()")
            self.assertEqual(js("document.querySelectorAll('.ucp').length"), 1)
            self.assertEqual(js("document.querySelector('#ucp-count').textContent"), "1 use case")
            js("document.querySelector('[data-tab=committed]').click()")
            self.assertTrue(wait(lambda: js("!!document.querySelector('[data-empty] [data-clear-all]')")))
            js("document.querySelector('[data-clear-all]').click()")
            self.assertEqual(js("document.querySelectorAll('.ucp').length"), 2)
            self.assertEqual(js("document.querySelector('[data-tab=all]').getAttribute('aria-pressed')"), "true")

    def test_a_published_row_is_the_dashboard_summary_row(self):
        # item 1149: the boxed reference ("UC" once), the title, where it stands, the status word and the shared next steps; no table, no column names
        for width in (1400, 900):
            with self.subTest(width=width), tempfile.TemporaryDirectory() as tmp, chrome() as cdp:
                sid = self.go(cdp, made(), tmp)
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1000, "deviceScaleFactor": 1, "mobile": False}, sid)
                js = lambda s: cdp.js(s, sid)  # noqa: E731
                self.assertEqual(js("[...document.querySelectorAll('.ucp > summary .ucref')].map(e => e.textContent).join()"), "UC 1.1,UC 9.9")
                self.assertEqual(js("document.querySelectorAll('.ucp > summary .ucsteps').length"), 2)
                self.assertTrue(js("/^(No open steps|\\d+ next steps?)$/.test(document.querySelector('.ucp > summary .ucsteps').textContent)"))
                self.assertEqual(js("[...document.querySelectorAll('.ucp > summary')].map(s => (s.innerText.match(/UC/g) || []).length).join()"), "1,1", "UC is said once on a row")
                self.assertEqual(js("getComputedStyle(document.querySelector('.ucp > summary')).display"), "grid")
                cols = js("getComputedStyle(document.querySelector('.ucp > summary')).gridTemplateColumns").split()
                self.assertEqual(cols[-2:], ["124px", "112px" if width == 1400 else "96px"], f"the row's narrow grid wins at {width} px (item 1149)")
                medium = js("(() => { const e = document.createElement('b'); e.style.fontWeight = 'var(--weight-medium)'; document.body.append(e); const w = getComputedStyle(e).fontWeight; e.remove(); return w; })()")
                self.assertEqual(js("getComputedStyle(document.querySelector('.ucp > summary .uctitle')).fontWeight"), medium, "the dashboard's title weight")
                self.assertEqual(js("document.querySelectorAll('.ucp-sorts, .ucp-sort').length"), 0, "the sort is a menu beside Group by")
                self.assertTrue(js("document.documentElement.scrollWidth <= window.innerWidth"))

    def test_group_by_status_and_a_group_shuts(self):
        with tempfile.TemporaryDirectory() as tmp, chrome() as cdp:
            sid = self.go(cdp, made(), tmp)
            js = lambda s: cdp.js(s, sid)  # noqa: E731
            js("document.querySelector('#ucp-group, [aria-label^=\"Group by\"]').click()")
            self.assertTrue(wait(lambda: js("!![...document.querySelectorAll('[role^=menuitem]')].find(e => e.textContent.trim() === 'Status')")))
            self.assertFalse(js("[...document.querySelectorAll('[role^=menuitem]')].some(e => e.textContent.includes('On the dashboard'))"))
            js("[...document.querySelectorAll('[role^=menuitem]')].find(e => e.textContent.trim() === 'Status').click()")
            self.assertTrue(wait(lambda: js("document.querySelectorAll('.ucp-group').length") == 2))
            js("document.querySelector('.ucp-group .grp-b').click()")
            self.assertEqual(js("document.querySelectorAll('.ucp').length"), 1)
            self.assertEqual(js("document.querySelector('.ucp-group .grp-b').getAttribute('aria-expanded')"), "false")

    def test_a_print_shows_every_use_case_with_no_tools(self):
        # The page's own ?print=1 route (item 438) turns the print mode on and draws every tab; the Use cases tab then has no tools.
        with tempfile.TemporaryDirectory() as tmp, chrome() as cdp:
            path = Path(tmp) / "r.html"
            path.write_text(made(), encoding="utf-8")
            tid = next(t["targetId"] for t in cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
            sid = cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
            cdp.call("Page.enable", {}, sid)
            cdp.call("Emulation.setDeviceMetricsOverride", {"width": 1400, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
            cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": "window.__asked = 0; window.print = function () { window.__asked++; };"}, sid)   # no print box in the test
            cdp.call("Page.navigate", {"url": path.as_uri() + "?print=1"}, sid)
            js = lambda s: cdp.js(s, sid)  # noqa: E731
            self.assertTrue(wait(lambda: js("window.__asked") == 1, 20), "the address asked the browser to print once")
            self.assertTrue(js("document.documentElement.classList.contains('print-all')"))
            self.assertTrue(wait(lambda: js("document.querySelectorAll('#usecases-file .ucp').length") == 2))
            self.assertTrue(js("[...document.querySelectorAll('#usecases-file .ucp')].every(d => d.open)"))
            self.assertEqual(js("document.querySelectorAll('#usecases-file .ucp-views, #usecases-file .ucp-sorts, #ucp-count').length"), 0)

    def test_a_file_with_no_use_cases_has_no_use_cases_tab(self):
        plant = fx.load()
        plant["data"]["use_cases"] = []
        pub = publish.select(fx.inputs(plant))
        self.assertFalse(pub["data"].get("use_case_pages"))
        text = publish.render(pub, page.page_html(EMPTY_BRANDING, view=True), plant["as_at"], pub["data"]["project"]["name"])
        with tempfile.TemporaryDirectory() as tmp, chrome() as cdp:
            path = Path(tmp) / "r.html"
            path.write_text(text, encoding="utf-8")
            sid = opened(cdp, path.as_uri())
            self.assertTrue(wait(lambda: cdp.js("document.documentElement.dataset.ready", sid) == "1"))
            self.assertEqual(cdp.js("document.querySelectorAll('[data-view=usecases]').length", sid), 0)
            self.assertEqual(cdp.js("document.querySelectorAll('[data-tab]').length", sid), 0)


if __name__ == "__main__":
    unittest.main()
