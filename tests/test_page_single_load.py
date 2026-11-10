"""One address, one page load (CMD 11-08-133, the macOS CI "Inspected target navigated or closed" blocker).

Run: python3 dev/run_tests.py -j 1 test_page_single_load
Headless Chrome over the real server (tests/_real_server.py). report.js calls reloadFor(start, false) at module start of EVERY load
(#944): an address that names a project in the hash but has no ?project= in the query ("/#dashboard&p=ABC", what a bookmark or the
tests' own pages use) is answered with location.replace("/?project=ABC#..."), so the browser loads the page TWICE. A slow runner's first
poll lands inside that second navigation (CDP -32000 "Inspected target navigated or closed").
Each case counts loads two ways that need no event stream: the server counts its GET / answers, and the page counts its own starts in
sessionStorage (it survives a same-origin navigation of the tab; Page.addScriptToEvaluateOnNewDocument runs on every start).
"""
import json
import time
import unittest
from unittest import mock

from _demo import USER, DemoStore
from _real_server import real_server

from clark import page, server as sv
from test_server import chrome, wait
from test_work_items import page_target

COUNT = "(() => { try { sessionStorage.setItem('loads', String(+(sessionStorage.getItem('loads') || 0) + 1)); } catch (e) {} })();"
SETTLE = 1.5          # seconds the address must stay put before the count is read: a second load starts well inside this


class SingleLoad(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.gets = []

        def counted(code=None):
            self.gets.append(code)
            return page.page_html(None)
        self.s = real_server(self.demo.store.path, self.demo.store.data_for, page_html=counted)
        self.addCleanup(self.s.close)
        quiet = mock.patch.object(sv.LOG, "disabled", True)
        quiet.start()
        self.addCleanup(quiet.stop)

    def load(self, address):
        """(server GET / answers, page starts, final address) for one visit to `address`, after the address has stayed put."""
        with chrome() as cdp:
            sid = page_target(cdp)
            cdp.call("Page.enable", {}, sid)
            cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": COUNT}, sid)
            cdp.call("Page.navigate", {"url": "about:blank"}, sid)
            self.gets.clear()
            cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{self.s.port}{address}"}, sid)
            self.assertTrue(wait(lambda: self._ok(cdp, sid, "document.readyState === 'complete' && !!document.querySelector('#app, #root, body > *')"), 20), "page loaded")
            last, since = None, time.time()
            while time.time() - since < SETTLE:                       # restart the clock whenever the address or the start count moves
                now = self._ok(cdp, sid, "location.href + ' ' + sessionStorage.getItem('loads')")
                if now != last:
                    last, since = now, time.time()
                time.sleep(0.1)
            href, starts = last.rsplit(" ", 1)
            return len(self.gets), int(starts), href

    @staticmethod
    def _ok(cdp, sid, expr):
        try:
            return cdp.js(expr, sid)
        except RuntimeError:                                          # -32000 in the window of a navigation: ask again
            return None

    def test_hash_only_project_loads_once(self):
        gets, starts, href = self.load("/#dashboard&p=ABC")
        print(f"\n[count] '/#dashboard&p=ABC'            server GET / = {gets}  page starts = {starts}  final = {href}  codes asked = {self.gets}")
        self.assertEqual((gets, starts), (1, 1), "an address naming its project in the hash loads the page once, not twice")

    def test_query_and_hash_project_loads_once(self):
        gets, starts, href = self.load("/?project=ABC#dashboard&p=ABC")
        print(f"\n[count] '/?project=ABC#dashboard&p=ABC' server GET / = {gets}  page starts = {starts}  final = {href}")
        self.assertEqual((gets, starts), (1, 1))

    def test_no_project_loads_once(self):
        gets, starts, href = self.load("/#dashboard")
        print(f"\n[count] '/#dashboard'                  server GET / = {gets}  page starts = {starts}  final = {href}")
        self.assertEqual((gets, starts), (1, 1))


if __name__ == "__main__":
    unittest.main()
