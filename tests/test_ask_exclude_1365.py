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

from clark import ask_exclude as ex, platform as pl, store as st
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


