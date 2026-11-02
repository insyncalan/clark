"""Prototype parity on the Dashboard's Milestones block (A-D22): the switch, and the progress bar on each row.

Run: python3 dev/run_tests.py test_milestones_dashboard
The committed page runs from the real server on the demo database (fixed CLARK_NOW) in headless Chrome (required: it fails, never
skips, without Chrome) at 1400 and 900 px, in light and dark. Laptop widths only. It checks that the block on the Dashboard is the
same block as on the Milestones page (the Timeline and Calendar switch, named, with its pressed state), that each row with a
progress figure draws a bar whose length is the figure and says the figure as text (so it is never colour alone), that the bar reads
against its track, that a row with no figure draws no bar and says so in words, and that the same rows show the same bars in the
Milestones page of a published file. The eye on each row is in tests/test_milestones_eye.py.
"""
import json
import shutil
import tempfile
import unittest

from _demo import USER, DemoStore

from clark import page, publish
from test_server import Running, chrome, wait
from test_work_items import FIXED_DATE, load_demo, page_target

EMPTY_BRANDING = tempfile.mkdtemp(prefix="clark-no-brand-")        # so a brand on this laptop never changes a test
PERCENTS = {"TUL-M-001": 100, "TUL-M-004": 60, "TUL-M-002": 0, "TUL-M-003": 20}      # TUL-M-005 has none: "Not set"
SHOWN = ["TUL-M-001", "TUL-M-004", "TUL-M-002", "TUL-M-003", "TUL-M-005"]        # the first five rows, in the list's own order

# What the block's rows look like to a person: for each row its name, the bar (if any), its figure as text and the spoken name.
# Colours go through a canvas so any colour syntax (rgb, oklch, color-mix) is read as plain sRGB.
SEE = """((root) => {
  const px = (c) => { const k = document.createElement('canvas').getContext('2d', {willReadFrequently: true}); k.clearRect(0, 0, 1, 1); k.fillStyle = c; k.fillRect(0, 0, 1, 1); return [...k.getImageData(0, 0, 1, 1).data]; };
  const lum = (c) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }; return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2]); };
  const back = (e) => { for (; e; e = e.parentElement) { const c = px(getComputedStyle(e).backgroundColor); if (c[3] === 255) return c; } return [255, 255, 255, 255]; };
  const ratio = (a, b) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
  const box = root.querySelector('.msv');
  if (!box) return null;
  const rows = [...box.querySelectorAll('.msl-row')].map((r) => {
    const prog = r.querySelector('.msl-prog'), bar = r.querySelector('.pbar'), fill = bar && bar.querySelector('i'), num = prog.querySelector('.num');
    const pr = prog.getBoundingClientRect(), rr = r.getBoundingClientRect();
    const out = {id: r.dataset.ms, text: prog.textContent.trim(), notSet: !!prog.querySelector('.muted'), bar: !!bar,
                 inside: pr.left >= rr.left - 1 && pr.right <= rr.right + 1 && pr.width > 0 && pr.height > 0};
    if (bar) {
      const bw = bar.getBoundingClientRect().width, fw = fill.getBoundingClientRect().width;
      out.pct = Math.round((fw / bw) * 100); out.barW = bw; out.barH = bar.getBoundingClientRect().height; out.hiddenFromReaders = bar.getAttribute('aria-hidden') === 'true';
      out.fillVsTrack = ratio(px(getComputedStyle(fill).backgroundColor), px(getComputedStyle(bar).backgroundColor));
      out.numVsRow = ratio(px(getComputedStyle(num).color), back(num));
      out.spoken = num.textContent.trim();
    }
    return out;
  });
  const sw = box.querySelector('.msv-sw');
  const buttons = sw ? [...sw.querySelectorAll('button')].map((b) => ({view: b.dataset.msvb, name: b.getAttribute('aria-label') || b.textContent.trim(), current: b.getAttribute('aria-current'), tag: b.tagName})) : [];
  return {place: box.dataset.place, group: sw ? sw.getAttribute('role') + '|' + sw.getAttribute('aria-label') : null, buttons, rows,
          noScroll: document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1};
})(document.querySelector('%s'))"""


