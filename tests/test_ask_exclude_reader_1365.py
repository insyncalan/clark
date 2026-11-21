"""Row 1365: Leave these subfolders out, the reader and the question.

Run: python3 dev/run_tests.py test_ask_exclude_reader_1365
Pins: the reader never opens a file in a left-out subfolder, a list that cannot be read means the folder is not read at all, left_out_path, and the question never sends a left-out file's text. Made-up names only.
"""
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _paths import SRC  # noqa: F401

import test_ask_route as tr
import test_ask_exclude_1365 as core
from clark import ask_passages, ask_service, reach, store as st


class Reader(core.Base):
    def test_the_reader_never_opens_a_file_in_a_left_out_subfolder(self):
        self.tree()
        opened = []
        real = reach.read_bytes

        def watch(path, *a, **k):
            opened.append(os.path.relpath(path, self.root))
            return real(path, *a, **k)

        with mock.patch.object(reach, "read_bytes", side_effect=watch):
            got = ask_passages.folder_data([str(self.root)], self.data, "terms candidate policy alpha", home=self.home,
                                           leave_out={str(self.root): '["Contract", "HR/Candidates"]'})
        self.assertEqual(sorted(opened), ["HR/Policy/rules.txt", "Notes/a.txt"])
        text = "\n".join(p.text for p in got.passages)
        self.assertIn("policy text", text)
        self.assertNotIn("contract terms", text)
        self.assertNotIn("candidate one", text)
        self.assertEqual((got.safety, got.other), (0, 0))

    def test_with_nothing_left_out_the_whole_folder_is_read(self):
        self.tree()
        for lo in (None, {}, {str(self.root): "[]"}, {str(self.root): []}):
            got = ask_passages.folder_data([str(self.root)], self.data, "terms candidate policy alpha", home=self.home, leave_out=lo)
            self.assertEqual(len(got.passages), 5, lo)

    def test_a_list_that_cannot_be_read_means_the_folder_is_not_read_at_all(self):
        self.tree()
        other = self.d / "home" / "second"
        other.mkdir()
        (other / "ok.txt").write_text("second folder text", encoding="utf-8")
        for bad in ("", "oops", '["../x"]', "{}", 5, b"[]"):
            got = ask_passages.folder_data([str(self.root), str(other)], self.data, "second text alpha", home=self.home, leave_out={str(self.root): bad})
            text = "\n".join(p.text for p in got.passages)
            self.assertNotIn("alpha notes", text, repr(bad))
            self.assertIn("second folder text", text, "another folder is still read")
            self.assertEqual(got.safety, 1, repr(bad))

    def test_the_service_hands_the_reader_each_saved_folders_own_list(self):
        s = self.store()
        with s.step("dashboard", "tester", place="menu") as step:
            step.create("projects", {"code": "ABC", "name": "Example Programme"})
            step.create("projects", {"code": "OTH", "name": "Other Programme"})
            step.create("source_folders", {"project": "ABC", "path": str(self.root), "sort_order": 0, "excluded": '["Contract"]'})
            step.create("source_folders", {"project": "OTH", "path": str(self.home), "sort_order": 0, "excluded": '["Z"]'})
        svc = ask_service.AskService.__new__(ask_service.AskService)
        self.assertEqual(svc.left_out_for(s, "ABC"), {str(self.root): '["Contract"]'})
        self.assertEqual(svc.left_out_for(s, "OTH"), {str(self.home): '["Z"]'})
        self.assertEqual(svc.left_out_for(s, "NONE"), {})


