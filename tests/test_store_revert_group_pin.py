"""Row 1385: what an Undo does for one item's rows from one step (store.revert_group), pinned branch by branch before the
function is split. Each test names the branch it holds; the words and the rows are those the function gave before the split."""
import unittest

from _demo import USER, DemoStore


class RevertGroupPin(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.s = self.demo.store

    def tearDown(self):
        self.demo.close()

    def test_a_creation_changed_since_is_left_and_names_the_later_step(self):
        a = self.demo.action()
        made = self.demo.last_step()
        later = self.demo.update("actions", a, {"priority": "High"})
        out = self.s.undo(made, USER)
        self.assertIsNotNone(self.s.read("actions", ref=a))
        self.assertEqual(out["reversed"], [])
        self.assertEqual([(x["field"], x["why"], x["by_step"]) for x in out["skipped"]],
                         [(None, "has changed since: left as it is", later)])

    def test_a_row_made_and_deleted_in_one_step_has_nothing_to_remove(self):
        with self.s.step("dashboard", USER) as st:
            a = st.create("actions", {"project": "ABC", "description": "d", "raised": "2026-10-01", "source": "demo"})
            st.delete("actions", a)
        out = self.s.undo(self.demo.last_step(), USER)
        self.assertIsNone(self.s.read("actions", ref=a))
        self.assertEqual(out["skipped"], [])
        self.assertTrue(out["reversed"])
        self.assertTrue(all(d["change"] == "removed" for d in out["reversed"]))

    def test_a_use_case_given_a_milestone_link_since_is_left_as_changed(self):
        from clark import store as sm
        with self.s.step("dashboard", USER) as st:
            u = st.create("use_cases", {"project": "ABC", "title": "New", "status": "On track", "source": "demo"})
        made = self.demo.last_step()
        with self.s.step("dashboard", USER) as st:
            sm.link_use_case_milestone(st, u, self.demo.milestone)
        out = self.s.undo(made, USER)
        self.assertIsNotNone(self.s.read("use_cases", ref=u))
        self.assertEqual([(x["why"], x["by_step"]) for x in out["skipped"]],
                         [("has changed since: left as it is", self.demo.last_step())])

    def test_a_deleted_row_is_put_back_with_the_first_old_value_of_a_field_changed_before_the_delete(self):
        a = self.demo.action(priority="Low")
        with self.s.step("dashboard", USER) as st:
            st.update("actions", a, {"priority": "High"})
            st.update("actions", a, {"priority": "Medium"})
            st.delete("actions", a)
        self.assertIsNone(self.s.read("actions", ref=a))
        out = self.s.undo(self.demo.last_step(), USER)
        self.assertEqual(self.s.read("actions", ref=a)["priority"], "Low")
        self.assertEqual(out["skipped"], [])
        self.assertTrue(any(d["change"] == "put back" for d in out["reversed"]))

    def test_a_taken_off_link_made_again_by_hand_is_left(self):
        a = self.demo.action()
        key = f"{a}|{self.demo.milestone}|blocks"
        with self.s.step("dashboard", USER) as st:
            st.create("links", {"from_item": a, "to_item": self.demo.milestone, "source": "demo"})
        with self.s.step("dashboard", USER) as st:
            st.cancel("links", key)
        taken = self.demo.last_step()
        with self.s.step("dashboard", USER) as st:
            st.create("links", {"from_item": a, "to_item": self.demo.milestone, "source": "demo"})
        out = self.s.undo(taken, USER)
        self.assertEqual(len(self.s.read("links")), 1)
        self.assertEqual(out["reversed"], [])
        self.assertEqual([x["why"] for x in out["skipped"]], ["is back already: left as it is"])

    def test_a_taken_off_link_whose_other_end_is_deleted_stays_off_and_says_nothing(self):
        b = self.demo.action()
        with self.s.step("dashboard", USER) as st:
            st.create("links", {"from_item": b, "to_item": self.demo.milestone, "source": "demo"})
        with self.s.step("dashboard", USER) as st:
            st.cancel("links", f"{b}|{self.demo.milestone}|blocks")
        taken = self.demo.last_step()
        with self.s.step("dashboard", USER) as st:
            st.delete("actions", b)
        out = self.s.undo(taken, USER)
        self.assertEqual((out["reversed"], out["skipped"]), ([], []))
        self.assertEqual(self.s.read("links"), [])

    def test_a_creation_that_a_kept_action_names_is_left_and_says_what_refers_to_it(self):
        with self.s.step("dashboard", USER) as st:
            u = st.create("use_cases", {"project": "ABC", "title": "New", "status": "On track", "source": "demo"})
            a = st.create("actions", {"project": "ABC", "description": "d", "raised": "2026-10-01", "source": "demo", "use_case": u})
        made = self.demo.last_step()
        self.demo.update("actions", a, {"priority": "High"})
        out = self.s.undo(made, USER)
        self.assertIsNotNone(self.s.read("use_cases", ref=u))
        self.assertIn(f"something refers to it now (an action {a}): left as it is", [x["why"] for x in out["skipped"]])

    def test_a_use_case_made_linked_and_unlinked_in_one_step_is_removed_with_its_kept_link_row(self):
        from clark import store as sm
        with self.s.step("dashboard", USER) as st:
            u = st.create("use_cases", {"project": "ABC", "title": "New", "status": "On track", "source": "demo"})
            sm.link_use_case_milestone(st, u, self.demo.milestone)
            sm.unlink_use_case_milestone(st, u, self.demo.milestone)
        out = self.s.undo(self.demo.last_step(), USER)
        self.assertIsNone(self.s.read("use_cases", ref=u))
        self.assertEqual(out["skipped"], [])

    def test_a_deleted_item_comes_back_with_the_link_a_neighbour_delete_took_while_its_other_end_was_gone(self):
        a, b = self.demo.action(), self.demo.action()
        with self.s.step("dashboard", USER) as st:
            st.create("links", {"from_item": a, "to_item": b, "source": "demo"})
        with self.s.step("dashboard", USER) as st:
            st.delete("actions", a)
        first = self.demo.last_step()
        with self.s.step("dashboard", USER) as st:
            st.delete("actions", b)
        second = self.demo.last_step()
        self.s.undo(first, USER)
        self.assertEqual(self.s.read("links"), [])
        self.s.undo(second, USER)
        self.assertEqual([(x["from_item"], x["to_item"]) for x in self.s.read("links")], [(a, b)])

    def test_a_change_to_a_row_deleted_since_says_it_no_longer_exists(self):
        a = self.demo.action()
        step = self.demo.update("actions", a, {"priority": "High"})
        with self.s.step("dashboard", USER) as st:
            st.delete("actions", a)
        out = self.s.undo(step, USER)
        self.assertEqual(out["reversed"], [])
        self.assertTrue(out["skipped"])
        self.assertIsNone(self.s.read("actions", ref=a))

    def test_a_field_changed_since_is_left_and_the_others_go_back(self):
        a = self.demo.action()
        step = self.demo.update("actions", a, {"priority": "High", "description": "Changed"})
        later = self.demo.update("actions", a, {"priority": "Low"})
        out = self.s.undo(step, USER)
        row = self.s.read("actions", ref=a)
        self.assertEqual((row["priority"], row["description"]), ("Low", "Draft the cut-over plan"))
        self.assertEqual([(x["field"], x["why"], x["by_step"]) for x in out["skipped"]],
                         [("priority", "has changed since: left as it is", later)])
        self.assertEqual({d["field"] for d in out["reversed"]} - {"updated_at"}, {"description"})

    def test_a_project_health_reason_changed_since_stays_and_the_health_goes_back(self):
        step = self.demo.update("projects", "ABC", {"health": "At risk", "health_reason": "Vendor late"})
        self.demo.update("projects", "ABC", {"health_reason": "Vendor withdrew"})
        out = self.s.undo(step, USER)
        p = self.s.read("projects")[0]
        self.assertEqual((p["health"], p["health_reason"]), ("On track", "Vendor withdrew"))
        self.assertEqual({x["field"] for x in out["skipped"]}, {"health_reason"})
        self.assertEqual([x["why"] for x in out["skipped"]],
                         ["has changed since: left as it is", "it follows other fields: left as it is"])

    def test_an_owner_link_is_not_put_back_alone_when_its_name_changed_since(self):
        a = self.demo.action()
        step = self.demo.update("actions", a, {"owner": "Sam Example"})
        later = self.demo.update("actions", a, {"owner": "Kim Example"})
        out = self.s.undo(step, USER)
        self.assertEqual(self.s.read("actions", ref=a)["owner"], "Kim Example")
        self.assertEqual(out["skipped"][0]["field"], "owner")
        self.assertEqual(out["skipped"][0]["by_step"], later)

    def test_an_archived_row_refuses_an_older_edit(self):
        from clark.store import Invalid
        a = self.demo.action()
        step = self.demo.update("actions", a, {"priority": "High"})
        with self.s.step("dashboard", USER) as st:
            st.archive("actions", a)
        out = self.s.undo(step, USER)
        self.assertEqual(out["reversed"], [])
        self.assertTrue(any("archived" in x["why"].lower() or "changed since" in x["why"] for x in out["skipped"]))
