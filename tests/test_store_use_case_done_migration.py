"""#412: a use case can be Done. The migration step that widens use_cases.status to take 'Done' (src/clark/store.py, guarded).

SQLite cannot widen a CHECK in place, so the step makes the use_cases table again from its own frozen text (schema_v10.sql),
copies every row by column name with its id and rowid, and drops the old copy: the same pattern as the section-types step.
Nothing points at use_cases by a key, an index of its own or a trigger (actions, raid and decisions name a use case in a plain
text column; links and item_labels by text), so those rows are checked to be kept as they were.

The step's number is STEP below. If another step lands first, renumbering is: STEP here, SCHEMA_VERSION's line and the literal
beside migrate_use_case_done in store.py's MIGRATIONS, the frozen file's name (and its line in store.py and in
tests/test_migration_chain.py's FROZEN). Fictional data only.

Run: python3 dev/run_tests.py test_store_use_case_done_migration
"""
import re
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _demo import USER
from _paths import ROOT
from clark import backup, changes, store as store_module
from clark.store import Invalid, connect, migrate, open_store
from test_store_migration import make_v1, version

STEP = 10                                           # this step's number (see the docstring)
BEFORE = str(STEP - 1)                              # the version this step brings a file from
NOW = str(store_module.SCHEMA_VERSION)              # the version a plain open brings a file to (this step and any later one)
FROZEN_FILE = f"schema_v{STEP}.sql"
OLD_STATUSES = ("On track", "Flag", "High risk")
NEW_STATUSES = OLD_STATUSES + ("Done",)


def make_at(folder, level):
    """A file at `level`: a version-1 file brought up by the steps up to `level` only. The copy that bringing it up took is
    removed, so tests count only their own."""
    path = make_v1(folder)
    with mock.patch.object(store_module, "SCHEMA_VERSION", level), \
            mock.patch.object(store_module, "MIGRATIONS", tuple(m for m in store_module.MIGRATIONS if m[0] <= level)):
        open_store(path, onedrive_roots=[]).close()
    shutil.rmtree(Path(folder) / "backups", ignore_errors=True)
    assert version(path) == str(level)
    return path


def make_before(folder):
    """A file at the version just before this step: its use_cases takes On track, Flag and High risk only."""
    return make_at(folder, STEP - 1)


def to_this_step(path):
    """Open `path` with the steps up to this one only (no later step), so a test sees what this step alone changes."""
    with mock.patch.object(store_module, "SCHEMA_VERSION", STEP), \
            mock.patch.object(store_module, "MIGRATIONS", tuple(m for m in store_module.MIGRATIONS if m[0] <= STEP)):
        open_store(path, onedrive_roots=[]).close()


def add_use_cases(path):
    """Use cases in all three old statuses (one archived, one off the dashboard, a gap in the rowids, markup in the standing),
    and every kind of row that names a use case: an action, a risk and a decision linked to one, a link between two items,
    a label on a use case and its history line. Raw SQL, as an old clark would have left them."""
    con = sqlite3.connect(str(path), isolation_level=None)
    con.execute("PRAGMA foreign_keys = OFF")
    ucs = [("ABC-U-001", "1.1", "Invoice matching", "On track", "Matching live", "<p>Live &amp; <b>steady</b></p>", 1, 1, 0),
           ("ABC-U-002", "1.2", "Supplier portal", "Flag", "Two weeks behind", "", 2, 0, 0),
           ("ABC-U-003", "1.3 and 1.7", "Old archive off", "High risk", "No date yet", "<p>Waiting on legal</p>", 3, 1, 0),
           ("ABC-U-004", "", "Retired idea", "Flag", "", "", 4, 1, 1)]
    for n, u in enumerate(ucs):
        con.execute("INSERT INTO use_cases (rowid, id, ref, title, status, headline, standing, sort_order, client_visible, archived, "
                    "project, source, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ABC', 'test', '2026-10-30 09:00:00')",
                    (n * 3 + 2,) + u)                                     # rowids 2, 5, 8, 11: a gap a plain copy would close
    con.execute("INSERT INTO actions (id, project, description, raised, use_case, source) "
                "VALUES ('ABC-A-001', 'ABC', 'Send the matching rules', '2026-10-01', 'ABC-U-001', 'test')")
    con.execute("INSERT INTO raid (id, project, type, description, raised, use_case, source) "
                "VALUES ('ABC-001', 'ABC', 'Risk', 'Portal supplier late', '2026-10-01', 'ABC-U-002', 'test')")
    con.execute("INSERT INTO decisions (id, project, decision, raised, use_case, source) "
                "VALUES ('ABC-D-001', 'ABC', 'Keep the archive read-only', '2026-10-01', 'ABC-U-003', 'test')")
    con.execute("INSERT INTO links (from_item, to_item, kind, source) VALUES ('ABC-A-001', 'ABC-U-002', 'blocks', 'test')")
    con.execute("INSERT OR IGNORE INTO labels (name, colour, behaviour, default_choice, builtin) VALUES ('Sensitive', 'red', 'warn', 'exclude', 1)")
    con.execute("INSERT INTO item_labels (item_id, label, added_by) VALUES ('ABC-U-003', 'Sensitive', 'Sam Lee')")
    con.execute("INSERT INTO item_events (at, item_id, kind, route, actor) VALUES ('2026-10-30 09:00:00', 'ABC-U-002', 'change', 'dashboard', 'you')")
    con.close()
    return ucs


