"""Row 1329 (Classic): the Milestones head of a published file for a project with no milestone says "No milestones yet.".

Run: python3 dev/run_tests.py test_ms_empty_published_1329
A published file is read with fromFile on; a change that draws the head only for the editor (or blanks the words in a file) fails here, and so does a head that still draws the forecast-summary paragraph (#ms-summary) in Classic.
"""
import shutil
import tempfile
import unittest
from pathlib import Path

from unittest import mock

import test_publish as tp
from clark import page
from test_server import chrome, wait


REAL_PAGE_HTML = page.page_html
GONE = "[document.querySelectorAll('#ms-summary').length, document.querySelectorAll('#milestones .head-sub-off').length, document.querySelectorAll('[data-mspage-switch], [data-mspv]').length]"      # Row 1329 AP1, AP2


class EmptyPublished(unittest.TestCase):
    def setUp(self):      # Classic only (ruling 20-11): the published file is drawn with the Classic Theme
        patch = mock.patch.object(page, "page_html", lambda branding=None, view=False, brand_id=None, theme=None: REAL_PAGE_HTML(branding, view, brand_id, "prototype-2.0"))
        patch.start()
        self.addCleanup(patch.stop)

    def test_a_published_file_with_no_milestone_says_no_milestones_yet(self):
        def none(plant):
            plant["data"]["milestones"] = []
        _plant, pub, text = tp.made(none)
        self.assertEqual(pub["data"]["milestones"], [])
        self.assertIn("milestones", pub["tabs"])
        folder = Path(tempfile.mkdtemp(prefix="clark-1329-"))
        self.addCleanup(lambda: shutil.rmtree(str(folder), ignore_errors=True))
        path = folder / "report.html"
        path.write_text(text, encoding="utf-8")
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = tp.opened(cdp, path.as_uri() + "#milestones&p=PUB", width)
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#milestones .head')", sid), 10), "the head drew")
                self.assertEqual(cdp.js("document.querySelector('#milestones .pub') !== null || document.querySelector('section.milestones.pub') !== null", sid), True, "drawn as a published file")
                self.assertEqual(cdp.js("(document.querySelector('#milestones .head-sub') || {textContent: ''}).textContent.trim()", sid), "No milestones yet.")
                self.assertEqual(cdp.js("document.querySelectorAll('#milestones .msl-row').length", sid), 0)
                self.assertEqual(cdp.js(GONE, sid), [0, 0, 0], "Classic draws no forecast-summary paragraph (#ms-summary), no head-sub-off, no Plan | Movement switch")

    def test_a_published_file_whose_only_milestone_is_cancelled_says_no_milestones_yet(self):
        # row 1329: a file drops cancelled rows for the client, so the head reads them as none; the rows read without the client flag would say "The only milestone is cancelled."
        def cancelled(plant):
            rows = plant["data"]["milestones"]
            del rows[1:]
            rows[0]["status"] = "Cancelled"
        _plant, pub, text = tp.made(cancelled)
        self.assertEqual([m["status"] for m in pub["data"]["milestones"]], ["Cancelled"])
        folder = Path(tempfile.mkdtemp(prefix="clark-1329-"))
        self.addCleanup(lambda: shutil.rmtree(str(folder), ignore_errors=True))
        path = folder / "report.html"
        path.write_text(text, encoding="utf-8")
        with chrome() as cdp:
            sid = tp.opened(cdp, path.as_uri() + "#milestones&p=PUB", 1400)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#milestones .head')", sid), 10), "the head drew")
            self.assertEqual(cdp.js("(document.querySelector('#milestones .head-sub') || {textContent: ''}).textContent.trim()", sid), "No milestones yet.")
            self.assertEqual(cdp.js("document.querySelectorAll('#milestones .msl-row').length", sid), 0)
            self.assertEqual(cdp.js(GONE, sid), [0, 0, 0], "Classic draws no forecast-summary paragraph (#ms-summary), no head-sub-off, no Plan | Movement switch")


if __name__ == "__main__":
    unittest.main()
