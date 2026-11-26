"""Row 1543 PR 1: the published header's pages group sits where the editor's does (same right edge, same line), and the room the
editor's right-hand buttons use is reserved, so the pages do not move between the two. In a real browser, light and dark, 1400 px,
and the 1200 and 1100 px edge checks (the 900 px bar: AP7 below). Fictional data.

Run: python3 dev/run_tests.py test_published_header_1543        (needs Chrome; run only while the machine's load is under 70)
"""
import base64
import json

import _backdrop_pics as pics
import test_glance_page as glance
from test_published_one_bar import HIDE, colour, ratio
from test_report_editor import tearDownModule  # noqa: F401
from test_server import chrome
from _classic_page import classic

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


NAME_PROBE = """(() => {
  const bar = document.querySelector('header.top'), n = bar.querySelector('#project-name'), b = bar.getBoundingClientRect(), r = n.getBoundingClientRect(), cs = getComputedStyle(n);
  const id = n.closest('.top-id, .hdr-id').getBoundingClientRect();
  return {name: n.textContent, barW: Math.round(b.width), barH: Math.round(b.height), nameW: Math.round(r.width), idW: Math.round(id.width), nameH: Math.round(r.height), lh: parseFloat(cs.lineHeight) || parseFloat(cs.fontSize) * 1.2,
    ws: cs.whiteSpace, tov: cs.textOverflow, ov: cs.overflow, cut: n.scrollWidth > n.clientWidth, title: n.getAttribute('title') || (n.firstElementChild && n.firstElementChild.getAttribute('title')) || ''};
})()"""
STRIP_PROBE = """(() => {
  const bar = document.querySelector('header.top'), tabs = bar.querySelector('.tabs'), b = bar.getBoundingClientRect(), t = tabs.getBoundingClientRect(), logo = bar.querySelector('.logo').getBoundingClientRect();
  const q = (n) => Math.round(n * 10) / 10, first = tabs.querySelector('[role=tab]').getBoundingClientRect(), cs = getComputedStyle(tabs);
  return {barH: q(b.height), tabsTop: q(t.top - b.top), tabsH: q(t.height), tabsLeft: q(t.left - b.left), tabsW: q(t.width), firstLeft: q(first.left - b.left), border: cs.borderTopWidth, logoTop: q(logo.top - b.top), logoLeft: q(logo.left - b.left), idLeft: q(bar.querySelector('.top-id, .hdr-id').getBoundingClientRect().left - b.left),
    search: bar.querySelectorAll('[aria-label="Go to or do"]').length, wide: document.documentElement.scrollWidth <= innerWidth};
})()"""


ROW_PROBE = """(() => {
  const bar = document.querySelector('header.top'), tabs = bar.querySelector('.tabs'), b = bar.getBoundingClientRect(), t = tabs.getBoundingClientRect(), cs = getComputedStyle(bar);
  const id = bar.querySelector('.top-id, .hdr-id').getBoundingClientRect(), q = (n) => Math.round(n * 10) / 10;
  return {barH: q(b.height), display: cs.display, wrap: cs.flexWrap, tabsTop: q(t.top - b.top), tabsH: q(t.height), border: getComputedStyle(tabs).borderTopWidth,
    inline: t.top >= b.top && t.bottom <= b.bottom && t.left >= id.right - 0.5 && id.top < t.bottom && id.bottom > t.top,
    search: bar.querySelectorAll('[aria-label="Go to or do"]').length, wide: document.documentElement.scrollWidth <= innerWidth};
})()"""


