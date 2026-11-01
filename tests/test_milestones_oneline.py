"""C-M10: a milestone list row's second line ("Expected a date · N days later") reads on one line at 1400 px.
C-M11 (#436 row 24): at 900 px the row keeps its columns (date, name, state, progress side by side, as the prototype's grid does,
system/prototype/app.css:849); it stacks in two columns only at 800 px and below (app.css:875).

Run: python3 dev/run_tests.py test_milestones_oneline
The browser parts load the committed page from the real server on the demo database (fixed CLARK_NOW), plus one milestone with a
very long name and a slip of hundreds of days, in light and in dark. At 1400 px each date cell's second line is a single row of
text and every cell sits inside its row; the long name wraps in its own cell. At 1400 and 900 px nothing runs past the card or
scrolls sideways. Part 3 is the published file: the same one-line check, in the client's words. The browser parts are required.
"""
import shutil
import tempfile
import unittest
from pathlib import Path

from _demo import USER, DemoStore
from _paths import SRC

from clark import page, publish
from test_server import chrome, wait, Running
from test_work_items import FIXED_DATE, load_demo, page_target

TODAY = "2026-10-28"
EMPTY_BRANDING = tempfile.mkdtemp(prefix="clark-no-brand-")
LONG_NAME = "Handover of the whole regional programme to the operating team after acceptance " + "Supercalifragilisticexpialidocious" * 2
SLIPPED = {"name": LONG_NAME, "baseline_date": "2026-11-12", "forecast_date": "2028-12-31", "client_visible": 1, "source": "demo"}

# For each list row: the lines the second line of the date cell takes, whether each cell stays inside the row, and what runs past the card.
MEASURE = r"""(() => {
  const lines = (el) => { const r = document.createRange(); r.selectNodeContents(el);
    return new Set([...r.getClientRects()].filter((q) => q.width > 0).map((q) => Math.round(q.top))).size; };
  const card = document.querySelector('.msl-box').closest('.card, .box, section, .ms-block') || document.querySelector('.msl-box').parentElement;
  const cb = card.getBoundingClientRect();
  const rows = [...document.querySelectorAll('.msl-row')].map((row) => {
    const rb = row.getBoundingClientRect(), small = row.querySelector('.msl-date small'), name = row.querySelector('.msl-name');
    const cells = [...row.querySelectorAll('.msl-cells > *')].map((c) => c.getBoundingClientRect());
    const sb = small.getBoundingClientRect(), db = row.querySelector('.msl-date').getBoundingClientRect(), nb = name.getBoundingClientRect();
    const texts = [...row.querySelectorAll('.msl-cells > *')];
    return {text: small.textContent, lines: lines(small), nameLines: lines(name),
            inRow: cells.every((c) => c.left >= rb.left - 1 && c.right <= rb.right + 1),
            smallInDate: sb.right <= db.right + 1, dateClearOfName: db.right <= nb.left + 1,
            cellsClip: texts.some((t) => t.scrollWidth > t.clientWidth + 1),
            cols: getComputedStyle(row.querySelector('.msl-cells')).gridTemplateColumns.split(' ').length,
            across: cells.every((c, i) => i === 0 || c.left > cells[i - 1].left),
            inCard: rb.left >= cb.left - 1 && rb.right <= cb.right + 1};
  });
  const de = document.documentElement;
  return {rows, pageScroll: de.scrollWidth > window.innerWidth, cardScroll: card.scrollWidth > card.clientWidth + 1,
          listScroll: document.querySelector('.msl-box').scrollWidth > document.querySelector('.msl-box').clientWidth + 1};
})()"""


def show_all(cdp, sid):
    if cdp.js("!!document.querySelector('.msl-all')", sid) and cdp.js("document.querySelector('.msl-all').textContent", sid).startswith("Show all"):
        cdp.js("document.querySelector('.msl-all').click()", sid)
        wait(lambda: cdp.js("document.querySelectorAll('.msl-row').length", sid) > 5)