def use_cases_of(path):
    con = sqlite3.connect(str(path))
    try:
        return con.execute("SELECT rowid, * FROM use_cases ORDER BY rowid").fetchall()
    finally:
        con.close()


def every_row(path):
    """Every table's rows (meta and SQLite's own tables left out), each in rowid order: what a migration must keep."""
    con = sqlite3.connect(str(path))
    try:
        names = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' "
                                           "AND name != 'meta' ORDER BY name")]
        return {n: con.execute(f'SELECT rowid, * FROM "{n}" ORDER BY rowid').fetchall() for n in names}
    finally:
        con.close()


def schema_of(path, table=None):
    """Every table, index and trigger of the file (or only those on `table`): {(type, name): its definition without quoting or
    spaces}. SQLite writes a renamed table's name in quotes; nothing else may differ between a brought-up file and a new one."""
    con = sqlite3.connect(str(path))
    try:
        return {(t, n): re.sub(r'["\s]', "", sql or "") for t, n, tbl, sql in
                con.execute("SELECT type, name, tbl_name, sql FROM sqlite_master") if table is None or tbl == table}
    finally:
        con.close()


def table_sql(path):
    con = sqlite3.connect(str(path))
    try:
        return con.execute("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'use_cases'").fetchone()[0]
    finally:
        con.close()


def dump(path):
    con = sqlite3.connect(str(path))
    try:
        return list(con.iterdump())
    finally:
        con.close()


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="clark-test-"))
        self.addCleanup(shutil.rmtree, self.dir, True)

    def copies(self):
        return sorted((self.dir / "backups").glob("*-migrate.db")) if (self.dir / "backups").exists() else []


class TheNumber(Base):
    def test_the_step_is_in_the_table_at_its_number_and_the_table_has_no_gap(self):
        self.assertIn((STEP, store_module.migrate_use_case_done), store_module.MIGRATIONS)
        self.assertGreaterEqual(store_module.SCHEMA_VERSION, STEP)
        self.assertEqual([n for n, _ in store_module.MIGRATIONS], list(range(2, store_module.SCHEMA_VERSION + 1)))

    def test_the_number_is_written_once_beside_its_step_and_the_frozen_file_carries_it_in_its_name_only(self):
        src = (ROOT / "src" / "clark" / "store.py").read_text(encoding="utf-8")
        self.assertEqual(re.findall(r"\((\d+), migrate_use_case_done\)", src), [str(STEP)])
        self.assertNotIn(f"migrate_to_{STEP}", src)                          # named for what it does, not for its number
        self.assertEqual(store_module.SCHEMA_USE_CASES_DONE.name, FROZEN_FILE)
        self.assertNotRegex(store_module.SCHEMA_USE_CASES_DONE.read_text(encoding="utf-8"), rf"\b{STEP}\b")

    def test_the_step_before_this_one_is_the_people_step(self):
        steps = dict(store_module.MIGRATIONS)
        self.assertIs(steps[STEP - 1], store_module.migrate_people)
        self.assertIs(steps[STEP], store_module.migrate_use_case_done)

    def test_the_step_changes_no_other_table_index_or_trigger(self):
        path = make_before(self.dir)
        before = {k: v for k, v in schema_of(path).items() if k != ("table", "use_cases")}
        to_this_step(path)
        after = {k: v for k, v in schema_of(path).items() if k != ("table", "use_cases")}
        self.assertEqual(after, before)


