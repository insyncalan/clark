"""Row 926: the Gantt lines in the Excel export. The editor's workbook carries a Gantt sheet with every line (eye-off included); the
client workbook carries one only from publish.gantt_for_client's output (eye-on lines, shown columns only), and only when the file has
the Gantt tab. Word is unchanged. Fictional data only.

Run: python3 dev/run_tests.py test_gantt_excel_export
"""
import copy
import io
import unittest
import zipfile
from datetime import date

import _publish_fixture as fixture
from _demo import USER, DemoStore
from _paths import SRC  # noqa: F401
from clark import changes, docx_build, excel, excel_client, publish
from openpyxl import load_workbook

ON = "2026-11-07"
LABELS = ["ID", "Line", "Type", "Parent", "Start", "End", "Days", "Done %", "Status", "Health", "Depends on", "Owner", "Workstream", "Priority",
          "Baseline start", "Baseline end", "Effort (days)", "Budget", "Deliverable", "On dashboard", "Notes"]
DEFAULT_SHOWN = ["ID", "Line", "Type", "Parent", "Start", "End", "Days", "Done %", "Status", "Health", "Depends on", "Owner", "Workstream",
                 "Priority", "Deliverable"]


def gid(n):
    return f"PUB-GNT-{n:03d}"


def line(n, kind, name, parent=None, show=1, depends="", **kw):
    """Line n: a stored Gantt row. Every line has its own owner, note, budget and effort, so a leak of any is found by its text."""
    start = f"2026-11-{n + 1:02d}"
    row = {"id": gid(n), "project": "PUB", "type": kind, "name": name, "parent": gid(parent) if parent else None, "start": start,
           "end": start if kind == "milestone" else f"2026-11-{n + 6:02d}", "pct": 10 * n % 100, "health": "Green", "depends": depends,
           "owner": f"ZQ-OWNER-{n}", "workstream": "Build", "priority": "High", "baseline_start": "2026-10-01", "baseline_end": "2026-10-09",
           "effort": 7777.0 + n, "budget": 424242.5 + n, "deliverable": f"Thing {n}", "show": show, "note": f"ZQ-NOTE-{n}", "sort_order": n * 1024}
    row.update(kw)
    return row


OFF = {5: "ZQ-OFF-PHASE", 7: "ZQ-OFF-TASK", 10: "ZQ-OFF-TASK-2", 12: "ZQ-OFF-MILESTONE"}


def twelve():
    """3 phases (1, 5, 9), 7 tasks, 2 milestones (4, 12); lines 5, 7, 10 and 12 have their eye off. Phase 5 is eye-off with eye-on children."""
    return [line(1, "phase", "Alpha"), line(2, "task", "Dig", 1, depends=gid(3)), line(3, "task", "Pour", 1), line(4, "milestone", "Alpha done", 1),
            line(5, "phase", OFF[5], show=0), line(6, "task", "Child of the hidden phase", 5, depends=f"{gid(7)},{gid(3)}"),
            line(7, "task", OFF[7], 5, show=0), line(8, "task", "Cure", 5), line(9, "phase", "Gamma"),
            line(10, "task", OFF[10], 9, show=0), line(11, "task", "Finish", 9, depends=f"{gid(10)},{gid(3)}"),
            line(12, "milestone", OFF[12], 9, show=0)]


def plant(lines=None, **project):
    inputs = fixture.inputs()
    d = inputs["data"]
    d["project"].update(show_gantt_client=1, gantt_tab_name="Plan", gantt_title="", gantt_hidden_columns="show,note,budget,effort,baseline_start,baseline_end",
                        gantt_default_rows=None)
    d["project"].update(project)
    d["gantt_lines"] = twelve() if lines is None else lines
    return inputs


def selected(inputs):
    return publish.select(copy.deepcopy(inputs))


def parts(blob):
    """Every part of an .xlsx or .docx, concatenated: the sheets, sharedStrings, docProps, everything."""
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        return b"".join(z.read(n) for n in z.namelist())


def client(inputs):
    return excel_client.workbook_bytes(selected(inputs))


def gantt_sheet(blob, name="Plan"):
    wb = load_workbook(io.BytesIO(blob))
    return wb[name] if name in wb.sheetnames else None


