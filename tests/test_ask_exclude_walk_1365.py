"""Row 1365: Leave these subfolders out, the folder walk.

Run: python3 dev/run_tests.py test_ask_exclude_walk_1365
Pins: the folder walk (reach.readable_files) never enters a left-out subfolder and takes nothing from the caps. Made-up names only.
"""
import os
from unittest import mock

from _paths import SRC  # noqa: F401

import test_ask_exclude_1365 as core
from clark import ask_passages, reach


class Walk(core.Base):
    def listed(self, leave_out=None, **kw):
        if leave_out is None:
            got = reach.readable_files([str(self.root)], self.data, None, self.home)
        else:
            got = reach.readable_files([str(self.root)], self.data, None, self.home, {f: ask_passages._gone(rels) for f, rels in leave_out.items()})
        return sorted(os.path.relpath(f, self.root) for f in got.files), got

    def test_with_no_list_every_file_is_listed_and_an_empty_list_changes_nothing(self):
        self.tree()
        every = ["Contract/deep/more.txt", "Contract/terms.txt", "HR/Candidates/cv.txt", "HR/Policy/rules.txt", "Notes/a.txt"]
        self.assertEqual(self.listed()[0], every)
        self.assertEqual(self.listed({})[0], every)
        self.assertEqual(self.listed({str(self.root): []})[0], every)

    def test_a_left_out_subfolder_and_all_below_it_are_never_listed(self):
        self.tree()
        files, got = self.listed({str(self.root): ["Contract", "HR/Candidates"]})
        self.assertEqual(files, ["HR/Policy/rules.txt", "Notes/a.txt"])
        self.assertEqual(got.skipped, 0, "left out by the person is not 'left out for safety'")

    def test_nested_case_trailing_slash_and_a_file_path_are_matched_as_stored(self):
        self.tree()
        self.assertEqual(self.listed({str(self.root): ["contract/DEEP"]})[0], ["Contract/terms.txt", "HR/Candidates/cv.txt", "HR/Policy/rules.txt", "Notes/a.txt"])
        self.assertEqual(self.listed({str(self.root): ["Notes/a.txt"]})[0], ["Contract/deep/more.txt", "Contract/terms.txt", "HR/Candidates/cv.txt", "HR/Policy/rules.txt"])
        self.assertEqual(self.listed({str(self.root): ["Notes"]})[0], ["Contract/deep/more.txt", "Contract/terms.txt", "HR/Candidates/cv.txt", "HR/Policy/rules.txt"])

    def test_a_name_that_only_starts_the_same_is_not_left_out(self):
        self.put("Contract/a.txt")
        self.put("Contracts/b.txt")
        self.put("Sub/Contract/c.txt")
        self.assertEqual(self.listed({str(self.root): ["Contract"]})[0], ["Contracts/b.txt", "Sub/Contract/c.txt"])

    def test_the_list_belongs_to_its_own_saved_folder_only(self):
        self.tree()
        self.assertEqual(len(self.listed({str(self.home / "elsewhere"): ["Contract", "Notes", "HR"]})[0]), 5)

    def test_a_link_out_of_the_folder_is_still_not_followed_and_left_out_names_do_not_unblock_anything(self):
        self.tree()
        outside = self.d / "outside"
        outside.mkdir()
        (outside / "secret.txt").write_text("outside", encoding="utf-8")
        os.symlink(outside, self.root / "Escape")
        files, _ = self.listed({str(self.root): ["Notes"]})
        self.assertNotIn("Escape/secret.txt", files)

    def test_a_left_out_subfolder_is_never_even_opened(self):
        self.tree()
        opened = []
        real = os.scandir

        def watch(path=".", *a, **k):
            opened.append(os.fspath(path))
            return real(path, *a, **k)

        with mock.patch.object(os, "scandir", side_effect=watch):
            self.listed({str(self.root): ["Contract", "HR/Candidates"]})
        self.assertFalse([p for p in opened if p.endswith("Contract") or "Candidates" in p or p.endswith("deep")], opened)
        self.assertTrue([p for p in opened if p.endswith("Notes")], "the rest is walked")

    def test_left_out_files_take_nothing_from_the_listing_cap(self):
        for i in range(5):
            self.put(f"Contract/f{i}.txt")
        self.put("Keep/a.txt")
        self.put("Keep/b.txt")
        with mock.patch.object(reach, "MAX_FILES", 2):
            files, got = self.listed({str(self.root): ["Contract"]})
        self.assertEqual(files, ["Keep/a.txt", "Keep/b.txt"])
        self.assertFalse(got.stopped)

    def test_two_spellings_of_one_saved_folder_each_leave_their_own_subfolders_out(self):
        self.tree()
        link = self.d / "link-to-lib"
        os.symlink(self.root, link)
        opened = []
        real = os.scandir

        def watch(path=".", *a, **k):
            opened.append(os.fspath(path))
            return real(path, *a, **k)

        with mock.patch.object(os, "scandir", side_effect=watch):
            files, _ = self.listed({str(self.root): ["Contract"], str(link): ["Notes"]})
        self.assertEqual(files, ["HR/Candidates/cv.txt", "HR/Policy/rules.txt"])
        self.assertFalse([p for p in opened if p.endswith("Contract") or p.endswith("Notes")], opened)

    def test_a_parent_saved_beside_a_child_with_a_list_still_leaves_the_childs_subfolders_out(self):
        self.tree()
        child = self.root / "HR"
        both = {str(child): ask_passages._gone(["Candidates"])}
        for order in ([str(self.root), str(child)], [str(child), str(self.root)]):
            got = reach.readable_files(order, self.data, None, self.home, both)
            names = sorted(os.path.relpath(f, self.root) for f in got.files)
            self.assertEqual(names, ["Contract/deep/more.txt", "Contract/terms.txt", "HR/Policy/rules.txt", "Notes/a.txt"], order)
        data = ask_passages.folder_data([str(self.root), str(child)], self.data, "candidate policy alpha terms", home=self.home,
                                        leave_out={str(child): '["Candidates"]'})
        self.assertNotIn("candidate one", "\n".join(p.text for p in data.passages))
        self.assertIn("policy text", "\n".join(p.text for p in data.passages))

    def test_a_childs_list_cuts_only_below_the_child_and_not_a_same_named_folder_elsewhere_in_the_parent(self):
        self.tree()
        self.put("Other/Candidates/keep.txt")
        self.put("Other/HR/Candidates/keep2.txt")
        child = self.root / "HR"
        got = reach.readable_files([str(self.root), str(child)], self.data, None, self.home, {str(child): ask_passages._gone(["Candidates"])})
        names = sorted(os.path.relpath(f, self.root) for f in got.files)
        self.assertEqual(names, ["Contract/deep/more.txt", "Contract/terms.txt", "HR/Policy/rules.txt", "Notes/a.txt", "Other/Candidates/keep.txt",
                                 "Other/HR/Candidates/keep2.txt"])

    def test_a_parents_own_list_does_not_cut_a_child_saved_folder_named_the_same(self):
        self.tree()
        child = self.root / "HR"
        got = reach.readable_files([str(child)], self.data, None, self.home, {str(self.root): ask_passages._gone(["HR"])})
        self.assertEqual(sorted(os.path.relpath(f, child) for f in got.files), ["Candidates/cv.txt", "Policy/rules.txt"])

    def test_a_left_out_name_is_cut_in_a_folder_added_after_the_list_was_saved(self):
        self.put("Notes/a.txt")
        later = {str(self.root): ["Archive", "Notes/Old"]}
        self.assertEqual(self.listed(later)[0], ["Notes/a.txt"], "nothing of that name yet: nothing changes")
        self.put("Archive/b.txt")
        self.put("Notes/Old/c.txt")
        self.put("Notes/New/d.txt")
        self.assertEqual(self.listed(later)[0], ["Notes/New/d.txt", "Notes/a.txt"], "a folder added later with a left-out name is left out too")

    def test_a_left_out_folder_the_system_would_skip_for_safety_is_not_counted_either(self):
        self.put(".ssh/id_rsa")
        self.put("Keep/a.txt")
        files, got = self.listed()
        self.assertEqual((files, got.skipped), (["Keep/a.txt"], 1), "unlisted: counted as left out for safety")
        files, got = self.listed({str(self.root): [".ssh"]})
        self.assertEqual((files, got.skipped), (["Keep/a.txt"], 0), "left out by the person first: not counted, not looked at")
        with mock.patch.object(reach, "MAX_ENTRIES", 2):
            files, got = self.listed({str(self.root): [".ssh"]})
        self.assertEqual((files, got.stopped), (["Keep/a.txt"], False), "and it takes nothing from the entry cap")

    def test_a_left_out_file_that_looks_like_a_secret_is_never_read_or_counted(self):
        self.put("Notes/a.txt", "alpha notes")
        self.put("Notes/pw.txt", "password = " + "hunter2" * 3)
        got = ask_passages.folder_data([str(self.root)], self.data, "alpha password", home=self.home, leave_out={str(self.root): '["Notes/pw.txt"]'})
        self.assertEqual((got.safety, got.secret_labels), (0, ()), "never reached the secret screen")
        again = ask_passages.folder_data([str(self.root)], self.data, "alpha password", home=self.home)
        self.assertEqual(again.safety, 1, "without the list the same file is a secret left out for safety")

    def test_a_folder_that_is_not_in_the_list_of_saved_folders_or_cannot_be_resolved_is_ignored(self):
        self.tree()
        got = reach.readable_files([str(self.root)], self.data, None, self.home, {f: ask_passages._gone(["Notes"]) for f in ("relative/path", "", "bad\x00")})
        self.assertEqual(len(got.files), 5)