class Ap7:      # mixed into Header1543 below
    LONG_NAME = "A very long programme name that goes on and on and on for the whole line and beyond"

    def test_published_header_project_name_one_line(self):
        self.store.con.execute("UPDATE projects SET name = ? WHERE code = 'ABC'", (self.LONG_NAME,))
        self.store.con.commit()
        for width, dark in ((1400, False), (1400, True), (900, False), (900, True)):
            with self.subTest(width=width, dark=dark):
                got = self.probe_file(NAME_PROBE, width, dark)
                self.assertEqual(got["name"], self.LONG_NAME, "control: the long name is the one drawn")
                self.assertLess(got["nameH"], got["lh"] * 1.5, f"the name is one line ({got['nameH']} px high, a line is {got['lh']})")
                self.assertEqual((got["ws"], got["tov"], got["ov"]), ("nowrap", "ellipsis", "hidden"), "cut with an ellipsis")
                self.assertTrue(got["cut"], "the long name does not fit, so it is cut")
                self.assertLessEqual(got["idW"], got["barW"] * 0.5, "the name box stops at the editor's cap of half the bar (row 1305)")
                self.assertEqual(got["title"], self.LONG_NAME, "its tooltip still names it")

    def test_published_header_name_cap_is_the_editors(self):
        """A GUARD, not a proof of a change: the name box cap of the published bar is the editor header's, read from the computed style (the cap does not bind at 1400 or 900, so the width alone cannot show it). Both bars take the one rule `.hdr-id, .top-id { max-width: 50% }` (rules.css, row 1305), so this passes with the Row 1543 AP7 CSS reverted; the 900 px layout is pinned by test_published_header_900px_follows_editor."""
        probe = "(() => { const n = document.querySelector('header.top #project-name').closest('.top-id, .hdr-id'); const cs = getComputedStyle(n); return {cls: n.className, max: cs.maxWidth}; })()"
        classic(self)      # the editor in the Classic look, the one the file is drawn in
        for width, dark in ((1400, False), (900, False), (1400, True), (900, True)):
            with self.subTest(width=width, dark=dark):
                with chrome() as cdp:
                    p = self.show(cdp, width, dark)
                    p.until("!!document.querySelector('header.top .tab')", "the editor's bar drew")
                    e = p.js(probe)
                f = self.probe_file(probe, width, dark)
                self.assertIn("hdr-id", e["cls"], "control: the editor's name box")
                self.assertIn("top-id", f["cls"], "control: the file's name box")
                self.assertEqual(f["max"], e["max"], f"name cap: the file {f['max']}, the editor {e['max']}")
                self.assertEqual(e["max"], "50%", "the editor's code value (rules.css row 1305: .hdr-id, .top-id max-width 50%)")

    def test_published_header_900px_follows_editor(self):
        """AP7 (review ruling): at 900 px the published header follows the CLASSIC editor's bar (rules.css 900 px block: a flex row 103 px high, the pages inline in the same row, no strip and no line above the pages). The file is always Classic, so the editor here is Classic too. 1400 px: the file's bar is the editor's (85 px, flex, pages inline)."""
        classic(self)
        for width, high in ((900, 103), (1400, 85)):
            for dark in (False, True):
                with self.subTest(width=width, dark=dark):
                    with chrome() as cdp:
                        p = self.show(cdp, width, dark)
                        p.until("!!document.querySelector('header.top .tab')", "the editor's bar drew")
                        e = p.js(ROW_PROBE)
                    f = self.probe_file(ROW_PROBE, width, dark)
                    for name, got in (("editor", e), ("file", f)):
                        self.assertAlmostEqual(got["barH"], high, delta=1, msg=f"the {name}'s bar is {got['barH']} px high, not {high}")
                        self.assertEqual(got["display"], "flex", f"the {name}'s bar is a flex row")
                        self.assertEqual(got["wrap"], "nowrap", f"the {name}'s bar does not wrap")
                        self.assertTrue(got["inline"], f"the {name}'s pages are inside the bar's box, in its one row: {got}")
                        self.assertEqual(got["border"], "0px", f"the {name}'s pages have no line above them (no strip)")
                    self.assertAlmostEqual(f["barH"], e["barH"], delta=1)
                    self.assertAlmostEqual(f["tabsTop"], e["tabsTop"], delta=1.5, msg=f"the pages' top: the file {f['tabsTop']}, the editor {e['tabsTop']}")
                    self.assertAlmostEqual(f["tabsH"], e["tabsH"], delta=1.5, msg=f"the pages' height: the file {f['tabsH']}, the editor {e['tabsH']}")
                    self.assertTrue(f["wide"], "no sideways scroll")
                    if width == 900:
                        self.assertEqual(f["search"], 0, "search is not drawn in the bar")
                        self.probe_menu(dark)

    def test_published_header_900px_every_page_label_keeps_4_5_to_1_over_the_picture(self):
        """AP7: at 900 px the pages sit in the bar's one row, over the cover picture; EVERY page label (selected or not) keeps 4.5 to 1 against the pixels drawn behind it, with a swirl and a bright picture in place, light and dark. The picture's fade at 900 px and narrower is what keeps it."""
        labels = """(() => [...document.querySelectorAll('header.top .tab')].map((t) => { const n = t.querySelector('.tab-label') || t, w = document.createTreeWalker(t, NodeFilter.SHOW_TEXT), out = [];
          for (let x; (x = w.nextNode());) { if (!x.textContent.trim()) continue; const rg = document.createRange(); rg.selectNodeContents(x);
            for (const r of rg.getClientRects()) if (r.width > 2) out.push({x: r.left, y: r.top, w: r.width, h: r.height}); }
          return {t: t.textContent.trim(), fg: getComputedStyle(t).color, rects: out}; }))()"""
        for dark in (False, True):
            for name, data in (("swirl", pics.swirl()), ("bright", pics.solid((60, 200, 230)))):
                with self.subTest(dark=dark, picture=name):
                    path = self.publish()
                    with chrome() as cdp:
                        p = self.draw(cdp, path, 900, dark)
                        p.until("!!document.querySelector('header.top-file .tab')", "the published bar drew")
                        p.js("document.documentElement.style.setProperty('--image-cover', %s)" % json.dumps("url(data:image/png;base64," + base64.b64encode(data).decode() + ")"))
                        p.until("document.getAnimations().every(a => a.playState === 'finished')", "settled")
                        items = p.js(labels)
                        p.js(HIDE)
                        w, h, rows = pics.decode(base64.b64decode(cdp.call("Page.captureScreenshot", {"format": "png"}, p.sid)["data"]))
                    self.assertGreaterEqual(len(items), 3, "control: the page labels were read")
                    for it in items:
                        self.assertTrue(it["rects"], f"control: {it['t']!r} has a drawn label")
                        r, g, b, a = colour(it["fg"])
                        low = 99.0
                        for q in it["rects"]:
                            for y in range(int(q["y"]), min(h, int(q["y"] + q["h"]) + 1), 2):
                                for x in range(int(q["x"]), min(w, int(q["x"] + q["w"]) + 1), 2):
                                    bg = rows[y][x]
                                    low = min(low, ratio([a * c + (1 - a) * k for c, k in zip((r, g, b), bg)], bg))
                        self.assertGreaterEqual(low, 4.5, f"{it['t']!r} is {low:.2f}:1 over the picture")

    def probe_menu(self, dark):
        path = self.publish()
        with chrome() as cdp:
            p = self.draw(cdp, path, 900, dark)
            p.until("!!document.querySelector('header.top-file .tab')", "the published bar drew")
            p.js("document.querySelector('.cm-badge').click()")
            p.until("!!document.querySelector('[role=menu]') && document.querySelector('[role=menu]').textContent.trim().length > 0", "the profile menu opened")
            menu = p.js("document.querySelector('[role=menu]').textContent")
        for page in ("Dashboard", "Work items", "Milestones"):
            self.assertNotIn(page, menu, "the pages do not move into the profile menu")


for _cls in (Ap7,):
    for _name in dir(_cls):
        if _name.startswith(("test", "plant_", "pages", "probe_", "LONG")):
            setattr(Header1543, _name, getattr(_cls, _name))
for _name in dir(glance.Published):      # the base class's own tests are run in its own file
    if _name.startswith("test") and _name not in Header1543.__dict__:
        setattr(Header1543, _name, None)
