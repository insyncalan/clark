"""Row 1185: Latest update on a risk, an issue and a milestone (store column, change route with one Undo, history, publish, Excel round trip).
Real store, real change route, real publish and Excel code. All rows are fictional.

Run: python3 dev/run_tests.py test_latest_update_1185
"""
import shutil
import tempfile
import unittest
from pathlib import Path

from _demo import USER, DemoStore
from clark import changes, excel, history, publish
from clark import excel_import as xi
from clark import store as store_module

KINDS = ("raid-risk", "raid-issue", "milestones")
ON = "2030-06-01"


class Base(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store
        self.change = changes.make_change(self.s.path, [], USER)
        self.undo = changes.make_undo(self.s.path, [], USER)

    def make(self, kind, **more):
        """A client-visible item of the kind with client wording; returns (table, ref)."""
        with self.s.step("dashboard", USER) as st:
            if kind == "milestones":
                return "milestones", st.create("milestones", {"project": "ABC", "name": "Go live", "baseline_date": "2030-03-01",
                                                              "client_message": "<p>Client wording</p>", "source": "demo", **more})
            return "raid", st.create("raid", {"project": "ABC", "type": kind.split("-")[1].capitalize(), "description": "Supplier late",
                                              "raised": "2026-10-01", "client_message": "<p>Client wording</p>", "source": "demo", **more})

    def set_latest(self, table, ref, text):
        return self.change({"project": "ABC", "kind": table, "op": "update", "id": ref,
                            "changes": {"latest_update": text}, "place": "peek"})


class Column(Base):
    def test_the_column_is_on_risks_issues_and_milestones_and_in_a_fresh_file(self):
        for t in ("raid", "milestones", "actions"):
            self.assertIn("latest_update", store_module.columns(self.s.con, t))
        self.assertIn("latest_update", store_module.columns(self.s.con, "decisions"))      # row 1195 (step 26)

    def test_the_change_kinds_allow_it_on_update_and_new(self):
        for t in ("raid", "milestones"):
            self.assertIn("latest_update", changes.CHANGE_KINDS[t]["update"], t)
            self.assertIn("latest_update", changes.CHANGE_KINDS[t]["new"], t)
        self.assertIn("latest_update", changes.CHANGE_KINDS["decisions"]["update"])      # row 1195


class SaveUndoHistory(Base):
    def test_a_change_saves_as_the_editors_html_and_one_undo_puts_it_back(self):
        for kind in KINDS:
            with self.subTest(kind=kind):
                table, ref = self.make(kind)
                status, body = self.set_latest(table, ref, "Waiting on the supplier")
                self.assertEqual(status, 200, body)
                self.assertEqual(self.s.read(table, ref=ref)["latest_update"], "<p>Waiting on the supplier</p>")
                status, out = self.undo({"project": "ABC", "apply_id": body["apply_id"]})
                self.assertEqual((status, out["skipped"]), (200, []))
                self.assertFalse(self.s.read(table, ref=ref)["latest_update"])

    def test_a_blank_text_clears_it_and_a_second_change_undoes_to_the_first(self):
        for kind in KINDS:
            with self.subTest(kind=kind):
                table, ref = self.make(kind)
                self.set_latest(table, ref, "First")
                status, body = self.set_latest(table, ref, "Second")
                self.assertEqual(status, 200, body)
                self.undo({"project": "ABC", "apply_id": body["apply_id"]})
                self.assertEqual(self.s.read(table, ref=ref)["latest_update"], "<p>First</p>")
                status, body = self.set_latest(table, ref, "")
                self.assertEqual(status, 200, body)
                self.assertFalse(self.s.read(table, ref=ref)["latest_update"])

    def test_the_limit_of_a_thousand_characters_holds(self):
        for kind in KINDS:
            with self.subTest(kind=kind):
                table, ref = self.make(kind)
                status, _ = self.set_latest(table, ref, "w" * 1001)
                self.assertEqual(status, 400)
                self.assertFalse(self.s.read(table, ref=ref)["latest_update"])

    def test_a_script_in_the_text_is_cleaned(self):
        table, ref = self.make("milestones")
        status, body = self.set_latest(table, ref, "<p>Fine</p><script>x()</script>")
        self.assertEqual(status, 200, body)
        self.assertNotIn("<script", self.s.read(table, ref=ref)["latest_update"])

    def test_a_new_item_can_carry_one(self):
        for kind in KINDS:
            with self.subTest(kind=kind):
                table, ref = self.make(kind, latest_update="<p>Born with one</p>")
                self.assertEqual(self.s.read(table, ref=ref)["latest_update"], "<p>Born with one</p>")

    def test_the_history_lists_it_with_the_label_and_the_undo(self):
        for kind in KINDS:
            with self.subTest(kind=kind):
                table, ref = self.make(kind)
                _, body = self.set_latest(table, ref, "Listed text")
                events = [e for e in history.history(self.s.con, ref) if e["field"] == "latest_update"]
                self.assertEqual(len(events), 1)
                self.assertIn("Listed text", events[0]["after"])
                self.assertEqual(history.field_name(table, "latest_update"), "Latest update")
                self.undo({"project": "ABC", "apply_id": body["apply_id"]})
                events = [e for e in history.history(self.s.con, ref) if e["field"] == "latest_update"]
                self.assertTrue(any(not e["in_force"] for e in events))


class UndoWords(Base):
    def test_the_undo_sentence_names_the_field_and_never_the_text(self):
        for kind in KINDS:
            with self.subTest(kind=kind):
                table, ref = self.make(kind)
                words = changes._field_words({"field": "latest_update", "to": "A secret sentence", "ref": ref}, ref)
                self.assertEqual(words, f"the latest update of {ref} is back as it was")


class Published(Base):
    def published(self):
        return publish.build(self.s, "ABC", now="2026-10-29")["body"].decode("utf-8")

    def test_publish_lists_the_field_as_rich_for_both_kinds(self):
        for t in ("raid", "milestones"):
            self.assertIn("latest_update", publish.PUBLISH_FIELDS[t], t)
            self.assertIn("latest_update", publish.RICH[t], t)
            self.assertIn((t, "latest_update"), publish.LEGACY_RICH)

    def test_a_plain_client_visible_item_with_client_wording_publishes_it(self):
        for kind in KINDS:
            with self.subTest(kind=kind):
                table, ref = self.make(kind)
                token = "zz-1185-" + kind
                self.set_latest(table, ref, token)
                self.assertIn(token, self.published())

    def test_blank_client_wording_keeps_it_out(self):
        for kind in KINDS:
            with self.subTest(kind=kind):
                table, ref = self.make(kind, client_message="")
                token = "zz-1185-blank-" + kind
                self.set_latest(table, ref, token)
                self.assertNotIn(token, self.published())

    def test_not_client_visible_report_hidden_sensitive_and_archived_keep_it_out(self):
        for kind in KINDS:
            table, ref = self.make(kind)
            token = "zz-1185-gate-" + kind
            self.set_latest(table, ref, token)
            with self.s.step("dashboard", USER) as st:
                st.update(table, ref, {"client_visible": 0})
            self.assertNotIn(token, self.published(), kind + " eye off")
            with self.s.step("dashboard", USER) as st:
                st.update(table, ref, {"client_visible": 1})
                st.create("report_hidden", {"project": "ABC", "item_id": ref})
            self.assertNotIn(token, self.published(), kind + " report hidden")
            if table == "raid":
                with self.s.step("dashboard", USER) as st:
                    st.create("item_labels", {"item_id": ref, "label": "Sensitive"})
                self.assertNotIn(token, self.published(), kind + " sensitive")

    def test_an_archived_item_keeps_it_out_and_the_open_one_beside_it_has_it(self):
        for kind in KINDS:
            with self.subTest(kind=kind):
                table, ref = self.make(kind)
                other = self.make(kind)[1]
                token = "zz-1185-arch-" + kind
                self.set_latest(table, ref, token)
                open_token = "zz-1185-open-" + kind
                self.set_latest(table, other, open_token)
                with self.s.step("dashboard", USER) as st:
                    st.archive(table, ref)
                text = self.published()
                self.assertNotIn(token, text, "archived")
                self.assertIn(open_token, text, "the open one is published")

    def test_a_decision_publishes_its_latest_update_as_rich_words_since_row_1195(self):
        self.assertIn("latest_update", publish.PUBLISH_FIELDS["decisions"])


class ExcelRoundTrip(Base):
    def test_both_sheets_carry_the_column_and_an_edit_comes_back_through_the_import(self):
        tmp = Path(tempfile.mkdtemp(prefix="clark-1185-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        refs = {k: self.make(k, latest_update="<p>Before</p>") for k in ("raid-risk", "milestones")}
        path, state = tmp / "ABC work items.xlsx", tmp / "state.json"
        excel.export_project(self.s, "ABC", path, state, on=ON)
        from openpyxl import load_workbook
        wb = load_workbook(str(path))
        for sheet in ("Risks & Issues", "Milestones"):
            self.assertIn(("Latest update"), [c.value for c in wb[sheet][1]], sheet)
        plan = xi.read_workbook(self.s, path, "ABC")
        self.assertEqual([c for c in plan.changes if c.kind != "unchanged"], [], "an unchanged export imports as no change")
        for sheet, key in (("Risks & Issues", "raid-risk"), ("Milestones", "milestones")):
            ws = wb[sheet]
            head = {c.value: c.column for c in ws[1]}
            row = next(r for r in range(2, ws.max_row + 1) if ws.cell(r, head["ID"]).value == refs[key][1])
            ws.cell(row, head["Latest update"]).value = "After the edit"
            if key == "milestones":
                ws.cell(row, head["State reason"]).value = "Waiting on the venue"          # a neighbouring text column in the same import
        wb.save(str(path))
        plan = xi.read_workbook(self.s, path, "ABC")
        plan.confirm_unrecorded()            # openpyxl saved the file again, so it has no export record
        plan.accept_all()
        done = xi.apply_import(self.s, plan, USER, state_path=state)
        self.assertTrue(done.applied, done.message)
        self.assertEqual(self.s.read("milestones", ref=refs["milestones"][1])["state_reason"], "Waiting on the venue")
        for table, ref in refs.values():
            self.assertIn("After the edit", self.s.read(table, ref=ref)["latest_update"], table)


if __name__ == "__main__":
    unittest.main()
