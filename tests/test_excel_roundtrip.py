"""#38: the round trip. A workbook written by the export (#37, src/clark/excel.py) is edited with openpyxl, as a person would edit
it in Excel, read by the import (src/clark/excel_import.py), applied as one step, and undone; the export's own guard
(edits not yet imported) lets go once the import has run.

Run: python3 dev/run_tests.py test_excel_roundtrip
"""
import atexit
import json
import re
import shutil
import zipfile
import tempfile
import unittest
from datetime import date, time
from pathlib import Path

import _paths  # noqa: F401  (puts src/ and vendor/ on the path)
from _demo import USER, DemoStore
from openpyxl import load_workbook

from clark import excel, sanitise
from clark import excel_import as xi
from clark import page
from clark.store import columns, open_store


_NO_BRAND = tempfile.mkdtemp(prefix="clark-no-brand-")    # a brand logo on this computer never changes a test (#133)


def setUpModule():
    global _OLD_BRANDING
    _OLD_BRANDING, page.BRANDING = page.BRANDING, Path(_NO_BRAND)


def tearDownModule():
    page.BRANDING = _OLD_BRANDING
    shutil.rmtree(_NO_BRAND, ignore_errors=True)


ON = "2030-06-01"
TABLES = ("actions", "raid", "decisions", "milestones", "use_cases", "item_labels")


def edit(path, sheet, item_id, **cells):
    """Set cells of the row with this ID, by the header LABEL the export writes (None clears a cell), as Excel would."""
    wb = load_workbook(str(path))
    ws = wb[sheet]
    head = {c.value: c.column for c in ws[1]}
    row = next(r for r in range(2, ws.max_row + 1) if ws.cell(r, head["ID"]).value == item_id)
    for label, value in cells.items():
        ws.cell(row, head[label]).value = value
    wb.save(str(path))


def add_row(path, sheet, **cells):
    """Append a row under the data, by header LABEL, with no ID (a new item), as a person typing under the table would."""
    wb = load_workbook(str(path))
    ws = wb[sheet]
    row = max(r for r in range(1, ws.max_row + 1) if ws.cell(r, 1).value is not None) + 1
    head = {c.value: c.column for c in ws[1]}
    for label, value in cells.items():
        ws.cell(row, head[label]).value = value
    wb.save(str(path))


def delete_row(path, sheet, item_id):
    wb = load_workbook(str(path))
    ws = wb[sheet]
    row = next(r for r in range(2, ws.max_row + 1) if ws.cell(r, 1).value == item_id)
    ws.delete_rows(row)
    wb.save(str(path))


def _build(demo, path, state):
    """The demo store's rows and the export of them, the same in every test of this file."""
    ids = {}
    with demo.store.step("dashboard", USER) as st:
        ids["a1"] = st.create("actions", {
            "project": "ABC", "description": "Draft the cut-over plan", "workstream": "Build", "owner": "Demo Owner",
            "priority": "High", "due_date": "2030-04-15", "raised": "2030-01-10", "latest_update": "First draft shared",
            "client_message": "The plan is being drafted", "milestone": demo.milestone,
            "use_case": demo.use_case, "labels": "Sensitive", "source": "demo"})
        ids["a2"] = st.create("actions", {"project": "ABC", "description": "Book the demo room", "raised": "2026-10-01",
                                          "client_visible": 0, "source": "demo"})
        ids["r1"] = st.create("raid", {"project": "ABC", "type": "Risk", "description": "Test data arrives late",
                                       "impact": "High", "likelihood": "Medium", "due_date": "2030-05-01",
                                       "response_action": "Ask for a sample early", "raised": "2030-01-12", "source": "demo"})
        ids["d1"] = st.create("decisions", {"project": "ABC", "decision": "Choose the second team", "status": "Pending",
                                            "needed_by": "2030-07-01", "source": "demo"})
        ids["m2"] = st.create("milestones", {"project": "ABC", "name": "Slipped milestone", "baseline_date": "2030-08-01",
                                             "forecast_date": "2030-08-20", "percent_complete": 40, "owner": "Demo Owner",
                                             "internal_note": "Keep an eye", "source": "demo"})
    # the demo milestone is rebaselined, so its Original column differs from its Baseline (and a decision is recorded)
    demo.update("milestones", demo.milestone, {"baseline_date": "2030-04-01"},
                rebaseline={"agreed_with": "Demo Sponsor", "reason": "Scope grew", "source": "Steering, 01-02-2030"})
    excel.export_project(demo.store, "ABC", path, state, on=ON)
    return ids


_TEMPLATE = {}


