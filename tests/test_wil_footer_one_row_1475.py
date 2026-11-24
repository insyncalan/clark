"""Row 1475: in a Work items section the footer is ONE line: Show all items at the left, Review all N items at the right. At half width the
footers of a pair are level (the footer sits at the bottom of the card), with or without Show all items and with lists of any length.
Classic only; the published file has neither link. Run: CLARK_CHROME=/usr/local/bin/creaite-chrome python3 dev/run_tests.py test_wil_footer_one_row_1475.py"""
import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path

import test_tpl_workitems as base
from test_work_items_mockup_1195 import Look
from clark import publish
from test_report_editor import EMPTY_BRANDING, Pg, tearDownModule  # noqa: F401
from test_server import chrome

COLS = ["id", "owner", "due", "status", "priority"]
GEO = """(ref => { const sec = document.querySelector('[data-id="' + ref + '"]'), foot = sec.querySelector('[data-wil-foot]'), all = sec.querySelector('[data-wil-all]'),
  rev = sec.querySelector('[data-wil-review]'), r = (e) => { if (!e) return null; const b = e.getBoundingClientRect(); return {top: b.top, bottom: b.bottom, left: b.left, right: b.right}; };
  const inner = sec.getBoundingClientRect(), cs = getComputedStyle(sec);
  return {all: r(all), rev: r(rev), foot: r(foot), innerLeft: inner.left + parseFloat(cs.paddingLeft) + 1, innerRight: inner.right - parseFloat(cs.paddingRight) - 1,
    bottom: inner.bottom, rows: sec.querySelectorAll('tr[data-id], li[data-id]').length, html: foot ? foot.outerHTML.slice(0, 400) : '', lines: foot ? foot.querySelectorAll('[data-wil-all], [data-wil-review]').length : 0}; })"""


def geo(p, ref):
    return p.js(f"({GEO})({json.dumps(ref)})")


