"""A published file whose data block is gone (the page's status is failed) has exactly one h1, at widths 1400 and 900.

The top bar's name is a heading only once the report is ready (item 1612); the failed page keeps its own single heading.
"""
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from _paths import ROOT  # noqa: F401  (puts src/ on the path)

from clark import publish
from clark.store import open_store
from test_client_hidden_counts import EMPTY_BRANDING, TODAY, fx
from test_server import chrome, wait
from test_work_filters import need_chrome
from test_work_items import page_target

DATA = re.compile(r'<script type="application/json" id="clark-data">.*?</script>', re.S)


class PublishedH1Once(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="clark-h1-"))
        store = open_store(fx.build_db(cls.tmp / "p.db", fx.load()), onedrive_roots=[])
        try:
            html = publish.build(store, "PUB", TODAY, EMPTY_BRANDING, number=1, workbook=True)["body"].decode("utf-8")
        finally:
            store.close()
        cls.whole = cls.tmp / "whole.html"
        cls.whole.write_text(html, encoding="utf-8")
        stripped, n = DATA.subn("", html)
        assert n == 1, "the data block was found once"
        cls.stripped = cls.tmp / "stripped.html"
        cls.stripped.write_text(stripped, encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, True)

    def count(self, path, tab, width):
        with chrome() as cdp:
            sid = page_target(cdp)
            cdp.call("Page.enable", {}, sid)
            cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
            cdp.call("Page.navigate", {"url": path.as_uri() + "#" + tab}, sid)
            self.assertTrue(wait(lambda: cdp.js("document.body.innerText.length > 20", sid)), "the page drew")
            return cdp.js("document.querySelectorAll('h1').length", sid)

    def test_a_file_without_its_data_block_has_exactly_one_h1_at_1400_and_900(self):
        need_chrome()
        for width in (1400, 900):
            for tab in ("dashboard", "gantt"):
                with self.subTest(width=width, tab=tab):
                    self.assertEqual(self.count(self.stripped, tab, width), 1)

    def test_a_whole_file_has_exactly_one_h1_at_1400_and_900(self):
        need_chrome()
        for width in (1400, 900):
            for tab in ("dashboard", "gantt"):
                with self.subTest(width=width, tab=tab):
                    self.assertEqual(self.count(self.whole, tab, width), 1)


if __name__ == "__main__":
    unittest.main()
