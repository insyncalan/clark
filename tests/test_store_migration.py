"""#126: schema version 2 (documents can be archived) and its migration from version 1."""
import shutil
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from _demo import USER, DemoStore
from _paths import ROOT
from clark import store as store_module
from clark.store import Invalid, connect, migrate, open_store

V1 = ROOT / "tests" / "fixtures" / "schema-v1.sql"
NEW_TABLES = ("report_sections", "glance_tiles", "report_hidden")


def make_v1(folder, without=()):
    """A version-1 clark.db: today's schema before this change, a project and a document, optionally missing some tables."""
    path = Path(folder) / "clark.db"
    con = sqlite3.connect(str(path), isolation_level=None)
    con.executescript(V1.read_text(encoding="utf-8"))
    for k, v in (("schema_version", "1"), ("created_at", "2026-10-01"), ("device", "d1"), ("db_id", "i1"), ("role", "owner")):
        con.execute("INSERT INTO meta (k, v) VALUES (?, ?)", (k, v))
    con.execute("INSERT INTO projects (code, name) VALUES ('ABC', 'Example Programme')")
    con.execute("INSERT INTO documents (project, id, title, kind, url, sort_order) "
                "VALUES ('ABC', 'd1', 'Plan', 'doc', 'https://example.org/plan', 1)")
    for t in without:
        con.execute(f"DROP TABLE {t}")
    con.close()
    return path


def version(path):
    con = sqlite3.connect(str(path))
    try:
        return con.execute("SELECT v FROM meta WHERE k = 'schema_version'").fetchone()[0]
    finally:
        con.close()


def tables(path):
    con = sqlite3.connect(str(path))
    try:
        return {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    finally:
        con.close()


class NewDatabase(unittest.TestCase):
    def test_a_new_database_is_the_current_version_with_the_column_and_is_not_migrated(self):
        with mock.patch.object(store_module, "migrate") as migrate, DemoStore() as s:
            self.assertEqual(store_module.SCHEMA_VERSION, 3)            # 3 is Word's (#48): item_events takes the route word. Word takes the next free number, 3 at the time of writing; renumber it if #120 or #115 land first
            self.assertEqual(s.con.execute("SELECT v FROM meta WHERE k = 'schema_version'").fetchone()[0], "3")
            self.assertIn("archived", store_module.columns(s.con, "documents"))
            migrate.assert_not_called()


class Migrating(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="clark-test-"))
        self.addCleanup(shutil.rmtree, self.dir, True)

    def test_a_version_1_file_gains_the_column_keeps_its_rows_and_is_version_2(self):
        path = make_v1(self.dir)
        s = open_store(path, onedrive_roots=[])
        try:
            self.assertEqual(s.con.execute("SELECT v FROM meta WHERE k = 'schema_version'").fetchone()[0], str(store_module.SCHEMA_VERSION))
            doc = s.con.execute("SELECT * FROM documents").fetchone()
            self.assertEqual((doc["title"], doc["archived"]), ("Plan", 0))
            self.assertEqual(s.read("projects", ref="ABC")["name"], "Example Programme")
            self.assertEqual(s.con.execute("SELECT count(*) FROM applies").fetchone()[0], 0)    # a migration is not a step
        finally:
            s.close()

    def test_a_second_open_changes_nothing(self):
        path = make_v1(self.dir)
        open_store(path, onedrive_roots=[]).close()
        con = sqlite3.connect(str(path))
        before = list(con.iterdump())
        con.close()
        open_store(path, onedrive_roots=[]).close()
        con = sqlite3.connect(str(path))
        self.assertEqual(list(con.iterdump()), before)
        con.close()

    def test_a_version_1_file_without_the_report_tables_gains_them(self):
        path = make_v1(self.dir, without=NEW_TABLES)
        self.assertFalse(set(NEW_TABLES) & tables(path))
        open_store(path, onedrive_roots=[]).close()
        self.assertTrue(set(NEW_TABLES) <= tables(path))
        self.assertEqual(version(path), str(store_module.SCHEMA_VERSION))

    def test_two_connections_on_one_version_1_file_migrate_once(self):
        path = make_v1(self.dir)
        first, second = connect(path), connect(path)
        try:
            migrate(first)
            first_dump = list(first.iterdump())
            with mock.patch.object(store_module, "_add_documents_archived") as again:
                migrate(second)          # it believed the file was version 1; after the lock it finds 2
            again.assert_not_called()
            self.assertEqual(list(second.iterdump()), first_dump)
            self.assertEqual(second.execute("SELECT v FROM meta WHERE k = 'schema_version'").fetchone()[0], str(store_module.SCHEMA_VERSION))
            self.assertEqual(second.execute("SELECT archived FROM documents").fetchone()[0], 0)
        finally:
            first.close()
            second.close()

    def test_a_failure_inside_the_migration_leaves_the_file_as_it_was(self):
        path = make_v1(self.dir, without=NEW_TABLES)
        con = sqlite3.connect(str(path))
        before = list(con.iterdump())
        con.close()
        with mock.patch.object(store_module, "_add_documents_archived", side_effect=RuntimeError("forced")):
            with self.assertRaises(Invalid):
                open_store(path, onedrive_roots=[])
        con = sqlite3.connect(str(path))
        self.assertEqual(list(con.iterdump()), before)
        con.close()
        self.assertEqual(version(path), "1")
        open_store(path, onedrive_roots=[]).close()           # and it still opens afterwards
        self.assertEqual(version(path), str(store_module.SCHEMA_VERSION))

    def test_a_half_applied_copy_is_safe(self):
        path = make_v1(self.dir)
        con = sqlite3.connect(str(path), isolation_level=None)
        con.execute("ALTER TABLE documents ADD COLUMN archived INTEGER NOT NULL DEFAULT 0 CHECK (archived IN (0,1))")
        con.close()
        open_store(path, onedrive_roots=[]).close()
        self.assertEqual(version(path), str(store_module.SCHEMA_VERSION))

    def test_a_newer_database_is_still_refused(self):
        path = make_v1(self.dir)
        con = sqlite3.connect(str(path), isolation_level=None)
        con.execute("UPDATE meta SET v = ? WHERE k = 'schema_version'", (str(store_module.SCHEMA_VERSION + 1),))
        con.close()
        with self.assertRaises(Invalid) as e:
            open_store(path, onedrive_roots=[])
        self.assertIn("newer clark", str(e.exception))


