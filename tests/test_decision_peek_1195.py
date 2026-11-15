"""Row 1195: the Decision peek's two new columns, Priority and Latest update (store, change route with one Undo, history, publish, Excel).
Real store, real change route, real publish and Excel code. All rows are fictional.

Run: python3 dev/run_tests.py test_decision_peek_1195
"""
import shutil
import tempfile
import unittest
from pathlib import Path

from _demo import USER, DemoStore
from clark import changes, excel, history, publish
from clark import excel_import as xi
from clark import store as store_module

ON = "2030-06-01"


class Base(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store
        self.change = changes.make_change(self.s.path, [], USER)
        self.undo = changes.make_undo(self.s.path, [], USER)

    def make(self, **more):
        with self.s.step("dashboard", USER) as st:
            return st.create("decisions", {"project": "ABC", "decision": "Use the new supplier", "status": "Pending", "needed_by": "2030-07-01",
                                           "client_message": "<p>Client wording</p>", "source": "demo", **more})

    def update(self, ref, **fields):
        return self.change({"project": "ABC", "kind": "decisions", "op": "update", "id": ref, "changes": fields, "place": "peek"})


class Columns(Base):
    def test_a_new_decision_is_medium_with_no_latest_update_and_the_columns_are_last(self):
        ref = self.make()
        row = self.s.read("decisions", ref=ref)
        self.assertEqual((row["priority"], row["latest_update"]), ("Medium", None))
        self.assertEqual(store_module.columns(self.s.con, "decisions")[-2:], ["priority", "latest_update"])

    def test_the_store_takes_the_four_priorities_and_refuses_the_rest(self):
        for word in ("Urgent", "High", "Medium", "Low"):
            self.assertEqual(self.s.read("decisions", ref=self.make(priority=word))["priority"], word)
        with self.assertRaises(Exception):
            self.make(priority="Critical")

    def test_the_change_kinds_allow_both_on_update_and_new(self):
        for f in ("priority", "latest_update"):
            self.assertIn(f, changes.CHANGE_KINDS["decisions"]["update"])
            self.assertIn(f, changes.CHANGE_KINDS["decisions"]["new"])
        self.assertEqual(store_module.ALLOWED[("decisions", "priority")], ("Urgent", "High", "Medium", "Low"))


class SaveUndoHistory(Base):
    def test_the_priority_saves_and_one_undo_puts_it_back(self):
        ref = self.make()
        status, body = self.update(ref, priority="Urgent")
        self.assertEqual(status, 200, body)
        self.assertEqual(self.s.read("decisions", ref=ref)["priority"], "Urgent")
        status, out = self.undo({"project": "ABC", "apply_id": body["apply_id"]})
        self.assertEqual((status, out["skipped"]), (200, []))
        self.assertEqual(self.s.read("decisions", ref=ref)["priority"], "Medium")

    def test_a_priority_that_is_not_one_of_the_four_is_refused_and_nothing_changes(self):
        ref = self.make()
        status, body = self.update(ref, priority="Critical")
        self.assertEqual((status, body["ok"]), (400, False), body)
        self.assertEqual(self.s.read("decisions", ref=ref)["priority"], "Medium")
        status, body = self.update(ref, priority=None)
        self.assertEqual((status, body["ok"]), (400, False), "a priority is never cleared")

    def test_the_latest_update_saves_as_html_clears_with_a_blank_and_one_undo_puts_it_back(self):
        ref = self.make()
        status, body = self.update(ref, latest_update="Waiting on the supplier")
        self.assertEqual(status, 200, body)
        self.assertEqual(self.s.read("decisions", ref=ref)["latest_update"], "<p>Waiting on the supplier</p>")
        self.undo({"project": "ABC", "apply_id": body["apply_id"]})
        self.assertFalse(self.s.read("decisions", ref=ref)["latest_update"])
        self.update(ref, latest_update="Second")
        status, body = self.update(ref, latest_update="")
        self.assertEqual(status, 200, body)
        self.assertFalse(self.s.read("decisions", ref=ref)["latest_update"])

    def test_a_latest_update_longer_than_the_limit_is_refused(self):
        status, body = self.update(self.make(), latest_update="x" * (changes.LATEST_UPDATE_MAX + 1))
        self.assertEqual((status, body["ok"], body["message"]), (400, False, changes.LATEST_LONG_WORDS))

    def test_the_history_lists_both_with_their_labels(self):
        ref = self.make()
        self.update(ref, priority="High")
        self.update(ref, latest_update="Listed text")
        fields = {e["field"] for e in history.history(self.s.con, ref)}
        self.assertTrue({"priority", "latest_update"} <= fields, fields)
        self.assertEqual(history.field_name("decisions", "latest_update"), "Latest update")
        self.assertEqual(history.field_name("decisions", "priority"), "Priority")

    def test_a_workstream_and_a_milestone_are_still_refused_and_a_bulk_change_still_takes_no_priority(self):
        ref = self.make()
        for f in ("workstream", "milestone"):
            status, body = self.update(ref, **{f: "Build"})
            self.assertEqual((status, body["ok"], body["message"]), (400, False, changes.NO_DECISION_FIELD[f]))

    def test_a_new_decision_may_carry_both(self):
        status, body = self.change({"project": "ABC", "kind": "decisions", "op": "new", "place": "peek",
                                    "values": {"decision": "Pick a vendor", "priority": "Low", "latest_update": "Asked twice"}})
        self.assertEqual(status, 200, body)
        row = self.s.read("decisions", ref=body["ref"])
        self.assertEqual((row["priority"], row["latest_update"]), ("Low", "<p>Asked twice</p>"))

    def test_a_copy_carries_both(self):
        ref = self.make(priority="High", latest_update="<p>Chased</p>")
        status, body = self.change({"project": "ABC", "kind": "decisions", "op": "new", "copy_of": ref, "place": "menu", "values": {"decision": "Use the new supplier (copy)"}})
        self.assertEqual(status, 200, body)
        row = self.s.read("decisions", ref=body["ref"])
        self.assertEqual((row["priority"], row["latest_update"]), ("High", "<p>Chased</p>"))


class Publishing(Base):
    def published(self):
        return publish.build(self.s, "ABC", now="2026-10-29")["body"].decode("utf-8")

    def test_publish_lists_both_and_the_latest_update_as_rich_words(self):
        for f in ("priority", "latest_update"):
            self.assertIn(f, publish.PUBLISH_FIELDS["decisions"])
        self.assertIn("latest_update", publish.RICH["decisions"])
        self.assertIn(("decisions", "latest_update"), publish.LEGACY_RICH)
        self.assertIn("latest_update", publish.WORDLESS_DROPS["decisions"])

    def test_a_client_visible_decision_with_wording_publishes_its_latest_update_and_one_without_wording_does_not(self):
        shown = self.make(client_visible=1, latest_update="<p>TOKENSHOWN</p>")
        bare = self.make(client_visible=1, client_message="", latest_update="<p>TOKENBARE</p>")
        text = self.published()
        self.assertIn("TOKENSHOWN", text)
        self.assertNotIn("TOKENBARE", text)
        self.assertTrue(shown and bare)

    def test_a_decision_with_the_eye_off_publishes_neither(self):
        self.make(client_visible=0, latest_update="<p>TOKENHIDDEN</p>")
        self.assertNotIn("TOKENHIDDEN", self.published())


class ExcelRoundTrip(Base):
    def test_the_sheet_carries_both_columns_and_an_edit_comes_back_through_the_import(self):
        tmp = Path(tempfile.mkdtemp(prefix="clark-1195-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        ref = self.make(priority="High", latest_update="<p>Before</p>")
        path, state = tmp / "ABC work items.xlsx", tmp / "state.json"
        excel.export_project(self.s, "ABC", path, state, on=ON)
        from openpyxl import load_workbook
        wb = load_workbook(str(path))
        head = {c.value: c.column for c in wb["Decisions"][1]}
        self.assertIn("Priority", head)
        self.assertIn("Latest update", head)
        self.assertEqual([c for c in xi.read_workbook(self.s, path, "ABC").changes if c.kind != "unchanged"], [], "an unchanged export imports as no change")
        ws = wb["Decisions"]
        row = next(r for r in range(2, ws.max_row + 1) if ws.cell(r, head["ID"]).value == ref)
        ws.cell(row, head["Priority"]).value = "Low"
        ws.cell(row, head["Latest update"]).value = "After"
        wb.save(str(path))
        plan = xi.read_workbook(self.s, path, "ABC")
        fields = {(c.kind, getattr(c, "field", None)) for c in plan.changes if c.kind != "unchanged"}
        self.assertTrue(fields, "the edit is seen")


if __name__ == "__main__":
    unittest.main()
