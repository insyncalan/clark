"""Prototype parity B-3 and row 805: the Work items page has a plain project name above the title and no intro line under it
(row 805 took the sentence away, in the editor and in the published file).

Run: python3 dev/run_tests.py test_work_intro_page
Headless Chrome (required: fails, never skips, without it). Desktop only: 1400 and 900 px, light and dark.
"""
import shutil
import tempfile
import unittest
from pathlib import Path

from _demo import USER, DemoStore
from clark import page, publish
from test_published_work_no_add import EMPTY_BRANDING, TODAY, VARIANTS, open_page
from test_server import Running, chrome, wait
from test_work_filters import need_chrome

CRUMB = "(() => { const c = document.querySelector('#work .crumbs'); return [getComputedStyle(c).textTransform, c.textContent]; })()"
H1 = "document.querySelector('#work h1')"
NOTE = "!!document.querySelector('#work #work-intro') || /Select an item to open it/.test(document.querySelector('#work').textContent)"


class WorkIntro(unittest.TestCase):
    def setUp(self):
        need_chrome()

    def test_the_published_file_has_no_intro_line_and_a_plain_name(self):
        demo = DemoStore()
        folder = tempfile.mkdtemp(prefix="clark-pub-")
        self.addCleanup(demo.close)
        self.addCleanup(shutil.rmtree, folder, True)
        path = Path(publish.publish(demo.store, "ABC", folder, by_user=USER, now=TODAY, branding=EMPTY_BRANDING)["path"])
        for width, scheme in VARIANTS:
            with self.subTest(width=width, scheme=scheme), chrome() as cdp:
                sid = open_page(cdp, path.as_uri(), width, scheme)
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.tab')", sid)))
                cdp.js("[...document.querySelectorAll('.tab')].find(t => /Work items/.test(t.textContent)).click()", sid)
                self.assertTrue(wait(lambda: cdp.js(f"!!{H1}", sid)), "the Work items page drew")
                self.assertFalse(cdp.js(NOTE, sid), "no intro line")
                self.assertEqual(cdp.js(CRUMB, sid)[0], "none", "the project name is not in capitals")

    def test_the_editor_has_no_intro_line_either(self):
        demo = DemoStore()
        self.addCleanup(demo.close)
        s = Running(data_for=demo.store.data_for, page_html=lambda: page.page_html(tempfile.mkdtemp()))
        self.addCleanup(s.close)
        for width, scheme in VARIANTS:
            with self.subTest(width=width, scheme=scheme), chrome() as cdp:
                sid = open_page(cdp, f"http://127.0.0.1:{s.port}/#work&p=ABC", width, scheme)
                self.assertTrue(wait(lambda: cdp.js(f"!!{H1}", sid)), "the Work items page drew")
                self.assertFalse(cdp.js(NOTE, sid), "no intro line")
                self.assertEqual(cdp.js(CRUMB, sid)[0], "none")


if __name__ == "__main__":
    unittest.main()