class DocumentsAreRegistered(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.s = self.demo.store
        self.s.con.execute("INSERT INTO documents (project, id, title, url, sort_order) "
                           "VALUES ('ABC', 'd1', 'Plan', 'https://example.org/plan', 1)")

    def tearDown(self):
        self.demo.close()

    def test_new_and_update_are_refused_for_documents(self):
        with self.assertRaises(Invalid) as e:
            with self.s.step("dashboard", USER) as st:
                st.create("documents", {"project": "ABC", "title": "T", "url": "https://example.org"})
        self.assertIn("only be archived or restored", str(e.exception))
        with self.assertRaises(Invalid):
            with self.s.step("dashboard", USER) as st:
                st.update("documents", "ABC|d1", {"title": "Other"})
        self.assertEqual(self.s.con.execute("SELECT count(*) FROM documents").fetchone()[0], 1)
        self.assertEqual(self.s.read("documents", "ABC")[0]["title"], "Plan")

    def test_documents_cannot_be_cancelled(self):
        with self.assertRaises(Invalid):
            with self.s.step("dashboard", USER) as st:
                st.cancel("documents", "ABC|d1")

    def test_the_key_is_project_and_id(self):
        self.assertEqual(store_module.key_of("documents", {"project": "ABC", "id": "d1"}), "ABC|d1")
        self.assertEqual(self.s.read("documents", ref="ABC|d1")["title"], "Plan")


class BoardPlace(unittest.TestCase):
    """#126: item_events.place accepts 'board' (the board's own moves), in a new database and after the migration."""

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="clark-test-"))
        self.addCleanup(shutil.rmtree, self.dir, True)

    def board_step(self, s):
        with s.step("dashboard", USER, place="board") as st:
            st.update("projects", "ABC", {"name": "Renamed"})
        return s.con.execute("SELECT place FROM item_events ORDER BY event_id DESC LIMIT 1").fetchone()[0]

    def test_board_is_a_place_in_the_store_and_a_new_database(self):
        self.assertIn("board", store_module.PLACES)
        with DemoStore() as s:
            self.assertEqual(self.board_step(s), "board")

    def test_a_place_that_is_not_listed_is_still_refused(self):
        with DemoStore() as s:
            with self.assertRaises(Invalid):
                with s.step("dashboard", USER, place="lobby") as st:
                    st.update("projects", "ABC", {"name": "Renamed"})

    def v1_with_events(self):
        path = make_v1(self.dir)
        con = sqlite3.connect(str(path), isolation_level=None)
        for i, place in enumerate(("peek", "excel", None), start=1):
            con.execute("INSERT INTO item_events (at, item_id, kind, route, place, actor) VALUES ('2026-10-01', ?, 'change', 'dashboard', ?, 'you')",
                        (f"ABC-A-00{i}", place))
        con.execute("DELETE FROM item_events WHERE event_id = 3")           # the sequence now stands above the last row
        con.close()
        return path

    def test_a_version_1_file_keeps_its_events_and_their_ids_and_accepts_board(self):
        path = self.v1_with_events()
        con = sqlite3.connect(str(path))
        before = con.execute("SELECT * FROM item_events ORDER BY event_id").fetchall()
        seq = con.execute("SELECT seq FROM sqlite_sequence WHERE name = 'item_events'").fetchone()[0]
        con.close()
        self.assertEqual(seq, 3)
        s = open_store(path, onedrive_roots=[])
        try:
            self.assertEqual([tuple(r) for r in s.con.execute("SELECT * FROM item_events ORDER BY event_id")], [tuple(r) for r in before])
            self.assertIn("'board'", s.con.execute("SELECT sql FROM sqlite_master WHERE name = 'item_events'").fetchone()[0])
            self.assertEqual({r[1] for r in s.con.execute("PRAGMA index_list(item_events)")} & {"item_events_item", "item_events_change"},
                             {"item_events_item", "item_events_change"})
            self.assertEqual(s.con.execute("SELECT seq FROM sqlite_sequence WHERE name = 'item_events'").fetchone()[0], 3)
            self.assertEqual(self.board_step(s), "board")
            self.assertEqual(s.con.execute("SELECT max(event_id) FROM item_events").fetchone()[0], 4)      # ids carry on, never reused
        finally:
            s.close()

    def test_a_second_open_does_not_rebuild_the_table(self):
        path = self.v1_with_events()
        open_store(path, onedrive_roots=[]).close()
        con = connect(path)
        try:
            with mock.patch.object(store_module, "_table_statements", side_effect=AssertionError("rebuilt")):
                store_module._item_events_allow_board(con)
        finally:
            con.close()

    def test_a_failure_in_the_rebuild_leaves_the_file_as_it_was(self):
        path = self.v1_with_events()
        con = sqlite3.connect(str(path))
        before = list(con.iterdump())
        con.close()
        with mock.patch.object(store_module, "_item_events_allow_board", side_effect=RuntimeError("forced")):
            with self.assertRaises(Invalid):
                open_store(path, onedrive_roots=[])
        con = sqlite3.connect(str(path))
        self.assertEqual(list(con.iterdump()), before)
        con.close()
        self.assertEqual(version(path), "1")


