"""Row 1366 rows 6 and 7: the files left out of a folder (Classic Settings page) and the answer note while the index is still being read.

Row 6: under each folder's status line in both Source folders lists a text button "Show the files left out" opens a plain list (file name, then the
reason, muted 13px), collapsed by default, at most 200 shown and then "and N more" (N = the rest). Classic only (Cards is unchanged: no button).
Row 7: the answer's note says "Still reading N files, so this answer may miss some." only while the index is incomplete.

Run: python3 dev/run_tests.py test_ask_index_list_1366
Chrome is required. Every file is made in the test from made-up text.
"""
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from _editor_checks import for_project
from test_ask_settings import make_db, service
from test_page import DATA, navigate
from test_server import Running, chrome, wait

from clark import ask, ask_folders, ask_index, ask_service, page, platform as pl, theme

WIDTHS = (1400, 900)
BTN = "document.querySelector('%s .ask-left-btn')"


class Base(unittest.TestCase):
    classic = True

    def setUp(self):
        patch = mock.patch.object(pl, "system", return_value=pl.MAC)
        patch.start()
        self.addCleanup(patch.stop)
        html = page.page_html(tempfile.mkdtemp())
        if self.classic:
            html = page.layer_theme(html, theme.css("prototype-2.0"))
        self.s = Running(data_for=lambda code, archived=None: DATA.get(code), page_html=lambda: html)
        self.addCleanup(self.s.close)
        self.d = Path(os.path.realpath(tempfile.mkdtemp(prefix="clark-test-")))
        self.addCleanup(shutil.rmtree, self.d, True)
        self.home, self.data = self.d / "home", self.d / "data"
        self.shared, self.own = self.d / "shared", self.d / "own"
        for p in (self.home, self.shared, self.own, self.data):
            p.mkdir(parents=True)
        (self.own / "a.txt").write_text("alpha river", encoding="utf-8")
        for i in range(240):
            (self.own / f"p{i:03d}.bin").write_bytes(b"x")
        (self.shared / "c.md").write_text("beta lake", encoding="utf-8")
        (self.shared / "z.bin").write_bytes(b"x")
        db = make_db(self.data)
        self.s.httpd.app_settings = service(db)
        self.ix = ask_index.Indexer(self.data, self.home)
        self.addCleanup(self.ix.shutdown)
        self.s.httpd.ask_folders = self.svc = ask_folders.AskFolders(db, [], data_dir=self.data, home=self.home, by_user=lambda: "tester", indexer=self.ix)
        ask_folders.AskFolders.change_all(self.svc, {"scope": "all", "action": "add", "path": str(self.shared)})
        self.svc.change({"project": "ABC", "action": "add", "path": str(self.own)})
        self.assertTrue(self.ix.wait_idle(20))

    def show(self, cdp, tab="project", ready="document.querySelectorAll('.ask-folder-line').length >= 2"):
        self.sid = navigate(cdp, self.s.port, for_project("#settings&p=ABC&s=claude"))
        js = lambda e: cdp.js(e, self.sid)          # noqa: E731
        self.assertTrue(wait(lambda: js("!!document.querySelector('[data-ask-tab]')"), 20))
        if tab == "all":
            js("document.querySelector('[data-ask-tab=all]').click()")
            self.assertTrue(wait(lambda: js("!!document.querySelector('#ask-all-folders')"), 10))
        self.assertTrue(wait(lambda: js(ready), 20), ready)
        return js


