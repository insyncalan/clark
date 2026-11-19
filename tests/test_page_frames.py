"""Row 832: the pages that were wrapped in a white bordered card (Work items, Milestones, Use cases, the Settings head) sit straight on the
tinted page. Each test runs at 1400 and 900 px, light and dark, in View and in Edit.

Run: python3 dev/run_tests.py test_page_frames
Headless Chrome (required: fails, never skips, without it).
"""
import unittest

from test_server import chrome
from test_work_board_page import Base

CASES = [(w, s, e) for w in (1400, 900) for s in ("light", "dark") for e in (False, True)]
SETTINGS_CASES = [c for c in CASES if not c[2]]       # row 826: Settings has no View | Edit switch, so there is no Edit to test there
FLAT = ("(sel) => { const e = document.querySelector(sel), c = getComputedStyle(e), r = e.getBoundingClientRect(), m = document.querySelector('main'), mc = getComputedStyle(m), mr = m.getBoundingClientRect();"
        " return {bg: c.backgroundColor, border: [c.borderTopWidth, c.borderRightWidth, c.borderBottomWidth, c.borderLeftWidth].join(' '), shadow: c.boxShadow, pad: [c.paddingTop, c.paddingRight, c.paddingLeft].join(' '),"
        " w: Math.round(r.width), inner: Math.round(mr.width - parseFloat(mc.paddingLeft) - parseFloat(mc.paddingRight)), top: Math.round(r.top)}; }")


class Frames(Base):
    def flat(self, hash_, sel, wait_for, cases=CASES):
        for width, scheme, edit in cases:
            with self.subTest(width=width, scheme=scheme, edit=edit), chrome() as cdp:
                sid = self.visit(cdp, width=width, edit=edit, hash_=hash_, wait_for=wait_for)
                cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme}]}, sid)
                got = cdp.js(f"({FLAT})({__import__('json').dumps(sel)})", sid)
                self.assertEqual(got["bg"], "rgba(0, 0, 0, 0)", "no white panel")
                self.assertEqual(got["border"], "0px 0px 0px 0px", "no border")
                self.assertEqual(got["shadow"], "none", "no shadow")
                self.assertEqual(got["pad"], "0px 0px 0px", "no padding that frames the page body")
                self.assertEqual(got["w"], got["inner"], "the content is as wide as the page's own column")

    def test_row_832_work_items_has_no_wrapping_card(self):
        self.flat("#work&p=ABC", "#work", "#work-list")

    def test_row_832_milestones_has_no_wrapping_card_but_the_viewer_keeps_its_own(self):
        self.flat("#milestones&p=ABC", "#milestones", ".msv")
        for width, scheme, edit in CASES:
            with self.subTest(width=width, scheme=scheme, edit=edit), chrome() as cdp:
                sid = self.visit(cdp, width=width, edit=edit, hash_="#milestones&p=ABC", wait_for=".msv")
                cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme}]}, sid)
                got = cdp.js("(() => { const c = getComputedStyle(document.querySelector('#milestones .msv')); return [c.borderTopWidth, c.boxShadow !== 'none', c.backgroundColor !== 'rgba(0, 0, 0, 0)']; })()", sid)
                self.assertEqual(got, ["1px", True, True], "the viewer and timeline keep a card")
                self.assertTrue(cdp.js("document.documentElement.scrollWidth <= innerWidth", sid))

    def test_row_832_use_cases_has_no_wrapping_card(self):
        self.flat("#usecases&p=ABC", "#usecases", "#usecases")

    def test_row_832_the_settings_head_has_no_card_but_the_cards_below_keep_theirs(self):
        self.flat("#settings&p=ABC", ".set-head", ".set-head", SETTINGS_CASES)
        for width, scheme, edit in SETTINGS_CASES:
            with self.subTest(width=width, scheme=scheme, edit=edit), chrome() as cdp:
                sid = self.visit(cdp, width=width, edit=edit, hash_="#settings&p=ABC", wait_for=".set-head")
                cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme}]}, sid)
                got = cdp.js("(() => { const c = getComputedStyle(document.querySelector('.frame.setting')); return [c.borderTopWidth, c.backgroundColor !== 'rgba(0, 0, 0, 0)']; })()", sid)
                # Row 841 took the Settings cards' shadow away on purpose; a card is its border and its own surface.
                self.assertEqual(got, ["1px", True], "a Settings card is still a card")


if __name__ == "__main__":
    unittest.main()
