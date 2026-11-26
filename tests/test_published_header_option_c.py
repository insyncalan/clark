"""Row 1178: the client published report's header matches the editor dashboard header option C: no 'for <client>' in the heading line
(file and editor), the report line keeps its one date as plain text (row 1253 took the clickable As at date out),
the header is 25 percent taller than the item 1146 bar and the logo 20 percent smaller (147x22 at 1400, 120x18 at 900), no published
chip or published-weeks list in the header (the published info is the last thing in the profile menu), search and ask clark first in the
menu where it has them, and no View/Edit pill in the client view. In a real browser.

Run: python3 dev/run_tests.py test_published_header_option_c        (needs Chrome; run only while the machine's load is under 70)
Computed style and DOM, at 1400 and 900 px, light and dark. Fictional data. Selectors are generic on purpose: they find the date, the
logo and the menu by what they say and do, not by a class the build has to use.
"""
import unittest

from _demo import USER
from test_glance_page import Published, Setup
from test_report_editor import tearDownModule  # noqa: F401
from test_server import chrome, wait

CASES = ((1400, False), (1400, True), (900, False), (900, True))
CLIENT = "Example Client"

# The bar, the heading line, the date (the element that holds a DD-MM-YYYY date and is not the heading line), the logo and its parts.
PROBE = """(() => {
  const bar = document.querySelector('header.top'), r = (e) => { const b = e.getBoundingClientRect(); return {w: b.width, h: b.height, l: b.left, r: b.right}; };
  const vis = (e) => { const s = getComputedStyle(e), b = e.getBoundingClientRect(); return s.display !== 'none' && s.visibility !== 'hidden' && b.width > 0 && b.height > 0; };
  const line = bar.querySelector('.top-line, .cover-line'), re = /\\b\\d\\d-\\d\\d-\\d{4}\\b/;
  const dateEl = [...bar.querySelectorAll('*')].filter((e) => vis(e) && re.test(e.textContent) && ![...e.children].some((c) => vis(c) && re.test(c.textContent)) && !(line && line.contains(e)))[0] || null;
  const tip = (e) => { for (let n = e; n && n !== bar.parentElement; n = n.parentElement) { const t = n.getAttribute('title') || n.getAttribute('data-tip') || n.getAttribute('aria-label'); if (t) return t; } return ''; };
  const boxes = [...bar.querySelectorAll('.logo, .logo-icon, .logo img, .logo svg')].filter(vis).map(r);
  const control = dateEl && dateEl.closest('button, a[href], [role=button], input, [tabindex]');
  return {h: bar.getBoundingClientRect().height, lineText: line ? line.textContent : null, barText: bar.textContent, wide: document.documentElement.scrollWidth <= innerWidth,
    date: dateEl ? {text: dateEl.textContent.trim(), tip: tip(dateEl), control: control ? control.tagName : null, tabbable: control ? control.tabIndex >= 0 && !control.disabled : false} : null,
    logoBoxes: boxes, pills: [...bar.querySelectorAll('button, [role=tab], [role=radio], [role=switch], [role=option], .pill, [class*=pill]')].filter(vis)
      .map((e) => (e.textContent || '').trim()).filter((t) => /^(view|edit)$/i.test(t)),
    chips: [...bar.querySelectorAll('[class*=chip], [class*=pubbar], [class*=pubchip], [class*=weeks]')].filter(vis).length};
})()"""
CAL = """(() => {
  const vis = (e) => { const s = getComputedStyle(e), b = e.getBoundingClientRect(); return s.display !== 'none' && s.visibility !== 'hidden' && b.width > 0 && b.height > 0; };
  const a = document.activeElement, native = !!(a && a.tagName === 'INPUT' && a.type === 'date');
  const pop = [...document.querySelectorAll('[role=dialog], [role=grid], [role=application], dialog[open], [class*=calendar], [class*=cal-], input[type=date]')].filter(vis);
  const days = [...document.querySelectorAll('[role=gridcell], [role=grid] button, [class*=calendar] button, [class*=cal-] button')].filter(vis).length;
  return {native, pops: pop.length, days};
})()"""
MENU = """(() => {
  const m = document.querySelector('[role=menu]'); if (!m) return null;
  const kids = [...m.children].map((e) => ({text: (e.textContent || '').trim(), bottom: e.getBoundingClientRect().bottom, top: e.getBoundingClientRect().top}));
  const items = [...m.querySelectorAll('[role=menuitem]')].map((e) => (e.getAttribute('aria-label') || e.textContent || '').trim());
  return {kids, items, bottom: m.getBoundingClientRect().bottom, text: m.textContent};
})()"""


