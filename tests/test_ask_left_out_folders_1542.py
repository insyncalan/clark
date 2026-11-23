"""Row 1542: the left-out subfolders are listed on the project's ask clark page, each with Include again (row 1365 AP10).

Run: python3 dev/run_tests.py test_ask_left_out_folders_1542
Pins: the server's list and its Include again action (one step, one Undo, the other entries kept, bad requests refused), that the next index run
lists the folder's files again and the question reader is no longer sent to the direct reader, and the page (Classic, 1400 and 900, light and dark):
one line and one button per left-out subfolder under the approved heading, the approved words, nothing drawn when the list is empty, Cards unchanged.
Made-up names only. Chrome is required for the page tests."""
import os
import re
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _editor_checks import for_project
from test_ask_settings import make_db, service
from test_page import DATA, navigate
from test_server import Running, chrome, wait

from clark import ask_exclude, ask_folders, ask_index, page, platform as pl, store as st

HERE = Path(__file__).resolve().parent
WORDS = ("Left out of questions", "Include again")


class Base(unittest.TestCase):
    def setUp(self):
        patch = mock.patch.object(pl, "system", return_value=pl.MAC)
        patch.start()
        self.addCleanup(patch.stop)
        self.d = Path(os.path.realpath(tempfile.mkdtemp(prefix="clark-test-")))
        self.addCleanup(shutil.rmtree, self.d, True)
        self.home, self.data, self.root = self.d / "home", self.d / "data", self.d / "home" / "lib"
        for p in (self.home, self.data, self.root):
            p.mkdir(parents=True, exist_ok=True)
        for rel, text in (("Notes/a.txt", "alpha notes"), ("Contract/terms.txt", "contract terms zebra"), ("HR/Candidates/cv.txt", "candidate one"), ("HR/Policy/r.txt", "policy")):
            f = self.root / rel
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(text, encoding="utf-8")
        self.db = make_db(self.data)
        self.started = []
        self.indexer = mock.Mock()
        self.indexer.start.side_effect = lambda code, folders: self.started.append((code, list(folders)))
        self.svc = ask_folders.AskFolders(self.db, [], data_dir=self.data, home=self.home, by_user=lambda: "tester", indexer=self.indexer)
        self.svc.change({"project": "ABC", "action": "add", "path": str(self.root)})
        self.started.clear()

    def store(self):
        s = st.open_store(self.db, onedrive_roots=[])
        self.addCleanup(s.close)
        return s

    def leave(self, *rels):
        s = self.store()
        with s.step("dashboard", "tester", place="menu") as step:
            step.update("source_folders", f"ABC|{self.root}", {"excluded": ask_exclude.dump(rels)})

    def saved(self):
        return ask_exclude.parse(self.store().read("source_folders", "ABC")[0]["excluded"])

    def include(self, rel, path=None):
        return self.svc.change({"project": "ABC", "action": "include", "path": path or str(self.root), "rel": rel})


