"""#48 (guarded store change): a database made before the Word route is brought up when it is opened, keeps all its data, and
then accepts a Word step. Fictional data only. Run: python3 dev/run_tests.py test_migration_word"""
import re
import sqlite3
import unittest
from pathlib import Path
from unittest import mock

import _paths  # noqa: F401
from _demo import DemoStore, USER
from clark import store as store_module
from clark.store import Invalid, open_store


def tables(path):
    """Every table's rows except meta, to compare before and after."""
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        names = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT IN ('meta') "
                                           "AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        return {n: con.execute(f"SELECT * FROM \"{n}\" ORDER BY 1").fetchall() for n in names}
    finally:
        con.close()


def item_events_sql(path):
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        return con.execute("SELECT sql FROM sqlite_master WHERE name = 'item_events'").fetchone()[0]
    finally:
        con.close()


def one(path, sql):
    con = sqlite3.connect(path)
    try:
        return con.execute(sql).fetchone()[0]
    finally:
        con.close()


class OldDatabase(unittest.TestCase):
    """A file as the clark before the Word route left it: version 2, and an item_events table whose route CHECK has no 'word'.
    Word takes the next free number, 3 at the time of writing; if #120 or #115 land first these tests are renumbered with the step."""

    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        ref = self.demo.action(description="Book the room")
        step = self.demo.update("actions", ref, {"status": "Closed"})
        self.demo.store.undo(step, USER)
        self.ref = ref
        self.demo.store.close()
        self.path = Path(self.demo.dir) / "clark.db"
        con = sqlite3.connect(self.path, isolation_level=None)
        con.execute("PRAGMA foreign_keys = OFF")
        old = item_events_sql(self.path).replace(",'word')", ")")
        self.assertNotEqual(old, item_events_sql(self.path))
        con.execute("BEGIN")
        con.execute("ALTER TABLE item_events RENAME TO item_events_new")
        con.execute(re.sub(r"CREATE TABLE \"?item_events_new\"?", "CREATE TABLE item_events", old, count=1))
        con.execute("INSERT INTO item_events SELECT * FROM item_events_new")
        con.execute("DROP TABLE item_events_new")
        con.execute("CREATE INDEX item_events_item ON item_events(item_id)")
        con.execute("CREATE INDEX item_events_change ON item_events(change)")
        con.execute("UPDATE meta SET v = '2' WHERE k = 'schema_version'")
        con.execute("COMMIT")
        con.close()
        self.before = tables(self.path)
        self.assertTrue(self.before["item_events"])
        con = sqlite3.connect(self.path)
        try:
            with self.assertRaises(sqlite3.IntegrityError):
                con.execute("INSERT INTO item_events (at, item_id, kind, route, actor) VALUES ('x', 'ABC-A-001', 'change', 'word', 'you')")
        finally:
            con.close()

    def version(self):
        return one(self.path, "SELECT v FROM meta WHERE k = 'schema_version'")

    def test_the_old_file_moves_up_keeps_every_row_and_then_accepts_a_word_step_with_one_undo(self):
        self.assertEqual(self.version(), "2")
        store = open_store(self.path, onedrive_roots=[])
        self.addCleanup(store.close)
        self.assertEqual(self.version(), str(store_module.SCHEMA_VERSION))
        self.assertEqual(tables(self.path), self.before)
        with store.step("word", USER, src_ref="Added from Word (plan.docx)") as st:
            new = st.create("actions", {"project": "ABC", "description": "Confirm the venue", "raised": "2026-10-02",
                                        "source": "Word import", "client_visible": 0})
        row = store.con.execute("SELECT route, src_ref FROM item_events WHERE item_id = ?", (new,)).fetchone()
        self.assertEqual((row["route"], row["src_ref"]), ("word", "Added from Word (plan.docx)"))
        step = store.con.execute("SELECT max(apply_id) FROM applies").fetchone()[0]
        store.undo(step, USER)
        self.assertEqual(store.con.execute("SELECT count(*) FROM actions WHERE id = ?", (new,)).fetchone()[0], 0)
        self.assertEqual(store.con.execute("PRAGMA integrity_check").fetchone()[0], "ok")
        self.assertEqual(store.con.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_the_moved_file_has_the_same_table_indexes_and_numbering_as_a_new_one(self):
        open_store(self.path, onedrive_roots=[]).close()
        fresh = DemoStore()
        self.addCleanup(fresh.close)
        shape = lambda p: re.sub(r"\s+|\"", "", re.sub(r"--[^\n]*", "", item_events_sql(p)))      # comments, spacing and quoting aside
        self.assertEqual(shape(self.path), shape(Path(fresh.dir) / "clark.db"))
        self.assertIn("'word'", item_events_sql(self.path))
        self.assertEqual(one(self.path, "SELECT count(*) FROM sqlite_master WHERE type = 'index' AND name IN "
                                        "('item_events_item', 'item_events_change')"), 2)
        self.assertEqual(one(self.path, "SELECT seq FROM sqlite_sequence WHERE name = 'item_events'"),
                         one(self.path, "SELECT max(event_id) FROM item_events"))

    def test_a_copy_is_taken_first_and_a_second_open_does_nothing(self):
        open_store(self.path, onedrive_roots=[]).close()
        copies = sorted((self.path.parent / "backups").glob("*migrate*"))
        self.assertEqual(len(copies), 1)
        self.assertEqual(one(copies[0], "SELECT v FROM meta WHERE k = 'schema_version'"), "2")
        open_store(self.path, onedrive_roots=[]).close()
        self.assertEqual(len(sorted((self.path.parent / "backups").glob("*migrate*"))), 1)

    def test_if_the_copy_cannot_be_made_nothing_is_changed(self):
        with mock.patch("clark.backup.make", side_effect=Invalid("The database could not be updated because a backup of your data must be made first. Nothing was changed.")):
            with self.assertRaisesRegex(Invalid, "Nothing was changed"):
                open_store(self.path, onedrive_roots=[])
        self.assertEqual(self.version(), "2")
        self.assertEqual(tables(self.path), self.before)

    def test_a_step_that_fails_rolls_everything_back(self):
        def broken(con):
            store_module.migrate_to_3(con)
            raise RuntimeError("stopped")
        with mock.patch.object(store_module, "MIGRATIONS", ((2, store_module.migrate_to_2), (3, broken), *store_module.MIGRATIONS[2:])):       # the later steps stay in the table: the runner refuses a table that ends short
            with self.assertRaisesRegex(Invalid, "Nothing was changed") as seen:
                open_store(self.path, onedrive_roots=[])
        self.assertNotIn("RuntimeError", str(seen.exception))
        self.assertEqual(self.version(), "2")
        self.assertEqual(tables(self.path), self.before)
        self.assertEqual(one(self.path, "SELECT count(*) FROM sqlite_master WHERE name = 'item_events_3'"), 0)
        open_store(self.path, onedrive_roots=[]).close()           # and a normal open afterwards moves it up
        self.assertEqual(self.version(), str(store_module.SCHEMA_VERSION))

    def test_a_version_1_file_goes_through_the_board_step_and_the_word_step_in_one_open(self):
        con = sqlite3.connect(self.path)
        con.execute("UPDATE meta SET v = '1' WHERE k = 'schema_version'")
        con.commit()
        con.close()
        open_store(self.path, onedrive_roots=[]).close()
        self.assertEqual(self.version(), str(store_module.SCHEMA_VERSION))
        self.assertIn("'word'", item_events_sql(self.path))
        self.assertIn("'board'", item_events_sql(self.path))
        self.assertEqual(tables(self.path), self.before)

    def test_the_word_step_is_the_one_numbered_3(self):
        self.assertIn((3, store_module.migrate_to_3), store_module.MIGRATIONS)
        self.assertEqual([n for n, _ in store_module.MIGRATIONS][:2], [2, 3])      # Word's number is fixed: a later step takes the next number after it

    def test_a_file_from_a_newer_clark_is_still_refused_and_left_alone(self):
        con = sqlite3.connect(self.path)
        con.execute("UPDATE meta SET v = '99' WHERE k = 'schema_version'")
        con.commit()
        con.close()
        with self.assertRaisesRegex(Invalid, "newer clark"):
            open_store(self.path, onedrive_roots=[])
        self.assertEqual(self.version(), "99")

    def test_the_word_step_run_twice_changes_nothing_the_second_time(self):
        open_store(self.path, onedrive_roots=[]).close()
        after = tables(self.path)
        con = store_module.connect(self.path)
        try:
            con.execute("PRAGMA foreign_keys = OFF")
            con.execute("BEGIN IMMEDIATE")
            store_module.migrate_to_3(con)
            con.execute("COMMIT")
        finally:
            con.close()
        self.assertEqual(tables(self.path), after)
        self.assertEqual(one(self.path, "SELECT seq FROM sqlite_sequence WHERE name = 'item_events'"),
                         one(self.path, "SELECT max(event_id) FROM item_events"))

    def test_the_rebuilt_table_keeps_its_self_reference_and_the_counter_after_the_newest_row_was_removed(self):
        con = sqlite3.connect(self.path)
        top = con.execute("SELECT max(event_id) FROM item_events").fetchone()[0]
        con.execute("PRAGMA foreign_keys = OFF")
        con.execute("DELETE FROM item_events WHERE event_id = ?", (top,))
        con.execute("UPDATE sqlite_sequence SET seq = ? WHERE name = 'item_events'", (top,))
        con.commit()
        con.close()
        open_store(self.path, onedrive_roots=[]).close()
        self.assertEqual(one(self.path, "SELECT seq FROM sqlite_sequence WHERE name = 'item_events'"), top)
        self.assertEqual(one(self.path, "SELECT count(*) FROM item_events WHERE undoes IS NOT NULL"),
                         sum(1 for r in self.before["item_events"] if r[-1] is not None and r[0] != top))
        fresh = DemoStore()
        self.addCleanup(fresh.close)
        refs = lambda p: sorted(tuple(r) for r in sqlite3.connect(p).execute(
            "SELECT \"table\", \"from\", \"to\" FROM pragma_foreign_key_list('item_events')"))
        self.assertEqual(refs(self.path), refs(Path(fresh.dir) / "clark.db"))
        self.assertIn(("item_events", "undoes", "event_id"), refs(self.path))


if __name__ == "__main__":
    unittest.main()
