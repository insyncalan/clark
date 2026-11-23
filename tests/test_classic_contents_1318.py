"""Row 1318: the Classic theme has the left Contents column and no Minimap (no right rail, no narrow "On this page" button); Cards keeps
its Minimap and has no left column. Chrome is required: these tests fail, never skip, without it. Fictional data only.

Run: python3 dev/run_tests.py test_classic_contents_1318
"""
import unittest
from pathlib import Path

from clark import page, theme
from test_inline_67 import size
from test_report_editor import Base
from test_server import chrome
import _testpage as testpage
import test_report_editor as tre

NAMES = "[...document.querySelectorAll('.cnt li a')].map(b => b.textContent)"
TITLES = "[...document.querySelectorAll('#report .secs > .sec')].filter(s => !s.classList.contains('is-hidden')).map(s => s.id)"


def classic_html():
    return page.layer_theme(testpage.html(), theme.css("prototype-2.0"))


class Classic(Base):
    def setUp(self):
        super().setUp()
        self.demo.action(description="Fictional open action", due_date="2030-01-05", owner="Sara Khan")
        self.s.close()
        self.s = tre.real_server(self.store.path, self.store.data_for, page_html=classic_html, seam=self.seam)
        self.addCleanup(self.s.close)

    def at(self, cdp, width):
        p = self.visit(cdp)
        size(cdp, p, width, 700)
        p.until("document.querySelectorAll('#report .sec').length > 1", "the sections are drawn")
        p.js("window.scrollTo(0, 0)")
        return p

    def test_at_1400_the_column_is_168_wide_beside_the_content_and_has_the_rail_gone(self):
        with chrome() as cdp:
            p = self.at(cdp, 1400)
            got = p.js("(function(){var n=document.querySelector('.cnt'), g=document.querySelector('.cnt-grid'), h=n.querySelector('.cnt-h'), b=n.querySelector('li a'), hs=getComputedStyle(h);"
                       "return [Math.round(n.getBoundingClientRect().width), getComputedStyle(g).display, getComputedStyle(n).position, h.textContent, hs.textTransform, hs.fontSize,"
                       "Math.round(b.getBoundingClientRect().height), n.getBoundingClientRect().right <= document.querySelector('.secs').getBoundingClientRect().left,"
                       "!!document.querySelector('.toc'), !!document.querySelector('.toc-lines'), n.getAttribute('aria-label')];})()")
            self.assertEqual(got, [168, "grid", "sticky", "Contents", "uppercase", "13px", 28, True, False, False, "Contents"])

    def test_gap_at_1400_the_heading_spacing_is_1_04px_and_the_current_entry_is_the_text_colour(self):
        with chrome() as cdp:
            p = self.at(cdp, 1400)
            got = p.js("[getComputedStyle(document.querySelector('.cnt-h')).letterSpacing, getComputedStyle(document.querySelector('.cnt li a.on')).color]")
            self.assertEqual(got, ["1.04px", "rgb(29, 36, 51)"])

    def test_gap_at_1400_nothing_but_the_main_padding_sits_left_of_the_column(self):
        with chrome() as cdp:
            p = self.at(cdp, 1400)
            got = p.js("(function(){var n=document.querySelector('.cnt').getBoundingClientRect().left, m=document.querySelector('main'), r=document.querySelector('#report.frame'),"
                       "rs=getComputedStyle(r), s=document.querySelector('.cnt-grid > .secs').getBoundingClientRect().left;"
                       "return [Math.round(n), rs.paddingLeft, Math.round(m.getBoundingClientRect().left + parseFloat(getComputedStyle(m).paddingLeft)), Math.round(s)];})()")
            self.assertEqual(got[1], "0px", "the report frame has no left padding in front of the grid")
            self.assertEqual(got[0], got[2], "the column starts at the report frame's left edge (was x=105 = frame 77 + padding 28)")
            self.assertEqual(got[3], got[0] + 168 + 28, "the content starts 168 + 28 after the column")

    def test_the_entries_are_the_visible_sections_in_page_order_with_their_own_titles(self):
        with chrome() as cdp:
            p = self.at(cdp, 1400)
            heads = p.js("[...document.querySelectorAll('#report .secs > .sec')].map(s => (s.querySelector('h2, h3, .sec-title') || {}).textContent)")
            names = p.js(NAMES)
            self.assertGreaterEqual(len(names), 2)
            self.assertEqual(names, [h.strip() for h in heads][:len(names)] if all(heads) else names)
            ids = p.js("[...document.querySelectorAll('.cnt li a')].map(b => !!document.getElementById('sec-' + b.dataset.entry.replace(/[^A-Za-z0-9_-]/g, '-')))")
            self.assertTrue(all(ids))
            self.assertEqual(len(ids), p.js("document.querySelectorAll('#report .secs > .sec:not(.is-hidden)').length"))

    def test_the_first_entry_is_marked_at_the_top_with_a_2px_brand_rule_and_a_click_moves_the_mark(self):
        with chrome() as cdp:
            p = self.at(cdp, 1400)
            first = p.js("(function(){var b=document.querySelector('.cnt li a.on'), s=getComputedStyle(b);return [document.querySelectorAll('.cnt li a.on').length, b.parentNode.parentNode.querySelector('a')===b, b.getAttribute('aria-current'), s.borderLeftWidth, s.borderLeftColor === (function(){var t=document.createElement('i'); t.style.color='var(--brand-blue)'; document.body.appendChild(t); var c=getComputedStyle(t).color; t.remove(); return c;})()];})()")
            self.assertEqual(first, [1, True, "true", "2px", True])
            other = p.js("document.querySelector('.cnt li:last-child a').dataset.entry")
            p.js("document.querySelector('.cnt li:last-child a').click()")
            p.until(f"(document.querySelector('.cnt li a.on') || {{dataset: {{}}}}).dataset.entry === {other!r}", "the last entry is marked after a click")
            self.assertEqual(p.js("location.hash"), "#dashboard&p=ABC")      # the address is untouched

    def test_the_entries_are_links_that_take_the_keyboard_with_a_focus_ring(self):
        with chrome() as cdp:
            p = self.at(cdp, 1400)
            got = p.js("(function(){var b=document.querySelector('.cnt li a'); b.focus(); var s=getComputedStyle(b); return [b.tagName, b.getAttribute('href').startsWith('#sec-'), document.activeElement===b, s.outlineStyle, s.outlineWidth];})()")
            self.assertEqual(got, ["A", True, True, "solid", "2px"])

    def keep_only(self, n):
        rows = self.store.con.execute("SELECT id FROM report_sections WHERE project = 'ABC' AND type != 'reportheadline' AND (hidden IS NULL OR hidden = 0) ORDER BY sort_order, id").fetchall()      # row 1266: the Headline is not a Contents entry
        for (ref,) in rows[n:]:
            self.demo.update("report_sections", ref, {"hidden": 1})

    def test_with_two_visible_sections_the_list_has_two_entries_and_with_one_there_is_no_column(self):
        self.keep_only(2)
        with chrome() as cdp:
            p = self.visit(cdp)
            size(cdp, p, 1400, 700)
            p.until("document.querySelectorAll('#report .secs > .sec').length >= 1", "drawn")
            self.assertEqual(p.js("document.querySelectorAll('.cnt li a').length"), 2)
        self.keep_only(1)
        with chrome() as cdp:
            p = self.visit(cdp)
            size(cdp, p, 1400, 700)
            p.until("document.querySelectorAll('#report .secs > .sec').length >= 1", "drawn")
            self.assertEqual(p.js("[document.querySelectorAll('.cnt').length, document.querySelectorAll('.toc').length]"), [0, 0])

    def test_a_section_is_listed_under_its_own_title(self):
        self.demo.plant_builtin_sections()
        ref = self.store.con.execute("SELECT id FROM report_sections WHERE project = 'ABC' AND type = 'actions'").fetchone()
        self.demo.update("report_sections", ref[0], {"title": "Fictional actions title"})
        with chrome() as cdp:
            p = self.at(cdp, 1400)
            names = p.js(NAMES)
            self.assertIn("Fictional actions title", names)
            self.assertIn("Risks and issues", names)

    # ---- second sweep (k-1907): the survivors of 26 mutants, one assertion each ----

    # where the mark must be: the last section whose top is above the line 30% down the part of the window under the top bar (the minimap's rule, written again here)
    EXPECT = ("(function(){var bar=document.querySelector('.top').getBoundingClientRect().height, line=window.scrollY+bar+(innerHeight-bar)*0.3, cur=null;"
              "document.querySelectorAll('.cnt li a').forEach(function(a){var e=document.getElementById(a.getAttribute('href').slice(1)); if(e.getBoundingClientRect().top+window.scrollY<=line) cur=a.dataset.entry;}); return cur;})()")
    ON = "[...document.querySelectorAll('.cnt li a.on')].map(a => a.dataset.entry)"
    # scroll so the line sits `past` pixels below the top of the entry numbered k (the window height as it is now)
    PUT = ("(function(k, past){var bar=document.querySelector('.top').getBoundingClientRect().height, a=document.querySelectorAll('.cnt li a')[k], e=document.getElementById(a.getAttribute('href').slice(1)),"
           "top=e.getBoundingClientRect().top+window.scrollY; window.scrollTo(0, Math.round(top+past-bar-(innerHeight-bar)*0.3)); return window.scrollY;})")

    def still(self, p):
        # the scroll may glide: wait until it has stopped, so no half-way mark is read
        import time
        seen = []
        for _ in range(100):
            seen.append(p.js("window.scrollY"))
            if len(seen) >= 6 and len(set(seen[-6:])) == 1:
                break
            time.sleep(0.1)
        return seen[-1]

    def test_the_nav_landmark_and_one_current_mark_before_and_after_a_click(self):
        with chrome() as cdp:
            p = self.at(cdp, 1400)
            self.assertEqual(p.js("document.querySelector('.cnt').tagName"), "NAV")      # M06
            self.assertEqual(p.js("[document.querySelectorAll('.cnt [aria-current]').length, document.querySelectorAll('.cnt a.on').length]"), [1, 1])      # M03
            p.js("document.querySelector('.cnt li:last-child a').click()")
            other = p.js("document.querySelector('.cnt li:last-child a').dataset.entry")
            p.until(f"(document.querySelector('.cnt li a.on') || {{dataset: {{}}}}).dataset.entry === {other!r}", "the last entry is marked")
            self.assertEqual(p.js("[document.querySelectorAll('.cnt [aria-current]').length, document.querySelectorAll('.cnt a.on').length, document.querySelector('.cnt li:first-child a').hasAttribute('aria-current')]"),
                             [1, 1, False])      # M03 and M04: the mark left the first entry

    def test_the_mark_counts_the_sticky_bar_height_in_the_line(self):
        # M09 and M24: with the bar's height left out the line sits about 0.7 of the bar higher; put it 5px past a section top, where only the right line marks it
        with chrome() as cdp:
            p = self.at(cdp, 1400)
            k = 5      # row 1266: a full-width section (Use cases); entries 2 and 3 are the This week and Next week pair, which share one top
            p.js(self.PUT + f"({k}, 5)")
            self.assertGreater(self.still(p), 0)
            entry = p.js(f"document.querySelectorAll('.cnt li a')[{k}].dataset.entry")
            self.assertEqual(p.js(self.EXPECT), entry)
            self.assertGreater(p.js("document.querySelector('.top').getBoundingClientRect().height"), 20)
            p.until(f"{self.ON}.length === 1 && {self.ON}[0] === {entry!r}", "the section 5px past the line is marked")
            self.still(p)
            self.assertEqual(p.js(self.ON), [entry])

    def test_a_resize_moves_the_mark(self):
        # M07: a shorter window moves the 30% line up without any scroll
        with chrome() as cdp:
            p = self.at(cdp, 1400)
            k = 3
            p.js(self.PUT + f"({k}, 5)")
            self.still(p)
            entry = p.js(f"document.querySelectorAll('.cnt li a')[{k}].dataset.entry")
            p.until(f"{self.ON}[0] === {entry!r}", "the entry is marked")
            y = p.js("window.scrollY")
            size(cdp, p, 1400, 300)
            p.until(f"window.scrollY === {y} && {self.EXPECT} !== {entry!r}", "the line moved above the section")
            p.until(f"{self.ON}.length === 1 && {self.ON}[0] === {self.EXPECT}", "the mark follows the resize")
            self.still(p)
            self.assertEqual(p.js(self.ON), [p.js(self.EXPECT)])

    def test_edit_lists_no_hidden_section_and_the_mark_follows_a_hide(self):
        # M10: Edit draws a hidden section dimmed but the column must not list it; M08: hiding one while the page is open re-reads the entries
        with chrome() as cdp:
            p = self.at(cdp, 1400)
            p.edit()
            total = p.js("document.querySelectorAll('.secs > .sec').length")
            p.menu("ABC-S-007", "hide")
            p.until("!!document.querySelector('[data-id=\"ABC-S-007\"].is-hidden')", "the section is hidden")
            entries = p.js("[...document.querySelectorAll('.cnt li a')].map(a => a.dataset.entry)")
            self.assertEqual(len(entries), total - 1)      # M10
            self.assertNotIn("ABC-S-007", entries)
            before = entries[entries.index(p.js("document.querySelector('[data-id=\"ABC-S-007\"]').previousElementSibling.dataset.id"))]
            p.js("(function(){var e=document.querySelector('[data-id=\"ABC-S-007\"]'), bar=document.querySelector('.top').getBoundingClientRect().height;"
                 "window.scrollTo(0, Math.round(e.getBoundingClientRect().top+window.scrollY+20-bar-(innerHeight-bar)*0.3));})()")
            self.assertGreater(self.still(p), 100)      # clear of the top, where the first entry is marked whatever the sections are
            p.until(f"{self.ON}.length === 1 && {self.ON}[0] === {before!r}", "the section before the hidden one is marked")      # M08
            self.still(p)
            self.assertEqual(p.js(self.ON), [before])

    def test_the_column_has_a_gap_sticks_under_the_top_bar_and_scrolls_inside_a_short_window(self):
        with chrome() as cdp:
            p = self.at(cdp, 1400)
            probe = "(function(v){var t=document.createElement('i'); t.style.display='block'; t.style.width='var('+v+')'; document.body.appendChild(t); var w=t.getBoundingClientRect().width; t.remove(); return w;})"
            gap = p.js("document.querySelector('.secs').getBoundingClientRect().left - document.querySelector('.cnt').getBoundingClientRect().right")
            self.assertEqual(round(gap), 28)      # M16 (row 1318 by-eye: 28, was --space-5 = 24)
            self.assertGreater(gap, 0)
            p.js("window.scrollTo(0, 400)")
            p.until("window.scrollY === 400", "scrolled")
            off = p.js("document.querySelector('.cnt').getBoundingClientRect().top - document.querySelector('.top').getBoundingClientRect().bottom")
            self.assertEqual(round(off), round(p.js(probe + "('--space-4')")))      # M17
            size(cdp, p, 1400, 300)
            got = p.js("(function(){var n=document.querySelector('.cnt'), s=getComputedStyle(n); return [s.overflowY, s.maxHeight !== 'none', n.getBoundingClientRect().height <= innerHeight, n.scrollHeight > n.clientHeight];})()")
            self.assertEqual(got, ["auto", True, True, True])      # M18

    def test_the_current_entry_is_heavier_and_a_long_title_stays_on_one_clipped_line(self):
        ref = self.store.con.execute("SELECT id FROM report_sections WHERE project = 'ABC' AND type != 'reportheadline' AND (hidden IS NULL OR hidden = 0) ORDER BY sort_order, id LIMIT 1 OFFSET 1").fetchone()[0]
        self.demo.update("report_sections", ref, {"title": "A very long fictional section title that needs far more room than the narrow column gives it"})
        with chrome() as cdp:
            p = self.at(cdp, 1400)
            w = p.js("[getComputedStyle(document.querySelector('.cnt li a.on')).fontWeight, getComputedStyle(document.querySelector('.cnt li a:not(.on)')).fontWeight]")
            self.assertGreater(int(w[0]), int(w[1]))      # M19
            got = p.js("(function(){var a=document.querySelectorAll('.cnt li a')[1], s=getComputedStyle(a); return [s.whiteSpace, s.textOverflow, s.overflow, a.scrollHeight <= a.clientHeight, a.scrollWidth > a.clientWidth, Math.round(a.getBoundingClientRect().height)];})()")
            self.assertEqual(got, ["nowrap", "ellipsis", "hidden", True, True, 28])      # M20

    def test_by_eye_gaps_a_1px_rule_down_the_list_12px_link_padding_heading_weight_500_and_the_28px_gap(self):
        with chrome() as cdp:
            p = self.at(cdp, 1400)
            got = p.js("(function(){var u=document.querySelector('.cnt ul'), us=getComputedStyle(u), a=document.querySelector('.cnt li a:not(.on)'), as=getComputedStyle(a), h=getComputedStyle(document.querySelector('.cnt-h')), g=getComputedStyle(document.querySelector('.cnt-grid'));"
                       "return [us.borderLeftWidth, us.borderLeftStyle, us.borderLeftColor, as.paddingLeft, as.paddingRight, h.fontWeight, g.columnGap, u.getBoundingClientRect().height > 0];})()")
            border = p.js("(function(){var t=document.createElement('i'); t.style.color='var(--border)'; document.body.appendChild(t); var c=getComputedStyle(t).color; t.remove(); return c;})()")
            self.assertEqual(got, ["1px", "solid", border, "12px", "12px", "500", "28px", True])

    def test_the_mark_of_the_current_entry_sits_over_the_rule_not_beside_it(self):
        with chrome() as cdp:
            p = self.at(cdp, 1400)
            left = p.js("Math.round(document.querySelector('.cnt li a.on').getBoundingClientRect().left - document.querySelector('.cnt ul').getBoundingClientRect().left)")
            self.assertEqual(left, 0)      # the 2px mark covers the 1px rule: it starts at the list's outer edge, where the rule is

    def test_at_900_there_is_no_column_no_rail_and_no_on_this_page_button(self):
        with chrome() as cdp:
            p = self.at(cdp, 900)
            got = p.js("[getComputedStyle(document.querySelector('.cnt')).display, !!document.querySelector('.toc'), !!document.querySelector('.toc-lines'), !!document.querySelector('.toc-lbl')]")
            self.assertEqual(got, ["none", False, False, False])


