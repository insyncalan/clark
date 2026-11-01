"""Duplicate on a work item: the copy is made from the item itself (`copy_of`), so it keeps every field it has, the eye included
(a copy of an item hidden from the client is hidden too, and is not in the published file), its title ends "(copy)", its source says
what it was copied from, and it is one step with one Undo. All rows are fictional.

Run: python3 dev/run_tests.py test_changes_duplicate
"""
import unittest

from _demo import USER, DemoStore
from clark import changes
from clark.publish import select


class Duplicate(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store
        self.change = changes.make_change(self.s.path, [], USER)
        self.undo = changes.make_undo(self.s.path, [], USER)
        self.a = self.demo.action(workstream="Build", owner="Sara Khan")
        with self.s.step("dashboard", USER) as st:
            st.update("actions", self.a, {"status": "Delayed", "latest_update": "Waiting on the supplier.", "priority": "High"})
            self.r = st.create("raid", {"project": "ABC", "type": "Risk", "description": "Supplier slips", "impact": "High",
                                        "likelihood": "Medium", "raised": "2026-10-01", "source": "demo", "response_action": "Ask for a date"})
            self.d = st.create("decisions", {"project": "ABC", "decision": "Use the new tool", "status": "Made", "date": "2026-10-02",
                                             "made_by": "Dana Hart", "source": "demo", "reasoning": "It is cheaper"})
        self.refs = {"actions": self.a, "raid": self.r, "decisions": self.d}

    def dup(self, kind, ref=None, **more):
        return self.change({"project": "ABC", "kind": kind, "op": "new", "copy_of": ref or self.refs[kind], "place": "menu", **more})

    def published(self):
        out = select({"data": self.s.data_for("ABC"), "hidden": [], "sections": [], "label_rules": [], "as_at": "2026-10-20"})["data"]
        return {k: {r["id"] for r in out[k]} for k in ("actions", "raid", "decisions")}

    def test_the_copy_keeps_every_field_and_says_it_is_a_copy(self):
        keep = {"actions": ("owner", "priority", "due_date", "workstream", "milestone", "status", "latest_update", "client_visible", "client_message", "use_case"),
                "raid": ("type", "owner", "impact", "likelihood", "priority", "due_date", "workstream", "status", "response_action", "client_visible"),
                "decisions": ("made_by", "status", "date", "needed_by", "reasoning", "client_visible")}
        title = {"actions": "description", "raid": "description", "decisions": "decision"}
        for kind, ref in self.refs.items():
            with self.subTest(kind=kind):
                status, body = self.dup(kind)
                self.assertEqual((status, body["ok"]), (200, True), body)
                self.assertNotEqual(body["ref"], ref)
                old, new = self.s.read(kind, ref=ref), self.s.read(kind, ref=body["ref"])
                for f in keep[kind]:
                    self.assertEqual(new[f], old[f], f)
                self.assertEqual(new[title[kind]], old[title[kind]] + " (copy)")
                self.assertEqual((new["source"], new["archived"]), ("Duplicated from " + ref, 0))
        self.assertEqual(self.s.read("actions", ref=self.a)["status"], "Delayed", "the original is as it was")

    def test_a_copy_of_a_hidden_item_stays_hidden_and_is_not_in_the_published_file(self):
        for kind, ref in self.refs.items():
            with self.subTest(kind=kind):
                self.assertEqual(self.change({"project": "ABC", "kind": kind, "op": "update", "id": ref, "changes": {"client_visible": 0}})[0], 200)
                self.assertNotIn(ref, self.published()[kind])
                status, body = self.dup(kind)
                self.assertEqual(status, 200, body)
                self.assertEqual(self.s.read(kind, ref=body["ref"])["client_visible"], 0)
                self.assertNotIn(body["ref"], self.published()[kind], "the copy of a hidden item is not in the published file")
                self.assertNotIn(ref, self.published()[kind])

    def test_a_copy_of_a_shown_item_is_shown_and_published(self):
        status, body = self.dup("actions")
        self.assertEqual(self.s.read("actions", ref=body["ref"])["client_visible"], 1)
        self.assertIn(body["ref"], self.published()["actions"])

    def test_one_step_one_undo(self):
        status, body = self.dup("actions")
        self.assertTrue(body["apply_id"])
        status, undone = self.undo({"project": "ABC", "apply_id": body["apply_id"]})
        self.assertEqual((status, undone["ok"]), (200, True), undone)
        self.assertIsNone(self.s.read("actions", ref=body["ref"]))

    def test_a_long_title_is_cut_so_the_copy_still_fits(self):
        with self.s.step("dashboard", USER) as st:
            st.update("actions", self.a, {"description": "x" * 200})
        status, body = self.dup("actions")
        self.assertEqual(status, 200, body)
        got = self.s.read("actions", ref=body["ref"])["description"]
        self.assertEqual((len(got), got.endswith(" (copy)")), (200, True))

    def test_another_projects_item_a_missing_one_and_an_archived_one_are_refused_alike(self):
        with self.s.step("dashboard", USER) as st:
            st.create("projects", {"code": "XYZ", "name": "Other Programme", "health": "On track"})
            other = st.create("actions", {"project": "XYZ", "description": "Theirs", "raised": "2026-10-01", "source": "demo"})
            gone = st.create("actions", {"project": "ABC", "description": "Gone", "raised": "2026-10-01", "source": "demo"})
            st.archive("actions", gone)
        for ref in (other, "ABC-A-999", gone, 7, None):
            if ref is None:
                continue
            status, body = self.dup("actions", ref)
            self.assertEqual((status, body["ok"], body["message"]), (400, False, changes.ITEM_NOT_MINE), ref)
        self.assertEqual(len(self.s.data_for("XYZ")["actions"]), 1)

    def test_the_request_cannot_choose_the_copys_fields_or_mix_values_and_a_copy(self):
        status, body = self.dup("actions", values={"description": "Mine"})
        self.assertEqual((status, body["ok"]), (400, False))
        status, body = self.change({"project": "ABC", "kind": "report_sections", "op": "new", "copy_of": self.a, "values": {"type": "text", "title": "t"}})
        self.assertEqual((status, body["ok"]), (400, False), "only a work item can be copied")
        status, body = self.change({"project": "ABC", "kind": "milestones", "op": "new", "copy_of": self.a})
        self.assertEqual((status, body["ok"]), (400, False))


if __name__ == "__main__":
    unittest.main()