class UndoRowsAndSize(unittest.TestCase):
    """#126 review HIGH 1 and 2: the rebuild of item_events with foreign keys on."""

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="clark-test-"))
        self.addCleanup(shutil.rmtree, self.dir, True)

    def test_a_version_1_file_with_an_undo_in_it_migrates_and_keeps_every_row(self):
        path = make_v1(self.dir)
        con = sqlite3.connect(str(path), isolation_level=None)
        for i in (1, 2):
            con.execute("INSERT INTO item_events (at, item_id, kind, route, actor, undoes) VALUES ('2026-10-01', ?, 'change', 'dashboard', 'you', ?)",
                        (f"ABC-A-00{i}", None if i == 1 else 1))        # event 2 is an Undo of event 1
        before = con.execute("SELECT * FROM item_events ORDER BY event_id").fetchall()
        con.close()
        s = open_store(path, onedrive_roots=[])
        try:
            self.assertEqual(version(path), str(store_module.SCHEMA_VERSION))
            self.assertEqual([tuple(r) for r in s.con.execute("SELECT * FROM item_events ORDER BY event_id")], [tuple(r) for r in before])
            self.assertEqual(s.con.execute("PRAGMA foreign_keys").fetchone()[0], 1)
            self.assertEqual(s.con.execute("PRAGMA foreign_key_check").fetchall(), [])
        finally:
            s.close()

    def test_foreign_keys_are_back_on_after_a_failure(self):
        path = make_v1(self.dir)
        con = connect(path)
        try:
            with mock.patch.object(store_module, "_item_events_allow_board", side_effect=RuntimeError("forced")):
                with self.assertRaises(RuntimeError):
                    migrate(con)
            self.assertEqual(con.execute("PRAGMA foreign_keys").fetchone()[0], 1)
        finally:
            con.close()

    def test_forty_thousand_events_migrate_in_under_five_seconds(self):
        path = make_v1(self.dir)
        con = sqlite3.connect(str(path), isolation_level=None)
        con.execute("BEGIN")
        con.executemany("INSERT INTO item_events (at, item_id, kind, route, actor, undoes) VALUES ('2026-10-01', 'ABC-A-001', 'change', 'dashboard', 'you', ?)",
                        [(None if i % 2 else max(1, i - 1),) for i in range(40000)])
        con.execute("COMMIT")
        con.close()
        began = time.monotonic()
        open_store(path, onedrive_roots=[]).close()
        self.assertLess(time.monotonic() - began, 5)
        self.assertEqual(version(path), str(store_module.SCHEMA_VERSION))


