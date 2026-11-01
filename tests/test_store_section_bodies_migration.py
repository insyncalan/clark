"""The migration step that lets report_sections hold the types 'needs' and 'tracker' (the shared base for 'Needs from you' and
'Progress tracker'; src/clark/store.py, guarded).

The step is number 4, after Word's 3 and before the history offset's 5 (#123). Its number is written as a literal in MIGRATIONS; a
step that lands before it renumbers it (there and in STEP below). The tests bring a file to the version just before this step, run
the steps up to this one where they look at this step alone, and expect the current version after a plain open.

Run: python3 dev/run_tests.py test_store_section_bodies_migration
"""
import re
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _demo import USER, DemoStore
from _paths import ROOT
from clark import backup, changes, store as store_module
from clark.store import Invalid, connect, migrate, open_store
from test_store_migration import make_v1, version

STEP = 4                                            # this step's number
BEFORE = str(STEP - 1)                              # the version this step brings a file from
NOW = str(store_module.SCHEMA_VERSION)              # the version a plain open brings a file to (this step and any later one)
TYPES_BEFORE = ("current", "glance", "usecases", "milestones", "text", "raid", "actions", "decisions", "docs")


def make_before(folder):
    """A file at the version just before this step: a version-1 file brought up by the earlier steps only. Its report_sections
    has the old type CHECK. The copy that bringing it up took is removed, so tests count only their own."""
    path = make_v1(folder)
    earlier = tuple(m for m in store_module.MIGRATIONS if m[0] < STEP)
    with mock.patch.object(store_module, "SCHEMA_VERSION", STEP - 1), \
            mock.patch.object(store_module, "MIGRATIONS", earlier):
        open_store(path, onedrive_roots=[]).close()
    shutil.rmtree(Path(folder) / "backups", ignore_errors=True)
    assert version(path) == BEFORE
    return path


def to_this_step(path):
    """Open `path` with the steps up to this one only (no later step), so a test sees what this step alone changes."""
    with mock.patch.object(store_module, "SCHEMA_VERSION", STEP), \
            mock.patch.object(store_module, "MIGRATIONS", tuple(m for m in store_module.MIGRATIONS if m[0] <= STEP)):
        open_store(path, onedrive_roots=[]).close()


def add_sections(path):
    """Sections of every kind, by raw SQL (the old CHECK): hidden, beside, a text body with markup, a gap in the order."""
    con = sqlite3.connect(str(path), isolation_level=None)
    rows = [("ABC-S-001", "current", "Current state", "", 0, 0, 1), ("ABC-S-002", "glance", "At a glance", "", 0, 1, 2),
            ("ABC-S-003", "usecases", "Use cases", "", 0, 0, 3), ("ABC-S-004", "milestones", "Milestones", "", 0, 0, 4),
            ("ABC-S-005", "text", "Summary", "<p>Words &amp; <b>more</b></p>", 1, 0, 5), ("ABC-S-006", "text", "This week", "", 0, 0, 6),
            ("ABC-S-007", "raid", "Risks and issues", "", 0, 1, 7), ("ABC-S-008", "actions", "Actions", "", 0, 0, 40),
            ("ABC-S-009", "decisions", "Decisions", "", 0, 0, 41), ("ABC-S-010", "docs", "Supporting documents", "", 0, 0, 42)]
    con.executemany("INSERT INTO report_sections (project, id, type, title, body, beside, hidden, sort_order) "
                    "VALUES ('ABC', ?, ?, ?, ?, ?, ?, ?)", rows)
    con.close()
    return rows


def sections_of(path):
    con = sqlite3.connect(str(path))
    try:
        return con.execute("SELECT rowid, project, id, type, title, body, beside, hidden, sort_order FROM report_sections ORDER BY rowid").fetchall()
    finally:
        con.close()


def table_sql(path):
    con = sqlite3.connect(str(path))
    try:
        return con.execute("SELECT sql FROM sqlite_master WHERE name = 'report_sections'").fetchone()[0]
    finally:
        con.close()


def shape(sql):
    """The definition of the table without its name or quoting: what must be the same in a migrated file and a new one."""
    return re.sub(r'["\s]', "", sql[sql.index("("):])


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="clark-test-"))
        self.addCleanup(shutil.rmtree, self.dir, True)

    def copies(self):
        return sorted((self.dir / "backups").glob("*-migrate.db")) if (self.dir / "backups").exists() else []


