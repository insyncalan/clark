"""Row 1605 (the edge cases of row 1475, deleted with PR 2272's test_wil_footer_hostile_1475.py): the one-line Work items footer in Edit mode, after
Show all items, with the keyboard focus, at a narrow width and in tab order. Built on main's FooterOneRow and its helpers (test_wil_footer_one_row_1475).
These open the browser and were written without one (not run where they were written). Run: CLARK_CHROME=/usr/local/bin/creaite-chrome python3 dev/run_tests.py test_wil_footer_hostile_1605.py"""
import json
import unittest

import test_wil_footer_one_row_1475 as F
from test_report_editor import tearDownModule  # noqa: F401
from test_server import chrome

# The footer of one section as it is drawn (the visible one: Edit and View may each hold a footer), with the box of each of its parts.
VIS = """(ref => { const sec = document.querySelector('[data-id="' + ref + '"]'); const vis = (q) => [...sec.querySelectorAll(q)].find((e) => e.offsetParent !== null) || null;
  const foot = vis('[data-wil-foot]'); const r = (e) => { if (!e) return null; const b = e.getBoundingClientRect(); return {top: b.top, bottom: b.bottom, left: b.left, right: b.right, w: b.width}; };
  const s = sec.getBoundingClientRect(), cs = getComputedStyle(sec);
  return {foot: r(foot), all: r(foot && foot.querySelector('[data-wil-all]')), rev: r(foot && foot.querySelector('[data-wil-review]')), secRight: s.right - parseFloat(cs.paddingRight),
    footScroll: foot ? foot.scrollWidth - foot.clientWidth : null, revScroll: foot ? foot.querySelector('[data-wil-review]').scrollWidth - foot.querySelector('[data-wil-review]').clientWidth : null,
    count: foot && foot.querySelector('[data-wil-count]') ? foot.querySelector('[data-wil-count]').textContent : null,
    // what a failing run must show: each part's box, line height, white-space and flex-shrink (a part squeezed to wrap onto two lines is taller than one line)
    parts: foot ? [...foot.children].map((e) => { const c = getComputedStyle(e), b = e.getBoundingClientRect(); return {tag: e.tagName, attr: [...e.attributes].map((a) => a.name).join(' '), w: b.width, h: b.height, lh: c.lineHeight, ws: c.whiteSpace, shrink: c.flexShrink, mt: c.marginTop, pt: c.paddingTop, ai: c.alignSelf, sw: e.scrollWidth}; }) : null,
    footAlign: foot ? getComputedStyle(foot).alignItems : null}; })"""


def vis(p, ref):
    return p.js(f"({VIS})({json.dumps(ref)})")


def _focus_all(ref):
    return f"document.querySelector('[data-id=\"{ref}\"] [data-wil-all]')"