class OrderedMigrations(unittest.TestCase):
    """#126: the migrations are an ordered table (version -> step) run in order in one transaction, so a version 3 can follow."""

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="clark-test-"))
        self.addCleanup(shutil.rmtree, self.dir, True)

    def test_the_table_runs_from_2_to_the_current_version(self):
        self.assertEqual([n for n, _ in store_module.MIGRATIONS], list(range(2, store_module.SCHEMA_VERSION + 1)))

    def test_steps_run_in_order_in_one_transaction_and_the_version_follows_each(self):
        path = make_v1(self.dir)
        seen = []
        con = connect(path)
        try:
            def two(c):
                seen.append((2, c.in_transaction, c.execute("SELECT v FROM meta WHERE k = 'schema_version'").fetchone()[0]))
            def three(c):
                seen.append((3, c.in_transaction, c.execute("SELECT v FROM meta WHERE k = 'schema_version'").fetchone()[0]))
            with mock.patch.object(store_module, "SCHEMA_VERSION", 3):
                migrate(con, table=((2, two), (3, three)))
            self.assertEqual(seen, [(2, True, "1"), (3, True, "2")])
            self.assertEqual(con.execute("SELECT v FROM meta WHERE k = 'schema_version'").fetchone()[0], "3")
        finally:
            con.close()

    def test_a_file_already_at_the_last_version_but_one_runs_only_the_last_step(self):
        path = make_v1(self.dir)
        open_store(path, onedrive_roots=[]).close()           # now at the current version
        ran = []
        con = connect(path)
        try:
            with mock.patch.object(store_module, "SCHEMA_VERSION", 4):
                migrate(con, table=((2, lambda c: ran.append(2)), (3, lambda c: ran.append(3)), (4, lambda c: ran.append(4))))
            self.assertEqual(ran, [4])
        finally:
            con.close()

    def test_a_failing_later_step_rolls_every_step_back(self):
        path = make_v1(self.dir)
        con = sqlite3.connect(str(path))
        before = list(con.iterdump())
        con.close()
        con = connect(path)
        try:
            def boom(c):
                raise RuntimeError("forced")
            with mock.patch.object(store_module, "SCHEMA_VERSION", 3):
                with self.assertRaises(RuntimeError):
                    migrate(con, table=((2, store_module.migrate_to_2), (3, boom)))
        finally:
            con.close()
        con = sqlite3.connect(str(path))
        self.assertEqual(list(con.iterdump()), before)
        con.close()

    def test_a_gap_or_a_wrong_end_in_the_table_is_refused_in_plain_words(self):
        for table in (((3, print),), ((2, print), (4, print)), ((2, print),)):
            with self.assertRaises(Invalid) as caught:
                store_module.migration_plan(1, table)
            self.assertIn("is missing a step. Install the latest clark, then try again.", str(caught.exception))
            self.assertNotIn("gap", str(caught.exception))
            self.assertNotIn("sqlite", str(caught.exception).lower())

    def test_an_unknown_version_is_refused_in_plain_words(self):
        for v in (0, store_module.SCHEMA_VERSION + 1):
            with self.assertRaises(Invalid) as caught:
                store_module.migration_plan(v)
            self.assertIn("does not know", str(caught.exception))

    def test_version_0_says_restore_a_backup_or_ask_the_clark_team(self):
        with self.assertRaises(Invalid) as caught:
            store_module.migration_plan(0)
        self.assertTrue(str(caught.exception).endswith("Restore a backup, or ask the clark team for help."))
        self.assertNotIn("damaged", str(caught.exception))

    def test_a_file_with_version_0_is_refused_and_left_alone(self):
        path = make_v1(self.dir)
        con = sqlite3.connect(str(path), isolation_level=None)
        con.execute("UPDATE meta SET v = '0' WHERE k = 'schema_version'")
        con.close()
        with self.assertRaises(Invalid):
            open_store(path, onedrive_roots=[])
        self.assertEqual(version(path), "0")


