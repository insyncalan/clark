"""Row 1365: Leave these subfolders out. A person keeps a whole folder for asking and leaves named subfolders out of it.

Run: python3 dev/run_tests.py test_ask_exclude_1365
Pins: the one place for the rules (ask_exclude.py), the schema step 34 (source_folders.excluded, default nothing left out, forward only, a second
run changes nothing), what the store accepts, that the folder walk (reach.readable_files, which the question's reader uses) never enters a left-out
subfolder and that it takes nothing from the caps, that the reader never opens a file in one, that a list that cannot be read means the folder is not
read at all, and the route action that saves the flagged subfolders. Made-up names only; no file is read by the name scan.
"""
import json
import os
import shutil
import sqlite3
import tempfile
import unicodedata
import unittest
from pathlib import Path
from unittest import mock

from _paths import SRC  # noqa: F401

import test_ask_route as tr
from clark import ask_exclude as ex, ask_passages, ask_service, platform as pl, reach, store as st
from clark.store import Invalid


class Rules(unittest.TestCase):
    def test_clean_keeps_a_plain_relative_path_and_drops_one_trailing_slash(self):
        self.assertEqual(ex.clean("Contract"), "Contract")
        self.assertEqual(ex.clean("Contract/"), "Contract")
        self.assertEqual(ex.clean("HR/Candidates"), "HR/Candidates")
        self.assertEqual(ex.clean("Café"), "Café", "kept in NFC")

    def test_clean_refuses_everything_that_is_not_a_plain_relative_path(self):
        for bad in ("", "/", "/abs", "/abs/x", ".", "..", "a/..", "../a", "a/./b", "a//b", "a/b//", " a", "a ", "a/ b", "a|b", "a\\b", "a\nb", "a\x00b",
                    "a b", "x" * 501, None, 5, ["a"], b"a"):
            self.assertIsNone(ex.clean(bad), repr(bad))
        self.assertEqual(ex.clean("x" * 500), "x" * 500)

    def test_parse_reads_the_stored_list_and_a_missing_column_means_nothing_left_out(self):
        self.assertEqual(ex.parse(None), [])
        self.assertEqual(ex.parse("[]"), [])
        self.assertEqual(ex.parse('["a", "b/c"]'), ["a", "b/c"])
        self.assertEqual(ex.parse(["a", "a"]), ["a"], "each once")

    def test_parse_refuses_what_it_cannot_read_and_never_returns_an_empty_list_for_it(self):
        for bad in ("", "not json", "{}", '"a"', "5", "null", '["a/"]', '["../a"]', '["/a"]', '[5]', '[""]', '["a", 5]', 5, b"[]", True,
                    json.dumps([f"d{i}" for i in range(ex.MAX_LEFT_OUT + 1)]), "[" + '"a",' * 5000 + '"a"]'):
            with self.assertRaises(ValueError, msg=repr(bad)[:60]):
                ex.parse(bad)
        self.assertEqual(len(ex.parse(json.dumps([f"d{i}" for i in range(ex.MAX_LEFT_OUT)]))), ex.MAX_LEFT_OUT)

    def test_parse_reads_every_path_of_a_list_and_the_size_limit_is_exact(self):
        self.assertEqual(ex.parse(["a", "b", "c/d"]), ["a", "b", "c/d"])
        for n, ok in ((ex.MAX_RAW, True), (ex.MAX_RAW + 1, False)):
            raw = '["a"' + " " * (n - 5) + "]"
            self.assertEqual(len(raw), n)
            if ok:
                self.assertEqual(ex.parse(raw), ["a"])
            else:
                with self.assertRaises(ValueError):
                    ex.parse(raw)

    def test_dump_keeps_letters_as_letters(self):
        self.assertEqual(ex.dump(["Caf\u00e9"]), '["Caf\u00e9"]')

    def test_dump_is_sorted_each_once_and_reads_back(self):
        self.assertEqual(ex.dump(["b", "a", "b"]), '["a", "b"]')
        self.assertEqual(ex.dump([]), "[]")
        self.assertEqual(ex.parse(ex.dump(["Café", "x/y"])), ["Café", "x/y"])

    def test_left_out_matches_the_folder_and_what_is_below_it_by_whole_names_ignoring_case_and_spelling(self):
        L = ["Contract", "HR/Candidates"]
        for rel in ("Contract", "contract", "CONTRACT/terms.txt", "Contract/a/b/c.docx", "hr/candidates", "HR/Candidates/cv.pdf", ("Contract", "x"), ["hr", "CANDIDATES"]):
            self.assertTrue(ex.left_out(rel, L), rel)
        for rel in ("Contracts", "Contract2", "Cont", "Plain/Contract", "HR", "HR/Other", "HR/Candidate", "x/HR/Candidates", ""):
            self.assertFalse(ex.left_out(rel, L), rel)
        self.assertFalse(ex.left_out("Contract", []))
        self.assertFalse(ex.left_out("Contract", ()))
        nfd = unicodedata.normalize("NFD", "Café")
        self.assertTrue(ex.left_out(nfd + "/a", ["Café"]))
        self.assertTrue(ex.left_out("Straße/a", ["STRASSE"]), "casefold, not lower")


