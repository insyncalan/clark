"""#38: the round trip, second half (split from test_excel_roundtrip.py so no one test file runs past about 300 s on a slow CI runner;
the tests are the same, only moved). The base class RoundTrip, its template and the helpers are in test_excel_roundtrip.py.

Run: python3 dev/run_tests.py test_excel_roundtrip_b
"""
import json
import shutil
import unittest
from pathlib import Path

import _paths  # noqa: F401  (puts src/ and vendor/ on the path)
from _demo import USER
from openpyxl import load_workbook

from clark import excel
from clark import excel_import as xi
from clark.store import open_store
from test_excel_roundtrip import ON, RoundTrip, add_row, edit, setUpModule, tearDownModule  # noqa: F401  (the hooks keep a brand logo out of every test)


class NotTwice(RoundTrip):
    """A no-id row an import already made is not made again when the same content is read from other bytes (review LOW)."""

    def make(self, **cells):
        add_row(self.path, "Actions", **(cells or {"Title": "Brand new"}))
        p = self.read()
        p.accept_all()
        res = xi.apply_import(self.s, p, USER, state_path=self.state)
        self.assertTrue(res.applied and res.marked, res.message)
        return res

    def resave(self, to=None):
        """The same content saved again by openpyxl: different bytes (a different file hash)."""
        before = self.path.read_bytes()
        out = Path(to) if to else self.path
        wb = load_workbook(str(self.path))
        wb.properties.title = f"Saved again {len(before)}"            # (a save by another program: other bytes, same cells)
        wb.save(str(out))
        wb.close()
        self.assertNotEqual(out.read_bytes(), before)
        return out

    def count(self):
        return len(self.s.read("actions", "ABC"))

    def add_rows(self, *texts, **more):
        """Several new rows (no ID) under the Actions table in one save."""
        wb = load_workbook(str(self.path))
        ws = wb["Actions"]
        head = {c.value: c.column for c in ws[1]}
        row = ws.max_row
        for text in texts:
            row += 1
            ws.cell(row, head["Title"]).value = text
            for label, value in more.items():
                ws.cell(row, head[label]).value = value
        wb.save(str(self.path))

    def test_a_resaved_copy_does_not_make_the_new_row_again_and_cancels_nothing(self):
        res = self.make()
        new_id = res.created[0]["id"]
        self.assertEqual(len(res.created), 1)
        n_rows, n_steps = self.count(), self.steps()
        self.resave()
        again = self.read()
        self.assertFalse(again.already_imported)                    # other bytes: the file is read again...
        self.assertEqual(again.changes, [])                         # ...but nothing is staged
        self.assertEqual(again.already_created, 1)
        self.assertTrue(any(f"Already imported as {new_id}: left as it is." in x for x in again.notes), again.notes)
        self.assertIn("1 already imported", again.report())
        again.accept_all()
        self.assertFalse(xi.apply_import(self.s, again, USER, state_path=self.state).applied)
        self.assertEqual((self.count(), self.steps()), (n_rows, n_steps))
        self.assertEqual(self.s.read("actions", ref=new_id)["status"], "Open")

    def test_a_copy_saved_to_another_path_is_covered_too(self):
        new_id = self.make().created[0]["id"]
        n_rows = self.count()
        copy = self.resave(self.dir / "ABC copy.xlsx")
        plan = xi.read_workbook(self.s, copy, "ABC", state_path=self.state)
        self.assertEqual([c for c in plan.changes if c.kind == "new"], [])
        self.assertTrue(any(f"Already imported as {new_id}" in x for x in plan.notes))
        self.assertEqual(self.count(), n_rows)

    def test_editing_the_new_row_after_importing_it_makes_a_different_new_row(self):
        self.make()
        self.resave()
        wb = load_workbook(str(self.path))
        ws = wb["Actions"]
        head = {c.value: c.column for c in ws[1]}
        row = next(r for r in range(2, ws.max_row + 1) if ws.cell(r, head["ID"]).value is None and ws.cell(r, head["Title"]).value)
        ws.cell(row, head["Title"]).value = "Brand new, reworded"
        wb.save(str(self.path))
        p = self.read()
        self.assertEqual([c.kind for c in p.changes], ["new"])
        self.assertEqual(p.already_created, 0)

    def test_two_identical_rows_in_one_import_are_both_made_and_both_recorded(self):
        self.add_rows("Same text", "Same text")
        p = self.read()
        self.assertEqual([c.kind for c in p.changes], ["new", "new"])
        p.accept_all()
        res = xi.apply_import(self.s, p, USER, state_path=self.state)
        self.assertEqual(res.counts["new"], 2)
        self.assertEqual(len({c["id"] for c in res.created}), 2)
        self.assertEqual(len(excel.load_state(self.state, self.path)["created"]), 2)
        n_rows = self.count()
        self.resave()
        again = self.read()
        self.assertEqual(again.changes, [])                         # each recorded row covers one workbook row
        self.assertEqual(again.already_created, 2)
        add_row(self.path, "Actions", Title="Same text")      # a third identical row typed later is a new row
        third = self.read()
        self.assertEqual([c.kind for c in third.changes], ["new"])
        self.assertEqual(third.already_created, 2)
        self.assertEqual(self.count(), n_rows)

    def test_a_rejected_new_row_is_not_recorded_and_is_staged_again(self):
        self.add_rows("Not wanted", "Wanted")
        p = self.read()
        wanted = next(c for c in p.changes if c.after["description"] == "Wanted")
        p.accept(wanted.n)
        res = xi.apply_import(self.s, p, USER, state_path=self.state)
        self.assertEqual(len(res.created), 1)
        self.resave()
        again = self.read()
        self.assertEqual([c.after["description"] for c in again.changes], ["Not wanted"])

    def test_nothing_is_recorded_for_a_refused_or_rolled_back_import(self):
        self.add_rows("Fine")
        edit(self.path, "Actions", self.a2, Status="Finished")                  # a bad accepted change: all is rolled back
        p = self.read()
        p.accept(*[c.n for c in p.changes])
        held = excel.load_state(self.state, self.path)
        res = xi.apply_import(self.s, p, USER, state_path=self.state)
        self.assertFalse(res.applied)
        self.assertEqual(res.created, [])
        self.assertEqual(excel.load_state(self.state, self.path), held)
        self.assertNotIn("created", held)

    def test_nothing_is_recorded_when_the_store_refuses_to_open_the_step(self):
        add_row(self.path, "Actions", Title="Fine")
        p = self.read()
        p.accept_all()

        class Refusing:
            path = self.s.path

            def __init__(self, real):
                self.real = real

            def step(self, *a, **k):
                raise xi.Invalid("The backup could not be made, so nothing was changed.")

            def __getattr__(self, name):
                return getattr(self.real, name)

        held = excel.load_state(self.state, self.path)
        self.assertFalse(xi.apply_import(Refusing(self.s), p, USER, state_path=self.state).applied)
        self.assertEqual(excel.load_state(self.state, self.path), held)

    def test_after_an_undo_the_same_file_makes_the_row_again_and_an_export_starts_a_fresh_record(self):
        res = self.make()
        self.s.undo(res.step_id, USER)
        self.assertEqual(len(excel.load_state(self.state, self.path)["created"]), 1)         # (the record stays; it is not in force)
        self.resave()
        again = self.read()
        self.assertEqual([c.kind for c in again.changes if c.kind == "new"], ["new"])        # the undo was on purpose: made again
        self.assertEqual(again.already_created, 0)
        self.path.unlink()
        self.export_again()                                                                  # an export starts a fresh record
        self.assertNotIn("created", excel.load_state(self.state, self.path))

    def test_a_workbook_saved_again_after_it_was_read_still_records_the_rows_it_made(self):
        add_row(self.path, "Actions", Title="Brand new")
        p = self.read()
        p.accept_all()
        edit(self.path, "Actions", self.a2, Owner="Alex Example")               # saved again after the plan was read
        res = xi.apply_import(self.s, p, USER, state_path=self.state)
        self.assertTrue(res.applied and not res.marked)
        self.assertEqual(len(excel.load_state(self.state, self.path)["created"]), 1)
        self.assertEqual([c.kind for c in self.read().changes if c.kind == "new"], [])

    def test_the_list_of_fingerprints_is_bounded_and_drops_the_oldest(self):
        rec = {}
        excel.add_created(rec, [{"fp": f"f{i}", "id": f"ABC-A-{i}"} for i in range(excel.MAX_CREATED + 10)])
        self.assertEqual(len(rec["created"]), excel.MAX_CREATED)
        self.assertEqual(rec["created"][0]["fp"], "f10")
        excel.add_created(rec, [{"fp": "last", "id": "x"}])
        self.assertEqual(len(rec["created"]), excel.MAX_CREATED)
        self.assertEqual((rec["created"][0]["fp"], rec["created"][-1]["fp"]), ("f11", "last"))

    def test_the_fingerprint_ignores_the_file_hash_and_column_order(self):
        a = xi.fingerprint("actions", {"description": "x", "owner": "y"})
        self.assertEqual(a, xi.fingerprint("actions", {"owner": "y", "description": "x"}))
        self.assertNotEqual(a, xi.fingerprint("raid", {"description": "x", "owner": "y"}))
        self.assertNotEqual(a, xi.fingerprint("actions", {"description": "x ", "owner": "y"}))

    def test_the_export_stays_byte_deterministic(self):
        first = self.path.read_bytes()
        self.make()
        self.export_again()
        self.export_again()
        again = self.path.read_bytes()
        self.export_again()
        self.assertEqual(again, self.path.read_bytes())
        self.assertNotEqual(first, again)                                        # (the new row is in it now)


