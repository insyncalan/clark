"""Row 1591 (v1.3 P0, Classic only): in Edit the section title box fills the heading row, stays on one line, never breaks inside a word.

Run: python3 dev/run_tests.py test_section_title_width_1591
Part 1 reads the stylesheets (no Chrome): the Classic rule is in rules-2.css before the Row 1314 block, Cards (shell.css) has none of it.
Part 2 is Chrome at 1400 and 900, light and dark, with the Classic theme layered; it needs Chrome (CLARK_CHROME).
"""
import re
import tempfile
import time
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
        for want in ("vertical-align: top", "width: 100%", "white-space: nowrap", "text-overflow: ellipsis", "overflow: hidden", "overflow-wrap: normal"):
            self.assertIn(want, rule)
        self.assertIn(".sec-t:has(> .sec-title) { width: 100%; }", BLOCK)
        self.assertNotIn("display: block", BLOCK)   # the title and its .sec-t stay inline-block: a block title changes the head's line height and moves the .tpl-icons offset

    def test_focused_the_text_is_not_cut(self):
        self.assertIn(".sec-t > .sec-title:focus { text-overflow: clip; }", BLOCK)

    def test_cards_stylesheet_has_none_of_it(self):
        self.assertNotIn("Row 1591", SHELL)
        self.assertNotIn("text-overflow", re.search(r"^\.sec-title \{[^}]*\}", SHELL, re.M).group(0))

    def test_no_other_rule_sets_white_space_on_the_title_and_ours_is_the_only_one_that_can_win(self):
        # Cascade pin (no Chrome): every white-space rule whose selector can reach .sec-title, across shell.css, edit.css and the Classic layer.
        # Only ours (two classes, in rules-2.css, layered after shell.css) may set it; the title span is contenteditable="plaintext-only",
        # for which Chrome itself turns the computed value of nowrap into pre (still no wrap), so the browser test accepts both.
        sheets = [SHELL, (ROOT / "src" / "clark" / "page" / "src" / "edit" / "edit.css").read_text(encoding="utf-8"),
                  (ROOT / "src" / "clark" / "themes" / "prototype-2.0" / "rules.css").read_text(encoding="utf-8"), RULES2]
        hits = []
        for css in sheets:
            for sel, body in re.findall(r"([^{}]+)\{([^{}]*)\}", re.sub(r"/\*.*?\*/", "", css, flags=re.S)):
                if re.search(r"(^|[\s,>])(\.sec-title\b|\.sec-t\b|span\b|\[data-title\]|\[contenteditable)", sel.strip().split(",")[0]) and "sec-title" in sel and "white-space" in body:
                    hits.append(sel.strip())
        self.assertEqual(hits, [".sec-t > .sec-title"])

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
            self.assertIn(r["ws"], ("nowrap", "pre"), where)      # the title span is contenteditable="plaintext-only": Chrome computes nowrap as pre there; neither wraps (the ticket asks for one line, no value)

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
            self.assertGreaterEqual(r["w"], 0.8 * (r["hw"] - 8), f"{where}: the box fills its half-row (not just stays inside it) {r}")

    def test_the_sweep_line_under_the_title_is_as_wide_as_the_title_text_while_the_box_fills_the_row(self):
        # Row 1408 x 1591: .sec-t is as wide as the heading row, but its ::after (the sweep line) is sized by the text copy in data-t.
        for cdp, p, where, r in self.each():
            got = p.js("(() => { const s = document.querySelector('[data-id=\"' + %r + '\"]'), t = s.querySelector('.sec-title'), st = s.querySelector('.sec-t'),"
                       " g = document.createRange(); g.selectNodeContents(t); return {text: g.getBoundingClientRect().width, after: parseFloat(getComputedStyle(st, '::after').width),"
                       " box: st.getBoundingClientRect().width, title: t.getBoundingClientRect().width, mirror: st.getAttribute('data-t'), want: t.textContent}; })()" % r["id"])
            self.assertEqual(got["mirror"], got["want"], where)
            self.assertAlmostEqual(got["after"], got["text"], delta=1, msg=f"{where}: line {got['after']} vs text {got['text']}")
            self.assertGreaterEqual(got["box"], 0.8 * (r["hw"] - 8), where)
            self.assertGreaterEqual(got["title"], 0.8 * (r["hw"] - 8), where)
            self.assertGreater(got["box"], got["after"] + 100, where)

    def test_the_copy_follows_typing(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            p.js("document.querySelector('.sec-title').focus(); document.execCommand('selectAll')")
            p.type("Hello there")
            self.assertEqual(p.js("document.querySelector('.sec-title').parentElement.getAttribute('data-t')"), "Hello there")
            p.key("Escape", vk=27)
            p.until("document.querySelector('.sec-title').parentElement.getAttribute('data-t') !== 'Hello there'", "Esc restores the copy")

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
            for _ in range(100):                      # Enter blurs the box, the blur saves: the store holds the new title
                if self.titles_in_store()[0] == "A renamed title":
                    break
                time.sleep(0.1)
            self.assertEqual(self.titles_in_store()[0], "A renamed title", "Enter saved the title to the store")
            self.assertNotEqual(p.js("document.activeElement === document.querySelector('.sec-title')"), True, "Enter left the box")


TITLE = "document.querySelector('[data-id=\"%s\"] .sec-title')"


class SectionTitleBrowser(Look):
    """Row 1591 done-check gaps (26-11): the pins a done-check asked for, run in Chrome at 1400 and 900 (the Classic theme layered)."""

    def widths(self, cdp, p):
        for w in (1400, 900):
            self.rows(cdp, p, w, "light")
            yield w

    def ids(self, p):
        return p.js("[...document.querySelectorAll('.secs > .sec')].filter((s) => s.querySelector('.sec-title')).map((s) => s.dataset.id)")

    def click_at(self, p, x, y):
        p.mouse("mousePressed", x, y, buttons=1)
        p.mouse("mouseReleased", x, y)

    def test_ap3_a_focused_long_title_scrolls_to_its_end_and_the_caret_stays_in_the_box(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            for w in self.widths(cdp, p):
                sid = self.ids(p)[0]
                t = TITLE % sid
                p.js(f"(() => {{ const t = {t}; t.focus(); document.execCommand('selectAll'); }})()")
                p.type("w" * 90 + " END")
                p.key("Home", code="Home", vk=36)
                home = p.js(f"{t}.scrollLeft")                 # a few px of padding may remain at the start
                p.key("End", code="End", vk=35)
                got = p.js(f"(() => {{ const t = {t}, cs = getComputedStyle(t), b = t.getBoundingClientRect(), g = getSelection().getRangeAt(0).cloneRange();"
                           " g.collapse(false); const c = g.getClientRects()[0] || g.getBoundingClientRect();"
                           " return {focus: document.activeElement === t, to: cs.textOverflow, over: t.scrollWidth > t.clientWidth, sl: t.scrollLeft,"
                           " caretIn: c.right <= b.right + 1 && c.left >= b.left - 1, text: t.textContent, h: b.height}; })()")
                self.assertTrue(got["focus"], w)
                self.assertEqual(got["to"], "clip", f"{w}: focused, no ellipsis")
                self.assertTrue(got["over"], w)
                self.assertGreater(got["sl"], home + 20, f"{w}: End scrolled the box to the end of the text, Home was at {home}")
                self.assertTrue(got["caretIn"], f"{w}: the caret at the end is inside the box {got}")
                self.assertTrue(got["text"].endswith(" END"), w)
                p.type("!")
                self.assertTrue(p.js(f"{t}.textContent.endsWith('END!')"), f"{w}: typed at the end")
                p.key("Escape", code="Escape", vk=27)
                p.until(f"!{t}.textContent.endsWith('END!')", "Esc restores")
                self.assertEqual(p.js(f"getComputedStyle({t}).textOverflow"), "ellipsis", f"{w}: unfocused again")

    def test_ap4_a_click_on_every_title_row_puts_the_caret_in_that_title(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            for w in self.widths(cdp, p):
                for sid in self.ids(p):
                    t = TITLE % sid
                    p.js(f"{t}.scrollIntoView({{block: 'center'}}); document.activeElement.blur()")
                    for frac in (0.02, 0.5, 0.9):               # 2%, 50% and 90% of the heading row (the box must fill it)
                        p.js("document.activeElement.blur()")
                        r = p.js(f"(() => {{ const b = {t}.closest('.sec-h').getBoundingClientRect(), k = {t}.getBoundingClientRect(); return [b.left + b.width * {frac}, k.top + k.height / 2]; }})()")      # x from the heading row, not the box: with the box as narrow as its text a point on the row misses it
                        self.assertTrue(p.js(f"document.elementFromPoint({r[0]}, {r[1]}) === {t}"), f"{w} {sid} {frac}: the point on the heading row is on the title box")
                        self.click_at(p, r[0], r[1])
                        p.until(f"document.activeElement === {t}", f"{w} {sid} {frac}: the click focused that title")

    def test_ap5_a_half_width_section_title_is_its_half_and_the_pair_do_not_overlap(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            p.menu("ABC-S-002", "beside")
            p.until("document.querySelector('[data-id=\"ABC-S-002\"]').classList.contains('slot-left')", "beside")
            for w in self.widths(cdp, p):
                pair = p.js("(() => { const l = document.querySelector('.sec.slot-left'), r = document.querySelector('.sec.slot-right');"
                            " const box = (s) => { const t = s.querySelector('.sec-title'), h = s.querySelector('.sec-h'), tr = t.getBoundingClientRect(), hr = h.getBoundingClientRect();"
                            " return {id: s.dataset.id, l: tr.left, r: tr.right, w: tr.width, hl: hr.left, hr: hr.right, hw: hr.width, sec: s.getBoundingClientRect().width}; };"
                            " return l && r ? [box(l), box(r)] : null; })()")
                self.assertIsNotNone(pair, f"{w}: a half-width pair is drawn")
                a, b = pair
                if w == 1400:
                    self.assertLess(a["sec"], 0.6 * 1400, f"{w}: the section is a half {a}")
                    self.assertLessEqual(a["r"], b["l"] + 1, f"{w}: the left title ends before the right title starts {pair}")
                self.assertGreaterEqual(a["w"], 0.8 * (a["hw"] - 8), f"{w}: left box fills its heading row {a}")
                self.assertGreaterEqual(b["w"], 0.8 * (b["hw"] - 8), f"{w}: right box fills its heading row {b}")
                for x in (a, b):
                    self.assertLessEqual(x["r"], x["hr"] + 1, f"{w}: box inside its row {x}")
                    self.assertLessEqual(x["w"], x["sec"], f"{w}: box inside its section {x}")

    def test_ap6_tab_reaches_the_title_box_and_enter_saves_it_in_the_store(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            for w in self.widths(cdp, p):
                sid = self.ids(p)[0]
                t = TITLE % sid
                p.js("document.activeElement.blur(); window.scrollTo(0, 0)")
                seen = False
                for _ in range(60):
                    p.key("Tab", code="Tab", vk=9)
                    if p.js(f"document.activeElement === {t}"):
                        seen = True
                        break
                self.assertTrue(seen, f"{w}: Tab reaches the title box of {sid}")
                self.assertEqual(p.js(f"getComputedStyle({t}).textOverflow"), "clip", f"{w}: focused by Tab")
                p.js("document.execCommand('selectAll')")
                new = f"Tabbed in {w}"
                p.type(new)
                p.key("Enter", code="Enter", vk=13)
                p.until(f"{t}.textContent === {new!r}", "Enter commits")
                p.until(f"document.activeElement !== {t}", "Enter leaves the box")
                for _ in range(100):                      # the save goes to the store after the field shows the text
                    if self.titles_in_store()[0] == new:
                        break
                    time.sleep(0.1)
                self.assertEqual(self.titles_in_store()[0], new, f"{w}: the store holds it: {self.titles_in_store()}")


if __name__ == "__main__":
    unittest.main()
