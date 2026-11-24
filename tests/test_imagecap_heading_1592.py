"""Row 1592 (v1.3 P0, Classic only): a full width image section shows its heading (number and title) above the picture, in View.

Run: python3 dev/run_tests.py test_imagecap_heading_1592
Part 1 reads the stylesheets (no Chrome): the Classic rule is in rules-2.css before the Row 1314 block, the Cards rule in shell.css is as it was.
Part 2 is Chrome at 1400 and 900, light and dark, with the Classic theme layered; it needs Chrome (CLARK_CHROME). Fictional data only.
Left out of this row (Product Manager ruling, ticket comment): the per-section heading switch, row 1272. Also not tested: a section with no title (the store refuses a blank title, store.section_title, so no such section exists).
"""
import json
import re
import tempfile
import unittest

from _demo import USER
from _paths import ROOT
from _pictures import data, png
from _real_server import real_server
from clark import page, theme
from clark import store as store_module
from clark.section_kinds import imagecap as fi
from test_report_editor import Base
from test_server import chrome

RULES2 = (ROOT / "src" / "clark" / "themes" / "prototype-2.0" / "rules-2.css").read_text(encoding="utf-8")
SHELL = (ROOT / "src" / "clark" / "page" / "shell.css").read_text(encoding="utf-8")
BLOCK = RULES2[RULES2.index("/* Row 1592"):RULES2.index("/* Row 1314")]
HIDE = '.sec[data-type="imagecap"] > .sec-head:has(~ .tpl-fullimg) { display: none; }'


class Sheets(unittest.TestCase):
    def test_the_rule_is_in_rules_2_before_row_1314_and_has_no_hex_or_px(self):
        self.assertLess(RULES2.index("/* Row 1592"), RULES2.index("/* Row 1314"))
        code = re.sub(r"/\*.*?\*/", "", BLOCK, flags=re.S)
        self.assertNotRegex(code, r"#[0-9a-fA-F]{3,6}\b")
        self.assertNotRegex(code, r"\d\s*px")

    def test_the_classic_rule_shows_the_heading_and_is_stronger_than_the_hide_rule(self):
        rule = re.search(r"^(\.secs \.sec\[data-type=\"imagecap\"\] > \.sec-head:has\(~ \.tpl-fullimg\)) \{([^}]*)\}", BLOCK, re.M)
        self.assertIsNotNone(rule)
        self.assertEqual(rule.group(2).strip(), "display: flex;")
        # the same selector as the hide rule plus the .secs ancestor: one class more, so it wins whatever the order
        self.assertEqual(rule.group(1), ".secs " + HIDE.split(" {")[0])

    def test_cards_stylesheet_keeps_its_hide_rule_and_has_none_of_ours(self):
        self.assertIn(HIDE, SHELL)
        self.assertNotIn("Row 1592", SHELL)

    def test_the_view_switch_for_a_hidden_heading_is_untouched(self):
        self.assertIn('#report[data-mode="view"] .sec.no-head > .sec-head { position: absolute;', SHELL)
        self.assertNotIn("no-head", re.sub(r"/\*.*?\*/", "", BLOCK, flags=re.S))

    def test_row_1314_is_still_the_last_row_block(self):
        self.assertEqual(RULES2.rindex("/* Row "), RULES2.index("/* Row 1314"))


PROBE = r"""(() => {
  const secs = [...document.querySelectorAll('.secs > .sec')];
  const num = (s) => { const h = s.querySelector(':scope > .sec-head'); return h && getComputedStyle(h, '::before').content; };
  return secs.map((s) => {
    const h = s.querySelector(':scope > .sec-head'), t = s.querySelector('.sec-h, .sec-title'), pic = s.querySelector('.tpl-fullimg, .fi-stage');
    const hr = h && h.getBoundingClientRect(), pr = pic && pic.getBoundingClientRect(), sr = s.getBoundingClientRect();
    return {id: s.dataset.id, type: s.dataset.type, head: !!h, display: h ? getComputedStyle(h).display : null, hw: hr ? hr.width : 0, hh: hr ? hr.height : 0,
            hbottom: hr ? hr.bottom : null, ptop: pr ? pr.top : null, text: t ? t.textContent.trim() : '', n: num(s), left: sr.left, right: sr.right,
            gap: hr && pr ? pr.top - hr.bottom : null};
  });
})()"""

MINE = "Fictional image"