class Guard(RoundTrip):
    def test_exporting_before_importing_is_refused_and_after_importing_is_allowed(self):
        self.edited()
        held = excel.file_hash(self.path)
        with self.assertRaises(excel.Refused) as cm:
            self.export_again()
        self.assertIn("Import it first", str(cm.exception))
        self.assertEqual(excel.file_hash(self.path), held)                              # the edited workbook is untouched
        p = self.read()
        p.accept_all()
        res = xi.apply_import(self.s, p, USER, state_path=self.state)
        self.assertTrue(res.applied and res.marked, res.message)
        self.export_again()                                                              # now allowed
        self.assertNotEqual(excel.file_hash(self.path), held)
        self.assertEqual(self.read().changes, [])                                        # and the new workbook matches the store
        self.assertEqual(excel.load_state(self.state, self.path)["imported_hash"], None)  # a fresh export starts a fresh record

    def test_the_default_state_file_beside_the_store_is_used_when_none_is_given(self):
        path = excel.export_project(self.s, "ABC", on=ON)                                # default path and default state file
        edit(path, "Actions", self.a1, Owner="Sam Example")
        with self.assertRaises(excel.Refused):
            excel.export_project(self.s, "ABC", on=ON)
        p = xi.read_workbook(self.s, path, "ABC")
        p.accept_all()
        res = xi.apply_import(self.s, p, USER)
        self.assertTrue(res.marked, res.message)
        self.assertTrue((Path(self.s.path).parent / excel.STATE_FILE).exists())
        excel.export_project(self.s, "ABC", on=ON)

    def test_nothing_is_marked_when_the_import_is_rejected_cancelled_or_rolled_back(self):
        self.edited()
        # rejected: nothing accepted
        p = self.read()
        p.reject_all()
        res = xi.apply_import(self.s, p, USER, state_path=self.state)
        self.assertFalse(res.applied or res.marked)
        # rolled back: a bad accepted row
        edit(self.path, "Actions", self.a2, Status="Finished")
        p = self.read()
        p.accept(*[c.n for c in p.changes])
        res = xi.apply_import(self.s, p, USER, state_path=self.state)
        self.assertFalse(res.applied or res.marked)
        self.assertIsNone(excel.load_state(self.state, self.path)["imported_hash"])
        with self.assertRaises(excel.Refused):
            self.export_again()

    def test_a_workbook_saved_again_after_it_was_read_is_not_marked_as_imported(self):
        self.edited()
        p = self.read()
        p.accept_all()
        edit(self.path, "Actions", self.a2, Owner="Alex Example")                        # saved after the plan was made
        res = xi.apply_import(self.s, p, USER, state_path=self.state)
        self.assertTrue(res.applied)
        self.assertFalse(res.marked)
        self.assertIn("saved again", res.message)
        with self.assertRaises(excel.Refused):
            self.export_again()

    def test_a_workbook_with_no_export_record_is_unrecorded_and_is_only_applied_once_confirmed(self):
        self.state.unlink()                                                              # the export's record is gone
        self.edited()
        before = self.snapshot()
        p = self.read()
        self.assertTrue(p.unrecorded and p.changes)
        self.assertTrue(any("no record of exporting" in n for n in p.notes))
        self.assertTrue(any("no longer in the workbook are offered for archiving (nothing is deleted)." in n and "count as removed" not in n for n in p.notes))
        p.accept_all()                                                                   # accepts nothing, silently or not
        self.assertEqual(p.accepted(), [])
        p.accept(p.changes[0].n)                                                         # even by number: apply refuses
        res = xi.apply_import(self.s, p, USER, state_path=self.state)
        self.assertFalse(res.applied)
        self.assertIn("no record of exporting", res.message)
        for words in (res.message, *[n for n in p.notes if "no record of exporting" in n],
                      *[l.strip() for l in p.report().splitlines() if "no record of exporting" in l]):
            self.assertTrue(words.removeprefix("Note: ").startswith("There is no record of exporting"), words)
        self.assertEqual(self.snapshot(), before)
        p.confirm_unrecorded()                                                           # the person confirms
        p.accept_all()
        res = xi.apply_import(self.s, p, USER, state_path=self.state)
        self.assertTrue(res.applied and res.marked, res.message)
        self.export_again()
        self.state.unlink()
        edit(self.path, "Actions", self.a2, Owner="Alex Example")
        again = xi.read_workbook(self.s, self.path, "ABC", state_path=self.state, allow_unrecorded=True)   # the parameter does it too
        again.accept_all()
        self.assertTrue(xi.apply_import(self.s, again, USER, state_path=self.state).applied)


