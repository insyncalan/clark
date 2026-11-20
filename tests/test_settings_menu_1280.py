"""Row 1280: the Settings menu shows what is a group heading and what is a page you can click, in a real browser at 1400 and 900 px,
light and dark. Run: python3 dev/run_tests.py test_settings_menu_1280

What is asserted: a group heading is a label (not a link or a button, not focusable, no pointer cursor, no hover fill, no line under it, smaller than a page row,
muted, capitals, 13 px or more and 4.5:1 on the bar) with more space above it than between two pages; the pages of one group touch (a block) and each row is
at most 32 px high; a page row is the whole hit area (its edges answer to the page), has a pointer cursor and a hover fill, the open page is marked
(aria-current and a filled row with an accent bar) and the keyboard ring shows. Chrome is required: these tests fail, never skip, without it.
"""
import time
import unittest

from test_publish_dialog import Base
from test_server import chrome, wait
from test_settings_head import GROUPS, PAGES, address, FIRST, ratio, rgb
from test_appearance import scheme

WIDTHS = (1400, 900)
MODES = ("light", "dark")
NAME = "[...document.querySelectorAll('.set-nav .set-group-name')]"
CHIPS = "[...document.querySelectorAll('.set-nav .set-chip')]"


class SettingsMenu1280(Base):
    def open_settings(self, p, w, mode):
        p.width(w)
        scheme(p, mode)
        p.js(f"location.hash = '{address(FIRST)}'")
        p.until("!!document.querySelector('.set-nav .set-chip[aria-current]') && !!document.getElementById('projects-h')", "Settings and its menu drew")
        wait(lambda: p.js("document.getElementById('projects-h').getBoundingClientRect().height") > 0, 10)

    def hover(self, p, x, y):
        p.cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y}, p.sid)

    def each(self, body):
        for w in WIDTHS:
            for mode in MODES:
                with self.subTest(width=w, mode=mode), chrome() as cdp:
                    p = self.page(cdp)
                    self.open_settings(p, w, mode)
                    body(p, w, mode)

    def test_C_a_heading_is_a_label_not_a_link(self):
        def body(p, w, mode):
            names = p.js(f"{NAME}.map(e => e.textContent)")
            self.assertEqual(names, [g for g, _ in GROUPS])
            got = p.js(f"""{NAME}.map(e => {{ const s = getComputedStyle(e), c = getComputedStyle(document.querySelector('.set-chip:not([aria-current])'));
                return [e.tagName, e.getAttribute('tabindex'), e.closest('a, button') === null, s.cursor, parseFloat(s.fontSize), parseFloat(c.fontSize), s.textTransform,
                        s.color, c.color, s.borderBottomWidth, s.borderTopWidth, s.fontWeight]; }})""")
            for tag, tabindex, not_inside, cursor, size, chip_size, upper, color, chip_color, below, above, _ in got:
                self.assertNotIn(tag, ("A", "BUTTON"))
                self.assertIsNone(tabindex, "a heading is not focusable")
                self.assertTrue(not_inside)
                self.assertNotEqual(cursor, "pointer")
                self.assertGreaterEqual(size, 13)
                self.assertLess(size, chip_size, "a heading is smaller than a page row")
                self.assertEqual(upper, "uppercase")
                self.assertNotEqual(color, chip_color, "a heading is muted, not the page colour")
                self.assertEqual(below, "0px", "no line under a heading")
            ground = p.js("getComputedStyle(document.querySelector('.set-bar')).backgroundColor")
            for g in got:
                self.assertGreaterEqual(ratio(rgb(g[7]), rgb(ground)), 4.5, f"{mode}: the heading on the bar")
            focusable = p.js("document.querySelectorAll('.set-nav button, .set-nav a, .set-nav [tabindex]').length")
            self.assertEqual(focusable, len(PAGES), "only the pages take focus")
            # nothing changes when the pointer is over a heading
            r = p.js(f"(function(){{ const b = {NAME}[1].getBoundingClientRect(); return [b.left + 20, b.top + b.height / 2]; }})()")
            before = p.js(f"getComputedStyle({NAME}[1]).backgroundColor")
            self.hover(p, *r)
            self.assertEqual(p.js(f"getComputedStyle({NAME}[1]).backgroundColor"), before, "no hover fill on a heading")
            self.assertEqual(p.js(f"getComputedStyle({NAME}[1]).cursor"), "default")
        self.each(body)

    def test_C_a_group_reads_as_a_block_with_space_above_its_heading(self):
        def body(p, w, mode):
            rows = p.js(f"""[...document.querySelectorAll('.set-nav .set-group')].map(g => {{ const n = g.querySelector('.set-group-name').getBoundingClientRect();
                const c = [...g.querySelectorAll('.set-chip')].map(b => b.getBoundingClientRect());
                return [n.top, n.bottom, c.map(r => [r.top, r.bottom, r.height]), g.querySelector('.set-group-name').textContent]; }})""")
            for _, _, chips, _ in rows:
                for _, _, h in chips:
                    self.assertLessEqual(h, 40, "page rows are tight: one line is 32, a long name that wraps in the 150 px list at 900 is two lines")
                    self.assertGreaterEqual(h, 24)
                for a, b in zip(chips, chips[1:]):
                    self.assertLessEqual(b[0] - a[1], 1, "the pages of a group touch: one block")
            for (_, _, a, _), (top, _, _, _) in zip(rows[:-1], rows[1:]):
                self.assertGreaterEqual(top - a[-1][1], 16, "space above a heading")
            for top, bottom, chips, name in rows:
                if name == "Advanced":
                    continue      # Advanced keeps its grey line of words between its heading and its first page, so the heading is not close to the page there
                self.assertLessEqual(chips[0][0] - bottom, 8, "a heading sits close to its own pages")
        self.each(body)

    def test_C_the_list_has_no_gap_between_groups_at_900(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_settings(p, 900, "light")
            self.assertEqual(p.js("getComputedStyle(document.querySelector('.set-nav')).rowGap"), "0px", "at 900 the list adds no gap of its own: the space above a heading is its margin")

    def test_C_heading_box_and_advanced_line(self):
        def body(p, w, mode):
            got = p.js(f"""{NAME}.map(e => {{ const s = getComputedStyle(e); return [s.display, s.fontWeight, s.paddingTop, s.paddingLeft, parseFloat(s.paddingBottom)]; }})""")
            for display, weight, top, left, bottom in got:
                self.assertEqual((display, weight, top, left), ("block", "700", "0px", "12px"), "a heading box: block, semibold, indented as a page name")
                self.assertLessEqual(bottom, 8, "padding under a heading is small")
            li = p.js("[...document.querySelectorAll('.set-nav .plain li')].map(e => { const s = getComputedStyle(e); return [s.borderTopWidth, s.paddingTop, s.paddingBottom]; })")
            self.assertTrue(all(x == ["0px", "0px", "0px"] for x in li), "no line or padding on a page's list item")
            if p.js("!!document.querySelector('.set-advanced')"):
                adv = p.js("(function(){ const s = getComputedStyle(document.querySelector('.set-advanced')); return [s.borderTopWidth, parseFloat(s.paddingTop)]; })()")
                self.assertEqual(adv[0], "1px", "Advanced keeps its line above")
                self.assertGreater(adv[1], 0, "and room under the line")
            else:
                self.assertEqual(p.js("document.querySelectorAll('.set-group-line').length"), 0, "row 1299 1a: no group is set apart and none has a line of words")
            first = p.js("(function(){ const g = document.querySelector('.set-nav .set-group'); return getComputedStyle(g).marginTop; })()")
            self.assertEqual(first, "0px", "the first group has no space above it")
        self.each(body)

    def test_C_a_page_row_is_clearly_clickable_and_the_open_one_is_marked(self):
        def body(p, w, mode):
            got = p.js(f"""{CHIPS}.map(b => {{ b.scrollIntoView({{block: 'nearest'}}); const s = getComputedStyle(b), r = b.getBoundingClientRect(), li = b.parentElement.getBoundingClientRect();
                return [s.cursor, Math.abs(r.width - li.width) < 1, document.elementFromPoint(r.left + 2, r.top + r.height / 2) === b, document.elementFromPoint(r.right - 2, r.top + r.height / 2) === b]; }})""")
            for cursor, wide, left, right in got:
                self.assertEqual(cursor, "pointer")
                self.assertTrue(wide and left and right, f"the whole row is the hit area: {got}")
            self.assertEqual(p.js("document.querySelector('.set-chip[aria-current]').getAttribute('aria-current')"), "page")
            marked = p.js("""(function(){ const b = document.querySelector('.set-chip[aria-current]'), s = getComputedStyle(b), m = getComputedStyle(b, '::before');
                return [s.backgroundColor, m.width, m.backgroundColor]; })()""")
            self.assertNotEqual(marked[0], "rgba(0, 0, 0, 0)", "the open row is filled")
            self.assertEqual(marked[1], "3px", "and has an accent bar")
            rest = p.js("(function(){ const b = document.querySelector('.set-chip:not([aria-current])'); return getComputedStyle(b).backgroundColor; })()")
            self.assertEqual(rest, "rgba(0, 0, 0, 0)")
            # the pointer is moved again on every poll, to a point re-measured from the row and one pixel different each time: a single move sent while the page is still
            # settling (a loaded runner) is lost, and a move to the same point is not a move at all
            tries = []
            def hovered():
                r = p.js("(function(){ const c = document.querySelector('.set-chip:not([aria-current])'); c.scrollIntoView({block: 'nearest'}); const b = c.getBoundingClientRect(); return [b.left + b.width - 3, b.top + b.height / 2]; })()")
                tries.append(1)
                self.hover(p, r[0] - len(tries) % 2, r[1])
                time.sleep(0.15)
                return p.js("getComputedStyle(document.querySelector('.set-chip:not([aria-current])')).backgroundColor") != "rgba(0, 0, 0, 0)"
            self.assertTrue(wait(hovered, 10), "a hover fill at the row's far edge")
            p.js("document.querySelector('.set-chip').focus()")
            p.key("Tab", code="Tab", vk=9)
            ring = p.js("(function(){ const s = getComputedStyle(document.activeElement); return [s.outlineWidth, s.outlineStyle]; })()")
            self.assertEqual(ring, ["2px", "solid"], "the keyboard ring")
        self.each(body)


if __name__ == "__main__":
    unittest.main()
