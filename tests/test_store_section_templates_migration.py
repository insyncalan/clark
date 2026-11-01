"""The migration step that lets report_sections hold the eighteen section template types (#96, the registry change that lands
first; src/clark/store.py, guarded).

The step is number 8, after the settings step (6, #47) and the sent record (7, #50): STEP below, the MIGRATIONS entry and
SCHEMA_VERSION's line in store.py are the only places it is written (the frozen text's name carries none). No entry in MIGRATIONS
is an empty step: a step that only held a number would stamp a file past a real step that never ran. The tests bring a file to
the version just before this step (and to 6 and 5, with rows in app_settings and email_sent), run the steps up to this one where
they look at this step alone, and expect the current version after a plain open. Fictional data only.

Run: python3 dev/run_tests.py test_store_section_templates_migration
"""
import ast
import inspect
import re
import shutil
import textwrap
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _demo import USER
from _paths import ROOT
from clark import backup, changes, section_kinds, store as store_module
from clark.store import Invalid, connect, migrate, open_store
from test_store_migration import make_v1, version

STEP = 8                                            # this step's number (see the docstring)
BEFORE = str(STEP - 1)                              # the version this step brings a file from
NOW = str(store_module.SCHEMA_VERSION)              # the version a plain open brings a file to (this step and any later one)
TYPES_BEFORE = ("current", "glance", "usecases", "milestones", "text", "raid", "actions", "decisions", "docs", "needs", "tracker")


def make_at(folder, level):
    """A file at `level`: a version-1 file brought up by the steps up to `level` only. The copy that bringing it up took is removed,
    so tests count only their own."""
    path = make_v1(folder)
    with mock.patch.object(store_module, "SCHEMA_VERSION", level), \
            mock.patch.object(store_module, "MIGRATIONS", tuple(m for m in store_module.MIGRATIONS if m[0] <= level)):
        open_store(path, onedrive_roots=[]).close()
    shutil.rmtree(Path(folder) / "backups", ignore_errors=True)
    assert version(path) == str(level)
    return path


def make_before(folder):
    """A file at the version just before this step. Its report_sections has the needs-and-tracker type CHECK."""
    return make_at(folder, STEP - 1)


def empty_steps(table):
    """The numbers in a migration table whose step is empty (only a docstring or pass) or is named as a placeholder."""
    found = []
    for n, f in table:
        name = f.__name__.lower()
        (fn,) = ast.parse(textwrap.dedent(inspect.getsource(f))).body
        body = [st for st in fn.body if not isinstance(st, ast.Pass)
                and not (isinstance(st, ast.Expr) and isinstance(st.value, ast.Constant))]
        if not body or any(w in name for w in ("placeholder", "held", "reserve", "noop", "no_op")):
            found.append(n)
    return found


def every_row(path):
    """Every table's rows (meta and SQLite's own tables left out), each in rowid order: what a migration must keep."""
    con = sqlite3.connect(str(path))
    try:
        names = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' "
                                           "AND name != 'meta' ORDER BY name")]
        return {n: con.execute(f'SELECT rowid, * FROM "{n}" ORDER BY rowid').fetchall() for n in names}
    finally:
        con.close()


def to_this_step(path):
    """Open `path` with the steps up to this one only (no later step), so a test sees what this step alone changes."""
    with mock.patch.object(store_module, "SCHEMA_VERSION", STEP), \
            mock.patch.object(store_module, "MIGRATIONS", tuple(m for m in store_module.MIGRATIONS if m[0] <= STEP)):
        open_store(path, onedrive_roots=[]).close()


