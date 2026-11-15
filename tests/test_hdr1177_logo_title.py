"""Item 1177: the editor dashboard's one slim sticky header holds the logo, the project name and the line "Weekly report" then
"Week ending DD-MM-YYYY"; the separate project banner is gone. Widths 1400 and 900 only. Chrome is required: these tests fail, never skip.

Run: python3 dev/run_tests.py test_hdr1177_logo_title
"""
import unittest

from test_inline_67 import size
from test_report_editor import Base
from test_server import chrome

WIDTHS = ((1400, 147, 22, 85), (900, 120, 18, 129))      # width, logo box w, logo box h, header height (item 1177; row 1212: the logo box is 147 x 22 and 120 x 18, the option C reference)
TOP = "document.querySelector('.top')"
LOGO = f"(function(){{var r={TOP}.querySelector('.logo').getBoundingClientRect(); return [Math.round(r.width), Math.round(r.height)];}})()"
LINE = ("(function(){var d=document.querySelector('.top .hdr-date'); if (!d) return ''; "
        "return d.parentElement.textContent.replace(/\\s+/g, ' ').trim();})()")


class HdrLogoTitle(Base):
    def at(self, cdp, p, w):
        size(cdp, p, w, 800)
        p.until("document.fonts.status === 'loaded'", "the fonts are loaded (a late font moves a wrap, so the header height waits for them)")
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

    def test_row_1212_the_project_name_is_24_px_in_the_heading_font_at_weight_800(self):
        """Row 1212: the option C reference shows the name in the heading font (Montserrat, 800), 24 px: 348 px wide for Mossgrove Customer Portal (measured 345.5 in the image)."""
        with chrome() as cdp:
            p = self.visit(cdp)
            for w, _, _, _ in WIDTHS:
                self.at(cdp, p, w)
                got = p.js("(function(){var s=getComputedStyle(document.querySelector('.top .hdr-project')); return [s.fontSize, s.fontWeight, s.fontFamily.split(',')[0].trim(), s.letterSpacing];})()")
                self.assertEqual(got, ["24px", "800", "Montserrat", "-0.24px"], f"{w}: the project name is 24 px, weight 800, Montserrat, -0.01em")

    def test_row_1212_the_tabs_end_10_px_above_the_bottom_edge_at_1400(self):
        """Row 1212: the underline (the bottom of the selected tab) sits 10 px above the bottom edge of the 85 px header (reference: 10 px measured in the image at 2x)."""
        with chrome() as cdp:
            p = self.visit(cdp)
            self.at(cdp, p, 1400)
            got = p.js(f"(function(){{var t={TOP}.getBoundingClientRect(), a=document.querySelector('.top .tab[aria-selected=\"true\"]').getBoundingClientRect(); "
                       "return Math.round(t.bottom - a.bottom);})()")
            self.assertEqual(got, 10, "the underline is 10 px above the bottom edge")

    def test_row_1212_no_second_logo_in_the_icon_group(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            for w, _, _, _ in WIDTHS:
                self.at(cdp, p, w)
                p.js("document.documentElement.style.setProperty('--image-logo', 'url(\"data:image/gif;base64,R0lGODlhAQABAAAAACw=\")'); document.documentElement.style.setProperty('--cover-logo-room', '192px')")
                got = p.js("(function(){var e=document.querySelector('.top .hdr-end'); return [getComputedStyle(e,'::before').content, getComputedStyle(e).paddingLeft];})()")
                self.assertEqual(got, ["none", "0px"], f"{w}: the icon group has no logo box in front of it")


if __name__ == "__main__":
    unittest.main()
