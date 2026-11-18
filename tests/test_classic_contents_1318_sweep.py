"""Row 1318, killer sweep: tests for the survivors of a one-at-a-time mutation pass over the Classic Contents column (Contents.jsx,
Dashboard.jsx and the row's block in the Classic theme's rules.css). Chrome is required: these tests fail, never skip, without it.
Fictional data only.

Run: python3 dev/run_tests.py test_classic_contents_1318_sweep
"""
import unittest

from clark import page, theme
from test_inline_67 import size
from test_report_editor import Base
from test_server import chrome
import _testpage as testpage
import test_report_editor as tre

# A probe: the computed value of a CSS length or colour written as a var(), read back as the browser resolves it.
PROBE = ("function pv(prop, expr, host){var t=document.createElement('i'); t.style[prop]=expr; t.style.position='absolute'; t.style.visibility='hidden';"
         "(host || document.body).appendChild(t); var c=getComputedStyle(t)[prop]; t.remove(); return c;}")


def classic_html():
    return page.layer_theme(testpage.html(), theme.css("prototype-2.0"))


class Sweep(Base):
    def setUp(self):
        super().setUp()
        self.demo.action(description="Fictional open action", due_date="2030-01-05", owner="Sara Khan")
        self.s.close()
        self.s = tre.real_server(self.store.path, self.store.data_for, page_html=classic_html, seam=self.seam)
        self.addCleanup(self.s.close)

    def at(self, cdp, width, height=700):
        p = self.visit(cdp)
        size(cdp, p, width, height)
        p.until("document.querySelectorAll('#report .sec').length > 1", "the sections are drawn")
        p.js("window.scrollTo(0, 0)")
        return p

    # ---- the marked entry follows a SCROLLED page, with the bar's height now ----

    def test_a_scrolled_page_marks_the_section_under_the_line_not_the_one_at_the_top(self):
        with chrome() as cdp:
            p = self.at(cdp, 1400, 500)
            got = p.js(PROBE + "(function(){var bar = Math.round(document.querySelector('.top').getBoundingClientRect().height), vh = innerHeight, line = bar + (vh - bar) * 0.3,"
                       "ids = [...document.querySelectorAll('.cnt li button')].map(b => b.dataset.id), out = null;"
                       "for (var k = 1; k < ids.length && !out; k++) { var el = document.getElementById('sec-' + ids[k].replace(/[^A-Za-z0-9_-]/g, '-'));"
                       "if (!el) continue; var top = el.getBoundingClientRect().top + scrollY, s = Math.round(top - line + 15);"
                       "if (s > 40 && s + vh < document.documentElement.scrollHeight - 2) out = [ids[k], ids[k - 1], s]; } return out; })()")
            self.assertIsNotNone(got, "a scrolled position with a section 15 px above the line was found")
            want, before, s = got
            p.js(f"window.scrollTo(0, {s})")
            p.until(f"(document.querySelector('.cnt li button.on') || {{dataset: {{}}}}).dataset.id === {want!r}", f"{want} is marked, not {before}")
            self.assertEqual(p.js("document.querySelectorAll('.cnt li button.on').length"), 1)

    def test_a_section_just_below_the_line_is_not_marked_yet(self):
        with chrome() as cdp:
            p = self.at(cdp, 1400, 500)
            got = p.js("(function(){var bar = Math.round(document.querySelector('.top').getBoundingClientRect().height), vh = innerHeight, line = bar + (vh - bar) * 0.3,"
                       "ids = [...document.querySelectorAll('.cnt li button')].map(b => b.dataset.id), out = null;"
                       "for (var k = 1; k < ids.length && !out; k++) { var el = document.getElementById('sec-' + ids[k].replace(/[^A-Za-z0-9_-]/g, '-'));"
                       "if (!el) continue; var top = el.getBoundingClientRect().top + scrollY, s = Math.round(top - line - 15);"
                       "if (s > 40 && s + vh < document.documentElement.scrollHeight - 2) out = [ids[k], ids[k - 1], s]; } return out; })()")
            self.assertIsNotNone(got)
            want, before, s = got
            p.js(f"window.scrollTo(0, {s})")
            p.until(f"(document.querySelector('.cnt li button.on') || {{dataset: {{}}}}).dataset.id === {before!r}", f"{before} is still marked, not {want}")

    def test_after_a_resize_from_1400_to_900_the_mark_uses_the_bar_height_of_900(self):
        with chrome() as cdp:
            p = self.at(cdp, 1400, 700)
            bar = "Math.round(document.querySelector('.top').getBoundingClientRect().height)"
            p.until(f"{bar} === 85", "the bar is 85 px at 1400")
            size(cdp, p, 900, 700)
            p.until(f"{bar} === 129", "the bar is 129 px at 900")
            got = p.js("(function(){var vh = innerHeight, line85 = 85 + (vh - 85) * 0.3,"
                       "ids = [...document.querySelectorAll('.cnt li button')].map(b => b.dataset.id), out = null;"
                       "for (var k = 1; k < ids.length && !out; k++) { var el = document.getElementById('sec-' + ids[k].replace(/[^A-Za-z0-9_-]/g, '-'));"
                       "if (!el) continue; var top = el.getBoundingClientRect().top + scrollY, s = Math.round(top - line85 - 15);"
                       "if (s > 0 && s + vh < document.documentElement.scrollHeight - 2) out = [ids[k], ids[k - 1], s]; } return out; })()")
            self.assertIsNotNone(got)
            want, before, s = got
            p.js(f"window.scrollTo(0, {s})")
            p.until(f"(document.querySelector('.cnt li button.on') || {{dataset: {{}}}}).dataset.id === {want!r}", "the 129 px bar sets the line")

    def test_at_the_bottom_of_the_page_the_last_entry_is_marked(self):
        with chrome() as cdp:
            p = self.at(cdp, 1400, 500)
            last = p.js("[...document.querySelectorAll('.cnt li button')].pop().dataset.id")
            p.js("window.scrollTo(0, document.documentElement.scrollHeight)")
            p.until(f"(document.querySelector('.cnt li button.on') || {{dataset: {{}}}}).dataset.id === {last!r}", "the last entry is marked at the bottom")

    def test_a_resize_alone_moves_the_mark(self):
        with chrome() as cdp:
            p = self.at(cdp, 1400, 500)
            got = p.js("(function(){var bar = Math.round(document.querySelector('.top').getBoundingClientRect().height), line500 = bar + (500 - bar) * 0.3,"
                       "ids = [...document.querySelectorAll('.cnt li button')].map(b => b.dataset.id), out = null;"
                       "for (var k = 1; k < ids.length && !out; k++) { var el = document.getElementById('sec-' + ids[k].replace(/[^A-Za-z0-9_-]/g, '-'));"
                       "if (!el) continue; var top = el.getBoundingClientRect().top + scrollY, s = Math.round(top - line500 - 20);"
                       "if (s > 40 && s + 900 < document.documentElement.scrollHeight - 2) out = [ids[k], ids[k - 1], s]; } return out; })()")
            self.assertIsNotNone(got, "a section just below the line of a 500 px tall window was found")
            want, before, s = got
            p.js(f"window.scrollTo(0, {s})")
            p.until(f"(document.querySelector('.cnt li button.on') || {{dataset: {{}}}}).dataset.id === {before!r}", f"{before} is marked in the 500 px window")
            size(cdp, p, 1400, 900)      # the line moves down with the taller window; the scroll stays, so only the resize event can move the mark
            p.until(f"(document.querySelector('.cnt li button.on') || {{dataset: {{}}}}).dataset.id === {want!r}", "the resize alone moved the mark")

    def test_the_first_entry_is_marked_by_the_draw_itself_with_no_scroll_or_resize_after_it(self):
        with chrome() as cdp:
            p = self.at(cdp, 1400, 700)
            p.js("location.reload()")      # the device size stays, so nothing after the draw can move or resize the page
            p.until("document.querySelectorAll('.cnt li button').length > 1", "the column is drawn again")
            p.until("(document.querySelector('.cnt li button.on') || {}) === document.querySelector('.cnt li button')", "the first entry is marked by the draw")

    # ---- the column's look, value by value ----

    def test_the_boundary_is_1000_wide(self):
        with chrome() as cdp:
            p = self.at(cdp, 1000)
            self.assertEqual(p.js("getComputedStyle(document.querySelector('.cnt')).display"), "block")
            size(cdp, p, 999, 700)
            p.until("getComputedStyle(document.querySelector('.cnt')).display === 'none'", "hidden at 999")
            self.assertEqual(p.js("getComputedStyle(document.querySelector('.cnt-grid')).display"), "block")

    def test_the_grid_has_a_168_column_the_space_5_gap_and_a_flush_content_column(self):
        with chrome() as cdp:
            p = self.at(cdp, 1400)
            got = p.js(PROBE + "(function(){var g=document.querySelector('.cnt-grid'), n=document.querySelector('.cnt'), s=document.querySelector('.cnt-grid > .secs'), gs=getComputedStyle(g);"
                       "var gap=pv('width','var(--space-5)');"
                       "return [gs.gridTemplateColumns.split(' ')[0], gs.columnGap === gap, gs.alignItems, getComputedStyle(s).marginLeft,"
                       "Math.round(s.getBoundingClientRect().left - n.getBoundingClientRect().right) === Math.round(parseFloat(gap)),"
                       "Math.round(s.getBoundingClientRect().left - g.getBoundingClientRect().left) === 168 + Math.round(parseFloat(gap))];})()")
            self.assertEqual(got, ["168px", True, "start", "0px", True, True])

    def test_the_column_sticks_under_the_bar_and_may_scroll_inside_itself(self):
        with chrome() as cdp:
            p = self.at(cdp, 1400, 500)
            p.js("window.scrollTo(0, 300)")
            got = p.js(PROBE + "(function(){var n=document.querySelector('.cnt'), cs=getComputedStyle(n), bar=pv('width','var(--topbar)'), s4=parseFloat(pv('width','var(--space-4)')), s6=parseFloat(pv('width','var(--space-6)'));"
                       "return [Math.round(n.getBoundingClientRect().top - (parseFloat(bar) + s4)), cs.overflowY, cs.maxHeight === (innerHeight - parseFloat(bar) - s6) + 'px'];})()")
            self.assertEqual(got, [0, "auto", True])

    def test_the_heading_and_list_look(self):
        with chrome() as cdp:
            p = self.at(cdp, 1400)
            got = p.js(PROBE + "(function(){var h=document.querySelector('.cnt-h'), u=document.querySelector('.cnt ul'), hs=getComputedStyle(h), us=getComputedStyle(u);"
                       "return [hs.marginBottom === pv('width','var(--space-2)'), hs.letterSpacing === pv('letterSpacing','var(--tracking-caps)', h), hs.color === pv('color','var(--text-muted)'),"
                       "hs.fontWeight === pv('fontWeight','var(--weight-medium)'), hs.marginTop, us.listStyleType, us.marginTop, us.marginLeft, us.paddingLeft, us.paddingTop];})()")
            self.assertEqual(got, [True, True, True, True, "0px", "none", "0px", "0px", "0px", "0px"])

    def test_an_entry_look_resting_and_marked(self):
        with chrome() as cdp:
            p = self.at(cdp, 1400)
            got = p.js(PROBE + "(function(){var on=document.querySelector('.cnt li button.on'), b=document.querySelectorAll('.cnt li button')[1], s=getComputedStyle(b), m=getComputedStyle(on), sp=pv('width','var(--space-2)');"
                       "return [s.boxSizing, s.display, s.alignItems, Math.round(b.getBoundingClientRect().width) === Math.round(b.parentNode.getBoundingClientRect().width),"
                       "s.paddingLeft === sp, s.paddingRight === sp, s.paddingTop, s.color === pv('color','var(--text-muted)'), s.fontSize === pv('fontSize','var(--size-caption)'),"
                       "s.cursor, s.whiteSpace, s.overflow, s.textOverflow, s.borderLeftWidth, s.borderLeftStyle, s.borderLeftColor === 'rgba(0, 0, 0, 0)', s.fontWeight === pv('fontWeight','400'),"
                       "m.color === pv('color','var(--heading)'), m.fontWeight === pv('fontWeight','var(--weight-medium)')];})()")
            self.assertEqual(got, ["border-box", "flex", "center", True, True, True, "0px", True, True, "pointer", "nowrap", "hidden", "ellipsis", "2px", "solid", True, True, True, True])

    def test_a_long_title_is_cut_with_an_ellipsis_on_one_line(self):
        self.demo.plant_builtin_sections()
        ref = self.store.con.execute("SELECT id FROM report_sections WHERE project = 'ABC' AND type = 'actions'").fetchone()
        self.demo.update("report_sections", ref[0], {"title": "A fictional and very long section title that cannot fit in one hundred and sixty eight pixels"})
        with chrome() as cdp:
            p = self.at(cdp, 1400)
            got = p.js("(function(){var b=[...document.querySelectorAll('.cnt li button')].find(x => x.textContent.indexOf('fictional and very long') > -1);"
                       "return [b.scrollWidth > b.clientWidth, Math.round(b.getBoundingClientRect().height), Math.round(b.getBoundingClientRect().width) <= 168];})()")
            self.assertEqual(got, [True, 28, True])

    def test_the_focus_ring_is_drawn_inside_the_entry_in_the_focus_colour(self):
        with chrome() as cdp:
            p = self.at(cdp, 1400)
            got = p.js(PROBE + "(function(){var b=document.querySelector('.cnt li button'); b.focus(); var s=getComputedStyle(b); return [s.outlineOffset, s.outlineColor === pv('color','var(--focus)')];})()")
            self.assertEqual(got, ["-2px", True])

    def test_hover_darkens_an_entry_to_the_text_colour(self):
        with chrome() as cdp:
            p = self.at(cdp, 1400)
            x, y = p.js("(function(){var r=document.querySelectorAll('.cnt li button')[1].getBoundingClientRect(); return [r.left + 10, r.top + 10];})()")
            cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y}, p.sid)
            p.until(PROBE + "getComputedStyle(document.querySelectorAll('.cnt li button')[1]).color === pv('color','var(--text)')", "hovered entry takes the text colour")

    def test_print_leaves_the_column_out_and_the_grid_a_block(self):
        with chrome() as cdp:
            p = self.at(cdp, 1400)
            cdp.call("Emulation.setEmulatedMedia", {"media": "print"}, p.sid)
            p.until("getComputedStyle(document.querySelector('.cnt')).display === 'none'", "the column is out of print")
            self.assertEqual(p.js("getComputedStyle(document.querySelector('.cnt-grid')).display"), "block")

    def test_print_all_leaves_the_column_out(self):
        with chrome() as cdp:
            p = self.at(cdp, 1400)
            p.js("document.documentElement.classList.add('print-all')")
            self.assertEqual(p.js("getComputedStyle(document.querySelector('.cnt')).display"), "none")


if __name__ == "__main__":
    unittest.main()
