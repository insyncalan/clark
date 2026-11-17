"""Row 1264: a report made before schema step 29 still opens after it. A file at version 28 holds the built-in At a glance section with
its glance_tiles, a Report headline section and the other sections; the step takes it to 29 and changes only the type CHECK of
report_sections. Fictional data only.

Run: python3 dev/run_tests.py test_glance_template_old_report_1264
"""
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _demo import USER
from clark import publish as publish_module, store as store_module
from clark.store import Invalid, open_store
from test_store_section_templates_migration import make_at

STEP = 29
BEFORE = STEP - 1
NOW_DAY = "2026-10-28"
NO_BRAND = tempfile.mkdtemp(prefix="clark-no-brand-")

SECTIONS = [
    ("ABC-S-001", "current", "Current state", "", 0, 0, 1),
    ("ABC-S-002", "glance", "At a glance", "", 0, 0, 2),
    ("ABC-S-003", "reportheadline", "Report headline", '{"headline":"Ahead of plan","health":"on_track","sentence":"Two weeks early — café open ","v":1}', 0, 0, 3),
    ("ABC-S-004", "text", "Summary", "<p>Words &amp; <b>more</b> </p>\n", 1, 0, 5),
    ("ABC-S-005", "raid", "Risks and issues", "", 0, 1, 7),
    ("ABC-S-006", "needs", "Needs from you", '{"rows":[]}', 0, 0, 43),
    ("ABC-S-007", "textimage", " A zebra ", "", 1, 1, 44),
    ("ABC-S-008", "usecases", "Use cases", "", 0, 0, 4),
]
TILES = [("ABC", "health", 0, "G", 10), ("ABC", "overdue", 1, "", 20), ("ABC", "risks", 0, "R", 30), ("ABC", "decisions", 1, "N", 40)]
SECTION_COLUMNS = "project, id, type, title, body, beside, hidden, sort_order"


def plant(path):
    con = sqlite3.connect(str(path), isolation_level=None)
    con.executemany(f"INSERT INTO report_sections ({SECTION_COLUMNS}) VALUES ('ABC', ?, ?, ?, ?, ?, ?, ?)", SECTIONS)
    con.executemany("INSERT INTO glance_tiles (project, tile, hidden, outline, sort_order) VALUES (?, ?, ?, ?, ?)", TILES)
    con.execute("UPDATE projects SET week_ending = '2026-10-23' WHERE code = 'ABC'")
    con.close()


def everything(path, skip=("meta",)):
    con = sqlite3.connect(str(path))
    try:
        names = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        out = {}
        for n in names:
            if n in skip:
                continue
            cols = ", ".join(f'CAST("{c[1]}" AS BLOB)' for c in con.execute(f'PRAGMA table_info("{n}")'))
            out[n] = con.execute(f'SELECT {cols} FROM "{n}" ORDER BY rowid').fetchall()
        return out
    finally:
        con.close()


def other_definitions(path):
    con = sqlite3.connect(str(path))
    try:
        return con.execute("SELECT type, name, sql FROM sqlite_master WHERE name != 'report_sections' AND name NOT LIKE 'sqlite_%' ORDER BY type, name").fetchall()
    finally:
        con.close()


def stamp(path):
    con = sqlite3.connect(str(path))
    try:
        return con.execute("SELECT v FROM meta WHERE k = 'schema_version'").fetchone()[0]
    finally:
        con.close()


def open_as(path, level):
    with mock.patch.object(store_module, "SCHEMA_VERSION", level), \
            mock.patch.object(store_module, "MIGRATIONS", tuple(m for m in store_module.MIGRATIONS if m[0] <= level)):
        return open_store(path, onedrive_roots=[])


def rebuilt(old, name):
    marker = "CREATE TABLE IF NOT EXISTS report_sections ("
    return old.replace(marker, f"CREATE TABLE {name} (", 1)


def copy_into(con, select_sql="SELECT {c} FROM report_sections ORDER BY rowid", columns=SECTION_COLUMNS, definition=None):
    sql = definition or store_module.REPORT_SECTIONS_WITH_GLANCE_TEMPLATE
    con.execute(rebuilt(sql, "report_sections_mu"))
    con.execute(f"INSERT INTO report_sections_mu ({columns}) " + select_sql.format(c=columns))
    con.execute("DROP TABLE report_sections")
    con.execute("ALTER TABLE report_sections_mu RENAME TO report_sections")


