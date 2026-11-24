"""Row 1592 (v1.3 P0, Classic only): a full width image section shows its heading (number and title) above the picture, in View.

Run: python3 dev/run_tests.py test_imagecap_heading_1592
Part 1 reads the stylesheets (no Chrome): the Classic rule is in rules-2.css before the Row 1314 block, the Cards rule in shell.css is as it was.
Part 2 is Chrome at 1400 and 900, light and dark, with the Classic theme layered; it needs Chrome (CLARK_CHROME). Fictional data only.
Left out of this row (Product Manager ruling, ticket comment): the per-section heading switch, row 1272. Also not tested: a section with no title (the store refuses a blank title, store.section_title raises Invalid for blank, so no such section exists; pinned by Sheets.test_a_section_with_no_title_cannot_exist).
Chrome could not run where this was written (no Chrome): the Chrome tests were reasoned from the render code and CSS, never run.
"""
import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from _demo import USER
from _paths import ROOT
from _pictures import data, png
from _real_server import real_server
from clark import page, publish, theme
from clark import store as store_module
from clark.section_kinds import imagecap as fi
from test_report_editor import Base
from test_server import chrome, wait
from test_work_items import page_target

RULES2 = (ROOT / "src" / "clark" / "themes" / "prototype-2.0" / "rules-2.css").read_text(encoding="utf-8")
SHELL = (ROOT / "src" / "clark" / "page" / "shell.css").read_text(encoding="utf-8")
BLOCK = RULES2[RULES2.index("/* Row 1592"):RULES2.index("/* Row 1314")]
CLASSIC_RULE = '.secs .sec[data-type="imagecap"] > .sec-head:has(~ .tpl-fullimg) { display: flex; }'
HIDE = '.sec[data-type="imagecap"] > .sec-head:has(~ .tpl-fullimg) { display: none; }'


class Sheets(unittest.TestCase):
    def test_the_rule_is_in_rules_2_before_row_1314_and_has_no_hex_or_px(self):
        """Mutant: rules-2.css, move the Row 1592 block below the Row 1314 comment (or add a color like #fff to it): red."""
        self.assertLess(RULES2.index("/* Row 1592"), RULES2.index("/* Row 1314"))
        code = re.sub(r"/\*.*?\*/", "", BLOCK, flags=re.S)
        self.assertNotRegex(code, r"#[0-9a-fA-F]{3,6}\b")
        self.assertNotRegex(code, r"\d\s*px")

    def test_the_classic_rule_shows_the_heading_and_is_stronger_than_the_hide_rule(self):
        """Mutant: rules-2.css line `.secs .sec[data-type=\"imagecap\"] ... { display: flex; }`: change `display: flex` to `display: none`, or drop the leading `.secs `: red."""
        rule = re.search(r"^(\.secs \.sec\[data-type=\"imagecap\"\] > \.sec-head:has\(~ \.tpl-fullimg\)) \{([^}]*)\}", BLOCK, re.M)
        self.assertIsNotNone(rule)
        self.assertEqual(rule.group(2).strip(), "display: flex;")
        # the same selector as the hide rule plus the .secs ancestor: one class more, so it wins whatever the order
        self.assertEqual(rule.group(1), ".secs " + HIDE.split(" {")[0])

    def test_cards_stylesheet_keeps_its_hide_rule_and_has_none_of_ours(self):
        """Mutant: shell.css:2319, delete the `.sec[data-type=\"imagecap\"] > .sec-head:has(~ .tpl-fullimg) { display: none; }` line (Cards would change): red."""
        self.assertIn(HIDE, SHELL)
        self.assertNotIn("Row 1592", SHELL)

    def test_the_view_switch_for_a_hidden_heading_is_untouched(self):
        """Mutant: shell.css:2068, delete the `#report[data-mode=\"view\"] .sec.no-head > .sec-head { position: absolute;` rule, or put `no-head` into the Row 1592 block: red."""
        self.assertIn('#report[data-mode="view"] .sec.no-head > .sec-head { position: absolute;', SHELL)
        self.assertNotIn("no-head", re.sub(r"/\*.*?\*/", "", BLOCK, flags=re.S))

    def test_the_published_file_gets_the_classic_layer_with_the_rule(self):
        """The published file is built by publish.build -> page.page_html(view=True, theme=theme_of(store)) -> layer_theme, so it carries <style id="theme"> with
        rules-2.css, and shell.css's hide rule is in it too (the layer is what overrides it). Local and To client write the same body bytes (publish_flow.py
        write_local(dest, body_bytes) and copy_to_client(..., body_bytes)).
        Mutant: src/clark/publish.py build(): pass `theme=None` to page.page_html (the file would lose the Classic layer and the heading would stay hidden): red."""
        text = page.page_html(view=True, theme=theme.CLASSIC)
        self.assertIn('<style id="theme">', text)
        self.assertIn(CLASSIC_RULE, text)
        self.assertIn(HIDE, text)
        self.assertGreater(text.index(CLASSIC_RULE), text.index('<style id="theme">'))

    def test_a_section_with_no_title_cannot_exist(self):
        """Mutant: src/clark/store.py section_title: delete the `if not title: raise Invalid` line (a blank title would then be stored) and this goes red."""
        for blank in ("", "   ", "\u200b"):
            with self.assertRaises(store_module.Invalid, msg=repr(blank)):
                store_module.section_title(blank)

    def test_row_1314_is_still_the_last_row_block(self):
        """Mutant: rules-2.css, add a `/* Row 1593` block after the Row 1314 block: red."""
        self.assertEqual(RULES2.rindex("/* Row "), RULES2.index("/* Row 1314"))


