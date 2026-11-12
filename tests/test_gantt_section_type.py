"""Row 926: the Gantt section type, end to end (schema layout 19; store.py, schema.sql, changes.py, publish.py: guarded). Fictional data only.

Pinned here: migration step 19 makes report_sections again with 'gantt' in its type CHECK (backup first, rows kept in order, a second run
changes nothing, an older clark refuses layout 19, a new database equals a migrated one); a Gantt section is added, moved, hidden and
deleted through the change route with one Undo each, and takes no body; the published file carries the section (id, type, title, beside
and nothing else) only when the Gantt tab is in it, and no eye-off line reaches the file through it; the Word and Excel paths leave it out.

Run: python3 dev/run_tests.py test_gantt_section_type
"""
import json
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _demo import USER, DemoStore
from _paths import SRC  # noqa: F401
from clark import changes, publish, store as store_module
from clark.store import Invalid, open_store
from test_gantt_migration import dump
from test_store_migration import version
from test_store_use_case_done_migration import make_at

STEP = 19
SECRET = "ZQ-EYE-OFF-LINE"


def sections_sql(path):
    con = sqlite3.connect(str(path))
    try:
        return con.execute("SELECT sql FROM sqlite_master WHERE name = 'report_sections'").fetchone()[0]
    finally:
        con.close()


def section_rows(path):
    con = sqlite3.connect(str(path))
    try:
        return con.execute("SELECT rowid, project, id, type, title, body, beside, hidden, sort_order FROM report_sections ORDER BY rowid").fetchall()
    finally:
        con.close()