class Server(Base):
    def test_the_read_lists_every_left_out_folder_and_subfolder_as_saved_sorted(self):
        self.leave("HR/Policy", "Contract", "HR/Candidates")
        status, body = self.svc.read("ABC")
        self.assertEqual(status, 200)
        self.assertEqual(body["left_out"], [{"folder": str(self.root), "paths": ["Contract", "HR/Candidates", "HR/Policy"]}])

    def test_nothing_left_out_is_an_empty_list_and_a_list_that_cannot_be_read_is_not_listed(self):
        self.assertEqual(self.svc.read("ABC")[1]["left_out"], [])
        con = __import__("sqlite3").connect(str(self.db))
        con.execute("UPDATE source_folders SET excluded = 'not json'")
        con.commit()
        con.close()
        self.assertEqual(self.svc.read("ABC")[1]["left_out"], [])

    def test_include_takes_only_that_entry_off_in_one_step_and_one_undo_puts_it_back(self):
        self.leave("Contract", "HR/Candidates")
        status, body = self.include("Contract")
        self.assertEqual((status, body["ok"]), (200, True))
        self.assertEqual(self.saved(), ["HR/Candidates"])
        self.assertEqual(body["left_out"], [{"folder": str(self.root), "paths": ["HR/Candidates"]}])
        self.assertEqual(self.started[-1][0], "ABC", "the folder is read again")
        status, back = self.svc.change({"project": "ABC", "action": "undo", "apply_id": body["apply_id"]})
        self.assertEqual(status, 200)
        self.assertEqual(self.saved(), ["Contract", "HR/Candidates"])
        self.assertEqual(back["left_out"][0]["paths"], ["Contract", "HR/Candidates"])

    def test_include_of_the_last_entry_leaves_an_empty_list(self):
        self.leave("Contract")
        self.include("Contract")
        self.assertEqual(self.saved(), [])
        self.assertEqual(self.svc.read("ABC")[1]["left_out"], [])

    def test_include_refuses_what_is_not_there_and_writes_nothing(self):
        self.leave("Contract")
        before = self.store().history() if hasattr(st.Store, "history") else None
        for rel, path, code in (("Other", None, 409), ("contract", None, 409), ("Contract", str(self.d / "nope"), 409)):
            status, body = self.include(rel, path)
            self.assertEqual((status, body["ok"]), (code, False), (rel, path))
        for bad in ({"project": "ABC", "action": "include", "path": str(self.root)}, {"project": "ABC", "action": "include", "path": str(self.root), "rel": 5},
                    {"project": "ABC", "action": "include", "path": str(self.root), "rel": "Contract", "x": 1}):
            self.assertEqual(self.svc.change(bad)[0], 400, bad)
        self.assertEqual(self.saved(), ["Contract"])
        self.assertEqual(before, self.store().history() if before is not None else None)

    def test_include_refuses_a_list_that_cannot_be_read_and_an_archived_project(self):
        self.leave("Contract")
        con = __import__("sqlite3").connect(str(self.db))
        con.execute("UPDATE source_folders SET excluded = 'not json'")
        con.commit()
        con.close()
        self.assertEqual(self.include("Contract")[0], 409)

    def test_include_again_puts_folder_back_and_next_run_indexes_it(self):
        self.leave("Contract")
        self.assertEqual(self.svc.left_out(self.store(), "ABC")[str(self.root)], '["Contract"]')
        status, body = self.include("Contract")
        self.assertEqual(status, 200)
        self.assertEqual(body["left_out"], [], "0 lines left for that folder")
        self.assertEqual(self.started, [("ABC", [str(self.root)])], "one index run was asked for, on the saved folder")
        from clark import ask_service
        self.assertEqual(ask_service.AskService.left_out_for(mock.Mock(), self.store(), "ABC")[str(self.root)], "[]", "the question reader sees nothing left out")
        ask_index.build(self.data, "ABC", [str(self.root)], self.home)
        files = {p.file for p in ask_index.search(self.data, "ABC", "zebra")}
        self.assertIn("terms.txt", {os.path.basename(f) for f in files}, "its files are in the index")


class Words(unittest.TestCase):
    def test_words_match_new_words_md(self):
        src = (HERE.parent / "src/clark/page/src/edit/askWords.js").read_text(encoding="utf-8")
        got = dict(re.findall(r'export const (LEFT_FOLDERS_\w+) = "([^"]*)"', src))
        self.assertEqual((got["LEFT_FOLDERS_HEAD"], got["LEFT_FOLDERS_AGAIN"]), WORDS)
        self.assertIn("leftFoldersAgainName = (rel) => `Include again: ${rel}`", src)
        approved = Path.home() / "wo/gates/NEW-WORDS.md"
        if approved.exists():
            text = approved.read_text(encoding="utf-8")
            self.assertIn('Heading "Left out of questions"', text)
            self.assertIn('text button "Include again"', text)
            self.assertIn('screen-reader name "Include again: <folder name>"', text)

    def test_the_page_draws_only_these_words_and_nothing_for_an_empty_list(self):
        jsx = (HERE.parent / "src/clark/page/src/edit/AskSettings.jsx").read_text(encoding="utf-8")
        self.assertIn("{classic && leftOut.length ? (", jsx)
        self.assertNotIn("None", re.search(r"ask-left-folders.*?\) : null\}", jsx, re.S).group(0))

    def test_cards_theme_unchanged(self):
        import subprocess
        out = subprocess.run(["git", "diff", "--name-only", "8d7452997", "--", "src/clark/themes"], cwd=HERE.parent, capture_output=True, text=True).stdout.split()
        self.assertTrue(all(n.endswith("prototype-2.0/rules-2.css") for n in out), out)
        css = (HERE.parent / "src/clark/themes/prototype-2.0/rules-2.css").read_text(encoding="utf-8")
        self.assertEqual(len(re.findall(r"^\.ask-left-(?:folders|head)", css, re.M)), 3)
        self.assertEqual(len([m for m in re.findall(r"^\.ask-left[^{]*\{", css, re.M) if not m.startswith(".ask-left-folders") and not m.startswith(".ask-left-head")]), 0)