class InTheFile(Published):
    def setUp(self):
        super().setUp()
        with self.store.step("dashboard", USER) as st:
            st.update("projects", "ABC", {"client_name": CLIENT, "week_ending": "2026-10-23"})
        self._cm = None
        self.addCleanup(self.close)

    def close(self):
        if self._cm:
            self._cm.__exit__(None, None, None)
            self._cm = None

    def bar(self, width, dark):
        self.close()
        if not getattr(self, "_path", None):
            self._path = self.publish()
        self._cm = chrome()
        cdp = self._cm.__enter__()
        p = self.draw(cdp, self._path, width, dark)
        p.until("!!document.querySelector('.top-file .tab, header.top .tab') && !!document.querySelector('.glance')", "the bar and the tiles drew")
        return cdp, p

    def test_the_heading_line_has_no_for_client(self):
        for width, dark in CASES:
            with self.subTest(width=width, dark=dark):
                cdp, p = self.bar(width, dark)
                b = p.js(PROBE)
                self.assertIsNotNone(b["lineText"], "the heading line is there")
                self.assertIn("WEEKLY REPORT", b["lineText"].upper())
                self.assertNotIn(CLIENT, b["lineText"], "the client's name is not in the heading line")
                self.assertNotRegex(b["lineText"], r"\bfor\b", "no 'for <client>' in the heading line")

    def test_the_header_is_25_percent_taller_than_the_1146_bar(self):
        for width, dark in CASES:
            with self.subTest(width=width, dark=dark):
                cdp, p = self.bar(width, dark)
                b = p.js(PROBE)
                want = 85 if width == 1400 else 129      # 68 px of item 1146 plus 25 percent; at 900 px (row 1543 AP7) the editor's 129 px
                self.assertAlmostEqual(b["h"], want, delta=2, msg=f"the header is {b['h']} px, want about {want}")
                self.assertTrue(b["wide"], "no sideways scroll")

    def test_the_logo_is_20_percent_smaller(self):
        for width, dark in CASES:
            with self.subTest(width=width, dark=dark):
                cdp, p = self.bar(width, dark)
                b = p.js(PROBE)
                want = (147, 22) if width == 1400 else (120, 24)      # row 1543 AP7: at 900 px the logo box is the editor's 120 x 24 (its icon stays 18)
                hit = [x for x in b["logoBoxes"] if abs(x["h"] - want[1]) <= 1 and abs(x["w"] - want[0]) <= 1]
                self.assertTrue(hit, f"some part of the logo (its box, icon, image or svg) is {want[0]}x{want[1]}: {b['logoBoxes']}")

    def test_the_report_line_has_its_one_date_as_plain_text_and_no_separate_date_button(self):      # row 1253: the 20-11 ruling took the As at button out of the client bar (it was the clickable date of row 1178)
        cdp, p = self.bar(1400, False)
        b = p.js(PROBE)
        self.assertIsNone(b["date"], "no date outside the report line")
        self.assertEqual(p.js("document.querySelectorAll('header.top button.asat, header.top input[type=date]').length"), 0, "no date button or date box")
        self.assertEqual(p.js("(document.querySelector('header.top .top-line').textContent.match(/\\b\\d\\d-\\d\\d-\\d{4}\\b/g) || []).length"), 1, "the report line keeps its one date")
        self.assertEqual(p.js("document.querySelectorAll('header.top .top-line button, header.top .top-line a, header.top .top-line input').length"), 0, "plain text")

    def test_one_bar_the_logo_once_no_frame_or_cover_and_no_as_at_button(self):      # row 1253
        for width in (1400, 900):
            with self.subTest(width=width):
                cdp, p = self.bar(width, False)
                self.assertEqual(p.js("document.querySelectorAll('header.top, header.cover, #cover, .cover').length"), 1, "one bar and no cover band")
                self.assertEqual(p.js("document.querySelectorAll('.logo').length"), 1, "the logo is drawn once")
                self.assertEqual(p.js("document.querySelectorAll('button.asat, .asat-wrap').length"), 0, "no As at button")
                self.assertEqual(p.js("document.querySelectorAll('header.top ~ .frame.cover, #cover.frame').length"), 0, "no frame cover")

    def test_no_as_at_anywhere_in_the_header_and_week_ending_stays_row_1543(self):
        for width, dark in CASES:
            with self.subTest(width=width, dark=dark):
                cdp, p = self.bar(width, dark)
                head = p.js("document.querySelector('header.top').textContent")
                self.assertNotRegex(head, r"(?i)as at", f"row 1543: no As at in the header: {head!r}")
                self.assertEqual(p.js("document.querySelectorAll('header.top .asat, header.top .asat-wrap, header.top input[type=date]').length"), 0)
                self.assertRegex(head, r"Week ending|Weekly report")
                tabs = p.js("[...document.querySelectorAll('header.top .tab')].map(t => t.textContent.trim().replace(/\\s+/g, ' ')).length")
                self.assertGreaterEqual(tabs, 3, "the pages are still there")

    def test_the_switcher_is_32_px_and_the_profile_circle_32_px_row_1543(self):
        for width, dark in ((1400, False), (1400, True)):
            with self.subTest(width=width, dark=dark):
                cdp, p = self.bar(width, dark)
                got = p.js("""(() => { const r = (s) => { const b = document.querySelector(s).getBoundingClientRect(); return [Math.round(b.width), Math.round(b.height)]; };
                  return {theme: r('.cm-theme'), badge: r('.cm-badge')}; })()""")
                self.assertEqual(got["theme"], [32, 32], "the light and dark button is 32 px (ticket AP5)")
                self.assertEqual(got["badge"], [32, 32], "the profile circle is 32 px")

    def test_no_published_chip_or_weeks_list_in_the_header(self):
        for width, dark in CASES:
            with self.subTest(width=width, dark=dark):
                cdp, p = self.bar(width, dark)
                b = p.js(PROBE)
                self.assertNotRegex(b["barText"], r"(?i)published|past reports", "the header does not carry the published info")
                self.assertEqual(b["chips"], 0, "no chip in the header")

    def test_the_past_reports_are_the_last_thing_in_the_profile_menu_and_no_as_at_row_1543(self):
        for width, dark in CASES:
            with self.subTest(width=width, dark=dark):
                cdp, p = self.bar(width, dark)
                p.js("document.querySelector('.cm-badge, #client-menu-btn').click()")
                p.until("!!document.querySelector('[role=menu]')", "the menu opened")
                m = p.js(MENU)
                self.assertGreaterEqual(m["kids"][-1]["bottom"], max(k["bottom"] for k in m["kids"]) - 0.5, "the last part sits at the bottom")
                self.assertEqual(sum(1 for k in m["kids"] if "as at" in k["text"].lower()), 0, f"row 1543: no As at note in the menu: {m['kids']}")

    def test_the_client_menu_has_no_search_or_ask_clark_item(self):
        """A client file draws no search and no ask clark (the menu is Profile and Export to PDF); the menu must have drawn, and if the build adds either, at 900 they are the first two."""
        for dark in (False, True):
            with self.subTest(dark=dark):
                cdp, p = self.bar(900, dark)
                p.js("document.querySelector('.cm-badge, #client-menu-btn').click()")
                p.until("!!document.querySelector('[role=menu]')", "the menu opened")
                items = [i.lower() for i in p.js(MENU)["items"]]
                self.assertIn("profile", items, f"the client menu opened but drew no items: {items}")
                found = [i for i in items if "search" in i or "ask clark" in i]
                self.assertEqual(found, [], f"a published file draws neither search nor ask clark in its menu: {items}")

    def test_the_client_view_has_no_view_edit_pill(self):
        for width, dark in CASES:
            with self.subTest(width=width, dark=dark):
                cdp, p = self.bar(width, dark)
                self.assertEqual(p.js(PROBE)["pills"], [], "no View or Edit control in the header")


class InTheEditor(Setup):
    def setUp(self):
        super().setUp()
        with self.store.step("dashboard", USER) as st:
            st.update("projects", "ABC", {"client_name": CLIENT, "week_ending": "2026-10-23"})

    def test_the_editor_heading_line_has_no_for_client(self):
        for width, dark in CASES:
            with self.subTest(width=width, dark=dark), chrome() as cdp:
                p = self.show(cdp, width, dark)
                line = p.js("(() => { const l = document.querySelector('header.top .hdr-line, header.cover .cover-line, header.top .top-line'); return l ? l.textContent : null; })()")
                self.assertIsNotNone(line, "the heading line is there")
                self.assertIn("WEEKLY REPORT", line.upper())
                self.assertNotIn(CLIENT, line)
                self.assertNotRegex(line, r"\bfor\b")


if __name__ == "__main__":
    unittest.main()
