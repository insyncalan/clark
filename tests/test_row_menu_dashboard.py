"""Row 1296: a right click on a work item row on the Dashboard opens the same menu the Work items list has (RowMenu.jsx).

Run: python3 dev/run_tests.py test_row_menu_dashboard
A real browser against a real server over the demo store. Same entries, same words, same order as the list; in View the changes are
listed but greyed (nothing is written), in Edit they are live. Desktop (1400) and 900 px.
"""
import json
import unittest

from _demo import DemoStore
from clark import draft_email_feed, page, publish

from test_item_rows import fill
from test_report_editor import Pg
from test_row_menu import right_click
from test_server import Running, chrome
from test_work_filters import click
import test_work_board_page as board
from test_server import wait
from test_work_items import page_target
import _testpage as testpage

WORDS = ["Draft email to Sara Khan", "Open the peek", "Change status", "Move due date", "Change owner", "Hide from the client",
         "Copy link to this item", "Copy ID", "Duplicate", "Archive"]
CHANGES = ("status", "due", "owner", "eye", "dup", "archive")


class DashboardRowMenu(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        fill(self.demo.store)
        self.demo.plant_builtin_sections()      # the rows are in the built-in sections, which a new project no longer has (row 1193)
        self.s = Running(data_for=self.demo.store.data_for, page_html=lambda: testpage.html())
        self.addCleanup(self.s.close)

    def entries(self, p):
        return p.js("[...document.querySelectorAll('.rowmenu [role=menuitem]')].map(b => [b.dataset.rm, b.querySelector('b').textContent, b.getAttribute('aria-disabled') === 'true'])")

    def show_menu(self, p, selector):
        right_click(p.cdp, p.sid, selector)
        p.until("!!document.querySelector('.rowmenu [role=menu]')", "the menu")

    def close(self, p):
        p.js("document.activeElement && document.activeElement.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true}))")
        p.until("!document.querySelector('.rowmenu')", "the menu closed")

    def test_the_dashboard_row_has_the_work_items_menu_in_view_and_in_edit(self):
        with chrome() as cdp:
            p = Pg.at(self, cdp, self.s.port)
            p.ready()
            sel = "[data-type=actions] .wl-row"
            for w in (1400, 900):
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                self.show_menu(p, sel)
                got = self.entries(p)
                words = [e[1] for e in got]
                self.assertTrue(words[0].startswith("Draft email to "), f"View at {w}: the first entry")
                self.assertEqual(words[1:len(WORDS)], WORDS[1:], f"View at {w}")
                self.assertEqual([e[1] for e in got][-1], "Archive", "no Delete while the page is read only")
                by = {e[0]: e for e in got}
                self.assertTrue(all(by[k][2] for k in CHANGES), f"View at {w}: the changes are listed and greyed")
                self.assertFalse(any(by[k][2] for k in ("peek", "link", "copyid")), "the reads stay live")
                self.assertTrue(p.js("(() => { const b = document.querySelector('.rowmenu .ddmenu').getBoundingClientRect(); return b.left >= 0 && b.right <= innerWidth && b.bottom <= innerHeight; })()"), "inside the window")
                self.close(p)
            p.edit()
            for w in (1400, 900):
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                self.show_menu(p, sel)
                got = self.entries(p)
                self.assertEqual([e[1] for e in got][1:], WORDS[1:] + ["Delete"], f"Edit at {w}")
                self.assertFalse(any(e[2] for e in got), "Edit: every entry is live")
                self.close(p)

    def test_escape_puts_focus_back_on_the_rows_id_button(self):
        """Row 1296 sweep: the Dashboard row hands focus back to its id button (homeOf), not to the row itself."""
        with chrome() as cdp:
            p = Pg.at(self, cdp, self.s.port)
            p.ready()
            p.edit()
            for w in (1400, 900):
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                self.show_menu(p, "[data-type=actions] .wl-row")
                self.close(p)
                self.assertTrue(p.js("(() => { const a = document.activeElement; return !!a && a.matches('li.wl-row .idl'); })()"), f"focus is on the id button at {w}")

    def test_the_keys_open_the_dashboard_row_menu_and_escape_returns_focus(self):
        """Row 1296: the menu key and Shift+F10 on a focused Dashboard row open the same menu as the right click (automated, no by-eye walk)."""
        with chrome() as cdp:
            p = Pg.at(self, cdp, self.s.port)
            p.ready()
            p.edit()
            for w in (1400, 900):
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                for name, shift in (("F10", True), ("ContextMenu", False)):
                    p.js("document.querySelector('[data-type=actions] li.wl-row .idl').focus()")
                    # a synthetic keydown: a real key press also makes the browser send a contextmenu event, which would open the menu by the other path
                    p.js(f"document.activeElement.dispatchEvent(new KeyboardEvent('keydown', {{key: '{name}', shiftKey: {str(shift).lower()}, bubbles: true, cancelable: true}}))")
                    p.until("!!document.querySelector('.rowmenu [role=menu]')", f"{name} opens the menu at {w}")
                    self.assertEqual([e[1] for e in self.entries(p)][1:], WORDS[1:] + ["Delete"], f"{name} at {w}: the same entries as the right click")
                    self.close(p)
                    self.assertTrue(p.js("(() => { const a = document.activeElement; return !!a && a.matches('li.wl-row .idl'); })()"), f"{name} at {w}: focus is back on the id button")

    def test_copy_id_and_open_the_peek_work_from_the_dashboard(self):
        with chrome() as cdp:
            p = Pg.at(self, cdp, self.s.port)
            p.ready()
            p.edit()
            p.js("window.__clip = []; Object.defineProperty(navigator, 'clipboard', {value: {writeText: (t) => { window.__clip.push(t); return Promise.resolve(); }}, configurable: true})")
            self.show_menu(p, "[data-type=actions] .wl-row")
            rid = p.js("document.querySelector('.rowmenu').dataset.rowmenu")
            p.js("document.querySelector('.rowmenu [data-rm=copyid]').click()")
            p.until("window.__clip.length === 1", "the copy")
            self.assertEqual(p.js("window.__clip[0]"), rid, "the item id is what is copied")
            p.until(f"[...document.querySelectorAll('.toast .toast-text')].some(t => t.textContent === {json.dumps(rid + ' copied.')})", "the copied words")
            self.show_menu(p, "[data-type=actions] .wl-row")
            p.js("document.querySelector('.rowmenu [data-rm=peek]').click()")
            p.until(f"location.hash.split('&').includes('item=' + {json.dumps(rid)})", "the peek of this item")

    def test_risks_and_decisions_rows_have_the_same_menu(self):
        """Row 1296: the three lists (risks, actions, decisions) all open the Work items menu."""
        with chrome() as cdp:
            p = Pg.at(self, cdp, self.s.port)
            p.ready()
            p.edit()
            for kind in ("raid", "actions", "decisions"):
                for w in (1400, 900):
                    cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                    self.show_menu(p, f"[data-type={kind}] .wl-row")
                    words = [e[1] for e in self.entries(p)]
                    self.assertEqual(words[1:], WORDS[1:] + ["Delete"], f"{kind} at {w}")
                    self.assertTrue(p.js("document.querySelector('.rowmenu').dataset.rowmenu === document.querySelector('[data-type=%s] .wl-row').dataset.id" % kind), f"{kind} at {w}: the menu is for the row clicked")
                    self.close(p)

    def test_a_board_card_is_never_drawn_on_the_dashboard(self):
        """Row 1296 owns the list rows only; the board card menu belongs to the Work items board. The Dashboard has no board to inherit from."""
        import pathlib
        src = pathlib.Path(page.__file__).parent / "src"
        users = sorted(f.name for f in src.rglob("*.jsx") if "<Board " in f.read_text(encoding="utf-8"))
        self.assertEqual(users, ["WorkItems.jsx"], "only the Work items page draws the board")
        with chrome() as cdp:
            p = Pg.at(self, cdp, self.s.port)
            p.ready()
            for w in (1400, 900):
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                self.assertEqual(p.js("document.querySelectorAll('article.bcard').length"), 0, f"no card on the Dashboard at {w}")
            p.edit()
            self.assertEqual(p.js("document.querySelectorAll('article.bcard').length"), 0, "none in Edit either")


class DashboardRowWrites(board.Base):
    """Row 1296 sweep: the writes a Dashboard row's menu makes, against the real store."""

    def setUp(self):
        super().setUp()
        self.demo.plant_builtin_sections()      # the rows are in the built-in sections, which a new project no longer has (row 1193)
        self.s.httpd.draft_email = draft_email_feed.make(
            self.store.data_for, profile=lambda: {"name": "Sam Example", "own_domains": []}, clock=lambda: "2026-10-05 09:00",
            rules_for=lambda c: draft_email_feed.rules_from_inputs(publish.read_inputs(self.store, c)))

    def edit_dashboard(self, cdp):
        self.s.httpd.page_html = lambda: testpage.html()          # the test page has window.clarkPage
        sid = page_target(cdp)
        cdp.call("Page.enable", {}, sid)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": 1400, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
        cdp.call("Emulation.setFocusEmulationEnabled", {"enabled": True}, sid)
        cdp.call("Page.navigate", {"url": "about:blank"}, sid)
        cdp.call("Page.navigate", {"url": board.for_url(f"http://127.0.0.1:{self.s.port}/#dashboard&p=ABC")}, sid)
        self.until(cdp, sid, "document.querySelectorAll('[data-type=actions] .wl-row').length >= 2", "the Dashboard rows")
        cdp.js("document.querySelector('[data-mode=edit]').click()", sid)
        self.until(cdp, sid, "document.querySelector('#report').dataset.mode === 'edit'", "Edit mode")
        return sid

    def open_menu(self, cdp, sid):
        right_click(cdp, sid, "[data-type=actions] .wl-row")
        self.until(cdp, sid, "!!document.querySelector('.rowmenu [role=menu]')", "the menu")
        return cdp.js("document.querySelector('.rowmenu').dataset.rowmenu", sid)

    def test_the_draft_dialog_opened_from_a_dashboard_row_stays_open(self):
        """The Dashboard counts as a page for the menu, so the Draft email dialog is not closed as 'another page'."""
        with chrome() as cdp:
            sid = self.edit_dashboard(cdp)
            self.open_menu(cdp, sid)
            cdp.js("document.querySelector('.rowmenu [data-rm=draft]').click()", sid)
            self.until(cdp, sid, "!!document.querySelector('[data-draft-email] .de')", "the Draft email")
            self.until(cdp, sid, "document.querySelector('.de').contains(document.activeElement)", "the focus in the dialog")
            self.assertTrue(cdp.js("!!document.querySelector('[data-draft-email] .de')", sid), "still open")

    def test_archive_moves_focus_to_the_next_row_and_undo_returns_it_to_the_id_button(self):
        """The neighbour is found among the list rows too, and the undo focus names the list row's id button."""
        with chrome() as cdp:
            sid = self.edit_dashboard(cdp)
            ids = cdp.js("[...document.querySelectorAll('[data-type=actions] .wl-row')].map(r => r.dataset.id)", sid)
            first = self.open_menu(cdp, sid)
            nxt = ids[ids.index(first) + 1]
            cdp.js("document.querySelector('.rowmenu [data-rm=archive]').click()", sid)
            self.until(cdp, sid, f"!document.querySelector('li.wl-row[data-id=\"{first}\"]')", "the row left the list")
            self.until(cdp, sid, f"(document.activeElement.closest('li.wl-row') || {{dataset: {{}}}}).dataset.id === '{nxt}'", "focus on the next row")
            click(cdp, sid, "[data-undo]")
            self.until(cdp, sid, f"!!document.querySelector('li.wl-row[data-id=\"{first}\"]')", "the row came back")
            self.until(cdp, sid, f"document.activeElement.matches('li.wl-row[data-id=\"{first}\"] .idl')", "focus back on the id button")

    def go(self, cdp, sid, view):
        click(cdp, sid, f"[role=tab][data-view={view}]")

    def test_a_dashboard_row_outside_the_work_items_search_still_gets_its_menu(self):
        """RowMenu itemOf falls back to the whole list: a search that matches no Work items row (itemRows empty) does not empty the Dashboard menu."""
        with chrome() as cdp:
            sid = self.edit_dashboard(cdp)
            self.assertTrue(cdp.js("typeof clarkPage.setQuery === 'function'", sid), "the test page")
            cdp.js("clarkPage.setQuery('zzqxnomatch')", sid)
            self.until(cdp, sid, "document.querySelectorAll('[data-type=actions] .wl-row').length >= 2", "the Dashboard rows still drawn")
            rid = self.open_menu(cdp, sid)
            self.assertEqual(cdp.js("document.querySelector('.rowmenu [data-rm=archive]').getAttribute('aria-disabled')", sid), None, "a live menu")
            cdp.js("window.__clip = []; Object.defineProperty(navigator, 'clipboard', {value: {writeText: (t) => { window.__clip.push(t); return Promise.resolve(); }}, configurable: true})", sid)
            cdp.js("document.querySelector('.rowmenu [data-rm=copyid]').click()", sid)
            self.until(cdp, sid, "window.__clip.length === 1", "the copy")
            self.assertEqual(cdp.js("window.__clip[0]", sid), rid)

    def test_a_work_selection_blocks_the_row_menu_but_a_dashboard_one_does_not(self):
        """RowMenu: with rows picked on Work items the menu stays shut (the bulk bar owns the click); on the Dashboard the same picks do not block it."""
        from test_multi_select import MOD, peek_away, tap
        with chrome() as cdp:
            sid = self.edit_dashboard(cdp)
            self.go(cdp, sid, "work")
            self.until(cdp, sid, "document.querySelectorAll('#work-list tr[data-id]').length >= 2", "the Work items rows")
            ids = cdp.js("[...document.querySelectorAll('#work-list tr[data-id]')].map(r => r.dataset.id)", sid)[:2]
            tap(cdp, sid, f"#work-list tr[data-id='{ids[0]}'] .c-item .t")
            peek_away(cdp, sid, cdp.js("innerWidth", sid))
            tap(cdp, sid, f"#work-list tr[data-id='{ids[1]}'] .c-item .t", MOD)
            self.assertEqual(cdp.js("clarkPage.selected()", sid), ids)
            right_click(cdp, sid, f"#work-list tr[data-id='{ids[0]}']")
            self.until(cdp, sid, "!!document.querySelector('.cpop.bmenu')", "the multi-select menu opens instead")
            self.assertFalse(cdp.js("!!document.querySelector('.rowmenu')", sid), "Work: a selection blocks the row menu")
            self.go(cdp, sid, "dashboard")
            self.until(cdp, sid, "document.querySelectorAll('[data-type=actions] .wl-row').length >= 2", "the Dashboard rows")
            self.assertEqual(cdp.js("clarkPage.selected()", sid), [], "leaving Work items empties the selection, so the Dashboard has none to block it")
            self.until(cdp, sid, "document.querySelector('#report').dataset.mode === 'edit'", "the Dashboard in Edit")
            for _ in range(6):          # the page needs a moment after the tab change before its listeners are on
                right_click(cdp, sid, "[data-type=actions] .wl-row")
                if wait(lambda: cdp.js("!!document.querySelector('.rowmenu [role=menu]')", sid), 1):
                    break
            self.assertTrue(cdp.js("!!document.querySelector('.rowmenu [role=menu]')", sid), "the Dashboard row menu opens: no selection blocks it")


if __name__ == "__main__":
    unittest.main()
