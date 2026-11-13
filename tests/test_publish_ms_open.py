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
PEEK_ID = "((document.querySelector('#peek') || {dataset: {}}).dataset.peek || '')"  # parenthesised: bare, "x || '' === ''" is always true


class PublishedMilestonesOpen(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        plant = fx.load()
        ms = plant["data"]["milestones"]
        extra = dict(ms[0], id="PUB-M-003", name="Third milestone", baseline_date="2026-06-15", forecast_date="2026-06-15")
        ms.insert(1, extra)          # three milestones, so one is neither first nor last
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

    def test_each_opens_its_own_milestone_not_another(self):
        """Every row, mark and chip is clicked in turn (the list's own order is not the data's), so one that is neither first nor last is among them."""
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.draw(cdp, width)
                for kind, sel in (("row", "#milestones .msl-row"), ("mark", "#milestones .mv-mk")):
                    ids = cdp.js(f"[...document.querySelectorAll({sel!r})].map(e => e.dataset.ms)", sid)
                    self.assertGreaterEqual(len(ids), 3, f"{kind}: one is neither first nor last")
                    for one in ids:
                        cdp.js("location.hash = '#milestones&p=PUB'", sid)
                        self.assertTrue(wait(lambda: cdp.js(f"({PEEK_ID}) === ''", sid)), "the peek closed")
                        target = f"{sel}[data-ms=\"{one}\"]" + (" .msl-cells" if kind == "row" else "")
                        cdp.js(f"document.querySelector({target!r}).click()", sid)
                        self.assertTrue(wait(lambda: cdp.js(f"({PEEK_ID}) === {one!r}", sid)), f"the {kind} {one} opened {cdp.js(PEEK_ID, sid)}")
                cdp.js("location.hash = '#milestones&p=PUB'", sid)
                cdp.js("document.querySelector('#milestones [data-msvb=cal]').click()", sid)
                self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('#milestones .cal-ms').length >= 3", sid)), "the Calendar drew the chips")
                chips = cdp.js("[...document.querySelectorAll('#milestones .cal-ms')].map(e => e.dataset.ms)", sid)
                for one in chips:
                    cdp.js("location.hash = '#milestones&p=PUB&mv=cal'", sid)      # the Calendar choice is in the address now, so closing the peek this way stays on the Calendar
                    self.assertTrue(wait(lambda: cdp.js(f"({PEEK_ID}) === ''", sid)), "the peek closed")
                    cdp.js(f"document.querySelector('#milestones .cal-ms[data-ms=\"{one}\"]').click()", sid)
                    self.assertTrue(wait(lambda: cdp.js(f"({PEEK_ID}) === {one!r}", sid)), f"the chip {one} opened {cdp.js(PEEK_ID, sid)}")

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
                self.assertTrue(wait(lambda: cdp.js(f"({PEEK_ID}) === ''", sid)), "the peek closed")
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