class Migrating(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="clark-test-"))
        self.addCleanup(shutil.rmtree, self.dir, True)

    def copies(self):
        return sorted((self.dir / "backups").glob("*-migrate.db")) if (self.dir / "backups").exists() else []

    def old_file(self):
        path = make_at(self.dir, STEP - 1)
        con = sqlite3.connect(str(path), isolation_level=None)
        con.executemany("INSERT INTO report_sections (project, id, type, title, body, beside, hidden, sort_order) VALUES ('ABC', ?, ?, ?, ?, ?, ?, ?)",
                        [("ABC-S-001", "text", "Summary", "<p>Hello</p>", 0, 0, 1), ("ABC-S-002", "callout", "Note", "", 1, 0, 2),
                         ("ABC-S-003", "needs", "Needs from you", "", 0, 1, 3)])
        con.close()
        return path

    def test_the_step_is_at_its_number_and_the_literal_and_the_table_agree(self):
        self.assertIn((STEP, store_module.migrate_gantt_section_type), store_module.MIGRATIONS)
        self.assertGreaterEqual(store_module.SCHEMA_VERSION, STEP)      # #944 T1: no longer the latest layout; test_v060 and test_gantt_migration pin the latest
        self.assertIn(STEP, [n for n, _ in store_module.MIGRATIONS])      # #944 T1: as above

    def test_a_layout_18_file_opens_with_the_new_check_and_every_row_kept_in_order(self):
        path = self.old_file()
        self.assertNotIn("'gantt'", sections_sql(path))
        before = section_rows(path)
        s = open_store(path, onedrive_roots=[])
        try:
            self.assertEqual(version(path), "22")
            self.assertEqual(s.con.execute("PRAGMA foreign_key_check").fetchall(), [])
            self.assertEqual(s.con.execute("SELECT count(*) FROM applies").fetchone()[0], 0)     # a migration is not a step: no Undo
            s.con.execute("INSERT INTO report_sections (project, id, type, title, sort_order) VALUES ('ABC', 'ABC-S-009', 'gantt', 'Gantt', 9)")
        finally:
            s.close()
        self.assertIn("'gantt'", sections_sql(path))
        self.assertEqual(section_rows(path)[:3], before)

    def test_a_safety_copy_is_taken_first_and_it_is_the_old_layout(self):
        path = self.old_file()
        open_store(path, onedrive_roots=[]).close()
        copies = self.copies()
        self.assertEqual(len(copies), 1)
        self.assertEqual(version(copies[0]), str(STEP - 1))
        self.assertNotIn("'gantt'", sections_sql(copies[0]))

    def test_a_second_open_changes_nothing_and_takes_no_copy(self):
        path = self.old_file()
        open_store(path, onedrive_roots=[]).close()
        was, copies = dump(path), self.copies()
        open_store(path, onedrive_roots=[]).close()
        self.assertEqual(dump(path), was)
        self.assertEqual(self.copies(), copies)

    def test_the_step_run_twice_does_nothing_the_second_time(self):
        path = self.old_file()
        con = sqlite3.connect(str(path), isolation_level=None)
        store_module.migrate_gantt_section_type(con)
        was = sections_sql(path), section_rows(path)
        store_module.migrate_gantt_section_type(con)
        con.close()
        self.assertEqual((sections_sql(path), section_rows(path)), was)

    def test_an_older_clark_refuses_the_migrated_file_and_changes_nothing(self):
        path = self.old_file()
        open_store(path, onedrive_roots=[]).close()
        was, copies = dump(path), self.copies()
        with mock.patch.object(store_module, "SCHEMA_VERSION", STEP - 1), \
                mock.patch.object(store_module, "MIGRATIONS", tuple(m for m in store_module.MIGRATIONS if m[0] < STEP)):
            with self.assertRaises(Invalid) as e:
                open_store(path, onedrive_roots=[])
        self.assertEqual(str(e.exception), store_module.NEWER_DATA)
        self.assertEqual(dump(path), was)
        self.assertEqual(self.copies(), copies)

    def test_a_brought_up_file_and_a_new_file_make_the_same_table(self):
        path = self.old_file()
        open_store(path, onedrive_roots=[]).close()
        fresh = self.dir / "fresh"
        fresh.mkdir()
        new = fresh / "clark.db"
        open_store(new, onedrive_roots=[]).close()

        def squash(text):
            return " ".join("\n".join(l.split("--")[0] for l in text.splitlines()).replace('"', "").replace("report_sections_gantt", "report_sections").replace("IF NOT EXISTS ", "").split())
        self.assertEqual(squash(sections_sql(path)), squash(sections_sql(new)))
        self.assertEqual(squash(store_module.REPORT_SECTIONS_WITH_GANTT), squash(sections_sql(new)))

    def test_a_failure_after_the_rebuild_rolls_back_and_the_next_open_migrates(self):
        path = self.old_file()
        was = dump(path)
        real = store_module.migrate_gantt_section_type

        def then_fail(con):
            real(con)
            raise sqlite3.OperationalError("disk I/O error")
        with mock.patch.object(store_module, "MIGRATIONS", tuple((n, then_fail if n == STEP else f) for n, f in store_module.MIGRATIONS)):
            with self.assertRaises(Invalid):
                open_store(path, onedrive_roots=[])
        self.assertEqual(dump(path), was)
        open_store(path, onedrive_roots=[]).close()
        self.assertEqual(version(path), "22")

    def test_a_layout_17_file_is_brought_to_19_with_the_copy_first_every_row_kept_idempotent_and_refused_by_an_older_clark(self):
        """In-clark update across both Gantt steps (18 then 19) in one open."""
        path = make_at(self.dir, 17)
        con = sqlite3.connect(str(path), isolation_level=None)
        con.executemany("INSERT INTO report_sections (project, id, type, title, body, beside, hidden, sort_order) VALUES ('ABC', ?, ?, ?, ?, ?, ?, ?)",
                        [("ABC-S-001", "text", "Summary", "<p>Hello</p>", 0, 0, 1), ("ABC-S-002", "quote", "Quote", "", 1, 0, 2),
                         ("ABC-S-003", "tracker", "Progress", "", 0, 1, 3)])
        con.execute("INSERT INTO milestones (id, project, name, source) VALUES ('ABC-M-001', 'ABC', 'Pilot live', 'test')")
        con.close()
        self.assertEqual(version(path), "17")
        self.assertNotIn("gantt_lines", {r[0] for r in sqlite3.connect(str(path)).execute("SELECT name FROM sqlite_master")})
        before = section_rows(path)
        s = open_store(path, onedrive_roots=[])
        try:
            self.assertEqual(version(path), "22")
            self.assertEqual(s.con.execute("PRAGMA foreign_key_check").fetchall(), [])
            self.assertEqual(s.con.execute("SELECT count(*) FROM gantt_lines").fetchone()[0], 0)
            self.assertEqual(s.read("projects", ref="ABC")["gantt_tab_name"], "Gantt")
            self.assertEqual(s.con.execute("SELECT count(*) FROM milestones").fetchone()[0], 1)
            self.assertEqual(s.con.execute("SELECT count(*) FROM applies").fetchone()[0], 0)
        finally:
            s.close()
        self.assertIn("'gantt'", sections_sql(path))
        self.assertEqual(section_rows(path), before)
        copies = self.copies()
        self.assertEqual(len(copies), 1, "one copy, taken before the steps")
        self.assertEqual(version(copies[0]), "17")
        self.assertNotIn("'gantt'", sections_sql(copies[0]))
        was = dump(path)
        open_store(path, onedrive_roots=[]).close()
        self.assertEqual((dump(path), self.copies()), (was, copies), "a second open changes nothing and takes no copy")
        with mock.patch.object(store_module, "SCHEMA_VERSION", 18), \
                mock.patch.object(store_module, "MIGRATIONS", tuple(m for m in store_module.MIGRATIONS if m[0] <= 18)):
            with self.assertRaises(Invalid) as e:
                open_store(path, onedrive_roots=[])
        self.assertEqual(str(e.exception), store_module.NEWER_DATA)
        self.assertEqual(dump(path), was)

    def test_the_type_check_refuses_an_unknown_type_and_takes_gantt(self):
        with DemoStore() as demo:
            con = demo.con
            con.execute("INSERT INTO report_sections (project, id, type, title, sort_order) VALUES ('ABC', 'ABC-S-090', 'gantt', 'Gantt', 90)")
            with self.assertRaises(sqlite3.IntegrityError):
                con.execute("INSERT INTO report_sections (project, id, type, title, sort_order) VALUES ('ABC', 'ABC-S-091', 'gantt2', 'X', 91)")


