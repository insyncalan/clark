"""Cards item 1 (row 1269): the project name above the title is plain, not tracked capitals, on the editor's Milestones and Use cases
pages, as it already is on Work items and on the published tabs.

Run: python3 dev/run_tests.py test_crumb_plain_editor
Headless Chrome (required: fails, never skips, without it). Desktop only: 1400 and 900 px, light and dark.
"""
import tempfile
import unittest

from _demo import DemoStore
from clark import page
from test_published_work_no_add import VARIANTS, open_page
from test_server import Running, chrome, wait
from test_work_filters import need_chrome

CRUMB = """(() => { const c = document.querySelector('%s .crumbs'); if (!c) return null; const s = getComputedStyle(c);
  return [s.textTransform, s.letterSpacing, s.fontWeight, c.textContent]; })()"""
PAGES = (("#milestones", "Milestones"), ("#usecases", "Use cases"))


class CrumbPlain(unittest.TestCase):
    def setUp(self):
        need_chrome()

    def test_the_editor_milestones_and_use_cases_name_line_is_plain(self):
        demo = DemoStore()
        self.addCleanup(demo.close)
        s = Running(data_for=demo.store.data_for, page_html=lambda: page.page_html(tempfile.mkdtemp()))
        self.addCleanup(s.close)
        for sel, name in PAGES:
            for width, scheme in VARIANTS:
                with self.subTest(page=name, width=width, scheme=scheme), chrome() as cdp:
                    sid = open_page(cdp, f"http://127.0.0.1:{s.port}/{sel}&p=ABC", width, scheme)
                    self.assertTrue(wait(lambda: cdp.js(f"!!document.querySelector('{sel} .crumbs')", sid)), name + " drew")
                    got = cdp.js(CRUMB % sel, sid)
                    self.assertEqual(got[0], "none", "the project name is not in capitals")
                    self.assertEqual(got[1], "normal", "no letter spacing")
                    self.assertEqual(got[2], "400", "regular weight")
                    self.assertEqual(got[3], "Example Programme")


if __name__ == "__main__":
    unittest.main()
