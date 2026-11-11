"""Row 1068: the table-only section type 'gantttable' (schema layout 22; store.py, schema.sql, changes.py, publish.py: guarded). Fictional data only.

It is the Gantt section without the Gantt view: the same lines, the same eye (only eye-on lines), the same hidden columns, drawn as the
Gantt table alone. It is a template section like the others (the owner's ruling, CMD 11-10-005): it does not ask the project's client
switch show_gantt_client, so it is in the file with the eye-on lines whether or not the Gantt tab is; with no eye-on line there is
nothing to draw and it is left out. Pinned here (the page part is pinned in tests/test_gantt_section.py): migration step 22 makes
report_sections again with 'gantttable' in its type CHECK (backup first, rows kept in order, a second run changes nothing, an older clark
refuses layout 22, a new database equals a migrated one); the section is added, retitled, hidden, moved and deleted through the change
route with one Undo each, and takes no body; the published file carries the section (id, type, title, beside and nothing else) with the
Gantt lines (data.gantt, without the tab when the switch is off) and no eye-off line reaches the file through it; a Gantt section and a
table section live side by side; the Word and Excel paths leave it out.

Run: python3 dev/run_tests.py test_gantt_table_section
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

STEP = 22
KIND = "gantttable"
SECRET = "ZQ-EYE-OFF-TABLE"


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
                        [("ABC-S-001", "text", "Summary", "<p>Hello</p>", 0, 0, 1), ("ABC-S-002", "gantt", "Gantt", "", 1, 0, 2),
                         ("ABC-S-003", "needs", "Needs from you", "", 0, 1, 3)])
        con.close()
        return path

    def test_the_step_is_at_its_number_and_is_the_latest(self):
        self.assertIn(STEP, [n for n, _ in store_module.MIGRATIONS])
        self.assertEqual(dict(store_module.MIGRATIONS)[STEP], store_module.migrate_gantt_table_section_type)
        self.assertGreaterEqual(store_module.SCHEMA_VERSION, STEP)

    def test_a_layout_20_file_opens_with_the_new_check_and_every_row_kept_in_order(self):
        path = self.old_file()
        self.assertNotIn(f"'{KIND}'", sections_sql(path))
        before = section_rows(path)
        s = open_store(path, onedrive_roots=[])
        try:
            self.assertEqual(version(path), str(store_module.SCHEMA_VERSION))
            self.assertEqual(s.con.execute("PRAGMA foreign_key_check").fetchall(), [])
            self.assertEqual(s.con.execute("SELECT count(*) FROM applies").fetchone()[0], 0)     # a migration is not a step: no Undo
            s.con.execute(f"INSERT INTO report_sections (project, id, type, title, sort_order) VALUES ('ABC', 'ABC-S-009', '{KIND}', 'Table', 9)")
        finally:
            s.close()
        self.assertIn(f"'{KIND}'", sections_sql(path))
        self.assertEqual(section_rows(path)[:3], before)

    def test_a_safety_copy_is_taken_first_and_it_is_the_old_layout(self):
        path = self.old_file()
        open_store(path, onedrive_roots=[]).close()
        copies = self.copies()
        self.assertEqual(len(copies), 1)
        self.assertEqual(version(copies[0]), str(STEP - 1))
        self.assertNotIn(f"'{KIND}'", sections_sql(copies[0]))

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
        store_module.migrate_gantt_table_section_type(con)
        was = sections_sql(path), section_rows(path)
        store_module.migrate_gantt_table_section_type(con)
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
            return " ".join("\n".join(l.split("--")[0] for l in text.splitlines()).replace('"', "").replace("report_sections_table", "report_sections").replace("IF NOT EXISTS ", "").split())
        self.assertEqual(squash(sections_sql(path)), squash(sections_sql(new)))
        self.assertEqual(squash(store_module.REPORT_SECTIONS_WITH_GANTT_TABLE), squash(sections_sql(new)))

    def test_a_failure_after_the_rebuild_rolls_back_and_the_next_open_migrates(self):
        path = self.old_file()
        was = dump(path)
        real = store_module.migrate_gantt_table_section_type

        def then_fail(con):
            real(con)
            raise sqlite3.OperationalError("disk I/O error")
        with mock.patch.object(store_module, "MIGRATIONS", tuple((n, then_fail if n == STEP else f) for n, f in store_module.MIGRATIONS)):
            with self.assertRaises(Invalid):
                open_store(path, onedrive_roots=[])
        self.assertEqual(dump(path), was)
        open_store(path, onedrive_roots=[]).close()
        self.assertEqual(version(path), str(store_module.SCHEMA_VERSION))

    def test_the_type_check_takes_both_gantt_types_and_refuses_an_unknown_one(self):
        with DemoStore() as demo:
            con = demo.con
            for n, kind in enumerate(("gantt", KIND), 90):
                con.execute(f"INSERT INTO report_sections (project, id, type, title, sort_order) VALUES ('ABC', 'ABC-S-0{n}', '{kind}', 'X', {n})")
            with self.assertRaises(sqlite3.IntegrityError):
                con.execute("INSERT INTO report_sections (project, id, type, title, sort_order) VALUES ('ABC', 'ABC-S-099', 'gantttable2', 'X', 99)")


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

    def add(self, kind=KIND, title="Table", **more):
        return self.ok(op="new", values={"type": kind, "title": title}, **more)


class TheChangeRoute(Base):
    def test_the_allow_list_names_the_type_and_the_store_lists_it_once(self):
        self.assertIn(KIND, changes.NEW_SECTION_TYPES)
        self.assertEqual(store_module.SECTION_TYPES.count(KIND), 1)
        self.assertIn(KIND, store_module.DELETABLE_TYPES)
        self.assertNotIn(KIND, store_module.BODY_TYPES)

    def test_a_table_section_is_added_with_one_undo_and_the_undo_takes_it_away(self):
        before = [s["id"] for s in self.sections()]
        body = self.add()
        added = [s for s in self.sections() if s["id"] not in before]
        self.assertEqual([(s["type"], s["title"], s["body"]) for s in added], [(KIND, "Table", "")])
        self.undo_step(body["apply_id"])
        self.assertEqual([s["id"] for s in self.sections()], before)

    def test_a_body_is_refused_on_a_new_table_section_and_on_an_update(self):
        n = len(self.sections())
        status, body = self.go(op="new", values={"type": KIND, "title": "Table", "body": "x"})
        self.assertEqual((status, body["message"]), (400, changes.NO_BODY_HERE))
        self.assertEqual(len(self.sections()), n)
        ref = self.add()["ref"]
        status, body = self.go(op="update", id=ref, changes={"body": "x"})
        self.assertEqual((status, body["message"]), (400, changes.NO_BODY_HERE))
        self.assertEqual(self.s.read("report_sections", "ABC", ref=ref)["body"], "")

    def test_a_table_section_keeps_its_type(self):
        ref = self.add()["ref"]
        status, body = self.go(op="update", id=ref, changes={"type": "gantt"})
        self.assertEqual((status, body["message"]), (400, changes.KEEPS_TYPE))
        self.assertEqual(self.s.read("report_sections", "ABC", ref=ref)["type"], KIND)

    def test_a_table_section_can_be_retitled_hidden_moved_and_deleted_each_with_one_undo(self):
        first = self.sections()[0]["id"]
        ref = self.add()["ref"]
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

    def test_a_gantt_section_and_a_table_section_live_side_by_side_and_more_than_one_table_is_not_refused(self):
        self.add("gantt", "Gantt")
        self.add()
        self.add()
        kinds = [s["type"] for s in self.sections()]
        self.assertEqual((kinds.count("gantt"), kinds.count(KIND)), (1, 2))


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

    def test_the_type_is_one_the_published_file_may_carry(self):
        self.assertIn(KIND, publish.SECTION_TYPES)

    def test_the_section_is_in_the_file_with_the_gantt_data_and_nothing_else_of_its_own(self):
        ref = self.add()["ref"]
        self.lines()
        self.tab(True)
        built = self.built()
        got = [s for s in built["published"]["sections"] if s["type"] == KIND]
        self.assertEqual(got, [{"id": ref, "type": KIND, "title": "Table", "beside": 0}])
        self.assertEqual([l["name"] for l in built["published"]["data"]["gantt"]["lines"]], ["Dig"])

    def test_the_table_section_does_not_ask_the_client_switch_only_an_eye_on_line(self):
        """The owner's ruling (CMD 11-10-005): a template section, not the Gantt tab's. With the switch off the section is in the file with
        the eye-on lines and nothing of the tab (no tab, no Gantt section, no tab name); with every eye off there is nothing to draw: no
        section and no Gantt data."""
        self.add("gantt", "Gantt")
        self.add()
        self.lines()
        self.tab(False)
        off = self.built()
        self.assertIn(KIND, self.types(off))
        self.assertNotIn("gantt", self.types(off), "the Gantt section is the tab's and stays out")
        self.assertNotIn("gantt", off["published"]["tabs"], "the tab stays off")
        self.assertEqual(off["published"]["data"]["gantt"], {"columns": off["published"]["data"]["gantt"]["columns"], "lines": off["published"]["data"]["gantt"]["lines"]}, "lines and columns only")
        self.assertEqual([l["name"] for l in off["published"]["data"]["gantt"]["lines"]], ["Dig"])
        self.assertNotIn("gantt_tab_name", off["published"]["data"]["project"])
        self.assertNotIn(SECRET, off["body"].decode("utf-8"))
        self.ok(kind="gantt_lines", op="update", id=self.s.read("gantt_lines", "ABC")[0]["id"], changes={"show": 0})
        none = self.built()
        self.assertNotIn(KIND, self.types(none))
        self.assertNotIn("gantt", none["published"]["data"])
        self.tab(True)
        self.assertNotIn(KIND, self.types(self.built()), "the switch does not bring an empty table section in either")

    def test_without_a_table_section_the_switch_off_still_keeps_the_gantt_data_out(self):
        self.lines()
        self.tab(False)
        off = self.built()
        self.assertNotIn("gantt", off["published"]["data"])
        self.assertNotIn("gantt", off["published"]["tabs"])

    def test_a_hidden_table_section_is_left_out_and_so_is_nothing_eye_off_in_the_file(self):
        ref = self.add()["ref"]
        self.lines()
        self.tab(True)
        self.ok(op="update", id=ref, changes={"hidden": 1})
        built = self.built()
        self.assertNotIn(KIND, self.types(built))
        self.assertNotIn(SECRET, built["body"].decode("utf-8"))
        self.ok(op="update", id=ref, changes={"hidden": 0})
        built = self.built()
        self.assertIn(KIND, self.types(built))
        self.assertNotIn(SECRET, built["body"].decode("utf-8"))
        self.assertNotIn(SECRET, json.dumps(built["published"], ensure_ascii=False))

    def test_a_table_section_beside_a_gantt_section_both_publish(self):
        self.add("gantt", "Gantt")
        self.add()
        self.lines()
        self.tab(True)
        self.assertEqual(sorted(t for t in self.types(self.built()) if t in ("gantt", KIND)), ["gantt", KIND])

    def test_the_excel_path_leaves_a_table_section_out(self):
        from clark import excel_cover
        lines = excel_cover.lines({"name": "Example Programme"}, [{"type": KIND, "title": "Table plan", "body": "", "hidden": 0}], [], "exported now")
        self.assertNotIn("Table plan", json.dumps(lines))

    def test_the_word_path_draws_nothing_of_its_own_for_it(self):
        from clark import docx_build
        published = {"sections": [{"id": "a", "type": KIND, "title": "Table", "beside": 0}], "data": {}}
        self.assertEqual(docx_build.sections(published, None), [])

    def workbook(self, built):
        import base64
        import io
        from openpyxl import load_workbook
        embedded = built["published"]["data"].get("client_workbook")
        self.assertIsNotNone(embedded, "the client workbook is in the file")
        wb = load_workbook(io.BytesIO(base64.b64decode(embedded["base64"])))
        return wb.sheetnames, [str(c.value) for ws in wb.worksheets for row in ws.iter_rows() for c in row if c.value is not None]

    def test_the_client_workbook_is_still_made_with_the_switch_off_and_the_gantt_sheet_is_the_tabs(self):
        """The Gantt sheet (row 926) is the tab's: it is in the workbook when the tab is in the file, not for a table section alone. With
        the switch off the workbook is made (no KeyError, no 'could not be made' warning) and holds no Gantt sheet; with the switch on
        the sheet is there as before."""
        import logging
        self.add()
        self.lines()
        self.tab(False)
        records = []
        handler = logging.Handler()
        handler.emit = records.append
        logging.getLogger("clark.publish").addHandler(handler)
        self.addCleanup(logging.getLogger("clark.publish").removeHandler, handler)
        off = publish.build(self.s, "ABC", now="2030-01-15", workbook=True)
        self.assertEqual([r.getMessage() for r in records if "workbook" in r.getMessage()], [], "the workbook is made")
        self.assertEqual([l["name"] for l in off["published"]["data"]["gantt"]["lines"]], ["Dig"], "the table section's lines are in the file")
        names, cells = self.workbook(off)
        self.assertNotIn("Gantt", names, "no tab, no Gantt sheet")
        self.assertNotIn("Dig", cells)
        self.assertNotIn(SECRET, "\n".join(cells))
        self.tab(True)
        names, cells = self.workbook(publish.build(self.s, "ABC", now="2030-01-15", workbook=True))
        self.assertIn("Gantt", names, "the tab brings its sheet")
        self.assertIn("Dig", cells)
        self.assertNotIn(SECRET, "\n".join(cells))

    def test_the_switch_off_with_a_table_section_is_not_held_back_by_the_marker_check(self):
        """publish_flow.gantt_markers mirrors publish.select: with a shown table section the eye-on line may be in the file (not a marker);
        the eye-off line is one; without a table section the eye-on line is a marker again (the switch alone decides)."""
        from clark import publish_flow, to_client
        ref = self.add()["ref"]
        self.lines()
        self.tab(False)
        built = self.built()
        on, off = [r["id"] for r in self.s.read("gantt_lines", "ABC")]
        markers = list(publish_flow.markers_for(self.s, "ABC", built["published"]))
        self.assertNotIn("Dig", markers)
        self.assertNotIn(on, markers)
        self.assertIn(SECRET, markers)
        self.assertIn(off, markers)
        self.assertEqual(to_client.check_copy(built["body"], markers=markers, folder=None), [], "the real publish would not hold the file back")
        self.ok(op="update", id=ref, changes={"hidden": 1})
        built = self.built()
        markers = list(publish_flow.markers_for(self.s, "ABC", built["published"]))
        self.assertIn(on, markers, "a hidden table section: the line may not be in the file")
        self.assertEqual(to_client.check_copy(built["body"], markers=markers, folder=None), [])


if __name__ == "__main__":
    unittest.main()
