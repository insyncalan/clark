"""The migration chain: an older database is copied first, then brought up through every step in order, in one transaction; a
failure leaves it as it was; a newer database, a gap or a missing step is refused with nothing changed; and the undo of an update
puts the copy back and reads the same rows."""
import ast
import hashlib
import inspect
import os
import re
import shutil
import sqlite3
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock

from _paths import ROOT
from clark import backup
from clark import store as store_module
from clark.store import Invalid, open_store
from test_store_migration import make_v1, version

SRC = ROOT / "src" / "clark"
FROZEN = {"schema_v2.sql": "baa137b0aad47bee9ddb4fb3ca98084a4e4f1d5dce51cf03e7cd74bd8262b960",
          "schema_v6.sql": "1929544493e9aee5efef288f62f68d4989f23e76d403b1fb0d97873ea208b732"}     # each step's frozen tables, by file: pinned, never changed


def dump(path):
    con = sqlite3.connect(str(path))
    try:
        return list(con.iterdump())
    finally:
        con.close()


def rows(path, table):
    con = sqlite3.connect(str(path))
    try:
        return con.execute(f"SELECT * FROM {table} ORDER BY rowid").fetchall()
    finally:
        con.close()


def copies(folder, tag=None):
    folder = Path(folder) / "backups"
    if not folder.is_dir():
        return []
    return [e for e in backup.entries(folder) if tag is None or e.tag == tag]


def chain(record, upto, fail_at=None, partial=True):
    """A table of steps 2 to `upto` that note their number and leave a row behind; the step `fail_at` writes first, then fails."""
    def step(n):
        def run(con):
            con.execute(f"CREATE TABLE IF NOT EXISTS step_{n} (a INTEGER)")
            con.execute(f"INSERT INTO step_{n} (a) VALUES ({n})")
            if n == fail_at:
                if partial:
                    con.execute("INSERT INTO projects (code, name) VALUES ('ZZZ', 'Written then failed')")
                raise RuntimeError("forced")
            record.append(n)
        return run
    return tuple((n, step(n)) for n in range(2, upto + 1))


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="clark-test-"))
        self.addCleanup(shutil.rmtree, self.dir, True)


