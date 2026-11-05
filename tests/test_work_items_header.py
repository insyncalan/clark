"""Release 1.0.3 UI Debt, the Work items header batch (rows 805, 808, 809, 812, 813, 807): browser tests.

Every test runs at 1400 and 900 px, in light and dark, in View and in Edit.

Run: python3 dev/run_tests.py test_work_items_header
Headless Chrome (required: fails, never skips, without it).
"""
import unittest

from test_server import chrome
from test_work_board_page import Base
from test_work_filters import click, key

CASES = [(w, s, e) for w in (1400, 900) for s in ("light", "dark") for e in (False, True)]


class Header(Base):
    def go(self, cdp, width, scheme, edit, **kw):
        sid = self.visit(cdp, width=width, edit=edit, **kw)
        cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme}]}, sid)
        return sid

    def each(self, check, **kw):
        """Run check(cdp, sid, width) at 1400 and 900, light and dark, View and Edit."""
        for width, scheme, edit in CASES:
            with self.subTest(width=width, scheme=scheme, edit=edit), chrome() as cdp:
                check(cdp, self.go(cdp, width, scheme, edit, **kw), width)

    # ---- row 805 ----
    def test_row_805_no_intro_sentence_and_no_count_line_and_no_gap_left(self):
        def check(cdp, sid, width):
            self.assertFalse(cdp.js("!!document.querySelector('#work-intro')", sid), "no intro sentence")
            self.assertFalse(cdp.js("/Select an item to open it beside/.test(document.querySelector('#work').textContent)", sid))
            # the count line is not drawn: what is left of it is clipped to a pixel, for a screen reader
            h = cdp.js("document.querySelector('#work-count').getBoundingClientRect().height", sid)
            self.assertLessEqual(h, 2, "no count line is drawn")
            self.assertFalse(cdp.js("!!document.querySelector('#work-list > .factive')", sid), "no empty row is left for it")
            gap = cdp.js("(() => { const a = document.querySelector('.fline-wrap').getBoundingClientRect(); "
                         "const t = [...document.querySelectorAll('#work-list > *')].find(e => e.getBoundingClientRect().height > 2 && !e.classList.contains('sr')); "
                         "return Math.round(t.getBoundingClientRect().top - a.bottom); })()", sid)
            self.assertLessEqual(gap, 12, f"the list follows the filter line closely ({gap}px)")
        self.each(check)

    # ---- row 808 ----
    def open_list(self, cdp, sid):
        click(cdp, sid, "#fline-input")
        cdp.js("document.querySelector('#fline-input').select()", sid)
        key(cdp, sid, "Backspace")
        self.until(cdp, sid, "document.querySelector('#fline-list')", "the suggestion list")

    def floats(self, cdp, sid, board):
        if board:
            self.board(cdp, sid, "status")
            cdp.js("document.activeElement.blur()", sid)
            self.until(cdp, sid, "!document.querySelector('#fline-list')", "the list closed")
        else:
            click(cdp, sid, "#fline-input")
            cdp.js("document.querySelector('#fline-input').select()", sid)
            key(cdp, sid, "Backspace")
            cdp.js("document.activeElement.blur()", sid)
            self.until(cdp, sid, "!document.querySelector('#fline-list')", "the list closed")
        probe = "(() => { const a = document.querySelector('#work-list').getBoundingClientRect().top, b = document.querySelector('#work-list').getBoundingClientRect().height; return [Math.round(a), Math.round(b)]; })()"
        before = cdp.js(probe, sid)
        self.open_list(cdp, sid)
        self.assertEqual(cdp.js(probe, sid), before, "opening the list moves nothing and changes no height")
        got = cdp.js("(() => { const l = document.querySelector('#fline-list'), s = getComputedStyle(l), r = l.getBoundingClientRect(), b = document.querySelector('[data-fline]').getBoundingClientRect(), w = document.querySelector('#work-list').getBoundingClientRect();"
                     " return {pos: s.position, z: +s.zIndex, gap: Math.round(r.top - b.bottom), left: Math.round(r.left - b.left), over: r.bottom > w.top}; })()", sid)
        self.assertEqual(got["pos"], "absolute")
        self.assertGreater(got["z"], 25)
        self.assertLessEqual(got["gap"], 8)
        self.assertEqual(got["left"], 0)
        self.assertTrue(got["over"], "the list lies over the page below the box")

    def test_row_808_the_suggestion_list_floats_over_the_table_and_pushes_nothing(self):
        self.each(lambda cdp, sid, width: self.floats(cdp, sid, False))

    def test_row_808_the_suggestion_list_floats_over_the_board_and_pushes_nothing(self):
        self.each(lambda cdp, sid, width: self.floats(cdp, sid, True))

    # ---- row 809 ----
    def test_row_809_views_are_text_tabs_on_a_rule_the_same_for_made_and_user_views(self):
        mine = [{"id": "mine", "name": "My own", "line": "is:open type:risk"}]

        def check(cdp, sid, width):
            cdp.js("localStorage.setItem('clark.fviews', JSON.stringify({ABC: %s}))" % __import__("json").dumps(mine), sid)
            self.reload(cdp, sid)
            self.until(cdp, sid, "document.querySelector('.vtab[data-view-id=mine]')", "the made view")
            probe = ("(() => { const css = (e) => getComputedStyle(e), box = document.querySelector('.fvrow'), bb = box.getBoundingClientRect();"
                     " const one = (e) => { const c = css(e), r = e.getBoundingClientRect(); return {radius: c.borderTopLeftRadius, bg: c.backgroundColor, l: c.borderLeftWidth, t: c.borderTopWidth, b: c.borderBottomWidth, bc: c.borderBottomColor, color: c.color, w: c.fontWeight, gap: Math.round(r.bottom - bb.bottom)}; };"
                     " const tabs = [...document.querySelectorAll('.vtab')];"
                     " return {rule: css(box).borderBottomWidth, ruleColor: css(box).borderBottomColor, tabs: tabs.map((e) => [e.dataset.viewId, e.getAttribute('aria-pressed') === 'true', one(e)]),"
                     " badge: one(document.querySelector('.vtab em')), made: one(document.querySelector('.vtab[data-view-id=mine]')), neu: one(document.querySelector('#viewNew')),"
                     " scrolls: /auto|scroll/.test(css(document.querySelector('.vtabs')).overflowX), fits: document.documentElement.scrollWidth <= innerWidth}; })()")
            got = cdp.js(probe, sid)
            self.assertEqual(got["rule"], "1px", "a thin rule under the row")
            self.assertTrue(got["scrolls"], "the row scrolls inside its own box")
            self.assertTrue(got["fits"], "the page does not scroll sideways")
            for vid, on, st in got["tabs"] + [("new", False, got["neu"])]:
                self.assertEqual(st["radius"], "0px", f"{vid}: not a pill")
                self.assertEqual((st["l"], st["t"]), ("0px", "0px"), f"{vid}: no outline box")
                self.assertEqual(st["bg"], "rgba(0, 0, 0, 0)", f"{vid}: no fill")
                if on:
                    self.assertEqual(st["b"], "2px", "the open tab has the underline")
                    self.assertEqual(st["gap"], 0, "and it sits on the rule (its foot is the rule's foot)")
                    self.assertNotEqual(st["bc"], "rgba(0, 0, 0, 0)")
                else:
                    self.assertEqual(st["bc"], "rgba(0, 0, 0, 0)", f"{vid}: no underline")
            self.assertEqual([t[1] for t in got["tabs"]].count(True), 1, "one tab is open")
            self.assertEqual(got["made"]["radius"], got["tabs"][0][2]["radius"], "the made view looks like a predefined one")
            self.assertEqual(got["made"]["b"], got["tabs"][0][2]["b"])
            self.assertEqual(got["made"]["color"], got["neu"]["color"], "a view that is not open is drawn in the one muted colour")
            self.assertNotEqual(got["badge"]["radius"], "0px", "the count is in a round badge")
            self.assertNotEqual(got["badge"]["bg"], "rgba(0, 0, 0, 0)")
            # the made view can be opened, and then it is the one with the underline
            click(cdp, sid, ".vtab[data-view-id=mine]")
            self.until(cdp, sid, "document.querySelector('.vtab[data-view-id=mine]').getAttribute('aria-pressed') === 'true'", "the made view is open")
            self.assertEqual(cdp.js("getComputedStyle(document.querySelector('.vtab[data-view-id=mine]')).borderBottomWidth", sid), "2px")
        self.each(check)

    # ---- row 812 ----
    def test_row_812_table_and_board_are_a_two_icon_switch_and_group_by_stays_in_the_view_menu(self):
        def check(cdp, sid, width):
            pair = ("[...document.querySelectorAll('#work .fvrow [role=group][aria-label=Layout] button')].map(b => [b.dataset.lay, b.getAttribute('aria-label'), b.title, b.getAttribute('aria-pressed'), b.textContent, !!b.querySelector('svg'),"
                    " Math.round(b.getBoundingClientRect().width), Math.round(b.getBoundingClientRect().height)])")
            got = cdp.js(pair, sid)
            self.assertEqual([g[:6] for g in got], [["table", "Table", "Table", "true", "", True], ["board", "Board", "Board", "false", "", True]], "icons, not words, named Table and Board")
            self.assertTrue(all(g[6] >= 32 and g[7] >= 28 for g in got), f"each icon is a target of a fair size: {got}")
            self.assertTrue(cdp.js("document.documentElement.scrollWidth <= innerWidth", sid), "the page does not scroll sideways")
            self.assertEqual(cdp.js("document.querySelectorAll('#work [aria-haspopup=menu]').length >= 1 && !document.querySelector('#work .fvrow [aria-label^=\"View:\"][data-lay]')", sid), True)
            # the View menu keeps Group by (and no Layout); its words and button name are unchanged
            click(cdp, sid, "#viewMenu")
            self.until(cdp, sid, "document.querySelector('#viewMenuList')", "the View menu")
            self.assertEqual(cdp.js("[...document.querySelectorAll('#viewMenuList .lab')].map(l => l.textContent)", sid), ["Group by"])
            self.assertEqual(cdp.js("document.querySelector('#viewMenu').getAttribute('aria-label')", sid), "View: table, grouped by Workstream")
            key(cdp, sid, "Escape")
            self.until(cdp, sid, "!document.querySelector('#viewMenuList')", "closed")
            # pressing Board: the board draws, the switch follows, and the menu gains the swimlanes; Table brings the table back
            click(cdp, sid, "#work [data-lay=board]")
            self.until(cdp, sid, "document.querySelector('#work-board')", "the board")
            self.assertEqual(self.checked(cdp, sid, "layout:"), ["layout:board"])
            click(cdp, sid, "#viewMenu")
            self.until(cdp, sid, "document.querySelector('#viewMenuList')", "the View menu on the board")
            self.assertEqual(cdp.js("[...document.querySelectorAll('#viewMenuList .lab')].map(l => l.textContent)", sid), ["Group by", "Swimlanes"])
            key(cdp, sid, "Escape")
            cdp.js("document.querySelector('#work [data-lay=table]').focus()", sid)
            key(cdp, sid, "Enter")
            self.until(cdp, sid, "document.querySelector('table.items') && !document.querySelector('#work-board')", "the table from the keyboard")
            self.assertEqual(self.checked(cdp, sid, "layout:"), ["layout:table"])
        self.each(check)


if __name__ == "__main__":
    unittest.main()
