"""Row 1203, the tab menu of the Use cases page: the open tab's small arrow has Rename view, Move view, Duplicate view and Delete view (Delete with Undo
in the toast), and + New view saves the line as a view named View 1, View 2 ... The views are kept under the page's own key, never the Work items memory.

Run: python3 dev/run_tests.py test_uc_tab_menu_1203
Drives the committed page against the real server in headless Chrome (set CLARK_CHROME to its path), at 1400 and 900 px.
"""
import json
import shutil
import unittest
from unittest import mock

from _real_server import real_server
from clark import __main__ as launcher, page, server as sv, use_cases_read
from clark.store import open_store
from test_inline_edits import EMPTY_BRANDING, click, key, need_chrome, tearDownModule  # noqa: F401
from test_server import chrome, wait
from test_work_items import FIXED_DATE, load_demo, page_target

START = ["All use cases", "On the dashboard", "Committed", "At risk"]
TABS = "[...document.querySelectorAll('#usecases .vtabs .vtab > span')].map(s => s.textContent)"
ACTIVE = "(document.querySelector('#usecases .vtab[aria-pressed=true] > span') || {}).textContent"
STORED = "JSON.parse(localStorage.getItem('clark.fviews.usecases') || '{}').TUL.map(v => v.name)"


class TabMenu(unittest.TestCase):
    def setUp(self):
        need_chrome()
        self.store, self.folder, _ = load_demo()
        self.addCleanup(shutil.rmtree, str(self.folder), True)
        self.addCleanup(self.store.close)
        self.path = self.folder / "clark.db"
        self.s = real_server(self.path, self.read, projects=lambda archived=False: [{"code": "TUL", "name": "Tulip"}], page_html=lambda: page.page_html(EMPTY_BRANDING))
        self.s.httpd.use_cases = use_cases_read.make_read(self.read, lambda code: set(), launcher.use_case_history(mock.Mock(path=self.path)))
        self.addCleanup(self.s.close)
        quiet = mock.patch.object(sv.LOG, "disabled", True)
        quiet.start()
        self.addCleanup(quiet.stop)

    def read(self, code, archived="hide"):
        st = open_store(self.path, onedrive_roots=[])
        try:
            return st.data_for(code, archived=archived)
        finally:
            st.close()

    def until(self, cdp, sid, expr, what, seconds=20):
        self.assertTrue(wait(lambda: cdp.js(expr, sid), seconds), what)

    def visit(self, cdp, width):
        sid = page_target(cdp)
        cdp.call("Page.enable", {}, sid)
        cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE}, sid)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
        cdp.call("Emulation.setFocusEmulationEnabled", {"enabled": True}, sid)
        cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{self.s.port}/#usecases&p=TUL"}, sid)
        self.until(cdp, sid, "document.querySelectorAll('#usecases .vtabs .vtab').length === 4", "the four starting tabs drew")
        return sid

    def menu(self, cdp, sid, kind):
        click(cdp, sid, "#ucl-viewTabMenu")
        self.until(cdp, sid, f"!!document.querySelector('#ucl-viewTabMenuList [data-kind={kind}]')", "the tab menu opened")
        click(cdp, sid, f"#ucl-viewTabMenuList [data-kind={kind}]")

    def test_the_tab_menu_renames_moves_duplicates_and_deletes_with_undo_and_new_view_adds_one(self):
        for width in (1400, 900):
            with self.subTest(width), chrome() as cdp:
                sid = self.visit(cdp, width)
                self.assertEqual(cdp.js(TABS, sid), START)
                strip = cdp.js("(() => { const s = document.querySelector('#usecases .vtabs'); return [s.scrollWidth, s.clientWidth]; })()", sid)
                self.assertLessEqual(strip[0], strip[1], f"{width}: the tab strip with the menu button and + New view beside four tabs does not scroll (scrollWidth {strip[0]}, clientWidth {strip[1]})")
                self.assertEqual(cdp.js("document.querySelectorAll('#usecases #ucl-viewTabMenu').length", sid), 1, "only the open tab has the arrow")
                click(cdp, sid, "#ucl-viewTabMenu")
                self.until(cdp, sid, "!!document.querySelector('#ucl-viewTabMenuList')", "the tab menu opened")
                self.assertEqual(cdp.js("[...document.querySelectorAll('#ucl-viewTabMenuList [role=menuitem]')].map(b => b.textContent)", sid),
                                 ["Rename view", "Move view", "Duplicate view", "Delete view"])
                self.assertTrue(cdp.js("document.querySelector('#ucl-viewTabMenuList [data-kind=delete]').classList.contains('danger')", sid))
                cdp.call("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Escape", "code": "Escape", "windowsVirtualKeyCode": 27}, sid)
                self.until(cdp, sid, "!document.querySelector('#ucl-viewTabMenuList')", "Esc closed the menu")
                # Duplicate: a copy right after it, open
                self.menu(cdp, sid, "duplicate")
                self.until(cdp, sid, f"{TABS}.length === 5", "the copy is a tab")
                self.assertEqual(cdp.js(TABS, sid), ["All use cases", "All use cases copy", "On the dashboard", "Committed", "At risk"])
                self.assertEqual(cdp.js(ACTIVE, sid), "All use cases copy")
                self.assertTrue(cdp.js("document.documentElement.scrollWidth <= window.innerWidth", sid), "no sideways scroll")
                # Rename
                self.menu(cdp, sid, "rename")
                self.until(cdp, sid, "document.activeElement && document.activeElement.id === 'vname'", "the name box opened with the focus")
                self.assertEqual(cdp.js("document.querySelector('label[for=vname]').textContent", sid), "New name for this view")
                cdp.js("(() => { const i = document.querySelector('#vname'); i.value = 'Mine'; i.dispatchEvent(new Event('input', {bubbles: true})); })()", sid)
                key(cdp, sid, "Enter")
                self.until(cdp, sid, f"{ACTIVE} === 'Mine'", "renamed")
                self.assertFalse(cdp.js("!!document.querySelector('#vname')", sid), "the box closed")
                # a name another view has is refused in words
                self.menu(cdp, sid, "rename")
                self.until(cdp, sid, "document.activeElement && document.activeElement.id === 'vname'", "the name box opened again with the focus")
                cdp.js("(() => { const i = document.querySelector('#vname'); i.value = 'Committed'; i.dispatchEvent(new Event('input', {bubbles: true})); })()", sid)
                key(cdp, sid, "Enter")
                self.until(cdp, sid, "document.querySelector('.vmsg').textContent.length > 0", "a name in use is told")
                self.assertEqual(cdp.js(ACTIVE, sid), "Mine")
                key(cdp, sid, "Escape")
                self.until(cdp, sid, "!document.querySelector('#vname')", "Esc closed the name box")
                # Move: one place right with the arrow key, Enter ends
                self.menu(cdp, sid, "move")
                self.until(cdp, sid, "document.activeElement && document.activeElement.classList.contains('vtab')", "the tab has the focus")
                key(cdp, sid, "ArrowRight")
                self.until(cdp, sid, f"{TABS}[1] === 'On the dashboard'", "moved right")
                self.assertEqual(cdp.js(TABS, sid), ["All use cases", "On the dashboard", "Mine", "Committed", "At risk"])
                key(cdp, sid, "Enter")
                self.assertEqual(cdp.js(STORED, sid), ["All use cases", "On the dashboard", "Mine", "Committed", "At risk"], "kept under the page's own key")
                self.assertEqual(cdp.js("Object.keys(localStorage).filter(k => k.startsWith('clark.fviews'))", sid), ["clark.fviews.usecases"])
                # Delete: gone at once, Undo in the toast puts it back in its place
                self.menu(cdp, sid, "delete")
                self.until(cdp, sid, f"{TABS}.length === 4", "the view left")
                self.until(cdp, sid, "(document.querySelector('.toast-text') || {}).textContent === 'View deleted: Mine'", "the toast")
                click(cdp, sid, "[data-undo]")
                self.until(cdp, sid, f"{TABS}.length === 5", "the view came back")
                self.assertEqual(cdp.js(TABS, sid), ["All use cases", "On the dashboard", "Mine", "Committed", "At risk"])
                # + New view: View 1, open
                click(cdp, sid, "#ucl-viewNew")
                self.until(cdp, sid, f"{TABS}.length === 6", "the new view is a tab")
                self.assertEqual(cdp.js(ACTIVE, sid), "View 1")
                self.assertEqual(cdp.js(TABS, sid)[-1], "View 1")


if __name__ == "__main__":
    unittest.main()