def add_sections(path, upto=None):
    """Sections of every kind the old CHECK takes, by raw SQL: hidden, beside, a text body with markup, a needs body, a gap."""
    con = sqlite3.connect(str(path), isolation_level=None)
    rows = [("ABC-S-001", "current", "Current state", "", 0, 0, 1), ("ABC-S-002", "glance", "At a glance", "", 0, 1, 2),
            ("ABC-S-003", "usecases", "Use cases", "", 0, 0, 3), ("ABC-S-004", "milestones", "Milestones", "", 0, 0, 4),
            ("ABC-S-005", "text", "Summary", "<p>Words &amp; <b>more</b></p>", 1, 0, 5), ("ABC-S-006", "text", "This week", "", 0, 0, 6),
            ("ABC-S-007", "raid", "Risks and issues", "", 0, 1, 7), ("ABC-S-008", "actions", "Actions", "", 0, 0, 40),
            ("ABC-S-009", "decisions", "Decisions", "", 0, 0, 41), ("ABC-S-010", "docs", "Supporting documents", "", 0, 0, 42),
            ("ABC-S-011", "needs", "Needs from you", '{"rows":[]}', 0, 0, 43), ("ABC-S-012", "tracker", "Progress", "", 1, 0, 44)]
    rows = rows[:upto]
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
        """Test 10 of the design note: the table runs from 2 with no gap and ends at SCHEMA_VERSION."""
        self.assertIn((STEP, store_module.migrate_section_templates), store_module.MIGRATIONS)
        self.assertGreaterEqual(store_module.SCHEMA_VERSION, STEP)
        self.assertEqual([n for n, _ in store_module.MIGRATIONS], list(range(2, store_module.SCHEMA_VERSION + 1)))

    def test_the_number_is_written_once_in_store_py_beside_its_step_and_once_as_the_version(self):
        src = (ROOT / "src" / "clark" / "store.py").read_text(encoding="utf-8")
        self.assertEqual(re.findall(r"^SCHEMA_VERSION = (\d+)", src, re.M), [str(store_module.SCHEMA_VERSION)])
        self.assertEqual(re.findall(r"\((\d+), migrate_section_templates\)", src), [str(STEP)])
        self.assertNotIn(f"migrate_to_{STEP}", src)                    # named for what it does, not for its number
        self.assertNotRegex(store_module.REPORT_SECTIONS_WITH_TEMPLATE_TYPES.split("(")[0], r"\d")

    def test_the_steps_before_this_one_are_the_settings_step_and_the_sent_record(self):
        self.assertEqual(store_module.MIGRATIONS[-3:], ((6, store_module.migrate_settings), (7, store_module.migrate_email_sent),
                                                        (STEP, store_module.migrate_section_templates)))

    def test_no_migration_step_is_empty(self):
        """Release gate: an entry that only holds a number would stamp a file past a real step that never ran."""
        self.assertEqual(empty_steps(store_module.MIGRATIONS), [])
        funcs = [f for _, f in store_module.MIGRATIONS]
        self.assertEqual(len(set(funcs)), len(funcs), "two numbers share one step")
        self.assertNotIn("_held_for_a_step_on_another_branch", vars(store_module))

    def test_the_gate_catches_an_empty_or_placeholder_step(self):
        """The check above can fail: an empty step, a step that only passes, and one named as a placeholder are each caught."""
        def _held_open(con):
            """Does nothing."""

        def only_passes(con):
            pass

        def placeholder_step(con):
            con.execute("SELECT 1")
        table = store_module.MIGRATIONS + ((9, _held_open), (10, only_passes), (11, placeholder_step))
        self.assertEqual(empty_steps(table), [9, 10, 11])

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
    def test_a_version_7_file_keeps_every_row_in_order_and_takes_the_new_version(self):
        """Test 1: same rows, same order, same rowids, the version up, foreign keys on afterwards, no step recorded."""
        path = make_before(self.dir)
        self.assertEqual(version(path), "7")
        add_sections(path)
        before = sections_of(path)
        self.assertEqual(len(before), 12)
        s = open_store(path, onedrive_roots=[])
        try:
            self.assertEqual(sections_of(path), before)
            self.assertEqual(version(path), NOW)
            self.assertEqual(s.con.execute("PRAGMA foreign_keys").fetchone()[0], 1)
            self.assertEqual(s.con.execute("PRAGMA foreign_key_check").fetchall(), [])
            self.assertEqual(s.con.execute("SELECT count(*) FROM applies").fetchone()[0], 0)     # a migration is not a step
            self.assertEqual([r["id"] for r in s.read("report_sections", "ABC")], [r[2] for r in before])
        finally:
            s.close()

    def test_a_version_7_file_with_a_sent_record_and_ask_off_keeps_every_row(self):
        path = make_before(self.dir)
        add_sections(path)
        con = sqlite3.connect(str(path), isolation_level=None)
        con.execute("UPDATE app_settings SET ask_enabled = 0, updated_at = '2026-10-30T09:00:00Z'")
        con.execute("INSERT INTO email_sent (project, at, day, mode, by_user) VALUES ('ABC', '2026-10-30 09:00:00', '2026-10-30', 'chase', 'Sam Lee')")
        con.execute("INSERT INTO email_sent_items (seq, item_id) VALUES (1, 'ABC-A-001')")
        con.close()
        self.check_every_row_kept(path, "7")
        self.assertEqual(every_row(path)["email_sent_items"], [(1, 1, "ABC-A-001")])

    def test_a_version_6_file_with_ask_off_goes_through_the_sent_record_and_this_step_and_keeps_every_row(self):
        path = make_at(self.dir, 6)
        add_sections(path)
        con = sqlite3.connect(str(path), isolation_level=None)
        con.execute("UPDATE app_settings SET ask_enabled = 0, updated_at = '2026-10-30T09:00:00Z'")
        self.assertNotIn("email_sent", [r[0] for r in con.execute("SELECT name FROM sqlite_master")])
        con.close()
        after = self.check_every_row_kept(path, "6")
        self.assertEqual((after["email_sent"], after["email_sent_items"]), ([], []))
        self.assertEqual([r[1:3] for r in after["app_settings"]], [(1, 0)])

    def test_a_version_5_file_goes_through_the_settings_step_the_sent_record_and_this_step_and_keeps_every_row(self):
        path = make_at(self.dir, 5)
        add_sections(path)
        con = sqlite3.connect(str(path))
        self.assertNotIn("app_settings", [r[0] for r in con.execute("SELECT name FROM sqlite_master")])
        con.close()
        after = self.check_every_row_kept(path, "5")
        self.assertEqual([r[1:3] for r in after["app_settings"]], [(1, 1)])          # the settings step's one row, ask on
        self.assertEqual(after["email_sent"], [])

    def check_every_row_kept(self, path, start):
        self.assertEqual(version(path), start)
        before = every_row(path)
        self.assertEqual(len(before["report_sections"]), 12)
        self.assertTrue(before["projects"] and before["documents"])
        open_store(path, onedrive_roots=[]).close()
        self.assertEqual(version(path), NOW)
        self.assertEqual(NOW, str(STEP))
        after = every_row(path)
        self.assertEqual({t: after[t] for t in before}, before)
        self.assertIn("'onedoc'", table_sql(path))
        self.assertEqual(len(self.copies()), 1)
        return after

    def test_a_version_1_file_goes_through_every_step_and_keeps_its_sections(self):
        path = make_v1(self.dir, without=())
        self.assertEqual(sections_of(path), [], "a version-1 file starts with no sections")
        rows = add_sections(path, upto=10)                                 # a version-1 file knows no needs or tracker
        before = sections_of(path)
        self.assertEqual(len(before), len(rows))
        open_store(path, onedrive_roots=[]).close()
        self.assertEqual(sections_of(path), before)
        self.assertEqual(version(path), NOW)
        self.assertIn("'onedoc'", table_sql(path))

    def test_the_safety_copy_is_taken_first_opens_and_holds_the_old_version_and_rows(self):
        """Test 6, first half."""
        path = make_before(self.dir)
        add_sections(path)
        before = sections_of(path)
        open_store(path, onedrive_roots=[]).close()
        (copy,) = self.copies()
        self.assertEqual(version(copy), BEFORE)
        self.assertEqual(sections_of(copy), before)
        self.assertEqual(sqlite3.connect(str(copy)).execute("PRAGMA integrity_check").fetchone()[0], "ok")

    def test_a_failed_copy_refuses_the_open_and_changes_nothing(self):
        """Test 6, second half."""
        path = make_before(self.dir)
        add_sections(path)
        was = dump(path)
        with mock.patch.object(backup, "_write", side_effect=OSError("disk full")):
            with self.assertRaises(Invalid) as e:
                open_store(path, onedrive_roots=[])
        self.assertIn("Nothing was changed", str(e.exception))
        self.assertNotIn("disk full", str(e.exception))
        self.assertEqual(dump(path), was)
        self.assertEqual(version(path), BEFORE)

    def test_the_new_check_takes_every_template_type_and_refuses_anything_else_from_a_migrated_file(self):
        """Test 2, a migrated file."""
        path = make_before(self.dir)
        with self.assertRaises(sqlite3.IntegrityError):                       # before: the old check refuses a template type
            con = sqlite3.connect(str(path), isolation_level=None)
            con.execute("INSERT INTO report_sections (project, id, type, title, sort_order) VALUES ('ABC', 'ABC-S-050', 'callout', 'T', 1)")
        open_store(path, onedrive_roots=[]).close()
        self.check_the_type_check(path)

    def test_the_new_check_is_the_same_in_a_new_database(self):
        """Test 2, a new database."""
        open_store(self.dir / "clark.db", onedrive_roots=[]).close()
        self.check_the_type_check(self.dir / "clark.db")

    def check_the_type_check(self, path):
        con = sqlite3.connect(str(path), isolation_level=None)
        con.execute("PRAGMA foreign_keys = OFF")
        try:
            for n, kind in enumerate(TYPES_BEFORE + section_kinds.TYPES):
                con.execute("INSERT INTO report_sections (project, id, type, title, sort_order) VALUES ('ABC', ?, ?, 'T', ?)", (f"ABC-S-{n + 60:03d}", kind, n))
            for bad in ("template", "Callout", "callout ", "", "figures", "raidcards", "raid5", "onedoc; drop", "ONEDOC"):
                with self.assertRaises(sqlite3.IntegrityError, msg=bad):
                    con.execute("INSERT INTO report_sections (project, id, type, title, sort_order) VALUES ('ABC', 'ABC-S-099', ?, 'T', 1)", (bad,))
        finally:
            con.close()

    def test_a_migrated_file_and_a_new_database_make_the_same_table(self):
        """Test 3."""
        path = make_before(self.dir)
        open_store(path, onedrive_roots=[]).close()
        fresh = Path(tempfile.mkdtemp(dir=str(self.dir)))
        open_store(fresh / "clark.db", onedrive_roots=[]).close()
        self.assertEqual(shape(table_sql(path)), shape(table_sql(fresh / "clark.db")))
        cols = []
        for p in (path, fresh / "clark.db"):
            con = sqlite3.connect(str(p))
            cols.append(con.execute("PRAGMA table_info(report_sections)").fetchall())
            con.close()
        self.assertEqual(cols[0], cols[1])

    def test_a_second_open_changes_nothing_and_takes_no_copy(self):
        """Test 4."""
        path = make_before(self.dir)
        add_sections(path)
        open_store(path, onedrive_roots=[]).close()
        for old in self.copies():
            old.unlink()
        was = dump(path)
        open_store(path, onedrive_roots=[]).close()
        self.assertEqual(dump(path), was)
        self.assertEqual(self.copies(), [])

    def test_the_step_is_safe_to_run_twice(self):
        path = make_before(self.dir)
        add_sections(path)
        before = sections_of(path)
        con = connect(path)
        try:
            con.execute("BEGIN IMMEDIATE")
            store_module.migrate_section_templates(con)
            store_module.migrate_section_templates(con)          # the table already names every template type: nothing happens
            con.execute("COMMIT")
        finally:
            con.close()
        self.assertEqual(sections_of(path), before)

    def test_a_table_naming_only_some_template_types_is_made_again(self):
        """A partly widened table (another branch's experiment) is not taken as done: every type must be named."""
        path = make_before(self.dir)
        con = sqlite3.connect(str(path), isolation_level=None)
        con.execute("PRAGMA foreign_keys = OFF")
        con.execute("DROP TABLE report_sections")
        con.execute(store_module.REPORT_SECTIONS_WITH_CONTENT_TYPES.replace("'tracker'", "'tracker','callout'"))
        con.close()
        to_this_step(path)
        self.assertIn("'onedoc'", table_sql(path))

    def test_two_windows_opening_one_old_file_migrate_once_and_take_one_copy(self):
        """Test 7."""
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
            with mock.patch.object(store_module, "_report_sections_allow_template_types") as again:
                migrate(second)
            again.assert_not_called()
        finally:
            first.close()
            second.close()

    def test_a_failing_step_leaves_the_file_as_it_was(self):
        """Test 5: version, rows, the old table and the foreign-key setting, as they were."""
        path = make_before(self.dir)
        add_sections(path)
        was = dump(path)
        real = store_module._report_sections_allow_template_types

        def rebuilds_then_fails(con):
            real(con)
            raise RuntimeError("forced")
        with mock.patch.object(store_module, "_report_sections_allow_template_types", side_effect=rebuilds_then_fails):
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

    def test_a_new_foreign_key_problem_refuses_and_rolls_back(self):
        path = make_before(self.dir)
        add_sections(path)
        was = dump(path)

        def orphan(con):
            store_module._report_sections_allow_template_types(con)
            con.execute("INSERT INTO report_sections (project, id, type, title, sort_order) VALUES ('NOP', 'NOP-S-001', 'callout', 'T', 1)")
        table = tuple((n, orphan if n == STEP else step) for n, step in store_module.MIGRATIONS)
        with mock.patch.object(store_module, "MIGRATIONS", table):
            with self.assertRaises(Invalid) as e:
                open_store(path, onedrive_roots=[])
        self.assertEqual(str(e.exception), store_module.MIGRATE_INCONSISTENT)
        self.assertEqual(dump(path), was)


