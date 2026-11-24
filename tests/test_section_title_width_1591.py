"""Row 1591 (v1.3 P0, Classic only): in Edit the section title box fills the heading row, stays on one line, never breaks inside a word.

Run: python3 dev/run_tests.py test_section_title_width_1591
Part 1 reads the stylesheets (no Chrome): the Classic rule is in rules-2.css before the Row 1314 block, Cards (shell.css) has none of it.
Part 2 is Chrome at 1400 and 900, light and dark, with the Classic theme layered; it needs Chrome (CLARK_CHROME).
"""
import re
import tempfile
import unittest

from _paths import ROOT
from test_server import chrome
from clark import page, theme
from _real_server import real_server
from test_report_editor import Base

RULES2 = (ROOT / "src" / "clark" / "themes" / "prototype-2.0" / "rules-2.css").read_text(encoding="utf-8")
SHELL = (ROOT / "src" / "clark" / "page" / "shell.css").read_text(encoding="utf-8")
BLOCK = RULES2[RULES2.index("/* Row 1591"):RULES2.index("/* Row 1314")]


class Sheets(unittest.TestCase):
    def test_the_rule_is_in_rules_2_before_row_1314_and_has_no_hex(self):
        self.assertLess(RULES2.index("/* Row 1591"), RULES2.index("/* Row 1314"))
        self.assertNotRegex(BLOCK, r"#[0-9a-fA-F]{3,6}\b")

    def test_the_box_fills_the_row_on_one_line_without_a_mid_word_break(self):
        rule = re.search(r"^\.sec-t > \.sec-title \{([^}]*)\}", BLOCK, re.M).group(1)
        for want in ("display: block", "width: 100%", "white-space: nowrap", "text-overflow: ellipsis", "overflow: hidden", "overflow-wrap: normal"):
            self.assertIn(want, rule)
        self.assertIn(".sec-t:has(> .sec-title) { display: block; }", BLOCK)

    def test_focused_the_text_is_not_cut(self):
        self.assertIn(".sec-t > .sec-title:focus { text-overflow: clip; }", BLOCK)

    def test_cards_stylesheet_has_none_of_it(self):
        self.assertNotIn("Row 1591", SHELL)
        self.assertNotIn("text-overflow", re.search(r"^\.sec-title \{[^}]*\}", SHELL, re.M).group(0))

    def test_row_1314_is_still_the_last_row_block(self):
        self.assertEqual(RULES2.rindex("/* Row "), RULES2.index("/* Row 1314"))


PROBE = r"""(() => [...document.querySelectorAll('.secs > .sec')].map((s) => {
  const t = s.querySelector('.sec-title'), h = s.querySelector('.sec-h'); if (!t || !h) return null;
  const r = t.getBoundingClientRect(), hr = h.getBoundingClientRect(), cs = getComputedStyle(t);
  const kids = [...s.querySelectorAll(':scope > .sec-head > .ask-about, :scope > .sec-head > .tag')].map((k) => k.getBoundingClientRect());
  return {id: s.dataset.id, w: r.width, left: r.left, right: r.right, hw: hr.width, hleft: hr.left, h: r.height,
          lh: parseFloat(cs.lineHeight) || parseFloat(cs.fontSize) * 1.3, ws: cs.whiteSpace, kids: kids.map((k) => [k.left, k.right])};
}).filter(Boolean))()"""


class Look(Base):
    def setUp(self):
        super().setUp()
        self.s.close()
        css = theme.css("prototype-2.0")
        self.s = real_server(self.store.path, self.store.data_for,
                             page_html=lambda: page.layer_theme(page.page_html(tempfile.mkdtemp()), css), seam=lambda real, which: real)
        self.addCleanup(self.s.close)

    def rows(self, cdp, p, width, scheme):
        cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme}]}, p.sid)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
        p.until(f"window.innerWidth === {width}", "resized")
        return p.js(PROBE)

    def each(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            for scheme in ("light", "dark"):
                for w in (1400, 900):
                    rows = self.rows(cdp, p, w, scheme)
                    self.assertTrue(rows)
                    for r in rows:
                        yield cdp, p, f"{w} px, {scheme}, {r['id']}", r


class SectionTitleWidth(Look):
    def test_the_title_field_fills_the_heading_row_of_every_section_kind(self):
        for _, _, where, r in self.each():
            self.assertGreaterEqual(r["w"], 0.8 * (r["hw"] - 8), f"{where}: {r}")

    def test_headline_and_milestones_are_on_one_line(self):
        for _, _, where, r in self.each():
            self.assertLess(r["h"], r["lh"] * 1.6, f"{where}: one line, {r}")
            self.assertEqual(r["ws"], "nowrap", where)

    def test_a_long_title_has_an_ellipsis_and_is_editable_to_its_end(self):
        for cdp, p, where, r in self.each():
            got = p.js("(() => { const t = document.querySelector('.sec-title'); const old = t.textContent; t.textContent = 'x'.repeat(80); const cs = getComputedStyle(t);"
                       " const o = {to: cs.textOverflow, over: t.scrollWidth > t.clientWidth, h: t.getBoundingClientRect().height}; t.textContent = old; return o; })()")
            self.assertEqual(got["to"], "ellipsis", where)
            self.assertTrue(got["over"], where)
            self.assertLess(got["h"], r["lh"] * 1.6, where)

    def test_a_short_title_starts_at_the_row_start_and_a_click_on_the_row_edits_it(self):
        for cdp, p, where, r in self.each():
            self.assertLessEqual(r["left"] - r["hleft"], 2, where)
            self.assertTrue(p.js("(() => { const t = document.querySelector('.sec-title'); const r = t.getBoundingClientRect();"
                                 " return document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2) === t; })()"), where)

    def test_a_half_width_box_is_the_half_and_nothing_overlaps_it(self):
        for _, _, where, r in self.each():
            for k in r["kids"]:
                self.assertLessEqual(r["right"], k[0] + 1, f"{where}: the box ends before {k}")
            self.assertLessEqual(r["right"], r["hleft"] + r["hw"] + 1, where)

    def test_typing_enter_and_esc_save_and_restore_as_before(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            before = self.titles_in_store()
            p.js("document.querySelector('.sec-title').focus(); document.execCommand('selectAll')")
            p.type("A renamed title")
            p.key("Escape", vk=27)
            p.until("document.querySelector('.sec-title').textContent !== 'A renamed title'", "Esc restores")
            self.assertEqual(self.titles_in_store(), before)
            p.js("document.querySelector('.sec-title').focus(); document.execCommand('selectAll')")
            p.type("A renamed title")
            p.key("Enter", vk=13)
            p.until("document.querySelector('.sec-title').textContent === 'A renamed title'", "Enter commits")


if __name__ == "__main__":
    unittest.main()
