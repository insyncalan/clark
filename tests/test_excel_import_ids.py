"""#129 (FR-70d): the Excel import gives new items their IDs. An empty ID is a new item; an ID clark doesn't know is not used; a
changed or pasted-over ID is refused for that row only; the same new row is never made twice; one Undo takes the new items back;
and a crafted workbook is refused or handled in plain words with nothing half written."""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from _demo import USER, DemoStore
import _workbook as wbk
from clark import excel_import as xi
from clark.store import Invalid
from openpyxl import load_workbook


class IdCase(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.s = self.demo.store
        self.tmp = Path(tempfile.mkdtemp(prefix="clark-ids-"))
        self.a1 = self.demo.action(description="Draft the cut-over plan")
        self.a2 = self.demo.action(description="Book the training room")
        self.path = wbk.make_workbook(self.s, self.tmp / "ABC.xlsx")

    def tearDown(self):
        self.demo.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def plan(self):
        return xi.read_workbook(self.s, self.path, "ABC", allow_unrecorded=True)

    def apply(self, p=None):
        p = p or self.plan()
        p.accept_all()
        return xi.apply_import(self.s, p, USER)

    def snapshot(self):
        return {t: self.s.read(t) for t in ("actions", "raid", "decisions", "milestones", "use_cases")}

    def ids(self, table="actions"):
        return sorted(r["id"] for r in self.s.read(table, project="ABC"))


class NewItems(IdCase):
    def test_an_unknown_typed_id_is_not_used_and_the_plan_names_it(self):
        wbk.add_row(self.path, "Actions", id="ABC-A-099", description="Order the laptops")
        p = self.plan()
        (c,) = p.changes
        self.assertEqual((c.kind, c.id), ("new", ""))
        self.assertIn("Actions, row 4: the ID ABC-A-099 isn't one clark knows, so the item gets a new ID.", p.notes)
        res = self.apply(p)
        self.assertTrue(res.applied, res.message)
        self.assertNotIn("ABC-A-099", self.ids())
        self.assertEqual(self.s.read("actions", ref="ABC-A-003")["description"], "Order the laptops")

    def test_a_changed_id_is_refused_for_that_row_and_the_others_apply(self):
        wbk.edit(self.path, "Actions", self.a2, id="ABC-A-050")         # a2's row now says an id clark doesn't know
        wbk.edit(self.path, "Actions", self.a1, owner="Sam Example")
        p = self.plan()
        self.assertEqual([(c.kind, c.id) for c in p.changes], [("changed", self.a1)])
        self.assertEqual([m.message for m in p.problems], ["Actions, row 3: the ID was changed. IDs can't be edited; the row was skipped."])
        res = self.apply(p)
        self.assertTrue(res.applied, res.message)
        self.assertEqual(self.s.read("actions", ref=self.a1)["owner"], "Sam Example")
        self.assertEqual(self.ids(), [self.a1, self.a2])

    def test_an_id_pasted_over_another_items_row_is_a_title_edit_with_a_warning(self):
        wbk.edit(self.path, "Actions", self.a1, description="Book the training room")     # a1's id on a2's words
        p = self.plan()
        self.assertEqual([(c.kind, c.id) for c in p.changes], [("changed", self.a1)])
        self.assertIn("Actions, row 2: ABC-A-001's new title is the same as ABC-A-002's.", p.notes)

    def test_swapped_ids_refuse_only_those_rows_and_the_rest_apply(self):
        wbk.edit(self.path, "Actions", self.a1, id="TMP")
        wbk.edit(self.path, "Actions", self.a2, id=self.a1)
        wbk.edit(self.path, "Actions", "TMP", id=self.a2)
        wbk.add_row(self.path, "Actions", description="Order the laptops")
        p = self.plan()
        self.assertEqual(len([m for m in p.problems if "the ID was changed" in m.message]), 2)
        self.assertEqual([c.kind for c in p.changes], ["new"])
        self.assertTrue(self.apply(p).applied)
        self.assertEqual(self.s.read("actions", ref=self.a1)["description"], "Draft the cut-over plan")

    def test_the_old_item_line_and_row_messages_use_neutral_words(self):
        wbk.edit(self.path, "Actions", self.a2, id="ABC-A-077", description="Book a bigger room")
        wbk.add_row(self.path, "Actions", id="XYZ-A-001", description="Elsewhere")
        p = self.plan()
        (gone,) = [c for c in p.changes if c.kind == "removed"]
        self.assertTrue(gone.describe().startswith(f"{self.a2}: No longer in the workbook"))
        self.assertNotIn("Cancel", gone.describe())
        self.assertTrue(all(m.message.startswith("Actions, row ") for m in p.problems), [m.message for m in p.problems])

    def test_two_descriptions_swapped_with_the_ids_kept_apply(self):
        self.s.con.execute("UPDATE actions SET owner = 'Alex Example' WHERE id = ?", (self.a1,))
        self.s.con.execute("UPDATE actions SET owner = 'Sam Example' WHERE id = ?", (self.a2,))
        self.s.con.commit()
        wbk.make_workbook(self.s, self.path)
        wbk.edit(self.path, "Actions", self.a1, description="Book the training room")
        wbk.edit(self.path, "Actions", self.a2, description="Draft the cut-over plan")
        p = self.plan()
        self.assertEqual([m.message for m in p.problems], [])
        self.assertEqual(sorted(c.id for c in p.changes), [self.a1, self.a2])
        self.assertTrue(self.apply(p).applied)
        self.assertEqual(self.s.read("actions", ref=self.a1)["description"], "Book the training room")

    def test_swapped_ids_are_still_refused_when_the_owners_follow_the_ids(self):
        self.s.con.execute("UPDATE actions SET owner = 'Alex Example' WHERE id = ?", (self.a1,))
        self.s.con.execute("UPDATE actions SET owner = 'Sam Example' WHERE id = ?", (self.a2,))
        self.s.con.commit()
        wbk.make_workbook(self.s, self.path)
        wbk.edit(self.path, "Actions", self.a1, id="TMP")
        wbk.edit(self.path, "Actions", self.a2, id=self.a1)
        wbk.edit(self.path, "Actions", "TMP", id=self.a2)
        p = self.plan()
        self.assertEqual(len([m for m in p.problems if "the ID was changed" in m.message]), 2)

    def test_a_title_edit_to_another_items_title_is_not_refused(self):
        wbk.edit(self.path, "Actions", self.a2, description="Draft the cut-over plan")
        p = self.plan()
        self.assertEqual([(c.kind, c.id) for c in p.changes], [("changed", self.a2)])
        self.assertFalse([m for m in p.problems if "ID was changed" in m.message])

    def test_an_id_change_plus_a_title_edit_warns_that_the_old_item_would_be_cancelled(self):
        wbk.edit(self.path, "Actions", self.a2, id="ABC-A-077", description="Book a bigger room")
        p = self.plan()
        self.assertEqual(sorted(c.kind for c in p.changes), ["new", "removed"])
        self.assertIn("Actions: This looks like an ID that was changed. The old item shows as no longer in the workbook: don't accept that line if you still want it.", p.notes)

    def test_a_typed_id_row_imported_twice_says_already_imported(self):
        wbk.add_row(self.path, "Actions", id="ABC-A-099", description="Order the laptops")
        self.assertTrue(self.apply().applied)
        n = len(self.ids())
        wbk.add_row(self.path, "Actions", description="Something else")      # saved again with one more row, so it is read again
        p = self.plan()
        self.assertEqual([c.kind for c in p.changes], ["new"])
        self.assertFalse([m for m in p.problems if "ID was changed" in m.message])
        self.assertTrue([x for x in p.notes if "Already imported as ABC-A-003" in x])
        self.assertEqual(len(self.ids()), n)

    def test_a_sorted_sheet_changes_nothing(self):
        wb = load_workbook(str(self.path))
        ws = wb["Actions"]
        rows = [[c.value for c in r] for r in ws.iter_rows(min_row=2)]
        for i, r in enumerate(reversed(rows), start=2):
            for j, v in enumerate(r, start=1):
                ws.cell(i, j).value = v
        wb.save(str(self.path))
        p = self.plan()
        self.assertEqual((p.changes, p.problems), ([], []))

    def test_control_and_direction_characters_are_not_echoed_in_the_plan(self):
        wbk.add_row(self.path, "Actions", description="Order \u202elaptops\u200b")
        wbk.add_row(self.path, "Actions", id="ABC-A-\u202e99", description="Other")
        p = self.plan()
        text = p.report() + " ".join(m.message for m in p.problems)
        for ch in ("\u202e", "\u200b"):
            self.assertNotIn(ch, text)


class IdsAndPlan(IdCase):
    def test_an_empty_id_gets_the_next_free_id_and_the_plan_line_names_it(self):
        wbk.add_row(self.path, "Actions", description="Order the laptops", owner="Alex Example")
        p = self.plan()
        (c,) = p.changes
        self.assertEqual(c.describe(), "New: Order the laptops → ABC-A-003")
        self.assertIn("New: Order the laptops → ABC-A-003", p.report())
        res = self.apply(p)
        self.assertTrue(res.applied, res.message)
        self.assertEqual(self.s.read("actions", ref="ABC-A-003")["owner"], "Alex Example")
        self.assertEqual(res.created[0]["id"], "ABC-A-003")

    def test_ids_go_out_in_row_order_per_type_with_no_gaps_and_rejecting_a_row_closes_the_gap(self):
        for d in ("First", "Second", "Third"):
            wbk.add_row(self.path, "Actions", description=d)
        wbk.add_row(self.path, "RAID", type="Issue", description="Server is late", impact="Low", likelihood="Low")
        p = self.plan()
        self.assertEqual([c.describe() for c in p.changes],
                         ["New: First → ABC-A-003", "New: Second → ABC-A-004", "New: Third → ABC-A-005",
                          "New: Server is late → ABC-006"])           # actions, RAID items and decisions share one run of numbers
        p.reject(p.changes[1].n)
        self.assertEqual([c.preview for c in p.changes], ["ABC-A-003", "", "ABC-A-004", "ABC-005"])
        p.accept(*[c.n for c in p.changes if c.state != "rejected"])
        res = xi.apply_import(self.s, p, USER)
        self.assertTrue(res.applied, res.message)
        self.assertEqual({m["description"]: m["id"] for m in self.s.read("actions", project="ABC")},
                         {"Draft the cut-over plan": "ABC-A-001", "Book the training room": "ABC-A-002",
                          "First": "ABC-A-003", "Third": "ABC-A-004"})
        self.assertEqual([r["id"] for r in self.s.read("raid", project="ABC")], ["ABC-005"])

    def test_an_archived_or_undone_items_id_is_never_given_again(self):
        self.s.con.execute("INSERT INTO actions (id, project, description, status, raised, source, archived, updated_at) "
                           "SELECT 'ABC-A-007', project, 'Old', 'Closed', raised, 'demo', 1, updated_at FROM actions "
                           "WHERE id = ?", (self.a1,))
        self.s.con.commit()
        wbk.make_workbook(self.s, self.path)
        wbk.add_row(self.path, "Actions", description="Fresh one")
        res = self.apply()
        self.assertTrue(res.applied, res.message)
        self.assertIn("ABC-A-008", self.ids())
        self.assertNotIn("ABC-A-003", self.ids())
        self.s.undo(res.step_id, USER)
        wbk.add_row(self.path, "Actions", description="Another one")
        res2 = self.apply()
        self.assertTrue(res2.applied, res2.message)
        self.assertIn("ABC-A-009", self.ids())              # the undone item's number (008) is not handed out again
        self.assertNotIn("ABC-A-008", self.ids())

    def test_the_same_file_imported_twice_makes_no_duplicates(self):
        wbk.add_row(self.path, "Actions", description="Order the laptops")
        first = self.apply()
        self.assertTrue(first.applied, first.message)
        n = len(self.ids())
        again = self.plan()                       # the same file, unchanged
        self.assertEqual(again.changes, [])
        self.assertFalse(self.apply(again).applied)
        wb = load_workbook(str(self.path))        # saved again by Excel: other bytes, the same row
        wb.save(str(self.path))
        third = self.plan()
        self.assertEqual(third.changes, [])
        self.assertEqual(len(self.ids()), n)

    def test_undo_of_the_import_takes_the_new_items_back_in_one_step(self):
        before = self.snapshot()
        wbk.add_row(self.path, "Actions", description="Order the laptops")
        wbk.add_row(self.path, "Actions", id="ABC-A-099", description="Book a van")
        wbk.add_row(self.path, "RAID", type="Issue", description="Server is late", impact="Low", likelihood="Low")
        steps = self.s.con.execute("SELECT count(*) FROM applies").fetchone()[0]
        res = self.apply()
        self.assertTrue(res.applied, res.message)
        self.assertEqual(self.s.con.execute("SELECT count(*) FROM applies").fetchone()[0], steps + 1)
        out = self.s.undo(res.step_id, USER)
        self.assertEqual(out["skipped"], [])
        self.assertEqual(self.snapshot(), before)

    def test_history_records_the_creation_by_excel_import_and_the_file(self):
        wbk.add_row(self.path, "Actions", description="Order the laptops")
        self.assertTrue(self.apply().applied)
        events = self.s.history("ABC-A-003")
        self.assertTrue(events)
        self.assertEqual({e["src_ref"] for e in events}, {"by Excel import (ABC.xlsx)"})
        self.assertEqual({e["place"] for e in events}, {"excel"})

    def test_two_identical_new_rows_are_both_made_and_the_plan_says_so(self):
        wbk.add_row(self.path, "Actions", description="Order the laptops")
        wbk.add_row(self.path, "Actions", description="Order the laptops")
        p = self.plan()
        self.assertEqual([c.preview for c in p.changes], ["ABC-A-003", "ABC-A-004"])
        self.assertIn("Actions, row 5 is the same as row 4, so two items will be made.", " ".join(p.notes))


class PlaceholderIds(IdCase):
    def test_a_placeholder_in_the_id_cell_means_no_id(self):
        for word in ("TBD", "new", "n/a", "-", "?", "tbc"):
            wbk.add_row(self.path, "Actions", id=word, description="Item " + word.upper())
        p = self.plan()
        self.assertEqual([c.kind for c in p.changes], ["new"] * 6)
        self.assertEqual(p.problems, [])
        self.assertIn("Actions, row 4: “TBD” isn't an ID, so the item gets a new ID.", p.notes)
        res = self.apply(p)
        self.assertTrue(res.applied, res.message)
        self.assertEqual(len(self.ids()), 8)

    def test_a_placeholder_row_is_not_made_twice_on_a_second_import(self):
        wbk.add_row(self.path, "Actions", id="TBD", description="Order the laptops")
        self.assertTrue(self.apply().applied)
        p = self.plan()
        self.assertEqual(p.changes, [])

    def test_the_999_ceiling_says_what_to_do(self):
        self.s.con.execute("INSERT INTO actions (id, project, description, status, raised, source, updated_at) "
                           "SELECT 'ABC-A-999', project, 'Last', 'Open', raised, 'demo', updated_at FROM actions WHERE id = ?",
                           (self.a1,))
        self.s.con.commit()
        wbk.make_workbook(self.s, self.path)
        wbk.add_row(self.path, "Actions", description="One too many")
        with self.assertRaises(Invalid) as cm:
            self.plan()
        self.assertIn("stops at 999", str(cm.exception))
        self.assertIn("Import fewer rows at a time", str(cm.exception))

    def test_a_cell_with_a_digit_is_still_a_bad_id(self):
        wbk.add_row(self.path, "Actions", id="ABC-A-0", description="Almost an ID")
        p = self.plan()
        self.assertEqual(p.changes, [])
        self.assertTrue(p.problems)


class Hostile(IdCase):
    """The black-box attacker: crafted workbooks are refused or handled in plain words, and nothing is half written."""

    def test_a_formula_in_the_id_cell_is_not_read_and_the_row_is_left_out(self):
        wbk.edit(self.path, "Actions", self.a1, id='="ABC-A-0"&"01"')               # a1's own id typed as a formula
        before = self.snapshot()
        p = self.plan()
        self.assertEqual(p.changes, [])                                  # and a1 is not reported as removed
        self.assertIn("Actions, row 2: the ID is a formula, which is not read; the row was left out", p.problems[0].message)
        self.assertEqual(self.snapshot(), before)

    def test_look_alike_ids_are_not_ids(self):
        for bad in ("\u0410\u0412\u0421-A-001", "ABC-A-\uff10\uff10\uff11", "ABC-A-\u0660\u0660\u0661",
                    "ABC\u2011A\u2011001", "ABC-A-001\u200b"):      # Cyrillic, full-width, Arabic-Indic, hyphens
            wbk.add_row(self.path, "Actions", id=bad, description="Look-alike " + bad)
        before = self.snapshot()
        p = self.plan()
        self.assertEqual(p.changes, [])
        self.assertEqual(len(p.problems), 5)
        self.assertTrue(all("isn't an action id" in m.message and "was left out" in m.message for m in p.problems))
        self.assertFalse(self.apply(p).applied)
        self.assertEqual(self.snapshot(), before)

    def test_a_look_alike_of_a_real_id_on_a_real_rows_words_cannot_take_its_place(self):
        wbk.edit(self.path, "Actions", self.a1, id="\u0410\u0412\u0421-A-001")        # Cyrillic A, B, C
        p = self.plan()
        self.assertEqual(p.changes, [])                                  # skipped, and a1 is not "removed" for it
        self.assertEqual(self.ids(), [self.a1, self.a2])

    def test_a_sheet_with_far_too_many_rows_is_refused_whole(self):
        wb = load_workbook(str(self.path))
        ws = wb["Actions"]
        for i in range(xi.MAX_ROWS + 5):
            ws.append([None, "ABC", f"Row {i}"])
        wb.save(str(self.path))
        before = self.snapshot()
        with self.assertRaises(Invalid) as cm:
            self.plan()
        self.assertIn("more than 2,000 rows", str(cm.exception))
        self.assertIn("Nothing was changed", str(cm.exception))
        self.assertEqual(self.snapshot(), before)

    def test_more_new_items_than_numbers_left_is_refused_before_anything_is_tried(self):
        self.s.con.execute("INSERT INTO actions (id, project, description, status, raised, source, updated_at) "
                           "SELECT 'ABC-A-998', project, 'Late', 'Open', raised, 'demo', updated_at FROM actions WHERE id = ?",
                           (self.a1,))
        self.s.con.commit()
        wbk.make_workbook(self.s, self.path)
        for d in ("One", "Two"):
            wbk.add_row(self.path, "Actions", description=d)
        with self.assertRaises(Invalid) as cm:
            self.plan()
        self.assertIn("more new items than ABC has numbers left", str(cm.exception))

    def test_duplicate_empty_id_rows_are_made_as_many_times_as_they_appear_and_said_so(self):
        for _ in range(3):
            wbk.add_row(self.path, "Actions", description="Same again")
        p = self.plan()
        self.assertEqual(len(p.changes), 3)
        self.assertEqual(len([n for n in p.notes if "so two items will be made" in n]), 2)

    def test_one_bad_new_row_means_nothing_is_written(self):
        wbk.add_row(self.path, "Actions", description="Fine row")
        wbk.add_row(self.path, "Actions", description="Bad priority", priority="Sideways")
        before = self.snapshot()
        p = self.plan()
        p.accept(*[c.n for c in p.changes])
        res = xi.apply_import(self.s, p, USER)
        self.assertFalse(res.applied)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.s.con.execute("SELECT count(*) FROM applies WHERE apply_id > ?", (self.demo.last_step(),)).fetchone()[0], 0)

    def test_an_id_with_spaces_or_lower_case_is_not_taken_for_a_known_one(self):
        wbk.add_row(self.path, "Actions", id=" abc-a-001 ", description="Not the same")
        p = self.plan()
        self.assertEqual(p.changes, [])
        self.assertTrue(p.problems)