PROBE = r"""(() => {
  const secs = [...document.querySelectorAll('.secs > .sec')];
  return secs.map((s) => {
    const h = s.querySelector(':scope > .sec-head'), t = s.querySelector(':scope > .sec-head .sec-h'), pic = s.querySelector(':scope > .tpl-fullimg, :scope > .fi-stage');
    const hr = h && h.getBoundingClientRect(), pr = pic && pic.getBoundingClientRect(), sr = s.getBoundingClientRect();
    const body = h && h.nextElementSibling, br = body && body.getBoundingClientRect();
    return {id: s.dataset.id, type: s.dataset.type, slot: [...s.classList].find((c) => c.startsWith('slot-')), hidden: s.classList.contains('is-hidden'),
            head: !!h, display: h ? getComputedStyle(h).display : null, hw: hr ? hr.width : 0, hh: hr ? hr.height : 0,
            hbottom: hr ? hr.bottom : null, hleft: hr ? hr.left : null, hright: hr ? hr.right : null, ptop: pr ? pr.top : null, text: t ? t.textContent.trim() : '',
            before: h ? getComputedStyle(h, '::before').content : null, beforeDisplay: h ? getComputedStyle(h, '::before').display : null,
            inc: getComputedStyle(s).counterIncrement, reset: getComputedStyle(s).counterReset,
            sibling: !!s.querySelector(':scope > .sec-head ~ .tpl-fullimg'), hideRuleApplies: !!(h && h.matches('.sec[data-type="imagecap"] > .sec-head:has(~ .tpl-fullimg)')),
            left: sr.left, right: sr.right, gap: hr && br ? br.top - hr.bottom : null};
  });
})()"""

RAIL = "[...document.querySelectorAll('nav.cnt a[data-entry]')].length"
MINE = "Fictional image"
PARTNER = "Fictional partner"
TOL = 1     # px: the ticket (AP6) says "equals"; one pixel is the sub-pixel rounding of getBoundingClientRect


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
            made = st.create("report_sections", {"project": "ABC", "type": "imagecap", "title": title, "sort_order": 990, "beside": beside,
                                                 "body": store_module.check_section_body("imagecap", json.dumps(body))})
            if beside:      # a half only exists with a section after it to share the row
                st.create("report_sections", {"project": "ABC", "type": "text", "title": PARTNER, "sort_order": 991, "beside": 0,
                                              "body": store_module.check_section_body("text", json.dumps("Fictional words."))})
            return made

    def settle(self, cdp, p, width, scheme):
        cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme}]}, p.sid)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
        p.until(f"window.innerWidth === {width}", "resized")
        p.until("document.querySelector('.tpl-fullimg, .fi-stage')", "the image section is drawn")

    def rows(self, cdp, p, width, scheme):
        self.settle(cdp, p, width, scheme)
        return p.js(PROBE)

    def each(self, edit=False):
        with chrome() as cdp:
            p = self.visit(cdp)
            if edit:
                p.edit()
            for scheme in ("light", "dark"):
                for w in (1400, 900):
                    yield cdp, p, f"{w} px, {scheme}", self.rows(cdp, p, w, scheme)