class Cards(Base):
    def at(self, cdp, width):
        p = self.visit(cdp)
        size(cdp, p, width, 700)
        p.until("document.querySelectorAll('#report .sec').length > 1", "the sections are drawn")
        return p

    def test_cards_keeps_the_rail_and_the_pill_and_draws_no_column(self):
        with chrome() as cdp:
            for width in (1400, 900):
                p = self.at(cdp, width)
                got = p.js("[!!document.querySelector('.toc'), !!document.querySelector('.toc-lines'), !!document.querySelector('.cnt'), !!document.querySelector('.cnt-grid'), document.querySelector('#report').firstElementChild.className.indexOf('cnt')]")
                self.assertEqual(got[:4], [True, True, False, False], width)


class Source(unittest.TestCase):
    def test_the_column_css_is_in_the_theme_and_not_in_the_shell(self):
        rules = (theme.THEMES / "prototype-2.0" / "rules.css").read_text(encoding="utf-8")
        shell = (page.__file__ and __import__("pathlib").Path(page.__file__).parent / "shell.css").read_text(encoding="utf-8")
        self.assertIn(".cnt-grid", rules)
        self.assertIn("168px", rules)
        self.assertRegex(rules, r"@media \(min-width: 1000px\) \{\s*\.cnt-grid \{ display: grid;")      # M12 and M13: the column shows from 1000px, by the text of the breakpoint
        self.assertNotIn(".cnt", shell)

    def test_print_and_print_all_leave_the_column_out(self):
        rules = (theme.THEMES / "prototype-2.0" / "rules.css").read_text(encoding="utf-8")
        self.assertRegex(rules, r"@media print \{ \.cnt \{ display: none; \} \.cnt-grid \{ display: block; \} \}")      # M14
        self.assertIn("html.print-all .cnt { display: none; }", rules)

    def test_the_classic_check_is_the_theme_layer_and_the_minimap_is_left_out_there(self):
        from pathlib import Path
        src = Path(page.__file__).parent / "src" / "components"
        self.assertIn('getElementById("theme")', (src / "Contents.jsx").read_text(encoding="utf-8"))
        dash = (src / "Dashboard.jsx").read_text(encoding="utf-8")
        self.assertIn("{classic ? null : <Minimap", dash)
        self.assertIn("<Contents ", dash)


    def test_an_entry_does_not_carry_the_data_id_of_its_section(self):
        # a page looks a section up by [data-id=...]; the column comes before the sections, so a button carrying that attribute would be found first (row 1264 killers)
        src = (Path(__file__).resolve().parent.parent / "src/clark/page/src/components/Contents.jsx").read_text(encoding="utf-8")
        self.assertNotIn("data-id", src)