class OldDanglingRows(unittest.TestCase):
    """#126: a row that was already dangling in the version-1 file is not the update's doing and must not block it."""

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="clark-test-"))
        self.addCleanup(shutil.rmtree, self.dir, True)

    def test_an_old_dangling_event_row_does_not_block_the_migration(self):
        path = make_v1(self.dir)
        con = sqlite3.connect(str(path), isolation_level=None)
        con.execute("INSERT INTO item_events (at, item_id, kind, route, actor, undoes) VALUES ('2026-10-01', 'ABC-A-001', 'change', 'dashboard', 'you', 999)")
        self.assertTrue(con.execute("PRAGMA foreign_key_check").fetchall())       # dangling before we start
        con.close()
        s = open_store(path, onedrive_roots=[])
        try:
            self.assertEqual(version(path), str(store_module.SCHEMA_VERSION))
            self.assertEqual(s.con.execute("SELECT count(*) FROM item_events").fetchone()[0], 1)
            self.assertEqual(s.con.execute("PRAGMA foreign_keys").fetchone()[0], 1)
        finally:
            s.close()

    def test_a_new_violation_still_refuses_and_leaves_the_file_as_it_was(self):
        path = make_v1(self.dir)
        con = sqlite3.connect(str(path), isolation_level=None)
        con.execute("INSERT INTO item_events (at, item_id, kind, route, actor, undoes) VALUES ('2026-10-01', 'ABC-A-001', 'change', 'dashboard', 'you', 999)")
        before = list(con.iterdump())
        con.close()
        def breaks(c):
            c.execute("INSERT INTO item_events (at, item_id, kind, route, actor, undoes) VALUES ('2026-10-02', 'ABC-A-002', 'change', 'dashboard', 'you', 998)")
        with mock.patch.object(store_module, "MIGRATIONS", ((2, store_module.migrate_to_2), (3, breaks))), \
                mock.patch.object(store_module, "SCHEMA_VERSION", 3):
            with self.assertRaises(Invalid) as caught:
                open_store(path, onedrive_roots=[])
        self.assertEqual(str(caught.exception), store_module.MIGRATE_INCONSISTENT)
        self.assertNotIn("space", str(caught.exception))
        self.assertIn("Nothing was changed", str(caught.exception))
        self.assertIn("Ask the clark team for help", str(caught.exception))
        con = sqlite3.connect(str(path))
        self.assertEqual(list(con.iterdump()), before)
        con.close()
        self.assertEqual(version(path), "1")

    def test_a_disk_error_keeps_the_space_message(self):
        path = make_v1(self.dir)
        with mock.patch.object(store_module, "_add_documents_archived", side_effect=sqlite3.OperationalError("disk I/O error")):
            with self.assertRaises(Invalid) as caught:
                open_store(path, onedrive_roots=[])
        self.assertEqual(str(caught.exception), store_module.MIGRATE_DISK)
        self.assertIn("has space", str(caught.exception))
        self.assertNotEqual(store_module.MIGRATE_DISK, store_module.MIGRATE_INCONSISTENT)

    def _words_for(self, message):
        folder = Path(tempfile.mkdtemp(dir=str(self.dir)))
        path = make_v1(folder)
        with mock.patch.object(store_module, "_add_documents_archived", side_effect=sqlite3.OperationalError(message)):
            with self.assertRaises(Invalid) as caught:
                open_store(path, onedrive_roots=[])
        return str(caught.exception)

    def test_disk_full_gets_the_space_words(self):
        for message in ("database or disk is full", "unable to open database file", "attempt to write a readonly database"):
            self.assertEqual(self._words_for(message), store_module.MIGRATE_DISK)

    def test_a_locked_database_says_it_is_in_use(self):
        for message in ("database is locked", "database table is locked"):
            self.assertEqual(self._words_for(message), store_module.MIGRATE_BUSY)
        self.assertIn("in use by another program", store_module.MIGRATE_BUSY)
        self.assertIn("Your data is as it was", store_module.MIGRATE_BUSY)

    def test_the_busy_words_reach_the_page_through_the_changes_route(self):
        """changes._call passes a store message on only when it starts with one of MIGRATE_REFUSAL_STARTS; any other start
        shows the page its 'restore a backup' wording, which is wrong for a database that is only busy."""
        from clark import changes
        self.assertTrue(store_module.MIGRATE_BUSY.startswith(store_module.MIGRATE_REFUSAL_STARTS))
        for message in ("database is locked", "database table is locked"):
            folder = Path(tempfile.mkdtemp(dir=str(self.dir)))
            path = make_v1(folder)
            with mock.patch.object(store_module, "_add_documents_archived", side_effect=sqlite3.OperationalError(message)):
                status, body = changes._call(path, [], "tester", lambda store, who, req: (200, {}), {})
            self.assertEqual(status, 503)
            self.assertEqual(body["message"], store_module.MIGRATE_BUSY)
            self.assertNotEqual(body["message"], changes.CANT_OPEN)

    def test_other_database_errors_do_not_mention_disk_space(self):
        for message in ("no such table: documents", "no such column: x", 'near "SELEC": syntax error'):
            said = self._words_for(message)
            self.assertEqual(said, store_module.MIGRATE_FAILED)
            self.assertNotIn("space", said)
            self.assertNotIn("disk", said)


