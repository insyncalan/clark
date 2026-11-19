"""Row 1366 slice (a): the status line under each saved folder, in a real browser at 1400 and 900, in the project card (own and for-all folders)
and the All projects card, against the real folder service and the real background reader (Classic).

Run: python3 dev/run_tests.py test_ask_index_page_1366
Chrome is required. Every file is made in the test from made-up text.
"""
import os
import shutil
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from _editor_checks import for_project
from test_ask_settings import make_db, service
from test_page import DATA, navigate
from test_server import Running, chrome, wait

from clark import ask_folders, ask_index, page, platform as pl, theme

WIDTHS = (1400, 900)


class Fixture(unittest.TestCase):
    CLASSIC = True

    def setUp(self):
        patch = mock.patch.object(pl, "system", return_value=pl.MAC)
        patch.start()
        self.addCleanup(patch.stop)
        html = page.page_html(tempfile.mkdtemp())
        if self.CLASSIC:
            html = page.layer_theme(html, theme.css("prototype-2.0"))      # the status-line rules are Classic-only
        self.s = Running(data_for=lambda code, archived=None: DATA.get(code), page_html=lambda: html)
        self.addCleanup(self.s.close)
        self.d = Path(os.path.realpath(tempfile.mkdtemp(prefix="clark-test-")))
        self.addCleanup(shutil.rmtree, self.d, True)
        self.home = self.d / "home"
        self.data = self.d / "data"
        self.shared, self.own = self.d / "shared", self.d / "own"
        for p in (self.home, self.shared, self.own, self.data):
            p.mkdir(parents=True)
        (self.own / "a.txt").write_text("alpha river", encoding="utf-8")
        (self.own / "b.png").write_bytes(b"x")
        (self.shared / "c.md").write_text("beta lake", encoding="utf-8")
        db = make_db(self.data)
        self.s.httpd.app_settings = service(db)
        self.gate = threading.Event()
        self.gate.set()
        real = ask_index.refresh

        def held(data, code, folders, home=None, stop=None, progress=None):
            def hold(f, d, t):
                progress(f, d, t)
                self.gate.wait(10)
            return real(data, code, folders, home, stop=stop, progress=hold)
        self.ix = ask_index.Indexer(self.data, self.home, refresh_fn=held)
        self.addCleanup(self.ix.shutdown)
        self.s.httpd.ask_folders = self.svc = ask_folders.AskFolders(db, [], data_dir=self.data, home=self.home, by_user=lambda: "tester", indexer=self.ix)

    def show(self, cdp, tab):
        self.sid = navigate(cdp, self.s.port, for_project("#settings&p=ABC&s=claude"))
        js = lambda e: cdp.js(e, self.sid)          # noqa: E731
        self.assertTrue(wait(lambda: js("!!document.querySelector('[data-ask-tab]')"), 20))
        if tab == "all":
            js("document.querySelector('[data-ask-tab=all]').click()")
            self.assertTrue(wait(lambda: js("!!document.querySelector('#ask-all-folders')"), 10))
        return js

    def until(self, js, expr, what):
        self.assertTrue(wait(lambda: js(expr), 20), f"{what}: {expr}")

    LOOK = ("(() => { const e = document.querySelector(%r); const c = getComputedStyle(e); const li = e.closest('li'); "
            "const r = li.querySelector('[data-ask-remove],[data-ask-all-remove],[data-ask-change-shared]').getBoundingClientRect(); "
            "return {size: c.fontSize, weight: c.fontWeight, color: c.color, mt: c.marginTop, role: e.getAttribute('role'), live: e.getAttribute('aria-live'), "
            "below: e.getBoundingClientRect().top >= r.bottom - 1, text: e.innerText}; })()")