def table(ws, head_row):
    heads = [c.value for c in ws[head_row]]
    return heads, [[c.value for c in r] for r in ws.iter_rows(min_row=head_row + 1)]


class TheEditorsWorkbook(unittest.TestCase):
    def book(self, lines=None, tab="Plan"):
        rows = {"gantt_lines": twelve() if lines is None else lines}
        return excel.workbook("PUB", rows, on=ON, gantt_tab=tab)

    def test_every_line_is_on_the_sheet_in_the_authors_order_eye_off_included(self):
        wb = self.book()
        self.assertEqual(wb.sheetnames[-1], "Plan")
        heads, rows = table(wb["Plan"], 1)
        self.assertEqual(heads, LABELS)
        self.assertEqual([r[0] for r in rows], [gid(n) for n in range(1, 13)])      # the stored id, so an import can match it
        self.assertEqual([r[1] for r in rows if r[0] in {gid(n) for n in OFF}], list(OFF.values()))
        self.assertEqual(len(rows), 12)

    def test_the_order_is_sort_order_not_the_id(self):
        lines = twelve()
        lines[0]["sort_order"], lines[1]["sort_order"] = 99999, 5
        _, rows = table(self.book(lines)["Plan"], 1)
        self.assertEqual([r[0] for r in rows][:2], [gid(2), gid(3)])
        self.assertEqual(rows[-1][0], gid(1))

    def test_the_cells_are_what_the_line_holds(self):
        _, rows = table(self.book()["Plan"], 1)
        by = {r[0]: dict(zip(LABELS, r)) for r in rows}
        one = by[gid(2)]
        self.assertEqual((one["Type"], one["Parent"], one["Depends on"], one["On dashboard"]), ("Task", gid(1), gid(3), "Yes"))
        self.assertEqual((one["Start"], one["End"]), (date(2026, 11, 3), date(2026, 11, 8)))
        self.assertEqual((one["Days"], one["Owner"], one["Budget"], one["Effort (days)"], one["Notes"]), (6, "ZQ-OWNER-2", 424244.5, 7779.0, "ZQ-NOTE-2"))
        self.assertEqual((one["Baseline start"], one["Baseline end"]), (date(2026, 10, 1), date(2026, 10, 9)))
        self.assertEqual(by[gid(5)]["On dashboard"], "No")
        self.assertEqual(by[gid(6)]["Depends on"], f"{gid(7)}, {gid(3)}")
        self.assertIsNone(by[gid(4)]["Days"])                                       # a milestone has no span, as on the page
        ws = self.book()["Plan"]
        self.assertEqual(ws["E2"].number_format, excel.DATE_FORMAT)

    def test_a_blank_value_is_a_blank_cell_and_a_text_is_never_a_formula(self):
        lines = [line(1, "task", "=SUM(1,2)", owner="", health="", priority="", baseline_start=None, baseline_end=None, effort=None, budget=None,
                      deliverable="", note="")]
        ws = self.book(lines)["Plan"]
        row = dict(zip(LABELS, [c for c in ws[2]]))
        self.assertEqual(row["Line"].data_type, "s")
        for k in ("Owner", "Health", "Baseline start", "Effort (days)", "Budget", "Notes"):
            self.assertIsNone(row[k].value, k)

    def test_the_sheet_is_named_for_the_tab_else_gantt_and_a_project_without_lines_has_none(self):
        self.assertIn("Gantt", self.book(tab=None).sheetnames)
        self.assertIn("Gantt", self.book(tab="a/b:[c]*?" * 0 or "///").sheetnames)
        self.assertIn("Plan 1", self.book(tab="Plan 1").sheetnames)
        self.assertEqual(excel.gantt_sheet_name("Actions", ["Actions"]), "Gantt")
        self.assertNotIn("Gantt", excel.workbook("PUB", {"gantt_lines": []}, on=ON, gantt_tab="Gantt").sheetnames)
        self.assertEqual(excel.workbook("PUB", {}, on=ON).sheetnames, excel.workbook("PUB", {"gantt_lines": []}, on=ON).sheetnames)

    def test_the_other_sheets_and_the_import_layout_are_as_they_were(self):
        with_g = self.book().sheetnames
        without = excel.workbook("PUB", {}, on=ON).sheetnames
        self.assertEqual([n for n in with_g if n != "Plan"], without)
        self.assertEqual(excel.TABLES, ("actions", "raid", "decisions", "milestones", "use_cases"))      # the import still reads these five only

    def test_days_and_status_follow_the_pages_rule(self):
        """Pinned to the examples of the page's rule (gantt/logic/grid.js statusOf and the Days cell): Done at 100; Late when the end is before
        today and not done; In progress when started or some done; else Not started; a milestone has no Days."""
        t = "2026-11-07"
        cases = [({"pct": 100, "start": "2026-01-01", "end": "2026-01-02"}, "Done"), ({"pct": 0, "start": "2026-11-01", "end": "2026-11-06"}, "Late"),
                 ({"pct": 50, "start": "2026-11-01", "end": "2026-11-06"}, "Late"), ({"pct": 0, "start": "2026-11-07", "end": "2026-11-09"}, "In progress"),
                 ({"pct": 0, "start": "2026-11-01", "end": "2026-11-07"}, "In progress"), ({"pct": 5, "start": "2026-12-01", "end": "2026-12-09"}, "In progress"),
                 ({"pct": 0, "start": "2026-11-08", "end": "2026-11-09"}, "Not started")]
        for ln, word in cases:
            self.assertEqual(excel.gantt_status(ln, t), word, ln)
        self.assertEqual(excel.gantt_days({"type": "task", "start": "2026-11-02", "end": "2026-11-13"}), 12)
        self.assertEqual(excel.gantt_days({"type": "task", "start": "2026-11-02", "end": "2026-11-02"}), 1)
        self.assertIsNone(excel.gantt_days({"type": "milestone", "start": "2026-11-02", "end": "2026-11-02"}))
        self.assertIsNone(excel.gantt_days({"type": "task", "start": None, "end": None}))