class TheNumber(Base):
    def test_the_step_is_number_4_and_the_version_is_4(self):
        self.assertIn((4, store_module.migrate_section_bodies), store_module.MIGRATIONS)
        self.assertEqual(STEP, 4)                                # both written out: a step that lands first renumbers this one, on purpose, in both places
        self.assertGreaterEqual(store_module.SCHEMA_VERSION, STEP)
        self.assertEqual([n for n, _ in store_module.MIGRATIONS], list(range(2, store_module.SCHEMA_VERSION + 1)))

    def test_the_step_is_named_for_what_it_does_not_for_its_number(self):
        src = (ROOT / "src" / "clark" / "store.py").read_text(encoding="utf-8")
        self.assertNotIn("migrate_to_4", src)
        self.assertEqual(len(re.findall(r"^SCHEMA_VERSION = ", src, re.M)), 1)

    def test_the_step_changes_no_other_table(self):
        path = make_before(self.dir)
        con = sqlite3.connect(str(path))
        before = {r[0]: r[1] for r in con.execute("SELECT name, sql FROM sqlite_master WHERE name != 'report_sections' AND name NOT LIKE 'sqlite_%'")}
        con.close()
        to_this_step(path)
        con = sqlite3.connect(str(path))
        after = {r[0]: r[1] for r in con.execute("SELECT name, sql FROM sqlite_master WHERE name != 'report_sections' AND name NOT LIKE 'sqlite_%'")}
        con.close()
        self.assertEqual(after, before)


