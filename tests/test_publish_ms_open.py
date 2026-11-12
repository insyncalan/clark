"""Row 1114 (first slice): on a published file's Milestones page a mark, a label, a calendar chip and a list row open the file's
read only peek (they were plain text). The page holds no editing control, and the Show details toggle stays the editor's only.

Run: python3 dev/run_tests.py test_publish_ms_open   (headless Chrome; fails, never skips, without it)
"""
import tempfile
import unittest
from pathlib import Path

import _publish_fixture as fx

from clark import page, publish
from test_server import chrome, wait
import test_publish as tp

CONTROLS = "button, input, textarea, select, [role=textbox], [role=combobox]"
PEEK_ID = "((document.querySelector('#peek') || {dataset: {}}).dataset.peek || '')"


class PublishedMilestonesOpen(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        plant = fx.load()
        pub = publish.select(fx.inputs(plant))
        text = publish.render(pub, page.page_html(tp.EMPTY_BRANDING, view=True), plant["as_at"], pub["data"]["project"]["name"])
        cls.folder = Path(tempfile.mkdtemp(prefix="clark-1114-"))
        cls.path = cls.folder / "report.html"
        cls.path.write_text(text, encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        __import__("shutil").rmtree(str(cls.folder), ignore_errors=True)

    def draw(self, cdp, width):
        sid = tp.opened(cdp, self.path.as_uri() + "#milestones&p=PUB", width)
        self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#milestones .msl-row')", sid)), "the Milestones page drew")
        return sid

    def test_a_row_a_mark_and_a_chip_open_the_read_only_peek(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.draw(cdp, width)
                self.assertEqual(cdp.js("document.querySelectorAll('#milestones .msl-row.plain, #milestones .mv-mk.plain, #milestones .mv-lab.plain').length", sid), 0, "nothing is plain text now")
                self.assertEqual(cdp.js("document.querySelectorAll('#milestones [data-msdet]').length", sid), 0, "a file keeps no Hide details toggle")
                cdp.js("document.querySelector('#milestones .msl-row .msl-cells').click()", sid)
                self.assertTrue(wait(lambda: cdp.js(f"{PEEK_ID} !== ''", sid)), "the row opened the peek")
                self.assertEqual(cdp.js(f"[...document.querySelectorAll('#peek .pk-body').length ? document.querySelectorAll('#peek .pk-body') : []].reduce((n, b) => n + b.querySelectorAll({CONTROLS!r}).length, 0)", sid), 0, "read only")
                cdp.js("location.hash = '#milestones&p=PUB'", sid)
                self.assertTrue(wait(lambda: cdp.js(f"{PEEK_ID} === ''", sid)), "the peek closed")
                cdp.js("document.querySelector('#milestones .mv-mk').click()", sid)
                self.assertTrue(wait(lambda: cdp.js(f"{PEEK_ID} !== ''", sid)), "a mark on the timeline opened the peek")
                cdp.js("location.hash = '#milestones&p=PUB'", sid)
                cdp.js("document.querySelector('#milestones [data-msvb=cal]').click()", sid)
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#milestones .cal-ms')", sid)), "the Calendar drew")
                self.assertEqual(cdp.js("document.querySelector('#milestones .cal-ms').tagName", sid), "BUTTON")
                cdp.js("document.querySelector('#milestones .cal-ms').click()", sid)
                self.assertTrue(wait(lambda: cdp.js(f"{PEEK_ID} !== ''", sid)), "a chip opened the peek")


if __name__ == "__main__":
    unittest.main()
