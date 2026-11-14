"""Item 1177, the slim sticky header: everything that sticks under it uses its real height. --topbar equals the header's height, the
contents strip sits directly under it, the selection bar and the jump margins do not hide a heading, in board view the board starts at
the header's bottom, and in full screen the header is hidden. Header heights: 85 px at 1400, 129 px at 900.

Run: python3 dev/run_tests.py test_hdr1177_offsets
Browser tests: headless Chrome through the harness against a real server, fictional data, at 1400 and 900 px only.
"""
import unittest

from test_inline_67 import size
from test_report_editor import Base
from test_server import chrome
from test_work_board_page import Base as BoardBase

SIZES = (1400, 900)
HEIGHT = {1400: 85, 900: 129}
TOP = "document.querySelector('.top').getBoundingClientRect()"
VAR = "parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--topbar'))"


class Offsets(Base):
    def test_the_topbar_variable_equals_the_header_height(self):      # item 1177
        with chrome() as cdp:
            p = self.visit(cdp)
            for w in SIZES:
                size(cdp, p, w)
                p.js("window.scrollTo(0, 0)")
                p.until(f"Math.round({TOP}.height) === {HEIGHT[w]}", f"the header is {HEIGHT[w]} px at {w}")
                got = p.js(f"[{VAR}, {TOP}.height]")
                self.assertLess(abs(got[0] - got[1]), 1, f"--topbar {got[0]} is not the header height {got[1]} at {w}")

    def test_the_header_sticks_to_the_top_while_the_page_scrolls(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            for w in SIZES:
                size(cdp, p, w, 700)
                p.js("window.scrollTo(0, 400)")
                p.until("window.scrollY > 100", f"scrolled at {w}")
                got = p.js(f"[getComputedStyle(document.querySelector('.top')).position, {TOP}.top]")
                self.assertEqual(got, ["sticky", 0], f"the header is not stuck to the top at {w}: {got}")

    def test_the_contents_strip_sits_directly_under_the_header(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            for w in SIZES:
                size(cdp, p, w, 700)
                p.js("window.scrollTo(0, 0)")
                got = p.js(f"[document.querySelector('.toc').getBoundingClientRect().top, {TOP}.bottom]")
                self.assertLess(abs(got[0] - got[1]), 1.5, f"the contents strip top {got[0]} is not the header bottom {got[1]} at {w}")

    def test_the_selection_bar_sticks_at_the_header_bottom(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            for w in SIZES:
                size(cdp, p, w)
                got = p.js("(function(){var e=document.createElement('div'); e.id='sel-bar'; e.className='selbar'; document.body.appendChild(e);"
                           f"var s=getComputedStyle(e), r=[s.position, parseFloat(s.top), {TOP}.height]; e.remove(); return r;}})()")
                self.assertEqual(got[0], "sticky", f"the selection bar is not sticky at {w}")
                self.assertLess(abs(got[1] - got[2]), 1, f"the selection bar sticks at {got[1]}, the header is {got[2]} px at {w}")

    def test_a_jump_to_a_card_does_not_leave_its_heading_under_the_header(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            for w in SIZES:
                size(cdp, p, w, 700)
                for ref in ("ABC-S-008", "ABC-S-010", "ABC-S-004"):      # not 011: Supporting documents is not drawn in View with no document (test_report_editor.py line 413)
                    p.js("window.scrollTo(0, 0)")
                    p.js(f"document.querySelector('[data-id=\"{ref}\"]').scrollIntoView()")
                    p.until(f"document.querySelector('[data-id=\"{ref}\"]').getBoundingClientRect().top >= {TOP}.bottom - 1",
                            f"{ref} clears the header at {w}")
                    got = p.js(f"[document.querySelector('[data-id=\"{ref}\"]').getBoundingClientRect().top, {TOP}.bottom]")
                    self.assertGreaterEqual(got[0], got[1] - 1, f"{ref} top {got[0]} is under the header bottom {got[1]} at {w}")

    def test_the_jump_margin_is_at_least_the_header_height(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            for w in SIZES:
                size(cdp, p, w)
                got = p.js(f"[parseFloat(getComputedStyle(document.querySelector('[data-id=\"ABC-S-008\"]')).scrollMarginTop) || 0, {TOP}.height]")
                self.assertGreaterEqual(got[0] + 1, got[1], f"scroll margin {got[0]} is less than the header height {got[1]} at {w}")


class BoardOffsets(BoardBase):
    def test_in_board_view_the_board_starts_at_the_header_bottom(self):
        for w in SIZES:
            with chrome() as cdp:
                sid = self.visit(cdp, width=w)
                self.board(cdp, sid, "status")
                got = cdp.js("(() => { window.scrollTo(0, 0); return [document.querySelector('#work-board').getBoundingClientRect().top, "
                             "document.querySelector('.top').getBoundingClientRect().bottom]; })()", sid)
                self.assertLess(abs(got[0] - got[1]), 40, f"the board top {got[0]} is not near the header bottom {got[1]} at {w}")
                top = cdp.js("(() => { const b = document.querySelector('#work-board'); const s = getComputedStyle(b); "
                             "return [s.position, parseFloat(s.top)]; })()", sid)
                var = cdp.js(f"{VAR}", sid)
                if top[0] == "sticky":
                    self.assertLess(abs(top[1] - var), 1, f"the board sticks at {top[1]}, --topbar is {var} at {w}")

    def test_in_full_screen_the_header_is_hidden(self):
        for w in SIZES:
            with chrome() as cdp:
                sid = self.visit(cdp, width=w)
                self.board(cdp, sid, "status")
                cdp.js("document.querySelector('#board-full').click()", sid)
                self.until(cdp, sid, "document.body.classList.contains('board-full')", f"full screen at {w}")
                got = cdp.js("(() => { const t = document.querySelector('.top'); const r = t.getBoundingClientRect(); "
                             "return [getComputedStyle(t).display === 'none' || getComputedStyle(t).visibility === 'hidden' || r.bottom <= 0]; })()", sid)
                self.assertEqual(got, [True], f"the header is still showing in full screen at {w}")


if __name__ == "__main__":
    unittest.main()