class Migrating(Base):
    def test_a_file_before_the_step_keeps_every_row_in_order_and_takes_the_new_version(self):
        path = make_before(self.dir)
        add_sections(path)
        before = sections_of(path)
        self.assertEqual(len(before), 10)
        s = open_store(path, onedrive_roots=[])
        try:
            self.assertEqual(sections_of(path), before)                       # the same rows, the same order, the same rowids
            self.assertEqual(version(path), NOW)
            self.assertEqual(s.con.execute("PRAGMA foreign_keys").fetchone()[0], 1)
            self.assertEqual(s.con.execute("PRAGMA foreign_key_check").fetchall(), [])
            self.assertEqual(s.con.execute("SELECT count(*) FROM applies").fetchone()[0], 0)     # a migration is not a step
            self.assertEqual([r["id"] for r in s.read("report_sections", "ABC")], [r[2] for r in before])
        finally:
            s.close()

    def test_a_version_1_file_goes_through_every_step_and_keeps_its_sections(self):
        path = make_v1(self.dir, without=())
        con = sqlite3.connect(str(path), isolation_level=None)
        con.execute("DELETE FROM report_sections")
        con.close()
        add_sections(path)
        before = sections_of(path)
        open_store(path, onedrive_roots=[]).close()
        self.assertEqual(sections_of(path), before)
        self.assertEqual(version(path), NOW)

    def test_the_safety_copy_is_taken_first_opens_and_holds_the_old_version_and_rows(self):
        path = make_before(self.dir)
        add_sections(path)
        before = sections_of(path)
        open_store(path, onedrive_roots=[]).close()
        (copy,) = self.copies()
        self.assertEqual(version(copy), BEFORE)
        self.assertEqual(sections_of(copy), before)
        self.assertEqual(sqlite3.connect(str(copy)).execute("PRAGMA integrity_check").fetchone()[0], "ok")

    def test_the_new_type_check_takes_needs_and_tracker_and_refuses_anything_else_from_a_migrated_file(self):
        path = make_before(self.dir)
        with self.assertRaises(sqlite3.IntegrityError):                       # before: the old check refuses it
            con = sqlite3.connect(str(path), isolation_level=None)
            con.execute("INSERT INTO report_sections (project, id, type, title, sort_order) VALUES ('ABC', 'ABC-S-050', 'needs', 'T', 1)")
        open_store(path, onedrive_roots=[]).close()
        self.check_the_type_check(path)

    def test_the_new_type_check_is_the_same_in_a_new_database(self):
        open_store(self.dir / "clark.db", onedrive_roots=[]).close()
        self.check_the_type_check(self.dir / "clark.db", project=False)

    def check_the_type_check(self, path, project=True):
        con = sqlite3.connect(str(path), isolation_level=None)
        con.execute("PRAGMA foreign_keys = OFF")
        try:
            for n, kind in enumerate(TYPES_BEFORE + ("needs", "tracker")):
                con.execute("INSERT INTO report_sections (project, id, type, title, sort_order) VALUES ('ABC', ?, ?, 'T', ?)", (f"ABC-S-{n + 60:03d}", kind, n))
            for bad in ("template", "Needs", "needs ", "", "tracker; drop", "NEEDS"):
                with self.assertRaises(sqlite3.IntegrityError, msg=bad):
                    con.execute("INSERT INTO report_sections (project, id, type, title, sort_order) VALUES ('ABC', 'ABC-S-099', ?, 'T', 1)", (bad,))
        finally:
            con.close()

    def test_a_migrated_file_and_a_new_database_make_the_same_table(self):
        path = make_before(self.dir)
        open_store(path, onedrive_roots=[]).close()
        fresh = Path(tempfile.mkdtemp(dir=str(self.dir)))
        open_store(fresh / "clark.db", onedrive_roots=[]).close()
        self.assertEqual(shape(table_sql(path)), shape(table_sql(fresh / "clark.db")))
        columns = []
        for p in (path, fresh / "clark.db"):
            con = sqlite3.connect(str(p))
            columns.append(con.execute("PRAGMA table_info(report_sections)").fetchall())
            con.close()
        self.assertEqual(columns[0], columns[1])

    def test_a_second_open_changes_nothing_and_takes_no_copy(self):
        path = make_before(self.dir)
        add_sections(path)
        open_store(path, onedrive_roots=[]).close()
        for old in self.copies():
            old.unlink()
        con = sqlite3.connect(str(path))
        dump = list(con.iterdump())
        con.close()
        open_store(path, onedrive_roots=[]).close()
        con = sqlite3.connect(str(path))
        self.assertEqual(list(con.iterdump()), dump)
        con.close()
        self.assertEqual(self.copies(), [])

    def test_the_step_is_safe_to_run_twice(self):
        path = make_before(self.dir)
        add_sections(path)
        before = sections_of(path)
        con = connect(path)
        try:
            con.execute("BEGIN IMMEDIATE")
            store_module.migrate_section_bodies(con)
            store_module.migrate_section_bodies(con)          # the table already names 'needs': nothing happens
            con.execute("COMMIT")
        finally:
            con.close()
        self.assertEqual(sections_of(path), before)

    def test_two_windows_opening_one_old_file_migrate_once_and_take_one_copy(self):
        path = make_before(self.dir)
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
            with mock.patch.object(store_module, "_report_sections_allow_content_types") as again:
                migrate(second)
            again.assert_not_called()
        finally:
            first.close()
            second.close()

    def test_a_failing_step_leaves_the_file_as_it_was(self):
        path = make_before(self.dir)
        add_sections(path)
        con = sqlite3.connect(str(path))
        dump = list(con.iterdump())
        con.close()
        real = store_module._report_sections_allow_content_types

        def rebuilds_then_fails(con):
            real(con)
            raise RuntimeError("forced")
        with mock.patch.object(store_module, "_report_sections_allow_content_types", side_effect=rebuilds_then_fails):
            with self.assertRaises(Invalid) as e:
                open_store(path, onedrive_roots=[])
        self.assertEqual(str(e.exception), store_module.MIGRATE_FAILED)
        con = sqlite3.connect(str(path))
        self.assertEqual(list(con.iterdump()), dump)                          # version, rows and the old table, as they were
        con.close()
        self.assertEqual(version(path), BEFORE)
        self.assertEqual(len(self.copies()), 1)                               # the copy stays on disk
        s = open_store(path, onedrive_roots=[])                               # and it still opens, with foreign keys on
        self.assertEqual(s.con.execute("PRAGMA foreign_keys").fetchone()[0], 1)
        s.close()
        self.assertEqual(version(path), NOW)

    def test_a_failed_copy_refuses_the_open_and_changes_nothing(self):
        path = make_before(self.dir)
        add_sections(path)
        con = sqlite3.connect(str(path))
        dump = list(con.iterdump())
        con.close()
        with mock.patch.object(backup, "_write", side_effect=OSError("disk full")):
            with self.assertRaises(Invalid) as e:
                open_store(path, onedrive_roots=[])
        self.assertIn("Nothing was changed", str(e.exception))
        self.assertNotIn("disk full", str(e.exception))
        con = sqlite3.connect(str(path))
        self.assertEqual(list(con.iterdump()), dump)
        con.close()
        self.assertEqual(version(path), BEFORE)

    def test_a_new_foreign_key_problem_refuses_and_rolls_back(self):
        path = make_before(self.dir)
        add_sections(path)
        con = sqlite3.connect(str(path))
        dump = list(con.iterdump())
        con.close()

        def orphan(con):
            store_module._report_sections_allow_content_types(con)
            con.execute("INSERT INTO report_sections (project, id, type, title, sort_order) VALUES ('NOP', 'NOP-S-001', 'text', 'T', 1)")
        table = tuple((n, orphan if n == STEP else step) for n, step in store_module.MIGRATIONS)
        with mock.patch.object(store_module, "MIGRATIONS", table):
            with self.assertRaises(Invalid) as e:
                open_store(path, onedrive_roots=[])
        self.assertEqual(str(e.exception), store_module.MIGRATE_INCONSISTENT)
        con = sqlite3.connect(str(path))
        self.assertEqual(list(con.iterdump()), dump)
        con.close()