def mine(rows, where):
    found = [r for r in rows if r["type"] == "imagecap" and r["text"] == MINE]
    assert len(found) == 1, f"{where}: the image section is in the page once, found {len(found)}"
    return found[0]


class ImagecapHeading(Look):
    def test_the_view_shows_the_heading_above_the_picture(self):
        """Mutant: rules-2.css, delete the Row 1592 rule line `.secs .sec[data-type="imagecap"] > .sec-head:has(~ .tpl-fullimg) { display: flex; }` (the heading is display:none again): red.
        Also red if src/clark/page/src/components/Section.jsx stops drawing the <header class="sec-head"> in View."""
        self.add(MINE)
        for _, _, where, rows in self.each():
            r = mine(rows, where)
            self.assertTrue(r["sibling"], f"{where}: the picture is drawn in the section (the hide rule would apply)")
            self.assertTrue(r["hideRuleApplies"], f"{where}: the heading is the one the hide rule in shell.css selects")
            self.assertNotEqual(r["display"], "none", where)
            self.assertGreater(r["hw"], 0, where)
            self.assertGreater(r["hh"], 0, where)
            self.assertLessEqual(r["hbottom"], r["ptop"], f"{where}: the heading ends above the picture")

    def test_a_half_width_image_shows_its_heading(self):
        """The image section is the left half of a row with a section after it (slot-left), it draws the .tpl-fullimg sibling the hide rule needs
        (ImageCap.jsx View draws <figure class="tpl-fullimg"> for a body of version 2 whatever the slot), so the hide rule applies to it.
        Renamed from ..._and_no_title_shows_none: a section with no title cannot exist (Sheets.test_a_section_with_no_title_cannot_exist).
        Mutant: rules-2.css, delete the Row 1592 rule line (display:none returns for the half too): red."""
        self.add(MINE, beside=1)
        for _, _, where, rows in self.each():
            r = mine(rows, where)
            self.assertEqual(r["slot"], "slot-left", f"{where}: it is a half width section")
            self.assertTrue(any(x["text"] == PARTNER and x["slot"] == "slot-right" for x in rows), f"{where}: its partner shares the row")
            self.assertTrue(r["sibling"], f"{where}: the .tpl-fullimg sibling exists, so the hide rule applies")
            self.assertTrue(r["hideRuleApplies"], where)
            self.assertNotEqual(r["display"], "none", where)
            self.assertGreater(r["hh"], 0, where)
            self.assertGreater(r["hw"], 0, where)
            self.assertGreaterEqual(r["hleft"], r["left"] - TOL, f"{where}: inside the half's box (left)")
            self.assertLessEqual(r["hright"], r["right"] + TOL, f"{where}: inside the half's box (right)")

    def test_the_numbers_are_continuous_and_the_rail_matches(self):
        """The number is the ::before of the heading, content counter(secn), and every .secs > .sec adds 1 (rules.css:8-11); Chrome gives the unresolved
        counter(secn) as the computed content, never the digit, so continuity 1..N with 0 skipped and 0 repeated is asserted from what makes the digit:
        each of the N sections draws its heading with a visible ::before whose content is counter(secn), adds exactly 1, and resets nothing; and the Contents
        rail (nav.cnt, row 1318) has N entries (it needs 2 or more sections; the demo has them, and a missing rail is a failure).
        Mutant: rules-2.css, delete the Row 1592 rule line (the image section's heading, and with it its ::before number, is display:none): red.
        Also red: rules.css:9 `.secs > .sec { counter-increment: secn; }` changed to `counter-increment: none`."""
        self.add(MINE)
        for _, p, where, rows in self.each():
            self.assertGreaterEqual(len(rows), 2, f"{where}: a page with a rail")
            n = len([r for r in rows if not r["hidden"]])
            self.assertEqual(n, len(rows), f"{where}: View draws no hidden section, so N is the number of sections drawn")
            for i, r in enumerate(rows, 1):
                self.assertTrue(r["head"], f"{where}: section {i} has its heading")
                self.assertNotEqual(r["display"], "none", f"{where}: section {i} ({r['type']}) draws its heading, so number {i} is not skipped")
                self.assertEqual(r["before"], "counter(secn)", f"{where}: section {i} draws its number")
                self.assertNotEqual(r["beforeDisplay"], "none", f"{where}: section {i}: the number is drawn")
                self.assertEqual(r["inc"], "secn 1", f"{where}: section {i} counts once (no repeat, no skip)")
                self.assertEqual(r["reset"], "none", f"{where}: section {i} does not restart the count")
            self.assertEqual(p.js(RAIL), n, f"{where}: the rail has one entry per section (a rail that is not drawn is 0, which fails)")

    def test_the_heading_spacing_matches_other_sections_and_edit_is_unchanged(self):
        """AP6: the gap between the heading's bottom and the picture's top (the section's next element) equals, within 1 px (the ticket says equals), the gap
        another section has between its heading and its body. Not a comparison of the heading's own computed values (those are the same when it is display:none).
        Edit: the image section draws the same heading it drew, never display none.
        Mutant: rules-2.css, change the Row 1592 rule body to `display: flex; margin-bottom: var(--space-8);` (the gap grows): red; deleting the rule line is red too (the heading is not drawn, height 0).
        """
        self.add(MINE)
        with chrome() as cdp:
            p = self.visit(cdp)
            for scheme in ("light", "dark"):
                for w in (1400, 900):
                    where = f"{w} px, {scheme}"
                    rows = self.rows(cdp, p, w, scheme)
                    r = mine(rows, where)
                    self.assertNotEqual(r["display"], "none", where)
                    self.assertGreater(r["hh"], 0, where)
                    others = [x["gap"] for x in rows if x["type"] != "imagecap" and x["head"] and x["display"] != "none" and x["gap"] is not None]
                    self.assertTrue(others, f"{where}: other sections to compare with")
                    self.assertTrue(any(abs(r["gap"] - g) <= TOL for g in others), f"{where}: heading to picture {r['gap']} px; other sections' heading to body: {others}")
            before = p.js("[...document.querySelectorAll('.secs > .sec[data-type=imagecap] > .sec-head')].length")
            p.edit()
            after = p.js("[...document.querySelectorAll('.secs > .sec[data-type=imagecap] > .sec-head')].map(h => getComputedStyle(h).display)")
            self.assertGreater(before, 0)
            self.assertEqual(len(after), before, "Edit draws every heading it drew")
            self.assertNotIn("none", after)