def mutant_drop_a_column(con):
    cols = "project, id, type, title, body, beside, sort_order"
    copy_into(con, columns=cols)


def mutant_rewrite_a_body(con):
    copy_into(con, select_sql="SELECT project, id, type, title, upper(body), beside, hidden, sort_order FROM report_sections ORDER BY rowid")


def mutant_change_the_type_check_text(con):
    copy_into(con, definition=store_module.REPORT_SECTIONS_WITH_GLANCE_TEMPLATE.replace("'glancetemplate'", "'glancetemplat'"))


def mutant_drop_hidden_rows(con):
    copy_into(con, select_sql="SELECT {c} FROM report_sections WHERE hidden = 0 ORDER BY rowid")


def mutant_reorder_rows(con):
    copy_into(con, select_sql="SELECT {c} FROM report_sections ORDER BY title")


def mutant_empty_the_tiles(con):
    copy_into(con)
    con.execute("DELETE FROM glance_tiles")


def mutant_convert_the_built_in_glance(con):
    copy_into(con, select_sql="SELECT project, id, CASE type WHEN 'glance' THEN 'glancetemplate' ELSE type END, title, body, beside, hidden, sort_order FROM report_sections ORDER BY rowid")


def mutant_add_a_row(con):
    copy_into(con)
    con.execute("INSERT INTO report_sections (project, id, type, title, body, beside, hidden, sort_order) VALUES ('ABC', 'ABC-S-099', 'glancetemplate', 'New', '', 0, 0, 99)")


def mutant_change_a_tile(con):
    copy_into(con)
    con.execute("UPDATE glance_tiles SET outline = 'A' WHERE tile = 'health'")


def mutant_trim_a_title(con):
    copy_into(con, select_sql="SELECT project, id, type, trim(title), rtrim(body), beside, hidden, sort_order FROM report_sections ORDER BY rowid")


MUTANTS = [mutant_drop_a_column, mutant_rewrite_a_body, mutant_change_the_type_check_text, mutant_drop_hidden_rows, mutant_reorder_rows,
           mutant_empty_the_tiles, mutant_convert_the_built_in_glance, mutant_add_a_row, mutant_change_a_tile, mutant_trim_a_title]


