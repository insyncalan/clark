"""The narrow contents button: in a real window: at 900 px the contents rail is an "On this page" button at the bottom right, and at
1400 px the rail is as it was. Chrome is required: these tests fail, never skip, without it.

Run: python3 dev/run_tests.py test_toc_button
The source-only checks are in test_toc_button_source.py.
"""
import unittest

from test_inline_67 import size
from test_report_editor import Base
from test_server import chrome

BTN = "document.querySelector('.toc-lines')"
OPEN = "document.querySelector('.toc').classList.contains('open')"


class TocButton(Base):
    def at(self, cdp, width):
        p = self.visit(cdp)
        size(cdp, p, width, 700)
        p.js("window.scrollTo(0, 0)")
        return p

    def test_at_900_it_is_a_button_at_the_bottom_right_and_the_lines_are_gone(self):
        # The gap is measured from the edge a person sees: clientWidth leaves out a drawn (Linux, Windows) scrollbar, which
        # innerWidth counts, so the same 16 px holds with or without one.
        with chrome() as cdp:
            p = self.at(cdp, 900)
            got = p.js(f"(function(){{var r={BTN}.getBoundingClientRect(), s=getComputedStyle({BTN}), t=document.querySelector('.toc-lbl');"
                       "return [Math.round(document.documentElement.clientWidth - r.right), Math.round(innerHeight - r.bottom), r.height >= 24, r.width >= 24, "
                       f"parseFloat(getComputedStyle(t).fontSize) >= 13, t.textContent, {BTN}.getAttribute('aria-expanded'), "
                       f"[...document.querySelectorAll('.toc-lines i')].every(i => getComputedStyle(i).display === 'none'), s.borderTopWidth];}})()")
            self.assertEqual(got, [16, 16, True, True, True, "On this page", "false", True, "1px"])

    def test_at_1400_it_is_the_thin_rail_at_the_right_edge_with_no_words(self):
        with chrome() as cdp:
            p = self.at(cdp, 1400)
            got = p.js(f"(function(){{var r={BTN}.getBoundingClientRect(), t=document.querySelector('.toc-lbl');"
                       "return [getComputedStyle(t).display, getComputedStyle(document.querySelector('.toc-ico')).display, "
                       f"r.right <= innerWidth, r.top > 100, [...document.querySelectorAll('.toc-lines i')].every(i => getComputedStyle(i).display !== 'none')];}})()")
            self.assertEqual(got, ["none", "none", True, True, True])

    def test_at_900_hover_and_plain_focus_do_not_open_it_but_a_click_does_and_again_shuts_it(self):
        with chrome() as cdp:
            p = self.at(cdp, 900)
            p.js("document.querySelector('.toc').dispatchEvent(new MouseEvent('mouseenter'))")
            p.js(f"{BTN}.focus()")
            self.assertFalse(p.js(OPEN), "hover and focus alone leave it shut")
            p.js(f"{BTN}.click()")
            p.until(OPEN, "a click opens it")
            self.assertEqual(p.js(f"{BTN}.getAttribute('aria-expanded')"), "true")
            p.js(f"{BTN}.click()")
            p.until(f"!{OPEN}", "a second click shuts it")
            self.assertEqual(p.js(f"{BTN}.getAttribute('aria-expanded')"), "false")

    def test_at_900_escape_closes_it_and_the_focus_is_back_on_the_button(self):
        with chrome() as cdp:
            p = self.at(cdp, 900)
            p.js(f"{BTN}.focus()")                 # a click from a person puts the focus on the button; a scripted click does not
            p.js(f"{BTN}.click()")
            p.until(OPEN, "open")
            p.key("ArrowDown", code="ArrowDown", vk=40)
            p.until("document.activeElement.matches('.toc li button')", "the arrow moves into the list")
            p.key("Escape", code="Escape", vk=27)
            p.until(f"!{OPEN}", "Escape shuts it")
            self.assertTrue(p.js("document.activeElement.matches('.toc-lines')"), "the focus is back on the button")
            p.key("Tab", code="Tab", vk=9)
            self.assertFalse(p.js("!!document.activeElement.closest('.toc-card')"), "Tab does not go into the shut list")

    def test_at_900_choosing_an_item_goes_to_the_section_and_its_heading_takes_focus(self):
        with chrome() as cdp:
            p = self.at(cdp, 900)
            p.js(f"{BTN}.click()")
            p.until(OPEN, "open")
            p.js("document.querySelector('.toc li button[data-id=\"ABC-S-008\"]').click()")
            p.until("window.scrollY > 0", "the page scrolled")
            p.until(f"!{OPEN}", "the list shut")
            self.assertEqual(p.js("document.activeElement.dataset.id"), "ABC-S-008", "the section has the focus")

    def test_at_900_a_click_outside_closes_it(self):
        with chrome() as cdp:
            p = self.at(cdp, 900)
            p.js(f"{BTN}.click()")
            p.until(OPEN, "open")
            # The page's listener is added just after it opens; press again on each poll until it has taken effect.
            p.until("(document.querySelector('h1').dispatchEvent(new PointerEvent('pointerdown', {bubbles: true})), "
                    f"!{OPEN})", "a click elsewhere shuts it")

    def test_at_900_the_open_list_and_button_fit_in_both_colours(self):
        with chrome() as cdp:
            p = self.at(cdp, 900)
            for scheme in ("light", "dark"):
                p.js(f"document.documentElement.dataset.theme = '{scheme}'")
                p.js(f"{BTN}.click()")
                p.until(OPEN + " && getComputedStyle(document.querySelector('.toc-card')).opacity === '1'", f"{scheme}: open")
                box = p.js("(function(){var r=document.querySelector('.toc-card').getBoundingClientRect(), b=document.querySelector('.toc-lines').getBoundingClientRect();"
                           "return [r.left >= 0, r.right <= innerWidth, r.top >= 0, r.bottom <= b.top, document.documentElement.scrollWidth <= innerWidth];})()")
                self.assertEqual(box, [True] * 5, f"{scheme}: the list sits inside the window, above the button")
                p.js(f"{BTN}.click()")
                p.until(f"!{OPEN}", f"{scheme}: shut")


if __name__ == "__main__":
    unittest.main()