class PublishedFile(unittest.TestCase):
    def test_the_classic_file_has_the_contents_column_with_what_the_file_shows_and_no_minimap(self):
        # row 1318: the published file follows the theme too; a section left hidden is not listed (the minimap's own rule, kept)
        import shutil, tempfile
        from _demo import USER, DemoStore
        from clark import changes, publish
        from test_report_editor import EMPTY_BRANDING
        from test_server import wait
        demo = DemoStore()
        self.addCleanup(demo.close)
        store = demo.store
        change = changes.make_change(store.path, [], USER)
        for ref, edit in (("ABC-S-007", {"title": "Hidden secret plan", "hidden": 1}), ("ABC-S-006", {"title": "Shown plan"}),
                          ("ABC-S-003", {"body": "<p>Fictional header words.</p>"}), ("ABC-S-004", {"body": "<p>Fictional work this week.</p>"})):      # row 1266: the file leaves out an empty text section, so two have words
            status, body = change({"project": "ABC", "kind": "report_sections", "op": "update", "id": ref, "changes": edit})
            self.assertEqual(status, 200, body)
        folder = tempfile.mkdtemp(prefix="clark-pub-")
        self.addCleanup(shutil.rmtree, folder, True)
        done = publish.publish(store, "ABC", folder, by_user=USER, now="2026-10-28", branding=EMPTY_BRANDING)
        with chrome() as cdp:
            tid = next(t["targetId"] for t in cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
            sid = cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
            cdp.call("Emulation.setDeviceMetricsOverride", {"width": 1400, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
            cdp.call("Page.navigate", {"url": Path(done["path"]).as_uri()}, sid)
            self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('#report .secs > .sec').length >= 3", sid)), "the file drew its sections")
            self.assertEqual(cdp.js("[...document.querySelectorAll('.cnt li a')].map(b => b.textContent)", sid), ["Header", "This week", "Shown plan"])      # what the Classic file draws on clean main too
            self.assertEqual(cdp.js("!!document.querySelector('.toc') || !!document.querySelector('.toc-lines')", sid), False)
            self.assertEqual(cdp.js("document.querySelectorAll('.cnt button').length", sid), 0, "the entries are links, not buttons: a view-only file has none")
            self.assertEqual(cdp.js("[...document.querySelectorAll('.cnt li a')].every(a => document.getElementById(a.getAttribute('href').slice(1)))", sid), True, "each link points at a section of the file")


if __name__ == "__main__":
    unittest.main()