def _template():
    """The store, its workbook and the state file of _build, made once (the export is the slow part, about 1.5 s) and kept as
    files; every test starts from a copy of them, so each still has a store, a workbook and a state file of its own."""
    if not _TEMPLATE:
        folder = Path(tempfile.mkdtemp(prefix="clark-roundtrip-template-"))
        demo = DemoStore()
        try:
            ids = _build(demo, folder / "ABC work items.xlsx", folder / "state.json")
            demo.store.close()
            shutil.copy(demo.dir / "clark.db", folder / "clark.db")
            _TEMPLATE.update(folder=folder, ids=ids, milestone=demo.milestone, use_case=demo.use_case)
        finally:
            shutil.rmtree(demo.dir, ignore_errors=True)
    return _TEMPLATE


@atexit.register
def _drop_template():       # at exit, not in tearDownModule: test_excel_refs also builds on RoundTrip
    if _TEMPLATE:
        shutil.rmtree(_TEMPLATE["folder"], ignore_errors=True)
        _TEMPLATE.clear()


class RoundTrip(unittest.TestCase):
    def setUp(self):
        t = _template()
        self.demo = DemoStore.__new__(DemoStore)      # DemoStore, opened on a copy of the template's database
        self.demo.dir = Path(tempfile.mkdtemp(prefix="clark-test-"))
        shutil.copy(t["folder"] / "clark.db", self.demo.dir / "clark.db")
        self.demo.store = open_store(self.demo.dir / "clark.db", onedrive_roots=[])
        self.demo.milestone, self.demo.use_case = t["milestone"], t["use_case"]
        self.s = self.demo.store
        self.dir = Path(tempfile.mkdtemp(prefix="clark-roundtrip-"))
        self.path = self.dir / "ABC work items.xlsx"
        self.state = self.dir / "state.json"
        shutil.copy(t["folder"] / "ABC work items.xlsx", self.path)
        # the state file is keyed by the workbook's path: the copy's, not the template's
        old = json.loads((t["folder"] / "state.json").read_text(encoding="utf-8"))
        template_path = excel._key(t["folder"] / "ABC work items.xlsx")      # the state file keys a path resolved (/private/var on a Mac), as excel._key does
        record = old["workbooks"][template_path]
        keyed = {k: v for k, v in old["workbooks"].items() if k.startswith(excel.KEYED)}     # keep the export's id: and sha256: keys: excel._find looks a workbook up by its id first
        self.state.write_text(json.dumps({**old, "workbooks": {**keyed, excel._key(self.path): record}}, indent=1, ensure_ascii=False),
                              encoding="utf-8")
        for name, value in t["ids"].items():
            setattr(self, name, value)

    def tearDown(self):
        self.demo.close()
        shutil.rmtree(self.dir, ignore_errors=True)

    def read(self):
        return xi.read_workbook(self.s, self.path, "ABC", state_path=self.state)

    def steps(self):
        return self.s.con.execute("SELECT count(*) FROM applies").fetchone()[0]

    def snapshot(self):
        """Every table the import can touch, without updated_at (an Undo restores values, not the time it was undone)."""
        return {t: sorted(({k: v for k, v in r.items() if k != "updated_at"} for r in self.s.read(t)),
                          key=lambda r: json.dumps(r, sort_keys=True, default=str)) for t in TABLES}

    def export_again(self):
        return excel.export_project(self.s, "ABC", self.path, self.state, on=ON)

    def edited(self):
        """The usual few edits: an action's owner and due date, a decision's status, a cleared nullable cell."""
        edit(self.path, "Actions", self.a1, Owner="Sam Example", Due=date(2030, 5, 20), **{"Latest update": None})
        edit(self.path, "Decisions", self.d1, Status="Withdrawn")

    # Row 966 follow-up: a long text the store holds is no change when the workbook gives it back; a time or an Excel day 60 is named or refused.

    def long_text(self, n):
        with self.s.step("dashboard", USER) as st:
            st.update("actions", self.a1, {"description": "x" * n})
        self.export_again()

    def problems(self):
        return [p.message for p in self.read().problems]



