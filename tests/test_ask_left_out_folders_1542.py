"""Row 1542: Settings > Ask clark lists the subfolders left out of a saved folder, one line each with Include again, under "Left out of questions" (Classic only).

Run: python3 dev/run_tests.py test_ask_left_out_folders_1542
The server half (the include action, its Undo, what the next index run reads) runs against a real data file; the page half runs in Chrome at 1400 and 900, light and dark,
with the folders route answered by a small stand-in that keeps a left-out list. Made-up names only.
"""
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _editor_checks import for_project
from _paths import SRC  # noqa: F401
from test_page import DATA, navigate
from test_server import Running, chrome, wait

from clark import ask_exclude, ask_folders, ask_index, page, platform as pl, reach, store as st

WIDTHS = (1400, 900)
SAVED = "/Example/Programme files"
HEAD = "Left out of questions"
BUTTON = "Include again"
FAKE = """
window.__left = {list: [{folder: '/Example/Programme files', rels: ['Contract', 'HR/Candidates']}], calls: [], undo: null};
const real = window.fetch;
window.fetch = function (url, opts) {
  if (String(url).indexOf('/api/ask-folders') < 0) return real.apply(this, arguments);
  const body = opts && opts.body ? JSON.parse(opts.body) : null;
  const L = window.__left;
  let out = {ok: true, folders: ['/Example/Programme files'], warnings: [], left_out: L.list};
  if (body && body.action === 'include') {
    L.calls.push(body);
    L.undo = JSON.parse(JSON.stringify(L.list));
    L.list = L.list.map(l => ({folder: l.folder, rels: l.rels.filter(r => r !== body.rel)})).filter(l => l.rels.length);
    out = {ok: true, folders: ['/Example/Programme files'], message: 'Added. Asking may now read the files in that folder.', apply_id: 5, warnings: [], left_out: L.list};
  } else if (body && body.action === 'undo') {
    L.calls.push(body);
    L.list = L.undo;
    out = {ok: true, folders: ['/Example/Programme files'], message: 'Undone.', left_out: L.list};
  }
  return Promise.resolve(new Response(JSON.stringify(out), {status: 200, headers: {'Content-Type': 'application/json'}}));
};
"""
ROWS = "[...document.querySelectorAll('#ask-left-folders li')]"


