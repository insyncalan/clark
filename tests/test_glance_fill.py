"""A-D14: the At a glance tiles fill the row, with Project health two tile widths, and nothing wraps at 900 px.

Run: python3 dev/run_tests.py test_glance_fill
The first class reads the source and needs no browser: the layout rules sit in shell.css (shared by the editor and the published
page, so both built pages carry them) and four tiles at the least width fit one line in the room the page leaves at 900 px. The
second class opens the real page at 1400 and 900 px, light and dark, in View (three tiles) and Edit (four tiles).
"""
import re
import unittest

from _paths import SRC

from test_glance_page import Setup  # noqa: F401
from test_server import chrome

PAGE = SRC / "clark" / "page"
GAP, TILE_MIN = 12, 150          # the row gap and the least a tile may be, in px (shell.css)
ROOM_900 = 900 - 2 * 16 - (2 * 16 + 2)   # the page's side padding, then the frame's padding and border at 900 px: 834 px


def rule(css, selector):
    m = re.search(r"(?m)^" + re.escape(selector) + r" \{([^}]*)\}", css)
    return m.group(1) if m else ""


class Source(unittest.TestCase):
    def test_tiles_share_the_row_and_health_takes_two_shares_and_the_gap(self):
        css = (PAGE / "shell.css").read_text()
        cell, health = rule(css, ".tcell"), rule(css, ".tcell.health")
        self.assertIn("flex: 1 1 0", cell, "each tile takes an equal share")
        self.assertIn(f"min-width: {TILE_MIN}px", cell)
        self.assertIn(f"flex: 2 1 {GAP}px", health, "two shares, and the gap as its basis, so it is 2 tiles + 1 gap wide")
        self.assertIn(f"min-width: {2 * TILE_MIN + GAP}px", health)
        self.assertIn(f"gap: {GAP}px", rule(css, ".glance"))
        self.assertNotIn("0 0 190px", css)
        self.assertNotIn("0 0 392px", css)

    def test_four_tiles_at_the_least_width_fit_one_line_at_900(self):
        health = 2 * TILE_MIN + GAP
        self.assertEqual(3 * TILE_MIN + health + 3 * GAP, 798)     # three tiles, Project health and three gaps
        self.assertLessEqual(3 * TILE_MIN + health + 3 * GAP, ROOM_900 - 15, "with a 15 px scroll bar too")

    def test_both_built_pages_carry_the_rules(self):
        for name in ("page.html", "page-view.html"):
            html = (PAGE / name).read_text()
            self.assertIn(f"flex: 2 1 {GAP}px", html, name)
            self.assertIn(f"min-width: {TILE_MIN}px", html, name)


class Fill(Setup):
    def check(self, p, width, count):
        box = p.js("""(() => {
          const g = document.querySelector('.glance'), r = g.getBoundingClientRect();
          return {left: r.left, width: r.width, gap: parseFloat(getComputedStyle(g).columnGap),
                  cells: [...g.children].map(e => { const b = e.getBoundingClientRect(); return {tile: e.dataset.tile, left: b.left, width: b.width, top: b.top}; })};
        })()""")
        cells = box["cells"]
        self.assertEqual(len(cells), count)
        self.assertEqual(len({round(c["top"]) for c in cells}), 1, f"one line at {width}")
        self.assertAlmostEqual(cells[0]["left"], box["left"], delta=1.5)
        self.assertAlmostEqual(cells[-1]["left"] + cells[-1]["width"], box["left"] + box["width"], delta=1.5, msg=f"fills the row at {width}")
        health, small = cells[0], cells[1]
        self.assertEqual(health["tile"], "health")
        self.assertAlmostEqual(health["width"], 2 * small["width"] + box["gap"], delta=1.5)
        for c in cells[1:]:
            self.assertAlmostEqual(c["width"], small["width"], delta=1.5)
            self.assertGreaterEqual(c["width"], TILE_MIN - 1.5)
        self.assertTrue(p.js("document.documentElement.scrollWidth <= window.innerWidth"), "no sideways scroll")
        small_text = p.js("Math.min(...[...document.querySelectorAll('.glance .fig .k, .glance .fig .dd, .glance .fig .tw')].map(e => parseFloat(getComputedStyle(e).fontSize)))")
        self.assertGreaterEqual(small_text, 13)

    def test_view_tiles_fill_the_row_at_1400_and_900_in_light_and_dark(self):
        for width in (1400, 900):
            for dark in (False, True):
                with self.subTest(width=width, dark=dark), chrome() as cdp:
                    self.check(self.show(cdp, width, dark), width, 3)

    def test_edit_shows_four_tiles_on_one_line_at_900_and_1400(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.show(cdp, width)
                p.edit()
                p.until("document.querySelectorAll('.glance > .tcell').length === 4", "four tiles in Edit")
                self.check(p, width, 4)

    def test_a_lone_health_tile_fills_the_row(self):
        with chrome() as cdp:
            p = self.show(cdp)
            p.js("document.querySelectorAll('.glance > .tcell:not(.health)').forEach(e => e.remove())")
            w = p.js("(() => { const g = document.querySelector('.glance').getBoundingClientRect(), h = document.querySelector('.tcell.health').getBoundingClientRect(); return [g.width, h.width]; })()")
            self.assertAlmostEqual(w[0], w[1], delta=1.5)


if __name__ == "__main__":
    unittest.main()