class TheChain(Base):
    def test_an_old_file_moves_up_through_every_real_step_in_order_and_keeps_its_rows(self):
        path = make_v1(self.dir)
        before = {t: rows(path, t) for t in ("projects", "documents")}
        seen = []
        table = tuple((n, (lambda fn, n: lambda con: (seen.append(n), fn(con)))(fn, n)) for n, fn in store_module.MIGRATIONS)
        with mock.patch.object(store_module, "MIGRATIONS", table):
            s = open_store(path, onedrive_roots=[])
            s.close()
        self.assertEqual(seen, list(range(2, store_module.SCHEMA_VERSION + 1)))
        self.assertEqual(version(path), str(store_module.SCHEMA_VERSION))
        self.assertEqual(rows(path, "projects"), before["projects"])
        self.assertEqual([r[:6] for r in rows(path, "documents")], [r[:6] for r in before["documents"]])

    def test_a_brought_up_file_has_the_same_tables_columns_indexes_and_keys_as_a_new_one(self):
        def shape(path):
            con = sqlite3.connect(str(path))
            try:
                out = {"indexes": sorted(r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type = 'index' AND sql IS NOT NULL"))}
                for (t,) in con.execute("SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name").fetchall():
                    out[t] = (sorted(tuple(r[1:6]) for r in con.execute(f"PRAGMA table_info({t})")),
                              sorted(tuple(r[2:5]) for r in con.execute(f"PRAGMA foreign_key_list({t})")))
                return out
            finally:
                con.close()
        old, new = self.dir / "old", self.dir / "new"
        old.mkdir()
        new.mkdir()
        open_store(make_v1(old), onedrive_roots=[]).close()
        open_store(new / "clark.db", onedrive_roots=[]).close()
        self.assertEqual(shape(old / "clark.db"), shape(new / "clark.db"))

    def test_every_start_runs_only_the_steps_after_it_in_order(self):
        for start in range(1, 5):
            with self.subTest(start=start):
                folder = self.dir / f"start{start}"
                folder.mkdir()
                path = make_v1(folder)
                con = sqlite3.connect(str(path), isolation_level=None)
                con.execute("UPDATE meta SET v = ? WHERE k = 'schema_version'", (str(start),))
                con.close()
                seen = []
                with mock.patch.object(store_module, "MIGRATIONS", chain(seen, 5)), \
                        mock.patch.object(store_module, "SCHEMA_VERSION", 5):
                    s = open_store(path, onedrive_roots=[])
                    self.assertIsNotNone(s.migration_backup)
                    s.close()
                self.assertEqual(seen, list(range(start + 1, 6)))
                self.assertEqual(version(path), "5")

    def test_the_copy_is_taken_before_the_first_step_and_holds_the_old_version(self):
        path = make_v1(self.dir)
        found = []

        def first(con):
            found.extend(copies(self.dir, "migrate"))
        with mock.patch.object(store_module, "MIGRATIONS", ((2, first),)), \
                mock.patch.object(store_module, "SCHEMA_VERSION", 2):
            s = open_store(path, onedrive_roots=[])
            s.close()
        self.assertEqual(len(found), 1)
        self.assertEqual(s.migration_backup, found[0].path)
        self.assertEqual(version(found[0].path), "1")

    def test_a_failure_at_any_step_after_partial_writes_leaves_the_file_as_it_was(self):
        for fail_at in range(2, 6):
            with self.subTest(fail_at=fail_at):
                folder = self.dir / f"fail{fail_at}"
                folder.mkdir()
                path = make_v1(folder)
                before = dump(path)
                with mock.patch.object(store_module, "MIGRATIONS", chain([], 5, fail_at)), \
                        mock.patch.object(store_module, "SCHEMA_VERSION", 5):
                    with self.assertRaises(Invalid) as caught:
                        open_store(path, onedrive_roots=[])
                said = str(caught.exception)
                self.assertTrue(said.startswith("The database could not be updated. Nothing was changed."), said)
                self.assertFalse(re.search(r"[0-9]", said), "no step number is shown")
                for word in ("migration", "schema", "rollback"):
                    self.assertNotIn(word, said.lower())
                self.assertEqual(dump(path), before)
                self.assertEqual(version(path), "1")
                self.assertEqual(len(copies(folder, "migrate")), 1)       # the copy was taken first, and is kept

    def test_a_failure_after_any_real_step_leaves_a_real_shaped_file_as_it_was(self):
        for fail_at in range(2, store_module.SCHEMA_VERSION + 1):
            with self.subTest(fail_at=fail_at):
                folder = self.dir / f"real{fail_at}"
                folder.mkdir()
                path = make_v1(folder)
                before = dump(path)

                def failing(n, fn):
                    def run(con):
                        fn(con)                       # the real step, then a fault after its writes
                        if n == fail_at:
                            raise RuntimeError("forced")
                    return run
                table = tuple((n, failing(n, fn)) for n, fn in store_module.MIGRATIONS)
                with mock.patch.object(store_module, "MIGRATIONS", table):
                    with self.assertRaises(Invalid):
                        open_store(path, onedrive_roots=[])
                self.assertEqual(dump(path), before)
                self.assertEqual(version(path), "1")

    def test_running_twice_changes_nothing_and_takes_one_copy(self):
        path = make_v1(self.dir)
        first = open_store(path, onedrive_roots=[])
        self.assertIsNotNone(first.migration_backup)
        first.close()
        after = dump(path)
        second = open_store(path, onedrive_roots=[])
        self.assertIsNone(second.migration_backup)
        second.close()
        self.assertEqual(dump(path), after)
        self.assertEqual(len(copies(self.dir, "migrate")), 1)

    def test_a_full_disk_in_a_step_says_so_and_leaves_the_file_as_it_was(self):
        path = make_v1(self.dir)
        before = dump(path)

        def full(con):
            con.execute("INSERT INTO projects (code, name) VALUES ('ZZZ', 'Half')")
            raise sqlite3.OperationalError("database or disk is full")
        with mock.patch.object(store_module, "MIGRATIONS", ((2, full),)), \
                mock.patch.object(store_module, "SCHEMA_VERSION", 2):
            with self.assertRaises(Invalid) as caught:
                open_store(path, onedrive_roots=[])
        self.assertEqual(str(caught.exception), store_module.MIGRATE_DISK)
        self.assertEqual(dump(path), before)

    @unittest.skipIf(hasattr(os, "geteuid") and os.geteuid() == 0, "the superuser can write anywhere")
    def test_a_data_folder_that_cannot_be_written_changes_nothing(self):
        path = make_v1(self.dir)
        before = dump(path)
        os.chmod(self.dir, 0o555)
        self.addCleanup(os.chmod, self.dir, 0o755)
        with self.assertRaises(Invalid):
            open_store(path, onedrive_roots=[])
        os.chmod(self.dir, 0o755)
        self.assertEqual(dump(path), before)
        self.assertEqual(version(path), "1")


class Refusals(Base):
    def test_a_newer_file_is_refused_in_the_set_words_with_nothing_changed_and_no_copy(self):
        path = make_v1(self.dir)
        con = sqlite3.connect(str(path), isolation_level=None)
        con.execute("UPDATE meta SET v = ? WHERE k = 'schema_version'", (str(store_module.SCHEMA_VERSION + 1),))
        con.close()
        before = dump(path)
        with self.assertRaises(Invalid) as caught:
            open_store(path, onedrive_roots=[])
        self.assertEqual(str(caught.exception), store_module.NEWER_DATA)
        self.assertTrue(str(caught.exception).startswith("This data needs a newer clark."))
        self.assertIn("Nothing was changed", str(caught.exception))
        self.assertEqual(dump(path), before)
        self.assertEqual(copies(self.dir), [])

    def test_the_newer_file_words_reach_the_page_as_written(self):
        from clark import changes
        path = make_v1(self.dir)
        con = sqlite3.connect(str(path), isolation_level=None)
        con.execute("UPDATE meta SET v = '99' WHERE k = 'schema_version'")
        con.close()
        status, body = changes._call(str(path), [], "you", lambda *a: (200, {}), {})
        self.assertEqual(status, 503)
        self.assertEqual(body["message"], store_module.NEWER_DATA)

    def test_a_gap_or_a_skipped_version_is_refused_before_any_copy(self):
        for table, top in ((((2, print), (4, print)), 4), (((3, print),), 3), (((2, print), (3, print)), 4)):
            with self.subTest(table=[n for n, _ in table]):
                folder = self.dir / ("t" + "".join(str(n) for n, _ in table) + str(top))
                folder.mkdir()
                path = make_v1(folder)
                before = dump(path)
                with mock.patch.object(store_module, "MIGRATIONS", table), \
                        mock.patch.object(store_module, "SCHEMA_VERSION", top):
                    with self.assertRaises(Invalid) as caught:
                        open_store(path, onedrive_roots=[])
                self.assertIn("missing a step", str(caught.exception))
                self.assertEqual(dump(path), before)
                self.assertEqual(copies(folder), [])

    def test_a_step_that_ends_the_transaction_is_stopped_and_does_not_claim_nothing_changed(self):
        path = make_v1(self.dir)

        def ends(con):
            con.executescript("CREATE TABLE IF NOT EXISTS stray (a INTEGER);")
        with mock.patch.object(store_module, "MIGRATIONS", ((2, ends),)), \
                mock.patch.object(store_module, "SCHEMA_VERSION", 2):
            with self.assertRaises(Invalid) as caught:
                open_store(path, onedrive_roots=[])
        self.assertEqual(str(caught.exception), store_module.MIGRATE_PART_WAY)
        self.assertNotIn("Nothing was changed", str(caught.exception))
        self.assertEqual(version(path), "1")
        self.assertEqual(len(copies(self.dir, "migrate")), 1)


class ForeignKeys(Base):
    def test_a_rebuilt_table_that_renumbers_its_rows_keeps_an_old_dangling_row_without_a_refusal(self):
        path = make_v1(self.dir)
        con = sqlite3.connect(str(path), isolation_level=None)
        con.execute("INSERT INTO item_events (at, item_id, kind, route, actor) VALUES ('2026-10-01', 'ABC-A-001', 'change', 'dashboard', 'you')")
        con.execute("INSERT INTO item_events (at, item_id, kind, route, actor, undoes) VALUES ('2026-10-01', 'ABC-A-001', 'change', 'dashboard', 'you', 999)")
        old = con.execute("PRAGMA foreign_key_check").fetchall()
        con.close()
        self.assertEqual(len(old), 1)

        def renumber(c):
            c.execute("CREATE TABLE ev_copy AS SELECT * FROM item_events")
            c.execute("DELETE FROM item_events")
            c.execute("INSERT INTO item_events (event_id, at, apply_id, item_id, change, kind, route, place, origin, actor, src_ref, undoes) "
                      "SELECT event_id + 100, at, apply_id, item_id, change, kind, route, place, origin, actor, src_ref, undoes "
                      "FROM ev_copy ORDER BY event_id DESC")
            c.execute("DROP TABLE ev_copy")
        with mock.patch.object(store_module, "MIGRATIONS", ((2, store_module.migrate_to_2), (3, renumber))), \
                mock.patch.object(store_module, "SCHEMA_VERSION", 3):
            s = open_store(path, onedrive_roots=[])
            s.close()
        con = sqlite3.connect(str(path))
        try:
            now = con.execute("PRAGMA foreign_key_check").fetchall()
        finally:
            con.close()
        self.assertEqual(version(path), "3")
        self.assertEqual(len(now), 1)
        self.assertNotEqual(now[0][1], old[0][1], "the test must really renumber the dangling row")

    def test_a_new_dangling_row_beside_an_old_one_is_refused(self):
        path = make_v1(self.dir)
        con = sqlite3.connect(str(path), isolation_level=None)
        con.execute("INSERT INTO item_events (at, item_id, kind, route, actor, undoes) VALUES ('2026-10-01', 'ABC-A-001', 'change', 'dashboard', 'you', 999)")
        con.close()
        before = dump(path)

        def another(c):
            c.execute("INSERT INTO item_events (at, item_id, kind, route, actor, undoes) VALUES ('2026-10-02', 'ABC-A-002', 'change', 'dashboard', 'you', 999)")
        with mock.patch.object(store_module, "MIGRATIONS", ((2, store_module.migrate_to_2), (3, another))), \
                mock.patch.object(store_module, "SCHEMA_VERSION", 3):
            with self.assertRaises(Invalid) as caught:
                open_store(path, onedrive_roots=[])
        self.assertEqual(str(caught.exception), store_module.MIGRATE_INCONSISTENT)
        self.assertEqual(dump(path), before)


class UndoAfterAnUpdate(Base):
    def updated(self):
        """A version-1 file brought up to date, then a project added after the update. The safety copy's name and the rows before."""
        path = make_v1(self.dir)
        before = {t: rows(path, t) for t in ("projects", "documents", "meta")}
        s = open_store(path, onedrive_roots=[])
        name = s.migration_backup.name
        s.close()
        con = sqlite3.connect(str(path), isolation_level=None)
        con.execute("INSERT INTO projects (code, name) VALUES ('DEF', 'Made after the update')")
        con.close()
        return path, name, before

    def test_undo_asks_first_and_changes_nothing_until_confirmed(self):
        path, name, _ = self.updated()
        before = dump(path)
        with self.assertRaises(Invalid) as caught:
            backup.restore_before_update(path, name)
        self.assertTrue(str(caught.exception).startswith("Changes made since the update will be lost."))
        self.assertEqual(dump(path), before)

    def test_undo_puts_the_copy_back_and_reads_the_same_rows_and_keeps_the_newer_file(self):
        path, name, before = self.updated()
        done = backup.restore_before_update(path, name, confirmed=True)
        self.assertEqual(done["said"], "Changes made since the update will be lost.")
        for t, had in before.items():
            self.assertEqual(rows(path, t), had, t)
        self.assertEqual(version(path), "1")
        aside = done["replaced"] / "clark.db"
        self.assertTrue(aside.is_file(), "the newer database is moved aside, never deleted")
        self.assertIn(("DEF", "Made after the update"), [tuple(r[:2]) for r in rows(aside, "projects")])
        self.assertTrue(copies(self.dir, "restore"), "a copy of the newer database is taken first as well")

    def test_undo_is_refused_while_the_database_is_open_in_a_running_clark(self):
        path, name, _ = self.updated()
        before = dump(path)
        running = store_module.connect(path)
        try:
            running.execute("SELECT count(*) FROM projects").fetchone()
            with self.assertRaises(Invalid) as caught:
                backup.restore_before_update(path, name, confirmed=True)
        finally:
            running.close()
        self.assertIn("Nothing was changed", str(caught.exception))
        self.assertEqual(dump(path), before)

    def test_undo_with_the_copy_gone_is_refused_and_changes_nothing(self):
        path, name, _ = self.updated()
        before = dump(path)
        (self.dir / "backups" / name).unlink()
        with self.assertRaises(Invalid) as caught:
            backup.restore_before_update(path, name, confirmed=True)
        self.assertEqual(str(caught.exception), backup.UPDATE_GONE)
        self.assertEqual(dump(path), before)

    def test_undo_takes_only_a_copy_made_before_an_update(self):
        path, _, _ = self.updated()
        daily = backup.make(path, self.dir / "backups", [], "daily")
        with self.assertRaises(Invalid) as caught:
            backup.restore_before_update(path, daily.name, confirmed=True)
        self.assertIn("is not a copy taken before an update", str(caught.exception))
        for odd in ("", "../clark.db", "clark.db"):
            with self.assertRaises(Invalid):
                backup.restore_before_update(path, odd, confirmed=True)

    def test_a_migrate_copy_is_not_pushed_out_by_daily_copies(self):
        path, name, _ = self.updated()
        for _ in range(backup.KEEP + 3):
            backup.make(path, self.dir / "backups", [], "daily")
        self.assertEqual(len(copies(self.dir, "daily")), backup.KEEP)     # retention really ran
        self.assertIn(name, [e.name for e in copies(self.dir, "migrate")])


def _steps_and_what_they_call():
    """Every function in store.py that a migration step runs, found by reading the steps' code: the steps themselves and the
    store functions they call, at any depth."""
    seen, todo = {}, [fn for _, fn in store_module.MIGRATIONS]
    while todo:
        fn = todo.pop()
        if fn.__name__ in seen:
            continue
        seen[fn.__name__] = fn
        for node in ast.walk(ast.parse(textwrap.dedent(inspect.getsource(fn)))):
            if isinstance(node, ast.Name) and inspect.isfunction(getattr(store_module, node.id, None)):
                todo.append(getattr(store_module, node.id))
    return seen


NEWER_SQL = {"a window function": r"\bOVER\s*\(", "DROP COLUMN": r"\bDROP\s+COLUMN\b", "RETURNING": r"\bRETURNING\b",
             "a STRICT table": r"\)\s*STRICT\b", "a generated column": r"\bGENERATED\s+ALWAYS\b|\bAS\s*\([^)]*\)\s*(STORED|VIRTUAL)\b",
             "RENAME COLUMN": r"\bRENAME\s+COLUMN\b", "NULLS FIRST or LAST": r"\bNULLS\s+(FIRST|LAST)\b",
             "the JSON arrow": r"->", "iif()": r"\bIIF\s*\(", "unixepoch()": r"\bUNIXEPOCH\s*\("}


def _sql_in(fn):
    """The string constants in a function's code: the SQL it runs."""
    return [n.value for n in ast.walk(ast.parse(textwrap.dedent(inspect.getsource(fn))))
            if isinstance(n, ast.Constant) and isinstance(n.value, str)]


class WhatAStepMayUse(unittest.TestCase):
    def test_the_steps_are_found(self):
        found = _steps_and_what_they_call()
        for name in ("migrate_to_2", "_add_documents_archived", "_item_events_allow_board", "_table_statements"):
            self.assertIn(name, found)

    def test_no_step_ends_the_transaction(self):
        for name, fn in _steps_and_what_they_call().items():
            calls = {n.func.attr for n in ast.walk(ast.parse(textwrap.dedent(inspect.getsource(fn))))
                     if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
            self.assertNotIn("executescript", calls, name)
            self.assertNotIn("commit", calls, name)
            self.assertNotIn("rollback", calls, name)
            for sql in _sql_in(fn):
                self.assertFalse(re.match(r"\s*(COMMIT|ROLLBACK|BEGIN|END|SAVEPOINT|RELEASE|VACUUM)\b|\s*PRAGMA\s+\w+\s*=", sql, re.I), (name, sql))

    def test_the_sql_uses_nothing_newer_than_the_stated_sqlite(self):
        texts = {p.name: p.read_text(encoding="utf-8") for p in sorted(SRC.glob("schema*.sql"))}
        texts.update({name: "\n".join(_sql_in(fn)) for name, fn in _steps_and_what_they_call().items()})
        self.assertIn("schema_v2.sql", texts)
        for name, text in texts.items():
            code = "\n".join(line.split("--", 1)[0] if name.endswith(".sql") else line for line in text.splitlines())
            for feature, pattern in NEWER_SQL.items():
                self.assertFalse(re.search(pattern, code, re.I), f"{name} uses {feature}")

    def test_the_stated_sqlite_is_old_enough_and_this_python_has_at_least_it(self):
        self.assertLess(store_module.MIN_SQLITE, (3, 25, 0), "window functions came in 3.25; the stated lowest is below them")
        self.assertGreaterEqual(sqlite3.sqlite_version_info, store_module.MIN_SQLITE)

    def test_each_frozen_table_file_is_pinned(self):
        frozen = sorted(p.name for p in SRC.glob("schema_v*.sql"))
        self.assertEqual(frozen, sorted(FROZEN), "a new frozen file is pinned here when its step is added")
        for name, digest in FROZEN.items():
            self.assertEqual(hashlib.sha256((SRC / name).read_bytes()).hexdigest(), digest, f"{name} must never change")
            self.assertLessEqual(int(re.search(r"v([0-9]+)", name).group(1)), store_module.SCHEMA_VERSION)


if __name__ == "__main__":
    unittest.main()