class FooterOneRow(Look):
    """The served Classic page (Cards is frozen)."""

    def setUp(self):
        super().setUp()
        for n in range(4):
            self.demo.action(description=f"Extra step {n}", owner="Pat Demo", due_date="2030-02-0%d" % (n + 1))
        with self.store.step("dashboard", base.USER) as st:
            self.text = st.create("report_sections", {"project": "ABC", "type": "text", "title": "Fictional notes", "sort_order": 1})

    def pair(self, left_max, right_max):
        a = self.add({"mode": "all", "columns": COLS, "kinds": ["action"], "max": left_max}, title="Left list", after=self.text)
        b = self.add({"mode": "all", "columns": COLS, "kinds": ["action"], "max": right_max}, title="Right list", after=a, beside=1)
        return a, b

    def drawn(self, p, *refs):
        for ref in refs:
            p.until(f"!!document.querySelector('[data-id=\"{ref}\"] [data-wil-foot]')", "the footer drew")

    def widths(self):
        return (1400, 900)

    def test_show_all_and_review_all_share_one_footer_line_at_half_width_1400_and_900(self):
        a, b = self.pair(2, 3)
        for width in self.widths():
            with self.subTest(width=width), chrome() as cdp:
                p = self.show(cdp, width)
                self.drawn(p, a, b)
                for ref in (a, b):
                    g = geo(p, ref)
                    self.assertIsNotNone(g["all"], g)
                    self.assertEqual(g["all"]["top"], g["rev"]["top"], f"{width}: {g}")
                    self.assertLessEqual(g["foot"]["bottom"] - g["rev"]["top"], g["rev"]["bottom"] - g["rev"]["top"] + 1, f"the footer is one line high: {g}")

    def test_review_all_is_at_the_right_edge_and_show_all_at_the_left_1400_and_900(self):
        a, b = self.pair(2, 3)
        for width in self.widths():
            with self.subTest(width=width), chrome() as cdp:
                p = self.show(cdp, width)
                self.drawn(p, a, b)
                for ref in (a, b):
                    g = geo(p, ref)
                    self.assertLessEqual(abs(g["rev"]["right"] - g["innerRight"]), 2, f"{width} right edge: {g}")
                    self.assertLessEqual(abs(g["all"]["left"] - g["innerLeft"]), 2, f"{width} left edge: {g}")

    def test_a_section_without_show_all_keeps_review_all_level_with_its_neighbour_1400_and_900(self):
        a, b = self.pair(2, 10)
        for width in self.widths():
            with self.subTest(width=width), chrome() as cdp:
                p = self.show(cdp, width)
                self.drawn(p, a, b)
                ga, gb = geo(p, a), geo(p, b)
                self.assertIsNone(gb["all"], gb)
                self.assertLessEqual(abs(gb["rev"]["right"] - gb["innerRight"]), 2, gb)
                if width > 900:
                    self.assertEqual(ga["rev"]["top"], gb["rev"]["top"], f"{ga} {gb}")

    def test_footers_of_two_half_width_sections_are_level_with_lists_of_different_length_at_1400(self):
        a, b = self.pair(2, 6)
        with chrome() as cdp:
            p = self.show(cdp, 1400)
            self.drawn(p, a, b)
            ga, gb = geo(p, a), geo(p, b)
            self.assertEqual(ga["rev"]["top"], gb["rev"]["top"], f"{ga} {gb}")
            self.assertEqual(ga["all"]["top"], gb["all"]["top"] if gb["all"] else ga["all"]["top"], f"{ga} {gb}")
            self.assertLessEqual(abs(ga["bottom"] - gb["bottom"]), 1)

    def test_stacked_sections_each_have_one_footer_row_at_900(self):
        a, b = self.pair(2, 3)
        with chrome() as cdp:
            p = self.show(cdp, 900)
            self.drawn(p, a, b)
            ga, gb = geo(p, a), geo(p, b)
            self.assertGreater(gb["foot"]["top"], ga["foot"]["bottom"], "stacked")
            for g in (ga, gb):
                self.assertEqual(g["all"]["top"], g["rev"]["top"], g)
                self.assertLess(g["all"]["left"], g["rev"]["left"], g)

    def test_full_width_one_footer_row_and_tab_order_show_all_then_review_all_light_and_dark(self):
        ref = self.add({"mode": "all", "columns": COLS, "kinds": ["action"], "max": 2}, title="Full list", after=self.text)
        for width in self.widths():
            for dark in (False, True):
                with self.subTest(width=width, dark=dark), chrome() as cdp:
                    p = self.show(cdp, width, dark)
                    self.drawn(p, ref)
                    g = geo(p, ref)
                    self.assertEqual(g["all"]["top"], g["rev"]["top"], g)
                    order = p.js(f"(() => {{ const s = document.querySelector('[data-id=\"{ref}\"]'); return [...s.querySelectorAll('[data-wil-all], [data-wil-review]')].map(e => e.hasAttribute('data-wil-all') ? 'all' : 'review'); }})()")
                    self.assertEqual(order, ["all", "review"])
                    p.js(f"document.querySelector('[data-id=\"{ref}\"] [data-wil-all]').focus()")
                    p.key("Tab", code="Tab", vk=9)
                    self.assertTrue(p.js("document.activeElement.hasAttribute('data-wil-review')"), "Tab goes from Show all items to Review all N items")

    def test_no_show_all_when_the_list_has_exactly_most_rows_1400(self):
        probe = self.add({"mode": "all", "columns": COLS, "kinds": ["action"], "max": 50}, title="Probe list", after=self.text)
        with chrome() as cdp:
            p = self.show(cdp, 1400)
            self.drawn(p, probe)
            n = int(re.search(r"of (\d+)", geo(p, probe)["html"]).group(1))      # the Foot says "Showing all of N"
        self.assertGreater(n, 2)
        exact = self.add({"mode": "all", "columns": COLS, "kinds": ["action"], "max": n}, title="Exact list", after=probe)
        with chrome() as cdp:
            p = self.show(cdp, 1400)
            self.drawn(p, exact)
            g = geo(p, exact)
            self.assertIn(f"of {n}", g["html"], g)
            self.assertIsNone(g["all"], f"a list of exactly Most rows has no Show all items: {g}")
            self.assertIsNotNone(g["rev"], g)

    def test_footer_padding_gap_and_link_box_1400_and_900(self):
        a, b = self.pair(2, 3)
        for width in self.widths():
            with self.subTest(width=width), chrome() as cdp:
                p = self.show(cdp, width)
                self.drawn(p, a)
                r = p.js("""(() => { const sec = document.querySelector('[data-id="%s"]'), f = sec.querySelector('[data-wil-foot]'), fs = getComputedStyle(f);
                  const out = {pad: parseFloat(fs.paddingTop), gap: parseFloat(fs.columnGap), links: []};
                  for (const e of f.querySelectorAll('[data-wil-all], [data-wil-review]')) { const c = getComputedStyle(e); out.links.push({d: c.display, ai: c.alignItems, pt: parseFloat(c.paddingTop), pb: parseFloat(c.paddingBottom), bs: c.boxSizing, mh: parseFloat(c.minHeight), h: e.getBoundingClientRect().height}); }
                  return out; })()""" % a)
                self.assertEqual(r["pad"], 8, r)      # var(--space-2)
                self.assertEqual(r["gap"], 12, r)      # var(--space-3)
                self.assertEqual(len(r["links"]), 2, r)
                for k in r["links"]:
                    self.assertEqual((k["d"], k["ai"], k["pt"], k["pb"], k["bs"]), ("flex", "center", 0, 0, "border-box"), r)
                    self.assertEqual(k["mh"], 32, r)      # var(--space-6)
                    self.assertGreaterEqual(k["h"], 32, r)

    def test_a_published_file_has_no_footer_links_1400_and_900(self):
        ref = self.add({"mode": "all", "columns": COLS, "kinds": ["action"], "max": 2}, title="File list", after=self.text)
        out = tempfile.mkdtemp(prefix="clark-1475-")
        self.addCleanup(shutil.rmtree, out, ignore_errors=True)
        path = Path(publish.publish(self.store, "ABC", out, by_user=base.USER, now=base.TODAY, branding=EMPTY_BRANDING)["path"])
        for width in self.widths():
            with self.subTest(width=width), chrome() as cdp:
                tid = next(t["targetId"] for t in cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
                sid = cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1100, "deviceScaleFactor": 1, "mobile": False}, sid)
                cdp.call("Page.navigate", {"url": path.as_uri()}, sid)
                p = Pg(self, cdp, sid)
                p.until("document.documentElement.dataset.ready === '1' && !!document.querySelector('h1')", "the file drew")
                p.until(f"!!document.querySelector('[data-id=\"{ref}\"] .wil')", "the list drew")
                self.assertEqual(p.js("document.querySelectorAll('[data-wil-all], [data-wil-review], [data-wil-foot]').length"), 0)


if __name__ == "__main__":
    unittest.main()