class Look(Base):
    def setUp(self):
        super().setUp()
        self.s.close()
        css = theme.css("prototype-2.0")
        self.s = real_server(self.store.path, self.store.data_for,
                             page_html=lambda: page.layer_theme(page.page_html(tempfile.mkdtemp()), css), seam=lambda real, which: real)
        self.addCleanup(self.s.close)

    def add(self, title, beside=0):
        body = fi.check(fi.with_picture({"v": 2, "shape": "16:9", "fx": 300, "caption": "Fictional plan"}, "original", data(png(w=40, h=20))), None)
        with self.store.step("dashboard", USER) as st:
            return st.create("report_sections", {"project": "ABC", "type": "imagecap", "title": title, "sort_order": 990, "beside": beside,
                                                 "body": store_module.check_section_body("imagecap", json.dumps(body))})

    def rows(self, cdp, p, width, scheme):
        cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme}]}, p.sid)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
        p.until(f"window.innerWidth === {width}", "resized")
        p.until("document.querySelector('.tpl-fullimg, .fi-stage')", "the image section is drawn")
        return p.js(PROBE)

    def each(self, edit=False):
        with chrome() as cdp:
            p = self.visit(cdp)
            if edit:
                p.edit()
            for scheme in ("light", "dark"):
                for w in (1400, 900):
                    yield cdp, p, f"{w} px, {scheme}", self.rows(cdp, p, w, scheme)


class ImagecapHeading(Look):
    def test_the_view_shows_the_heading_above_the_picture(self):
        self.add(MINE)
        for _, _, where, rows in self.each():
            mine = next(r for r in rows if r["type"] == "imagecap" and r["text"] == MINE)
            self.assertNotEqual(mine["display"], "none", where)
            self.assertGreater(mine["hw"], 0, where)
            self.assertGreater(mine["hh"], 0, where)
            self.assertLessEqual(mine["hbottom"], mine["ptop"], f"{where}: the heading ends above the picture")

    def test_a_half_width_image_shows_its_heading(self):
        self.add(MINE, beside=1)
        for _, _, where, rows in self.each():
            half = next(r for r in rows if r["type"] == "imagecap" and r["text"] == MINE)
            self.assertGreater(half["hh"], 0, where)
            self.assertGreaterEqual(half["hw"], 1, where)
            self.assertLessEqual(half["hw"], half["right"] - half["left"] + 1, f"{where}: inside the half's box")

    def test_the_numbers_are_continuous_and_the_rail_matches(self):
        self.add(MINE)
        for _, p, where, rows in self.each():
            heads = [r for r in rows if r["head"] and r["display"] != "none" and r["n"] not in (None, "none", "normal")]
            self.assertEqual(len(heads), len([r for r in rows if r["head"]]), f"{where}: no section draws without its number")
            rail = p.js("document.querySelectorAll('.rail a, nav a[href^=\"#sec\"], [data-rail] a').length")
            if rail:
                self.assertEqual(rail, len(rows), where)

    def test_the_heading_spacing_matches_other_sections_and_edit_is_unchanged(self):
        self.add(MINE)
        with chrome() as cdp:
            p = self.visit(cdp)
            for scheme in ("light", "dark"):
                for w in (1400, 900):
                    rows = self.rows(cdp, p, w, scheme)
                    mine = next(r for r in rows if r["type"] == "imagecap" and r["text"] == MINE)
                    ref = p.js("(() => { const h = document.querySelector('.secs > .sec:not([data-type=imagecap]) > .sec-head'); const cs = getComputedStyle(h);"
                               " return {mb: cs.marginBottom, pb: cs.paddingBottom, fs: getComputedStyle(h.querySelector('.sec-h')).fontSize}; })()")
                    got = p.js("(() => { const h = [...document.querySelectorAll('.secs > .sec[data-type=imagecap] > .sec-head')].find(x => x.textContent.includes('" + MINE + "'));"
                               " const cs = getComputedStyle(h); return {mb: cs.marginBottom, pb: cs.paddingBottom, fs: getComputedStyle(h.querySelector('.sec-h')).fontSize}; })()")
                    self.assertEqual(got, ref, f"{w} px, {scheme}: the same heading rules as any section ({mine['gap']} px to the picture)")
            before = p.js("[...document.querySelectorAll('.secs > .sec[data-type=imagecap] > .sec-head')].length")
            p.edit()
            after = p.js("[...document.querySelectorAll('.secs > .sec[data-type=imagecap] > .sec-head')].map(h => getComputedStyle(h).display)")
            self.assertEqual(len(after), before, "Edit draws every heading it drew")
            self.assertNotIn("none", after)


if __name__ == "__main__":
    unittest.main()