class Base(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store
        self.change = changes.make_change(self.s.path, [], USER)
        self.undo = changes.make_undo(self.s.path, [], USER)

    def go(self, kind="report_sections", **req):
        return self.change({"project": "ABC", "kind": kind, **req})

    def ok(self, **req):
        status, body = self.go(**req)
        self.assertEqual((status, body.get("message")), (200, None), body)
        return body

    def sections(self):
        return self.s.read("report_sections", "ABC")

    def undo_step(self, apply_id):
        status, body = self.undo({"project": "ABC", "apply_id": apply_id})
        self.assertEqual(status, 200, body)
        return body

    def add_gantt(self, **more):
        return self.ok(op="new", values={"type": "gantt", "title": "Gantt"}, **more)


class TheChangeRoute(Base):
    def test_the_allow_list_names_gantt_and_the_store_lists_it_once(self):
        self.assertIn("gantt", changes.NEW_SECTION_TYPES)
        self.assertEqual(store_module.SECTION_TYPES.count("gantt"), 1)
        self.assertIn("gantt", store_module.DELETABLE_TYPES)
        self.assertNotIn("gantt", store_module.BODY_TYPES)

    def test_a_gantt_section_is_added_with_one_undo_and_the_undo_takes_it_away(self):
        before = [s["id"] for s in self.sections()]
        body = self.add_gantt()
        added = [s for s in self.sections() if s["id"] not in before]
        self.assertEqual([(s["type"], s["title"], s["body"]) for s in added], [("gantt", "Gantt", "")])
        self.undo_step(body["apply_id"])
        self.assertEqual([s["id"] for s in self.sections()], before)

    def test_a_body_is_refused_on_a_new_gantt_section_and_on_an_update(self):
        n = len(self.sections())
        status, body = self.go(op="new", values={"type": "gantt", "title": "Gantt", "body": "x"})
        self.assertEqual((status, body["message"]), (400, changes.NO_BODY_HERE))
        self.assertEqual(len(self.sections()), n)
        ref = self.add_gantt()["ref"]
        for req in ({"op": "update", "id": ref, "changes": {"body": "x"}},):
            status, body = self.go(**req)
            self.assertEqual((status, body["message"]), (400, changes.NO_BODY_HERE))
        self.assertEqual(self.s.read("report_sections", "ABC", ref=ref)["body"], "")

    def test_a_gantt_section_can_be_retitled_hidden_moved_and_deleted_each_with_one_undo(self):
        first = self.sections()[0]["id"]
        ref = self.add_gantt()["ref"]
        for req, check in (({"op": "update", "id": ref, "changes": {"title": "Plan"}}, lambda: self.s.read("report_sections", "ABC", ref=ref)["title"]),
                           ({"op": "update", "id": ref, "changes": {"hidden": 1}}, lambda: self.s.read("report_sections", "ABC", ref=ref)["hidden"]),
                           ({"op": "move", "id": ref, "before": first}, lambda: self.s.read("report_sections", "ABC", ref=ref)["sort_order"])):
            was = check()
            body = self.ok(**req)
            self.assertNotEqual(check(), was, req)
            self.undo_step(body["apply_id"])
            self.assertEqual(check(), was, req)
        body = self.ok(op="delete", id=ref)
        self.assertNotIn(ref, [s["id"] for s in self.sections()])
        self.undo_step(body["apply_id"])
        self.assertIn(ref, [s["id"] for s in self.sections()])

    def test_a_second_gantt_section_is_not_refused(self):
        self.add_gantt()
        self.add_gantt()
        self.assertEqual([s["type"] for s in self.sections()].count("gantt"), 2)


class Published(Base):
    def lines(self):
        base = {"type": "task", "start": "2026-11-02", "end": "2026-11-13", "health": "Green"}
        self.ok(kind="gantt_lines", op="new", values={**base, "name": "Dig", "show": 1})
        self.ok(kind="gantt_lines", op="new", values={**base, "name": SECRET, "show": 0, "note": SECRET})

    def tab(self, on):
        self.ok(kind="projects", op="update", changes={"show_gantt_client": 1 if on else 0})

    def built(self):
        return publish.build(self.s, "ABC", now="2030-01-15")

    def types(self, built):
        return [s["type"] for s in built["published"]["sections"]]

    def test_the_section_is_in_the_file_exactly_with_the_gantt_tab(self):
        ref = self.add_gantt()["ref"]
        self.lines()
        self.tab(False)
        off = self.built()
        self.assertNotIn("gantt", self.types(off))
        self.assertNotIn("gantt", off["published"]["tabs"])
        self.tab(True)
        on = self.built()
        self.assertIn("gantt", on["published"]["tabs"])
        got = [s for s in on["published"]["sections"] if s["type"] == "gantt"]
        self.assertEqual(got, [{"id": ref, "type": "gantt", "title": "Gantt", "beside": 0}])      # no data of its own
        self.assertEqual([l["name"] for l in on["published"]["data"]["gantt"]["lines"]], ["Dig"])

    def test_no_eye_on_line_means_no_tab_and_no_section_even_with_the_switch_on(self):
        self.add_gantt()
        self.tab(True)
        self.assertNotIn("gantt", self.types(self.built()))
        self.ok(kind="gantt_lines", op="new", values={"type": "task", "name": "Hidden", "start": "2026-11-02", "end": "2026-11-03", "show": 0})
        built = self.built()
        self.assertNotIn("gantt", self.types(built))
        self.assertNotIn("gantt", built["published"]["data"])

    def test_a_hidden_gantt_section_is_left_out_and_so_is_nothing_eye_off_in_the_file(self):
        ref = self.add_gantt()["ref"]
        self.lines()
        self.tab(True)
        self.ok(op="update", id=ref, changes={"hidden": 1})
        built = self.built()
        self.assertNotIn("gantt", self.types(built))
        self.assertNotIn(SECRET, built["body"].decode("utf-8"))
        self.ok(op="update", id=ref, changes={"hidden": 0})
        built = self.built()
        self.assertIn("gantt", self.types(built))
        self.assertNotIn(SECRET, built["body"].decode("utf-8"))
        self.assertNotIn(SECRET, json.dumps(built["published"], ensure_ascii=False))

    def test_the_excel_path_leaves_a_gantt_section_out_and_the_word_path_only_when_the_file_has_no_gantt(self):
        from clark import docx_build, excel_cover
        self.assertEqual(docx_build.TITLES["gantt"], "Gantt")          # #1012: the Word report draws the Gantt tab (tests/test_docx_gantt.py); it is left out when data.gantt is not in the file
        published = {"sections": [{"id": "a", "type": "gantt", "title": "Gantt", "beside": 0}], "data": {}}
        self.assertEqual(docx_build.sections(published, None), [])
        lines = excel_cover.lines({"name": "Example Programme"}, [{"type": "gantt", "title": "Gantt plan", "body": "", "hidden": 0}], [], "exported now")
        self.assertNotIn("Gantt plan", json.dumps(lines))


if __name__ == "__main__":
    unittest.main()
