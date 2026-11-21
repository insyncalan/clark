"""Row 1082: 'Show history' under the peek's Latest update (Edit's own peek; read only, from the Activity read).
Run: python3 dev/run_tests.py test_peek_history_1082

Part 1 is the source and the built pages: the link, its two words, the component, and that no published file carries any of it.
Part 2 is the page in a real browser at 1400 and 900 px, light and dark: seven stored changes of the Latest update, five in view, the rest
by scrolling, the link reading Hide history while open, only that one field's changes, the list inside the peek, and text drawn as text.
"""
import json
import shutil
import unittest

from _editor_checks import for_url
from _paths import ROOT
import _testpage as testpage

from clark import activity_read, changes, sneak  # noqa: E402
from test_server import Running, chrome, wait  # noqa: E402
from test_work_items import FIXED_DATE, load_demo, page_target  # noqa: E402

SRC = ROOT / "src" / "clark" / "page" / "src"
ITEM = "TUL-A-002"
BTN, LIST, ROWS = "[data-pk-lh-btn]", "[data-pk-lh-list]", "[data-pk-lh-row]"


class Source(unittest.TestCase):
    def test_the_link_has_the_issues_two_words_and_reads_only(self):
        jsx = (SRC / "edit" / "PeekLatestHistory.jsx").read_text(encoding="utf-8")
        self.assertIn('"Hide history" : "Show history"', jsx)
        self.assertIn("readActivity(", jsx)
        self.assertNotIn("changeCell", jsx)
        self.assertNotIn("undoSeveral", jsx)
        self.assertIn("PeekLatestHistory", (SRC / "edit" / "PeekLatest.jsx").read_text(encoding="utf-8"))

    def test_no_published_file_carries_it(self):
        for name in ("page-view.html",):
            built = (ROOT / "src" / "clark" / "page" / name)
            if built.exists():
                self.assertNotIn("data-pk-lh", built.read_text(encoding="utf-8"), name)


