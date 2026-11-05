"""#731: a data folder with nothing in it opens with the made-up demo projects; they come off again, whole and safely.

Run: python3 dev/run_tests.py test_demo_seed
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _paths import SRC  # noqa: F401  (puts src on the path)
from clark import backup, demo_seed, store as clark_store  # noqa: E402

USER = "Test Person"
NO_ONEDRIVE = []


def fresh_folder(test):
    folder = tempfile.TemporaryDirectory()
    test.addCleanup(folder.cleanup)
    return Path(folder.name)


def opened(folder):
    return demo_seed.load_if_fresh(clark_store.open_store(folder / "clark.db", onedrive_roots=NO_ONEDRIVE), NO_ONEDRIVE)


def codes(store):
    return sorted(r["code"] for r in store.read("projects"))


def real_project(store, code="REAL"):
    with store.step("dashboard", USER) as st:
        st.create("projects", {"code": code, "name": "Our own project"})


def add_action(store, project, text="Added by the person"):
    with store.step("dashboard", USER) as st:
        return st.create("actions", {"project": project, "description": text, "raised": "2026-10-01", "source": "test"})


class Load(unittest.TestCase):
    def test_a_fresh_store_loads_the_demo_projects_marked_in_meta(self):
        folder = fresh_folder(self)
        before = clark_store.open_store(folder / "clark.db", onedrive_roots=NO_ONEDRIVE)
        device = before.device
        before.close()
        s = opened(folder)
        self.addCleanup(s.close)
        self.assertEqual(codes(s), ["MOSS", "TUL"])
        meta = dict(s.con.execute("SELECT k, v FROM meta").fetchall())
        self.assertEqual(json.loads(meta["demo_projects"]), ["MOSS", "TUL"])
        self.assertTrue(json.loads(meta["demo_applies"]))
        self.assertEqual(meta["schema_version"], str(clark_store.SCHEMA_VERSION))
        self.assertEqual(s.device, device)                                              # this installation's own identity, not the demo build's
        self.assertEqual(set(r[0] for r in s.con.execute("SELECT DISTINCT device FROM applies")), {device})
        self.assertEqual(list((folder).glob(".demo-*")), [])                            # the scratch folder is gone
        self.assertFalse((folder / "backups").exists())                                 # no copy of an empty file was left to stand for today's
        self.assertTrue(demo_seed.Demo(s.path, NO_ONEDRIVE).status()[1]["demo"])

    def test_a_store_with_any_data_never_gets_the_demo(self):
        folder = fresh_folder(self)
        s = clark_store.open_store(folder / "clark.db", onedrive_roots=NO_ONEDRIVE)
        real_project(s)
        s = demo_seed.load_if_fresh(s, NO_ONEDRIVE)
        self.addCleanup(s.close)
        self.assertEqual(codes(s), ["REAL"])
        self.assertFalse(demo_seed.Demo(s.path, NO_ONEDRIVE).status()[1]["demo"])

    def test_a_store_that_once_had_steps_but_no_project_is_not_fresh(self):
        folder = fresh_folder(self)
        s = clark_store.open_store(folder / "clark.db", onedrive_roots=NO_ONEDRIVE)
        with s.step("dashboard", USER) as st:
            st.create("people", {"name": "Sam Example", "source": "test"})
        s = demo_seed.load_if_fresh(s, NO_ONEDRIVE)
        self.addCleanup(s.close)
        self.assertEqual(codes(s), [])

    def test_a_missing_demo_file_leaves_the_store_empty_and_does_not_fail(self):
        folder = fresh_folder(self)
        with mock.patch.dict(sys.modules, {"demo_data": None}):
            s = opened(folder)
        self.addCleanup(s.close)
        self.assertEqual(codes(s), [])

    def test_a_failed_build_leaves_the_store_empty_and_does_not_fail(self):
        folder = fresh_folder(self)
        sys.path.insert(0, str(demo_seed.DEV))
        import demo_data
        with mock.patch.object(demo_data, "build", side_effect=RuntimeError("no")):
            s = opened(folder)
        self.addCleanup(s.close)
        self.assertEqual(codes(s), [])
        self.assertEqual(list(folder.glob(".demo-*")), [])

    def test_the_demo_is_never_put_back_once_removed(self):
        folder = fresh_folder(self)
        s = opened(folder)
        demo_seed.remove(s)
        s.close()
        s = opened(folder)                                                              # the next start of the same folder
        self.addCleanup(s.close)
        self.assertEqual(codes(s), [])
        s.close()
        again = opened(folder)
        self.addCleanup(again.close)
        self.assertEqual(codes(again), [])


class Remove(unittest.TestCase):
    def setUp(self):
        self.folder = fresh_folder(self)
        self.s = opened(self.folder)
        self.addCleanup(self.s.close)

    def count(self, table, project):
        return self.s.con.execute(f"SELECT count(*) FROM {table} WHERE project = ?", (project,)).fetchone()[0]

    def test_remove_takes_only_the_demo_projects_and_leaves_a_real_one_beside_them(self):
        real_project(self.s)
        keep = add_action(self.s, "REAL")
        self.assertEqual(demo_seed.remove(self.s), 2)
        self.assertEqual(codes(self.s), ["REAL"])
        self.assertEqual(self.s.read("actions", ref=keep)["description"], "Added by the person")
        for table in ("milestones", "workstreams", "actions", "raid", "decisions", "use_cases", "updates", "report_sections"):
            for code in ("TUL", "MOSS"):
                self.assertEqual(self.count(table, code), 0, (table, code))
        left = self.s.con.execute("SELECT count(*) FROM links").fetchone()[0], self.s.con.execute("SELECT count(*) FROM item_labels").fetchone()[0]
        self.assertEqual(left, (0, 0))
        for table in ("change_log", "item_events"):
            ids = {r[0] for r in self.s.con.execute(f"SELECT item_id FROM {table}")}
            self.assertFalse([i for i in ids if i.startswith(("TUL", "MOSS"))], table)
        self.assertEqual(self.s.con.execute("SELECT v FROM meta WHERE k = 'demo_removed'").fetchone()[0], "1")
        self.assertFalse(demo_seed.Demo(self.s.path, NO_ONEDRIVE).status()[1]["demo"])

    def test_a_row_added_inside_a_demo_project_keeps_that_project_whole(self):
        keep = add_action(self.s, "TUL")
        self.assertEqual(demo_seed.removable(self.s).keys(), {"MOSS"})
        self.assertEqual(demo_seed.remove(self.s), 1)
        self.assertEqual(codes(self.s), ["TUL"])
        self.assertEqual(self.s.read("actions", ref=keep)["description"], "Added by the person")
        self.assertGreater(self.count("milestones", "TUL"), 0)                           # its demo rows stay with it: if unsure, keep

    def test_an_edit_to_a_demo_project_makes_it_the_persons(self):
        with self.s.step("dashboard", USER) as st:
            st.update("projects", "MOSS", {"name": "Renamed by the person"})
        self.assertEqual(demo_seed.removable(self.s).keys(), {"TUL"})
        demo_seed.remove(self.s)
        self.assertEqual(codes(self.s), ["MOSS"])

    def test_nothing_touched_by_the_person_means_the_banner_goes_when_all_is_edited(self):
        for code in ("TUL", "MOSS"):
            add_action(self.s, code)
        self.assertFalse(demo_seed.Demo(self.s.path, NO_ONEDRIVE).status()[1]["demo"])
        self.assertEqual(demo_seed.remove(self.s), 0)
        self.assertEqual(codes(self.s), ["MOSS", "TUL"])

    def test_the_safety_copy_exists_and_is_taken_before_anything_is_deleted(self):
        seen = []
        real_take = backup.take

        def take(store, tag):
            seen.append(store.con.execute("SELECT count(*) FROM projects").fetchone()[0])      # what the store held when the copy was asked for
            return real_take(store, tag)
        with mock.patch.object(backup, "take", take):
            demo_seed.remove(self.s)
        self.assertEqual(seen, [2])
        copies = list((self.folder / "backups").glob("clark-*.db"))
        self.assertTrue(copies)
        import sqlite3
        con = sqlite3.connect(str(copies[0]))
        try:
            self.assertEqual(con.execute("SELECT count(*) FROM projects").fetchone()[0], 2)    # the copy still has the demo
        finally:
            con.close()
        self.assertEqual(codes(self.s), [])

    def test_when_the_safety_copy_cannot_be_made_nothing_is_removed(self):
        with mock.patch.object(backup, "take", side_effect=clark_store.Invalid("A backup of your data must be made first, and it couldn't be.")):
            with self.assertRaises(clark_store.Invalid):
                demo_seed.remove(self.s)
        self.assertEqual(codes(self.s), ["MOSS", "TUL"])
        self.assertIsNone(self.s.con.execute("SELECT v FROM meta WHERE k = 'demo_removed'").fetchone())
        status, body = demo_seed.Demo(self.s.path, NO_ONEDRIVE).status()
        self.assertTrue(body["demo"])

    def test_the_route_removes_and_says_so(self):
        status, body = demo_seed.Demo(self.s.path, NO_ONEDRIVE).remove({})
        self.assertEqual((status, body["ok"], body["removed"]), (200, True, 2))
        self.assertEqual(codes(clark_store.open_store(self.s.path, onedrive_roots=NO_ONEDRIVE)), [])


if __name__ == "__main__":
    unittest.main()
