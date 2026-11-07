"""Row 926: the workbook import reads the Gantt sheet the export writes (src/clark/excel_import.py, changes.gantt_import_write) and applies it
to the project's Gantt lines through the page's own change route and the data layer's rules. Fictional data only.

Model followed (the other sheets'): a row refused by a rule makes the whole check refuse (nothing is applied); the apply is ONE step with
ONE Undo; an import never deletes; a wrong-project id leaves that row out and says so (as on the other sheets).

Run: python3 dev/run_tests.py test_gantt_excel_import
"""
import shutil
import tempfile
import unittest
from pathlib import Path

import _paths  # noqa: F401
from _demo import USER, DemoStore
from clark import changes, excel, excel_client
from clark import excel_import as xi
from clark import store as store_module
from openpyxl import Workbook, load_workbook

ON = "2030-06-01"


def gid(n, code="ABC"):
    return f"{code}-GNT-{n:03d}"


class Base(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store
        self.tmp = Path(tempfile.mkdtemp(prefix="clark-gxi-"))
        self.addCleanup(shutil.rmtree, str(self.tmp), True)
        self.change = changes.make_change(self.s.path, [], USER)
        self.state = self.tmp / "state.json"
        self.n = 0

    def add(self, **values):
        status, body = self.change({"project": "ABC", "kind": "gantt_lines", "op": "new", "values": values})
        self.assertEqual(status, 200, body)
        return body["ref"]

    def twelve(self):
        """3 phases (1, 5, 9), 7 tasks, 2 milestones (4, 12), dependencies, owners, effort, budget, baselines; lines 5, 7, 10, 12 have the eye off."""
        extra = dict(owner="Sam", workstream="Build", priority="High", health="Green", baseline_start="2026-10-01", baseline_end="2026-10-09",
                     effort=12.5, budget=1000.5, deliverable="Thing", note="A note")
        spec = [("phase", "Alpha", None, 1), ("task", "Dig", 1, 1), ("task", "Pour", 1, 1), ("milestone", "Alpha done", 1, 1),
                ("phase", "Beta", None, 0), ("task", "Wire", 5, 1), ("task", "Plumb", 5, 0), ("task", "Cure", 5, 1),
                ("phase", "Gamma", None, 1), ("task", "Fit", 9, 0), ("task", "Finish", 9, 1), ("milestone", "Handover", 9, 0)]
        for i, (kind, name, parent, show) in enumerate(spec, start=1):
            start = f"2026-11-{i + 1:02d}"
            vals = dict(type=kind, name=name, start=start, end=start if kind == "milestone" else f"2026-11-{i + 6:02d}", show=show, pct=5 * i, **extra)
            if parent:
                vals["parent"] = gid(parent)
            self.add(**vals)
        for i, dep in ((2, gid(3)), (6, f"{gid(7)},{gid(3)}"), (11, f"{gid(10)},{gid(3)}")):       # a line may depend on one added after it
            status, body = self.change({"project": "ABC", "kind": "gantt_lines", "op": "update", "id": gid(i), "changes": {"depends": dep}})
            self.assertEqual(status, 200, body)

    def export(self, name="out.xlsx"):
        path = self.tmp / name
        excel.export_project(self.s, "ABC", path, self.state, on=ON)
        return path

    def lines(self, project="ABC"):
        return {r["id"]: {k: v for k, v in r.items() if k != "updated_at"} for r in self.s.read("gantt_lines", project=project)}

    def edit(self, path, ref, **cells):
        wb = load_workbook(str(path))
        ws = wb["Gantt"]
        head = {c.value: c.column for c in ws[1]}
        row = next(r for r in range(2, ws.max_row + 1) if ws.cell(r, 1).value == ref)
        for label, value in cells.items():
            ws.cell(row, head[label]).value = value
        wb.save(str(path))
        return row

    def plan(self, path, project="ABC"):
        return xi.read_workbook(self.s, path, project, state_path=self.state, allow_unrecorded=True)

    def apply(self, path):
        p = self.plan(path)
        p.accept_all()
        return xi.apply_import(self.s, p, USER, state_path=self.state), p

    def steps(self):
        return self.s.con.execute("SELECT count(*) FROM applies").fetchone()[0]


class RoundTrip(Base):
    def test_the_same_workbook_changes_nothing_and_takes_no_step(self):
        self.twelve()
        before, steps = self.lines(), self.steps()
        res, p = self.apply(self.export())
        self.assertEqual((p.counts(), p.problems), ({"new": 0, "changed": 0, "removed": 0}, []))
        self.assertGreaterEqual(p.unchanged, 12)
        self.assertFalse(res.applied)
        self.assertEqual((self.lines(), self.steps()), (before, steps))

    def test_the_workbook_into_an_empty_project_of_the_same_code_makes_the_same_lines(self):
        self.twelve()
        path, want = self.export(), self.lines()
        other = DemoStore()
        self.addCleanup(other.close)
        # the same code, nothing in it: the lines are made with the same data, the ids given again from 001
        res = xi.apply_import(other.store, self._plan(other.store, path), USER, state_path=self.tmp / "other.json")
        self.assertTrue(res.applied, res.message)
        got = {r["id"]: {k: v for k, v in r.items() if k != "updated_at"} for r in other.store.read("gantt_lines", project="ABC")}
        self.assertEqual(got, want)

    def _plan(self, store, path):
        p = xi.read_workbook(store, path, "ABC", state_path=self.tmp / "other.json", allow_unrecorded=True)
        self.assertEqual((p.counts()["new"], p.problems), (12, []))
        p.accept_all()
        return p

    def test_a_workbook_without_a_gantt_sheet_imports_as_before(self):
        wb = Workbook()
        wb.active.title = "Actions"
        wb.active.append(["ID", "Description"])
        path = self.tmp / "plain.xlsx"
        wb.save(str(path))
        p = self.plan(path)
        self.assertEqual([c for c in p.changes if c.table == "gantt_lines"], [])


class Edits(Base):
    def test_edited_cells_update_exactly_that_line_in_one_step_and_one_undo_puts_all_back(self):
        self.twelve()
        before = self.lines()
        path = self.export()
        self.edit(path, gid(2), **{"End": __import__("datetime").date(2026, 11, 20), "Done %": 80, "Line": "Dig deeper", "Depends on": f"{gid(3)}, {gid(4)}",
                                   "On dashboard": "No"})
        steps = self.steps()
        res, p = self.apply(path)
        self.assertTrue(res.applied, res.message)
        self.assertEqual((p.counts(), self.steps()), ({"new": 0, "changed": 1, "removed": 0}, steps + 1))
        now = self.lines()
        self.assertEqual({k: v for k, v in now[gid(2)].items() if before[gid(2)][k] != v},
                         {"end": "2026-11-20", "pct": 80, "name": "Dig deeper", "depends": f"{gid(3)},{gid(4)}", "show": 0})
        self.assertEqual({k: v for k, v in now.items() if k != gid(2)}, {k: v for k, v in before.items() if k != gid(2)})
        from clark import excel_route
        undone = excel_route._undo(self.s, USER, {"apply_id": res.step_id}, "ABC")
        self.assertEqual(undone[0], 200)
        self.assertEqual(self.lines(), before)

    def test_days_and_status_edits_are_ignored(self):
        self.twelve()
        path = self.export()
        self.edit(path, gid(2), **{"Days": 99, "Status": "Done"})
        res, p = self.apply(path)
        self.assertEqual((p.counts()["changed"], res.applied), (0, False))

    def test_a_new_row_makes_a_line_with_the_next_free_id_and_a_line_missing_is_not_deleted(self):
        self.twelve()
        path = self.export()
        wb = load_workbook(str(path))
        ws = wb["Gantt"]
        head = {c.value: c.column for c in ws[1]}
        ws.delete_rows(2)                           # line 1 is missing from the sheet
        row = ws.max_row + 1
        for label, v in {"ID": "TBD", "Line": "Extra", "Type": "Task", "Start": __import__("datetime").date(2026, 12, 1),
                         "End": __import__("datetime").date(2026, 12, 3), "On dashboard": "Yes"}.items():
            ws.cell(row, head[label]).value = v
        wb.save(str(path))
        res, p = self.apply(path)
        self.assertTrue(res.applied, res.message)
        self.assertEqual(p.counts()["new"], 1)
        self.assertIn(gid(13), self.lines())
        self.assertEqual((self.lines()[gid(13)]["name"], self.lines()[gid(13)]["show"], self.lines()[gid(13)]["pct"]), ("Extra", 1, 0))
        self.assertIn(gid(1), self.lines())

    def test_the_typed_id_of_a_new_row_is_not_taken(self):
        self.twelve()
        path = self.export()
        self.edit(path, gid(12), ID=gid(40))
        p = self.plan(path)
        self.assertEqual([c.kind for c in p.changes], ["new"])
        self.assertTrue(p.changes[0].preview.endswith("013"))


class Refusals(Base):
    def refused(self, why, **cells):
        self.twelve()
        before, steps = self.lines(), self.steps()
        path = self.export()
        row = self.edit(path, gid(3), **cells)
        p = self.plan(path)
        bad = [c for c in p.changes if c.problem]
        self.assertEqual(len(bad), 1, p.report())
        self.assertEqual((bad[0].problem, bad[0].row), (why, row))
        self.assertIn(f"row {row} of Gantt", bad[0].describe())
        p.accept_all()
        res = xi.apply_import(self.s, p, USER, state_path=self.state)
        self.assertFalse(res.applied)
        self.assertEqual((self.lines(), self.steps()), (before, steps))

    def test_a_bad_date(self):
        self.refused(store_module.GANTT_BAD_DATE, Start="not a date")

    def test_end_before_start(self):
        self.refused(store_module.GANTT_END_BEFORE_START, End=__import__("datetime").date(2026, 1, 1))

    def test_done_101(self):
        self.refused(store_module.GANTT_BAD_PCT, **{"Done %": 101})

    def test_effort_over_the_limit(self):
        self.refused(store_module.GANTT_BAD_NUMBER, **{"Effort (days)": 2000000})

    def test_budget_1e99(self):
        self.refused(store_module.GANTT_BAD_NUMBER, Budget=1e99)

    def test_a_parent_that_is_not_a_phase(self):
        self.refused(store_module.GANTT_PARENT_PHASE, Parent=gid(2))

    def test_a_depends_loop(self):
        self.refused(store_module.GANTT_LOOP, **{"Depends on": gid(2)})      # 2 already depends on 3

    def test_an_unknown_type(self):
        self.refused(store_module.GANTT_BAD_TYPE, Type="Epic")

    def test_a_missing_name(self):
        self.refused(store_module.GANTT_NO_NAME, Line=None)

    def test_a_formula_cell_is_not_read(self):
        self.twelve()
        path = self.export()
        wb = load_workbook(str(path))
        ws = wb["Gantt"]
        ws.cell(3, 2).value = "=1+1"
        wb.save(str(path))
        self.assertEqual(ws.cell(3, 2).data_type, "f")
        p = self.plan(path)
        self.assertEqual(p.counts()["changed"], 0)
        self.assertTrue(any("formula" in n for n in p.notes))

    def test_a_10000_character_text_is_refused(self):
        self.refused(store_module.GANTT_BAD_TEXT, Notes="x" * 10000)

    def test_another_projects_id_leaves_the_row_out_and_changes_nothing(self):
        self.twelve()
        with self.s.step("dashboard", USER) as st:
            st.create("projects", {"code": "DEF", "name": "Other Programme"})
            st.create("gantt_lines", {"project": "DEF", "type": "task", "name": "Theirs", "start": "2026-11-02",
                                      "end": "2026-11-03", "sort_order": 1024})
        theirs, mine = self.lines("DEF"), self.lines()
        path = self.export()
        self.edit(path, gid(2), ID=gid(1, "DEF"), Line="Hijack")
        p = self.plan(path)
        self.assertTrue(any("belongs to project DEF" in x.message and x.row for x in p.problems))
        p.accept_all()
        xi.apply_import(self.s, p, USER, state_path=self.state)
        self.assertEqual(self.lines("DEF"), theirs)
        self.assertEqual(self.lines(), mine)

    def test_the_client_workbook_sheet_is_refused(self):
        self.twelve()
        self.s.read("projects", ref="ABC")
        wb = Workbook()
        ws = wb.active
        ws.title = "Gantt"
        ws.append(["Example Programme"])
        ws.append(["As at 01-06-2030"])
        ws.append([])
        ws.append(["ID", "Line", "Type", "Start", "End"])
        ws.append([gid(1), "Hijack", "Phase", __import__("datetime").date(2026, 11, 2), __import__("datetime").date(2026, 11, 9)])
        path = self.tmp / "client.xlsx"
        wb.save(str(path))
        before = self.lines()
        p = self.plan(path)
        self.assertEqual(p.changes, [])
        self.assertTrue(any("no id column" in x.message for x in p.problems))
        self.assertEqual(self.lines(), before)

    def client_copy(self, name="client.xlsx", band=True, mark=True):
        """The client workbook built by the export (the lines of this project, ids as stored), saved to a file. band=False deletes the
        3 title rows so the header is row 1; mark=False removes the client copy mark."""
        import io
        import test_gantt_excel_export as ge
        from clark import publish
        self.twelve()
        inputs = ge.plant(gantt_tab_name="Gantt")
        inputs["data"]["project"]["code"] = "ABC"
        inputs["data"]["gantt_lines"] = [{k: (v.replace("PUB-", "ABC-") if isinstance(v, str) else v) for k, v in r.items()} | {"project": "ABC"}
                                         for r in inputs["data"]["gantt_lines"]]
        wb = load_workbook(io.BytesIO(excel_client.workbook_bytes(publish.select(inputs))))
        self.assertIn(excel.CLIENT_COPY_NAME, wb.defined_names)
        if not band:
            wb["Gantt"].delete_rows(1, 3)
        if not mark:
            del wb.defined_names[excel.CLIENT_COPY_NAME]
        path = self.tmp / name
        wb.save(str(path))
        return path

    def test_a_client_copy_imported_by_hand_is_refused_and_nothing_is_written(self):
        path = self.client_copy()
        before, steps = self.lines(), self.steps()
        p = self.plan(path)
        self.assertEqual(p.changes, [])
        self.assertTrue(any("Gantt: there is no id column, so the sheet was skipped (every row would look new)" in x.message for x in p.problems), p.problems)
        self.assertEqual((self.lines(), self.steps()), (before, steps))

    def test_a_client_copy_with_the_title_band_deleted_is_still_refused_by_the_mark(self):
        path = self.client_copy(band=False)
        before = self.lines()
        p = self.plan(path)
        self.assertEqual(p.changes, [])
        self.assertTrue(any(x.sheet == "Gantt" and "there is no id column" in x.message for x in p.problems), p.problems)
        self.assertEqual(self.lines(), before)

    def test_without_the_mark_only_the_layout_rule_refuses_a_client_copy(self):
        self.assertTrue(any(x.sheet == "Gantt" and "there is no id column" in x.message for x in self.plan(self.client_copy(mark=False)).problems))       # the band is row 1
        p = self.plan(self.client_copy("moved.xlsx", band=False, mark=False))                                                       # header in row 1: read
        self.assertFalse(any(x.sheet == "Gantt" for x in p.problems), p.problems)

    def test_an_editor_export_has_no_mark_and_still_imports(self):
        self.twelve()
        path = self.export()
        self.assertNotIn(excel.CLIENT_COPY_NAME, load_workbook(str(path)).defined_names)
        self.assertFalse(any(x.sheet == "Gantt" for x in self.plan(path).problems))

    def test_a_workbook_with_no_sheet_names_the_gantt_sheet_in_the_refusal(self):
        self.twelve()
        path = self.export()
        wb = load_workbook(str(path))
        for ws in wb.worksheets:
            ws.title = "Old " + ws.title
        wb.save(str(path))
        p = self.plan(path)
        self.assertEqual(p.changes, [])
        self.assertTrue(any("Milestones, Use cases or Gantt, so there is nothing to compare" in x.message for x in p.problems), p.problems)


class Isolation(Base):
    def test_importing_writes_no_client_file(self):
        self.twelve()
        path = self.export()
        self.edit(path, gid(2), **{"Done %": 50})
        files = sorted(p.name for p in self.tmp.iterdir())
        self.apply(path)
        self.assertEqual([n for n in sorted(p.name for p in self.tmp.iterdir()) if n not in files and n.endswith((".xlsx", ".docx", ".pdf", ".html"))], [])


if __name__ == "__main__":
    unittest.main()