class Migrating(Base):
    def test_a_version_9_file_keeps_every_use_case_id_status_and_link_and_takes_the_new_version(self):
        """The old-database upgrade: use cases in all three old statuses and every row that names one, all kept, ids kept."""
        path = make_before(self.dir)
        self.assertEqual(version(path), BEFORE)
        ucs = add_use_cases(path)
        before = every_row(path)
        self.assertEqual([r[1] for r in before["use_cases"]], [u[0] for u in ucs])
        self.assertEqual({r[5] for r in before["use_cases"]}, set(OLD_STATUSES))
        s = open_store(path, onedrive_roots=[])
        try:
            self.assertEqual(version(path), NOW)
            self.assertEqual(s.con.execute("PRAGMA foreign_keys").fetchone()[0], 1)
            self.assertEqual(s.con.execute("PRAGMA foreign_key_check").fetchall(), [])
            self.assertEqual(s.con.execute("SELECT count(*) FROM applies").fetchone()[0], 0)        # a migration is not a step
            self.assertEqual({r["id"]: r["status"] for r in s.read("use_cases", "ABC")},
                             {u[0]: u[3] for u in ucs if not u[8]})
        finally:
            s.close()
        after = every_row(path)
        self.assertEqual({t: after[t] for t in before}, before, "every row of every table, with its rowid, as it was")
        self.assertEqual([r[0] for r in after["use_cases"]], [2, 5, 8, 11], "the rowids are kept, gaps and all")
        self.assertIn("'Done'", table_sql(path))
        self.assertEqual(len(self.copies()), 1)

    def test_a_version_1_file_goes_through_every_step_and_keeps_its_use_cases(self):
        path = make_v1(self.dir)
        add_use_cases(path)
        before = use_cases_of(path)
        open_store(path, onedrive_roots=[]).close()
        self.assertEqual(use_cases_of(path), before)
        self.assertEqual(version(path), NOW)
        self.assertIn("'Done'", table_sql(path))

    def test_the_safety_copy_is_taken_first_opens_and_holds_the_old_version_and_rows(self):
        path = make_before(self.dir)
        add_use_cases(path)
        before = every_row(path)
        found = []
        real = store_module.migrate_use_case_done

        def look_first(con):
            found.extend(self.copies())                                       # the copy is already on disk when the step runs
            real(con)
        table = tuple((n, look_first if n == STEP else fn) for n, fn in store_module.MIGRATIONS)
        with mock.patch.object(store_module, "MIGRATIONS", table):
            open_store(path, onedrive_roots=[]).close()
        self.assertEqual(len(found), 1)
        (copy,) = self.copies()
        self.assertEqual(copy, found[0])
        self.assertEqual(version(copy), BEFORE)
        self.assertEqual(every_row(copy), before)
        self.assertNotIn("'Done'", table_sql(copy))
        con = sqlite3.connect(str(copy))
        self.assertEqual(con.execute("PRAGMA integrity_check").fetchone()[0], "ok")
        con.close()

    def test_a_failed_copy_refuses_the_open_and_changes_nothing(self):
        path = make_before(self.dir)
        add_use_cases(path)
        was = dump(path)
        with mock.patch.object(backup, "_write", side_effect=OSError("disk full")):
            with self.assertRaises(Invalid) as e:
                open_store(path, onedrive_roots=[])
        self.assertIn("Nothing was changed", str(e.exception))
        self.assertEqual(dump(path), was)
        self.assertEqual(version(path), BEFORE)

    def test_done_is_refused_before_and_taken_after_and_nothing_else_is(self):
        path = make_before(self.dir)
        con = sqlite3.connect(str(path), isolation_level=None)
        with self.assertRaises(sqlite3.IntegrityError):
            con.execute("INSERT INTO use_cases (id, project, title, status, source) VALUES ('ABC-U-050', 'ABC', 'T', 'Done', 'test')")
        con.close()
        open_store(path, onedrive_roots=[]).close()
        self.check_the_status_check(path)

    def test_a_new_database_takes_the_same_four(self):
        open_store(self.dir / "clark.db", onedrive_roots=[]).close()
        self.check_the_status_check(self.dir / "clark.db")

    def check_the_status_check(self, path):
        con = sqlite3.connect(str(path), isolation_level=None)
        con.execute("PRAGMA foreign_keys = OFF")
        try:
            for n, status in enumerate(NEW_STATUSES):
                con.execute("INSERT INTO use_cases (id, project, title, status, source) VALUES (?, 'ABC', 'T', ?, 'test')",
                            (f"ABC-U-{n + 60:03d}", status))
            for bad in ("done", "Done ", "Closed", "", "Complete", "DONE"):
                with self.assertRaises(sqlite3.IntegrityError, msg=bad):
                    con.execute("INSERT INTO use_cases (id, project, title, status, source) VALUES ('ABC-U-099', 'ABC', 'T', ?, 'test')", (bad,))
        finally:
            con.close()

    def test_a_brought_up_file_and_a_new_file_have_the_same_tables_indexes_and_triggers(self):
        path = make_before(self.dir)
        open_store(path, onedrive_roots=[]).close()
        fresh = Path(tempfile.mkdtemp(dir=str(self.dir)))
        open_store(fresh / "clark.db", onedrive_roots=[]).close()
        self.assertEqual(schema_of(path, "use_cases"), schema_of(fresh / "clark.db", "use_cases"))
        self.assertEqual(set(schema_of(path)), set(schema_of(fresh / "clark.db")), "the same tables, indexes and triggers by name")
        cols = []
        for p in (path, fresh / "clark.db"):
            con = sqlite3.connect(str(p))
            cols.append((con.execute("PRAGMA table_info(use_cases)").fetchall(), con.execute("PRAGMA index_list(use_cases)").fetchall()))
            con.close()
        self.assertEqual(cols[0], cols[1])

    def test_a_second_open_changes_nothing_and_takes_no_copy(self):
        path = make_before(self.dir)
        add_use_cases(path)
        open_store(path, onedrive_roots=[]).close()
        for old in self.copies():
            old.unlink()
        was = dump(path)
        open_store(path, onedrive_roots=[]).close()
        self.assertEqual(dump(path), was)
        self.assertEqual(self.copies(), [])

    def test_the_step_is_safe_to_run_twice(self):
        path = make_before(self.dir)
        add_use_cases(path)
        before = every_row(path)
        con = connect(path)
        try:
            con.execute("BEGIN IMMEDIATE")
            store_module.migrate_use_case_done(con)
            once = con.execute("SELECT sql FROM sqlite_master WHERE name = 'use_cases'").fetchone()[0]
            store_module.migrate_use_case_done(con)                     # the table already takes Done: nothing happens
            self.assertEqual(con.execute("SELECT sql FROM sqlite_master WHERE name = 'use_cases'").fetchone()[0], once)
            con.execute("COMMIT")
        finally:
            con.close()
        self.assertEqual(every_row(path), before)

    def test_the_step_on_a_new_database_does_nothing(self):
        path = self.dir / "clark.db"
        open_store(path, onedrive_roots=[]).close()
        was = dump(path)
        con = connect(path)
        try:
            con.execute("BEGIN IMMEDIATE")
            store_module.migrate_use_case_done(con)
            con.execute("COMMIT")
        finally:
            con.close()
        self.assertEqual(dump(path), was)

    def test_two_windows_opening_one_old_file_migrate_once_and_take_one_copy(self):
        path = make_before(self.dir)
        add_use_cases(path)
        first, second = open_store(path, onedrive_roots=[]), open_store(path, onedrive_roots=[])
        first.close()
        second.close()
        self.assertEqual(version(path), NOW)
        self.assertEqual(len(self.copies()), 1)

    def test_two_connections_on_one_old_file_run_the_step_once(self):
        path = make_before(self.dir)
        first, second = connect(path), connect(path)
        try:
            migrate(first)
            with mock.patch.object(store_module, "_use_cases_allow_done") as again:
                migrate(second)
            again.assert_not_called()
        finally:
            first.close()
            second.close()

    def test_a_failing_step_leaves_the_file_as_it_was(self):
        path = make_before(self.dir)
        add_use_cases(path)
        was = dump(path)
        real = store_module._use_cases_allow_done

        def rebuilds_then_fails(con):
            real(con)
            raise RuntimeError("forced")
        with mock.patch.object(store_module, "_use_cases_allow_done", side_effect=rebuilds_then_fails):
            with self.assertRaises(Invalid) as e:
                open_store(path, onedrive_roots=[])
        self.assertEqual(str(e.exception), store_module.MIGRATE_FAILED)
        self.assertEqual(dump(path), was)
        self.assertEqual(version(path), BEFORE)
        self.assertEqual(len(self.copies()), 1)                               # the copy stays on disk
        s = open_store(path, onedrive_roots=[])                               # and it still opens, with foreign keys on
        self.assertEqual(s.con.execute("PRAGMA foreign_keys").fetchone()[0], 1)
        s.close()
        self.assertEqual(version(path), NOW)

    def test_a_newer_file_is_refused_by_the_old_clark(self):
        """The release note's first line: once a file has taken this step, a clark from before it cannot open it."""
        path = make_before(self.dir)
        open_store(path, onedrive_roots=[]).close()
        was = dump(path)
        with mock.patch.object(store_module, "SCHEMA_VERSION", STEP - 1), \
                mock.patch.object(store_module, "MIGRATIONS", tuple(m for m in store_module.MIGRATIONS if m[0] < STEP)):
            with self.assertRaises(Invalid) as e:
                open_store(path, onedrive_roots=[])
        self.assertIn("newer clark", str(e.exception))
        self.assertEqual(dump(path), was)