class FrozenText(Base):
    def test_the_frozen_text_is_the_later_steps_text_without_the_template_types(self):
        """Pin: this step's frozen text names the eleven types, and is otherwise what the later section templates step (#96) makes,
        which tests/test_store_section_templates_migration.py pins to schema.sql. A later change to report_sections is a later
        step with its own frozen text; this one never changes."""
        def squash(text):
            return re.sub(r"\s+", " ", "\n".join(l.split("--")[0] for l in text.splitlines())).strip().rstrip(";")

        def types_and_rest(text):
            text = squash(text)
            m = re.search(r"CHECK \(type IN \(([^)]*)\)\)", text)
            return [t.strip().strip("'") for t in m.group(1).split(",")], text[:m.start()] + text[m.end():]
        mine, rest = types_and_rest(store_module.REPORT_SECTIONS_WITH_CONTENT_TYPES)
        later, later_rest = types_and_rest(store_module.REPORT_SECTIONS_WITH_TEMPLATE_TYPES)
        self.assertEqual(mine, list(TYPES_BEFORE) + ["needs", "tracker"])
        self.assertEqual(later[:len(mine)], mine)
        self.assertEqual(rest, later_rest)

    def test_the_step_does_not_read_the_live_schema(self):
        path = make_before(self.dir)
        real = store_module.SCHEMA.read_text(encoding="utf-8")
        changed = real.replace("  sort_order INTEGER NOT NULL,\n  PRIMARY KEY (project, id)\n);\n\nCREATE TABLE IF NOT EXISTS glance_tiles",
                               "  later_column TEXT,\n  sort_order INTEGER NOT NULL,\n  PRIMARY KEY (project, id)\n);\n\nCREATE TABLE IF NOT EXISTS glance_tiles")
        self.assertNotEqual(real, changed, "the test must really change report_sections")
        fake = self.dir / "schema-later.sql"
        fake.write_text(changed, encoding="utf-8")
        with mock.patch.object(store_module, "SCHEMA", fake):
            open_store(path, onedrive_roots=[]).close()
        con = sqlite3.connect(str(path))
        names = [r[1] for r in con.execute("PRAGMA table_info(report_sections)")]
        con.close()
        self.assertNotIn("later_column", names)

    def test_the_frozen_version_2_file_is_not_edited(self):
        text = store_module.SCHEMA_V2.read_text(encoding="utf-8")
        self.assertNotIn("'needs'", text)
        self.assertNotIn("'tracker'", text)
        self.assertIn("'docs')),", text)


