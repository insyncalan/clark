"""A-D3 in a real browser: each Dashboard section is a card with a square before its heading, in all four section styles.

Run: python3 dev/run_tests.py test_section_card_look_page
Same set-up as test_glance_page (a real server over a temporary store, fictional data). Laptop widths only: 1400 and 900 px, light
and dark. The published file is opened from file:// and follows the same shared CSS.
"""
import unittest

import test_glance_page as g
from test_report_editor import tearDownModule  # noqa: F401
from test_server import chrome

SQUARE = ("(() => { const h = document.querySelector('.secs > .sec .sec-head'); const s = getComputedStyle(h, '::before');"
          " return [s.width, s.height, s.backgroundColor, getComputedStyle(h.closest('.sec')).borderTopWidth,"
          " getComputedStyle(h.closest('.sec')).borderTopLeftRadius, getComputedStyle(h.closest('.sec')).backgroundColor,"
          " getComputedStyle(document.documentElement).getPropertyValue('--brand-blue').trim()]; })()")


class Cards(g.Setup):
    def test_every_section_is_a_card_with_one_square_in_each_style(self):
        for width, dark in ((1400, False), (900, False), (1400, True)):
            with chrome() as cdp:
                p = self.show(cdp, width=width, dark=dark)
                for style in ("slim", "roomy", "grey", "card"):
                    p.js(f"document.documentElement.dataset.secstyle = '{style}'")
                    w, h, bg, border, radius, sec_bg, _ = p.js(SQUARE)
                    self.assertEqual((w, h), ("10px", "10px"), f"{style} {width}: the square is drawn")
                    self.assertNotEqual(bg, "rgba(0, 0, 0, 0)", style)
                    if style == "card":
                        self.assertEqual(sec_bg, "rgba(0, 0, 0, 0)", "One card: the sections are flat")
                    else:
                        self.assertEqual(border, "1px", f"{style}: a card has one border")
                        self.assertNotEqual(radius, "0px", style)
                p.js("document.documentElement.dataset.secstyle = 'slim'")
                gap = p.js("parseFloat(getComputedStyle(document.querySelector('.secs')).rowGap)")
                self.assertLessEqual(gap, 16, "a slim gap between cards")
                self.assertEqual(p.js("document.documentElement.scrollWidth <= window.innerWidth"), True, f"no sideways scroll at {width}")

# One card (Settings › Personal › Dashboard sections › One card): the report's frame is the only border, Edit's grip and + sit in the
# frame's side padding (on no border line), and a half-width pair has one unbroken line above it.
LOOK = """(() => {
  const sides = (e) => { const c = getComputedStyle(e); return ['Top', 'Right', 'Bottom', 'Left'].map((s) => c['border' + s + 'Style'] !== 'none' ? parseFloat(c['border' + s + 'Width']) : 0); };
  const R = (e) => { const b = e.getBoundingClientRect(); return { l: b.left, t: b.top, r: b.right, b: b.bottom }; };
  const frame = document.getElementById('report'), secs = frame.querySelector('.secs');
  const boxed = [frame, secs].filter((e) => sides(e).every((w) => w > 0)).map((e) => e.id || e.className);
  const secSides = [...frame.querySelectorAll('.secs > .sec')].map((e) => sides(e).slice(1));      // right, bottom, left of every section
  // the border lines of the frame, the inner box and every section, as thin rectangles
  const lines = [];
  for (const e of [frame, secs, ...frame.querySelectorAll('.secs > .sec')]) {
    const [t, r, b, l] = sides(e), q = R(e);
    if (t) lines.push({ l: q.l, t: q.t, r: q.r, b: q.t + t });
    if (b) lines.push({ l: q.l, t: q.b - b, r: q.r, b: q.b });
    if (l) lines.push({ l: q.l, t: q.t, r: q.l + l, b: q.b });
    if (r) lines.push({ l: q.r - r, t: q.t, r: q.r, b: q.b });
  }
  const hit = (a, b) => a.l < b.r && a.r > b.l && a.t < b.b && a.b > b.t;
  const ctl = [...frame.querySelectorAll('.sec-ctl .handle, .sec-ctl .plus')].map(R);
  const touching = ctl.filter((c) => lines.some((ln) => hit(c, ln))).length;
  const pair = (id) => { const e = frame.querySelector('[data-id="' + id + '"]'), c = getComputedStyle(e); return { rect: R(e), w: c.borderTopWidth, colour: c.borderTopColor, style: c.borderTopStyle }; };
  return JSON.stringify({ boxed, secSides, touching, controls: ctl.length, left: pair('ABC-S-006'), right: pair('ABC-S-007'), scroll: document.documentElement.scrollWidth <= innerWidth });
})()"""


