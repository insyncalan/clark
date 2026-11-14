"""Item 1177: the floating View/Edit pill (#mode-pill) switches the mode like the V and E keys, the old switch in the report bar is
gone, and the pill hides in the full-screen board and while a dialog or a menu is open. Widths 1400 and 900 only.
Chrome is required: these tests fail, never skip, without it.

Run: python3 dev/run_tests.py test_hdr1177_pill_modes
"""
import unittest

from test_inline_67 import size
from test_report_editor import Base
from test_server import chrome

PILL = "document.querySelector('#mode-pill')"
MODE = "document.querySelector('#report').dataset.mode"
SHOWN = ("(function(){var e=" + PILL + "; if (!e) return false; var s=getComputedStyle(e), r=e.getBoundingClientRect();"
         "return s.display !== 'none' && s.visibility !== 'hidden' && Number(s.opacity) > 0 && s.pointerEvents !== 'none' && r.width > 0 && r.height > 0;})()")


class PillModes(Base):
    def test_clicking_edit_and_view_in_the_pill_switches_the_mode_at_both_widths(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            for w in (1400, 900):
                size(cdp, p, w, 700)
                p.until(SHOWN, f"{w}: the pill is shown")
                p.js(f"{PILL}.querySelector('[data-mode=edit]').click()")
                p.until(f"{MODE} === 'edit'", f"{w}: edit")
                got = p.js(f"[...{PILL}.querySelectorAll('button')].map(b => b.dataset.mode + b.getAttribute('aria-pressed'))")
                self.assertEqual(got, ["viewfalse", "edittrue"], f"{w}: aria-pressed follows edit")
                p.js(f"{PILL}.querySelector('[data-mode=view]').click()")
                p.until(f"{MODE} === 'view'", f"{w}: view")
                got = p.js(f"[...{PILL}.querySelectorAll('button')].map(b => b.dataset.mode + b.getAttribute('aria-pressed'))")
                self.assertEqual(got, ["viewtrue", "editfalse"], f"{w}: aria-pressed follows view")

    def test_the_pill_and_the_keys_agree_in_both_directions(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            p.key("e", code="KeyE", vk=69)
            p.until(f"{MODE} === 'edit'", "E key")
            self.assertEqual(p.js(f"{PILL}.querySelector('[data-mode=edit]').getAttribute('aria-pressed')"), "true", "the key moves the pill")
            p.js(f"{PILL}.querySelector('[data-mode=view]').click()")
            p.until(f"{MODE} === 'view'", "pill back to view")
            p.key("e", code="KeyE", vk=69)
            p.until(f"{MODE} === 'edit'", "E key after a pill click")
            p.key("v", code="KeyV", vk=86)
            p.until(f"{MODE} === 'view'", "V key")
            self.assertEqual(p.js(f"{PILL}.querySelector('[data-mode=view]').getAttribute('aria-pressed')"), "true", "the V key moves the pill")

    def test_the_old_switch_in_the_report_bar_is_gone(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            p.until(SHOWN, "the pill is shown")
            self.assertEqual(p.js("document.querySelectorAll('[aria-label=\"View or Edit\"]').length"), 0, "no old View or Edit group left")
            self.assertEqual(p.js("document.querySelectorAll('#report-bar [data-mode]').length"), 0, "no mode button left in the report bar")
            self.assertEqual(p.js("document.querySelectorAll('.top [data-mode]').length"), 0, "no mode button in the header")
            self.assertEqual(p.js("document.querySelectorAll('button[data-mode]').length"), 2, "exactly the pill's two mode buttons")      # buttons only: #report itself carries data-mode (Dashboard.jsx:100), as an attribute and not a switch

    def test_the_pill_is_fixed_above_the_page_and_below_the_header_with_icons_only(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            for w in (1400, 900):
                size(cdp, p, w, 700)
                p.until(SHOWN, f"{w}: shown")
                got = p.js(f"(function(){{var e={PILL}, s=getComputedStyle(e), r=e.getBoundingClientRect(); return [s.position, Number(s.zIndex), "
                           "e.textContent.trim(), e.querySelectorAll('button svg').length, r.right <= innerWidth, r.bottom <= innerHeight, r.top >= 0];})()")
                self.assertEqual(got[0], "fixed", f"{w}: position is fixed")
                self.assertTrue(26 <= got[1] <= 29, f"{w}: z-index {got[1]} is not 26..29")
                self.assertEqual(got[2:], ["", 2, True, True, True], f"{w}: no text, two svgs, inside the window")

    def test_the_pill_stays_put_when_the_page_scrolls(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            p.until(SHOWN, "shown")
            top = p.js(f"{PILL}.getBoundingClientRect().top")
            p.js("window.scrollTo(0, 600)")
            p.until("window.scrollY > 0", "scrolled")
            self.assertEqual(p.js(f"{PILL}.getBoundingClientRect().top"), top, "the pill did not move with the scroll")

    def test_the_pill_hides_in_the_full_screen_board(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            p.until(SHOWN, "shown first")
            p.js("document.body.classList.add('board-full')")
            p.until(f"!({SHOWN})", "hidden in full screen")
            p.js("document.body.classList.remove('board-full')")
            p.until(SHOWN, "back after full screen")

    def test_the_pill_hides_under_an_open_dialog_and_comes_back(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            p.until(SHOWN, "shown first")
            p.js("var d = document.createElement('div'); d.id = 'probe-1177'; d.setAttribute('role', 'dialog'); d.style.cssText = 'position:fixed;left:0;top:0;width:10px;height:10px'; document.body.appendChild(d)")
            p.until(f"!({SHOWN})", "hidden under a dialog")
            p.js("document.querySelector('#probe-1177').remove()")
            p.until(SHOWN, "back after the dialog")

    def test_the_pill_hides_while_the_profile_menu_is_open_and_comes_back(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            for w in (1400, 900):
                size(cdp, p, w, 700)
                p.until(SHOWN, f"{w}: shown first")
                p.js("document.querySelector('.top #profile-menu, .top #profile-btn').click()")
                p.until("!!document.querySelector('#profile-menu')", f"{w}: menu open")
                p.until(f"!({SHOWN})", f"{w}: hidden under the profile menu")
                p.key("Escape", code="Escape", vk=27)
                p.until("!document.querySelector('#profile-menu [role=menuitem], #profile-menu button')", f"{w}: menu shut")
                p.until(SHOWN, f"{w}: back after the menu")

    def test_the_pill_is_not_on_the_other_tabs(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            p.until(SHOWN, "shown on the dashboard")
            for name in ("work", "milestones", "usecases"):
                p.js(f"document.querySelector('.tab[data-view=\"{name}\"]').click()")
                p.until(f"document.querySelector('.tab[data-view=\"{name}\"]').getAttribute('aria-selected') === 'true'", f"{name} open")
                p.until(f"!({SHOWN})", f"{name}: no pill")


if __name__ == "__main__":
    unittest.main()
