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
PEEK_LABELS = ("Description", "Agreed date", "Forecast date", "Workstream", "Client wording")
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
                    cdp.js("location.hash = '#milestones&p=PUB'", sid)
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

    def key(self, cdp, sid, name, vk, code=None):
        for kind in ("keyDown", "keyUp"):
            cdp.call("Input.dispatchKeyEvent", {"type": kind, "key": name, "code": code or name, "windowsVirtualKeyCode": vk, **({"text": " "} if name == " " else {})}, sid)

    def test_a_row_opens_from_the_keyboard_and_esc_closes_it_with_focus_back_on_the_row(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.draw(cdp, width)
                for name, vk, code in (("Enter", 13, "Enter"), (" ", 32, "Space")):
                    cdp.js("document.querySelector('#milestones .msl-row .msl-cells').focus()", sid)
                    self.key(cdp, sid, name, vk, code)
                    self.assertTrue(wait(lambda: cdp.js(f"{PEEK_ID} !== ''", sid)), f"{code} opened the peek")
                    self.key(cdp, sid, "Escape", 27)
                    self.assertTrue(wait(lambda: cdp.js(f"{PEEK_ID} === ''", sid)), f"Esc closed the peek ({code})")
                    self.assertTrue(wait(lambda: cdp.js("document.activeElement === document.querySelector('#milestones .msl-row .msl-cells')", sid)), "focus came back to the row")

    def test_the_clients_peek_shows_only_the_whitelisted_labels(self):
        with chrome() as cdp:
            sid = self.draw(cdp, 1400)
            rows = cdp.js("document.querySelectorAll('#milestones .msl-row').length", sid)
            for i in range(rows):
                cdp.js(f"document.querySelectorAll('#milestones .msl-row .msl-cells')[{i}].click()", sid)
                self.assertTrue(wait(lambda: cdp.js(f"{PEEK_ID} !== ''", sid)), "the peek opened")
                labels = cdp.js("[...document.querySelectorAll('#peek dt')].map(e => e.textContent.trim())", sid)
                self.assertTrue(labels, "the peek lists its fields")
                self.assertEqual([l for l in labels if l not in PEEK_LABELS], [], "only a client's own labels")
                self.assertEqual(cdp.js("document.querySelectorAll('#peek .tag').length && [...document.querySelectorAll('#peek .tag')].map(e => e.textContent).filter(t => /internal/i.test(t)).length", sid), 0)
                cdp.js("location.hash = '#milestones&p=PUB'", sid)
                self.assertTrue(wait(lambda: cdp.js(f"{PEEK_ID} === ''", sid)), "closed")

    def test_a_file_with_many_milestones_remembers_nothing_not_even_the_show_all_choice(self):
        plant = fx.load()
        rows = plant["data"]["milestones"]
        rows.extend({**rows[i % len(rows)], "id": f"ZQ-extra-{i}", "name": f"Extra step {i}"} for i in range(8))
        pub = publish.select(fx.inputs(plant))
        text = publish.render(pub, page.page_html(tp.EMPTY_BRANDING, view=True), plant["as_at"], pub["data"]["project"]["name"])
        folder = Path(tempfile.mkdtemp(prefix="clark-1114-"))
        self.addCleanup(__import__("shutil").rmtree, str(folder), ignore_errors=True)
        (folder / "report.html").write_text(text, encoding="utf-8")
        with chrome() as cdp:
            sid = tp.opened(cdp, (folder / "report.html").as_uri() + "#milestones&p=PUB", 1400)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('[data-msall]')", sid)), "more than five milestones: the Show all button is there")
            cdp.js("localStorage.setItem('clark.msAll.page', 'true')", sid)
            cdp.call("Page.reload", {}, sid)
            self.assertTrue(wait(lambda: cdp.js("document.documentElement.dataset.ready === '1' && !!document.querySelector('[data-msall]')", sid)), "drew again")
            self.assertEqual(cdp.js("document.querySelectorAll('#milestones .msl-row').length", sid), 5, "an editor's stored choice does not reach a file")
            cdp.js("localStorage.removeItem('clark.msAll.page')", sid)
            cdp.js("document.querySelector('[data-msall]').click()", sid)
            self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('#milestones .msl-row').length > 5", sid)), "Show all worked")
            cdp.js("document.querySelector('#milestones [data-msvb=cal]').click()", sid)
            self.assertEqual(cdp.js("Object.keys(window.localStorage).filter(k => k.indexOf('clark.') === 0)", sid), [], "nothing under clark. (msAll, msDet, msv)")

if __name__ == "__main__":
    unittest.main()
