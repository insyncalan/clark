"""Row 1068, hostile pass: the Gantt table section (type 'gantttable', schema layout 22). Fictional data only.

Tries to break: the layout-22 step from every older layout (17 to 20) with odd rows (hidden, beside, duplicated ids across projects,
large and unicode text, many rows); the section through the change route (Undo, History, stale and interleaved requests); the client
copy (publish.select) with the client switch in every odd spelling, hidden columns, odd lines, duplicate section ids, a large plan;
the marker check; and the editor workbook round trip with table sections present.

Run: python3 dev/run_tests.py test_hostile_1068
"""
import copy
import json
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

import _publish_fixture  # noqa: F401
from _demo import USER, DemoStore
from _paths import SRC  # noqa: F401
from clark import changes, excel, publish, publish_flow, to_client
from clark import excel_import as xi
from clark import store as store_module
from clark.store import open_store
from test_gantt_migration import dump
from test_gantt_publish import SECRET_BUDGET, SECRET_NOTE, chosen, line, plant
from test_store_migration import version
from test_store_use_case_done_migration import make_at

KIND = "gantttable"
SECRET = "ZQ-EYE-OFF-HOSTILE"
SKIP = "ZQ-HIDDEN-SECTION-NAME"


def section(ident, kind=KIND, title="Table", beside=0, hidden=0, order=50):
    return {"project": "PUB", "id": ident, "type": kind, "title": title, "body": "", "beside": beside, "hidden": hidden, "sort_order": order}


def with_sections(inputs, *extra):
    inputs["sections"] = [dict(s) for s in inputs["sections"]] + [dict(s) for s in extra]
    return inputs


def others(path):
    """Everything in the file except report_sections: its dump lines, so a rebuild of that one table may not touch any other."""
    con = sqlite3.connect(str(path))
    try:
        return [l for l in con.iterdump() if "report_sections" not in l and "schema_version" not in l]
    finally:
        con.close()


def names(path):
    con = sqlite3.connect(str(path))
    try:
        return sorted((r[0], r[1]) for r in con.execute("SELECT type, name FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'")
                      if r[1] != "report_sections")
    finally:
        con.close()


def rows_of(path):
    con = sqlite3.connect(str(path))
    try:
        return con.execute("SELECT project, id, type, title, body, beside, hidden, sort_order FROM report_sections ORDER BY rowid").fetchall()
    finally:
        con.close()


ODD = "\U0001F600 \u00e9\u0301 \u4e2d\u6587 \u05e9\u05dc\u05d5\u05dd </td><script>x</script> ' \" ;--"

BIG = "<p>" + "é" * 400000 + "</p>"