class Idempotent(RoundTrip):
    """Importing the same file twice must change nothing the second time (review HIGH)."""

    def test_a_second_import_of_the_same_file_changes_and_cancels_nothing(self):
        add_row(self.path, "Actions", Title="Brand new")
        p = self.read()
        p.accept_all()
        res = xi.apply_import(self.s, p, USER, state_path=self.state)
        self.assertTrue(res.applied and res.marked, res.message)
        self.assertEqual(res.counts, {"new": 1, "changed": 0, "removed": 0})
        new = [a for a in self.s.read("actions", "ABC") if a["description"] == "Brand new"]
        self.assertEqual(len(new), 1)
        before, n = self.snapshot(), self.steps()
        again = self.read()                                                              # the same file, imported again
        self.assertTrue(again.already_imported)
        self.assertEqual(again.changes, [])
        self.assertTrue(any("already imported" in x for x in again.notes))
        again.accept_all()
        res = xi.apply_import(self.s, again, USER, state_path=self.state)
        self.assertFalse(res.applied)
        self.assertIn("already imported", res.message)
        self.assertEqual((self.snapshot(), self.steps()), (before, n))
        self.assertEqual(self.s.read("actions", ref=new[0]["id"])["status"], "Open")     # the new item was not cancelled

    def test_two_plans_of_one_file_apply_only_once(self):
        add_row(self.path, "Actions", Title="Brand new")
        first, second = self.read(), self.read()
        first.accept_all()
        second.accept_all()
        self.assertTrue(xi.apply_import(self.s, first, USER, state_path=self.state).applied)
        n = self.steps()
        res = xi.apply_import(self.s, second, USER, state_path=self.state)
        self.assertFalse(res.applied)
        self.assertEqual(self.steps(), n)

    def test_the_file_saved_again_does_not_turn_the_item_it_made_into_one_removed_from_the_workbook(self):
        add_row(self.path, "Actions", Title="Brand new")
        p = self.read()
        p.accept_all()
        self.assertTrue(xi.apply_import(self.s, p, USER, state_path=self.state).applied)
        edit(self.path, "Actions", self.a2, Owner="Alex Example")                        # saved again: a different file
        again = self.read()
        self.assertFalse(again.already_imported)
        self.assertEqual([c.kind for c in again.changes if c.kind == "removed"], [])     # the new item was not in the export
        self.assertEqual(sorted(c.kind for c in again.changes), ["changed"])             # the new row (no id) is not made again
        self.assertEqual(again.already_created, 1)