class HostileShape(IdCase):
    def test_one_cell_far_down_and_across_is_refused_fast_and_small(self):
        import resource
        import time
        wb = load_workbook(str(self.path))
        wb["Actions"]["XFD1000"] = "x"
        wb.save(str(self.path))
        before = self.snapshot()
        r0 = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        t0 = time.time()
        with self.assertRaises(Invalid) as cm:
            self.plan()
        grown = (resource.getrusage(resource.RUSAGE_SELF).ru_maxrss - r0) * (1 if sys.platform == "darwin" else 1024)
        self.assertLess(time.time() - t0, 1.0)
        self.assertLess(grown, 100 * 1024 * 1024)
        self.assertIn("Actions", str(cm.exception))
        self.assertIn("Nothing was changed", str(cm.exception))
        self.assertEqual(self.snapshot(), before)

    def test_one_far_cell_on_every_sheet_is_refused_fast_and_small(self):
        import resource
        import time
        wb = load_workbook(str(self.path))
        for name in ("Actions", "RAID", "Decisions", "Milestones", "Use cases"):
            wb[name]["CV5000"] = "x"                       # row 5000, column 100: inside each sheet's own limits
        wb.save(str(self.path))
        before = self.snapshot()
        r0 = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        t0 = time.time()
        with self.assertRaises(Invalid) as cm:
            self.plan()
        grown = (resource.getrusage(resource.RUSAGE_SELF).ru_maxrss - r0) * (1 if sys.platform == "darwin" else 1024)
        self.assertLess(time.time() - t0, 1.0)
        self.assertLess(grown, 200 * 1024 * 1024)
        self.assertIn("too large", str(cm.exception))
        self.assertIn("Nothing was changed", str(cm.exception))
        self.assertEqual(self.snapshot(), before)

    def test_a_sheet_wide_and_deep_but_under_the_limits_alone_is_refused_by_its_area(self):
        wb = load_workbook(str(self.path))
        wb["Actions"]["CV5000"] = "x"
        wb.save(str(self.path))
        with self.assertRaises(Invalid) as cm:
            self.plan()
        self.assertIn("Actions", str(cm.exception))

    def test_sheets_each_under_the_limit_but_too_large_together_are_refused(self):
        wb = load_workbook(str(self.path))
        for name in ("Actions", "RAID", "Decisions", "Milestones", "Use cases"):
            wb[name]["CV1900"] = "x"                       # 190,000 cells each: fine alone, 950,000 together
        wb.save(str(self.path))
        with self.assertRaises(Invalid) as cm:
            self.plan()
        self.assertIn("too large together", str(cm.exception))

    def test_a_normal_export_size_is_not_refused(self):
        wb = load_workbook(str(self.path))
        wb["Actions"]["AD1500"] = "x"                      # 30 columns by 1,500 rows, as a big real export
        wb.save(str(self.path))
        self.plan()

    def test_too_many_columns_or_rows_alone_are_refused(self):
        for cell in ("CZ2", "A5001"):                      # column 104, row 5001
            wbk.make_workbook(self.s, self.path)
            wb = load_workbook(str(self.path))
            wb["Actions"][cell] = "x"
            wb.save(str(self.path))
            with self.assertRaises(Invalid, msg=cell):
                self.plan()


