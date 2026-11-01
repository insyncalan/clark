"""#153: the filter line is the app's only. A published file keeps the older filter bar (#69) and holds no filter-line markup;
the app's Work items page has the line.

Run: python3 dev/run_tests.py test_filter_line_not_published
The published page is opened from disk (headless Chrome, no server); the app page is served by the test server.
"""
import copy
import shutil
import tempfile
import unittest
from pathlib import Path

from _paths import ROOT  # noqa: F401
import _publish_fixture as fx
import _testpage as testpage

from clark import publish
from clark.store import open_store
from test_client_page_filters import EMPTY_BRANDING, TODAY, open_page, plant
from test_server import Running, chrome, wait
from test_work_filters import need_chrome
from test_work_items import FIXED_DATE, load_demo, page_target

# Everything the line draws: its wrapper, the line, the input, the suggestions, the message and the saved-view tabs/menu.
LINE_PARTS = [".fline-wrap", ".fline", "[data-fline]", "#fline-input", "#fline-list", "#fline-msg", ".flist", ".fchip .ft"]


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
        s = Running(data_for=lambda code: copy.deepcopy(data.get(code)), projects=lambda: projects, page_html=lambda: testpage.html())
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


if __name__ == "__main__":
    unittest.main()