class FormulaGuard(unittest.TestCase):
    """Text that could be a formula is written as a text cell, as typed; the import must give it back unchanged."""

    TEXTS = ("=1+1", "+1", "-cmd", "@SUM(A1)", "'quoted", "'=1", "a=b", "-5", " =1", "x ", "  padded  ", " 'q")

    def test_text_that_looks_like_a_formula_round_trips_without_a_change(self):
        demo = DemoStore()
        tmp = Path(tempfile.mkdtemp(prefix="clark-formula-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        self.addCleanup(demo.close)
        with demo.store.step("dashboard", USER) as st:
            ids = [st.create("actions", {"project": "ABC", "description": text, "raised": "2026-10-01", "source": "demo"})
                   for text in self.TEXTS]
        path, state = tmp / "ABC work items.xlsx", tmp / "state.json"
        excel.export_project(demo.store, "ABC", path, state, on=ON)
        plan = xi.read_workbook(demo.store, path, "ABC")
        self.assertEqual([c for c in plan.changes if c.kind != "unchanged"], [], "no false change from the apostrophes")
        edit(path, "Actions", ids[0], Owner="Sam Example")                # an ordinary edit still imports, text intact
        plan = xi.read_workbook(demo.store, path, "ABC")
        plan.accept_all()
        xi.apply_import(demo.store, plan, USER, state_path=state)
        got = {r["id"]: r["description"] for r in demo.store.read("actions", "ABC") if r["id"] in ids}
        self.assertEqual([got[i] for i in ids], list(self.TEXTS))


class RichFields(unittest.TestCase):
    """Row 1005: Latest update and Description are the editor's HTML (or an older plain text). The sheet carries their words, and an unchanged sheet imports with no change."""

    def test_the_sheet_holds_the_words_and_an_unchanged_export_imports_as_no_change(self):
        demo = DemoStore()
        tmp = Path(tempfile.mkdtemp(prefix="clark-rich-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        self.addCleanup(demo.close)
        with demo.store.step("dashboard", USER) as st:
            a_new = st.create("actions", {"project": "ABC", "description": "One", "raised": "2026-10-01", "source": "demo",
                                          "latest_update": "<p>Done &amp; dusted</p><p>Next: a &lt; b</p>"})
            a_old = st.create("actions", {"project": "ABC", "description": "Two", "raised": "2026-10-01", "source": "demo",
                                          "latest_update": 'old < new & "q"\nline two'})
            st.update("milestones", demo.milestone, {"description": "<p>Scope <strong>bold</strong></p>"})
        path, state = tmp / "ABC work items.xlsx", tmp / "state.json"
        excel.export_project(demo.store, "ABC", path, state, on=ON)
        wb = load_workbook(str(path))
        head = {c.value: c.column for c in wb["Actions"][1]}
        cells = {wb["Actions"].cell(r, 1).value: wb["Actions"].cell(r, head["Latest update"]).value for r in range(2, wb["Actions"].max_row + 1)}
        self.assertEqual(cells[a_new], "Done & dusted\nNext: a < b")
        self.assertEqual(cells[a_old], 'old < new & "q"\nline two')
        mhead = {c.value: c.column for c in wb["Milestones"][1]}
        self.assertEqual([wb["Milestones"].cell(r, mhead["Description"]).value for r in range(2, wb["Milestones"].max_row + 1) if wb["Milestones"].cell(r, 1).value == demo.milestone], ["Scope bold"])
        plan = xi.read_workbook(demo.store, path, "ABC", state_path=state)
        self.assertEqual([c for c in plan.changes if c.kind != "unchanged"], [], "the words round trip with no false change")
        edit(path, "Actions", a_new, **{"Latest update": "Rewritten in Excel"})
        plan = xi.read_workbook(demo.store, path, "ABC", state_path=state)
        self.assertEqual([c.id for c in plan.changes if c.kind == "changed"], [a_new], "a real edit is staged, and only that one")


class Reading(RoundTrip):
    def test_every_exported_label_reads_back_as_a_column_a_derived_field_or_labels(self):
        for table, labels in excel.COLUMN_OF.items():
            for label, f in labels.items():
                self.assertTrue(f in columns(self.s.con, table) or f in excel.DERIVED or f in (xi.LABELS, xi.UC_MILESTONES), (table, label, f))
        self.assertEqual({t: excel.SHEET_OF[t] for t in excel.TABLES},
                         {"milestones": "Milestones", "actions": "Actions", "raid": "Risks & Issues", "decisions": "Decisions",
                          "use_cases": "Use cases"})

    def test_an_unchanged_export_imports_as_no_changes_and_nothing_is_ignored(self):
        p = self.read()
        self.assertEqual((p.changes, p.problems), ([], []))
        self.assertEqual([n for n in p.notes if "ignored" in n], [])
        self.assertEqual(p.unchanged, 8)      # 2 actions, 1 risk, 2 decisions (one from the rebaseline), 2 milestones, 1 use case

    def test_the_two_worked_out_columns_are_never_read_back(self):
        edit(self.path, "Milestones", self.m2, Original=date(2031, 1, 1), **{"State": "Achieved"})
        p = self.read()
        self.assertEqual((p.changes, p.problems), ([], []))

    def test_labels_flags_and_dates_typed_as_text_are_read(self):
        edit(self.path, "Actions", self.a1, Due="20-05-2030", **{"Client visible": "No", "Labels": None})
        (c,) = self.read().changes
        self.assertEqual(c.after, {"due_date": "2030-05-20", "client_visible": 0, "labels": None})
        edit(self.path, "Actions", self.a1, Labels="sensitive")          # the same label in another case: no change on its own
        (c,) = self.read().changes
        self.assertNotIn("labels", c.after)

    def test_a_milestone_agreed_date_edit_in_the_workbook_is_ignored_with_a_note(self):
        edit(self.path, "Milestones", self.m2, Agreed=date(2030, 9, 1), Owner="Sam Example")
        p = self.read()
        (c,) = p.changes
        self.assertEqual(c.after, {"owner": "Sam Example"})
        self.assertTrue(any("rebaseline" in n for n in p.notes))

    def test_database_column_names_still_work_as_headers(self):
        wb = load_workbook(str(self.path))
        ws = wb["Actions"]
        for c in ws[1]:
            c.value = {"ID": "id", "Owner": "owner"}.get(c.value, c.value)
        wb.save(str(self.path))
        edit_wb = load_workbook(str(self.path))
        edit_wb["Actions"].cell(2, 5).value = "Sam Example"
        edit_wb.save(str(self.path))
        (c,) = self.read().changes
        self.assertEqual((c.id, c.after), (self.a1, {"owner": "Sam Example"}))


class Importing(RoundTrip):
    def test_edit_import_and_undo_restores_the_store_in_one_step(self):
        before, n = self.snapshot(), self.steps()
        self.edited()
        p = self.read()
        self.assertEqual(p.problems, [])
        self.assertEqual({(c.id, tuple(c.after)) for c in p.changes},
                         {(self.a1, ("owner", "due_date", "latest_update")), (self.d1, ("status",))})
        p.accept_all()
        res = xi.apply_import(self.s, p, USER, state_path=self.state)
        self.assertTrue(res.applied, res.message)
        self.assertEqual(res.counts, {"new": 0, "changed": 2, "removed": 0})
        a = self.s.read("actions", ref=self.a1)
        self.assertEqual((a["owner"], a["due_date"], a["latest_update"]), ("Sam Example", "2030-05-20", None))
        self.assertEqual(self.s.read("decisions", ref=self.d1)["status"], "Withdrawn")
        self.assertEqual(self.steps(), n + 1)
        self.assertEqual(res.step_id, self.demo.last_step())
        out = self.s.undo(res.step_id, USER)
        self.assertEqual(out["skipped"], [])
        self.assertEqual(self.snapshot(), before)

    def test_an_edited_dropdown_value_imports(self):
        """A priority and a status changed to another listed value (as picking from the drop-down does) are staged, and only those."""
        edit(self.path, "Actions", self.a1, Priority="Low")
        edit(self.path, "Decisions", self.d1, Status="Withdrawn")
        p = self.read()
        self.assertEqual(p.problems, [])
        self.assertEqual({(c.id, tuple(c.after)) for c in p.changes},
                         {(self.a1, ("priority",)), (self.d1, ("status",))})

    def test_a_labels_edit_is_applied_and_undone_too(self):
        before = self.snapshot()
        edit(self.path, "Actions", self.a1, Labels=None)
        p = self.read()
        p.accept_all()
        res = xi.apply_import(self.s, p, USER, state_path=self.state)
        self.assertTrue(res.applied, res.message)
        self.assertEqual(self.s.read("item_labels"), [])
        self.s.undo(res.step_id, USER)
        self.assertEqual(self.snapshot(), before)

    def test_a_row_deleted_in_the_sheet_is_staged_as_removed_and_applied_as_archived(self):
        delete_row(self.path, "Actions", self.a2)
        p = self.read()
        (c,) = p.changes
        self.assertEqual((c.kind, c.id), ("removed", self.a2))
        p.accept_all()
        self.assertEqual(p.accepted(), [])                                               # never accepted in bulk
        p.accept(c.n)
        res = xi.apply_import(self.s, p, USER, state_path=self.state)
        self.assertTrue(res.applied, res.message)
        row = self.s.read("actions", ref=self.a2)
        self.assertEqual((row["status"], row["archived"]), ("Open", 1))
        self.s.undo(res.step_id, USER)
        self.assertEqual(self.s.read("actions", ref=self.a2)["status"], "Open")

    def test_a_new_row_typed_under_the_data_is_added(self):
        wb = load_workbook(str(self.path))
        ws = wb["Actions"]
        head = {c.value: c.column for c in ws[1]}
        row = ws.max_row + 1
        ws.cell(row, head["Title"]).value = "Order the laptops"
        ws.cell(row, head["Owner"]).value = "Sam Example"
        wb.save(str(self.path))
        p = self.read()
        (c,) = p.changes
        self.assertEqual((c.kind, c.table), ("new", "actions"))
        p.accept_all()
        res = xi.apply_import(self.s, p, USER, state_path=self.state)
        self.assertTrue(res.applied, res.message)
        (new,) = [a for a in self.s.read("actions", project="ABC") if a["description"] == "Order the laptops"]
        self.assertEqual((new["owner"], new["id"] not in (self.a1, self.a2)), ("Sam Example", True))

    def test_a_bad_value_is_reported_with_the_id_and_field_and_nothing_is_applied(self):
        edit(self.path, "Actions", self.a1, Owner="Sam Example")                       # fine
        edit(self.path, "Actions", self.a2, Status="Finished")                         # not a status
        edit(self.path, "Decisions", self.d1, Status="Maybe")                          # nor this
        p = self.read()
        self.assertEqual({c.id for c in p.changes if c.problem}, {self.a2, self.d1})
        p.accept(*[c.n for c in p.changes])                                            # accepted, bad rows too
        before, n = self.snapshot(), self.steps()
        res = xi.apply_import(self.s, p, USER, state_path=self.state)
        self.assertFalse(res.applied)
        self.assertEqual({(x.id, x.field) for x in res.problems}, {(self.a2, "status"), (self.d1, "status")})
        self.assertIn(self.a2, res.message)
        self.assertEqual((self.snapshot(), self.steps()), (before, n))
        self.assertFalse(res.marked)

    def test_a_date_that_is_not_a_date_is_reported_with_the_id_and_field(self):
        edit(self.path, "Actions", self.a1, Due="next week")
        p = self.read()
        self.assertEqual(p.changes, [])
        self.assertEqual([(x.id, x.field) for x in p.problems], [(self.a1, "due_date")])


class ClientView(RoundTrip):
    """The import honours the Client visible column: Yes shows, No hides, a blank cell shows, for a use case as for a work item.
    (A use case added by hand in clark starts hidden; an Excel import does not follow that, it follows the column.)"""

    def add_all(self):
        """One new row per sheet for each of blank, Yes and No, as a person typing under the tables would."""
        wb = load_workbook(str(self.path))
        for n, cv in enumerate((None, "Yes", "No")):
            tag = {None: "blank", "Yes": "yes", "No": "no"}[cv]
            for sheet, cells in (("Use cases", {"Use case": f"UC {tag}", "Reference": f"9.{n}", "Status": "On track"}),
                                 ("Actions", {"Title": f"A {tag}"}),
                                 ("Risks & Issues", {"Type": "Risk", "Title": f"R {tag}", "Impact": "High", "Likelihood": "Low"}),
                                 ("Decisions", {"Decision": f"D {tag}", "Status": "Pending"})):
                ws = wb[sheet]
                head = {c.value: c.column for c in ws[1]}
                row = ws.max_row + 1                    # under the data, one row per cell set; no ID, so a new item
                for label, value in {**cells, ("On the dashboard" if sheet == "Use cases" else "Client visible"): cv}.items():
                    ws.cell(row, head[label]).value = value
        wb.save(str(self.path))

    def seen(self):
        title = {"use_cases": "title", "actions": "description", "raid": "description", "decisions": "decision"}
        return {(t, r[col]): r["client_visible"] for t, col in title.items() for r in self.s.read(t, project="ABC")
                if str(r[col]).split(" ")[-1] in ("blank", "yes", "no")}

    def test_yes_no_and_blank_for_use_cases_and_work_items(self):
        self.add_all()
        p = self.read()
        self.assertEqual(p.problems, [])
        p.accept_all()
        res = xi.apply_import(self.s, p, USER, state_path=self.state)
        self.assertTrue(res.applied, res.message)
        want = {"blank": 1, "yes": 1, "no": 0}
        self.assertEqual(self.seen(), {(t, f"{pre} {tag}"): v for t, pre in (("use_cases", "UC"), ("actions", "A"), ("raid", "R"),
                                                                              ("decisions", "D")) for tag, v in want.items()})

    def test_the_whole_import_is_taken_back_by_one_undo(self):
        before, n = self.snapshot(), self.steps()
        self.add_all()
        p = self.read()
        p.accept_all()
        res = xi.apply_import(self.s, p, USER, state_path=self.state)
        self.assertTrue(res.applied, res.message)
        self.assertEqual((len(self.seen()), self.steps()), (12, n + 1))
        self.assertEqual(self.s.undo(res.step_id, USER)["skipped"], [])
        self.assertEqual((self.seen(), self.snapshot()), ({}, before))

    def test_an_exported_file_comes_back_with_the_same_visibility(self):
        with self.s.step("dashboard", USER) as st:
            st.update("use_cases", self.demo.use_case, {"client_visible": 0})
        self.export_again()
        ws = load_workbook(str(self.path))["Use cases"]
        head = {c.value: c.column for c in ws[1]}
        self.assertEqual(ws.cell(2, head["On the dashboard"]).value, "No")
        before = self.snapshot()
        p = self.read()
        self.assertEqual((p.changes, p.problems), ([], []))
        edit(self.path, "Use cases", self.demo.use_case, **{"On the dashboard": "Yes"})
        edit(self.path, "Actions", self.a2, **{"Client visible": "Yes"})
        p = self.read()
        p.accept_all()
        res = xi.apply_import(self.s, p, USER, state_path=self.state)
        self.assertTrue(res.applied, res.message)
        self.assertEqual([self.s.read("use_cases", ref=self.demo.use_case)["client_visible"],
                          self.s.read("actions", ref=self.a2)["client_visible"]], [1, 1])
        self.s.undo(res.step_id, USER)
        self.assertEqual(self.snapshot(), before)


class Refusal(RoundTrip):
    def test_a_store_that_refuses_to_open_the_step_gives_a_plain_result_and_the_workbook_is_not_marked(self):
        self.edited()
        p = self.read()
        p.accept_all()
        before, n, held = self.snapshot(), self.steps(), excel.load_state(self.state, self.path)

        class Refusing:                      # a store whose step() is refused on entry (as a failed backup will be, #86)
            path = self.s.path

            def __init__(self, real):
                self.real = real

            def step(self, *a, **k):
                raise xi.Invalid("The backup could not be made, so nothing was changed.")

            def __getattr__(self, name):
                return getattr(self.real, name)

        marked = []
        real_mark = excel.mark_imported
        excel.mark_imported = lambda *a, **k: marked.append(a)
        try:
            res = xi.apply_import(Refusing(self.s), p, USER, state_path=self.state)
        finally:
            excel.mark_imported = real_mark
        self.assertFalse(res.applied or res.marked)
        self.assertIsNone(res.step_id)
        self.assertIn("The backup could not be made", res.message)
        self.assertEqual(marked, [])
        self.assertEqual((self.snapshot(), self.steps()), (before, n))
        self.assertEqual(excel.load_state(self.state, self.path), held)
        with self.assertRaises(excel.Refused):                    # still counts as having unimported edits
            self.export_again()


class Wording(RoundTrip):
    def test_an_unchanged_long_text_is_no_change_and_a_changed_one_is_refused(self):
        for n in (12000, 40000):
            self.long_text(n)
            plan = self.read()
            self.assertEqual([p.message for p in plan.problems], [], n)
            self.assertEqual(plan.changes, [], n)
        edit(self.path, "Actions", self.a1, Title="y" * 12000)
        self.assertTrue(any("too long (12,000 characters" in m for m in self.problems()))

    def test_a_time_in_a_date_cell_is_named_as_a_time(self):
        edit(self.path, "Actions", self.a1, Due=time(0, 0))
        self.assertTrue(any("(got 00:00)" in m for m in self.problems()), self.problems())

    def test_excel_day_60_and_a_negative_day_are_not_dates(self):
        for serial in (60, -5):
            edit(self.path, "Actions", self.a1, Due=date(2030, 5, 20))
            with zipfile.ZipFile(self.path) as z:
                parts = {n: z.read(n) for n in z.namelist()}
            sheet = "xl/worksheets/sheet%d.xml" % (load_workbook(str(self.path)).sheetnames.index("Actions") + 1)
            fixed = re.sub(rb"<v>%d</v>" % 47623, b"<v>%d</v>" % serial, parts[sheet])
            self.assertNotEqual(fixed, parts[sheet])
            parts[sheet] = fixed
            with zipfile.ZipFile(self.path, "w", zipfile.ZIP_DEFLATED) as z:
                for n, b in parts.items():
                    z.writestr(n, b)
            self.assertTrue(any("must be a date" in m for m in self.problems()), serial)

    def test_a_database_error_is_put_in_plain_words(self):
        self.edited()
        p = self.read()
        p.accept_all()

        class Locked:
            path = self.s.path

            def __init__(self, real):
                self.real = real

            def step(self, *a, **k):
                raise xi.sqlite3.OperationalError("database is locked")

            def __getattr__(self, name):
                return getattr(self.real, name)

        res = xi.apply_import(Locked(self.s), p, USER, state_path=self.state)
        self.assertFalse(res.applied)
        self.assertIn("in use by another program", res.message)
        self.assertNotIn("database is locked", res.message)


class UseCaseDone(RoundTrip):
    """#412: Done is a use case status. Chosen in the workbook it imports as Done; a Done use case exports as Done, in grey, and an
    unchanged workbook imports as no change at all."""

    def test_done_typed_in_the_workbook_imports_as_done_and_undoes(self):
        edit(self.path, "Use cases", self.demo.use_case, Status="Done")
        p = self.read()
        self.assertEqual(p.problems, [])
        p.accept_all()
        self.assertTrue(xi.apply_import(self.s, p, USER, state_path=self.state).applied)
        self.assertEqual(self.s.read("use_cases", ref=self.demo.use_case)["status"], "Done")

    def test_a_done_use_case_exports_as_done_in_grey_and_reads_back_unchanged(self):
        from clark import excel_colours as colours
        with self.s.step("dashboard", USER) as st:
            st.update("use_cases", self.demo.use_case, {"status": "Done"})
        self.export_again()
        ws = load_workbook(str(self.path))["Use cases"]
        head = {c.value: c.column for c in ws[1]}
        row = next(r for r in range(2, ws.max_row + 1) if ws.cell(r, head["ID"]).value == self.demo.use_case)
        cell = ws.cell(row, head["Status"])
        self.assertEqual(cell.value, "Done")
        rules = [r for cf in ws.conditional_formatting for r in cf.rules
                 if str(cf.sqref).startswith(cell.column_letter) and r.type == "cellIs" and r.formula == ['"Done"']]
        self.assertEqual(len(rules), 1, "one rule draws Done")
        self.assertEqual((rules[0].dxf.fill.bgColor.rgb[-6:], rules[0].dxf.font.color.rgb[-6:]), colours.hexes("grey"))
        p = self.read()
        self.assertEqual((p.changes, p.problems), ([], []))
        self.assertEqual(xi.read_workbook(self.s, self.path, "ABC", state_path=self.state).problems, [])

    def test_a_status_that_is_not_one_of_the_four_is_still_refused(self):
        edit(self.path, "Use cases", self.demo.use_case, Status="Finished")
        p = self.read()
        self.assertEqual([c.problem for c in p.changes], ["Status must be one of On track, Flag, High risk, Done (the cell says Finished)"])
        p.accept_all()
        xi.apply_import(self.s, p, USER, state_path=self.state)
        self.assertEqual(self.s.read("use_cases", ref=self.demo.use_case)["status"], "On track", "a change with a problem is not applied")


class RichText(RoundTrip):
    HOSTILE = '<p onerror="steal()">Live</p><script>alert(1)</script><img src=x onerror=alert(2)>'

    def import_standing(self, text):
        edit(self.path, "Use cases", self.demo.use_case, **{"Where it stands": text})
        p = self.read()
        p.accept_all()
        self.assertTrue(xi.apply_import(self.s, p, USER, state_path=self.state).applied)
        return self.s.read("use_cases", ref=self.demo.use_case)["standing"]

    def test_standing_goes_through_the_clean_rich_seam(self):
        seen = []
        real = xi.clean_rich
        xi.clean_rich = lambda field, text: seen.append(field) or "[cleaned] " + text
        try:
            stored = self.import_standing("Going well")
        finally:
            xi.clean_rich = real
        self.assertEqual(seen, ["standing"])
        self.assertEqual(stored, "[cleaned] Going well")
        self.assertEqual(xi.RICH_FIELDS, {"standing"})

    def test_the_seam_is_a_no_op_today_and_hostile_html_is_stored_as_typed(self):
        self.assertEqual(xi.clean_rich("standing", self.HOSTILE), self.HOSTILE)
        self.assertEqual(self.import_standing(self.HOSTILE), xi.clean_rich("standing", self.HOSTILE))

    def test_hostile_html_is_published_without_its_active_part(self):
        try:
            from clark import publish
        except ImportError:
            self.skipTest("clark.publish is not on this branch yet (#39); this test runs once it merges")
        stored = self.import_standing(self.HOSTILE)
        out = publish.clean_html(stored)
        for bad in ("<script", "onerror", "alert("):
            self.assertNotIn(bad, out)
        self.assertIn("Live", out)


class RichNote(RoundTrip):
    """Row 1005: the Internal note is the editor's HTML now (or plain text from before). The sheet carries its WORDS; the import compares a
    cell with the words, so an export that is imported untouched changes nothing, and an edited cell is a change."""
    HTML = "<p>Keep &amp; watch &lt;b&gt;</p><p>second line</p>"
    WORDS = "Keep & watch <b>\nsecond line"

    def cell(self):
        wb = load_workbook(str(self.path))
        ws = wb["Milestones"]
        head = {c.value: c.column for c in ws[1]}
        row = next(r for r in range(2, ws.max_row + 1) if ws.cell(r, 1).value == self.m2)
        return ws.cell(row, head["Internal note"]).value

    def set_note(self, text):
        with self.s.step("dashboard", USER) as st:
            st.update("milestones", self.m2, {"internal_note": text})
        self.export_again()

    def test_the_sheet_holds_the_words_not_the_markup(self):
        self.set_note(self.HTML)
        self.assertEqual(self.cell(), self.WORDS)
        self.set_note("an old plain note\nwith < and &")
        self.assertEqual(self.cell(), "an old plain note\nwith < and &")

    def test_an_untouched_export_imports_as_no_change(self):
        for stored in (self.HTML, "an old plain note\nwith < and &"):
            self.set_note(stored)
            p = self.read()
            self.assertEqual([c for c in p.changes if c.id == self.m2], [], stored)
            self.assertEqual(p.problems, [])

    def test_an_edited_cell_is_one_change_and_reads_as_the_words_typed(self):
        self.set_note(self.HTML)
        edit(self.path, "Milestones", self.m2, **{"Internal note": "New <i>words</i>\nand more"})
        p = self.read()
        self.assertEqual([tuple(c.after) for c in p.changes if c.id == self.m2], [("internal_note",)])
        p.accept_all()
        self.assertTrue(xi.apply_import(self.s, p, USER, state_path=self.state).applied)
        stored = self.s.read("milestones", ref=self.m2)["internal_note"]
        self.assertEqual(sanitise.rich_plain_text(stored), "New <i>words</i>\nand more")
        self.assertEqual(sanitise.rich_or_plain(stored), "<p>New &lt;i&gt;words&lt;/i&gt;</p><p>and more</p>", "an old-style plain text still reads, escaped")


class TooBig(RoundTrip):
    def bomb(self, name="bomb.xlsx", size=60 * 1024 * 1024, members=1):
        path = self.dir / name
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
            for i in range(members):
                z.writestr(f"xl/worksheets/sheet{i}.xml", b"\0" * (size // members))
        return path

    def test_a_small_file_that_unpacks_to_a_huge_one_is_refused_in_plain_words_before_it_is_opened(self):
        path = self.bomb()
        self.assertLess(path.stat().st_size, 5 * 1024 * 1024)
        for call in (lambda: xi.read_workbook(self.s, path, "ABC", state_path=self.state), lambda: excel.read_workbook(path)):
            with self.assertRaises((xi.Invalid, excel.Refused)) as cm:
                call()
            self.assertIn("would unpack to", str(cm.exception))
            self.assertIn("bomb.xlsx", str(cm.exception))

    def test_one_member_over_its_limit_or_too_many_members_is_refused(self):
        with self.assertRaises(xi.Invalid):
            xi.read_workbook(self.s, self.bomb("one.xlsx", size=excel.MAX_MEMBER_BYTES + 1), "ABC", state_path=self.state)
        with self.assertRaises(xi.Invalid) as cm:
            xi.read_workbook(self.s, self.bomb("many.xlsx", size=excel.MAX_MEMBERS + 5, members=excel.MAX_MEMBERS + 5), "ABC",
                             state_path=self.state)
        self.assertIn("parts", str(cm.exception))

    def test_a_file_over_the_size_limit_is_refused_and_a_real_export_is_far_below_every_limit(self):
        big = self.dir / "big.xlsx"
        big.write_bytes(b"x" * (excel.MAX_FILE_BYTES + 1))
        with self.assertRaises(xi.Invalid) as cm:
            xi.read_workbook(self.s, big, "ABC", state_path=self.state)
        self.assertIn("more than", str(cm.exception))
        self.assertLess(self.path.stat().st_size, excel.MAX_FILE_BYTES // 100)
        excel.check_workbook_size(self.path)                                             # the real export passes


if __name__ == "__main__":
    unittest.main()
