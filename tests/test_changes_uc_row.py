"""#485: the two writes behind a use case's row on the Dashboard in Edit: a next step added from the row (a new action that names the
use case, in one step) and several existing work items linked to the use case in one step (op "link" on a use case), each with one
Undo. The eye and "Where it stands" use the existing use case update (test_changes_use_cases), and a use case taken off the page is
left out of a published file (checked here against the same select the file is made with).

Run: python3 dev/run_tests.py test_changes_uc_row
"""
import sqlite3
import unittest

from _demo import USER, DemoStore
from clark import changes, publish


class Setup(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store
        self.uc = self.demo.use_case
        self.change = changes.make_change(self.s.path, [], USER)
        self.undo = changes.make_undo(self.s.path, [], USER)
        with self.s.step("dashboard", USER) as st:
            st.create("projects", {"code": "DEF", "name": "Other Programme", "health": "On track"})
            self.other_uc = st.create("use_cases", {"project": "DEF", "title": "Elsewhere", "status": "On track", "source": "demo"})
            self.second = st.create("use_cases", {"project": "ABC", "title": "Receipts", "status": "On track", "source": "demo"})
            self.old = st.create("use_cases", {"project": "ABC", "title": "Retired", "status": "On track", "source": "demo"})
            self.a = st.create("actions", {"project": "ABC", "description": "Draft the plan", "raised": "2026-10-01", "source": "demo"})
            self.r = st.create("raid", {"project": "ABC", "type": "Risk", "description": "Late data", "raised": "2026-10-01",
                                        "impact": "Medium", "likelihood": "Medium", "source": "demo"})
            self.d = st.create("decisions", {"project": "ABC", "decision": "Use the new format", "status": "Pending", "source": "demo"})
            self.foreign = st.create("actions", {"project": "DEF", "description": "Not ours", "raised": "2026-10-01", "source": "demo"})
            self.gone = st.create("actions", {"project": "ABC", "description": "Archived one", "raised": "2026-10-01", "source": "demo"})
        with self.s.step("dashboard", USER) as st:
            st.archive("use_cases", self.old)
            st.archive("actions", self.gone)

    def counts(self):
        con = sqlite3.connect(str(self.s.path))
        try:
            return con.execute("SELECT (SELECT count(*) FROM applies), (SELECT count(*) FROM change_log), (SELECT count(*) FROM actions), "
                               "(SELECT group_concat(ifnull(use_case, '-')) FROM (SELECT use_case FROM actions UNION ALL SELECT use_case FROM raid "
                               "UNION ALL SELECT use_case FROM decisions))").fetchone()
        finally:
            con.close()


class NextStep(Setup):
    def add(self, values, **more):
        return self.change({"project": "ABC", "kind": "actions", "op": "new", "values": values, **more})

    def test_a_next_step_names_its_use_case_and_is_one_step_with_one_undo(self):
        before = self.counts()
        code, body = self.add({"description": "Check the totals", "owner": "Sam", "due_date": "2026-11-09", "use_case": self.uc}, place="report")
        self.assertEqual((code, body.get("message")), (200, None), body)
        row = self.s.read("actions", ref=body["ref"])
        self.assertEqual((row["use_case"], row["owner"], row["description"], row["client_visible"], row["status"]), (self.uc, "Sam", "Check the totals", 1, "Open"))
        self.assertEqual(self.counts()[0], before[0] + 1, "one step")
        self.assertTrue(body["apply_id"])
        code, undone = self.undo({"project": "ABC", "apply_id": body["apply_id"]})
        self.assertEqual((code, undone["ok"]), (200, True), undone)
        self.assertIsNone(self.s.read("actions", ref=body["ref"]), "the Undo took the new step away")

    def test_it_is_refused_for_a_use_case_that_is_not_this_projects_or_is_archived_or_missing(self):
        for use_case, words in ((self.other_uc, changes.NO_USE_CASE), (self.old, changes.ARCHIVED_USE_CASE), ("ABC-U-099", changes.NO_USE_CASE), ("not an id", changes.NO_USE_CASE)):
            with self.subTest(use_case=use_case):
                before = self.counts()
                code, body = self.add({"description": "Check the totals", "use_case": use_case})
                self.assertEqual((code, body["ok"], body["message"]), (400, False, words))
                self.assertEqual(self.counts(), before, "nothing was written")

    def test_without_a_use_case_it_is_as_it_was(self):
        code, body = self.add({"description": "Check the totals"})
        self.assertEqual(code, 200)
        self.assertIsNone(self.s.read("actions", ref=body["ref"])["use_case"])

    def test_only_an_action_can_be_added_with_a_use_case(self):
        self.assertIn("use_case", changes.CHANGE_KINDS["actions"]["new"])
        for kind in ("raid", "decisions"):
            self.assertNotIn("use_case", changes.CHANGE_KINDS[kind]["new"])


class Link(Setup):
    def link(self, ids, ref=None, project="ABC", **more):
        return self.change({"project": project, "kind": "use_cases", "op": "link", "id": self.uc if ref is None else ref, "ids": ids, **more})

    def linked(self):
        return [self.s.read(t, ref=i)["use_case"] for t, i in (("actions", self.a), ("raid", self.r), ("decisions", self.d))]

    def test_three_kinds_are_linked_in_one_step_and_one_undo_puts_them_all_back(self):
        before = self.counts()
        code, body = self.link([self.a, self.r, self.d], place="report")
        self.assertEqual((code, body.get("message")), (200, None), body)
        self.assertEqual(self.linked(), [self.uc] * 3)
        self.assertEqual(self.counts()[0], before[0] + 1, "one step")
        self.assertTrue(body["undoable"])
        self.assertEqual(sorted(body["linked"]), sorted([self.a, self.r, self.d]))
        self.assertEqual(len({r["via"] for r in self.s.step_rows(body["apply_id"])}), 1)
        code, undone = self.undo({"project": "ABC", "apply_id": body["apply_id"]})
        self.assertEqual((code, undone["ok"]), (200, True), undone)
        self.assertEqual(self.linked(), [None] * 3)

    def test_an_item_moves_from_another_use_case_and_an_item_already_there_is_left_alone(self):
        self.assertEqual(self.link([self.a], ref=self.second)[0], 200)
        code, body = self.link([self.a, self.r])
        self.assertEqual(code, 200, body)
        self.assertEqual(self.linked()[:2], [self.uc, self.uc])
        code, again = self.link([self.a, self.r])
        self.assertEqual(code, 200)
        self.assertFalse(again["undoable"], "nothing changed: no Undo")

    def test_each_refusal_is_in_plain_words_and_writes_nothing(self):
        cases = (
            ({"ids": [self.foreign]}, changes.ITEM_NOT_MINE),
            ({"ids": [self.gone]}, changes.ITEM_NOT_MINE),
            ({"ids": [self.a, "ABC-A-099"]}, changes.ITEM_NOT_MINE),
            ({"ids": [self.second]}, changes.ITEM_NOT_MINE),          # a use case is not a work item
            ({"ids": ["x"]}, changes.ITEM_NOT_MINE),
            ({"ids": [self.a], "ref": self.other_uc}, changes.UC_NOT_MINE),
            ({"ids": [self.a], "ref": self.old}, changes.ARCHIVED_USE_CASE),
            ({"ids": [self.a], "ref": "ABC-U-099"}, changes.UC_NOT_MINE),
            ({"ids": []}, changes.LINK_NOTHING),
            ({"ids": "ABC-A-001"}, changes.LINK_NOTHING),
            ({"ids": [self.a] * (changes.MAX_PICK + 1)}, changes.PICK_TOO_MANY),
        )
        for case, words in cases:
            with self.subTest(case=case):
                before = self.counts()
                code, body = self.link(case["ids"], ref=case.get("ref"))
                self.assertEqual((code, body["ok"], body["message"]), (400, False, words))
                self.assertEqual(self.counts(), before, "nothing was written")

    def test_the_request_takes_only_its_own_keys_and_the_use_case_is_not_given_a_field(self):
        before = self.counts()
        code, body = self.change({"project": "ABC", "kind": "use_cases", "op": "link", "id": self.uc, "ids": [self.a], "changes": {"title": "x"}})
        self.assertEqual((code, body["ok"]), (400, False))
        self.assertEqual(self.counts(), before)

    def test_an_archived_project_is_read_only(self):
        with self.s.step("dashboard", USER) as st:
            st.archive("projects", "ABC")
        code, body = self.link([self.a])
        self.assertEqual((code, body["ok"], body["message"]), (400, False, changes.PROJECT_NOT_ACTIVE))


class Eye(Setup):
    """The eye on the dashboard row is the use case's own flag (client_visible): one step, one Undo, and a use case that is off the page
    is left out of what a published file is made from (publish.select), with the next steps that named it."""

    def published(self):
        data = publish.select(publish.read_inputs(self.s, "ABC", "2026-10-29"))["data"]
        return sorted(u["id"] for u in data["use_cases"]), sorted(p["id"] for p in data["use_case_pages"])

    def test_one_step_one_undo_and_a_published_file_leaves_it_out(self):
        self.assertIn(self.uc, self.published()[0])
        before = self.counts()
        code, body = self.change({"project": "ABC", "kind": "use_cases", "op": "update", "id": self.uc, "changes": {"client_visible": 0}, "place": "eye"})
        self.assertEqual((code, body.get("message")), (200, None), body)
        self.assertTrue(body["undoable"])
        self.assertEqual(self.counts()[0], before[0] + 1, "one step")
        self.assertNotIn(self.uc, self.published()[0], "off the page: out of the file")
        self.assertNotIn(self.uc, self.published()[1])
        self.assertIn(self.second, self.published()[0], "the others stay")
        code, undone = self.undo({"project": "ABC", "apply_id": body["apply_id"]})
        self.assertEqual((code, undone["ok"]), (200, True), undone)
        self.assertIn(self.uc, self.published()[0], "back on the page: back in the file")

    def test_a_standing_text_is_one_step_with_one_undo(self):
        before = self.counts()
        code, body = self.change({"project": "ABC", "kind": "use_cases", "op": "update", "id": self.uc, "changes": {"standing": "<p>Two suppliers live.</p>"}, "place": "cell"})
        self.assertEqual((code, body.get("message")), (200, None), body)
        self.assertEqual(self.counts()[0], before[0] + 1)
        code, undone = self.undo({"project": "ABC", "apply_id": body["apply_id"]})
        self.assertEqual((code, undone["ok"]), (200, True), undone)
        self.assertEqual(self.s.read("use_cases", ref=self.uc)["standing"], "")


if __name__ == "__main__":
    unittest.main()
