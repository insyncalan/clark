"""Row 1107: linking a use case straight to milestones through POST /api/change (changes.py; guarded), with Undo and History. Fictional data.
Run: python3 dev/run_tests.py test_uc_milestones_change
"""
import sqlite3
import unittest

from _demo import USER, DemoStore
from clark import changes, history, store as sm


class Change(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s, self.uc, self.ms = self.demo.store, self.demo.use_case, self.demo.milestone
        self.change = changes.make_change(self.s.path, [], USER)
        self.undo = changes.make_undo(self.s.path, [], USER)
        with self.s.step("dashboard", USER) as st:
            self.ms2 = st.create("milestones", {"project": "ABC", "name": "Go live", "baseline_date": "2030-06-01", "source": "demo"})
            st.create("projects", {"code": "DEF", "name": "Other", "health": "On track"})
            self.other = st.create("milestones", {"project": "DEF", "name": "Elsewhere", "baseline_date": "2030-06-01", "source": "demo"})

    def req(self, op, ids, uc=None):
        return {"project": "ABC", "kind": "use_cases", "op": op, "id": uc or self.uc, "ids": ids}

    def live(self):
        return sm.use_case_milestone_ids(self.s.con, self.uc)

    def test_add_several_in_one_step_and_one_undo_takes_them_back(self):
        code, body = self.change(self.req("msadd", [self.ms, self.ms2]))
        self.assertEqual((code, body["ok"], body["milestones"], body["undoable"]), (200, True, [self.ms, self.ms2], True), body)
        self.assertEqual(self.live(), sorted([self.ms, self.ms2]))
        code, back = self.undo({"project": "ABC", "apply_id": body["apply_id"]})
        self.assertEqual(code, 200, back)
        self.assertEqual(self.live(), [])

    def test_a_second_add_changes_nothing_and_has_no_undo(self):
        self.change(self.req("msadd", [self.ms]))
        code, body = self.change(self.req("msadd", [self.ms]))
        self.assertEqual((code, body["apply_id"], body["milestones"]), (200, None, []))

    def test_remove_keeps_the_row_and_undo_puts_the_link_back(self):
        self.change(self.req("msadd", [self.ms]))
        code, body = self.change(self.req("msremove", [self.ms]))
        self.assertEqual((code, body["milestones"], self.live()), (200, [self.ms], []))
        self.assertEqual(len(sm.use_case_milestone_history(self.s.con, self.uc)), 1)
        code, back = self.undo({"project": "ABC", "apply_id": body["apply_id"]})
        self.assertEqual(code, 200, back)
        self.assertEqual(self.live(), [self.ms])

    def test_linking_again_after_a_removal_then_removing_again_works(self):
        for op in ("msadd", "msremove", "msadd", "msremove"):
            self.assertEqual(self.change(self.req(op, [self.ms]))[0], 200)
        self.assertEqual((self.live(), len(sm.use_case_milestone_history(self.s.con, self.uc))), ([], 2))

    def test_refusals_write_nothing(self):
        for ids, uc in (([self.other], None), (["ABC-M-099"], None), ([], None), (["nope"], None), ([self.ms, self.other], None),
                        ([self.ms], "ABC-U-099")):
            code, body = self.change(self.req("msadd", ids, uc))
            self.assertEqual((code, body["ok"]), (400, False), ids)
        con = sqlite3.connect(str(self.s.path))
        self.assertEqual(con.execute("SELECT count(*) FROM use_case_milestones").fetchone()[0], 0)
        con.close()

    def test_a_second_add_says_there_is_nothing_to_undo(self):
        """Hunt: a no-op add must not offer an Undo (undoable false, not just no apply_id)."""
        self.change(self.req("msadd", [self.ms]))
        code, body = self.change(self.req("msadd", [self.ms]))
        self.assertEqual((code, body["undoable"], body["apply_id"]), (200, False, None))

    def test_history_shows_the_link_on_both_items(self):
        self.change(self.req("msadd", [self.ms]))
        self.change(self.req("msremove", [self.ms]))
        for item in (self.uc, self.ms):
            kinds = [(e["table"], e["field"]) for e in history.history(self.s.con, item) if e["table"] == "use_case_milestones"]
            self.assertIn(("use_case_milestones", "removed_at"), kinds, item)
            self.assertIn(("use_case_milestones", "milestone"), kinds, item)


if __name__ == "__main__":
    unittest.main()