class OneCard(g.Setup):
    def look(self, p):
        import json
        return json.loads(p.js(LOOK))

    def test_one_card_has_one_border_and_edit_controls_sit_on_none_in_both_modes_and_themes(self):
        for width in (1400, 900):
            for dark in (False, True):
                with chrome() as cdp:
                    p = self.show(cdp, width=width, dark=dark)
                    p.js("document.documentElement.dataset.secstyle = 'card'")
                    for mode in ("view", "edit"):
                        if mode == "edit":
                            p.edit()
                        got = self.look(p)
                        where = f"{width} {'dark' if dark else 'light'} {mode}"
                        self.assertEqual(got["boxed"], ["report"], f"{where}: only the report's frame is a box with a border (never the inner card too)")
                        self.assertTrue(all(side == [0, 0, 0] for side in got["secSides"]), f"{where}: a section has only its top line")
                        self.assertTrue(got["scroll"], where)
                        if mode == "edit":
                            self.assertGreater(got["controls"], 10, where)
                            self.assertEqual(got["touching"], 0, f"{where}: the grip and + sit on no border line")

    def test_a_pair_has_one_unbroken_line_above_it_and_the_first_row_has_none(self):
        with chrome() as cdp:
            p = self.show(cdp, width=1400)
            p.js("document.documentElement.dataset.secstyle = 'card'")
            for mode in ("view", "edit"):
                if mode == "edit":
                    p.edit()
                got = self.look(p)
                a, b = got["left"], got["right"]
                self.assertEqual(p.js("document.querySelector('[data-id=\"ABC-S-006\"]').classList.contains('slot-left')"), True, "This week is half width")
                self.assertEqual((a["w"], b["w"]), ("1px", "1px"), mode)
                self.assertEqual((a["colour"], a["style"]), (b["colour"], b["style"]), f"{mode}: both halves' lines look the same")
                self.assertAlmostEqual(a["rect"]["t"], b["rect"]["t"], delta=0.5)
                self.assertAlmostEqual(a["rect"]["r"], b["rect"]["l"], delta=0.5, msg=f"{mode}: the halves' lines meet, no gap in the middle")
            # the first two sections as a pair: neither half has a line (done last: the page is rearranged by hand)
            p.js("(() => { const s = document.querySelector('#report .secs'), l = s.querySelector('[data-id=\"ABC-S-006\"]'), r = s.querySelector('[data-id=\"ABC-S-007\"]');"
                 " s.prepend(r); s.prepend(l); })()")
            got = self.look(p)
            self.assertEqual((got["left"]["w"], got["right"]["w"]), ("0px", "0px"), "the first row has no top line, for either half")
            self.assertEqual(p.js("getComputedStyle(document.querySelectorAll('#report .secs > .sec')[2]).borderTopWidth"), "1px", "the row after it has its line")

    def test_at_900_the_pair_stacks_and_each_section_keeps_the_same_line(self):
        with chrome() as cdp:
            p = self.show(cdp, width=900)
            p.js("document.documentElement.dataset.secstyle = 'card'")
            got = self.look(p)
            self.assertEqual((got["left"]["w"], got["right"]["w"]), ("1px", "1px"))
            self.assertEqual(got["left"]["colour"], got["right"]["colour"])
            self.assertAlmostEqual(got["left"]["rect"]["l"], got["right"]["rect"]["l"], delta=0.5, msg="one column: both stacked sections start at the same edge")


class PublishedCards(g.Setup):
    publish = g.Published.publish          # the finished file, written the way test_glance_page writes it
    draw = g.Published.draw

    def test_the_published_file_draws_the_same_cards(self):
        path = self.publish()
        with chrome() as cdp:
            p = self.draw(cdp, path)
            w, h, bg, border, radius, _, _ = p.js(SQUARE)
            self.assertEqual((w, h, border), ("10px", "10px", "1px"))


if __name__ == "__main__":
    unittest.main()