class Page(Fixture):
    def test_the_line_in_the_project_card_for_an_own_and_a_shared_folder_at_both_widths(self):
        ask_folders.AskFolders.change_all(self.svc, {"scope": "all", "action": "add", "path": str(self.shared)})
        self.svc.change({"project": "ABC", "action": "add", "path": str(self.own)})
        self.assertTrue(self.ix.wait_idle(10))
        with chrome() as cdp:
            js = self.show(cdp, "project")
            self.until(js, "document.querySelectorAll('.ask-folder-line').length === 2", "two lines")
            self.until(js, "[...document.querySelectorAll('.ask-folder-line')].every(e => e.innerText.startsWith('Indexed'))", "indexed")
            self.assertEqual(js("document.querySelector('#ask-folders-shared .ask-folder-line').innerText"), "Indexed 1 of 1 file.")
            self.assertEqual(js("document.querySelector('#ask-folders .ask-folder-line').innerText"), "Indexed 1 of 2 files. 1 is of a type clark can't read yet.")
            muted = js("getComputedStyle(document.querySelector('.ask-folders')).color && (() => { const p = document.createElement('p'); p.style.color = 'var(--text-muted)'; document.body.appendChild(p); const c = getComputedStyle(p).color; p.remove(); return c; })()")
            for w in WIDTHS:
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, self.sid)
                self.until(js, "document.documentElement.scrollWidth <= window.innerWidth", f"no sideways scroll at {w}")
                for q in ("#ask-folders-shared .ask-folder-line", "#ask-folders .ask-folder-line"):
                    look = js(self.LOOK % q)
                    self.assertEqual((look["size"], look["weight"], look["mt"], look["role"], look["live"], look["below"]), ("13px", "400", "2px", "status", "polite", True), (w, q, look))
                    self.assertEqual(look["color"], muted, (w, q))

    def test_the_line_in_the_all_projects_card_reads_reading_then_indexed_and_goes_with_its_folder(self):
        self.gate.clear()
        ask_folders.AskFolders.change_all(self.svc, {"scope": "all", "action": "add", "path": str(self.shared)})
        with chrome() as cdp:
            js = self.show(cdp, "all")
            self.until(js, "!!document.querySelector('#ask-all-folder-list .ask-folder-line')", "list")
            self.until(js, "document.querySelector('#ask-all-folder-list .ask-folder-line').innerText === 'Reading 0 of 1 file.'", "reading")
            for w in WIDTHS:
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, self.sid)
                look = js(self.LOOK % "#ask-all-folder-list .ask-folder-line")
                self.assertEqual((look["size"], look["weight"], look["mt"], look["role"], look["live"], look["below"]), ("13px", "400", "2px", "status", "polite", True), (w, look))
            self.gate.set()
            self.until(js, "document.querySelector('#ask-all-folder-list .ask-folder-line').innerText === 'Indexed 1 of 1 file.'", "indexed (asked again within 2 s polls)")
            js("document.querySelector('[data-ask-all-remove]').click()")
            self.until(js, "!!document.querySelector('#ask-all-folders-none')", "removed with its line")
            self.assertFalse(js("!!document.querySelector('#ask-all-folders .ask-folder-line')"))


class CardsPage(Fixture):
    """The status line and the left-out list are the Classic theme's: the Cards page is as it was (no line, no button), in every card."""
    CLASSIC = False

    def test_cards_has_no_status_line_and_no_left_out_button_in_any_card(self):
        ask_folders.AskFolders.change_all(self.svc, {"scope": "all", "action": "add", "path": str(self.shared)})
        self.svc.change({"project": "ABC", "action": "add", "path": str(self.own)})
        self.assertTrue(self.ix.wait_idle(10))
        self.assertTrue(ask_index.status(self.data, "ABC", [str(self.own)])["type"], "the folder has a file left out, so Classic would show the button")
        with chrome() as cdp:
            for tab in ("project", "all"):
                js = self.show(cdp, tab)
                self.until(js, "document.querySelectorAll('.folder-now').length >= 1", f"the folders are listed ({tab})")
                self.assertEqual(js("document.querySelectorAll('.ask-folder-line, .ask-left-out, .ask-left-btn').length"), 0, tab)


if __name__ == "__main__":
    unittest.main()
