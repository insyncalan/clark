"""Item 1177: the View | Edit switch is a floating icon pill (#mode-pill), fixed just below the sticky header, right side, icon-only.
Chrome is required: these tests fail, never skip, without it.

Run: python3 dev/run_tests.py test_hdr1177_pill
"""
import unittest

from test_inline_67 import size
from test_report_editor import Base
from test_server import chrome

PILL = "document.querySelector('#mode-pill')"
MODE = "document.querySelector('#report').dataset.mode"
WIDTHS = (1400, 900)


class FloatingPill(Base):
    def at(self, cdp, p, w):
        size(cdp, p, w, 700)
        p.js("window.scrollTo(0, 0)")
        p.until(f"!!{PILL}", f"{w}: the pill is drawn")

    def test_the_pill_exists_once_and_is_fixed_with_a_z_index_between_the_toc_and_the_header(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            for w in WIDTHS:
                self.at(cdp, p, w)
                got = p.js(f"(function(){{var s=getComputedStyle({PILL}); return [document.querySelectorAll('#mode-pill').length, s.position, parseInt(s.zIndex, 10)];}})()")
                self.assertEqual(got[:2], [1, "fixed"], f"{w}: one pill, position fixed, got {got}")
                self.assertTrue(26 <= got[2] <= 29, f"{w}: z-index must be 26..29, got {got[2]}")

    def test_the_pill_sits_just_below_the_header_on_the_right_side(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            for w in WIDTHS:
                self.at(cdp, p, w)
                got = p.js(f"(function(){{var r={PILL}.getBoundingClientRect(), h=document.querySelector('.top').getBoundingClientRect();"
                           "return [r.top - h.bottom, r.left + r.width / 2 > innerWidth / 2, r.right <= innerWidth, r.width > 0 && r.height > 0];})()")
                self.assertTrue(0 <= got[0] <= 24, f"{w}: pill top must be 0..24 px under the header bottom, got {got[0]}")
                self.assertEqual(got[1:], [True, True, True], f"{w}: pill in the right half and inside the viewport, got {got}")

    def test_the_two_buttons_are_icon_only_with_a_tooltip_and_the_eye_and_pencil_svgs(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            for w in WIDTHS:
                self.at(cdp, p, w)
                got = p.js(f"[...{PILL}.querySelectorAll('button')].map(b => [b.dataset.mode, b.textContent.trim(), !!b.querySelector('svg'), b.title, "
                           "b.getBoundingClientRect().width > 0])")
                self.assertEqual(got, [["view", "", True, "View", True], ["edit", "", True, "Edit", True]], f"{w}: icon-only View and Edit, got {got}")

    def test_aria_pressed_follows_the_mode_when_edit_and_view_are_clicked(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            self.at(cdp, p, 1400)
            pressed = f"[...{PILL}.querySelectorAll('button')].map(b => b.dataset.mode + b.getAttribute('aria-pressed'))"
            self.assertEqual(p.js(pressed), ["viewtrue", "editfalse"], "view mode: View pressed")
            p.js(f"{PILL}.querySelector('[data-mode=edit]').click()")
            p.until(f"{MODE} === 'edit'", "edit")
            self.assertEqual(p.js(pressed), ["viewfalse", "edittrue"], "edit mode: Edit pressed")
            p.js(f"{PILL}.querySelector('[data-mode=view]').click()")
            p.until(f"{MODE} === 'view'", "view")
            self.assertEqual(p.js(pressed), ["viewtrue", "editfalse"], "back in view mode: View pressed")

    def test_the_pill_keeps_its_viewport_place_and_stays_visible_after_scrolling_1500px(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            for w in WIDTHS:
                self.at(cdp, p, w)
                box = f"(function(){{var r={PILL}.getBoundingClientRect(); return [Math.round(r.top), Math.round(r.left), Math.round(r.width), Math.round(r.height)];}})()"
                before = p.js(box)
                p.js("window.scrollTo(0, 1500)")
                p.until("window.scrollY > 500", f"{w}: scrolled down")
                after = p.js(box)
                self.assertEqual(after, before, f"{w}: pill box after scroll {after} must equal {before}")
                shown = p.js(f"(function(){{var r={PILL}.getBoundingClientRect(), e=document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2); "
                             f"return !!e && {PILL}.contains(e);}})()")
                self.assertTrue(shown, f"{w}: the pill is the topmost thing at its centre after scrolling")


if __name__ == "__main__":
    unittest.main()
