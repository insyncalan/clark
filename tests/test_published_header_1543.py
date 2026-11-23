"""Row 1543 PR 1 and PR 2a (the Classic header has no "As at"; read only) and 2b (the 32 px switcher and profile circle): the published header's pages group sits where the editor's does (same right edge, same line), and the room the
editor's right-hand buttons use is reserved, so the pages do not move between the two. In a real browser, light and dark, 1400 px,
and the 1200 and 1100 px edge checks (the 900 px bar is a later part of the row). Fictional data.

Run: python3 dev/run_tests.py test_published_header_1543        (needs Chrome; run only while the machine's load is under 70)
"""
from _demo import USER
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
# PR 2a: the bar's text and buttons, and what the editor draws that a file must not.
RIGHT = """(() => {
  const bar = document.querySelector('header.top'), b = bar.getBoundingClientRect(), st = (e, k) => getComputedStyle(e)[k];
  const box = (e) => { if (!e) return null; const r = e.getBoundingClientRect(); return {w: Math.round(r.width * 100) / 100, h: Math.round(r.height * 100) / 100, right: Math.round((b.right - r.right) * 100) / 100}; };
  const sw = bar.querySelector('.cm-theme'), me = bar.querySelector('.cm-badge, #profile-btn');
  return {text: bar.textContent, asatBtn: bar.querySelectorAll('.asat, .asat-wrap, .asat-box').length, week: !!/Week ending/.test(bar.textContent),
    sw: box(sw), me: box(me), swBorder: sw ? [st(sw, 'borderTopWidth'), st(sw, 'color')] : null, meBg: me ? st(me, 'backgroundColor') : null,
    meBorder: me ? st(me, 'borderTopWidth') : null, ask: bar.querySelectorAll('#ask-btn, .tb-ask, [aria-label*="Ask" i]').length,
    buttons: [...bar.querySelectorAll('button')].filter((x) => !x.classList.contains('tab') && !x.closest('.cm-wrap') && !x.closest('.logo')).length,
    eye: bar.querySelectorAll('.eye, [aria-label*="Client visible" i], [aria-label*="eye" i]').length, tools: bar.querySelectorAll('.tb-act, .hdr-end').length};
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
    def right_group(self, width, dark):
        with self.store.step("dashboard", USER) as st:
            st.update("projects", "ABC", {"week_ending": "2026-10-23"})
        path = self.publish()
        with chrome() as cdp:
            p = self.draw(cdp, path, width, dark)
            p.until("!!document.querySelector('header.top-file .cm-badge')", "the published bar drew")
            got = p.js(RIGHT)
            return got

    def test_published_header_no_as_at(self):
        for width, dark in ((1400, False), (1400, True), (900, False), (900, True)):
            with self.subTest(width=width, dark=dark):
                f = self.right_group(width, dark)
                self.assertNotIn("As at", f["text"], "no As at in the bar")
                self.assertEqual(f["asatBtn"], 0, "no date button, box or note in the bar")
                self.assertTrue(f["week"], "Week ending stays")

    def test_published_header_switcher_and_profile_sizes(self):
        for width, dark in ((1400, False), (1400, True), (900, False), (900, True)):
            with self.subTest(width=width, dark=dark):
                f = self.right_group(width, dark)
                self.assertEqual((f["sw"]["w"], f["sw"]["h"]), (32, 32), "the switcher is 32 px")
                self.assertEqual((f["me"]["w"], f["me"]["h"]), (32, 32), "the profile circle is 32 px")
                if width > 900:
                    self.assertEqual(f["me"]["right"], 28, "the circle ends at the bar's 28 px side, where the editor's does")
                self.assertEqual(f["swBorder"][0], "1px", "the switcher has the editor's button border")
                self.assertEqual(f["swBorder"][1], "rgb(255, 255, 255)", "and its white mark")
                self.assertEqual(f["meBg"], "rgb(56, 224, 238)", "the profile circle is filled, as the editor's")
                self.assertEqual(f["meBorder"], "2px", "with the editor's ring")

    def test_published_header_no_edit_controls(self):
        for width, dark in ((1400, False), (1400, True), (900, False), (900, True)):
            with self.subTest(width=width, dark=dark):
                f = self.right_group(width, dark)
                self.assertEqual((f["ask"], f["eye"], f["tools"]), (0, 0, 0), "no ask clark, no eye or Client visible, no editor tool")
                self.assertEqual(f["buttons"], 0, "the only buttons in the bar are the pages, the switcher and the profile circle")


for _name in dir(glance.Published):      # the base class's own tests are run in its own file
    if _name.startswith("test") and _name not in Header1543.__dict__:
        setattr(Header1543, _name, None)
