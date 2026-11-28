"""Row 1230, part 1: the status tracker ends the Dashboard's Milestones section, in View and in Edit, where the Legend was.

Run: python3 dev/run_tests.py -j 1 test_ms_tracker_1230
The page runs from the real server over a real store (fictional data) in headless Chrome (required: it fails, never skips, without
Chrome). One chip for each state: its mark, its count and its word, under the label Status. The counts are the section's rows by
state. The Dashboard has no Legend any more; the Milestones page keeps its Legend and has no tracker. Widths 1400 and 900 only.
"""
import json
import shutil
import tempfile
import unittest
from unittest import mock

from _demo import USER, DemoStore

from clark import page, server as sv
from test_server import Running, chrome, wait
from test_milestones_page import publish_with_plants
from test_work_items import FIXED_DATE, page_target

EMPTY_BRANDING = tempfile.mkdtemp(prefix="clark-no-brand-")
STATES = ["Achieved", "On track", "At risk", "Slipped", "Overdue", "Forecast", "Cancelled"]

SEE = """(() => {
  const box = document.querySelector('.msv[data-place^=sec-]'), t = box && box.querySelector('[data-tracker]');
  if (!box) return null;
  const chips = t ? [...t.querySelectorAll('[data-tracker-state]')].map((c) => ({state: c.dataset.trackerState, n: Number(c.dataset.n), text: c.textContent.trim(),
                                                                                 mark: !!c.querySelector('svg'), shown: c.getBoundingClientRect().width > 0})) : [];
  const rows = [...box.querySelectorAll('.msl-row .mst')].map((e) => e.textContent.trim());
  return {has: !!t, role: t && t.getAttribute('role'), aria: t && t.getAttribute('aria-label'), label: t && t.querySelector('.mtk-cap').textContent,
          last: !!t && box.lastElementChild === t, inside: !!t && t.getBoundingClientRect().right <= box.getBoundingClientRect().right + 1,
          chips, rows, legend: box.querySelectorAll('.mlg').length, noScroll: document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1};
})()"""


