"""Row 1329: the Milestones head of a published file for a project with no milestone says "No milestones yet.".

Run: python3 dev/run_tests.py test_ms_empty_published_1329
A published file is read with fromFile on; a change that draws the head only for the editor (or blanks the words in a file) fails here.
"""
import shutil
import tempfile
import unittest
from pathlib import Path

import test_publish as tp
from test_server import chrome, wait


class EmptyPublished(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
