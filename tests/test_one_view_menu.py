"""#287, one View menu on the filter line: Layout (Table or Board), Group by and the board's swimlanes are in
the one View menu, as in the signed-off prototype (system/prototype/views.js, "one View menu: Group by, and on the board the
swimlanes"; docs/handoff/prototype-gap-list.md B-2 and B-17). The Group by button, the layout icons and the board's Swimlanes button
are gone; every entry works from the mouse and the keyboard (Down opens, arrows move, Enter picks, Esc closes with the focus back).

Run: python3 dev/run_tests.py test_one_view_menu
The real page in headless Chrome (required: these fail, never skip, without it) against the real server over a demo database.
1400 and 900 px, light and dark.
"""
import json
import unittest

from test_server import chrome, wait  # noqa: E402
from test_work_filters import click, key  # noqa: E402
from test_work_board_page import Base  # noqa: E402

KINDS = "[...document.querySelectorAll('#viewMenuList [role^=menuitem]')].map(b => b.dataset.kind)"
LABS = "[...document.querySelectorAll('#viewMenuList .lab')].map(l => l.textContent)"
GROUPS = ["workstream", "status", "due", "owner", "priority", "milestone", "type"]


class OneMenu(Base):
    def open_menu(self, cdp, sid):
        click(cdp, sid, "#viewMenu")
        self.until(cdp, sid, "!!document.querySelector('#viewMenuList')", "the View menu")

    def test_the_table_menu_holds_group_by_only_layout_is_the_two_icon_switch_beside_it(self):
        with chrome() as cdp:
            sid = self.visit(cdp)
            self.open_menu(cdp, sid)
            self.assertEqual(cdp.js(LABS, sid), ["Group by"], "row 812: Table and Board left the menu")
            kinds = cdp.js(KINDS, sid)
            self.assertEqual(kinds[:8], [f"group:{g}" for g in GROUPS + ["nothing"]])
            self.assertEqual(kinds[8:], [], "the saved-view actions are on the open tab's arrow and + New view now (#640)")
            self.assertFalse([k for k in kinds if k.startswith("lane:")], "no swimlanes in the table")
            self.assertEqual(cdp.js("[...document.querySelectorAll('#viewMenuList [role=group]')].map(g => document.getElementById(g.getAttribute('aria-labelledby')).textContent)", sid),
                             ["Group by"], "each set of choices is a named group of radio items")
            self.assertEqual(cdp.js("document.querySelectorAll('#viewMenuList [role=menuitemradio][aria-checked=true]').length", sid), 1, "one grouping is marked")

    def test_on_the_board_the_menu_adds_the_swimlanes_and_drops_nothing(self):
        with chrome() as cdp:
            sid = self.visit(cdp)
            self.board(cdp, sid, "status")
            self.open_menu(cdp, sid)
            self.assertEqual(cdp.js(LABS, sid), ["Group by", "Swimlanes"])
            kinds = cdp.js(KINDS, sid)
            self.assertNotIn("group:nothing", kinds)
            self.assertEqual([k for k in kinds if k.startswith("lane:")], ["lane:none", "lane:workstream", "lane:type"])
            self.assertEqual(cdp.js("[...document.querySelectorAll('#viewMenuList [data-kind^=\"lane:\"]')].map(b => b.textContent.replace('\\u2713', ''))", sid),
                             ["No lanes", "Workstream lanes", "Type lanes"], "the prototype's words")

    def only_the_archived_pill_in_the_bar(self, cdp, sid):
        # item 1067: the Archived pill is gone (is:archived replaces it), so the bar holds no .vctl wrapper at all
        got = cdp.js("[...document.querySelectorAll('.wbar .vctl')].map(v => [...v.children].map(c => c.className))", sid)
        self.assertEqual(got, [], "no wrapper: the Archived pill is gone and nothing else lives there")
        self.assertEqual(cdp.js("document.querySelectorAll('.wbar .vctl #group-by, .wbar .vctl [data-layout], .wbar .vctl [aria-label=Layout], .wbar .vctl [data-lay], .wbar .vctl #swimlanes, .wbar .vctl [aria-haspopup=menu]').length", sid), 0,
                         "no layout or group controls in it")

    def test_the_old_separate_controls_are_gone(self):
        with chrome() as cdp:
            sid = self.visit(cdp)
            self.assertEqual(cdp.js("document.querySelectorAll('#group-by, [data-layout]').length", sid), 0)
            self.assertEqual(cdp.js("document.querySelectorAll('.fline .vicons [data-lay]').length", sid), 2, "row 812: the two-icon switch is on the filter box line")
            self.only_the_archived_pill_in_the_bar(cdp, sid)
            self.board(cdp, sid, "status")
            self.assertEqual(cdp.js("document.querySelectorAll('#group-by, [data-layout], #swimlanes').length", sid), 0)
            self.only_the_archived_pill_in_the_bar(cdp, sid)
            self.assertEqual(cdp.js("document.querySelectorAll('#work .wbar [aria-haspopup=menu], #work .fline-wrap [aria-haspopup=menu], #work .lanebar [aria-haspopup=menu]').length", sid), 2, "View and the open tab's arrow, nothing else (row 813: no Freshness pill)")
            self.assertTrue(cdp.js("!!document.querySelector('.lanebar #board-full')", sid), "full screen stays on the board bar")

    def test_each_entry_works(self):
        with chrome() as cdp:
            sid = self.visit(cdp)
            self.view_pick(cdp, sid, "group:status")
            self.until(cdp, sid, "document.querySelector('#viewMenu').getAttribute('aria-label') === 'Group by: Status' && !!document.querySelector('tbody[data-group]')", "grouped by status")
            self.assertEqual(cdp.js("document.querySelector('#work-live').textContent", sid), "Grouped by Status.")
            self.view_pick(cdp, sid, "layout:board")
            self.until(cdp, sid, "!!document.querySelector('#work-board')", "the board")
            self.view_pick(cdp, sid, "lane:type")
            self.until(cdp, sid, "document.querySelectorAll('#work-board .lane-h').length > 0", "type lanes")
            self.assertEqual(cdp.js("document.querySelector('#viewMenu').getAttribute('aria-label')", sid), "Group by: Status, type lanes")
            self.view_pick(cdp, sid, "lane:none")
            self.until(cdp, sid, "!document.querySelector('#work-board .lane-h')", "no lanes")
            self.view_pick(cdp, sid, "layout:table")
            self.until(cdp, sid, "!!document.querySelector('table.items') && !document.querySelector('#work-board')", "the table")
            # a saved-view action from + New view
            click(cdp, sid, "#viewNew")
            self.until(cdp, sid, "[...document.querySelectorAll('.vtab')].some(t => t.textContent.startsWith('View 1'))", "the new view's tab")

    def test_the_keyboard_opens_moves_picks_and_closes(self):
        with chrome() as cdp:
            sid = self.visit(cdp)
            cdp.js("document.querySelector('#viewMenu').focus()", sid)
            key(cdp, sid, "ArrowDown")
            self.until(cdp, sid, "!!document.querySelector('#viewMenuList')", "Down opens the menu")
            self.assertEqual(cdp.js("document.activeElement.dataset.kind", sid), "group:workstream", "the first entry has the focus")
            key(cdp, sid, "ArrowDown")
            self.assertEqual(cdp.js("document.activeElement.dataset.kind", sid), "group:status")
            key(cdp, sid, "ArrowUp")
            key(cdp, sid, "ArrowUp")
            self.assertNotEqual(cdp.js("document.activeElement.dataset.kind", sid), "group:workstream", "Up wraps to the last entry")
            key(cdp, sid, "Home")
            self.assertEqual(cdp.js("document.activeElement.dataset.kind", sid), "group:workstream")
            key(cdp, sid, "Escape")
            self.until(cdp, sid, "!document.querySelector('#viewMenuList')", "Esc closes it")
            self.until(cdp, sid, "document.activeElement.id === 'viewMenu'", "the focus back on the button")
            # pick Group by: Status with arrows and Enter
            key(cdp, sid, "ArrowDown")
            self.until(cdp, sid, "!!document.querySelector('#viewMenuList')")
            key(cdp, sid, "ArrowDown")
            self.assertEqual(cdp.js("document.activeElement.dataset.kind", sid), "group:status")
            key(cdp, sid, "Enter")
            self.until(cdp, sid, "!document.querySelector('#viewMenuList')", "Enter picks and closes")
            self.until(cdp, sid, "document.querySelector('#viewMenu').getAttribute('aria-label') === 'Group by: Status' && !!document.querySelector('tbody[data-group]')", "grouped by status")
            self.until(cdp, sid, "document.activeElement.id === 'viewMenu'", "the focus back on the button after a pick")
            # and the board from the keyboard: the Board icon is a button, Enter or Space presses it
            cdp.js("document.querySelector('[data-lay=board]').focus()", sid)
            key(cdp, sid, "Enter")
            self.until(cdp, sid, "!!document.querySelector('#work-board')", "the board from the keyboard")

    def test_esc_in_full_screen_closes_the_menu_first(self):
        with chrome() as cdp:
            sid = self.visit(cdp)
            self.board(cdp, sid, "status")
            click(cdp, sid, "#board-full")
            self.until(cdp, sid, "document.body.classList.contains('board-full')")
            self.open_menu(cdp, sid)
            key(cdp, sid, "Escape")
            self.until(cdp, sid, "!document.querySelector('#viewMenuList')", "Esc closes the menu")
            self.assertTrue(cdp.js("document.body.classList.contains('board-full')", sid), "and leaves full screen alone")

    def test_the_menu_reads_and_fits_at_1400_and_900_in_light_and_dark(self):
        js = ("(() => { const lum = (c) => { const v = c.match(/[\\d.]+/g).slice(0, 3).map(Number).map((x) => { x /= 255; return x <= .03928 ? x / 12.92 : Math.pow((x + .055) / 1.055, 2.4); }); return .2126 * v[0] + .7152 * v[1] + .0722 * v[2]; };"
              " const bg = (e) => { while (e) { const b = getComputedStyle(e).backgroundColor; if (b && !/rgba\\(0, 0, 0, 0\\)|transparent/.test(b)) return b; e = e.parentElement; } return 'rgb(255, 255, 255)'; };"
              " const m = document.querySelector('#viewMenuList'), r = m.getBoundingClientRect();"
              " const ratios = [...m.querySelectorAll('[role^=menuitem], .lab')].map((b) => { const a = lum(getComputedStyle(b).color), z = lum(bg(b)), hi = Math.max(a, z), lo = Math.min(a, z); return (hi + .05) / (lo + .05); });"
              " return {left: r.left, right: r.right, w: innerWidth, sideways: document.documentElement.scrollWidth > innerWidth, min: Math.min(...ratios), n: ratios.length}; })()")
        for theme in ("light", "dark"):
            for width in (1400, 900):
                with self.subTest(theme=theme, width=width), chrome() as cdp:
                    sid = self.visit(cdp, width=width, height=800)
                    cdp.js(f"document.documentElement.dataset.theme = {json.dumps(theme)}", sid)
                    self.board(cdp, sid, "status")
                    cdp.js(f"document.documentElement.dataset.theme = {json.dumps(theme)}", sid)
                    self.open_menu(cdp, sid)
                    got = cdp.js(js, sid)
                    self.assertGreaterEqual(got["n"], 12, got)      # row 812: three fewer, the Layout label and its two entries
                    self.assertGreaterEqual(got["left"], 0, got)
                    self.assertLessEqual(got["right"], got["w"], got)
                    self.assertFalse(got["sideways"], got)
                    self.assertGreaterEqual(got["min"], 4.5, got)
                    self.assertTrue(wait(lambda: cdp.js("document.activeElement.closest('#viewMenuList') !== null", sid)), "the focus is in the menu")


if __name__ == "__main__":
    unittest.main()
