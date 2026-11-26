"""Row 1365 (row 1365 ticket rule 13:39, approved 13:41; schema ruling WO-M17452 14:03): a saved folder with a people or contract word in a name is left out
of asking until the person presses Accept for that folder. Default Declined. Accept is remembered per folder (source_folders.accepted, step 34); Decline
keeps it left out. Pins: the default, the per-folder memory, Decline, the fresh and the upgraded database both reading every folder as declined, the
question's reader and the index's folder list both following the same rule. Made-up names only.

Run: python3 dev/run_tests.py test_ask_accept_1365
"""
import os
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _paths import SRC  # noqa: F401

import test_ask_route as tr
from clark import ask_folders, platform as pl, reach, sensitive_names, store as st


class Base(unittest.TestCase):
    def setUp(self):
        patch = mock.patch.object(pl, "system", return_value=pl.MAC)
        patch.start()
        self.addCleanup(patch.stop)
        self.d = Path(os.path.realpath(tempfile.mkdtemp(prefix="clark-test-")))
        self.addCleanup(shutil.rmtree, self.d, True)
        self.data, self.home = self.d / "data", self.d / "home"
        self.flagged, self.plain = self.home / "lib", self.home / "notes"
        for p in (self.data, self.flagged / "Contract", self.plain):
            p.mkdir(parents=True)
        (self.flagged / "Contract" / "terms.txt").write_text("terms", encoding="utf-8")
        (self.plain / "a.txt").write_text("alpha", encoding="utf-8")
        self.db = self.data / "clark.db"
        s = self.store()
        with s.step("dashboard", "tester", place="menu") as step:
            step.create("projects", {"code": "ABC", "name": "Example Programme"})
        self.svc = ask_folders.AskFolders(self.db, [], data_dir=self.data, home=self.home, by_user=lambda: "tester")

    def store(self):
        s = st.open_store(self.db, onedrive_roots=[])
        self.addCleanup(s.close)
        return s

    def do(self, action, path=None, **more):
        body = {"project": "ABC", "action": action, **({"path": str(path)} if path is not None else {}), **more}
        return self.svc.change(body)

    def accepted(self):
        return {r["path"]: r["accepted"] for r in self.store().read("source_folders", "ABC")}

    def readable(self):
        return ask_folders.readable_paths(self.store().read("source_folders", "ABC"))


