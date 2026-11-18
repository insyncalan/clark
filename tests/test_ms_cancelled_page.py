"""Finding 29, row 1128: the drawn Milestones page of a project whose milestones are all cancelled.

Run: python3 dev/run_tests.py test_ms_cancelled_page
The real server over a real store (fictional data) in headless Chrome (required: it fails, never skips, without Chrome).
Each row's second line says "No longer going ahead" (never "Agreed"), and the head (#ms-summary) says "The only milestone is
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
  summary: (document.querySelector('#ms-summary') || {textContent: null}).textContent.trim(),
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

    def check(self, extra, summary):
        self.cancel(extra)
        for width in (1400, 900):
            seen = self.drawn(width)
            self.assertEqual(seen["rows"], extra + 1, width)
            self.assertEqual(seen["subs"], ["No longer going ahead"] * (extra + 1), width)
            self.assertEqual(seen["summary"], summary, width)
            for text in seen["subs"] + [seen["summary"]]:
                self.assertNotIn("Agreed", text)
                self.assertNotIn("No milestones yet", text)

    def test_one_cancelled_milestone(self):
        self.check(0, "The only milestone is cancelled.")

    def test_several_cancelled_milestones(self):
        self.check(2, "All 3 milestones are cancelled.")


if __name__ == "__main__":
    unittest.main()