class Data(unittest.TestCase):
    """The server half: a saved folder with two subfolders left out."""

    def setUp(self):
        patch = mock.patch.object(pl, "system", return_value=pl.MAC)
        patch.start()
        self.addCleanup(patch.stop)
        self.d = Path(os.path.realpath(tempfile.mkdtemp(prefix="clark-test-")))
        self.addCleanup(shutil.rmtree, self.d, True)
        self.data, self.home = self.d / "data", self.d / "home"
        self.root = self.home / "lib"
        for rel, text in (("Notes/a.txt", "alpha notes"), ("Contract/terms.txt", "contract terms"), ("HR/Candidates/cv.txt", "candidate one")):
            f = self.root / rel
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(text, encoding="utf-8")
        self.data.mkdir()
        self.db = self.data / "clark.db"
        s = self.store()
        with s.step("dashboard", "tester", place="menu") as step:
            step.create("projects", {"code": "ABC", "name": "Example Programme"})
            step.create("source_folders", {"project": "ABC", "path": str(self.root), "sort_order": 0, "excluded": ask_exclude.dump(["Contract", "HR/Candidates"])})
        self.svc = ask_folders.AskFolders(self.db, [], data_dir=self.data, home=self.home, by_user=lambda: "tester")

    def store(self):
        s = st.open_store(self.db, onedrive_roots=[])
        self.addCleanup(s.close)
        return s

    def stored(self):
        return ask_exclude.parse(self.store().read("source_folders", "ABC")[0]["excluded"])

    def left_files(self):
        """The files a read of the saved folder lists with the stored list applied, as relative names."""
        raw = {str(self.root): self.stored()}
        got = reach.readable_files([str(self.root)], self.data, None, self.home, {f: (lambda names, r=r: ask_exclude.left_out(names, r)) for f, r in raw.items()})
        return sorted(os.path.relpath(f, self.root) for f in got.files)

    def test_include_again_puts_folder_back_and_next_run_indexes_it(self):
        status, body = self.svc.read("ABC")
        self.assertEqual(body["left_out"], [{"folder": str(self.root), "rels": ["Contract", "HR/Candidates"]}], "read lists what is left out, relative as saved")
        self.assertEqual(self.left_files(), ["Notes/a.txt"])
        status, body = self.svc.change({"project": "ABC", "action": "include", "path": str(self.root), "rel": "Contract"})
        self.assertEqual((status, body["ok"]), (200, True), body)
        self.assertEqual(body["left_out"], [{"folder": str(self.root), "rels": ["HR/Candidates"]}], "0 lines left for that folder")
        self.assertEqual(self.stored(), ["HR/Candidates"])
        self.assertEqual(self.left_files(), ["Contract/terms.txt", "Notes/a.txt"], "its files are read again")
        ask_index.build(self.data, "ABC", [str(self.root)], self.home)
        self.assertTrue(any("terms.txt" in p.label for p in ask_index.search(self.data, "ABC", "contract terms")), "the next index run has its files")

    def test_include_again_is_one_step_with_one_undo_and_refuses_what_is_not_left_out(self):
        status, body = self.svc.change({"project": "ABC", "action": "include", "path": str(self.root), "rel": "Contract"})
        self.assertEqual(status, 200)
        status, undone = self.svc.change({"project": "ABC", "action": "undo", "apply_id": body["apply_id"]})
        self.assertEqual((status, undone["message"]), (200, ask_folders.MESSAGES["undone"]))
        self.assertEqual(self.stored(), ["Contract", "HR/Candidates"])
        self.assertEqual(undone["left_out"], [{"folder": str(self.root), "rels": ["Contract", "HR/Candidates"]}])
        for bad in ({"rel": "Notes"}, {"rel": "../x"}, {"rel": 5}, {"path": str(self.d)}):
            status, out = self.svc.change({"project": "ABC", "action": "include", "path": str(self.root), "rel": "Contract", **bad})
            self.assertEqual((status, out["ok"]), (409 if status == 409 else 400, False), (bad, out))
        self.assertEqual(self.stored(), ["Contract", "HR/Candidates"], "a refused include changes nothing")
        self.assertEqual(self.svc.change({"project": "ABC", "action": "include", "path": str(self.root)})[0], 400, "the subfolder is required")


class Page(unittest.TestCase):
    theme = "prototype-2.0"

    def setUp(self):
        theme = self.theme
        self.s = Running(data_for=lambda code, archived=None: DATA.get(code), page_html=lambda: page.page_html(tempfile.mkdtemp(), theme=theme))
        self.addCleanup(self.s.close)

    def show(self, cdp, fake=FAKE):
        self.sid = navigate(cdp, self.s.port, for_project("#settings&p=ABC&s=claude"))
        js = lambda e: cdp.js(e, self.sid)          # noqa: E731
        js(fake)
        js("location.hash = '#dashboard&p=ABC'")
        wait(lambda: js("!document.querySelector('#ask-settings')"), 10)
        js("location.hash = '#settings&p=ABC&s=claude'")
        self.assertTrue(wait(lambda: js("!!document.querySelector('#ask-folders')"), 20), "the folder list is drawn")
        return js