class UndoAndRestore(RoundTrip):
    """"""

    def imported(self):
        self.edited()
        p = self.read()
        p.accept_all()
        res = xi.apply_import(self.s, p, USER, state_path=self.state)
        self.assertTrue(res.applied and res.marked, res.message)
        return res

    def test_import_then_undo_then_the_same_file_can_be_imported_again(self):
        res = self.imported()
        self.assertTrue(self.read().already_imported)                       # in force: refused as already imported
        self.s.undo(res.step_id, USER)
        again = self.read()
        self.assertFalse(again.already_imported)
        self.assertTrue(any("has been undone" in n for n in again.notes), again.notes)
        self.assertTrue(again.changes)
        again.accept(*[c.n for c in again.changes])                         # (the undo made a row newer: a clash, by number)
        res2 = xi.apply_import(self.s, again, USER, state_path=self.state)
        self.assertTrue(res2.applied and res2.marked, res2.message)
        self.assertEqual(self.s.read("actions", ref=self.a1)["owner"], "Sam Example")
        self.assertTrue(self.read().already_imported)                       # and the second import is in force

    def test_import_then_import_again_is_refused_as_already_imported(self):
        self.imported()
        n, before = self.steps(), self.snapshot()
        again = self.read()
        self.assertTrue(again.already_imported)
        again.accept_all()
        res = xi.apply_import(self.s, again, USER, state_path=self.state)
        self.assertFalse(res.applied)
        self.assertIn("already imported", res.message)
        self.assertEqual((self.steps(), self.snapshot()), (n, before))

    def test_a_plan_made_before_an_undo_cannot_hide_behind_the_old_stamp_and_an_undone_undo_puts_it_back_in_force(self):
        res = self.imported()
        undo = self.s.undo(res.step_id, USER)
        self.assertFalse(self.read().already_imported)
        self.s.undo(undo["step_id"], USER)                                  # the undo undone: the import is in force again
        self.assertTrue(self.read().already_imported)

    def restored_store(self):
        """A second store on a copy of the database taken now (before the import)."""
        self.s.con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        folder = self.dir / "restored"
        folder.mkdir()
        shutil.copy(self.s.path, folder / "clark.db")
        return open_store(folder / "clark.db", onedrive_roots=[])

    def test_a_restored_older_database_can_import_the_file_again(self):
        self.edited()
        old = self.restored_store()
        self.addCleanup(old.close)
        p = self.read()
        p.accept_all()
        self.assertTrue(xi.apply_import(self.s, p, USER, state_path=self.state).applied)
        self.assertTrue(self.read().already_imported)
        with old.step("dashboard", USER) as st:                             # the restored copy goes on, and reuses the step number
            st.update("actions", self.a2, {"owner": "Someone Else"})
        again = xi.read_workbook(old, self.path, "ABC", state_path=self.state)
        self.assertFalse(again.already_imported)
        self.assertTrue(again.changes)
        again.accept(*[c.n for c in again.changes])
        res = xi.apply_import(old, again, USER, state_path=self.state)
        self.assertTrue(res.applied, res.message)
        self.assertEqual(old.read("actions", ref=self.a1)["owner"], "Sam Example")

    def test_a_fingerprint_counts_only_while_its_step_is_in_force(self):
        add_row(self.path, "Actions", Title="Brand new")
        old = self.restored_store()
        self.addCleanup(old.close)
        p = self.read()
        p.accept_all()
        res = xi.apply_import(self.s, p, USER, state_path=self.state)
        self.assertTrue(res.applied, res.message)
        edit(self.path, "Actions", self.a2, Owner="Alex Example")            # other bytes
        self.assertEqual(self.read().already_created, 1)                     # in force: not made again
        self.s.undo(res.step_id, USER)
        undone = self.read()
        self.assertEqual(undone.already_created, 0)                          # undone: made again
        self.assertEqual([c.kind for c in undone.changes if c.kind == "new"], ["new"])
        undone.accept(*[c.n for c in undone.changes if c.kind == "new"])
        self.assertTrue(xi.apply_import(self.s, undone, USER, state_path=self.state).applied)
        rows = [a for a in self.s.read("actions", "ABC") if a["description"] == "Brand new"]
        self.assertEqual(len(rows), 1)                                       # (the undo removed the first; this is the second)
        in_old = xi.read_workbook(old, self.path, "ABC", state_path=self.state)       # a restored copy: no such step either
        self.assertEqual(in_old.already_created, 0)


