"""Row 1107, the mutation hunt on PR 1382: what the first tests left unpinned. Fictional data only.
Every refusal says its own words (a layer that went missing would still refuse, in other words), a milestone archived after it was linked
can still be unlinked, an Undo is for the project and the route that made the step, and a link's number is never one a logged link had.
Run: python3 dev/run_tests.py test_uc_milestones_mutants_1382
"""
import unittest

from _demo import USER, DemoStore
from clark import changes, store as sm
from clark.store import Invalid


class Refusals(unittest.TestCase):
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
            self.other_uc = st.create("use_cases", {"project": "DEF", "ref": "DEF-1", "title": "Elsewhere case", "status": "On track", "source": "demo"})

    def req(self, op, ids, uc=None, project="ABC"):
        return {"project": project, "kind": "use_cases", "op": op, "id": uc or self.uc, "ids": ids}

    def live(self):
        return sm.use_case_milestone_ids(self.s.con, self.uc)

    def said(self, req, words):
        code, body = self.change(req)
        self.assertEqual((code, body["ok"]), (400, False), body)
        self.assertEqual(body["message"], words)
        self.assertEqual(sm.use_case_milestone_history(self.s.con), [], "nothing was written")

    def test_each_refusal_says_its_own_words(self):
        self.said(self.req("msadd", []), changes.MS_NOTHING)
        self.said(self.req("msadd", "ABC-M-001"), changes.MS_NOTHING)
        self.said(self.req("msadd", [self.ms] * 1 + ["ABC-M-%03d" % i for i in range(changes.MAX_PICK)]), changes.PICK_TOO_MANY)
        for bad in (["ABC-M-099"], [self.other], ["nope"], [7], [self.ms, self.other], [self.demo.action()]):
            self.said(self.req("msadd", bad), changes.MS_NOT_MINE)
        self.said(self.req("msremove", [self.other]), changes.MS_NOT_MINE)
        self.said(self.req("msadd", [self.ms], uc="ABC-U-099"), changes.UC_NOT_MINE)
        self.said(self.req("msadd", [self.ms], uc=self.other_uc), changes.UC_NOT_MINE)
        self.said(self.req("msadd", [self.ms], uc=5), changes.UC_NOT_MINE)

    def test_an_archived_use_case_or_milestone_or_project_is_refused_in_its_own_words(self):
        with self.s.step("dashboard", USER) as st:
            st.archive("milestones", self.ms2)
        self.said(self.req("msadd", [self.ms2]), changes.MS_NOT_MINE)
        self.said(self.req("msadd", [self.ms, self.ms2]), changes.MS_NOT_MINE)
        with self.s.step("dashboard", USER) as st:
            st.archive("use_cases", self.uc)
        self.said(self.req("msadd", [self.ms]), changes.ARCHIVED_USE_CASE)
        self.said(self.req("msremove", [self.ms]), changes.ARCHIVED_USE_CASE)

    def test_an_archived_project_is_refused(self):
        with self.s.step("dashboard", USER) as st:
            st.archive("projects", "ABC")
        self.said(self.req("msadd", [self.ms]), changes.PROJECT_NOT_ACTIVE)

    def test_the_same_milestone_twice_is_one_link(self):
        code, body = self.change(self.req("msadd", [self.ms, self.ms, self.ms2, self.ms]))
        self.assertEqual((code, body["milestones"]), (200, [self.ms, self.ms2]))
        self.assertEqual(len(sm.use_case_milestone_history(self.s.con, self.uc)), 2)

    def test_a_link_to_a_milestone_archived_since_can_still_be_taken_off(self):
        self.change(self.req("msadd", [self.ms2]))
        with self.s.step("dashboard", USER) as st:
            st.archive("milestones", self.ms2)
        code, body = self.change(self.req("msremove", [self.ms2]))
        self.assertEqual((code, body["milestones"], self.live()), (200, [self.ms2], []), body)

    def test_the_reply_lists_every_live_link_and_a_remove_of_one_not_linked_has_no_undo(self):
        self.change(self.req("msadd", [self.ms]))
        code, body = self.change(self.req("msadd", [self.ms2]))
        self.assertEqual((body["milestones"], body["linked"]), ([self.ms2], sorted([self.ms, self.ms2])))
        code, body = self.change(self.req("msremove", [self.ms2, self.ms2]))
        self.assertEqual((body["milestones"], body["linked"], body["undoable"]), ([self.ms2], [self.ms], True))
        code, body = self.change(self.req("msremove", [self.ms2]))
        self.assertEqual((code, body["milestones"], body["apply_id"], body["undoable"]), (200, [], None, False))

    def test_an_undo_is_for_the_project_and_the_route_that_made_the_step(self):
        code, made = self.change(self.req("msadd", [self.ms]))
        code, body = self.undo({"project": "DEF", "apply_id": made["apply_id"]})
        self.assertEqual((code, body["ok"]), (400, False), "another project's page cannot undo it")
        self.assertEqual(self.live(), [self.ms])
        with self.s.step("excel", USER) as st:               # a step written by another route
            sm.link_use_case_milestone(st, self.uc, self.ms2)
        step = max(r[0] for r in self.s.con.execute("SELECT DISTINCT apply_id FROM change_log"))
        code, body = self.undo({"project": "ABC", "apply_id": step})
        self.assertEqual((code, body["ok"]), (400, False), "a step the change route did not make is not undone from here")
        self.assertIn(self.ms2, self.live())
        code, body = self.undo({"project": "ABC", "apply_id": made["apply_id"]})
        self.assertEqual(code, 200, body)
        self.assertEqual(self.live(), [self.ms2])


