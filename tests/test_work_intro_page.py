"""Prototype parity B-3: the Work items page has a plain project name above the title and one intro line under it.
The editor's line says what Shown to client means; the published file's line does not (it has no such mark).

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

INTRO = "Select an item to open it beside the list."
CRUMB = "(() => { const c = document.querySelector('#work .crumbs'); return [getComputedStyle(c).textTransform, c.textContent]; })()"
TEXT = "(document.querySelector('#work #work-intro') || {}).textContent"


class WorkIntro(unittest.TestCase):
    def setUp(self):
        need_chrome()

    def test_the_published_file_has_the_short_line_and_a_plain_name(self):
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
                self.assertTrue(wait(lambda: cdp.js(f"!!{TEXT}", sid)), "the intro line drew")
                self.assertEqual(cdp.js(TEXT, sid), INTRO)
                self.assertEqual(cdp.js(CRUMB, sid)[0], "none", "the project name is not in capitals")

    def test_the_editor_line_says_what_shown_to_client_means(self):
        demo = DemoStore()
        self.addCleanup(demo.close)
        s = Running(data_for=demo.store.data_for, page_html=lambda: page.page_html(tempfile.mkdtemp()))
        self.addCleanup(s.close)
        for width, scheme in VARIANTS:
            with self.subTest(width=width, scheme=scheme), chrome() as cdp:
                sid = open_page(cdp, f"http://127.0.0.1:{s.port}/#work&p=ABC", width, scheme)
                self.assertTrue(wait(lambda: cdp.js(f"!!{TEXT}", sid)), "the intro line drew")
                self.assertEqual(cdp.js(TEXT, sid), INTRO + " Items marked Shown to client appear on the published page.")
                self.assertEqual(cdp.js(CRUMB, sid)[0], "none")


if __name__ == "__main__":
    unittest.main()
