"""Row 1543 PR 1: the published header's pages group sits where the editor's does (same right edge, same line), and the room the
editor's right-hand buttons use is reserved, so the pages do not move between the two. In a real browser, light and dark, 1400 px,
and the 1200 and 1100 px edge checks (the 900 px bar is a later part of the row). Fictional data.

Run: python3 dev/run_tests.py test_published_header_1543        (needs Chrome; run only while the machine's load is under 70)
"""
import test_glance_page as glance
from test_report_editor import tearDownModule  # noqa: F401
from test_server import chrome

# The pages group and the bar: the group's gaps to the bar's right and bottom edges, each tab's left edge, and the right-hand group's box.
PROBE = """(() => {
  const bar = document.querySelector('header.top'), tabs = bar.querySelector('.tabs'), b = bar.getBoundingClientRect(), t = tabs.getBoundingClientRect();
  const q = (n) => Math.round(n * 100) / 100, end = bar.querySelector('.cm-wrap, .hdr-end'), e = end ? end.getBoundingClientRect() : null;
  const list = [...tabs.querySelectorAll('[role=tab]')].map((x) => x.getBoundingClientRect());
  return {gapRight: q(b.right - t.right), gapBottom: q(b.bottom - t.bottom), n: list.length, lefts: list.map((r) => q(r.left)), lastRight: q(list[list.length - 1].right),
    endRight: e ? q(b.right - e.right) : null, wide: document.documentElement.scrollWidth <= innerWidth};
})()"""
WIDTHS = ((1400, False), (1400, True), (1200, False), (1100, False))