class Classic(Page):
    def test_lists_every_left_out_folder_with_include_again(self):
        """Row 1542 AP1: one line and one Include again per left-out folder, under the heading, below the folder list; 13px text, 2px margins, 14px button, 24px min height."""
        for scheme in ("light", "dark"):
            for width in WIDTHS:
                with chrome() as cdp:
                    js = self.show(cdp)
                    cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, self.sid)
                    cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme}]}, self.sid)
                    where = f"{scheme} {width}"
                    self.assertTrue(wait(lambda: js("!!document.querySelector('#ask-left-folders')"), 10), where)
                    self.assertEqual(js(f"{ROWS}.map(li => li.querySelector('.ask-left-name').innerText)"), ["Contract", "HR/Candidates"], where)
                    self.assertEqual(js(f"{ROWS}.map(li => li.querySelectorAll('button').length)"), [1, 1], where)
                    self.assertTrue(js("document.querySelector('#ask-folders').compareDocumentPosition(document.querySelector('#ask-left-folders')) & Node.DOCUMENT_POSITION_FOLLOWING"), "below the folder list")
                    lst, li, btn = "document.querySelector('#ask-left-folders ul')", f"{ROWS}[0]", "document.querySelector('[data-ask-include]')"
                    self.assertEqual(js(f"[getComputedStyle({lst}).fontSize, getComputedStyle({lst}).marginTop, getComputedStyle({li}).marginBottom]"), ["13px", "2px", "2px"], where)
                    self.assertEqual(js(f"[getComputedStyle({btn}).fontSize, getComputedStyle({btn}).minHeight]"), ["14px", "24px"], where)
                    self.assertTrue(js(f"{li}.getBoundingClientRect().right <= innerWidth && document.documentElement.scrollWidth <= innerWidth"), f"no sideways scroll at {where}")

    def test_words_match_new_words_md(self):
        """Row 1542 AP3: heading, button and screen-reader name as approved; the toast is the existing Added line and the existing Undo; an empty list draws nothing."""
        with chrome() as cdp:
            js = self.show(cdp)
            self.assertTrue(wait(lambda: js("!!document.querySelector('#ask-left-folders')"), 10))
            self.assertEqual(js("document.querySelector('#ask-left-folders h3').innerText"), HEAD)
            self.assertEqual(js("[...document.querySelectorAll('[data-ask-include]')].map(b => b.innerText)"), [BUTTON, BUTTON])
            self.assertEqual(js("[...document.querySelectorAll('[data-ask-include]')].map(b => b.getAttribute('aria-label'))"), [f"{BUTTON}: Contract", f"{BUTTON}: HR/Candidates"])
            self.assertEqual(js("document.querySelector('#ask-left-folders ul').getAttribute('aria-labelledby')"), "ask-left-folders-h")
            js("document.querySelector('[data-ask-include=\"Contract\"]').click()")
            self.assertTrue(wait(lambda: js(f"{ROWS}.length") == 1, 10), "the line goes")
            self.assertEqual(js("window.__left.calls"), [{"project": "ABC", "action": "include", "path": SAVED, "rel": "Contract"}])
            self.assertTrue(wait(lambda: js("(document.querySelector('.toast .toast-text') || {}).textContent") == ask_folders.MESSAGES["added"], 10), "an existing line")
            self.assertEqual(js("document.querySelectorAll('.toast [data-undo]').length"), 1, "one Undo")
            js("document.querySelector('.toast [data-undo]').click()")
            self.assertTrue(wait(lambda: js(f"{ROWS}.length") == 2, 10), "Undo puts the line back")
            self.assertEqual(js("window.__left.calls[1]"), {"project": "ABC", "action": "undo", "apply_id": 5})
            self.assertTrue(wait(lambda: js("(document.querySelector('.toast .toast-text') || {}).textContent") == ask_folders.MESSAGES["undone"], 10))
            for rel in ("Contract", "HR/Candidates"):
                js(f"document.querySelector('[data-ask-include=\"{rel}\"]').click()")
                self.assertTrue(wait(lambda: js("!document.querySelector('[data-ask-include=\"%s\"]')" % rel), 10))
            self.assertEqual(js("document.querySelectorAll('#ask-left-folders, #ask-left-folders-h').length"), 0, "an empty list draws 0 elements")
            self.assertNotIn("None", js("document.querySelector('#ask-folders-card').innerText"))


class Cards(Page):
    theme = None

    def test_cards_theme_unchanged(self):
        """Row 1542 AP4: Cards draws no list, and its style file holds no rule for it; only Classic's rules file does."""
        with chrome() as cdp:
            js = self.show(cdp)
            for width in WIDTHS:
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, self.sid)
                self.assertEqual(js("document.querySelectorAll('#ask-left-folders, [data-ask-include]').length"), 0, width)
                self.assertNotIn(HEAD, js("document.body.innerText"))
        for name in ("shell.css",):
            self.assertNotIn("ask-left-folders", (Path(page.PAGE).parent / name).read_text(encoding="utf-8"), name)
        self.assertIn("ask-left-folders", (Path(page.PAGE).parent.parent / "themes" / "prototype-2.0" / "rules.css").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