class FrozenText(Base):
    def test_the_frozen_text_is_what_schema_sql_makes_today(self):
        """Test 9. Pin: while this is the newest version of report_sections, the step's frozen text and schema.sql say the same."""
        statements = [st for st in store_module._statements(store_module.SCHEMA.read_text(encoding="utf-8"))
                      if "TABLE IF NOT EXISTS report_sections (" in st]
        self.assertEqual(len(statements), 1)

        def squash(text):
            return re.sub(r"\s+", " ", "\n".join(l.split("--")[0] for l in text.splitlines())).strip().rstrip(";")
        self.assertEqual(squash(store_module.REPORT_SECTIONS_WITH_TEMPLATE_TYPES), squash(statements[0]))

    def test_the_frozen_text_and_the_store_name_the_same_types(self):
        named = re.findall(r"'([a-z0-9]+)'", store_module.REPORT_SECTIONS_WITH_TEMPLATE_TYPES.split("CHECK (type IN (")[1].split("))")[0])
        self.assertEqual(tuple(named), store_module.SECTION_TYPES)
        self.assertEqual(tuple(w.strip("'") for w in store_module.TEMPLATE_TYPE_WORDS), section_kinds.TYPES)

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
        self.assertIn("'onedoc'", table_sql(path))

    def test_the_earlier_frozen_texts_are_not_edited(self):
        self.assertNotIn("'callout'", store_module.REPORT_SECTIONS_WITH_CONTENT_TYPES)
        text = store_module.SCHEMA_V2.read_text(encoding="utf-8")
        self.assertNotIn("'callout'", text)
        self.assertNotIn("'needs'", text)