class SafetyCopy(unittest.TestCase):
    """An existing version-1 file is copied first (backup.make, family migrate); a brand-new database takes no copy."""

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="clark-test-"))
        self.addCleanup(shutil.rmtree, self.dir, True)

    def copies(self):
        return sorted((self.dir / "backups").glob("*-migrate.db")) if (self.dir / "backups").exists() else []

    def test_a_version_1_file_is_copied_before_it_is_migrated(self):
        path = make_v1(self.dir)
        open_store(path, onedrive_roots=[]).con.close()
        (copy,) = self.copies()
        self.assertEqual(version(copy), "1")
        self.assertEqual(version(path), str(store_module.SCHEMA_VERSION))

    def test_a_new_database_takes_no_copy(self):
        open_store(self.dir / "clark.db", onedrive_roots=[]).con.close()
        self.assertEqual(self.copies(), [])

    def test_a_file_already_at_version_2_takes_no_copy(self):
        path = make_v1(self.dir)
        open_store(path, onedrive_roots=[]).con.close()
        for old in self.copies():
            old.unlink()
        open_store(path, onedrive_roots=[]).con.close()
        self.assertEqual(self.copies(), [])

    def test_a_failed_copy_refuses_the_update_and_leaves_the_file_as_it_was(self):
        path = make_v1(self.dir)
        con = sqlite3.connect(str(path))
        before = list(con.iterdump())
        con.close()
        from clark import backup
        with mock.patch.object(backup, "_write", side_effect=OSError("disk full")):
            with self.assertRaises(Invalid) as caught:
                open_store(path, onedrive_roots=[])
        words = str(caught.exception)
        self.assertIn("backup of your data must be made first", words)
        self.assertIn("Nothing was changed", words)
        self.assertNotIn("disk full", words)
        con = sqlite3.connect(str(path))
        self.assertEqual(list(con.iterdump()), before)        # every table and row as it was (opening sets the file to WAL, as ever)
        con.close()
        self.assertEqual(version(path), "1")


    def test_a_backups_folder_that_cannot_be_written_changes_nothing(self):
        path = make_v1(self.dir)
        (self.dir / "backups").write_text("a file where the folder should be", encoding="utf-8")
        with self.assertRaises(Invalid) as caught:
            open_store(path, onedrive_roots=[])
        self.assertIn("Nothing was changed", str(caught.exception))
        self.assertEqual(version(path), "1")

    def test_two_windows_opening_the_same_version_1_file_take_one_copy(self):
        path = make_v1(self.dir)
        first = open_store(path, onedrive_roots=[])
        second = open_store(path, onedrive_roots=[])
        first.con.close()
        second.con.close()
        self.assertEqual(len(self.copies()), 1)
        self.assertEqual(version(path), str(store_module.SCHEMA_VERSION))