class Edges(F.FooterOneRow):
    """The served Classic page again; main's own tests stay in main's file, so they are switched off here."""


    def test_edit_mode_footer_is_one_line_with_review_all_at_the_right_edge_1400_and_900(self):
        """Edit mode. Mutant: src/clark/page/shell.css, the rule `.wil-foot { display: flex; ...` becomes `display: block;` (the three parts stack:
        Show all items, the count and Review all N items are no longer on one line, so the one-line-high and the equal-top checks go red)."""
        a, b = self.pair(2, 10)
        for width in self.widths():
            for dark in (False, True):
                with self.subTest(width=width, dark=dark), chrome() as cdp:
                    p = self.show(cdp, width, dark)
                    self.drawn(p, a, b)
                    p.edit()
                    p.until(f"!!document.querySelector('[data-id=\"{a}\"] [data-wil-review]')", "the footer is there in Edit")
                    ga, gb = vis(p, a), vis(p, b)
                    self.assertIsNotNone(ga["all"], f"Show all items is drawn in Edit: {ga}")
                    self.assertEqual(ga["all"]["top"], ga["rev"]["top"], f"{width}: Show all items and Review all share a line in Edit: {ga}")
                    self.assertLessEqual(ga["foot"]["bottom"] - ga["rev"]["top"], ga["rev"]["bottom"] - ga["rev"]["top"] + 1, f"one line high in Edit: {ga}")
                    self.assertLessEqual(abs(ga["rev"]["right"] - ga["secRight"]), 2, f"Review all is at the right edge in Edit: {ga}")
                    self.assertIsNone(gb["all"], gb)
                    # Review all N items is one text line (it is 32px high, not 42): a squeezed button wraps onto two lines and lifts the pair's tops apart
                    self.assertLessEqual(ga["rev"]["bottom"] - ga["rev"]["top"], 36, f"{width}: Review all N items is on one line in Edit: {ga}")
                    if width > 900:
                        self.assertEqual(ga["rev"]["top"], gb["rev"]["top"], f"the pair's footers are level in Edit: {ga} {gb}")

    def test_after_show_all_the_link_stays_in_the_footer_line_and_the_pair_stays_level(self):
        """After Show all items. Mutant: src/clark/page/src/templates/WorkItemsList.jsx, in Foot the line `{more ? <ShowAll ...` becomes
        `{more && !open ? <ShowAll ...` (the link vanishes once the list is open, so the aria-expanded wait and the link-in-the-footer check go red)."""
        a, b = self.pair(2, 2)
        for width in self.widths():
            with self.subTest(width=width), chrome() as cdp:
                p = self.show(cdp, width)
                self.drawn(p, a, b)
                before = vis(p, a)["count"]
                p.js(f"{_focus_all(a)}.click()")
                p.until(f"!!{_focus_all(a)} && {_focus_all(a)}.getAttribute('aria-expanded') === 'true'", "Show all items opened (it now reads Show only N)")
                ga, gb = vis(p, a), vis(p, b)
                self.assertIsNotNone(ga["all"], f"the link is still in the footer: {ga}")
                self.assertEqual(ga["all"]["top"], ga["rev"]["top"], f"{width}: still one line after opening: {ga}")
                self.assertLessEqual(ga["foot"]["bottom"] - ga["rev"]["top"], ga["rev"]["bottom"] - ga["rev"]["top"] + 1, ga)
                self.assertNotEqual(ga["count"], before, "the count words change when the list is open")
                if width > 900:
                    self.assertEqual(ga["rev"]["bottom"], gb["rev"]["bottom"], f"the pair's footers stay level after opening one: {ga} {gb}")

    def test_the_focus_stays_on_show_all_after_it_is_pressed_and_after_it_is_pressed_again(self):
        """Focus. Mutant: src/clark/page/src/templates/WorkItemsList.jsx, in Foot the opening tag `<div class="wil-foot" data-wil-foot="">` gets
        `key={open ? "o" : "c"}` (the footer is rebuilt on each press, the button is a new element and the focus falls back to the page body)."""
        a, b = self.pair(2, 3)
        with chrome() as cdp:
            p = self.show(cdp, 1400)
            self.drawn(p, a, b)
            p.js(f"{_focus_all(a)}.focus()")
            for state in ("true", "false"):
                p.js(f"{_focus_all(a)}.click()")
                p.until(f"!!{_focus_all(a)} && {_focus_all(a)}.getAttribute('aria-expanded') === '{state}'", f"aria-expanded is {state}")
                self.assertTrue(p.js(f"document.activeElement === {_focus_all(a)}"), f"the focus is still on Show all items (aria-expanded {state})")

    def test_narrow_width_footer_does_not_overflow_the_card_or_the_page(self):
        """Narrow width (400 and 600, the pair is stacked). Mutant: src/clark/themes/prototype-2.0/rules-2.css, in the block `.sec > .wil > .wil-foot` add
        `flex-wrap: nowrap; white-space: nowrap;` and in `.wil-foot .wil-all-b, .wil-foot .wil-review` add `flex: none` (the three parts need more than the card
        is wide and spill out of it: the footer scroll-width, the right-edge and the page-width checks go red)."""
        a, b = self.pair(2, 3)
        for width in (600, 400):
            with self.subTest(width=width), chrome() as cdp:
                p = self.show(cdp, width)
                self.drawn(p, a, b)
                for ref in (a, b):
                    g = vis(p, ref)
                    self.assertLessEqual(g["footScroll"], 1, f"{width}: the footer is not wider than its card: {g}")
                    self.assertLessEqual(g["rev"]["right"], g["secRight"] + 2, f"{width}: Review all stays inside the card: {g}")
                    self.assertGreaterEqual(g["rev"]["left"], 0, g)
                self.assertTrue(p.js("document.documentElement.scrollWidth <= innerWidth + 1"), f"{width}: the page does not scroll sideways")

    def test_tab_goes_show_all_then_review_all_and_back_and_review_all_is_not_squeezed_1400_and_900(self):
        """Tab order. Mutant: src/clark/page/src/templates/WorkItemsList.jsx, in Foot move the line `{filter ? <button ... data-wil-review ...` above the line
        `{more ? <ShowAll ...` (Review all N items comes first in the DOM, so Tab from Show all items no longer lands on it and the order check goes red); a
        second mutant, rules-2.css `.wil-foot .wil-review` with `flex: 0 1 0; overflow: hidden`, squeezes the link (the scroll-width check goes red)."""
        a, b = self.pair(2, 3)
        for width in self.widths():
            with self.subTest(width=width), chrome() as cdp:
                p = self.show(cdp, width)
                self.drawn(p, a, b)
                for ref in (a, b):
                    g = vis(p, ref)
                    self.assertLessEqual(g["revScroll"], 0, f"{width}: Review all N items is not clipped: {g}")
                order = p.js(f"[...document.querySelector('[data-id=\"{a}\"] [data-wil-foot]').children].map(e => e.hasAttribute('data-wil-all') ? 'all' : e.hasAttribute('data-wil-count') ? 'count' : e.hasAttribute('data-wil-review') ? 'review' : 'other')")
                self.assertEqual([x for x in order if x != "other"], ["all", "count", "review"], order)
                p.js(f"{_focus_all(a)}.focus()")
                p.key("Tab", code="Tab", vk=9)
                self.assertTrue(p.js("document.activeElement.hasAttribute('data-wil-review')"), "Tab goes from Show all items to Review all N items (the count is not a stop)")
                p.key("Tab", modifiers=8, code="Tab", vk=9)      # Shift+Tab
                self.assertTrue(p.js("document.activeElement.hasAttribute('data-wil-all')"), "Shift+Tab goes back to Show all items")


for _n in list(vars(F.FooterOneRow)):      # main's own tests stay in main's file
    if _n.startswith("test_"):
        setattr(Edges, _n, None)


if __name__ == "__main__":
    unittest.main()