class PublishedFields(unittest.TestCase):
    def test_a_published_milestone_carries_its_progress_figure(self):
        self.assertIn("percent_complete", publish.PUBLISH_FIELDS["milestones"])


class Block(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store, cls.folder, _ = load_demo()
        with cls.store.step("dashboard", USER) as st:
            for ident, pct in PERCENTS.items():
                st.update("milestones", ident, {"percent_complete": pct})
        cls.projects = cls.store.read("projects")

    @classmethod
    def tearDownClass(cls):
        cls.store.close()
        shutil.rmtree(str(cls.folder), ignore_errors=True)

    def serve(self):
        s = Running(data_for=self.store.data_for, projects=lambda: self.projects, page_html=lambda: page.page_html(tempfile.mkdtemp()))
        self.addCleanup(s.close)
        return s.port

    def visit(self, cdp, width, hash_, theme=None, edit=False):
        sid = page_target(cdp)
        cdp.call("Page.enable", {}, sid)
        cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE}, sid)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
        cdp.call("Page.navigate", {"url": "about:blank"}, sid)
        cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{self.serve()}/{hash_}"}, sid)
        self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.msv[data-place^=sec-] .msl-row')", sid)), "the block drew its rows")
        if edit:
            cdp.js("document.querySelector('[data-mode=edit]').click()", sid)
            self.assertTrue(wait(lambda: cdp.js("document.querySelector('#report').dataset.mode === 'edit'", sid)), "Edit is on")
        if theme:
            cdp.js(f"document.documentElement.dataset.theme = {json.dumps(theme)}", sid)
        return sid

    def check_rows(self, seen, label):
        by = {r["id"]: r for r in seen["rows"]}
        self.assertEqual([r["id"] for r in seen["rows"]], SHOWN, label)
        for ident in SHOWN:
            r = by[ident]
            self.assertTrue(r["inside"], f"{label} {ident}: the progress sits inside its row")
            if ident in PERCENTS:
                pct = PERCENTS[ident]
                self.assertTrue(r["bar"] and not r["notSet"], f"{label} {ident}: a bar")
                self.assertEqual(r["text"], f"Progress {pct}%", f"{label} {ident}: the figure is text, with its name for a reader")
                self.assertEqual(r["spoken"], f"Progress {pct}%")
                self.assertLessEqual(abs(r["pct"] - pct), 2, f"{label} {ident}: the bar is {pct}% of its track")
                self.assertTrue(r["hiddenFromReaders"], f"{label} {ident}: the bar is a picture; the text speaks")
                self.assertGreaterEqual(r["barW"], 40, f"{label} {ident}: the track is wide enough to read")
                self.assertGreaterEqual(r["barH"], 4, f"{label} {ident}: the track is tall enough to see")
                if 0 < pct < 100:
                    self.assertGreaterEqual(r["fillVsTrack"], 3, f"{label} {ident}: the filled part shows against the track at 3:1")
                self.assertGreaterEqual(r["numVsRow"], 4.5, f"{label} {ident}: the figure reads at 4.5:1")
            else:
                self.assertFalse(r["bar"], f"{label} {ident}: no figure, no bar")
                self.assertTrue(r["notSet"] and r["text"] == "Not set", f"{label} {ident}: it says so in words")

    def test_the_dashboard_block_is_the_milestones_block_with_a_bar_and_a_figure_on_each_row(self):
        for width in (1400, 900):
            for theme in ("light", "dark"):
                with chrome() as cdp:
                    sid = self.visit(cdp, width, "#dashboard&p=TUL", theme=theme)
                    with self.subTest(width=width, theme=theme):
                        seen = cdp.js(SEE % ".secs", sid)
                        self.assertTrue(seen["place"].startswith("sec-"), "this is the Dashboard's own block")
                        self.assertEqual(seen["group"], "group|Milestone view")
                        self.assertEqual([(b["view"], b["name"], b["tag"]) for b in seen["buttons"]],
                                         [("line", "Timeline", "BUTTON"), ("cal", "Calendar", "BUTTON")])
                        self.assertEqual([b["current"] for b in seen["buttons"]], ["true", "false"])
                        self.check_rows(seen, f"{width}/{theme}")
                        self.assertTrue(seen["noScroll"], "no page-wide scroll")

    def test_the_same_rows_show_the_same_bars_in_edit_and_on_the_milestones_page(self):
        with chrome() as cdp:
            sid = self.visit(cdp, 1400, "#dashboard&p=TUL", edit=True)
            self.check_rows(cdp.js(SEE % ".secs", sid), "edit")
        with chrome() as cdp:
            sid = self.visit(cdp, 1400, "#dashboard&p=TUL")
            cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{self.serve()}/#milestones&p=TUL"}, sid)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.msv[data-place=page] .msl-row')", sid)))
            seen = cdp.js(SEE % ".frame", sid)
            self.assertEqual(seen["place"], "page")
            self.check_rows(seen, "page")

    def test_a_row_is_still_one_tab_stop_and_the_bar_adds_none(self):
        with chrome() as cdp:
            sid = self.visit(cdp, 1400, "#dashboard&p=TUL")
            stops = cdp.js("[...document.querySelectorAll('.msv[data-place^=sec-] .msl-row .msl-prog *')].filter((e) => e.tabIndex >= 0).length", sid)
            self.assertEqual(stops, 0, "the bar and its figure are not controls")