class Browser(unittest.TestCase):
    def load(self, cdp, width, dark=False):
        self.store, folder, ids = load_demo()
        self.code = next(iter(ids))
        self.addCleanup(lambda: (self.store.close(), shutil.rmtree(str(folder), ignore_errors=True)))
        change = changes.make_change(self.store.path, [], "Demo User")
        for n in range(1, 8):
            self.assertEqual(change({"project": self.code, "kind": "actions", "op": "update", "id": ITEM, "changes": {"latest_update": f"Version {n} <b>x</b>"}, "place": "peek"})[0], 200)
        change({"project": self.code, "kind": "actions", "op": "update", "id": ITEM, "changes": {"owner": "Someone Else"}, "place": "peek"})
        projects = self.store.read("projects")
        s = Running(data_for=self.store.data_for, projects=lambda archived=False: projects, page_html=lambda: testpage.html(),
                    sneak=sneak.make_read(self.store.data_for), change=change, undo=changes.make_undo(self.store.path, [], "Demo User"))
        s.httpd.activity = activity_read.make_read(self.store.path, self.store.data_for)      # the seam the Activity route reads
        self.addCleanup(s.close)
        sid = page_target(cdp)
        cdp.call("Page.enable", {}, sid)
        cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE}, sid)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
        cdp.call("Emulation.setFocusEmulationEnabled", {"enabled": True}, sid)
        cdp.call("Page.navigate", {"url": for_url(f"http://127.0.0.1:{s.port}/#work&p={self.code}")}, sid)
        self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('#work tbody tr[data-id]').length", sid) > 0))
        if dark:
            cdp.js("document.documentElement.dataset.theme = 'dark'", sid)
        cdp.js(f"clarkPage.openPeek({json.dumps(ITEM)})", sid)
        self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#peek [data-pk-lh-btn]')", sid)))
        return sid

    def press(self, cdp, sid):
        cdp.js(f"document.querySelector({json.dumps(BTN)}).click()", sid)       # the button's own click: a mouse press can land while the peek is still sliding in

    def test_five_in_view_the_rest_scroll_and_the_link_toggles(self):
        for width in (1400, 900):
            for dark in (False, True):
                with self.subTest(width=width, dark=dark), chrome() as cdp:
                    sid = self.load(cdp, width, dark)
                    self.assertEqual(cdp.js(f"document.querySelector({json.dumps(BTN)}).textContent", sid), "Show history")
                    self.assertFalse(cdp.js(f"!!document.querySelector({json.dumps(LIST)})", sid))
                    self.press(cdp, sid)
                    self.assertTrue(wait(lambda: cdp.js(f"document.querySelectorAll({json.dumps(ROWS)}).length", sid) == 7), "only the Latest update's seven changes, not the owner change")
                    self.assertEqual(cdp.js(f"document.querySelector({json.dumps(BTN)}).textContent", sid), "Hide history")
                    self.assertEqual(cdp.js(f"document.querySelector({json.dumps(BTN)}).getAttribute('aria-expanded')", sid), "true")
                    # five rows' height in view; more is behind the scroll
                    seen = cdp.js(f"(l => [l.clientHeight, l.scrollHeight, getComputedStyle(l).overflowY, [...l.querySelectorAll({json.dumps(ROWS)})].filter(r => r.getBoundingClientRect().bottom <= l.getBoundingClientRect().bottom + 1).length])(document.querySelector({json.dumps(LIST)}))", sid)
                    self.assertGreater(seen[1], seen[0])
                    self.assertEqual(seen[2], "auto")
                    self.assertEqual(seen[3], 5)
                    first = cdp.js(f"document.querySelector({json.dumps(ROWS)}).textContent", sid)
                    self.assertIn("Version 7", first, "newest first")
                    self.assertIn("<b>x</b>", first, "drawn as text, never as markup")
                    self.assertTrue(cdp.js("(c => { const r = c.getBoundingClientRect(), p = document.querySelector('#peek').getBoundingClientRect(); return r.left >= p.left - 1 && r.right <= p.right + 1; })(document.querySelector('[data-pk-lh-panel]'))", sid))
                    self.assertEqual(cdp.js(f"(l => (l.scrollTop = l.scrollHeight, l.scrollTop > 0))(document.querySelector({json.dumps(LIST)}))", sid), True)
                    self.press(cdp, sid)
                    self.assertTrue(wait(lambda: not cdp.js("!!document.querySelector('[data-pk-lh-panel]')", sid)))
                    self.assertEqual(cdp.js(f"document.querySelector({json.dumps(BTN)}).textContent", sid), "Show history")
                    self.assertEqual(cdp.js(f"document.querySelector({json.dumps(BTN)}).getAttribute('aria-expanded')", sid), "false")

    def stub(self, cdp, sid, answer):
        cdp.js("(a => { const f = window.fetch; window.fetch = (u, o) => String(u).includes('/api/activity') ? a() : f(u, o); })(" + answer + ")", sid)

    def test_empty_failed_and_only_real_changes(self):
        rows = '[{field:"Latest update",kind:"Created",to:"c",when_text:"x"},{field:"Latest update",kind:"Comment",to:"k",when_text:"x"},{field:"Owner",kind:"Changed",to:"o",when_text:"x"}]'
        cases = (("[data-pk-lh-empty]", "Nothing has changed on this item yet.", "() => Promise.resolve(new Response(JSON.stringify({ok:true,activity:{rows:" + rows + "}})))"),
                 ("[data-pk-lh-failed]", "The history could not be read just now.", "() => Promise.reject(new Error('down'))"))
        for sel, words, answer in cases:
            with self.subTest(sel=sel), chrome() as cdp:
                sid = self.load(cdp, 1400)
                self.stub(cdp, sid, answer)
                self.press(cdp, sid)
                self.assertTrue(wait(lambda: cdp.js(f"!!document.querySelector({json.dumps(sel)})", sid)))
                self.assertEqual(cdp.js(f"document.querySelector({json.dumps(sel)}).textContent", sid), words)
                self.assertEqual(cdp.js(f"document.querySelectorAll({json.dumps(ROWS)}).length", sid), 0)


if __name__ == "__main__":
    unittest.main()