class Classic(Base):
    def look(self, js, sel):
        return js("(() => { const b = document.querySelector(%r + ' .ask-left-btn'); const c = getComputedStyle(b); const tok = (v) => { const p = document.createElement('p'); p.style.color = 'var(' + v + ')'; document.body.appendChild(p); const x = getComputedStyle(p).color; p.remove(); return x; }; "
                  "return {color: c.color, blue: tok('--brand-blue'), size: c.fontSize, h: b.getBoundingClientRect().height, role: b.tagName, exp: b.getAttribute('aria-expanded'), "
                  "list: !!document.querySelector(%r + ' .ask-left-list'), below: !!b.closest('.ask-folder-line')}; })()" % (sel, sel))

    def open_list(self, js, sel):
        js(BTN % sel + ".click()")
        self.assertTrue(wait(lambda: js("!!document.querySelector(%r + ' .ask-left-list')" % sel), 10))

    def test_collapsed_by_default_then_a_list_of_200_and_and_40_more_at_both_widths_in_light_and_dark(self):
        with chrome() as cdp:
            js = self.show(cdp)
            self.assertTrue(wait(lambda: js("!!document.querySelector('#ask-folders .ask-left-btn')"), 20))
            for mode in ("light", "dark"):
                js(f"document.documentElement.dataset.theme = {mode!r}")
                for w in WIDTHS:
                    cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, self.sid)
                    self.assertTrue(wait(lambda: js("document.documentElement.scrollWidth <= window.innerWidth"), 10), (mode, w))
                    for sel in ("#ask-folders-shared", "#ask-folders"):
                        k = self.look(js, sel)
                        self.assertEqual((k["color"], k["size"], k["role"], k["exp"], k["list"], k["below"]), (k["blue"], "13px", "BUTTON", "false", False, True), (mode, w, sel, k))
                        self.assertEqual(js(BTN % sel + ".textContent"), "(why)")
            self.open_list(js, "#ask-folders")
            self.assertEqual(js(BTN % "#ask-folders" + ".getAttribute('aria-expanded')"), "true")
            n = js("document.querySelectorAll('#ask-folders .ask-left-list li').length")
            self.assertEqual(n, 201)
            self.assertEqual(js("document.querySelector('#ask-folders .ask-left-list li:last-child').innerText"), "and 40 more")
            self.assertEqual(js("document.querySelector('#ask-folders .ask-left-list li:first-child').innerText"), "p000.bin of a type clark can't read yet")
            for mode in ("light", "dark"):
                js(f"document.documentElement.dataset.theme = {mode!r}")
                got = js("(() => { const li = document.querySelector('#ask-folders .ask-left-list li'); const why = li.querySelector('.ask-left-why'); const c = getComputedStyle(why); "
                         "const p = document.createElement('p'); p.style.color = 'var(--text-muted)'; document.body.appendChild(p); const m = getComputedStyle(p).color; p.remove(); "
                         "return {size: c.fontSize, color: c.color, muted: m, names: li.firstElementChild.className, order: li.firstElementChild.getBoundingClientRect().left <= why.getBoundingClientRect().left}; })()")
                self.assertEqual((got["size"], got["color"], got["order"]), ("13px", got["muted"], True), (mode, got))
            js(BTN % "#ask-folders" + ".click()")
            self.assertTrue(wait(lambda: js("!document.querySelector('#ask-folders .ask-left-list')"), 10))
            # the folder for all projects has one file left out, no "and N more"
            self.open_list(js, "#ask-folders-shared")
            self.assertEqual(js("[...document.querySelectorAll('#ask-folders-shared .ask-left-list li')].map(e => e.innerText)"), ["z.bin of a type clark can't read yet"])

    def test_the_keyboard_opens_and_closes_the_list(self):
        with chrome() as cdp:
            js = self.show(cdp)
            self.assertTrue(wait(lambda: js("!!document.querySelector('#ask-folders .ask-left-btn')"), 20))
            js(BTN % "#ask-folders" + ".focus()")
            for kind, expected in (("Enter", True), ("Enter", False), (" ", True)):
                for t in ("keyDown", "keyUp"):
                    args = {"type": t, "key": kind, "code": "Space" if kind == " " else "Enter", "windowsVirtualKeyCode": 32 if kind == " " else 13}
                    if t == "keyDown" and kind == "Enter":
                        args["text"] = "\r"
                    if t == "keyDown" and kind == " ":
                        args["text"] = " "
                    cdp.call("Input.dispatchKeyEvent", args, self.sid)
                self.assertTrue(wait(lambda: js("!!document.querySelector('#ask-folders .ask-left-list')") == expected, 10), (kind, expected))
            self.assertTrue(js("document.activeElement === " + (BTN % "#ask-folders")))

    def test_all_projects_card_has_the_button_and_a_removed_folder_takes_its_list_away(self):
        with chrome() as cdp:
            js = self.show(cdp, "all", "!!document.querySelector('#ask-all-folder-list .ask-folder-line')")
            self.assertTrue(wait(lambda: js("!!document.querySelector('#ask-all-folder-list .ask-left-btn')"), 20))
            self.open_list(js, "#ask-all-folder-list")
            js("document.querySelector('[data-ask-all-remove]').click()")
            self.assertTrue(wait(lambda: js("!!document.querySelector('#ask-all-folders-none')"), 10))
            self.assertFalse(js("!!document.querySelector('#ask-all-folders .ask-left-btn, #ask-all-folders .ask-left-list')"))