class Base(unittest.TestCase):
    def setUp(self):
        patch = mock.patch.object(pl, "system", return_value=pl.MAC)
        patch.start()
        self.addCleanup(patch.stop)
        self.d = Path(os.path.realpath(tempfile.mkdtemp(prefix="clark-test-")))
        self.addCleanup(shutil.rmtree, self.d, True)
        self.data = self.d / "data"
        self.home = self.d / "home"
        self.root = self.home / "lib"
        for p in (self.data, self.home, self.root):
            p.mkdir(parents=True)
        self.db = self.data / "clark.db"

    def put(self, rel, text="plan text"):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return p

    def store(self):
        s = st.open_store(self.db, onedrive_roots=[])
        self.addCleanup(s.close)
        return s

    def tree(self):
        self.put("Notes/a.txt", "alpha notes")
        self.put("Contract/terms.txt", "contract terms")
        self.put("Contract/deep/more.txt", "deep terms")
        self.put("HR/Candidates/cv.txt", "candidate one")
        self.put("HR/Policy/rules.txt", "policy text")


class Schema(Base):
    def test_a_new_file_has_the_column_with_nothing_left_out_and_step_34_is_in_the_table(self):
        s = self.store()
        with s.step("dashboard", "tester", place="menu") as step:
            step.create("projects", {"code": "ABC", "name": "Example Programme"})
            step.create("source_folders", {"project": "ABC", "path": str(self.root), "sort_order": 0})
        self.assertEqual(s.read("source_folders", "ABC")[0]["excluded"], "[]")
        self.assertEqual(st.SCHEMA_VERSION, 34)
        self.assertIn((34, st.migrate_source_exclusions), st.MIGRATIONS)
        self.assertEqual(st.EXCLUDED_STEP, 34)

    def test_the_migration_adds_the_column_with_nothing_left_out_keeps_rows_and_a_second_run_changes_nothing(self):
        con = sqlite3.connect(":memory:")
        con.row_factory = sqlite3.Row
        con.execute("CREATE TABLE source_folders (project TEXT NOT NULL, path TEXT NOT NULL, sort_order INTEGER NOT NULL, PRIMARY KEY (project, path))")
        con.execute("INSERT INTO source_folders VALUES ('ABC', '/x/y', 3)")
        st.migrate_source_exclusions(con)
        st.migrate_source_exclusions(con)
        self.assertEqual([tuple(r) for r in con.execute("SELECT project, path, sort_order, excluded FROM source_folders")], [("ABC", "/x/y", 3, "[]")])
        self.assertEqual([r["name"] for r in con.execute("PRAGMA table_info(source_folders)")].count("excluded"), 1)
        empty = sqlite3.connect(":memory:")
        empty.row_factory = sqlite3.Row
        st.migrate_source_exclusions(empty)      # no table: nothing to do, nothing fails
        self.assertEqual(list(empty.execute("SELECT name FROM sqlite_master")), [])

    def test_the_schema_and_the_step_say_the_same_column_text(self):
        s = self.store()
        made = {r["name"]: (r["type"], r["notnull"], r["dflt_value"]) for r in s.con.execute("PRAGMA table_info(source_folders)")}
        old = sqlite3.connect(":memory:")
        old.row_factory = sqlite3.Row
        old.execute("CREATE TABLE source_folders (project TEXT, path TEXT, sort_order INTEGER)")
        st.migrate_source_exclusions(old)
        stepped = {r["name"]: (r["type"], r["notnull"], r["dflt_value"]) for r in old.execute("PRAGMA table_info(source_folders)")}
        self.assertEqual(stepped["excluded"], made["excluded"])
        self.assertEqual(made["excluded"], ("TEXT", 1, "'[]'"))

    def test_the_database_refuses_a_list_that_is_not_text_or_over_the_size(self):
        s = self.store()
        with s.step("dashboard", "tester", place="menu") as step:
            step.create("projects", {"code": "ABC", "name": "Example Programme"})
            step.create("source_folders", {"project": "ABC", "path": str(self.root), "sort_order": 0})
        for sql, args in (("UPDATE source_folders SET excluded = ?", ("x" * 20001,)), ("UPDATE source_folders SET excluded = NULL", ())):
            with self.assertRaises(sqlite3.IntegrityError, msg=sql):
                s.con.execute(sql, args)
        s.con.execute("UPDATE source_folders SET excluded = ?", ("x" * 20000,))