class Published(Base):
    """The published file, opened from disk. publish_flow writes the same body bytes to Local and (To client) copies them (write_local(dest, body_bytes),
    copy_to_client(..., body_bytes)), so the two modes are two files of one set of bytes, and both are opened."""

    def setUp(self):
        super().setUp()
        self.tmp = Path(tempfile.mkdtemp(prefix="clark-1592-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.add(MINE)

    add = Look.add

    def files(self):
        brand = Path(tempfile.mkdtemp(prefix="clark-no-brand-", dir=self.tmp))
        built = publish.build(self.store, "ABC", "2026-11-24", brand)
        self.assertIn(b'<style id="theme">', built["body"], "the file carries the Classic layer")
        out = {}
        for mode in ("local", "to client"):
            path = self.tmp / f"{mode.replace(' ', '-')}.html"
            path.write_bytes(built["body"])
            out[mode] = path
        return out

    def test_the_published_file_shows_the_heading_in_both_modes(self):
        """Mutant: src/clark/publish.py build(): pass `theme=None` to page.page_html (no Classic layer in the file, so shell.css:2319 hides the heading): red;
        also red if rules-2.css loses the Row 1592 rule line."""
        files = self.files()
        with chrome() as cdp:
            for mode, path in files.items():
                for scheme in ("light", "dark"):
                    for w in (1400, 900):
                        where = f"{mode}, {w} px, {scheme}"
                        sid = page_target(cdp)
                        cdp.call("Page.enable", {}, sid)
                        cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
                        cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme}]}, sid)
                        cdp.call("Page.navigate", {"url": path.as_uri()}, sid)
                        self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.secs .tpl-fullimg')", sid)), f"{where}: the image section drew")
                        rows = cdp.js(PROBE, sid)
                        r = mine(rows, where)
                        self.assertTrue(r["hideRuleApplies"], f"{where}: the hide rule would apply to this heading")
                        self.assertNotEqual(r["display"], "none", where)
                        self.assertGreater(r["hh"], 0, where)
                        self.assertGreater(r["hw"], 0, where)
                        self.assertLessEqual(r["hbottom"], r["ptop"], f"{where}: the heading ends above the picture")


if __name__ == "__main__":
    unittest.main()