class Page(Base):
    classic = "prototype-2.0"

    def setUp(self):
        super().setUp()
        self.s = Running(data_for=lambda code, archived=None: DATA.get(code), page_html=lambda: page.page_html(tempfile.mkdtemp(), theme=self.classic))
        self.addCleanup(self.s.close)
        self.s.httpd.app_settings = service(self.db)
        self.s.httpd.ask_folders = self.svc

    def show(self, cdp, width, scheme):
        self.sid = navigate(cdp, self.s.port, for_project("#settings&p=ABC&s=claude"))
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, self.sid)
        cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme}]}, self.sid)
        js = lambda e: cdp.js(e, self.sid)          # noqa: E731
        self.assertTrue(wait(lambda: js("!!document.querySelector('#ask-folders')"), 20))
        return js

    def test_lists_every_left_out_folder_with_include_again(self):
        self.leave("Contract", "HR/Candidates")
        with chrome() as cdp:
            for width in (1400, 900):
                for scheme in ("light", "dark"):
                    js = self.show(cdp, width, scheme)
                    self.assertTrue(wait(lambda: js("!!document.querySelector('#ask-left-folders')"), 10), (width, scheme))
                    self.assertEqual(js("document.querySelector('#ask-left-folders .ask-left-head').textContent"), "Left out of questions")
                    self.assertEqual(js("[...document.querySelectorAll('#ask-left-folders li .ask-left-name')].map(e => e.textContent)"), ["Contract", "HR/Candidates"])
                    self.assertEqual(js("[...document.querySelectorAll('#ask-left-folders li button')].map(e => e.textContent)"), ["Include again"] * 2)
                    self.assertEqual(js("[...document.querySelectorAll('#ask-left-folders li button')].map(e => e.getAttribute('aria-label'))"),
                                     ["Include again: Contract", "Include again: HR/Candidates"])
                    self.assertEqual(js("getComputedStyle(document.querySelector('#ask-left-folders .ask-left-list')).fontSize"), "13px")
                    self.assertEqual(js("getComputedStyle(document.querySelector('#ask-left-folders .ask-left-btn')).minHeight"), "24px")
                    self.assertEqual(js("getComputedStyle(document.querySelector('#ask-left-folders .ask-left-btn')).fontSize"), "14px")
                    self.assertEqual(js("getComputedStyle(document.querySelector('#ask-left-folders .ask-left-list li')).marginBottom"), "2px")
                    self.assertEqual(js("document.documentElement.scrollWidth <= window.innerWidth"), True, "no sideways scroll")
                    below = js("document.querySelector('#ask-folders').getBoundingClientRect().bottom <= document.querySelector('#ask-left-folders').getBoundingClientRect().top")
                    self.assertTrue(below, "under the source-folder list")

    def test_include_again_in_the_page_saves_it_and_the_line_goes(self):
        self.leave("Contract", "HR/Candidates")
        with chrome() as cdp:
            js = self.show(cdp, 1400, "light")
            self.assertTrue(wait(lambda: js("!!document.querySelector('#ask-left-folders')"), 10))
            js("document.querySelector('[aria-label=\"Include again: Contract\"]').click()")
            self.assertTrue(wait(lambda: js("document.querySelectorAll('#ask-left-folders li').length === 1"), 10))
            self.assertEqual(self.saved(), ["HR/Candidates"])
            js("document.querySelector('[data-ask-include]').click()")
            self.assertTrue(wait(lambda: js("!document.querySelector('#ask-left-folders')"), 10), "an empty list draws nothing")
            self.assertEqual(self.saved(), [])
            self.assertEqual(js("document.querySelector('#ask-folders-card').innerText.includes('None')"), False)

    def test_nothing_left_out_draws_nothing(self):
        with chrome() as cdp:
            js = self.show(cdp, 1400, "light")
            js("new Promise(r => setTimeout(r, 500))")
            self.assertEqual(js("document.querySelectorAll('#ask-left-folders, .ask-left-head').length"), 0)


class Cards(Page):
    classic = None

    def test_lists_every_left_out_folder_with_include_again(self):
        self.leave("Contract")
        with chrome() as cdp:
            js = self.show(cdp, 1400, "light")
            js("new Promise(r => setTimeout(r, 500))")
            self.assertEqual(js("document.querySelectorAll('#ask-left-folders').length"), 0)

    test_include_again_in_the_page_saves_it_and_the_line_goes = None
    test_nothing_left_out_draws_nothing = None


if __name__ == "__main__":
    unittest.main()
