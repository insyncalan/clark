"""#97: the eye on a work item (Show to the client, Hide from the client): `client_visible` is changed on an action, a RAID item and
a decision exactly as on a use case. The same 0-or-1 words, one step, one Undo, a history line, and a hidden item leaves the
published file. All rows are fictional.

Run: python3 dev/run_tests.py test_changes_item_eye
"""
import sqlite3
import unittest

from _demo import USER, DemoStore
from clark import changes, history
from clark.publish import select


class Eye(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store
        self.change = changes.make_change(self.s.path, [], USER)
        self.undo = changes.make_undo(self.s.path, [], USER)
        self.a = self.demo.action(workstream="Build", owner="Sara Khan")
        with self.s.step("dashboard", USER) as st:
            self.r = st.create("raid", {"project": "ABC", "type": "Risk", "description": "Supplier slips", "impact": "High",
                                        "likelihood": "Medium", "raised": "2026-10-01", "source": "demo"})
            self.d = st.create("decisions", {"project": "ABC", "decision": "Use the new tool", "status": "Pending",
                                             "needed_by": "2030-01-05", "source": "demo"})
        self.refs = {"actions": self.a, "raid": self.r, "decisions": self.d}

    def eye(self, kind, value, **more):
        return self.change({"project": "ABC", "kind": kind, "op": "update", "id": self.refs[kind], "changes": {"client_visible": value},
                            "place": "menu", **more})

    def flag(self, kind):
        return self.s.read(kind, ref=self.refs[kind])["client_visible"]

    def count(self):
        con = sqlite3.connect(str(self.s.path))
        try:
            return con.execute("SELECT count(*) FROM change_log").fetchone()[0]
        finally:
            con.close()

    def test_each_kind_hides_and_shows_with_one_undo_and_a_reply_the_page_can_draw(self):
        for kind in self.refs:
            with self.subTest(kind=kind):
                self.assertEqual(self.flag(kind), 1)
                status, body = self.eye(kind, 0)
                self.assertEqual((status, body.get("message")), (200, None), body)
                self.assertEqual((self.flag(kind), body["undoable"], body["item"]["client_visible"]), (0, True, 0))
                status, undone = self.undo({"project": "ABC", "apply_id": body["apply_id"]})
                self.assertEqual((status, undone["ok"]), (200, True), undone)
                self.assertEqual(self.flag(kind), 1)
                self.assertIn("shown to the client again", undone["words"])
                self.assertIn(self.refs[kind], undone["words"])      # a work item is called by its id
                status, _ = self.undo({"project": "ABC", "apply_id": body["apply_id"]})
                self.assertEqual(status, 409)

    def test_showing_again_and_a_change_that_changes_nothing(self):
        for kind in self.refs:
            self.eye(kind, 0)
            status, _ = self.eye(kind, 1)
            self.assertEqual((status, self.flag(kind)), (200, 1))
            status, same = self.eye(kind, 1)
            self.assertEqual((status, same["undoable"]), (200, False))      # nothing changed: no step, so no Undo

    def test_a_bad_value_is_refused_in_the_use_cases_words_and_nothing_is_written(self):
        before = self.count()
        for kind in self.refs:
            for bad in (True, False, 2, -1, "1", "yes", None, 1.0, [1], {"a": 1}, ""):
                with self.subTest(kind=kind, bad=bad):
                    status, body = self.eye(kind, bad)
                    self.assertEqual((status, body["ok"], body["message"]), (400, False, changes.FLAG_WORDS))
                    self.assertEqual(self.flag(kind), 1)
        self.assertEqual(self.count(), before)

    def test_the_eye_goes_in_one_step_with_other_fields_and_one_undo_takes_both_back(self):
        status, body = self.change({"project": "ABC", "kind": "actions", "op": "update", "id": self.a,
                                    "changes": {"client_visible": 0, "owner": "Dana Hart"}})
        self.assertEqual(status, 200, body)
        self.assertEqual(len({r["via"] for r in self.s.step_rows(body["apply_id"])}), 1)
        self.undo({"project": "ABC", "apply_id": body["apply_id"]})
        row = self.s.read("actions", ref=self.a)
        self.assertEqual((row["client_visible"], row["owner"]), (1, "Sara Khan"))

    def test_another_projects_item_and_a_missing_one_are_refused(self):
        with self.s.step("dashboard", USER) as st:
            st.create("projects", {"code": "XYZ", "name": "Other Programme", "health": "On track"})
            other = st.create("actions", {"project": "XYZ", "description": "Theirs", "raised": "2026-10-01", "source": "demo"})
        before = self.count()
        for ref in (other, "ABC-A-999"):
            status, body = self.change({"project": "ABC", "kind": "actions", "op": "update", "id": ref, "changes": {"client_visible": 0}})
            self.assertEqual((status, body["ok"], body["message"]), (400, False, changes.ITEM_NOT_MINE))
        self.assertEqual((self.s.read("actions", ref=other)["client_visible"], self.count()), (1, before))

    def test_history_says_who_where_and_from_to_and_the_undo_too(self):
        status, body = self.eye("actions", 0)
        self.undo({"project": "ABC", "apply_id": body["apply_id"]})
        events = history.history(self.s.con, self.a)
        made = [e for e in events if e["field"] == "client_visible" and not e["is_undo"]][0]
        self.assertEqual((made["by_user"], made["place"], made["before"], made["after"]), (USER, "menu", "1", "0"))
        back = [e for e in events if e["is_undo"]][0]
        self.assertEqual((back["before"], back["after"], back["undoes"]), ("0", "1", made["event_id"]))
        self.assertEqual(history.field_name("actions", "client_visible"), "Shown to the client")

    def test_a_hidden_item_leaves_the_published_file_and_showing_it_puts_it_back(self):
        def published():
            out = select({"data": self.s.data_for("ABC"), "hidden": [], "sections": [], "label_rules": [], "as_at": "2026-10-20"})["data"]
            return {k: {r["id"] for r in out[k]} for k in ("actions", "raid", "decisions")}
        shown = published()
        for kind in self.refs:
            self.assertIn(self.refs[kind], shown[kind], kind)
        steps = {kind: self.eye(kind, 0)[1]["apply_id"] for kind in self.refs}
        hidden = published()
        for kind in self.refs:
            self.assertNotIn(self.refs[kind], hidden[kind], kind)
        for kind in self.refs:
            self.undo({"project": "ABC", "apply_id": steps[kind]})
        self.assertEqual(published(), shown)

    def test_a_new_row_may_be_hidden_from_the_start_and_only_with_0_or_1(self):
        """#97: Duplicate of a hidden item creates its copy hidden, in the same step (one Undo)."""
        for kind, vals in (("actions", {"description": "Copy of a"}), ("raid", {"type": "Risk", "description": "Copy of r"}),
                           ("decisions", {"decision": "Copy of d"})):
            for eye in (0, 1):
                r = self.change({"project": "ABC", "kind": kind, "op": "new", "values": {**vals, "client_visible": eye}, "place": "menu"})
                self.assertEqual(r[0], 200, r)
                self.assertEqual(self.s.read(kind, ref=r[1]["ref"])["client_visible"], eye, (kind, eye))
            bad = self.change({"project": "ABC", "kind": kind, "op": "new", "values": {**vals, "client_visible": True}, "place": "menu"})
            self.assertNotEqual(bad[0], 200, "True is not 0 or 1")
            self.assertNotEqual(self.change({"project": "ABC", "kind": kind, "op": "new", "values": {**vals, "client_visible": "0"}, "place": "menu"})[0], 200)


if __name__ == "__main__":
    unittest.main()
