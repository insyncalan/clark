"""Row 1178: the client published report's header matches the editor dashboard header option C: no 'for <client>' in the heading line
(file and editor), the date in the header is clickable (tooltip 'Click to change date', a click opens a calendar, same date format),
the header is 25 percent taller than the item 1146 bar and the logo 20 percent smaller (147x22 at 1400, 120x18 at 900), no published
chip or published-weeks list in the header (the published info is the last thing in the profile menu), search and ask clark first in the
menu where it has them, and no View/Edit pill in the client view. In a real browser.

Run: python3 dev/run_tests.py test_published_header_option_c        (needs Chrome; run only while the machine's load is under 70)
Computed style and DOM, at 1400 and 900 px, light and dark. Fictional data. Selectors are generic on purpose: they find the date, the
logo and the menu by what they say and do, not by a class the build has to use.
"""
import time
import unittest

from _demo import USER
from test_glance_page import Published, Setup
from test_report_editor import tearDownModule  # noqa: F401
from test_server import chrome

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
                want = 85 if width == 1400 else 125      # 68 and 100 px of item 1146, each plus 25 percent
                self.assertAlmostEqual(b["h"], want, delta=2, msg=f"the header is {b['h']} px, want about {want}")
                self.assertTrue(b["wide"], "no sideways scroll")

    def test_the_logo_is_20_percent_smaller(self):
        for width, dark in CASES:
            with self.subTest(width=width, dark=dark):
                cdp, p = self.bar(width, dark)
                b = p.js(PROBE)
                want = (147, 22) if width == 1400 else (120, 18)
                hit = [x for x in b["logoBoxes"] if abs(x["h"] - want[1]) <= 1]
                self.assertTrue(hit, f"some part of the logo (its box, icon, image or svg) is {want[0]}x{want[1]}: {b['logoBoxes']}")

    def test_the_date_is_clickable_with_a_tooltip_and_the_same_format(self):
        cdp, p = self.bar(1400, False)
        b = p.js(PROBE)
        d = b["date"]
        self.assertIsNotNone(d, "the date is shown in the header at 1400")
        self.assertRegex(d["text"], r"\b28-10-2026\b", "DD-MM-YYYY, as before")
        self.assertEqual(d["tip"], "Click to change date")
        self.assertIsNotNone(d["control"], "the date is a control (button, link or box), not plain text")
        self.assertTrue(d["tabbable"], "and reachable by keyboard")

    def test_a_click_on_the_date_opens_a_calendar(self):
        cdp, p = self.bar(1400, False)
        before = p.js(CAL)
        p.js("""(() => { const bar = document.querySelector('header.top'), re = /\\b\\d\\d-\\d\\d-\\d{4}\\b/;
          const el = [...bar.querySelectorAll('*')].filter((e) => re.test(e.textContent) && ![...e.children].some((c) => re.test(c.textContent)))
            .filter((e) => !e.closest('.top-line, .cover-line'))[0];
          (el.closest('button, a[href], [role=button], input, [tabindex]') || el).click(); })()""")
        time.sleep(0.4)
        after = p.js(CAL)
        opened = after["native"] or after["pops"] > before["pops"] or after["days"] >= 28
        self.assertTrue(opened, f"a calendar opened (before {before}, after {after})")

    def test_no_published_chip_or_weeks_list_in_the_header(self):
        for width, dark in CASES:
            with self.subTest(width=width, dark=dark):
                cdp, p = self.bar(width, dark)
                b = p.js(PROBE)
                self.assertNotRegex(b["barText"], r"(?i)published|past reports", "the header does not carry the published info")
                self.assertEqual(b["chips"], 0, "no chip in the header")

    def test_the_published_info_is_the_last_thing_in_the_profile_menu(self):
        for width, dark in CASES:
            with self.subTest(width=width, dark=dark):
                cdp, p = self.bar(width, dark)
                p.js("document.querySelector('.cm-badge, #client-menu-btn').click()")
                p.until("!!document.querySelector('[role=menu]')", "the menu opened")
                m = p.js(MENU)
                self.assertRegex(m["kids"][-1]["text"], r"(?i)as at|publish", f"the last part of the menu says it is published: {m['kids']}")
                self.assertGreaterEqual(m["kids"][-1]["bottom"], max(k["bottom"] for k in m["kids"]) - 0.5, "and sits at the bottom")
                self.assertEqual(sum(1 for k in m["kids"][:-1] if "publish" in k["text"].lower() and "export" not in k["text"].lower()), 0, "said once, at the bottom")

    def test_where_the_menu_has_search_and_ask_clark_they_come_first(self):
        """A client file has no search and no ask clark; if the build adds either to the menu, at 900 they are the first two."""
        for dark in (False, True):
            with self.subTest(dark=dark):
                cdp, p = self.bar(900, dark)
                p.js("document.querySelector('.cm-badge, #client-menu-btn').click()")
                p.until("!!document.querySelector('[role=menu]')", "the menu opened")
                items = [i.lower() for i in p.js(MENU)["items"]]
                found = [i for i in items if "search" in i or "ask clark" in i]
                for i in found:
                    self.assertLess(items.index(i), 2, f"{i!r} is among the first two items: {items}")

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
                line = p.js("(() => { const l = document.querySelector('header.cover .cover-line, header.top .top-line, .cover-line'); return l ? l.textContent : null; })()")
                self.assertIsNotNone(line, "the heading line is there")
                self.assertIn("WEEKLY REPORT", line.upper())
                self.assertNotIn(CLIENT, line)
                self.assertNotRegex(line, r"\bfor\b")


if __name__ == "__main__":
    unittest.main()
