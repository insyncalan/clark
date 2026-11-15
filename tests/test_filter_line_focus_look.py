"""Issue 1137: the Work items filter line. The filter field keeps its normal look while the cursor is in it (no purple ring, no coloured
border, no shadow; the ruling: "nothing at all"), and the icons stand beside the box, not inside it, at the place they had.
1400 and 900 px, light and dark.

Run: python3 dev/run_tests.py test_filter_line_focus_look
"""
import re
import unittest
from pathlib import Path

from test_server import chrome  # noqa: E402
from test_work_board_page import Base  # noqa: E402

CSS = (Path(__file__).resolve().parent.parent / "src" / "clark" / "page" / "shell.css").read_text(encoding="utf-8")

LOOK = ("(() => { const b = document.querySelector('#work .fline'), s = getComputedStyle(b); "
        "return {outline: s.outlineStyle + ' ' + s.outlineWidth, shadow: s.boxShadow, border: s.borderTopColor, bg: s.backgroundColor}; })()")
GEO = ("(() => { const row = document.querySelector('#work .fline-row').getBoundingClientRect(), box = document.querySelector('#work .fline').getBoundingClientRect(), "
       "ids = ['#work .vicons [data-lay=table]', '#work .vicons [data-lay=board]', '#viewMenu'], "
       "icons = ids.map(q => { const e = document.querySelector(q); return e ? Math.round(e.getBoundingClientRect().left - row.left) : null; }), "
       "last = document.querySelector('#viewMenu').getBoundingClientRect(); "
       "return {icons, fromRight: Math.round(row.right - last.right), "
       "inside: document.querySelectorAll('#work .fline [data-lay], #work .fline #viewMenu').length, "
       "boxW: box.width, rowW: row.width, boxRight: box.right, firstIcon: Math.min(...ids.map(q => document.querySelector(q).getBoundingClientRect().left)), "
       "wide: document.documentElement.scrollWidth > innerWidth}; })()")


class FocusLook(Base):
    def test_focused_field_has_no_ring_shadow_or_darker_border(self):
        for width in (1400, 900):
            for scheme in ("light", "dark"):
                with self.subTest(width=width, scheme=scheme), chrome() as cdp:
                    sid = self.visit(cdp, width=width)
                    cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme}]}, sid)
                    cdp.js("document.activeElement && document.activeElement.blur()", sid)
                    before = cdp.js(LOOK, sid)
                    cdp.js("document.querySelector('#fline-input').focus()", sid)
                    self.until(cdp, sid, "document.activeElement.id === 'fline-input'", "the cursor in the field")
                    after = cdp.js(LOOK, sid)
                    self.assertTrue(after["outline"].startswith("none") or after["outline"].endswith(" 0px"), f"no outline: {after}")
                    self.assertEqual(after["shadow"], "none", "no ring drawn as a shadow")
                    self.assertEqual(after, before, "the box looks the same with and without the cursor in it")

    def test_icons_are_beside_the_box_and_keep_their_place(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.visit(cdp, width=width)
                g = cdp.js(GEO, sid)
                self.assertEqual(g["inside"], 0, "no icon is inside the filter box element")
                self.assertNotIn(None, g["icons"], "all five icons are on the line")
                self.assertEqual(g["fromRight"], 11, "the last icon ends 11 px from the line's right edge, where it ended inside the old box")
                self.assertLess(g["boxW"], g["rowW"] - 100, "the box is smaller than the line by the icons' room")
                self.assertLessEqual(g["boxRight"], g["firstIcon"], "the box ends before the first icon")
                self.assertEqual(g["icons"], sorted(g["icons"]), "the icons keep their order")
                self.assertFalse(g["wide"], "the page does not scroll sideways")
                cdp.js("document.querySelector('#fline-input').focus()", sid)
                self.until(cdp, sid, "document.activeElement.id === 'fline-input'", "the cursor in the field")
                self.assertEqual(cdp.js(GEO, sid)["icons"], g["icons"], "the icons do not move when the field has the cursor")

    def test_the_shared_style_has_no_focus_colour_for_the_box(self):
        self.assertIsNone(re.search(r"\.fline(\.on)?:focus-within\s*[,{]", CSS))
        self.assertIsNone(re.search(r"\.fline\.on\s*[,{]", CSS))
        self.assertIn(".fline.bad:focus-within", CSS, "a word the line cannot use still turns the box red")


if __name__ == "__main__":
    unittest.main()