class ProbableIdEdit(IdCase):
    def test_a_title_edit_to_another_items_title_with_an_owner_edit_applies(self):
        wbk.edit(self.path, "Actions", self.a1, description="Book the training room", owner="Sam")
        wbk.edit(self.path, "Actions", self.a2, description="Book a bigger room")        # and the other row is edited too
        p = self.plan()
        self.assertFalse([m for m in p.problems if "ID was changed" in m.message])
        self.assertEqual(sorted(c.id for c in p.changes), [self.a1, self.a2])
        self.assertTrue(self.apply(p).applied)
        self.assertEqual(self.s.read("actions", ref=self.a1)["owner"], "Sam")

    def test_the_same_edit_with_the_other_row_untouched_applies(self):
        wbk.edit(self.path, "Actions", self.a1, description="Book the training room", owner="Sam")
        p = self.plan()
        self.assertEqual([(c.kind, c.id) for c in p.changes], [("changed", self.a1)])
        self.assertEqual(p.problems, [])

    def test_a_blanked_id_is_flagged_as_a_probable_id_edit(self):
        wbk.edit(self.path, "Actions", self.a2, id=None)
        p = self.plan()
        self.assertEqual(sorted(c.kind for c in p.changes), ["new", "removed"])
        self.assertIn("Actions: This looks like an ID that was changed. The old item shows as no longer in the workbook: don't accept that line if you still want it.", p.notes)

    def test_a_blanked_id_with_an_edited_description_is_flagged_too(self):
        wbk.edit(self.path, "Actions", self.a2, id=None, description="Book a bigger room")
        p = self.plan()
        self.assertIn("Actions: This looks like an ID that was changed. The old item shows as no longer in the workbook: don't accept that line if you still want it.", p.notes)

    def test_a_blanked_id_with_another_field_edited_is_flagged_too(self):
        wbk.edit(self.path, "Actions", self.a2, id=None, owner="Sam")
        p = self.plan()
        self.assertEqual(sorted(c.kind for c in p.changes), ["new", "removed"])
        self.assertTrue([n for n in p.notes if "ID that was changed" in n])

    def test_a_genuinely_new_row_is_not_flagged(self):
        wbk.add_row(self.path, "Actions", description="Order the laptops", owner="Alex Example")
        wbk.drop_row(self.path, "Actions", self.a2)
        p = self.plan()
        self.assertFalse([n for n in p.notes if "ID that was changed" in n])


