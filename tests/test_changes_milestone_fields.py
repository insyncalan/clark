"""Row 828: a milestone's name, owner, workstream, progress and description through the one writer (changes.py): set, clear,
bad values, Undo as one step, History. Fictional data only.

Run: python3 dev/run_tests.py test_changes_milestone_fields
"""
import unittest

from _demo import USER, DemoStore
from clark import changes, history


class Fields(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store
        self.m = self.demo.milestone
        self.change = changes.make_change(self.s.path, [], USER)
        self.undo = changes.make_undo(self.s.path, [], USER)
        with self.s.step("dashboard", USER) as st:
            st.create("workstreams", {"project": "ABC", "name": "Delivery", "source": "demo"})

    def send(self, fields):
        return self.change({"project": "ABC", "kind": "milestones", "op": "update", "id": self.m, "changes": fields, "place": "peek"})

    def ok(self, fields):
        status, body = self.send(fields)
        self.assertEqual((status, body.get("ok")), (200, True), body)
        return body

    def row(self):
        return self.s.read("milestones", ref=self.m)

    def steps(self):
        return self.s.con.execute("SELECT count(*) FROM applies").fetchone()[0]

    def test_all_five_are_set_in_one_step_and_one_undo_puts_them_all_back(self):
        was = {k: self.row()[k] for k in ("name", "owner", "workstream", "percent_complete", "description")}
        before = self.steps()
        body = self.ok({"name": "Go live", "owner": "Sam Example", "workstream": "Delivery", "percent_complete": 40, "description": "Line one\nLine two"})
        self.assertEqual(self.steps(), before + 1)
        now = self.row()
        self.assertEqual((now["name"], now["owner"], now["workstream"], now["percent_complete"], now["description"]),
                         ("Go live", "Sam Example", "Delivery", 40, "Line one\nLine two"))
        self.assertTrue(body["undoable"])
        status, undone = self.undo({"project": "ABC", "apply_id": body["apply_id"]})
        self.assertEqual((status, undone["ok"]), (200, True), undone)
        back = self.row()
        self.assertEqual({k: back[k] for k in was}, was)

    def test_each_optional_field_clears_in_one_step_with_one_undo(self):
        self.ok({"owner": "Sam Example", "workstream": "Delivery", "percent_complete": 10, "description": "Scope"})
        for field in ("owner", "workstream", "percent_complete", "description"):
            with self.subTest(field=field):
                kept = self.row()[field]
                body = self.ok({field: None})
                self.assertIsNone(self.row()[field])
                self.assertTrue(body["undoable"])
                status, undone = self.undo({"project": "ABC", "apply_id": body["apply_id"]})
                self.assertEqual(status, 200, undone)
                self.assertEqual(self.row()[field], kept)

    def linked(self, name):
        """A person on the people list, and the milestone linked to them (owner text and owner_id), as a rename or merge leaves it."""
        with self.s.step("dashboard", USER) as st:
            person = st.add_person(name=name, source="test")
            st.update("milestones", self.m, {"owner": name, "owner_id": person})
        return person

    def test_an_owner_edit_cuts_the_link_so_a_rename_or_merge_cannot_put_the_old_name_back(self):
        a = self.linked("Sam Reed")
        self.ok({"owner": "Someone Else"})
        self.assertEqual((self.row()["owner"], self.row()["owner_id"]), ("Someone Else", None))
        with self.s.step("dashboard", USER) as st:
            st.rename_person(a, "Sam Reid")
        self.assertEqual(self.row()["owner"], "Someone Else")
        b = self.linked("Jo Park")
        self.ok({"owner": "Someone Else"})
        with self.s.step("dashboard", USER) as st:
            st.merge_people(b, a)
        self.assertEqual((self.row()["owner"], self.row()["owner_id"]), ("Someone Else", None))

    def test_clearing_the_owner_clears_the_link_and_a_rename_leaves_it_empty(self):
        a = self.linked("Sam Reed")
        self.ok({"owner": None})
        self.assertEqual((self.row()["owner"], self.row()["owner_id"]), (None, None))
        with self.s.step("dashboard", USER) as st:
            st.rename_person(a, "Sam Reid")
        self.assertEqual((self.row()["owner"], self.row()["owner_id"]), (None, None))

    def test_an_owner_named_as_a_person_links_to_them_and_one_undo_puts_back_both(self):
        a = self.linked("Sam Reed")
        self.ok({"owner": "Someone Else"})
        body = self.ok({"owner": "Sam Reed"})
        self.assertEqual((self.row()["owner"], self.row()["owner_id"]), ("Sam Reed", a))
        undone = self.undo({"project": "ABC", "apply_id": body["apply_id"]})
        self.assertEqual(undone[0], 200, undone)
        self.assertEqual((self.row()["owner"], self.row()["owner_id"]), ("Someone Else", None))
        self.ok({"owner": "Sam Reed"})
        with self.s.step("dashboard", USER) as st:
            st.rename_person(a, "Sam Reid")
        self.assertEqual(self.row()["owner"], "Sam Reid")               # a linked owner follows the person

    def test_an_owner_edit_is_one_history_line_and_the_link_column_is_never_listed(self):
        a = self.linked("Sam Reed")
        body = self.ok({"owner": "Someone Else"})
        lines = [r for r in history.rows_for_item(self.s.con, self.m) if r["step"] == body["apply_id"]]
        self.assertEqual([r["field"] for r in lines], ["Owner"], lines)
        self.assertEqual((lines[0]["from"], lines[0]["to"]), ("Sam Reed", "Someone Else"))
        self.assertEqual(self.undo({"project": "ABC", "apply_id": body["apply_id"]})[0], 200)       # still undone as one step, both columns
        self.assertEqual((self.row()["owner"], self.row()["owner_id"]), ("Sam Reed", a))
        for r in history.rows_for_item(self.s.con, self.m):
            self.assertNotEqual(r["field"], "Owner (linked person)", r)

    def test_the_same_value_again_makes_no_step(self):
        self.ok({"owner": "Sam Example"})
        before = self.steps()
        body = self.ok({"owner": "Sam Example"})
        self.assertEqual((body["apply_id"], body["undoable"], self.steps()), (None, False, before))

    def test_bad_values_are_refused_in_plain_words_and_write_nothing(self):
        for fields in ({"name": ""}, {"name": "   "}, {"name": None}, {"name": "a\nb"}, {"name": "x" * 201}, {"name": 5},
                       {"percent_complete": 101}, {"percent_complete": -1}, {"percent_complete": True}, {"percent_complete": "40"},
                       {"percent_complete": 4.5}, {"owner": "x" * 201}, {"owner": ["x"]}, {"owner": "a‮b"},
                       {"description": "x" * 2001}, {"description": 7}, {"description": "a\u0000b"}, {"workstream": "Nowhere"}):
            with self.subTest(fields=fields):
                before, row = self.steps(), dict(self.row())
                status, body = self.send(fields)
                self.assertEqual((status, body["ok"]), (400, False), body)
                self.assertLessEqual(len(body["message"]), 200)
                self.assertEqual((self.steps(), self.row()), (before, row))

    def test_an_unknown_workstream_is_said_in_the_workstream_words(self):
        status, body = self.send({"workstream": "Nowhere"})
        self.assertEqual((status, body["message"]), (400, changes.NO_WORKSTREAM))

    def test_a_blank_name_says_to_give_the_milestone_a_name(self):
        status, body = self.send({"name": " "})
        self.assertEqual(body["message"], changes.NEW_NEEDS["milestones"])

    def test_history_names_the_fields_with_from_and_to(self):
        self.ok({"owner": "Sam Example", "percent_complete": 25})
        shown = {e["field"]: e for e in history.history(self.s.con, self.m)}
        self.assertEqual((shown["owner"]["after"], shown["percent_complete"]["after"]), ("Sam Example", "25"))

    def test_an_archived_milestone_is_not_changed(self):
        self.assertEqual(self.change({"project": "ABC", "kind": "milestones", "op": "archive", "id": self.m})[0], 200)
        status, body = self.send({"owner": "Sam Example"})
        self.assertEqual((status, body["message"]), (400, changes.ARCHIVED_MILESTONE))


if __name__ == "__main__":
    unittest.main()
