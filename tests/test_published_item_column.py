"""Row 784: the published Work items tab keeps a readable Item column at 900 px (and 1400), light and dark, with no sideways page scroll.

Run: python3 dev/run_tests.py test_published_item_column
Headless Chrome (required). The published file is opened from disk.
"""
import shutil
import tempfile
import unittest
from pathlib import Path

from _demo import USER, DemoStore
from clark import publish
from test_server import chrome, wait
from test_work_filters import need_chrome
from test_published_work_no_add import open_page, EMPTY_BRANDING, VARIANTS

TODAY = "2026-10-28"
TITLES = ["Agree the data cut-over plan with the finance team before the pilot starts",
          "Confirm the supplier invoice format and the matching tolerance with each region"]
MIN_ITEM = 280      # prototype 290 px, build about 281 (main was about 257)


class PublishedItemColumn(unittest.TestCase):
    def setUp(self):
        need_chrome()

    def test_the_item_column_is_wide_enough_and_the_table_fits(self):
        demo = DemoStore()
        folder = tempfile.mkdtemp(prefix="clark-pub-")
        self.addCleanup(demo.close)
        self.addCleanup(shutil.rmtree, folder, True)
        for i, title in enumerate(TITLES):
            demo.action(description=title, owner="Example Owner", due_date="2026-11-%02d" % (10 + i), status="Open", priority="High")
        path = Path(publish.publish(demo.store, "ABC", folder, by_user=USER, now=TODAY, branding=EMPTY_BRANDING)["path"])
        for width, scheme in VARIANTS:
            with self.subTest(width=width, scheme=scheme), chrome() as cdp:
                sid = open_page(cdp, path.as_uri(), width, scheme)
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.tab')", sid)))
                cdp.js("[...document.querySelectorAll('.tab')].find(t => /Work items/.test(t.textContent)).click()", sid)
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#work table.items td.c-item')", sid)))
                item = cdp.js("document.querySelector('#work table.items td.c-item').getBoundingClientRect().width", sid)
                self.assertGreaterEqual(item, MIN_ITEM, "the Item column is readable")
                over = cdp.js("(() => { const t = document.querySelector('#work table.items').getBoundingClientRect(), f = document.querySelector('#work').getBoundingClientRect(); return t.right - f.right; })()", sid)
                self.assertLessEqual(over, 1, "the table fits its section")
                self.assertLessEqual(cdp.js("document.documentElement.scrollWidth - document.documentElement.clientWidth", sid), 0, "no sideways page scroll")


if __name__ == "__main__":
    unittest.main()
