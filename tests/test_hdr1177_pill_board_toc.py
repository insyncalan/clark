"""Item 1177: the floating View/Edit pill (#mode-pill) against the contents strip (.toc) and against the board view. Chrome is required:
these tests fail, never skip, without it. Widths 1400 and 900 only.

Run: python3 dev/run_tests.py test_hdr1177_pill_board_toc
"""
import unittest

import test_work_board_page as wb
from test_inline_67 import size
from test_report_editor import Base
from test_server import chrome

PILL = "document.querySelector('#mode-pill')"
TOC = "document.querySelector('nav.toc')"
SHOWN = ("(function(){var e=" + PILL + "; if (!e) return false; var s=getComputedStyle(e), r=e.getBoundingClientRect();"
         "return s.display !== 'none' && s.visibility !== 'hidden' && Number(s.opacity) > 0 && r.width > 0 && r.height > 0;})()")


setUpModule, tearDownModule = wb.setUpModule, wb.tearDownModule


class PillAgainstTheStrip(Base):
    def test_the_pill_is_above_the_contents_strip_and_below_the_header_in_the_stack(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            for w in (1400, 900):
                size(cdp, p, w, 700)
                p.until(f"!!{PILL} && !!{TOC}", f"{w}: the pill and the strip are drawn")
                z = p.js(f"(function(){{var z=function(e){{return parseInt(getComputedStyle(e).zIndex, 10);}}; return [z({TOC}), z({PILL}), z(document.querySelector('header.top'))];}})()")
                self.assertTrue(z[0] < z[1] < z[2], f"{w}: strip, pill, header z-index must rise in that order, got {z}")

    def test_the_pill_does_not_cover_the_strip_closed_or_open(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            for w in (1400, 900):
                size(cdp, p, w, 700)
                p.until(f"!!{PILL} && !!{TOC}", f"{w}: drawn")
                gap = ("(function(){var a=" + PILL + ".getBoundingClientRect(), b=" + TOC + ".getBoundingClientRect();"
                       "return a.right <= b.left || b.right <= a.left || a.bottom <= b.top || b.bottom <= a.top;})()")
                self.assertTrue(p.js(gap), f"{w}: the pill and the closed strip do not overlap")
                p.js(f"if (!{TOC}.classList.contains('open')) {TOC}.querySelector('.toc-lines').click()")
                p.until(f"{TOC}.classList.contains('open')", f"{w}: the strip opened")
                self.assertTrue(p.js(gap), f"{w}: the pill and the open strip do not overlap")
                p.js("document.activeElement.blur()")


class PillInTheBoardView(wb.Base):
    def test_no_pill_in_the_board_view_or_the_full_screen_board_and_it_is_back_on_the_dashboard(self):
        with wb.shared.page() as cdp:
            for w in (1400, 900):
                sid = self.visit(cdp, width=w)
                self.board(cdp, sid, "status", lane="workstream")
                self.assertEqual(cdp.js("document.querySelectorAll('#mode-pill').length", sid), 0, f"{w}: no pill in the board view")
                cdp.js("document.querySelector('#board-full').click()", sid)
                self.until(cdp, sid, "document.body.classList.contains('board-full')", f"{w}: full screen on")
                self.assertEqual(cdp.js("document.querySelectorAll('#mode-pill').length", sid), 0, f"{w}: no pill in the full-screen board")
                cdp.js("document.querySelector('#board-full').click()", sid)
                self.until(cdp, sid, "!document.body.classList.contains('board-full')", f"{w}: full screen off")
                cdp.js("document.querySelector('.tab[data-view=\"dashboard\"]').click()", sid)
                self.until(cdp, sid, "!!document.querySelector('#mode-pill') && getComputedStyle(document.querySelector('#mode-pill')).display !== 'none'", f"{w}: the pill is back on the dashboard")


if __name__ == "__main__":
    unittest.main()
