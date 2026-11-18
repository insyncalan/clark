"""Row 1317 (Settings sidebar, Classic Theme) killers: the hover tint is a real step from the panel, and the open page keeps its square edge while hovered.

Run: python3 dev/run_tests.py test_theme_classic_1317a_killers
Mutants killed (rules.css): the hover mix percentage set to 0 (the first test reads the colours through a canvas, because Chrome returns a
color-mix() value in a different notation from rgb(), so comparing the two strings never saw the difference), and the hover rule for the open page removed.
1400 and 900 px, light and dark. Fails, never skips, without Chrome.
"""
import unittest

from _paths import ROOT  # noqa: F401
from test_server import chrome
from test_theme_classic_1317a import SIZES, Sidebar

PIXEL = """((css) => { const c = document.createElement('canvas'); c.width = c.height = 1; const x = c.getContext('2d');
  x.fillStyle = '#000'; x.fillStyle = css; x.fillRect(0, 0, 1, 1); return [...x.getImageData(0, 0, 1, 1).data]; })"""


class Killers(unittest.TestCase):
    load = Sidebar.load

    def hover(self, cdp, sid, selector):
        box = cdp.js("(() => { const r = document.querySelector(%r).getBoundingClientRect(); return [r.x + r.width / 2, r.y + r.height / 2]; })()" % selector, sid)
        cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": box[0], "y": box[1]}, sid)

    def test_the_hover_tint_is_a_visible_step_from_the_panel_in_rgb(self):
        with chrome() as cdp:
            for scheme in ("light", "dark"):
                for w in SIZES:
                    got, sid = self.load(cdp, w, scheme, "prototype-2.0")
                    tag = f"hover tint {scheme} {w}"
                    self.hover(cdp, sid, ".set-chip:not([aria-current])")
                    hov = cdp.js("getComputedStyle(document.querySelector('.set-chip:not([aria-current])')).backgroundColor", sid)
                    a = cdp.js(f"{PIXEL}({hov!r})", sid)
                    b = cdp.js(f"{PIXEL}({got['pbg']!r})", sid)
                    self.assertGreaterEqual(sum(abs(x - y) for x, y in zip(a[:3], b[:3])), 6, f"{tag} {a} {b}")

    def test_the_open_page_keeps_its_square_edge_and_its_tint_while_hovered(self):
        with chrome() as cdp:
            for scheme in ("light", "dark"):
                for w in SIZES:
                    got, sid = self.load(cdp, w, scheme, "prototype-2.0")
                    tag = f"open hover {scheme} {w}"
                    self.hover(cdp, sid, ".set-chip[aria-current]")
                    r = cdp.js("(() => { const s = getComputedStyle(document.querySelector('.set-chip[aria-current]')); return [s.borderTopLeftRadius, s.borderTopRightRadius, s.borderBottomLeftRadius, s.borderBottomRightRadius, s.backgroundColor]; })()", sid)
                    self.assertEqual(r[:4], ["0px", "10px", "0px", "10px"], tag)
                    self.assertEqual(r[4], got["cbg"], tag)


if __name__ == "__main__":
    unittest.main()