class FailedMigrationWords(unittest.TestCase):
    """A failed update says so in plain words, with a next step, never "not a database clark can read" or SQLite's text."""

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="clark-test-"))
        self.addCleanup(shutil.rmtree, self.dir, True)

    def test_a_failed_migration_says_nothing_was_changed(self):
        path = make_v1(self.dir)
        con = sqlite3.connect(str(path))
        before = list(con.iterdump())
        con.close()
        with mock.patch.object(store_module, "_add_documents_archived", side_effect=sqlite3.DatabaseError("disk image is malformed")):
            with self.assertRaises(Invalid) as caught:
                open_store(path, onedrive_roots=[])
        words = str(caught.exception)
        self.assertEqual(words, store_module.MIGRATE_FAILED)
        for leak in ("not a database", "malformed", "restore a backup", "sqlite"):
            self.assertNotIn(leak, words.lower())
        self.assertIn("Nothing was changed", words)
        self.assertIn("ask the clark team for help", words)
        self.assertNotIn("space", words)             # the catch-all says nothing about the disk
        self.assertTrue(words.startswith("The database could not be updated."))
        self.assertFalse(words.lower().startswith("clark"))
        con = sqlite3.connect(str(path))
        self.assertEqual(list(con.iterdump()), before)
        con.close()

    def test_the_server_says_the_same_words(self):
        from clark import changes
        path = make_v1(self.dir)
        with mock.patch.object(store_module, "_add_documents_archived", side_effect=sqlite3.DatabaseError("x")):
            status, body = changes._call(str(path), [], "you", lambda *a: (200, {}), {})
        self.assertEqual((status, body["message"]), (503, store_module.MIGRATE_FAILED))

    def test_a_file_that_is_not_a_database_does_not_show_sqlite_text(self):
        path = self.dir / "clark.db"
        path.write_bytes(b"this is not a database at all" * 50)
        with self.assertRaises(Invalid) as caught:
            open_store(path, onedrive_roots=[])
        self.assertNotIn("(", str(caught.exception))


if __name__ == "__main__":
    unittest.main()


class MadeOpWord(unittest.TestCase):
    """#126: changes.py uses the store's own constant for a made row, not a word built from two pieces."""

    def test_changes_imports_the_stores_constant(self):
        from clark import changes
        self.assertIs(changes.MADE_OP, store_module.OP_MADE)
        self.assertEqual(store_module.OP_MADE, "insert")

    def test_the_word_is_not_built_from_pieces(self):
        src = (ROOT / "src" / "clark" / "changes.py").read_text(encoding="utf-8")
        self.assertNotIn('"ins" +', src)
        self.assertNotIn("'ins' +", src)


class AnyFaultAndPlanFirst(unittest.TestCase):
    """#126: any fault in a step (not only SQLite's) is said in plain words and rolled back; a refused plan makes no copy."""

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="clark-test-"))
        self.addCleanup(shutil.rmtree, self.dir, True)

    def test_a_runtime_error_in_a_step_comes_out_as_the_plain_words_and_the_file_is_as_it_was(self):
        path = make_v1(self.dir)
        con = sqlite3.connect(str(path))
        before = list(con.iterdump())
        con.close()
        with mock.patch.object(store_module, "_add_documents_archived", side_effect=RuntimeError("forced")):
            with self.assertRaises(Invalid) as caught:
                open_store(path, onedrive_roots=[])
        self.assertEqual(str(caught.exception), store_module.MIGRATE_FAILED)
        self.assertNotIn("forced", str(caught.exception))
        con = sqlite3.connect(str(path))
        self.assertEqual(list(con.iterdump()), before)
        con.close()

    def test_a_refused_plan_takes_no_safety_copy(self):
        path = make_v1(self.dir)
        with mock.patch.object(store_module, "SCHEMA_VERSION", 4):          # the table ends at 3: a step is missing
            with self.assertRaises(Invalid) as caught:
                open_store(path, onedrive_roots=[])
        self.assertIn("missing a step", str(caught.exception))
        self.assertFalse((self.dir / "backups").exists() and list((self.dir / "backups").glob("*-migrate.db")))
        self.assertEqual(version(path), "1")

    def test_an_empty_table_is_refused_once_the_version_is_above_1(self):
        with mock.patch.object(store_module, "SCHEMA_VERSION", 3):
            with self.assertRaises(Invalid) as caught:
                store_module.migration_plan(1, ())
        self.assertIn("is missing a step. Install the latest clark, then try again.", str(caught.exception))
        with mock.patch.object(store_module, "SCHEMA_VERSION", 1):
            self.assertEqual(store_module.migration_plan(1, ()), [])

    def test_a_bumped_version_with_no_steps_does_not_hand_back_an_unmigrated_file(self):
        path = make_v1(self.dir)
        with mock.patch.object(store_module, "SCHEMA_VERSION", 3), mock.patch.object(store_module, "MIGRATIONS", ()):
            with self.assertRaises(Invalid):
                open_store(path, onedrive_roots=[])
        self.assertEqual(version(path), "1")