class FromARealStore(unittest.TestCase):
    def test_export_project_writes_the_stored_ids_and_the_projects_tab_name(self):
        import shutil
        import tempfile
        from pathlib import Path
        demo = DemoStore()
        self.addCleanup(demo.close)
        change = changes.make_change(demo.store.path, [], USER)
        self.assertEqual(change({"project": "ABC", "kind": "projects", "op": "update", "changes": {"gantt_tab_name": "Plan"}})[0], 200)
        for kind, name, after in (("phase", "Build", None), ("task", "Dig", "ABC-GNT-001")):
            status, body = change({"project": "ABC", "kind": "gantt_lines", "op": "new", "values": {"type": kind, "name": name}, "after": after})
            self.assertEqual(status, 200, body)
        folder = Path(tempfile.mkdtemp(prefix="clark-gxe-"))
        self.addCleanup(shutil.rmtree, folder, True)
        path = excel.export_project(demo.store, "ABC", folder / "a.xlsx", folder / "s.json", on=ON)
        ws = load_workbook(path)["Plan"]
        self.assertEqual([r[0] for r in table(ws, 1)[1]], ["ABC-GNT-001", "ABC-GNT-002"])
        self.assertEqual([r[1] for r in table(ws, 1)[1]], ["Build", "Dig"])


