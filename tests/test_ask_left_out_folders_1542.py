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
        for rel, text in (("Notes/a.txt", "alpha notes"), ("Archive/terms.txt", "archive terms"), ("Drafts/Old/cv.txt", "draft one")):
            f = self.root / rel
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(text, encoding="utf-8")
        self.data.mkdir()
        self.db = self.data / "clark.db"
        s = self.store()
        with s.step("dashboard", "tester", place="menu") as step:
            step.create("projects", {"code": "ABC", "name": "Example Programme"})
            step.create("source_folders", {"project": "ABC", "path": str(self.root), "sort_order": 0, "excluded": ask_exclude.dump(["Archive", "Drafts/Old"])})
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
        self.assertEqual(body["left_out"], [{"folder": str(self.root), "rels": ["Archive", "Drafts/Old"]}], "read lists what is left out, relative as saved")
        self.assertEqual(self.left_files(), ["Notes/a.txt"])
        status, body = self.svc.change({"project": "ABC", "action": "include", "path": str(self.root), "rel": "Archive"})
        self.assertEqual((status, body["ok"]), (200, True), body)
        self.assertEqual(body["left_out"], [{"folder": str(self.root), "rels": ["Drafts/Old"]}], "0 lines left for that folder")
        self.assertEqual(self.stored(), ["Drafts/Old"])
        self.assertEqual(self.left_files(), ["Archive/terms.txt", "Notes/a.txt"], "its files are read again")

    def indexed(self, words):
        return sorted(p.file for p in ask_index.search(self.data, "ABC", words))

    def test_the_index_run_leaves_out_a_left_out_folder_drops_what_was_kept_and_takes_it_back_after_include_again(self):
        """Row 1542 AP2: a left-out folder is absent from an index run (also files an earlier run kept), and present on the next run after Include again."""
        folders = [str(self.root)]
        ask_index.build(self.data, "ABC", folders, self.home)                                      # an earlier run, before the folders were left out
        self.assertEqual(self.indexed("archive terms"), ["lib/Archive/terms.txt"])
        ask_index.refresh(self.data, "ABC", folders, self.home, leave_out=self.svc.left_map("ABC"))
        self.assertEqual((self.indexed("archive terms"), self.indexed("draft")), ([], []), "left out: dropped from the index")
        self.assertEqual(self.indexed("alpha"), ["lib/Notes/a.txt"], "the rest stays")
        self.assertFalse(ask_index.stale(self.data, "ABC", folders, self.home, self.svc.left_map("ABC")), "nothing changed since that run")
        self.assertEqual(self.svc.change({"project": "ABC", "action": "include", "path": str(self.root), "rel": "Archive"})[0], 200)
        self.assertTrue(ask_index.stale(self.data, "ABC", folders, self.home, self.svc.left_map("ABC")), "put back: the next run has something to read")
        ask_index.refresh(self.data, "ABC", folders, self.home, leave_out=self.svc.left_map("ABC"))
        self.assertEqual(self.indexed("archive terms"), ["lib/Archive/terms.txt"], "back in on the next run")
        self.assertEqual(self.indexed("draft"), [], "the one still left out stays out")

    def test_include_again_on_a_matching_name_sets_the_saved_folder_back_to_declined_and_one_undo_restores_both(self):
        """Row 1542 AP5: a subfolder whose name is on the 1365 list (or holds one) comes back: the saved folder's accepted goes back to 0 in the same step; one Undo restores both.
        A name that does not match leaves accepted as it was."""
        f = self.root / "Contracts"
        f.mkdir()
        (f / "c.txt").write_text("terms", encoding="utf-8")
        both = ask_exclude.dump(["Archive", "Contracts"])
        with self.store().step("dashboard", "tester", place="menu") as step:
            step.update("source_folders", f"ABC|{self.root}", {"excluded": both, "accepted": 1})
        accepted = lambda: self.store().read("source_folders", "ABC")[0]["accepted"]
        status, body = self.svc.change({"project": "ABC", "action": "include", "path": str(self.root), "rel": "Archive"})
        self.assertEqual((status, accepted()), (200, 1), "no match: accepted unchanged")
        status, body = self.svc.change({"project": "ABC", "action": "include", "path": str(self.root), "rel": "Contracts"})
        self.assertEqual((status, body["ok"], accepted()), (200, True, 0), "a match: back to Declined in the same step")
        self.assertEqual(self.stored(), [])
        status, _ = self.svc.change({"project": "ABC", "action": "undo", "apply_id": body["apply_id"]})
        self.assertEqual((status, accepted(), self.stored()), (200, 1, ["Contracts"]), "one Undo restores both")

    def test_the_files_changed_count_ignores_a_left_out_folder(self):
        """Row 1542 (Hawkeye CHANGES): a new file under a left-out subfolder is not a change: the Updating line counts only what a run would read."""
        folders = [str(self.root)]
        left = self.svc.left_map("ABC")
        ask_index.refresh(self.data, "ABC", folders, self.home, leave_out=left)
        (self.root / "Archive" / "new.txt").write_text("new archive words", encoding="utf-8")
        (self.root / "Notes" / "b.txt").write_text("beta notes", encoding="utf-8")
        self.assertEqual(ask_index.changed_by_folder(self.data, "ABC", folders, self.home, leave_out=left), {str(self.root): 1})
        self.assertEqual(ask_index.changed_by_folder(self.data, "ABC", folders, self.home), {str(self.root): 4}, "control: without the list the left-out files count too (new.txt, terms.txt, cv.txt) besides b.txt")

    def test_a_four_argument_stale_stand_in_is_still_called_with_four_arguments_when_nothing_is_left_out(self):
        """Row 1542 (Hawkeye CHANGES): the Indexer gives `stale` the left-out lists only when there are some."""
        calls = []
        ix = ask_index.Indexer(self.data, home=self.home)
        self.addCleanup(ix.shutdown)
        ix.leave_out = lambda code: {}
        with mock.patch.object(ask_index, "stale", lambda d, c, f, h: calls.append((d, c, f, h)) or False):
            self.assertFalse(ix._stale("ABC", [str(self.root)]))
        self.assertEqual(len(calls), 1)

    def test_the_background_reader_asks_for_the_left_out_list_itself(self):
        """Row 1542: an Indexer given to AskFolders reads what the person left out from the saved data on every run, so no start path can index it."""
        ix = ask_index.Indexer(self.data, home=self.home)
        self.addCleanup(ix.shutdown)
        svc = ask_folders.AskFolders(self.db, [], data_dir=self.data, home=self.home, by_user=lambda: "tester", indexer=ix)
        ix.start("ABC", [str(self.root)])
        self.assertTrue(ix.wait_idle(30))
        self.assertEqual((self.indexed("archive terms"), self.indexed("alpha")), ([], ["lib/Notes/a.txt"]))
        self.assertEqual(svc.change({"project": "ABC", "action": "include", "path": str(self.root), "rel": "Archive"})[0], 200)      # the change starts the next run itself
        self.assertTrue(ix.wait_idle(30))
        self.assertEqual(self.indexed("archive terms"), ["lib/Archive/terms.txt"])

    def test_include_again_is_one_step_with_one_undo_and_refuses_what_is_not_left_out(self):
        status, body = self.svc.change({"project": "ABC", "action": "include", "path": str(self.root), "rel": "Archive"})
        self.assertEqual(status, 200)
        status, undone = self.svc.change({"project": "ABC", "action": "undo", "apply_id": body["apply_id"]})
        self.assertEqual((status, undone["message"]), (200, ask_folders.MESSAGES["undone"]))
        self.assertEqual(self.stored(), ["Archive", "Drafts/Old"])
        self.assertEqual(undone["left_out"], [{"folder": str(self.root), "rels": ["Archive", "Drafts/Old"]}])
        for bad in ({"rel": "Notes"}, {"rel": "../x"}, {"rel": 5}, {"path": str(self.d)}):
            status, out = self.svc.change({"project": "ABC", "action": "include", "path": str(self.root), "rel": "Archive", **bad})
            self.assertEqual((status, out["ok"]), (409 if status == 409 else 400, False), (bad, out))
        self.assertEqual(self.stored(), ["Archive", "Drafts/Old"], "a refused include changes nothing")
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
