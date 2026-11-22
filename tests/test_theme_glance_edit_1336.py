"""Row 1336: the At a glance template in Edit under the Classic Theme, as Chrome computes it at 1400 and 900 px, light and dark: the tile has the
mock-up's inner padding (12px top and bottom, 16px sides), the status pill does not touch the tile border, and the status dot is 8x8 before the
label. The same page under Cards is the control (its own rules stay). The held items (bin on built-in tiles, grip and eye positions, help text,
empty fourth column) are not pinned here. Fictional data only.

Run: TZ=UTC python3 dev/run_tests.py test_theme_glance_edit_1336
"""
import json
import re
import unittest
from unittest import mock

from clark import page, theme
import _testpage as testpage
from _paths import SRC
from test_server import chrome
from test_tpl_glance_editor_1264 import Editor, tearDownModule  # noqa: F401

NAME = "prototype-2.0"
RULES = ((SRC / "clark" / "themes" / NAME / "rules.css").read_text(encoding="utf-8") + (SRC / "clark" / "themes" / NAME / "rules-2.css").read_text(encoding="utf-8"))
PROBE = """(function(sel){ var out = {}; var tiles = document.querySelectorAll(sel + ' [data-tile] .fig'); out.n = tiles.length; out.tiles = [];
  tiles.forEach(function(f){ var cs = getComputedStyle(f), fr = f.getBoundingClientRect(), dot = f.querySelector('.ragdot'), tw = f.querySelector('.tw'), d = dot ? dot.getBoundingClientRect() : null,
    t = tw ? tw.getBoundingClientRect() : null;
    out.tiles.push({ pad: [cs.paddingTop, cs.paddingRight, cs.paddingBottom, cs.paddingLeft].join(' '), border: cs.borderTopWidth,
      dot: d ? [Math.round(d.width), Math.round(d.height), getComputedStyle(dot).display] : null,
      pillGap: t ? Math.round((fr.right - t.right) * 10) / 10 : null, tag: tw ? tw.textContent.trim() : null }); });
  return out; })"""


class ClassicEdit(Editor):
    theme_name = NAME

    def setUp(self):
        orig = testpage.html
        css = theme.css(self.theme_name) if self.theme_name else None
        m = mock.patch.object(testpage, "html", lambda branding=None: page.layer_theme(orig(), css) if css else orig())
        m.start()
        self.addCleanup(m.stop)
        super().setUp()

    def look(self, width, dark):
        with chrome() as cdp:
            p = self.page(cdp, width, dark)
            return p.js(f"({PROBE})({json.dumps(self.sel())})")

    def test_T1_classic_tile_padding_is_12_and_16_and_the_pill_clears_the_border(self):
        for width in (1400, 900):
            for dark in (False, True):
                with self.subTest(width=width, dark=dark):
                    got = self.look(width, dark)
                    self.assertGreaterEqual(got["n"], 3, got)
                    for t in got["tiles"]:
                        self.assertEqual(t["pad"], "12px 16px 12px 16px", f"tile padding: {t}")
                    tagged = [t for t in got["tiles"] if t["tag"]]
                    self.assertTrue(tagged, "a tile with a status pill is drawn")
                    for t in tagged:
                        self.assertGreaterEqual(t["pillGap"], 16, f"the pill is 16px or more from the tile edge (border 1px + padding 16px): {t}")

    def test_T2_classic_status_dot_is_8_by_8_and_shown(self):
        for width in (1400, 900):
            with self.subTest(width=width):
                got = self.look(width, False)
                for t in got["tiles"]:
                    if t["dot"]:
                        self.assertEqual(t["dot"], [8, 8, "block"], f"status dot: {t}")
                self.assertTrue(any(t["dot"] for t in got["tiles"]), "a built-in tile with a dot is drawn")

    def test_T3_the_block_sits_before_the_row_1314_block_which_stays_the_last_row_block(self):
        rows = [l for l in RULES.split("\n") if l.startswith("/* Row ")]
        self.assertTrue(rows[-1].startswith("/* Row 1314"), rows[-1][:40])
        self.assertLess(RULES.index("/* Row 1336"), RULES.index("/* Row 1314"))
        self.assertIn(".tpl-edit-glancetemplate .glance .fig { padding: 12px 16px; }", RULES)
        block = RULES.split("/* Row 1336")[1].split("/* Row 1314")[0]
        self.assertIsNone(re.search(r"#\d", block), "no hash and digits in a CSS comment")


class CardsControl(ClassicEdit):
    theme_name = None

    def test_T1_classic_tile_padding_is_12_and_16_and_the_pill_clears_the_border(self):
        pass

    test_T2_classic_status_dot_is_8_by_8_and_shown = test_T1_classic_tile_padding_is_12_and_16_and_the_pill_clears_the_border
    test_T3_the_block_sits_before_the_row_1314_block_which_stays_the_last_row_block = test_T1_classic_tile_padding_is_12_and_16_and_the_pill_clears_the_border

    def test_C1_cards_keeps_its_own_edit_tile(self):
        got = self.look(1400, False)
        for t in got["tiles"]:
            self.assertEqual(t["pad"], "12px 16px 12px 16px", f"Cards tile padding as measured without the theme: {t}")
            self.assertEqual(t["dot"][:2] if t["dot"] else None, [8, 8], t)


if __name__ == "__main__":
    unittest.main()