class Cards(Base):
    classic = False

    def test_cards_has_no_button(self):
        """Re-pinned (named exemption): this test used to wait for the status line under Cards, which was the leak (its rules are Classic's,
        so on Cards it showed as unstyled text and changed the page). Cards now has no line, no button and no list."""
        with chrome() as cdp:
            js = self.show(cdp, ready="document.querySelectorAll('.folder-now').length >= 2")
            self.assertTrue(wait(lambda: js("document.querySelectorAll('.folder-now').length >= 1"), 20))
            self.assertFalse(js("!!document.querySelector('.ask-folder-line, .ask-left-btn, .ask-left-list')"))


class Note(unittest.TestCase):
    """Row 7, through the real service: the server sends the note, only while a run is reading."""

    def setUp(self):
        import _publish_fixture as plant
        from clark import ask_claude as ac
        from test_ask_connector_wiring import LIST_M365, PATH, final, stream
        self.d = Path(os.path.realpath(tempfile.mkdtemp(prefix="clark-test-")))
        self.addCleanup(shutil.rmtree, self.d, True)
        self.db = plant.build_db(self.d / "clark.db")
        self.provider = ac.ClaudeCommand(places=(), env={}, limit=5)
        self.provider.connector_runner = lambda: LIST_M365
        out = stream(final("The plan is on track.\nCITE: P1"))
        for p in (mock.patch.object(self.provider, "usable", return_value=(PATH, None)),
                  mock.patch.object(ac, "run", side_effect=lambda *a, **k: ("ok", out, 0))):
            p.start()
            self.addCleanup(p.stop)
        self.not_yet = 0
        self.folder = self.d / "f"
        self.folder.mkdir()
        (self.folder / "a.txt").write_text("alpha", encoding="utf-8")
        self.indexer = SimpleNamespace(current=lambda code, folders: False, not_yet=lambda code: self.not_yet)
        self.service = ask_service.AskService(self.db, self.provider, [], data_dir=self.d, indexer=self.indexer)
        p = mock.patch.object(self.service, "folders_for", return_value=[str(self.folder)])
        p.start()
        self.addCleanup(p.stop)

    def notes(self):
        status, body = self.service.ask({"project": "PUB", "question": "What is the state of the plan?"})
        self.assertEqual(status, 200, body)
        self.last = body
        return body["notes"]

    def test_the_note_is_there_while_reading_singular_and_plural_and_gone_when_complete(self):
        """Re-pinned (named exemption): this test read the note from the shared notes list; it is now its own field (`index_note`, at `index_note_at`),
        so the Cards page, which draws the shared list, never gets it."""
        self.not_yet = 120
        notes = self.notes()
        self.assertEqual(self.last["index_note"], "Still reading 120 files, so this answer may miss some.")
        self.assertNotIn(self.last["index_note"], notes)
        self.assertEqual(self.last["index_note_at"], len(notes), "it comes after the notes before it, as before")
        self.not_yet = 1
        self.notes()
        self.assertEqual(self.last["index_note"], "Still reading 1 file, so this answer may miss some.")
        self.not_yet = 0
        notes = self.notes()
        self.assertFalse([n for n in notes if n.startswith("Still reading")])
        self.assertNotIn("index_note", self.last)
        self.assertNotIn("index_note_at", self.last)

    def test_the_real_indexer_counts_what_is_not_read_yet(self):
        ix = ask_index.Indexer(self.d, self.d)
        self.addCleanup(ix.shutdown)
        self.assertEqual(ix.not_yet("PUB"), 0)
        ix.live["PUB"] = {"x": (3, 10), "y": (0, 2)}
        self.assertEqual(ix.not_yet("PUB"), 9)


if __name__ == "__main__":
    unittest.main()