class LongAndOdd(IdCase):
    def test_a_huge_id_cell_is_shown_short_and_clean(self):
        wbk.add_row(self.path, "Actions", id="ABC-A-" + "9" * 5000, description="Order the laptops")
        wbk.add_row(self.path, "Actions", id="X" * 5000 + "\u202e", description="Other")
        p = self.plan()
        text = p.report()
        self.assertLess(max(len(line) for line in text.splitlines()), 400)
        self.assertTrue(all(len(m.id) < 100 and len(m.message) < 400 for m in p.problems))
        self.assertNotIn("\u202e", text)

    def test_more_control_and_direction_characters_are_not_echoed(self):
        bad = "\u202e\u2066\u200b\u0085\u007f"
        wbk.add_row(self.path, "Actions", id="evil" + bad, description="x" + bad + "y")
        wbk.add_row(self.path, "Actions", description="Fine", owner="Own" + bad + "er")
        p = self.plan()
        text = p.report() + " ".join(m.message + m.id for m in p.problems)
        for ch in bad:
            self.assertNotIn(ch, text)

    def test_a_huge_text_cell_is_refused_in_plain_words(self):
        big = "x" * (xi.MAX_TEXT + 1)
        wbk.add_row(self.path, "Actions", description=big)
        wbk.edit(self.path, "Actions", self.a2, owner=big)
        p = self.plan()
        self.assertEqual(p.changes, [])
        self.assertEqual(len(p.problems), 2)
        for m in p.problems:
            self.assertIn("too long", m.message)
            self.assertLess(len(m.message), 300)