class UndoAcrossTheStep(Base):
    def test_steps_made_before_the_step_are_undone_after_it(self):
        """Test 8: a section made, hidden, moved and deleted at the old version are each undone after the file is brought up."""
        path = make_before(self.dir)
        earlier = tuple(m for m in store_module.MIGRATIONS if m[0] < STEP)
        with mock.patch.object(store_module, "SCHEMA_VERSION", STEP - 1), mock.patch.object(store_module, "MIGRATIONS", earlier):
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
        self.assertEqual(version(path), BEFORE)
        undo = changes.make_undo(path, [], USER)
        for apply_id in (delete_step, move_step, hide_step, made_step):
            status, body = undo({"project": "ZZZ", "apply_id": apply_id})
            self.assertEqual((status, body.get("ok")), (200, True), (apply_id, body))
        self.assertEqual(version(path), NOW)
        s = open_store(path, onedrive_roots=[])
        try:
            rows = {r["id"]: r for r in s.read("report_sections", "ZZZ")}
            self.assertEqual(set(rows), set(keep))
            self.assertEqual((rows[keep[0]]["hidden"], rows[keep[1]]["sort_order"] == 500), (0, False))
        finally:
            s.close()

    def test_a_template_section_can_be_made_after_the_step_and_undone(self):
        path = make_before(self.dir)
        open_store(path, onedrive_roots=[]).close()
        s = open_store(path, onedrive_roots=[])
        try:
            with s.step("dashboard", USER) as st:
                st.create("projects", {"code": "ZZZ", "name": "Other Programme", "health": "On track"})
        finally:
            s.close()
        status, body = changes.make_change(path, [], USER)({"project": "ZZZ", "kind": "report_sections", "op": "new",
                                                             "values": {"type": "callout", "title": "Callout"}})
        self.assertEqual((status, body.get("ok")), (200, True), body)
        s = open_store(path, onedrive_roots=[])
        try:
            made = [r for r in s.read("report_sections", "ZZZ") if r["type"] == "callout"]
            self.assertEqual([(r["title"], r["body"]) for r in made], [("Callout", "")])
            last = s.con.execute("SELECT max(apply_id) FROM applies").fetchone()[0]
        finally:
            s.close()
        status, body = changes.make_undo(path, [], USER)({"project": "ZZZ", "apply_id": last})
        self.assertEqual((status, body.get("ok")), (200, True), body)
        s = open_store(path, onedrive_roots=[])
        try:
            self.assertEqual([r for r in s.read("report_sections", "ZZZ") if r["type"] == "callout"], [])
        finally:
            s.close()


if __name__ == "__main__":
    unittest.main()