class PlainRefusalsReachThePage(unittest.TestCase):
    """#126: the safety-copy refusal and the plan's refusals are shown as written, not as "clark can't read its data"."""

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="clark-test-"))
        self.addCleanup(shutil.rmtree, self.dir, True)

    def said(self, path):
        from clark import changes
        return changes._call(str(path), [], "you", lambda *a: (200, {}), {})

    def test_a_failed_safety_copy_is_shown_as_it_was_written(self):
        from clark import backup, changes
        path = make_v1(self.dir)
        with mock.patch.object(backup, "_write", side_effect=OSError("disk full")):
            status, body = self.said(path)
        self.assertEqual(status, 503)
        self.assertIn("backup of your data must be made first", body["message"])
        self.assertNotEqual(body["message"], changes.CANT_OPEN)

    def test_a_missing_step_is_shown_as_it_was_written(self):
        path = make_v1(self.dir)
        with mock.patch.object(store_module, "SCHEMA_VERSION", 4):
            status, body = self.said(path)
        self.assertEqual(status, 503)
        self.assertIn("missing a step. Install the latest clark, then try again.", body["message"])

    def test_an_unknown_version_is_shown_as_it_was_written(self):
        path = make_v1(self.dir)
        con = sqlite3.connect(str(path), isolation_level=None)
        con.execute("UPDATE meta SET v = '0' WHERE k = 'schema_version'")
        con.close()
        status, body = self.said(path)
        self.assertEqual(status, 503)
        self.assertIn("does not know", body["message"])


class WordsHaveANextStep(unittest.TestCase):
    """#126: the unknown-version message says what to do next, and the data-model note matches the code."""

    def test_a_version_newer_than_clark_knows_says_to_install_the_latest_clark(self):
        with self.assertRaises(Invalid) as caught:
            store_module.migration_plan(store_module.SCHEMA_VERSION + 1)
        self.assertTrue(str(caught.exception).endswith("Install the latest clark, then try again."))

    def test_the_excel_import_says_no_longer_in_the_workbook_and_nothing_is_deleted(self):
        text = (ROOT / "src" / "clark" / "excel_import.py").read_text(encoding="utf-8")
        self.assertIn("nothing is deleted", text)
        self.assertNotIn("rows missing from the", text)
        self.assertNotIn("is missing from it", text)
        self.assertNotIn("for being missing from", text)

    def test_a_project_need_not_be_closed_before_it_is_archived(self):
        text = (ROOT / "docs" / "handoff" / "data-model.md").read_text(encoding="utf-8")
        self.assertNotIn("must be closed", text)
        with DemoStore() as status:
            with status.step("dashboard", USER) as st:
                st.archive("projects", "ABC")
            self.assertEqual(status.read("projects", ref="ABC")["archived"], 1)


class FrozenVersion2(unittest.TestCase):
    """#126: migrate_to_2 makes the tables as version 2 had them, from its own frozen file, not from the live schema.sql, so a
    version 3 that changes one of them cannot change what a version-1 file is brought to."""

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="clark-test-"))
        self.addCleanup(shutil.rmtree, self.dir, True)

    def test_migrate_to_2_does_not_read_the_live_schema(self):
        path = make_v1(self.dir, without=NEW_TABLES)
        real = store_module.SCHEMA.read_text(encoding="utf-8")
        changed = real.replace("hidden  INTEGER NOT NULL DEFAULT 0 CHECK (hidden IN (0,1)),\n  sort_order INTEGER NOT NULL,\n  PRIMARY KEY (project, id)",
                               "hidden  INTEGER NOT NULL DEFAULT 0 CHECK (hidden IN (0,1)),\n  later_column TEXT,\n  sort_order INTEGER NOT NULL,\n  PRIMARY KEY (project, id)")
        self.assertNotEqual(real, changed, "the test must really change report_sections")
        fake = Path(self.dir) / "schema-later.sql"
        fake.write_text(changed, encoding="utf-8")
        with mock.patch.object(store_module, "SCHEMA", fake):
            open_store(path, onedrive_roots=[]).close()
        con = sqlite3.connect(str(path))
        try:
            names = [r[1] for r in con.execute("PRAGMA table_info(report_sections)")]
        finally:
            con.close()
        self.assertNotIn("later_column", names)
        self.assertIn("sort_order", names)

    def test_the_frozen_file_holds_the_four_tables_version_2_makes_and_the_board_place(self):
        text = store_module.SCHEMA_V2.read_text(encoding="utf-8")
        for name in ("item_events", "report_sections", "glance_tiles", "report_hidden"):
            self.assertIn(f"CREATE TABLE IF NOT EXISTS {name} (", text)
        self.assertIn("'board'", text)
        self.assertEqual(len(store_module._table_statements()), 4)