class Clash(RoundTrip):
    def test_only_the_cells_the_person_edited_are_staged_and_newer_values_in_clark_are_left_alone(self):
        self.demo.update("actions", self.a1, {"owner": "Kim Example"})                   # changed in clark after the export
        edit(self.path, "Actions", self.a1, Title="Draft the cut-over plan v2")    # the person edits one cell
        p = self.read()
        (c,) = p.changes
        self.assertEqual((c.state, c.clash, c.from_snapshot), ("clash", True, True))
        self.assertEqual(c.after, {"description": "Draft the cut-over plan v2"})
        self.assertEqual(c.kept, {"owner": "Kim Example"})
        text = p.report()
        self.assertIn("You edited Title", text)
        self.assertIn("Newer in clark and left alone: Owner (now Kim Example)", text)
        p.accept(c.n)
        self.assertTrue(xi.apply_import(self.s, p, USER, state_path=self.state).applied)
        row = self.s.read("actions", ref=self.a1)
        self.assertEqual((row["description"], row["owner"]), ("Draft the cut-over plan v2", "Kim Example"))

    def test_a_clash_where_the_person_edits_the_same_cell_stages_it_and_an_untouched_row_is_no_change(self):
        self.demo.update("actions", self.a1, {"owner": "Kim Example"})
        self.demo.update("actions", self.a2, {"owner": "Kim Example"})
        edit(self.path, "Actions", self.a1, Owner="Sam Example")
        p = self.read()
        (c,) = p.changes                                                                  # a2 was only changed in clark: no change
        self.assertEqual((c.after, c.before, c.kept), ({"owner": "Sam Example"}, {"owner": "Kim Example"}, {}))

    def test_without_the_export_snapshot_the_clash_says_unedited_fields_are_also_reverted(self):
        self.demo.update("actions", self.a1, {"owner": "Kim Example"})
        edit(self.path, "Actions", self.a1, Title="Draft the cut-over plan v2")
        state = json.loads(self.state.read_text(encoding="utf-8"))
        for rec in state["workbooks"].values():
            rec["rows"] = None
        self.state.write_text(json.dumps(state), encoding="utf-8")
        (c,) = self.read().changes
        self.assertEqual((c.clash, c.from_snapshot), (True, False))
        self.assertEqual(set(c.after), {"description", "owner"})
        p = self.read()
        self.assertIn("including ones you did not edit", p.report())

    def test_a_row_added_in_clark_after_the_export_is_not_removed_from_the_workbook(self):
        with self.s.step("dashboard", USER) as st:
            late = st.create("actions", {"project": "ABC", "description": "Added later", "raised": "2030-02-01", "source": "demo"})
        p = self.read()
        self.assertEqual(p.changes, [])
        p.accept_all()
        xi.apply_import(self.s, p, USER, state_path=self.state)
        self.assertEqual(self.s.read("actions", ref=late)["status"], "Open")


if __name__ == "__main__":
    unittest.main()