class PlainWords(IdCase):
    def all_text(self, p):
        return p.report()

    def test_writer_messages_use_the_column_names_a_person_sees(self):
        self.assertEqual(xi.plain("actions", "status must be one of Open, Closed (got 'Sideways')"),
                         "Status must be one of Open, Closed (got 'Sideways')")
        self.assertEqual(xi.plain("raid", "missing required field(s): type"), "Type is needed")
        self.assertEqual(xi.plain("raid", "missing required field(s): type, description"), "Type and Description are needed")
        self.assertEqual(xi.plain("milestones", "percent_complete must be a whole number from 0 to 100 (got 101)"),
                         "% complete must be a whole number from 0 to 100 (got 101)")
        self.assertEqual(xi.plain("actions", "unknown label 'L0' (labels: none); add it in Settings first"),
                         "There is no label 'L0' (labels: none); add it in Settings first")

    def test_a_row_with_no_type_or_a_bad_status_reads_plainly_in_the_plan(self):
        wbk.add_row(self.path, "RAID", description="A risk with no type")
        wbk.add_row(self.path, "Actions", description="Order the laptops", labels="L0")
        p = self.plan()
        text = p.report()
        for jargon in ("missing required field", "unknown label", "percent_complete", " a action"):
            self.assertNotIn(jargon, text)
        self.assertIn("Type is needed", text)

    def test_an_action_with_no_title_is_an_action(self):
        wbk.add_row(self.path, "Actions", owner="Alex Example")
        text = self.plan().report()
        self.assertIn("an action with no title", text)
        self.assertNotIn("a action", text)

    def test_a_date_in_a_text_cell_is_shown_as_dd_mm_yyyy(self):
        from datetime import datetime
        wbk.edit(self.path, "Actions", self.a2, owner=datetime(2026, 1, 1))
        p = self.plan()
        (m,) = p.problems
        self.assertIn("01-01-2026", m.message)
        self.assertNotIn("00:00:00", m.message)

    def test_the_result_names_the_ids_actually_given(self):
        for d in ("One", "Two"):
            wbk.add_row(self.path, "Actions", description=d)
        res = self.apply()
        self.assertTrue(res.applied)
        self.assertIn("ABC-A-003, ABC-A-004", res.message)
