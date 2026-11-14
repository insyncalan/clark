"""Item 1177: the editor dashboard has ONE slim sticky header (class top): sticky at top 0, 85 px high at 1400 and 129 px at 900,
still at the top after the page is scrolled, and the only element with that class. Chrome is required: these tests fail, never skip, without it.

Run: python3 dev/run_tests.py test_hdr1177_height
"""
from test_inline_67 import size
from test_report_editor import Base
from test_server import chrome

HEIGHTS = {1400: 85, 900: 129}
TOP = "document.querySelector('.top')"


class HeaderHeight(Base):
    def test_there_is_exactly_one_element_with_class_top(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            for w in HEIGHTS:
                size(cdp, p, w)
                self.assertEqual(p.js("document.querySelectorAll('.top').length"), 1, f"{w}: one .top element")

    def test_the_header_is_sticky_at_top_0_above_the_page(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            for w in HEIGHTS:
                size(cdp, p, w)
                got = p.js(f"(function(){{var s=getComputedStyle({TOP}); return [s.position, s.top, parseInt(s.zIndex, 10)];}})()")
                self.assertEqual(got, ["sticky", "0px", 30], f"{w}: sticky, top 0, z-index 30")

    def test_the_header_is_85_px_high_at_1400_and_129_px_at_900(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            for w, h in HEIGHTS.items():
                size(cdp, p, w)
                got = p.js(f"Math.round({TOP}.getBoundingClientRect().height)")
                self.assertEqual(got, h, f"{w}: header height {got}, wanted {h}")

    def test_the_header_stays_at_the_top_after_scrolling_800_px_at_1400_and_900(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            for w, h in HEIGHTS.items():
                size(cdp, p, w, 900)
                p.js("window.scrollTo(0, 800)")
                p.until("window.scrollY >= 700", f"{w}: the page scrolled")
                got = p.js(f"(function(){{var r={TOP}.getBoundingClientRect(), e=document.elementFromPoint(r.left + 40, r.top + r.height / 2);"
                           "return [Math.round(r.top), Math.round(r.height), !!(e && e.closest('.top'))];})()")
                self.assertEqual(got, [0, h, True], f"{w}: after scrolling the header is at top 0, {h} high and on top, got {got}")
                p.js("window.scrollTo(0, 0)")