class TheClientsWorkbook(unittest.TestCase):
    def test_only_the_eye_on_lines_and_only_the_visible_columns(self):
        ws = gantt_sheet(client(plant()))
        heads, rows = table(ws, 4)
        self.assertEqual(heads, DEFAULT_SHOWN)
        want = [gid(n) for n in range(1, 13) if n not in OFF]
        self.assertEqual([r[0] for r in rows], want)
        self.assertEqual(len(rows), 8)
        by = {r[0]: dict(zip(heads, r)) for r in rows}
        self.assertEqual(by[gid(6)]["Parent"], None)                          # its phase is eye-off: the parent is blanked
        self.assertEqual(by[gid(6)]["Depends on"], gid(3))                    # the dependency on the dropped line is gone, the kept one stays
        self.assertEqual(by[gid(11)]["Depends on"], gid(3))
        self.assertEqual(by[gid(2)]["Parent"], gid(1))

    def test_a_hidden_owner_is_absent_as_a_header_and_as_a_value(self):
        blob = client(plant(gantt_hidden_columns="owner,show,note,budget,effort,baseline_start,baseline_end"))
        heads, _ = table(gantt_sheet(blob), 4)
        self.assertNotIn("Owner", heads)
        self.assertNotIn(b"ZQ-OWNER", parts(blob))

    def test_no_leak_anywhere_in_the_client_file(self):
        everything = parts(client(plant()))
        for n in OFF:
            for text in (OFF[n], gid(n), f"ZQ-OWNER-{n}", f"ZQ-NOTE-{n}"):
                self.assertNotIn(text.encode(), everything, text)
        for n in range(1, 13):                                                # the hidden columns, for every line
            for text in (f"ZQ-NOTE-{n}", str(424242.5 + n), str(7777 + n), "Baseline", "Budget", "Notes", "Effort", "On dashboard"):
                self.assertNotIn(text.encode(), everything, text)

    def test_no_leak_after_the_hidden_columns_change(self):
        for hidden, gone, present in (("owner,health,deliverable", (b"ZQ-OWNER", b"Thing 2"), (b"ZQ-NOTE-1", b"424243.5")),
                                      ("", (), (b"ZQ-OWNER-1", b"ZQ-NOTE-1")), ("note", (b"ZQ-NOTE-",), (b"ZQ-OWNER-1",))):
            blob = client(plant(gantt_hidden_columns=hidden))
            everything = parts(blob)
            for text in gone:
                self.assertNotIn(text, everything, (hidden, text))
            for text in present[:1]:
                self.assertIn(text, everything, (hidden, text))
            for n in OFF:                                                      # the eye-off lines stay out, whatever is hidden
                for text in (OFF[n], gid(n), f"ZQ-OWNER-{n}", f"ZQ-NOTE-{n}"):
                    self.assertNotIn(text.encode(), everything, (hidden, text))

    def test_an_eye_off_phase_with_an_eye_on_child_blanks_the_childs_parent(self):
        lines = [line(1, "phase", OFF[5], show=0), line(2, "task", "Child", 1, depends=gid(1))]
        blob = client(plant(lines))
        _, rows = table(gantt_sheet(blob), 4)
        self.assertEqual([(r[0], r[3], r[10]) for r in rows], [(gid(2), None, None)])
        self.assertNotIn(OFF[5].encode(), parts(blob))
        self.assertNotIn(gid(1).encode(), parts(blob))

    def test_the_wrong_hidden_names_cannot_bring_a_hidden_column_back(self):
        blob = client(plant(gantt_hidden_columns=["note"]))                    # damaged: reads as the default hiding
        self.assertNotIn(b"ZQ-NOTE-", parts(blob))
        self.assertNotIn(b"ZQ-OWNER-5", parts(blob))

    def test_the_setting_off_or_no_eye_on_line_means_no_gantt_sheet(self):
        base = excel_client.workbook_bytes(selected(fixture.inputs()))
        for inputs in (plant(show_gantt_client=0), plant([line(1, "phase", "A", show=0), line(2, "task", "B", 1, show=0)]), plant([])):
            blob = client(inputs)
            self.assertEqual(load_workbook(io.BytesIO(blob)).sheetnames, load_workbook(io.BytesIO(base)).sheetnames)
            self.assertNotIn(b"ZQ-OWNER", parts(blob))
            self.assertNotIn(b"ZQ-OFF", parts(blob))

    def test_it_is_made_from_the_gate_not_the_store(self):
        out = selected(plant())
        out["data"]["gantt"]["lines"] = out["data"]["gantt"]["lines"][:1]       # whatever the gate hands over is all the sheet has
        _, rows = table(gantt_sheet(excel_client.workbook_bytes(out)), 4)
        self.assertEqual([r[0] for r in rows], [gid(1)])

    def test_the_sheet_is_locked_and_the_same_bytes_come_twice(self):
        blob = client(plant())
        self.assertTrue(gantt_sheet(blob).protection.sheet)
        self.assertEqual(blob, client(plant()))


class WordIsUnchanged(unittest.TestCase):
    def test_a_word_build_is_the_same_bytes_with_or_without_gantt_lines(self):
        without = docx_build.build(selected(fixture.inputs()))
        withg = docx_build.build(selected(plant()))
        self.assertEqual(without, withg)
        for text in (b"ZQ-OWNER", b"ZQ-NOTE", b"ZQ-OFF", b"Alpha", b"PUB-GNT"):
            self.assertNotIn(text, parts(withg))


if __name__ == "__main__":
    unittest.main()