class Tracker(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.store = self.demo.store
        with self.store.step("dashboard", USER) as st:
            st.create("milestones", {"project": "ABC", "name": "Training done", "baseline_date": "2030-04-01", "source": "demo"})
            st.create("milestones", {"project": "ABC", "name": "Handover", "baseline_date": "2020-05-01", "source": "demo"})
        self.s = Running(data_for=self.store.data_for, page_html=lambda: page.page_html(EMPTY_BRANDING))
        self.addCleanup(self.s.close)
        quiet = mock.patch.object(sv.LOG, "disabled", True)
        quiet.start()
        self.addCleanup(quiet.stop)

    def visit(self, cdp, hash_, width, edit, ready=".msv"):
        sid = page_target(cdp)
        cdp.call("Page.enable", {}, sid)
        cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE}, sid)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
        cdp.call("Page.navigate", {"url": "about:blank"}, sid)
        cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{self.s.port}/{hash_}"}, sid)
        self.assertTrue(wait(lambda: cdp.js(f"!!document.querySelector('{ready}')", sid), 10), "the block drew")
        if edit:
            cdp.js("document.querySelector('[data-mode=edit]').click()", sid)
            self.assertTrue(wait(lambda: cdp.js("document.querySelector('[data-mode=edit]').getAttribute('aria-pressed') === 'true'", sid), 10), "Edit is on")
        self.assertTrue(wait(lambda: cdp.js("document.getAnimations().length === 0", sid), 10))
        return sid

    def test_the_tracker_ends_the_dashboard_section_in_view_and_in_edit(self):
        for width in (1400, 900):
            for edit in (False, True):
                with self.subTest(width=width, edit=edit), chrome() as cdp:
                    sid = self.visit(cdp, "#dashboard&p=ABC", width, edit, ".msv .msl-row")
                    got = cdp.js(SEE, sid)
                    self.assertTrue(got["has"], "the tracker is drawn")
                    self.assertEqual((got["label"], got["aria"], got["role"]), ("Status", "Status summary and key", "group"))
                    self.assertTrue(got["last"] and got["inside"], "last in the section, inside it")
                    self.assertEqual(got["legend"], 0, "the Legend is gone from the Dashboard")
                    self.assertTrue(got["noScroll"], "no sideways scroll")
                    self.assertEqual([c["state"] for c in got["chips"]], STATES, "one chip for each state, in order")
                    for c in got["chips"]:
                        self.assertTrue(c["mark"] and c["shown"], c["state"])
                        self.assertEqual(c["text"], f"{c['n']} {c['state']}")
                        self.assertEqual(c["n"], got["rows"].count(c["state"]), f"{c['state']}: the count is the rows in that state")
                    self.assertEqual(sum(c["n"] for c in got["chips"]), len(got["rows"]), "every row is counted once")
                    self.assertGreaterEqual(len(got["rows"]), 3)

    def test_the_tracker_styling_zero_chips_icon_size_and_top_border(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.visit(cdp, "#dashboard&p=ABC", width, False, ".msv .msl-row")
                got = cdp.js("""(() => {
                  const t = document.querySelector('.msv[data-place^=sec-] [data-tracker]'), cs = (e) => getComputedStyle(e);
                  const chips = [...t.querySelectorAll('.mtk-chip')].map((c) => { const i = c.querySelector('.ms-i').getBoundingClientRect();
                    return {zero: c.classList.contains('zero'), n: Number(c.dataset.n), color: cs(c).color, w: i.width, h: i.height}; });
                  return {chips, cap: cs(t.querySelector('.mtk-cap')).color, bw: cs(t).borderTopWidth, bs: cs(t).borderTopStyle, bc: cs(t).borderTopColor};
                })()""", sid)
                zeros = [c for c in got["chips"] if c["n"] == 0]
                full = [c for c in got["chips"] if c["n"] > 0]
                self.assertTrue(zeros and full, "the demo has both empty and counted states")
                for c in got["chips"]:
                    self.assertEqual(c["zero"], c["n"] == 0, "the zero class is on exactly the empty chips")
                    self.assertEqual((c["w"], c["h"]), (16, 16), "the chip mark is 16 by 16")
                for c in zeros:
                    self.assertEqual(c["color"], got["cap"], "an empty chip is in the muted text colour")
                for c in full:
                    self.assertNotEqual(c["color"], got["cap"], "a counted chip is in the normal text colour")
                self.assertEqual((got["bw"], got["bs"]), ("1px", "solid"), "the tracker has a 1px solid top border")
                self.assertNotIn(got["bc"], ("rgba(0, 0, 0, 0)", "transparent"), "the top border is visible")

    def test_the_milestones_page_keeps_its_legend_and_has_no_tracker(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.visit(cdp, "#milestones&p=ABC", width, False, ".mv-wrap")
                self.assertEqual(cdp.js("document.querySelectorAll('.msv[data-place=page] .mlg').length", sid), 1)
                self.assertEqual(cdp.js("document.querySelectorAll('[data-tracker]').length", sid), 0)

    def test_a_published_file_says_the_clients_words_and_has_no_cancelled_chip(self):
        demo, folder, path, _ids = publish_with_plants()
        self.addCleanup(demo.close)
        self.addCleanup(shutil.rmtree, folder, True)
        with chrome() as cdp:
            sid = page_target(cdp)
            cdp.call("Page.navigate", {"url": path.as_uri()}, sid)
            self.assertTrue(wait(lambda: cdp.js("document.documentElement.dataset.ready === '1'", sid), 10))
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('[data-tracker]')", sid), 10), "the file draws the tracker")
            got = cdp.js("[...document.querySelectorAll('[data-tracker]')[0].querySelectorAll('[data-tracker-state]')].map((c) => [c.dataset.trackerState, c.textContent.trim()])", sid)
        self.assertEqual([s for s, _ in got], [s for s in STATES[:-1] if s != "Overdue"], "no Cancelled chip and no Late chip in a file (row 1543 AP4)")
        words = dict(got)
        self.assertRegex(words["Slipped"], r"^\d+ Expected later$")
        self.assertNotIn("Overdue", words)
        self.assertNotIn("Slipped", words["Slipped"])

    def test_every_chip_has_a_title_and_only_empty_chips_are_zero(self):
        with chrome() as cdp:
            sid = self.visit(cdp, "#dashboard&p=ABC", 1400, False, ".msv .msl-row")
            got = cdp.js("[...document.querySelectorAll('.msv[data-place^=sec-] [data-tracker-state]')].map((c) => ({n: Number(c.dataset.n), title: c.getAttribute('title'), zero: c.classList.contains('zero')}))", sid)
        self.assertEqual(len(got), len(STATES))
        for c in got:
            self.assertTrue(c["title"] and c["title"].strip(), "the chip says what its state means")
            self.assertEqual(c["zero"], c["n"] == 0, "the dim class is on a chip with none, and only there")
        self.assertTrue(any(c["zero"] for c in got) and any(not c["zero"] for c in got), "both kinds are in the data")


if __name__ == "__main__":
    unittest.main()