class Rule(Base):
    def test_default_declined_until_accept(self):
        status, body = self.do("add", self.flagged)
        self.assertEqual((status, body["ok"]), (200, True), body)
        self.assertEqual(self.accepted(), {str(self.flagged): 0})
        self.assertEqual(body["warnings"][0]["accepted"], False)
        self.assertEqual(self.readable(), [], "listed, but not read")
        self.assertEqual(self.do("add", self.plain)[0], 200)
        self.assertEqual(self.readable(), [str(self.plain)], "a folder with no such name is read without any choice")
        self.assertEqual(self.svc.all_folders("ABC"), [str(self.plain)], "the index is given the same list")
        self.assertEqual(self.svc.read("ABC")[1]["folders"], [str(self.flagged), str(self.plain)], "the folder stays listed")
        status, body = self.do("accept", self.flagged)
        self.assertEqual((status, body["ok"], body["warnings"][0]["accepted"]), (200, True, True), body)
        self.assertEqual(self.readable(), [str(self.flagged), str(self.plain)])
        self.assertEqual(self.svc.all_folders("ABC"), [str(self.flagged), str(self.plain)])

    def test_accept_remembered_per_folder(self):
        other = self.home / "other"
        (other / "Payroll").mkdir(parents=True)
        self.do("add", self.flagged)
        self.do("add", other)
        self.assertEqual(self.do("accept", self.flagged)[0], 200)
        self.assertEqual(self.accepted(), {str(self.flagged): 1, str(other): 0}, "only the one that was accepted")
        again = ask_folders.AskFolders(self.db, [], data_dir=self.data, home=self.home, by_user=lambda: "tester")      # a new service, a new window: the choice is in the file
        warns = {w["folder"]: w["accepted"] for w in again.read("ABC")[1]["warnings"]}
        self.assertEqual(warns, {str(self.flagged): True, str(other): False})
        self.assertEqual(again.all_folders("ABC"), [str(self.flagged)])

    def test_decline_keeps_folder_left_out(self):
        self.do("add", self.flagged)
        status, body = self.do("decline", self.flagged)
        self.assertEqual((status, body["ok"], body["warnings"][0]["accepted"]), (200, True, False))
        self.assertEqual(self.readable(), [])
        self.do("accept", self.flagged)
        self.assertEqual(self.readable(), [str(self.flagged)])
        status, body = self.do("decline", self.flagged)
        self.assertEqual((status, body["ok"]), (200, True))
        self.assertEqual(self.accepted(), {str(self.flagged): 0})
        self.assertEqual(self.readable(), [], "Decline takes an Accept back")

    def test_accept_takes_one_undo_and_a_folder_not_in_the_list_is_refused(self):
        self.do("add", self.flagged)
        step = self.do("accept", self.flagged)[1]["apply_id"]
        self.assertEqual(self.svc.change({"project": "ABC", "action": "undo", "apply_id": step})[0], 200)
        self.assertEqual(self.accepted(), {str(self.flagged): 0})
        self.assertEqual(self.do("accept", self.plain)[0], 409)
        self.assertEqual(self.do("decline", self.plain)[0], 409)
        self.assertEqual(self.do("accept")[0], 400, "a path is needed")

    def test_leaving_the_flagged_subfolder_out_makes_the_rest_readable_without_accept(self):
        self.do("add", self.flagged)
        self.assertEqual(self.readable(), [])
        self.assertEqual(self.do("exclude", self.flagged)[0], 200)
        self.assertEqual(self.readable(), [str(self.flagged)])
        self.assertEqual(self.accepted(), {str(self.flagged): 0})

    def test_the_store_takes_only_0_or_1(self):
        self.do("add", self.flagged)
        s = self.store()
        for bad in (2, -1, "1", 1.0, None):      # True and False are the flag rule's own: they are stored as 1 and 0 (the flag rule, row 1365 FLAG_COLUMNS)
            with self.assertRaises(st.Invalid, msg=repr(bad)):
                with s.step("dashboard", "tester", place="menu") as step:
                    step.update("source_folders", f"ABC|{self.flagged}", {"accepted": bad})
        self.assertEqual(self.accepted(), {str(self.flagged): 0})
        with s.step("dashboard", "tester", place="menu") as step:
            step.update("source_folders", f"ABC|{self.flagged}", {"accepted": True})
        self.assertEqual(self.accepted(), {str(self.flagged): 1}, "True is stored as 1, the flag rule's way")

    def test_the_saved_folders_own_name_is_flagged_and_named(self):
        own = self.home / "Payroll"
        own.mkdir()
        (own / "a.txt").write_text("alpha", encoding="utf-8")
        status, body = self.do("add", own)
        self.assertEqual((status, body["ok"]), (200, True), body)
        self.assertEqual(self.readable(), [], "plain file names, but the folder's own name is flagged: Declined")
        self.assertEqual([i["name"] for i in body["warnings"][0]["items"]], ["Payroll"], "the warning names it")
        self.assertEqual(self.svc.all_folders("ABC"), [])
        self.assertEqual(self.do("accept", own)[0], 200)
        self.assertEqual(self.readable(), [str(own)])

    def test_a_truncated_name_scan_fails_closed(self):
        for n in range(5):
            (self.plain / f"f{n}.txt").write_text("x", encoding="utf-8")
        self.assertEqual(self.do("add", self.plain)[0], 200)
        self.assertEqual(self.readable(), [str(self.plain)], "a small scan finds nothing: read")
        with mock.patch.object(sensitive_names, "MAX_ENTRIES", 3):
            self.assertTrue(sensitive_names.scan(self.plain).truncated)
            self.assertEqual(self.readable(), [], "a scan that stopped counts as flagged: Declined")
            self.assertEqual(self.svc.all_folders("ABC"), [])
            warns = self.svc.read("ABC")[1]["warnings"]
            self.assertEqual([(w["folder"], w["accepted"], w.get("truncated")) for w in warns], [(str(self.plain), False, True)])
            self.assertEqual(self.do("accept", self.plain)[0], 200)
            self.assertEqual(self.readable(), [str(self.plain)], "until Accept")

    def test_a_left_out_list_that_cannot_be_read_is_passed_to_the_reader_which_refuses_it(self):
        self.assertTrue(ask_folders.read_ok(str(self.plain), "not json"), "the reader (test_ask_exclude_1365) sends nothing from it and counts it")
        self.assertTrue(ask_folders.read_ok(str(self.plain), "[]"))


