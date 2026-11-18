"""#153: the filter line is the app's only. A published file keeps the older filter bar (#69) and holds no filter-line markup;
the app's Work items page has the line.

Run: python3 dev/run_tests.py test_filter_line_not_published
The published page is opened from disk (headless Chrome, no server); the app page is served by the test server.
"""
import copy
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from _paths import ROOT, SRC  # noqa: F401
import _publish_fixture as fx
import _testpage as testpage

from clark import publish
from clark.store import open_store
from test_client_page_filters import EMPTY_BRANDING, TODAY, open_page, plant
from test_server import Running, chrome, wait
from test_work_filters import need_chrome
from test_work_items import FIXED_DATE, load_demo, page_target

# Everything the line draws: its wrapper, the line, the input, the suggestions, the message and the saved-view tabs/menu.
LINE_PARTS = [".fline-wrap", ".fline", "[data-fline]", "#fline-input", "#fline-list", "#fline-msg", ".flist", ".fchip .ft", ".fhi", ".fcount", "#fline-count", "#fline-x", "#clearFilter"]


# Words and keys that only the filter line (the app's) carries; the published file's page must hold none of them (as on main).
LINE_ONLY_WORDS = ["owner:me", "Archived work", "Saved views", "Filter by keyword or by field", "Set your name in Settings",
                   "clark.fline", "clark.fviews", "Filter work items", "Remove the search word",
                   "No work items match.", "Clear filter", "Did you mean", "could mean more than one field", "Add a value after", "Unknown state"]


def count_of(cdp, sid, selector):
    return cdp.js(f"document.querySelectorAll({selector!r}).length", sid)


class NotPublished(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        need_chrome()
        cls.tmp = Path(tempfile.mkdtemp(prefix="clark-flnp-"))
        db = fx.build_db(cls.tmp / "c.db", plant())
        cls.store = open_store(db, onedrive_roots=[])
        out = cls.tmp / "out"
        out.mkdir()
        cls.path = Path(publish.publish(cls.store, "PUB", out, by_user="Demo User", now=TODAY, branding=EMPTY_BRANDING)["path"])

    @classmethod
    def tearDownClass(cls):
        cls.store.close()
        shutil.rmtree(cls.tmp, True)

    def test_the_published_file_draws_the_older_bar_and_no_line(self):
        with chrome() as cdp:
            sid = open_page(cdp, self.path.as_uri() + "#work", 1400, "light")
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#work-list')", sid)), "the Work items tab drew")
            self.assertGreater(count_of(cdp, sid, ".fbar [data-fb]"), 0, "the older filter bar is drawn")
            self.assertEqual(count_of(cdp, sid, "#q"), 1, "the search box is drawn")
            for part in LINE_PARTS:
                self.assertEqual(count_of(cdp, sid, part), 0, f"a published file has no {part}")
            self.assertNotIn("fline", cdp.js("document.getElementById('work').outerHTML", sid), "no filter-line class or id in the page")

    def test_the_app_page_has_the_line_and_not_the_older_bar(self):
        store, folder, _ids = load_demo()
        self.addCleanup(lambda: (store.close(), shutil.rmtree(str(folder), ignore_errors=True)))
        projects = store.read("projects")
        data = {p["code"]: store.data_for(p["code"]) for p in projects}
        s = Running(data_for=lambda code, **kw: copy.deepcopy(data.get(code)), projects=lambda archived=False: projects, page_html=lambda: testpage.html())
        self.addCleanup(s.close)
        with chrome() as cdp:
            sid = page_target(cdp)
            cdp.call("Page.enable", {}, sid)
            cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE}, sid)
            cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{s.port}/#work&p=TUL"}, sid)
            self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('#work tbody tr[data-id]').length", sid) > 0), "the list drew")
            self.assertEqual(count_of(cdp, sid, "#fline-input"), 1, "the app has the line")
            self.assertEqual(count_of(cdp, sid, ".fline-wrap"), 1)
            self.assertEqual(count_of(cdp, sid, ".fbar [data-fb]"), 0, "the app does not draw the older bar")

    def test_peek_next_and_previous_step_through_the_rows_the_published_filters_leave(self):
        # The published Due filter has "Earlier" (a finished item's due day, before the file's day), which the line does not know:
        # the peek must step with the older bar's rows, not the line's.
        def hash_ids(cdp, sid):
            return re.findall(r"PUB-[A-Z]-\d+", cdp.js("location.hash", sid))

        with chrome() as cdp:
            sid = open_page(cdp, self.path.as_uri() + "#work", 1400, "light")
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#work-list')", sid)))
            cdp.js("document.querySelector('[data-show=all]').click()", sid)
            self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('#work-list tr[data-id]').length", sid) > 1))
            everything = cdp.js("document.querySelectorAll('#work-list tr[data-id]').length", sid)
            cdp.js("document.querySelector('[data-fb=due]').click()", sid)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#fbox-due')", sid)))
            self.assertTrue(cdp.js("(() => { const i = [...document.querySelectorAll('#fbox-due input[type=checkbox]')].find(x => x.value === 'past'); if (!i) return false; i.click(); return true; })()", sid), "the published Due filter has Earlier")
            self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('#work-list tr[data-id]').length", sid) < everything))
            want = cdp.js("[...document.querySelectorAll('#work-list tr[data-id]')].map(r => r.dataset.id)", sid)
            self.assertGreaterEqual(len(want), 1)
            cdp.js("document.querySelector('#work-list tr[data-id]').click()", sid)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('[data-pk-next]')", sid)))
            seen = [hash_ids(cdp, sid)[-1]]
            for _ in range(everything):
                if cdp.js("document.querySelector('[data-pk-next]').disabled", sid):
                    break
                cdp.js("document.querySelector('[data-pk-next]').click()", sid)
                self.assertTrue(wait(lambda: hash_ids(cdp, sid)[-1] != seen[-1]))
                seen.append(hash_ids(cdp, sid)[-1])
            self.assertEqual(seen, want, "Next steps through the rows the page draws, no more")
            self.assertTrue(cdp.js("document.querySelector('[data-pk-next]').disabled", sid), "Next stops at the last drawn row")
            for _ in range(len(want) - 1):
                cdp.js("document.querySelector('[data-pk-prev]').click()", sid)
                self.assertTrue(wait(lambda: hash_ids(cdp, sid)[-1] != seen[-1]))
                seen.append(hash_ids(cdp, sid)[-1])
            self.assertEqual(seen[len(want):], want[-2::-1], "Previous steps back through the same rows")
            self.assertTrue(cdp.js("document.querySelector('[data-pk-prev]').disabled", sid), "Previous stops at the first drawn row")

    def test_the_published_page_holds_none_of_the_filter_lines_words(self):
        html = (SRC / "clark" / "page" / "page-view.html").read_text(encoding="utf-8")
        for word in LINE_ONLY_WORDS:
            self.assertEqual(html.count(word), 0, f"page-view.html must not carry {word!r}")
        self.assertNotIn("fline-input", html)

if __name__ == "__main__":
    unittest.main()