class UndoAcrossTheStep(Base):
    def test_steps_made_before_the_step_are_undone_after_it(self):
        """A section made, hidden, moved and deleted at the old version are each undone after the file is brought up."""
        path = make_before(self.dir)
        con = sqlite3.connect(str(path), isolation_level=None)       # the writer records the offset (#123, a later step); an older clark
        con.execute("ALTER TABLE applies ADD COLUMN utc_offset TEXT")   # wrote these steps without it, so the column is added for it here
        con.close()
        with mock.patch.object(store_module, "SCHEMA_VERSION", STEP - 1), \
                mock.patch.object(store_module, "MIGRATIONS", tuple(m for m in store_module.MIGRATIONS if m[0] < STEP)):
            s = open_store(path, onedrive_roots=[])
            with s.step("dashboard", USER) as st:
                st.create("projects", {"code": "ZZZ", "name": "Other Programme", "health": "On track"})
            keep = [r["id"] for r in s.read("report_sections", "ZZZ")]
            with s.step("dashboard", USER) as st:
                made = st.create("report_sections", {"project": "ZZZ", "type": "text", "title": "Notes", "sort_order": 99})
            made_step = s.con.execute("SELECT max(apply_id) FROM applies").fetchone()[0]
            with s.step("dashboard", USER) as st:
                st.update("report_sections", keep[0], {"hidden": 1})
            hide_step = s.con.execute("SELECT max(apply_id) FROM applies").fetchone()[0]
            with s.step("dashboard", USER) as st:
                st.update("report_sections", keep[1], {"sort_order": 500})
            move_step = s.con.execute("SELECT max(apply_id) FROM applies").fetchone()[0]
            with s.step("dashboard", USER) as st:
                st.cancel("report_sections", made)
            delete_step = s.con.execute("SELECT max(apply_id) FROM applies").fetchone()[0]
            s.close()
        con = sqlite3.connect(str(path))
        con.execute("UPDATE meta SET v = ? WHERE k = 'schema_version'", (BEFORE,))
        con.commit()
        con.close()
        undo = changes.make_undo(path, [], USER)
        for apply_id in (delete_step, move_step, hide_step, made_step):
            status, body = undo({"project": "ZZZ", "apply_id": apply_id})
            self.assertEqual((status, body.get("ok")), (200, True), (apply_id, body))
        self.assertEqual(version(path), NOW)
        s = open_store(path, onedrive_roots=[])
        try:
            rows = {r["id"]: r for r in s.read("report_sections", "ZZZ")}
            self.assertEqual(set(rows), set(keep))                                   # the section made, then deleted, then put back, then un-made
            self.assertEqual((rows[keep[0]]["hidden"], rows[keep[1]]["sort_order"] == 500), (0, False))
        finally:
            s.close()


class OtherBranchesDatabase(Base):
    def test_a_file_at_this_version_without_this_step_refuses_a_new_type_in_plain_words(self):
        """A development database migrated by another branch's step with the same number reports this version but still has the
        old type check. The first write of a new type is a plain refusal, never a crash."""
        path = make_before(self.dir)
        con = sqlite3.connect(str(path), isolation_level=None)
        con.execute("UPDATE meta SET v = ? WHERE k = 'schema_version'", (str(STEP),))
        con.close()
        # #96's later step makes the table again (which mends such a file), so this test runs with every step but that one
        without_rebuilds = tuple((n, (lambda con: None) if f is store_module.migrate_section_templates else f)     # same numbers: no gap
                                 for n, f in store_module.MIGRATIONS)
        with mock.patch.object(store_module, "SCHEMA_VERSION", without_rebuilds[-1][0]), \
                mock.patch.object(store_module, "MIGRATIONS", without_rebuilds):
            s = open_store(path, onedrive_roots=[])                   # any later step still runs; this one is skipped
            try:
                self.assertEqual(version(path), str(without_rebuilds[-1][0]))
                self.assertNotIn("'needs'", table_sql(path))
                with s.step("dashboard", USER) as st:
                    st.create("projects", {"code": "ZZZ", "name": "Other Programme", "health": "On track"})
            finally:
                s.close()
            before = sections_of(path)
            with self.assertRaises(sqlite3.IntegrityError):           # not caught by changes: the server answers it with its own 500, in plain words, no class and no text
                changes.make_change(path, [], USER)({"project": "ZZZ", "kind": "report_sections", "op": "new", "values": {"type": "needs", "title": "Needs"}})
            self.assertEqual(sections_of(path), before)               # nothing was written
        from clark import server
        self.assertEqual(server.MESSAGES["server_error"], "Something went wrong, and nothing was changed. Try again, or restart clark.")