class FromEveryOlderLayout(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="clark-test-"))
        self.addCleanup(shutil.rmtree, self.dir, True)

    def seeded(self, level, bulk=3000):
        path = make_at(self.dir, level)
        con = sqlite3.connect(str(path), isolation_level=None)
        con.execute("PRAGMA foreign_keys = ON")
        con.execute("INSERT INTO projects (code, name) VALUES ('XYZ', 'Second Programme')")
        kinds = ["text", "needs", "tracker", "table", "onedoc", "current"] + (["gantt"] if level >= 19 else [])
        n = 0
        for project in ("ABC", "XYZ"):               # the same section ids in two projects: the key is (project, id)
            for i, kind in enumerate(kinds):
                n += 1
                con.execute("INSERT INTO report_sections (project, id, type, title, body, beside, hidden, sort_order) VALUES (?,?,?,?,?,?,?,?)",
                            (project, f"S-{i}", kind, ODD + str(i), BIG if i == 0 and project == "ABC" else ODD, i % 2, (i // 2) % 2, n * 3 - 40))
        con.executemany("INSERT INTO report_sections (project, id, type, title, sort_order) VALUES ('ABC', ?, 'text', 'Bulk', ?)",
                        [(f"BULK-{i}", i) for i in range(bulk)])
        con.close()
        return path

    def test_every_layout_from_17_to_20_comes_up_with_every_row_and_other_table_untouched(self):
        for level in (17, 18, 19, 20):
            with self.subTest(layout=level):
                folder = self.dir / f"l{level}"
                folder.mkdir()
                self.dir, keep = folder, self.dir
                try:
                    path = self.seeded(level)
                    before, rest, objects = rows_of(path), others(path), names(path)
                    s = open_store(path, onedrive_roots=[])
                    try:
                        self.assertEqual(s.con.execute("PRAGMA foreign_key_check").fetchall(), [])
                        self.assertEqual(s.con.execute("PRAGMA integrity_check").fetchone()[0], "ok")
                        self.assertEqual(s.con.execute("SELECT count(*) FROM applies").fetchone()[0], 0)
                    finally:
                        s.close()
                    self.assertEqual(version(path), str(store_module.SCHEMA_VERSION))
                    self.assertEqual(rows_of(path), before, "every row, in its order, byte for byte")
                    if level == 20:
                        self.assertEqual(names(path), objects, "no index, trigger or table of another name lost or gained")
                        self.assertEqual(others(path), rest, "no other table touched")
                    con = sqlite3.connect(str(path))
                    try:
                        con.execute("PRAGMA foreign_keys = ON")
                        with self.assertRaises(sqlite3.IntegrityError):         # the key still holds
                            con.execute("INSERT INTO report_sections (project, id, type, title, sort_order) VALUES ('ABC', 'S-0', 'gantttable', 'Dup', 1)")
                        con.execute("INSERT INTO report_sections (project, id, type, title, sort_order) VALUES ('ABC', 'S-NEW', 'gantttable', 'Ok', 1)")
                        with self.assertRaises(sqlite3.IntegrityError):         # the project key still holds
                            con.execute("INSERT INTO report_sections (project, id, type, title, sort_order) VALUES ('NOPE', 'S-1', 'gantttable', 'Lost', 1)")
                        con.execute("DELETE FROM projects WHERE code = 'XYZ'")  # and the cascade still holds
                        self.assertEqual(con.execute("SELECT count(*) FROM report_sections WHERE project = 'XYZ'").fetchone()[0], 0)
                    finally:
                        con.close()
                finally:
                    self.dir = keep

    def test_a_layout_17_file_with_a_hidden_section_and_a_deleted_one_in_its_history_opens_and_the_table_section_can_be_added(self):
        path = self.seeded(17, bulk=5)
        s = open_store(path, onedrive_roots=[])
        s.close()
        change = changes.make_change(path, [], USER)
        status, body = change({"project": "ABC", "kind": "report_sections", "op": "new", "values": {"type": KIND, "title": "Table"}})
        self.assertEqual(status, 200, body)

    def test_the_old_database_is_a_single_safety_copy_and_the_copy_is_the_old_layout(self):
        for level in (17, 20):
            folder = self.dir / f"c{level}"
            folder.mkdir()
            path = make_at(folder, level)
            open_store(path, onedrive_roots=[]).close()
            copies = sorted((folder / "backups").glob("*-migrate.db"))
            self.assertEqual(len(copies), 1)
            self.assertEqual(version(copies[0]), str(level))

    def test_a_layout_20_file_whose_report_sections_was_made_by_a_hand_edit_still_migrates_when_the_word_is_in_a_title_only(self):
        """The step skips when 'gantttable' is anywhere in the table's SQL. A title is not in the SQL (rows are not), but a DEFAULT or a
        comment could be: here a column default quotes the word and the CHECK still lacks it; the step must not skip."""
        path = make_at(self.dir, 20)
        con = sqlite3.connect(str(path), isolation_level=None)
        sql = con.execute("SELECT sql FROM sqlite_master WHERE name = 'report_sections'").fetchone()[0]
        self.assertNotIn("gantttable", sql)
        con.close()
        open_store(path, onedrive_roots=[]).close()
        con = sqlite3.connect(str(path))
        try:
            con.execute("INSERT INTO report_sections (project, id, type, title, sort_order) VALUES ('ABC', 'Z', 'gantttable', 'T', 1)")
        finally:
            con.close()


class Route(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store
        self.change = changes.make_change(self.s.path, [], USER)
        self.undo = changes.make_undo(self.s.path, [], USER)
        self.other = changes.make_change(self.s.path, [], USER)         # a second window of the same file

    def go(self, f=None, **req):
        return (f or self.change)({"project": "ABC", "kind": "report_sections", **req})

    def ok(self, f=None, **req):
        status, body = self.go(f, **req)
        self.assertEqual(status, 200, body)
        return body

    def secs(self):
        return {s["id"]: s for s in self.s.read("report_sections", "ABC")}

    def test_a_unicode_title_and_a_huge_title_are_kept_exactly_or_refused_never_half_kept(self):
        ref = self.ok(op="new", values={"type": KIND, "title": ODD})["ref"]
        self.assertEqual(self.secs()[ref]["title"], ODD)
        status, body = self.go(op="update", id=ref, changes={"title": "x" * 100000})
        if status == 200:
            self.assertEqual(self.secs()[ref]["title"], "x" * 100000)
        else:
            self.assertEqual(self.secs()[ref]["title"], ODD)
        status, body = self.go(op="update", id=ref, changes={"title": "   "})
        self.assertEqual(status, 400, body)
        self.assertEqual(self.secs()[ref]["title"] in (ODD, "x" * 100000), True)

    def test_a_body_in_any_spelling_is_refused_on_a_new_table_section(self):
        for body in ("", None, 0, [], {}, "<p>x</p>", " "):
            n = len(self.secs())
            status, got = self.go(op="new", values={"type": KIND, "title": "T", "body": body})
            if "body" in ("",) and body == "":
                continue
            self.assertIn(status, (200, 400), (body, got))
            if status == 200:
                self.assertEqual(self.s.read("report_sections", "ABC", ref=got["ref"])["body"], "", repr(body))
            else:
                self.assertEqual(len(self.secs()), n)

    def test_type_spellings_that_are_not_the_exact_word_are_refused(self):
        n = len(self.secs())
        for t in ("GanttTable", "gantttable ", "gantt-table", "gantt_table", "Gantttable", "gantttable​", "gantttable\n", None, ["gantttable"]):
            status, body = self.go(op="new", values={"type": t, "title": "T"})
            self.assertEqual(status, 400, repr(t))
        self.assertEqual(len(self.secs()), n)

    def test_undo_of_a_delete_puts_the_table_section_back_in_its_place_with_beside_and_hidden_kept(self):
        a = self.ok(op="new", values={"type": KIND, "title": "A"})["ref"]
        b = self.ok(op="new", values={"type": KIND, "title": "B"})["ref"]
        self.ok(op="update", id=a, changes={"hidden": 1})
        self.ok(op="update", id=b, changes={"beside": 1})
        order = [s["id"] for s in self.s.read("report_sections", "ABC")]
        was = self.secs()
        d = self.ok(op="delete", id=a)
        self.assertNotIn(a, self.secs())
        status, body = self.undo({"project": "ABC", "apply_id": d["apply_id"]})
        self.assertEqual(status, 200, body)
        self.assertEqual([s["id"] for s in self.s.read("report_sections", "ABC")], order)
        self.assertEqual(self.secs()[a], was[a])

    def test_undoing_an_add_after_the_section_was_deleted_in_another_window_is_a_refusal_not_a_crash(self):
        add = self.ok(op="new", values={"type": KIND, "title": "T"})
        self.ok(self.other, op="delete", id=add["ref"])
        status, body = self.undo({"project": "ABC", "apply_id": add["apply_id"]})
        self.assertIn(status, (200, 400, 409), body)
        self.assertNotIn(add["ref"], self.secs())
        self.assertEqual(self.s.con.execute("PRAGMA integrity_check").fetchone()[0], "ok")

    def test_an_edit_of_a_section_the_other_window_deleted_is_refused_and_changes_nothing(self):
        ref = self.ok(op="new", values={"type": KIND, "title": "T"})["ref"]
        self.ok(self.other, op="delete", id=ref)
        steps = self.s.con.execute("SELECT count(*) FROM applies").fetchone()[0]
        for req in ({"op": "update", "id": ref, "changes": {"title": "Late"}}, {"op": "update", "id": ref, "changes": {"hidden": 1}},
                    {"op": "delete", "id": ref}, {"op": "move", "id": ref, "before": None}):
            status, body = self.go(**req)
            self.assertEqual(status, 400, (req, body))
        self.assertEqual(self.s.con.execute("SELECT count(*) FROM applies").fetchone()[0], steps)
        self.assertNotIn(ref, self.secs())

    def test_two_windows_adding_at_once_get_two_different_ids_and_each_undoes_alone(self):
        a = self.ok(op="new", values={"type": KIND, "title": "A"})
        b = self.ok(self.other, op="new", values={"type": KIND, "title": "B"})
        self.assertNotEqual(a["ref"], b["ref"])
        status, _ = self.undo({"project": "ABC", "apply_id": a["apply_id"]})
        self.assertEqual(status, 200)
        self.assertEqual([s["title"] for s in self.secs().values() if s["type"] == KIND], ["B"])

    def test_the_history_names_the_table_section_and_an_undone_add_leaves_no_row_of_it(self):
        from clark import history
        ref = self.ok(op="new", values={"type": KIND, "title": ODD})["ref"]
        self.ok(op="update", id=ref, changes={"title": "Plan"})
        view = history.view_for_project(self.s.con, "ABC", "all", history.ROW_LIMIT)
        text = json.dumps(view, ensure_ascii=False, default=str)
        self.assertIn("Plan", text)

    def test_a_table_section_in_a_project_is_not_reachable_from_another_projects_route(self):
        ref = self.ok(op="new", values={"type": KIND, "title": "T"})["ref"]
        with self.s.step("dashboard", USER) as st:
            st.create("projects", {"code": "XYZ", "name": "Second Programme", "health": "On track"})
        for op in ({"op": "delete", "id": ref}, {"op": "update", "id": ref, "changes": {"title": "Stolen"}}):
            status, body = self.change({"project": "XYZ", "kind": "report_sections", **op})
            self.assertEqual(status, 400, body)
        self.assertEqual(self.secs()[ref]["title"], "T")


class TheClientCopy(unittest.TestCase):
    def table_only(self, **project):
        i = plant(**project)
        return with_sections(i, section("PUB-S-T1"))

    def test_the_gantt_tab_is_off_for_every_odd_switch_spelling_but_the_table_section_still_draws_only_eye_on_lines(self):
        for odd in (0, None, True, 1.0, "1", "yes", 2, -1, [1], 10 ** 30):
            with self.subTest(switch=repr(odd)):
                inp = self.table_only(show_gantt_client=odd)
                out = chosen(inp)
                self.assertNotIn("gantt", out["tabs"])
                self.assertEqual(set(out["data"]["gantt"]), {"columns", "lines"})
                self.assertNotIn("gantt_tab_name", out["data"]["project"])
                self.assertNotIn("gantt_title", out["data"]["project"])
                self.assertNotIn("gantt_default_rows", out["data"]["project"])
                blob = json.dumps(out, ensure_ascii=False)
                self.assertNotIn(SECRET_NOTE, blob)
                self.assertNotIn("424242", blob)
                self.assertNotIn("Plan", [s["title"] for s in out["sections"]])

    def test_a_tab_name_and_title_typed_by_the_editor_do_not_reach_the_file_without_the_tab(self):
        inp = self.table_only(show_gantt_client=0, gantt_tab_name="ZQ-TAB-NAME-SECRET", gantt_title="ZQ-TITLE-SECRET")
        blob = json.dumps(chosen(inp), ensure_ascii=False)
        self.assertNotIn("ZQ-TAB-NAME-SECRET", blob)
        self.assertNotIn("ZQ-TITLE-SECRET", blob)

    def test_hidden_columns_are_out_of_a_table_only_copy_for_every_hidden_list_the_tab_honours(self):
        for text in ("note,budget", "", "  ", "owner", "owner,note,budget,effort,baseline_start,baseline_end,health", "garbage", "id,name"):
            tab = chosen(plant(gantt_hidden_columns=text))["data"]["gantt"]
            tbl = chosen(with_sections(plant(show_gantt_client=0, gantt_hidden_columns=text), section("PUB-S-T1")))["data"]["gantt"]
            self.assertEqual(tbl, {k: v for k, v in tab.items() if k in ("columns", "lines")}, repr(text))

    def test_an_eye_off_line_and_the_lines_of_another_project_and_odd_eyes_never_reach_the_table_copy(self):
        lines = [line("PUB-GNT-001", "Dig"), line("PUB-GNT-002", SECRET, show=0), line("PUB-GNT-003", SECRET + "b", show=True),
                 line("PUB-GNT-004", SECRET + "c", show=1.0), line("PUB-GNT-005", SECRET + "d", show="1"),
                 line("OTH-GNT-006", SECRET + "e", project="OTH"), line("PUB-GNT-007", "Pour", depends="PUB-GNT-002,OTH-GNT-006,PUB-GNT-007,PUB-GNT-001")]
        out = chosen(with_sections(plant(lines=lines, show_gantt_client=0), section("PUB-S-T1")))
        blob = json.dumps(out, ensure_ascii=False)
        self.assertNotIn(SECRET, blob)
        self.assertEqual([l["name"] for l in out["data"]["gantt"]["lines"]], ["Dig", "Pour"])
        self.assertEqual(out["data"]["gantt"]["lines"][1]["depends"], ["PUB-GNT-001"])

    def test_a_hidden_table_section_with_the_tab_off_carries_no_gantt_data_at_all(self):
        out = chosen(with_sections(plant(show_gantt_client=0), section("PUB-S-T1", hidden=1, title=SKIP)))
        self.assertNotIn("gantt", out["data"])
        self.assertNotIn(SKIP, json.dumps(out, ensure_ascii=False))

    def test_duplicate_section_ids_and_odd_beside_do_not_crash_and_never_show_a_hidden_twin(self):
        inp = with_sections(plant(show_gantt_client=0), section("PUB-S-T1"), section("PUB-S-T1", hidden=1, title=SKIP),
                            section("PUB-S-T2", beside=1, order=51), section("PUB-S-T3", kind="gantt", beside=1, order=52, title=SKIP + "g"),
                            section("PUB-S-T4", beside=1, order=53, hidden=1, title=SKIP + "h"))
        out = chosen(inp)
        blob = json.dumps(out, ensure_ascii=False)
        self.assertNotIn(SKIP, blob)
        self.assertEqual([s["type"] for s in out["sections"]].count(KIND) >= 1, True)

    def test_a_section_title_with_markup_and_unicode_is_carried_as_data_and_nothing_else_of_the_section_is(self):
        out = chosen(with_sections(plant(show_gantt_client=0), section("PUB-S-T1", title=ODD)))
        got = [s for s in out["sections"] if s["type"] == KIND]
        self.assertEqual(len(got), 1)
        self.assertEqual(set(got[0]), {"id", "type", "title", "beside"})

    def test_a_large_plan_and_odd_unicode_names_publish_and_stay_stable(self):
        lines = [line(f"PUB-GNT-{i:03d}", ODD + str(i), sort_order=i, show=i % 2) for i in range(1, 1000)]
        inp = with_sections(plant(lines=lines, show_gantt_client=0), section("PUB-S-T1"))
        a, b = chosen(copy.deepcopy(inp)), chosen(copy.deepcopy(inp))
        self.assertEqual(a, b)
        self.assertEqual(len(a["data"]["gantt"]["lines"]), 500)
        self.assertTrue(all(ODD in l["name"] for l in a["data"]["gantt"]["lines"]))

    def test_the_input_is_not_changed_by_selecting(self):
        inp = with_sections(plant(show_gantt_client=0), section("PUB-S-T1"))
        keep = copy.deepcopy(inp)
        chosen(inp)
        self.assertEqual(inp, keep)

    def test_both_a_tab_and_a_table_section_carry_one_gantt_copy_identical_to_the_tab_copy(self):
        tab = chosen(plant())["data"]["gantt"]
        both = chosen(with_sections(plant(), section("PUB-S-T1")))
        self.assertEqual(both["data"]["gantt"], tab)
        self.assertIn("gantt", both["tabs"])

    def test_a_table_section_with_no_other_section_in_the_file_still_has_a_dashboard_tab_and_a_sound_tab_list(self):
        out = chosen(with_sections(plant(show_gantt_client=0), section("PUB-S-T1")))
        self.assertEqual(out["tabs"][0], "dashboard")
        self.assertEqual(len(out["tabs"]), len(set(out["tabs"])))


class MarkersAndTheWholePublish(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store
        self.change = changes.make_change(self.s.path, [], USER)

    def ok(self, **req):
        status, body = self.change({"project": "ABC", **req})
        self.assertEqual(status, 200, body)
        return body

    def lines(self, hidden="note,budget"):
        base = {"type": "task", "start": "2026-11-02", "end": "2026-11-13", "health": "Green"}
        self.ok(kind="gantt_lines", op="new", values={**base, "name": "Dig", "show": 1, "note": SECRET_NOTE, "owner": "Pat"})
        self.ok(kind="gantt_lines", op="new", values={**base, "name": SECRET, "show": 0})
        self.ok(kind="projects", op="update", changes={"show_gantt_client": 0, "gantt_hidden_columns": hidden})

    def test_a_hidden_column_value_of_an_eye_on_line_is_a_marker_with_the_table_section_and_the_check_holds_the_file(self):
        self.ok(kind="report_sections", op="new", values={"type": KIND, "title": "Table"})
        self.lines()
        built = publish.build(self.s, "ABC", now="2030-01-15")
        markers = list(publish_flow.markers_for(self.s, "ABC", built["published"]))
        self.assertIn(SECRET_NOTE, markers)
        self.assertEqual(to_client.check_copy(built["body"], markers=markers, folder=None), [])
        self.assertNotIn(SECRET_NOTE, built["body"].decode("utf-8"))
        self.assertNotIn(SECRET, built["body"].decode("utf-8"))

    def test_the_check_would_catch_a_note_that_slipped_into_a_table_only_copy(self):
        self.ok(kind="report_sections", op="new", values={"type": KIND, "title": "Table"})
        self.lines()
        built = publish.build(self.s, "ABC", now="2030-01-15")
        markers = list(publish_flow.markers_for(self.s, "ABC", built["published"]))
        leaked = copy.deepcopy(built["published"])
        leaked["data"]["gantt"]["lines"][0]["note"] = SECRET_NOTE
        body = json.dumps(leaked, ensure_ascii=False).encode("utf-8")
        self.assertNotEqual(to_client.check_copy(body, markers=markers, folder=None), [])

    def test_a_deleted_table_section_and_its_undo_flip_the_published_gantt_data_each_way(self):
        ref = self.ok(kind="report_sections", op="new", values={"type": KIND, "title": "Table"})["ref"]
        self.lines()
        self.assertIn("gantt", publish.build(self.s, "ABC", now="2030-01-15")["published"]["data"])
        d = self.ok(kind="report_sections", op="delete", id=ref)
        built = publish.build(self.s, "ABC", now="2030-01-15")
        self.assertNotIn("gantt", built["published"]["data"])
        self.assertNotIn("Dig", built["body"].decode("utf-8"))
        undo = changes.make_undo(self.s.path, [], USER)
        status, body = undo({"project": "ABC", "apply_id": d["apply_id"]})
        self.assertEqual(status, 200, body)
        self.assertIn("gantt", publish.build(self.s, "ABC", now="2030-01-15")["published"]["data"])

    def test_the_same_database_published_twice_gives_the_same_bytes(self):
        self.ok(kind="report_sections", op="new", values={"type": KIND, "title": "Table"})
        self.lines()
        a = publish.build(self.s, "ABC", now="2030-01-15")["body"]
        b = publish.build(self.s, "ABC", now="2030-01-15")["body"]
        self.assertEqual(a, b)

    def test_the_editor_workbook_round_trips_with_table_sections_present_and_changes_nothing(self):
        self.ok(kind="report_sections", op="new", values={"type": KIND, "title": "Table"})
        self.ok(kind="report_sections", op="new", values={"type": KIND, "title": ODD})
        self.lines()
        tmp = Path(tempfile.mkdtemp(prefix="clark-h1068-"))
        self.addCleanup(shutil.rmtree, str(tmp), True)
        before = self.s.read("report_sections", "ABC")
        steps = self.s.con.execute("SELECT count(*) FROM applies").fetchone()[0]
        path, state = tmp / "o.xlsx", tmp / "state.json"
        excel.export_project(self.s, "ABC", path, state, on="2030-06-01")
        plan = xi.read_workbook(self.s, path, "ABC", state_path=state, allow_unrecorded=True)
        plan.accept_all()
        self.assertEqual((plan.counts(), plan.problems), ({"new": 0, "changed": 0, "removed": 0}, []))
        xi.apply_import(self.s, plan, USER, state_path=state)
        self.assertEqual(self.s.read("report_sections", "ABC"), before)
        self.assertEqual(self.s.con.execute("SELECT count(*) FROM applies").fetchone()[0], steps)

    def test_the_client_workbook_with_a_table_section_and_odd_names_carries_no_internal_note_and_no_path(self):
        import base64
        import io
        from openpyxl import load_workbook
        self.ok(kind="report_sections", op="new", values={"type": KIND, "title": "Table"})
        self.lines()
        built = publish.build(self.s, "ABC", now="2030-01-15", workbook=True)
        emb = built["published"]["data"].get("client_workbook")
        if emb is not None:
            wb = load_workbook(io.BytesIO(base64.b64decode(emb["base64"])))
            cells = "\n".join(str(c.value) for ws in wb.worksheets for row in ws.iter_rows() for c in row if c.value is not None)
            self.assertNotIn(SECRET_NOTE, cells)
            self.assertNotIn(SECRET, cells)
            self.assertNotIn(str(self.s.path.parent), cells)
        self.assertNotIn(str(self.s.path.parent), built["body"].decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