class PublishedFile(unittest.TestCase):
    def test_the_published_milestones_page_shows_the_bar_where_the_file_carries_a_figure(self):
        demo = DemoStore()
        self.addCleanup(demo.close)
        with demo.store.step("dashboard", USER) as st:
            with_pct = st.create("milestones", {"project": "ABC", "name": "Half done", "baseline_date": "2030-05-01",
                                                "percent_complete": 50, "client_visible": 1, "source": "demo"})
            without = st.create("milestones", {"project": "ABC", "name": "Not measured", "baseline_date": "2030-06-01",
                                               "client_visible": 1, "source": "demo"})
        folder = tempfile.mkdtemp(prefix="clark-pub-")
        self.addCleanup(shutil.rmtree, folder, True)
        done = publish.publish(demo.store, "ABC", folder, by_user=USER, now="2026-10-28", branding=EMPTY_BRANDING)
        with chrome() as cdp:
            sid = page_target(cdp)
            cdp.call("Page.navigate", {"url": "file://" + str(done["path"])}, sid)
            self.assertTrue(wait(lambda: cdp.js("document.documentElement.dataset.ready === '1'", sid)))
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.tab')", sid)))
            cdp.js("[...document.querySelectorAll('.tab')].find(t => /Milestones/.test(t.textContent)).click()", sid)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.msv .msl-row')", sid)), "the file's Milestones page drew its rows")
            seen = cdp.js(SEE % "body", sid)
            by = {r["id"]: r for r in seen["rows"]}
            self.assertEqual(by[with_pct]["text"], "Progress 50%")
            self.assertLessEqual(abs(by[with_pct]["pct"] - 50), 2)
            self.assertFalse(by[without]["bar"], "no figure in the file: no bar")
            self.assertEqual(by[without]["text"], "Not set")
            self.assertEqual([b["name"] for b in seen["buttons"]], ["Timeline", "Calendar"])
            self.assertEqual(cdp.js("document.querySelectorAll('.msv .msl-prog button, .msv .msl-prog a, .msv .msl-prog input').length", sid), 0,
                             "the file's progress holds no control")


if __name__ == "__main__":
    unittest.main()