class LeftOutPath(core.Base):
    """ask_passages.left_out_path: whole names below the saved folder, never a text prefix of either the folder or the left-out name."""

    def cut(self, rel, listed, folder=None, key=None):
        folder = folder or self.root
        return ask_passages.left_out_path(self.home / rel, {str(key or folder): listed}, self.home)

    def test_the_left_out_folder_and_everything_below_it_is_cut_and_the_saved_folder_itself_is_not(self):
        self.assertTrue(self.cut("lib/Archive", '["Archive"]'))
        self.assertTrue(self.cut("lib/Archive/a.txt", '["Archive"]'))
        self.assertTrue(self.cut("lib/Archive/deep/b.txt", '["Archive"]'))
        self.assertFalse(self.cut("lib", '["Archive"]'))
        self.assertFalse(self.cut("lib/Notes/a.txt", '["Archive"]'))

    def test_a_name_that_only_starts_or_ends_like_a_left_out_name_is_not_cut(self):
        for rel in ("lib/Archive2/a.txt", "lib/Archived", "lib/OldArchive/a.txt", "lib/Arch/a.txt", "lib/Archiv"):
            self.assertFalse(self.cut(rel, '["Archive"]'), rel)

    def test_a_left_out_name_is_matched_by_whole_names_at_each_level_below_the_folder(self):
        self.assertTrue(self.cut("lib/HR/Candidates/cv.txt", '["HR/Candidates"]'))
        self.assertFalse(self.cut("lib/HR/Policy/rules.txt", '["HR/Candidates"]'))
        self.assertFalse(self.cut("lib/HR/Candidates2/cv.txt", '["HR/Candidates"]'))
        self.assertFalse(self.cut("lib/Other/HR/Candidates/cv.txt", '["HR/Candidates"]'))

    def test_case_and_spelling_do_not_hide_a_left_out_name(self):
        self.assertTrue(self.cut("lib/ARCHIVE/a.txt", '["archive"]'))
        self.assertTrue(self.cut("lib/Cafe\u0301/a.txt", json.dumps(["Caf\u00e9"])))
        self.assertFalse(self.cut("lib/Cafe/a.txt", json.dumps(["Caf\u00e9"])))

    def test_a_list_belongs_to_the_saved_folder_that_holds_the_path_and_not_to_one_named_like_it(self):
        sibling = self.home / "lib2"
        (sibling / "Archive").mkdir(parents=True)
        self.assertFalse(self.cut("lib2/Archive/a.txt", '["Archive"]'))
        self.assertTrue(self.cut("lib2/Archive/a.txt", '["Archive"]', folder=sibling))
        self.assertFalse(self.cut("lib/Archive/a.txt", '["Archive"]', folder=sibling))
        (self.root / "li").mkdir()
        self.assertFalse(ask_passages.left_out_path(self.root / "Archive", {str(self.home / "li"): '["Archive"]'}, self.home))

    def test_nothing_listed_cuts_nothing_and_an_unreadable_list_or_path_cuts_everything(self):
        self.assertFalse(ask_passages.left_out_path(self.root / "a.txt", None, self.home))
        self.assertFalse(ask_passages.left_out_path(self.root / "a.txt", {}, self.home))
        self.assertFalse(self.cut("lib/a.txt", "[]"))
        for bad in ("not json", '"Archive"', '["../x"]'):
            self.assertTrue(self.cut("lib/a.txt", bad), bad)
        self.assertTrue(ask_passages.left_out_path("relative/path", {str(self.root): '["Archive"]'}, self.home))


class OnTheRoute(tr.Base):
    """The question itself: a left-out subfolder's text never reaches the provider; a list that cannot be read sends nothing from that folder."""

    def setUp(self):
        patch = mock.patch.object(reach.platform, "system", return_value=reach.platform.MAC)
        patch.start()
        self.addCleanup(patch.stop)
        super().setUp()
        patch = mock.patch.object(reach.platform, "system", return_value=reach.platform.MAC)
        patch.start()
        self.addCleanup(patch.stop)
        self.mine = Path(os.path.realpath(tempfile.mkdtemp(prefix="clark-mine-")))
        self.addCleanup(shutil.rmtree, self.mine, True)
        (self.mine / "plan.txt").write_text("FOLDERKEEP the cutover plan is booked", encoding="utf-8")
        (self.mine / "Contract").mkdir()
        (self.mine / "Contract" / "terms.txt").write_text("FOLDEROUT the cutover plan terms for the cutover plan, the cutover plan again", encoding="utf-8")
        self.store = st.open_store(self.db, onedrive_roots=[])
        with self.store.step("dashboard", "tester", place="menu") as s:
            s.create("source_folders", {"project": tr.CODE, "path": str(self.mine), "sort_order": 1})
        self.addCleanup(self.store.close)

    def set(self, value):
        with self.store.step("dashboard", "tester", place="menu") as s:
            s.update("source_folders", f"{tr.CODE}|{self.mine}", {"excluded": value})

    def sent(self):
        """The question is asked; (what was sent to the provider, what the reader was given as its list of left-out subfolders, what the reader returned)."""
        seen = []
        real = ask_passages.folder_data

        def watch(*a, **k):
            got = real(*a, **k)
            seen.append((a[6] if len(a) > 6 else k.get("leave_out"), got))
            return got

        with mock.patch.object(ask_passages, "folder_data", side_effect=watch):
            status, got = self.question("What is the cutover plan?")
        self.assertEqual(status, 200, got)
        self.assertEqual(len(seen), 1)
        return self.provider.sent[-1], seen[0][0], "\n".join(p.text for p in seen[0][1].passages), seen[0][1]

    def test_the_reader_is_given_each_folders_own_stored_list_and_the_left_out_text_never_reaches_the_provider(self):
        sent, given, read, _ = self.sent()
        self.assertEqual(given, {str(self.mine): "[]"})
        self.set('["Contract"]')
        sent, given, read, _ = self.sent()
        self.assertEqual(given, {str(self.mine): '["Contract"]'})
        self.assertNotIn("FOLDEROUT", sent)
        self.assertNotIn("FOLDEROUT", read)

    def test_a_list_that_cannot_be_read_sends_nothing_from_the_folder(self):
        self.store.con.execute("UPDATE source_folders SET excluded = 'garbage'")
        self.store.con.commit()
        sent, given, read, data = self.sent()
        self.assertEqual(given, {str(self.mine): "garbage"})
        self.assertEqual((read, data.safety), ("", 1))
        self.assertNotIn("FOLDERKEEP", sent)
        self.assertNotIn("FOLDEROUT", sent)


if __name__ == "__main__":
    unittest.main()