class Rows(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store, cls.folder, _ = load_demo()
        with cls.store.step("dashboard", USER) as step:
            step.create("milestones", dict(SLIPPED, project="TUL"))
        cls.projects = cls.store.read("projects")

    @classmethod
    def tearDownClass(cls):
        cls.store.close()
        shutil.rmtree(str(cls.folder), ignore_errors=True)

    def open_page(self, cdp, port, width, scheme, code):
        sid = page_target(cdp)
        cdp.call("Page.enable", {}, sid)
        cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme}]}, sid)
        cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE}, sid)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
        cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{port}/#milestones&p={code}"}, sid)
        self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.msl-row')", sid)), "the list drew")
        show_all(cdp, sid)
        return sid

    def test_the_second_line_is_one_line_at_1400_and_nothing_overflows_at_1400_and_900(self):
        s = Running(data_for=self.store.data_for, projects=lambda: self.projects, page_html=lambda: page.page_html(tempfile.mkdtemp()))
        self.addCleanup(s.close)
        for code in ("TUL", "MOSS"):
            for scheme in ("light", "dark"):
                for width in (1400, 900):
                    with self.subTest(code=code, scheme=scheme, width=width), chrome() as cdp:
                        sid = self.open_page(cdp, s.port, width, scheme, code)
                        got = cdp.js(MEASURE, sid)
                        where = f"{code} {scheme} {width}px"
                        self.assertGreaterEqual(len(got["rows"]), 5, where)
                        slipped = [r for r in got["rows"] if " · " in r["text"]]
                        self.assertTrue(slipped, f"{where}: the demo has a slipped milestone on this list")
                        for r in slipped:
                            self.assertRegex(r["text"], r"^Expected \d\d-\d\d-\d{4} · \d+ days? later$", where)
                        self.assertFalse(got["pageScroll"], f"{where}: no sideways scroll on the page")
                        self.assertFalse(got["cardScroll"] or got["listScroll"], f"{where}: nothing scrolls inside the card")
                        for r in got["rows"]:
                            self.assertEqual((r["cols"], r["across"]), (4, True), f"{where}: the columns stay side by side ({r['text']})")
                            self.assertTrue(r["inCard"], f"{where}: the row stays inside the card ({r['text']})")
                            self.assertTrue(r["inRow"], f"{where}: every cell stays inside its row ({r['text']})")
                            self.assertTrue(r["dateClearOfName"], f"{where}: the date cell does not run into the name ({r['text']})")
                            if width == 1400:
                                self.assertEqual(r["lines"], 1, f"{where}: the second line is one line ({r['text']})")
                                self.assertTrue(r["smallInDate"], f"{where}: the second line stays inside its cell ({r['text']})")
                                self.assertFalse(r["cellsClip"], f"{where}: no cell cuts text off ({r['text']})")
                        if code == "TUL":
                            long = [r for r in got["rows"] if r["nameLines"] > 1]
                            self.assertTrue(long, f"{where}: the very long name wraps in its own cell")

    def test_the_cells_stack_in_two_columns_only_at_800_px_and_below(self):
        s = Running(data_for=self.store.data_for, projects=lambda: self.projects, page_html=lambda: page.page_html(tempfile.mkdtemp()))
        self.addCleanup(s.close)
        for width, cols in ((901, 4), (900, 4), (801, 4), (800, 2), (700, 2)):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.open_page(cdp, s.port, width, "light", "TUL")
                got = cdp.js(MEASURE, sid)
                self.assertTrue(got["rows"])
                self.assertEqual({r["cols"] for r in got["rows"]}, {cols}, f"{width}px")
                self.assertFalse(got["pageScroll"] or got["cardScroll"] or got["listScroll"], f"{width}px: nothing scrolls sideways")

    def test_the_stylesheet_stacks_the_cells_only_below_801_px(self):
        css = (SRC / "clark" / "page" / "shell.css").read_text(encoding="utf-8")
        import re
        for m in re.finditer(r"@media \(max-width: (\d+)px\)\s*\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}", css):
            if ".msl-cells" in m.group(2) and "grid-template-columns" in m.group(2):
                self.assertEqual(m.group(1), "800", "the rule that stacks the list cells is the 800 px one, not 900")

    def test_the_words_are_the_products_with_the_middle_dot(self):
        s = Running(data_for=self.store.data_for, projects=lambda: self.projects, page_html=lambda: page.page_html(tempfile.mkdtemp()))
        self.addCleanup(s.close)
        with chrome() as cdp:
            sid = self.open_page(cdp, s.port, 1400, "light", "TUL")
            texts = cdp.js("[...document.querySelectorAll('.msl-date small')].map((e) => e.textContent)", sid)
            self.assertIn("Expected 31-12-2028 · 780 days later", texts)
            for t in texts:
                self.assertTrue(t in ("Agreed", "No agreed date", "Forecast, not agreed") or t.startswith(("Expected ", "Achieved")), t)


class Published(unittest.TestCase):
    def test_the_published_file_reads_the_second_line_on_one_line_at_1400_and_fits_at_900(self):
        demo = DemoStore()
        with demo.store.step("dashboard", USER) as step:
            step.create("milestones", dict(SLIPPED, project="ABC"))
        folder = tempfile.mkdtemp(prefix="clark-pub-")
        self.addCleanup(demo.close)
        self.addCleanup(shutil.rmtree, folder, True)
        path = Path(publish.publish(demo.store, "ABC", folder, by_user=USER, now=TODAY, branding=EMPTY_BRANDING)["path"])
        for scheme in ("light", "dark"):
            for width in (1400, 900):
                with self.subTest(scheme=scheme, width=width), chrome() as cdp:
                    sid = page_target(cdp)
                    cdp.call("Page.enable", {}, sid)
                    cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme}]}, sid)
                    cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE}, sid)
                    cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
                    cdp.call("Page.navigate", {"url": path.as_uri()}, sid)
                    self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.tab')", sid)))
                    cdp.js("[...document.querySelectorAll('.tab')].find(t => /Milestones/.test(t.textContent)).click()", sid)
                    self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.msl-row')", sid)))
                    show_all(cdp, sid)
                    got = cdp.js(MEASURE, sid)
                    where = f"published {scheme} {width}px"
                    slipped = [r for r in got["rows"] if " · " in r["text"]]
                    self.assertTrue(slipped, where)
                    self.assertFalse(got["pageScroll"] or got["cardScroll"] or got["listScroll"], f"{where}: nothing scrolls sideways")
                    for r in got["rows"]:
                        self.assertTrue(r["inCard"] and r["inRow"] and r["dateClearOfName"], f"{where}: {r['text']}")
                        self.assertEqual((r["cols"], r["across"]), (4, True), f"{where}: the columns stay side by side ({r['text']})")
                        if width == 1400:
                            self.assertEqual(r["lines"], 1, f"{where}: one line ({r['text']})")
                            self.assertFalse(r["cellsClip"], where)
                    for r in slipped:
                        self.assertTrue(r["text"].startswith("Expected "), where)


if __name__ == "__main__":
    unittest.main()
