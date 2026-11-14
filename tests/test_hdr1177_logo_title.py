"""Item 1177: the editor dashboard's one slim sticky header holds the logo, the project name and the line "Weekly report" then
"Week ending DD-MM-YYYY"; the separate project banner is gone. Widths 1400 and 900 only. Chrome is required: these tests fail, never skip.

Run: python3 dev/run_tests.py test_hdr1177_logo_title
"""
import unittest

from test_inline_67 import size
from test_report_editor import Base
from test_server import chrome

WIDTHS = ((1400, 147, 22, 85), (900, 120, 18, 129))      # width, logo box w, logo box h, header height (item 1177)
TOP = "document.querySelector('.top')"
LOGO = f"(function(){{var r={TOP}.querySelector('.logo').getBoundingClientRect(); return [Math.round(r.width), Math.round(r.height)];}})()"
LINE = ("(function(){var d=document.querySelector('.top .hdr-date'); if (!d) return ''; "
        "return d.parentElement.textContent.replace(/\\s+/g, ' ').trim();})()")


class HdrLogoTitle(Base):
    def at(self, cdp, p, w):
        size(cdp, p, w, 800)
        p.js("window.scrollTo(0, 0)")

    def test_the_logo_box_is_147_by_22_at_1400_and_120_by_18_at_900(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            for w, lw, lh, _ in WIDTHS:
                self.at(cdp, p, w)
                self.assertEqual(p.js(LOGO), [lw, lh], f"{w}: the logo box should measure {lw}x{lh}")

    def test_the_header_is_85_px_high_at_1400_and_129_at_900_with_the_logo_inside(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            for w, _, _, h in WIDTHS:
                self.at(cdp, p, w)
                got = p.js(f"(function(){{var t={TOP}.getBoundingClientRect(); return [Math.round(t.height), !!{TOP}.querySelector('.logo')];}})()")
                self.assertEqual(got, [h, True], f"{w}: the header should be {h} px high and hold the logo")

    def test_the_project_name_is_one_button_in_the_header(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            for w, _, _, _ in WIDTHS:
                self.at(cdp, p, w)
                got = p.js("(function(){var n=document.querySelectorAll('.top .hdr-project'); "
                           "return [n.length, n.length ? n[0].tagName : '', n.length ? n[0].textContent.trim().length > 0 : false];})()")
                self.assertEqual(got, [1, "BUTTON", True], f"{w}: one non-empty project-name button in the header")

    def test_the_line_reads_weekly_report_then_week_ending_with_a_dmy_date_and_no_for(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            for w, _, _, _ in WIDTHS:
                self.at(cdp, p, w)
                got = p.js(f"(function(){{var l={LINE}; return [/^Weekly report\\b.*\\bWeek ending \\d\\d-\\d\\d-\\d{{4}}$/.test(l), /\\bfor\\b/i.test(l), "
                           "document.querySelector('.top .hdr-date').tagName];})()")
                self.assertEqual(got, [True, False, "BUTTON"], f"{w}: the line should read Weekly report then Week ending DD-MM-YYYY, no for")
                self.assertEqual(p.js(LINE)[:13], "Weekly report", f"{w}: the line starts with Weekly report")

    def test_weekly_report_comes_before_the_date_and_the_name_comes_before_the_line(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            for w, _, _, _ in WIDTHS:
                self.at(cdp, p, w)
                got = p.js("(function(){var n=document.querySelector('.top .hdr-project').getBoundingClientRect(), d=document.querySelector('.top .hdr-date').getBoundingClientRect(), "
                           "t=document.querySelector('.top').getBoundingClientRect(); "
                           "return [d.top >= n.top - 1, d.right <= t.right, n.left >= t.left, d.bottom <= t.bottom];})()")
                self.assertEqual(got, [True, True, True, True], f"{w}: name and date sit inside the header, date not above the name")

    def test_no_separate_project_banner_is_left_on_the_editor_dashboard(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            for w, _, _, _ in WIDTHS:
                self.at(cdp, p, w)
                got = p.js("[document.querySelectorAll('#cover').length, document.querySelectorAll('header.cover').length, "
                           "document.querySelectorAll('.cover-kind').length, document.querySelectorAll('#project-name').length]")
                self.assertEqual(got, [0, 0, 0, 1], f"{w}: no cover banner; the project name exists once (in the header)")
                self.assertTrue(p.js("!!document.querySelector('#project-name').closest('.top')"), f"{w}: the one project name is in the header")


if __name__ == "__main__":
    unittest.main()