class SchemaChecks(Base):
    def check(self, con):
        for value, why in ((b"\x00", "a blob"), ("x" * 20001, "over the size")):
            with self.assertRaises(sqlite3.IntegrityError, msg=why):
                con.execute("UPDATE source_folders SET excluded = ?", (value,))
        con.execute("UPDATE source_folders SET excluded = ?", ("x" * 20000,))

    def test_a_fresh_file_and_a_migrated_one_refuse_the_same_values(self):
        s = self.store()
        with s.step("dashboard", "tester", place="menu") as step:
            step.create("projects", {"code": "ABC", "name": "Example Programme"})
            step.create("source_folders", {"project": "ABC", "path": str(self.root), "sort_order": 0})
        self.check(s.con)
        old = sqlite3.connect(":memory:")
        old.row_factory = sqlite3.Row
        old.execute("CREATE TABLE source_folders (project TEXT, path TEXT, sort_order INTEGER)")
        old.execute("INSERT INTO source_folders VALUES ('ABC', '/x', 0)")
        st.migrate_source_exclusions(old)
        self.check(old)


class Store(Base):
    def setUp(self):
        super().setUp()
        s = self.store()
        with s.step("dashboard", "tester", place="menu") as step:
            step.create("projects", {"code": "ABC", "name": "Example Programme"})
            step.create("source_folders", {"project": "ABC", "path": str(self.root), "sort_order": 0})
        self.s = s
        self.key = f"ABC|{self.root}"

    def set(self, value):
        with self.s.step("dashboard", "tester", place="menu") as step:
            step.update("source_folders", self.key, {"excluded": value})

    def test_a_good_list_is_saved_read_back_and_one_undo_takes_it_back(self):
        self.set('["Contract", "HR/Candidates"]')
        self.assertEqual(self.s.read("source_folders", "ABC")[0]["excluded"], '["Contract", "HR/Candidates"]')
        with self.s.step("dashboard", "tester", place="menu") as step:
            step.update("source_folders", self.key, {"excluded": "[]"})
            apply_id = step.peek_apply_id()
        self.s.undo(apply_id, "tester", place="menu")
        self.assertEqual(self.s.read("source_folders", "ABC")[0]["excluded"], '["Contract", "HR/Candidates"]')

    def test_the_store_refuses_a_list_that_is_not_a_short_list_of_plain_relative_paths(self):
        for bad in ("", "nope", "{}", '["../x"]', '["/x"]', '["a/"]', '[5]', json.dumps([f"d{i}" for i in range(51)]), 5, None, ["a"], True):
            with self.assertRaises(Invalid, msg=repr(bad)[:40]), self.s.step("dashboard", "tester", place="menu") as step:
                step.update("source_folders", self.key, {"excluded": bad})
        self.assertEqual(self.s.read("source_folders", "ABC")[0]["excluded"], "[]")

    def test_a_new_folder_may_carry_a_list_and_a_bad_one_is_refused(self):
        other = self.d / "other"
        other.mkdir()
        with self.s.step("dashboard", "tester", place="menu") as step:
            step.create("source_folders", {"project": "ABC", "path": str(other), "sort_order": 1, "excluded": '["Contract"]'})
        with self.assertRaises(Invalid), self.s.step("dashboard", "tester", place="menu") as step:
            step.create("source_folders", {"project": "ABC", "path": str(self.home), "sort_order": 2, "excluded": "bad"})


class Walk(Base):
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


class Reader(Base):
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




class LeftOutPath(Base):
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
