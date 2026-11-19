"""Finding 29, row 1128: the drawn Milestones page of a project whose milestones are all cancelled.

Run: python3 dev/run_tests.py test_ms_cancelled_page
The real server over a real store (fictional data) in headless Chrome (required: it fails, never skips, without Chrome).
Each row's second line says "No longer going ahead" (never "Agreed"), and the head (.head-sub) says "The only milestone is
cancelled." for one cancelled milestone and "All N milestones are cancelled." for several, never "No milestones yet.".
Laptop widths only: 1400 and 900 px.
"""
import tempfile
import unittest
from unittest import mock

from _demo import USER, DemoStore

from clark import page, server as sv
from test_server import Running, chrome, wait
from test_work_items import FIXED_DATE, page_target

EMPTY_BRANDING = tempfile.mkdtemp(prefix="clark-no-brand-")        # so a brand on this laptop never changes a test
SEE = """(() => ({
  subs: [...document.querySelectorAll('.msv .msl-row .msl-sub')].map((e) => e.textContent.trim()),
  rows: document.querySelectorAll('.msv .msl-row').length,
  sub: (() => { const e = document.querySelector('.head-sub'); if (!e) return null; const c = getComputedStyle(e), r = e.getBoundingClientRect(); return {display: c.display, size: c.fontSize, small: (() => { const t = document.createElement('span'); t.style.fontSize = 'var(--size-small)'; document.body.appendChild(t); const v = getComputedStyle(t).fontSize; t.remove(); return v; })(), h: r.height}; })(),
  summary: (document.querySelector('.head-sub') || {textContent: ''}).textContent.trim(),
}))()"""


class Drawn(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.store = self.demo.store
        quiet = mock.patch.object(sv.LOG, "disabled", True)
        quiet.start()
        self.addCleanup(quiet.stop)

    def cancel(self, extra):
        self.demo.update("milestones", self.demo.milestone, {"status": "Cancelled"})
        for i in range(extra):
            with self.store.step("dashboard", USER) as st:
                st.create("milestones", {"project": "ABC", "name": f"Dropped {i}", "baseline_date": f"2030-0{4 + i}-01",
                                         "status": "Cancelled", "source": "demo"})

    def drawn(self, width):
        s = Running(data_for=self.store.data_for, page_html=lambda: page.page_html(EMPTY_BRANDING))
        self.addCleanup(s.close)
        with chrome() as cdp:
            sid = page_target(cdp)
            cdp.call("Page.enable", {}, sid)
            cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE}, sid)
            cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
            cdp.call("Page.navigate", {"url": "about:blank"}, sid)
            cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{s.port}/#milestones&p=ABC"}, sid)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.msv .msl-row')", sid), 10), "the list drew its rows")
            return cdp.js(SEE, sid)

    def drawn_empty(self, width):
        """The page of a project with no milestone at all: no rows to wait for, so wait for the head itself."""
        s = Running(data_for=self.store.data_for, page_html=lambda: page.page_html(EMPTY_BRANDING))
        self.addCleanup(s.close)
        with chrome() as cdp:
            sid = page_target(cdp)
            cdp.call("Page.enable", {}, sid)
            cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE}, sid)
            cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
            cdp.call("Page.navigate", {"url": "about:blank"}, sid)
            cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{s.port}/#milestones&p=ABC"}, sid)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#milestones .head')", sid), 10), "the head drew")
            return cdp.js(SEE, sid)

    def check(self, extra, summary):
        self.cancel(extra)
        for width in (1400, 900):
            seen = self.drawn(width)
            self.assertEqual(seen["rows"], extra + 1, width)
            self.assertEqual(seen["subs"], ["No longer going ahead"] * (extra + 1), width)
            self.assertEqual(seen["summary"], summary, width)
            self.assertNotEqual(seen["sub"]["display"], "none", "the line is shown")
            self.assertGreater(seen["sub"]["h"], 0, "the line takes room")
            self.assertEqual(seen["sub"]["size"], seen["sub"]["small"], "the line is in the small text size")
            for text in seen["subs"] + [seen["summary"]]:
                self.assertNotIn("Agreed", text)
                self.assertNotIn("No milestones yet", text)

    def test_one_cancelled_milestone(self):
        self.check(0, "The only milestone is cancelled.")

    def test_several_cancelled_milestones(self):
        self.check(2, "All 3 milestones are cancelled.")

    def test_no_milestone_at_all_says_no_milestones_yet(self):
        # row 1329: blanking "No milestones yet." in emptyHead leaves the head empty; this fails then
        with self.store.step("dashboard", USER) as st:
            st.archive("milestones", self.demo.milestone)
        for width in (1400, 900):
            seen = self.drawn_empty(width)
            self.assertEqual(seen["rows"], 0, width)
            self.assertEqual(seen["summary"], "No milestones yet.", width)


if __name__ == "__main__":
    unittest.main()