class FrozenText(Base):
    def test_the_frozen_text_is_what_schema_sql_makes_today(self):
        """Pin: while this is the newest version of use_cases, the step's frozen text and schema.sql say the same."""
        def the_table(text):
            found = [st for st in store_module._statements(text) if "TABLE IF NOT EXISTS use_cases (" in st]
            self.assertEqual(len(found), 1)
            return "\n".join(l for l in found[0].splitlines() if not l.startswith("--")).strip()
        self.assertEqual(the_table(store_module.SCHEMA_USE_CASES_DONE.read_text(encoding="utf-8")),
                         the_table(store_module.SCHEMA.read_text(encoding="utf-8")))

    def test_the_frozen_text_names_the_stores_four_statuses(self):
        text = store_module.SCHEMA_USE_CASES_DONE.read_text(encoding="utf-8")
        named = re.findall(r"'([^']+)'", text.split("CHECK (status IN (")[1].split("))")[0])
        self.assertEqual(tuple(named), store_module.ALLOWED[("use_cases", "status")])
        self.assertEqual(tuple(named), NEW_STATUSES)

    def test_the_frozen_file_holds_only_the_one_table(self):
        statements = store_module._statements(store_module.SCHEMA_USE_CASES_DONE.read_text(encoding="utf-8"))
        code = ["\n".join(l for l in st.splitlines() if not l.strip().startswith("--")).strip() for st in statements]
        self.assertEqual([c.split("(")[0].strip() for c in code if c], ["CREATE TABLE IF NOT EXISTS use_cases"])

    def test_the_step_does_not_read_the_live_schema(self):
        path = make_before(self.dir)
        real = store_module.SCHEMA.read_text(encoding="utf-8")
        changed = real.replace("  updated_at    TEXT NOT NULL DEFAULT (datetime('now'))\n);\n\nCREATE TABLE IF NOT EXISTS report_sections",
                               "  updated_at    TEXT NOT NULL DEFAULT (datetime('now')),\n  later_column TEXT\n);\n\n"
                               "CREATE TABLE IF NOT EXISTS report_sections")
        self.assertNotEqual(real, changed, "the test must really change use_cases")
        fake = self.dir / "schema-later.sql"
        fake.write_text(changed, encoding="utf-8")
        with mock.patch.object(store_module, "SCHEMA", fake):
            open_store(path, onedrive_roots=[]).close()
        con = sqlite3.connect(str(path))
        names = [r[1] for r in con.execute("PRAGMA table_info(use_cases)")]
        con.close()
        self.assertNotIn("later_column", names)
        self.assertIn("'Done'", table_sql(path))

    def test_the_earlier_frozen_texts_are_not_edited(self):
        for name in ("schema_v2.sql", "schema_v6.sql", "schema_v9.sql"):
            self.assertNotIn("use_cases", (ROOT / "src" / "clark" / name).read_text(encoding="utf-8"), name)


class AfterTheStep(Base):
    def test_a_use_case_made_before_the_step_can_be_set_done_after_it_and_undone(self):
        path = make_before(self.dir)
        ucs = add_use_cases(path)
        open_store(path, onedrive_roots=[]).close()
        status, body = changes.make_change(path, [], USER)({"project": "ABC", "kind": "use_cases", "op": "update",
                                                             "id": ucs[1][0], "changes": {"status": "Done"}})
        self.assertEqual((status, body.get("ok")), (200, True), body)
        self.assertEqual(body["use_case"]["status"], "Done")
        status, back = changes.make_undo(path, [], USER)({"project": "ABC", "apply_id": body["apply_id"]})
        self.assertEqual((status, back.get("ok")), (200, True), back)
        con = sqlite3.connect(str(path))
        self.assertEqual(con.execute("SELECT status FROM use_cases WHERE id = ?", (ucs[1][0],)).fetchone()[0], "Flag")
        con.close()


if __name__ == "__main__":
    unittest.main()