class Header1543(glance.Published):
    def editor_bar(self, cdp, width, dark):
        p = self.show(cdp, width, dark)
        p.until("!!document.querySelector('header.top .tab')", "the editor's bar drew")
        return p.js(PROBE)

    def published_bar(self, width, dark, three=False):
        if three:      # a use case the client may not see: the file has no Use cases page
            self.store.con.execute("UPDATE use_cases SET client_visible = 0 WHERE project = 'ABC'")
            self.store.con.commit()
        path = self.publish()
        with chrome() as cdp:
            p = self.draw(cdp, path, width, dark)
            p.until("!!document.querySelector('header.top-file .tab')", "the published bar drew")
            return p.js(PROBE)

    def test_published_header_pages_same_right_edge_as_editor(self):
        for width, dark in WIDTHS:
            with self.subTest(width=width, dark=dark):
                with chrome() as cdp:
                    e = self.editor_bar(cdp, width, dark)
                f = self.published_bar(width, dark)
                self.assertEqual(f["n"], e["n"], "both bars show the same pages")
                self.assertAlmostEqual(f["gapRight"], e["gapRight"], delta=0.05, msg=f"published pages end {f['gapRight']} px from the bar's right edge, the editor's {e['gapRight']}")
                self.assertAlmostEqual(f["gapBottom"], e["gapBottom"], delta=0.05, msg=f"published pages end {f['gapBottom']} px above the bar's bottom, the editor's {e['gapBottom']}")
                for a, b in zip(f["lefts"], e["lefts"]):
                    self.assertAlmostEqual(a, b, delta=1.5, msg=f"the pages sit {f['lefts']} in the file, {e['lefts']} in the editor")
                self.assertTrue(f["wide"], "no sideways scroll")

    def test_published_header_pages_right_aligned_three_or_four(self):
        cases = ((1400, False), (1400, True), (1100, False))
        fours = {c: self.published_bar(*c) for c in cases}
        for width, dark in cases:
            with self.subTest(width=width, dark=dark):
                four = fours[(width, dark)]
                self.assertEqual(four["n"], 4)
                three = self.published_bar(width, dark, three=True)
                self.assertEqual(three["n"], 3, "a report with no Use cases page has three pages")
                self.assertEqual(three["gapRight"], four["gapRight"], "the pages group still ends at the same right edge")
                self.assertEqual(three["lastRight"], four["lastRight"], "its last page has not moved")
                self.assertEqual(three["endRight"], four["endRight"], "nothing to the right of the pages moved")
                self.assertGreater(three["lefts"][0], four["lefts"][0], "the group is shorter on its left")

    def probe_file(self, js, width, dark):
        path = self.publish()
        with chrome() as cdp:
            p = self.draw(cdp, path, width, dark)
            p.until("!!document.querySelector('header.top-file .tab')", "the published bar drew")
            return p.js(js)

    def test_published_header_no_as_at(self):
        head_js = """(() => ({head: document.querySelector('header.top').textContent,
          boxes: document.querySelectorAll('header.top .asat, header.top .asat-wrap, header.top button.asat, header.top input[type=date]').length}))()"""
        for width, dark in ((1400, False), (1400, True), (900, False), (900, True)):
            with self.subTest(width=width, dark=dark):
                path = self.publish()
                with chrome() as cdp:
                    p = self.draw(cdp, path, width, dark)
                    p.until("!!document.querySelector('header.top-file .tab')", "the published bar drew")
                    got = p.js(head_js)
                    p.js("document.querySelector('.cm-badge').click()")
                    p.until("!!document.querySelector('[role=menu]') && document.querySelector('[role=menu]').textContent.trim().length > 0", "the profile menu opened")
                    menu = p.js("document.querySelector('[role=menu]').textContent")
                self.assertGreater(len(menu.strip()), 0, "control: the menu was read after it drew")
                self.assertNotRegex(got["head"], r"(?i)as at", "no As at in the header")
                self.assertNotRegex(menu, r"(?i)as at", "no As at in the profile menu either")
                self.assertEqual(got["boxes"], 0)
                self.assertIn("Weekly report", got["head"], "the line under the project name stays (this fixture has no week ending date; the date text is unchanged)")

    def test_published_header_switcher_and_profile_sizes(self):
        """AP5, at 1400 and at 900, light and dark: the switcher is a bare icon (no fill, no border), the profile circle is filled with the brand cyan."""
        js = """(() => { const r = (s) => { const b = document.querySelector(s).getBoundingClientRect(); return [Math.round(b.width), Math.round(b.height), Math.round(document.querySelector("header.top").getBoundingClientRect().right - b.right)]; };
          const c = document.createElement('i'); c.style.background = 'var(--brand-cyan)'; document.body.appendChild(c);
          const cs = (s) => getComputedStyle(document.querySelector(s)), cyan = getComputedStyle(c).backgroundColor, t = cs('.cm-theme');
          return {theme: r('.cm-theme'), badge: r('.cm-badge'), cyan: cyan, badgeFill: cs('.cm-badge').backgroundColor, themeFill: t.backgroundColor,
                  themeBorder: parseFloat(t.borderTopWidth) + parseFloat(t.borderLeftWidth)}; })()"""
        for width, dark in ((1400, False), (1400, True), (900, False), (900, True)):
            with self.subTest(width=width, dark=dark):
                got = self.probe_file(js, width, dark)
                self.assertEqual(got["theme"][:2], [32, 32], "the light and dark button is 32 px (ticket AP5; 38 px is the editor's search button width)")
                self.assertEqual(got["badge"][:2], [32, 32], "the profile circle is 32 px")
                self.assertEqual(got["badgeFill"], got["cyan"], "the profile circle is filled with the brand cyan")
                self.assertIn(got["themeFill"], ("rgba(0, 0, 0, 0)", "transparent"), "the switcher is a bare icon: no fill")
                self.assertEqual(got["themeBorder"], 0, "the switcher has no border")
                if width == 1400:
                    self.assertEqual(got["badge"][2], 28, "the circle ends 28 px from the bar's right edge, as the editor's")

    def test_published_header_no_edit_controls(self):
        js = """(() => { const h = document.querySelector('header.top');
          return {n: h.querySelectorAll('.tb-ask, .tb-act, .hdr-end, .bell, [aria-label="Ask clark"], [aria-label="Client visible"]').length,
                  btns: [...h.querySelectorAll('button')].map((b) => b.className).sort()}; })()"""
        for width, dark in ((1400, False), (1400, True), (900, False), (900, True)):
            with self.subTest(width=width, dark=dark):
                got = self.probe_file(js, width, dark)
                self.assertEqual(got["n"], 0, f"no editor control in the published header: {got['btns']}")


for _name in dir(glance.Published):      # the base class's own tests are run in its own file
    if _name.startswith("test") and _name not in Header1543.__dict__:
        setattr(Header1543, _name, None)