class Checks(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="clark-test-"))
        self.addCleanup(shutil.rmtree, self.dir, True)

    def old_report(self, name):
        folder = self.dir / name
        folder.mkdir()
        path = make_at(folder, BEFORE)
        plant(path)
        return folder, path

    def migrate(self, path, step=None):
        if step is None:
            open_store(path, onedrive_roots=[]).close()
            return
        table = tuple((n, step if n == STEP else f) for n, f in store_module.MIGRATIONS)
        with mock.patch.object(store_module, "MIGRATIONS", table):
            open_store(path, onedrive_roots=[]).close()

    def run_everything(self, name, step=None):
        folder, path = self.old_report(name)
        self.assertEqual(stamp(path), str(BEFORE))
        before = everything(path)
        before_other = other_definitions(path)

        old = open_as(path, BEFORE)
        try:
            published = publish_module.publish(old, "ABC", folder, by_user=USER, now=NOW_DAY, branding=NO_BRAND)
        finally:
            old.close()
        file_before = Path(published["path"]).read_bytes()
        before = everything(path)

        with self.assertRaises(sqlite3.IntegrityError):
            con = sqlite3.connect(str(path), isolation_level=None)
            try:
                con.execute("INSERT INTO report_sections (project, id, type, title, sort_order) VALUES ('ABC', 'ABC-S-090', 'glancetemplate', 'X', 90)")
            finally:
                con.close()

        self.migrate(path, step)
        self.assertEqual(stamp(path), str(STEP))
        after = everything(path)

        self.assertEqual(sorted(after), sorted(before))
        for table in before:
            self.assertEqual(len(after[table]), len(before[table]), f"rows of {table}")
        self.assertEqual(after["report_sections"], before["report_sections"], "report_sections byte for byte, in order")
        self.assertEqual(after, before, "no other table changed")
        self.assertEqual(other_definitions(path), before_other)

        built_in = [r for r in after["report_sections"] if r[2] == b"glance"]
        self.assertEqual(len(built_in), 1)
        self.assertEqual(built_in[0][3], b"At a glance")
        self.assertEqual(after["glance_tiles"], [tuple(str(v).encode() if not isinstance(v, int) else str(v).encode() for v in t) for t in TILES])

        con = sqlite3.connect(str(path), isolation_level=None)
        try:
            con.execute("INSERT INTO report_sections (project, id, type, title, body, sort_order) VALUES ('ABC', 'ABC-S-091', 'glancetemplate', 'Glance', '', 91)")
            self.assertEqual(con.execute("SELECT type FROM report_sections WHERE id = 'ABC-S-091'").fetchone()[0], "glancetemplate")
            with self.assertRaises(sqlite3.IntegrityError):
                con.execute("INSERT INTO report_sections (project, id, type, title, sort_order) VALUES ('ABC', 'ABC-S-092', 'nosuchtype', 'X', 92)")
            con.execute("DELETE FROM report_sections WHERE id = 'ABC-S-091'")
        finally:
            con.close()
        self.assertEqual(everything(path), before)

        new = open_store(path, onedrive_roots=[])
        try:
            rebuilt_file = publish_module.build(new, "ABC", NOW_DAY, NO_BRAND, number=published["number"])["body"]
        finally:
            new.close()
        self.assertEqual(rebuilt_file, file_before, "the published file of the old report is the same bytes")

        copies = sorted((folder / "backups").glob("*-migrate.db"))
        self.assertEqual(len(copies), 1)
        one_more = everything(path)
        marker = path.stat().st_size
        open_store(path, onedrive_roots=[]).close()
        self.assertEqual(everything(path), one_more)
        self.assertEqual(stamp(path), str(STEP))
        self.assertEqual(sorted((folder / "backups").glob("*-migrate.db")), copies)
        self.assertEqual(path.stat().st_size, marker)
        return path


class OldReportOpens(Checks):
    def test_an_old_report_opens_after_step_29_and_loses_nothing(self):
        self.run_everything("a")

    def test_the_step_is_the_last_one_and_is_numbered_29(self):
        self.assertEqual(store_module.SCHEMA_VERSION, STEP)
        self.assertEqual(store_module.MIGRATIONS[-1][0], STEP)
        self.assertIs(store_module.MIGRATIONS[-1][1], store_module.migrate_glance_template_section_type)

    def test_a_29_file_opened_by_the_step_28_check_is_refused_in_the_same_words_as_any_newer_file(self):
        path = self.run_everything("b")
        before = everything(path, skip=())
        with self.assertRaises(Invalid) as caught:
            open_as(path, BEFORE)
        self.assertEqual(str(caught.exception), store_module.NEWER_DATA)
        self.assertTrue(str(caught.exception).startswith("This data needs a newer clark."))
        self.assertEqual(everything(path, skip=()), before)
        self.assertEqual(stamp(path), str(STEP))

        other = self.dir / "c"
        other.mkdir()
        newer = make_at(other, BEFORE)
        con = sqlite3.connect(str(newer), isolation_level=None)
        con.execute("UPDATE meta SET v = ? WHERE k = 'schema_version'", (str(STEP + 1),))
        con.close()
        with self.assertRaises(Invalid) as same:
            open_store(newer, onedrive_roots=[])
        self.assertEqual(str(same.exception), str(caught.exception))


class MutantsOfTheStep(Checks):
    def test_the_unmutated_step_passes_the_same_checks(self):
        self.run_everything("plain")

    def test_every_mutant_of_the_step_fails_the_checks(self):
        self.assertGreaterEqual(len(MUTANTS), 4)
        for n, mutant in enumerate(MUTANTS):
            with self.subTest(mutant=mutant.__name__):
                with self.assertRaises((AssertionError, sqlite3.Error, Invalid)):
                    self.run_everything(f"m{n}", step=mutant)


if __name__ == "__main__":
    unittest.main()