class Store(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s, self.uc, self.ms = self.demo.store, self.demo.use_case, self.demo.milestone
        with self.s.step("dashboard", USER) as st:
            self.ms2 = st.create("milestones", {"project": "ABC", "name": "Go live", "baseline_date": "2030-06-01", "source": "demo"})

    def link(self, ms=None):
        with self.s.step("dashboard", USER) as st:
            return sm.link_use_case_milestone(st, self.uc, ms or self.ms)

    def test_a_milestone_lists_only_the_use_cases_still_linked(self):
        self.link()
        self.link(self.ms2)
        with self.s.step("dashboard", USER) as st:
            sm.unlink_use_case_milestone(st, self.uc, self.ms)
        self.assertEqual(sm.milestone_use_case_ids(self.s.con, self.ms), [])
        self.assertEqual(sm.milestone_use_case_ids(self.s.con, self.ms2), [self.uc])

    def test_an_archived_use_case_is_refused_and_ending_a_link_of_one_is_not(self):
        self.link()
        with self.s.step("dashboard", USER) as st:
            st.archive("use_cases", self.uc)
        with self.assertRaises(Invalid) as e:
            self.link(self.ms2)
        self.assertEqual(str(e.exception), sm.UC_MS_ARCHIVED)
        with self.s.step("dashboard", USER) as st:                # an update only ends a link: the pair is not judged again
            self.assertTrue(sm.unlink_use_case_milestone(st, self.uc, self.ms))
        self.assertEqual(sm.use_case_milestone_ids(self.s.con, self.uc), [])

    @unittest.expectedFailure
    def test_a_link_number_is_never_one_a_logged_link_had(self):
        """REPORTED, NOT FIXED (store.py is guarded): the comment on the numbering says "never one a logged link had", but the log's item_id is
        'USE_CASE|MILESTONE|NUMBER', so CAST(item_id AS INTEGER) is 0 and only the table's own highest number is counted. An Undo of an add
        deletes the row, so the next add takes the same number and the log then holds two different links under one key. Remove the
        expectedFailure when store.py reads the number off the end of the key."""
        change = changes.make_change(self.s.path, [], USER)
        undo = changes.make_undo(self.s.path, [], USER)
        req = {"project": "ABC", "kind": "use_cases", "op": "msadd", "id": self.uc, "ids": [self.ms]}
        code, made = change(req)
        self.assertEqual(code, 200)
        self.assertEqual(undo({"project": "ABC", "apply_id": made["apply_id"]})[0], 200)
        change(req)
        self.assertEqual([r["link_id"] for r in sm.use_case_milestone_history(self.s.con, self.uc)], [2])


if __name__ == "__main__":
    unittest.main()