class Schema(Base):
    def test_a_fresh_database_reads_every_folder_as_declined(self):
        self.assertEqual(st.SCHEMA_VERSION, 39)      # 38 before row 1628 (step 39); row 1252 step 38 follows row 1533 step 37, row 1417 step 36, row 1534 step 35 and this row step 34
        self.assertEqual(st.EXCLUDED_STEP, 34)
        self.assertIn((34, st.migrate_source_folders_1365), st.MIGRATIONS)
        self.assertEqual([n for n, _ in st.MIGRATIONS][-6:-4], [33, 34], "one step for the whole row")
        s = self.store()
        with s.step("dashboard", "tester", place="menu") as step:
            step.create("source_folders", {"project": "ABC", "path": str(self.flagged), "sort_order": 0})
            step.create("source_folders", {"project": "ABC", "path": str(self.plain), "sort_order": 1})
        self.assertEqual(self.accepted(), {str(self.flagged): 0, str(self.plain): 0})
        self.assertEqual(s.con.execute("SELECT v FROM meta WHERE k = 'schema_version'").fetchone()[0], str(st.SCHEMA_VERSION))

    def test_an_upgraded_database_reads_every_saved_folder_as_declined(self):
        s = self.store()
        with s.step("dashboard", "tester", place="menu") as step:
            step.create("source_folders", {"project": "ABC", "path": str(self.flagged), "sort_order": 0, "excluded": '["Old"]'})
            step.create("source_folders", {"project": "ABC", "path": str(self.plain), "sort_order": 3})
        s.close()
        con = sqlite3.connect(str(self.db))
        con.execute("ALTER TABLE source_folders DROP COLUMN accepted")      # the file as step 33 leaves it: neither of this row's columns
        con.execute("ALTER TABLE source_folders DROP COLUMN excluded")
        con.execute("UPDATE meta SET v = '33' WHERE k = 'schema_version'")
        con.commit()
        self.assertNotIn("accepted", [r[1] for r in con.execute("PRAGMA table_info(source_folders)")])
        con.close()
        up = st.open_store(self.db, onedrive_roots=[])
        self.addCleanup(up.close)
        self.assertEqual(up.con.execute("SELECT v FROM meta WHERE k = 'schema_version'").fetchone()[0], str(st.SCHEMA_VERSION))
        rows = {r["path"]: (r["accepted"], r["excluded"], r["sort_order"]) for r in up.read("source_folders", "ABC")}
        self.assertEqual(rows, {str(self.flagged): (0, "[]", 0), str(self.plain): (0, "[]", 3)}, "declined, and nothing else changed")

    def test_the_migration_adds_the_column_once_keeps_rows_and_skips_a_missing_table(self):
        con = sqlite3.connect(":memory:")
        con.row_factory = sqlite3.Row
        con.execute("CREATE TABLE source_folders (project TEXT NOT NULL, path TEXT NOT NULL, sort_order INTEGER NOT NULL, excluded TEXT NOT NULL DEFAULT '[]', PRIMARY KEY (project, path))")
        con.execute("INSERT INTO source_folders VALUES ('ABC', '/x/y', 3, '[]')")
        st.migrate_source_folders_1365(con)
        st.migrate_source_folders_1365(con)
        self.assertEqual([tuple(r) for r in con.execute("SELECT project, path, sort_order, excluded, accepted FROM source_folders")], [("ABC", "/x/y", 3, "[]", 0)])
        self.assertEqual([r["name"] for r in con.execute("PRAGMA table_info(source_folders)")].count("accepted"), 1)
        empty = sqlite3.connect(":memory:")
        st.migrate_source_folders_1365(empty)
        self.assertEqual(list(empty.execute("SELECT name FROM sqlite_master")), [])


class OnTheRoute(tr.Base):
    """The question: nothing from a folder that is not accepted reaches the provider; after Accept it does."""

    def setUp(self):
        patch = mock.patch.object(reach.platform, "system", return_value=reach.platform.MAC)
        patch.start()
        self.addCleanup(patch.stop)
        super().setUp()
        self.mine = Path(os.path.realpath(tempfile.mkdtemp(prefix="clark-mine-")))
        self.addCleanup(shutil.rmtree, self.mine, True)
        (self.mine / "plan.txt").write_text("FOLDERKEEP the cutover plan is booked", encoding="utf-8")
        (self.mine / "Contract").mkdir()
        self.store = st.open_store(self.db, onedrive_roots=[])
        self.addCleanup(self.store.close)
        with self.store.step("dashboard", "tester", place="menu") as s:
            s.create("source_folders", {"project": tr.CODE, "path": str(self.mine), "sort_order": 1})

    def set(self, value):
        with self.store.step("dashboard", "tester", place="menu") as s:
            s.update("source_folders", f"{tr.CODE}|{self.mine}", {"accepted": value})

    def test_default_declined_until_accept_the_provider_gets_nothing_from_the_folder(self):
        status, got = self.question("What is the cutover plan?")
        self.assertEqual(status, 200, got)
        self.assertNotIn("FOLDERKEEP", self.provider.sent[-1])
        self.set(1)
        self.question("What is the cutover plan?")
        self.assertIn("FOLDERKEEP", self.provider.sent[-1])
        self.set(0)
        self.question("What is the cutover plan?")
        self.assertNotIn("FOLDERKEEP", self.provider.sent[-1], "Decline leaves it out again")


if __name__ == "__main__":
    unittest.main()
