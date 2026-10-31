"""#45: linking a work item to an existing use case through POST /api/change (src/clark/changes.py; guarded).

Run: python3 dev/run_tests.py test_changes_use_case_link
Each test makes a real store in a temporary folder (fictional data) and calls the same functions the server calls.
"""
import sqlite3
import unittest

from _demo import USER, DemoStore
from clark import changes, store as store_module


class Link(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store
        self.uc = self.demo.use_case
        self.change = changes.make_change(self.s.path, [], USER)
        self.undo = changes.make_undo(self.s.path, [], USER)
        with self.s.step("dashboard", USER) as st:
            st.create("projects", {"code": "DEF", "name": "Other Programme", "health": "On track"})
            self.other = st.create("use_cases", {"project": "DEF", "title": "Elsewhere", "status": "On track", "source": "demo"})
            self.second = st.create("use_cases", {"project": "ABC", "title": "Receipts", "status": "On track", "source": "demo"})
            self.old = st.create("use_cases", {"project": "ABC", "title": "Retired", "status": "On track", "source": "demo"})
            self.a = st.create("actions", {"project": "ABC", "description": "Draft the plan", "raised": "2026-10-01", "source": "demo"})
            self.r = st.create("raid", {"project": "ABC", "type": "Risk", "description": "Late data", "raised": "2026-10-01",
                                        "impact": "Medium", "likelihood": "Medium", "source": "demo"})
            self.d = st.create("decisions", {"project": "ABC", "decision": "Use the new format", "status": "Pending", "source": "demo"})
        with self.s.step("dashboard", USER) as st:
            st.archive("use_cases", self.old)
        self.kinds = (("actions", self.a), ("raid", self.r), ("decisions", self.d))

    def req(self, kind, ref, value):
        return {"project": "ABC", "kind": kind, "op": "update", "id": ref, "changes": {"use_case": value}}

    def snapshot(self):
        con = sqlite3.connect(str(self.s.path))
        try:
            return (con.execute("SELECT count(*) FROM applies").fetchone()[0], con.execute("SELECT count(*) FROM change_log").fetchone()[0],
                    con.execute("SELECT group_concat(ifnull(use_case, '-')) FROM (SELECT use_case FROM actions UNION ALL "
                                "SELECT use_case FROM raid UNION ALL SELECT use_case FROM decisions)").fetchone()[0])
        finally:
            con.close()

    def refused(self, request, words):
        before = self.snapshot()
        got = self.change(request)
        self.assertEqual((got[0], got[1]["ok"], got[1]["message"]), (400, False, words), request)
        self.assertEqual(self.snapshot(), before, "nothing was written")

    def test_use_case_is_allowed_on_the_three_kinds_and_is_a_column(self):
        for kind, _ in self.kinds:
            self.assertIn("use_case", changes.CHANGE_KINDS[kind]["update"])
            self.assertIn("use_case", store_module.columns(self.s.con, kind))
            self.assertIn("use_case", changes.ITEM_SHOWN[kind])

    def test_link_change_and_clear_each_one_step_with_one_undo(self):
        for kind, ref in self.kinds:
            code, body = self.change(self.req(kind, ref, self.uc))
            self.assertEqual((code, body["ok"], body["item"]["use_case"]), (200, True, self.uc), body)
            self.assertEqual(self.s.read(kind, ref=ref)["use_case"], self.uc)
            code, back = self.undo({"project": "ABC", "apply_id": body["apply_id"]})
            self.assertEqual(code, 200, back)
            self.assertEqual(back["words"], f"Put back: the use case of {ref} is cleared again.")
            self.assertIsNone(self.s.read(kind, ref=ref)["use_case"])
            self.change(self.req(kind, ref, self.uc))
            _, moved = self.change(self.req(kind, ref, self.second))
            self.assertEqual(self.s.read(kind, ref=ref)["use_case"], self.second)
            _, back = self.undo({"project": "ABC", "apply_id": moved["apply_id"]})
            self.assertEqual(back["words"], f"Put back: the use case of {ref} is back to {self.uc}.")
            _, cleared = self.change(self.req(kind, ref, None))
            self.assertIsNone(self.s.read(kind, ref=ref)["use_case"])
            self.assertTrue(cleared["undoable"])

    def test_an_empty_string_clears_the_link_and_stores_nothing_empty(self):
        self.change(self.req("actions", self.a, self.uc))
        code, body = self.change(self.req("actions", self.a, ""))
        self.assertEqual(code, 200, body)
        self.assertIsNone(self.s.read("actions", ref=self.a)["use_case"])

    def test_the_same_value_makes_no_step(self):
        self.change(self.req("actions", self.a, self.uc))
        before = self.snapshot()
        code, body = self.change(self.req("actions", self.a, self.uc))
        self.assertEqual((code, body["apply_id"]), (200, None))
        self.assertEqual(self.snapshot(), before)

    def test_another_projects_use_case_and_a_missing_one_get_the_same_words(self):
        for kind, ref in self.kinds:
            for bad in (self.other, "ABC-U-777", "DEF-U-777", "ABC-A-001", "nonsense"):
                self.refused(self.req(kind, ref, bad), changes.NO_USE_CASE)

    def test_an_archived_use_case_says_restore_it_first(self):
        for kind, ref in self.kinds:
            self.refused(self.req(kind, ref, self.old), changes.ARCHIVED_USE_CASE)

    def test_a_value_that_is_not_text_is_refused(self):
        for bad in (3, True, ["ABC-U-001"], {"a": 1}, "ABC-U-001\n", "   "):
            before = self.snapshot()
            got = self.change(self.req("actions", self.a, bad))
            self.assertEqual((got[0], got[1]["ok"]), (400, False), bad)
            self.assertEqual(self.snapshot(), before)

    def test_another_projects_item_is_not_changed(self):
        self.refused({"project": "DEF", "kind": "actions", "op": "update", "id": self.a, "changes": {"use_case": self.other}},
                     changes.ITEM_NOT_MINE)

    def test_it_goes_with_other_fields_in_one_step(self):
        code, body = self.change({"project": "ABC", "kind": "actions", "op": "update", "id": self.a,
                                  "changes": {"use_case": self.uc, "owner": "Sam Example"}})
        self.assertEqual(code, 200, body)
        self.assertEqual(len({r["apply_id"] if "apply_id" in r else body["apply_id"] for r in self.s.step_rows(body["apply_id"])}), 1)
        self.undo({"project": "ABC", "apply_id": body["apply_id"]})
        row = self.s.read("actions", ref=self.a)
        self.assertIsNone(row["use_case"])
        self.assertNotEqual(row["owner"], "Sam Example")

    def test_the_words_never_hold_the_id_that_was_sent(self):
        got = self.change(self.req("actions", self.a, "ZZZ-U-999"))
        self.assertNotIn("ZZZ", got[1]["message"])


if __name__ == "__main__":
    unittest.main()
