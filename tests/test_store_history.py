"""#31: one row's history reads back newest first, with undo links."""
import unittest

from _demo import USER, DemoStore


class History(unittest.TestCase):
    def test_five_steps_newest_first_with_undo_links(self):
        demo = DemoStore()
        try:
            s = demo.store
            a = demo.action()
            demo.update("actions", a, {"owner": "Sam Example"})
            demo.update("actions", a, {"priority": "High"})
            third = demo.update("actions", a, {"due_date": "2030-01-31"})
            undo = s.undo(third, USER)["step_id"]
            steps = [e["step"] for e in s.history(a)]
            self.assertEqual(steps, sorted(steps, reverse=True))
            self.assertEqual(len(set(steps)), 5)
            newest = s.history(a)[0]
            self.assertEqual((newest["step"], newest["field"], newest["is_undo"], newest["by_user"]),
                             (undo, "due_date", True, USER))
            undone = next(e for e in s.history(a) if e["step"] == third and e["field"] == "due_date")
            self.assertEqual(newest["undoes"], undone["event_id"])
            self.assertEqual(undone["undone_by"], newest["event_id"])
            self.assertFalse(undone["in_force"])
            self.assertNotIn("updated_at", {e["field"] for e in s.history(a)})
        finally:
            demo.close()

    def test_a_label_and_a_link_show_on_the_item(self):
        demo = DemoStore()
        try:
            a = demo.action()
            with demo.store.step("dashboard", USER) as st:
                st.update("actions", a, {"labels": "Sensitive"})
                st.create("links", {"from_item": a, "to_item": demo.milestone, "source": "demo"})
            tables = {e["table"] for e in demo.store.history(a)}
            self.assertTrue({"actions", "item_labels", "links"} <= tables)
            self.assertIn("links", {e["table"] for e in demo.store.history(demo.milestone)})
        finally:
            demo.close()


class HistoryMany(unittest.TestCase):
    """The batch read (history_many) gives exactly what history() gives, for every row (#158: one pass, not one per item)."""

    def test_the_batch_equals_the_single_item_history_for_every_row(self):
        from clark import history
        demo = DemoStore()
        try:
            s = demo.store
            a1, a2, a3 = demo.action(), demo.action(description="Second"), demo.action(description="Third")
            demo.update("actions", a1, {"owner": "Sam Example"})
            demo.update("actions", a1, {"priority": "High"})
            third = demo.update("actions", a1, {"due_date": "2030-01-31"})
            s.undo(third, USER)                                           # an undone change, and the undo itself
            demo.update("actions", a2, {"status": "Delayed"})
            with s.step("assistant", USER, actor="clark", src_ref="mail 1") as st:       # a change ask clark made
                st.update("actions", a3, {"owner": "Alex Example"})
            with s.step("dashboard", USER) as st:
                r = st.create("raid", {"project": "ABC", "type": "Risk", "description": "A risk", "raised": "2026-10-01",
                                       "source": "demo"})
                d = st.create("decisions", {"project": "ABC", "decision": "A choice", "status": "Pending", "source": "demo"})
                st.update("actions", a2, {"labels": "Sensitive"})
                st.create("links", {"from_item": a1, "to_item": a2, "source": "demo"})   # a1 at the front, a2 at the end
                st.create("links", {"from_item": a3, "to_item": a1, "source": "demo"})   # a1 at the end
                st.create("links", {"from_item": r, "to_item": demo.milestone, "source": "demo"})
            later = demo.update("raid", r, {"description": "A sharper risk"})
            s.undo(later, USER)
            demo.update("decisions", d, {"decision": "A better choice"})
            ids = [a1, a2, a3, r, d, demo.milestone, "ABC-A-999"]
            many = history.history_many(s.con, ids)
            self.assertEqual(set(many), set(ids))
            for i in ids:
                with self.subTest(item=i):
                    self.assertEqual(many[i], history.history(s.con, i))
            self.assertEqual(many["ABC-A-999"], [])
            self.assertTrue(any(e["table"] == "links" for e in many[a2]))
            self.assertTrue(any(e["table"] == "links" for e in many[a1]))
            self.assertEqual(history.history_many(s.con, []), {})
        finally:
            demo.close()

    def test_an_id_without_a_hyphen_is_found(self):
        """A project's code has no hyphen: the batch read still finds its rows, as history() does (#252)."""
        from clark import history
        demo = DemoStore()
        try:
            demo.update("projects", "ABC", {"health": "At risk"})
            one = history.history(demo.store.con, "ABC")
            self.assertTrue(one)
            self.assertEqual(history.history_many(demo.store.con, ["ABC"]), {"ABC": one})
        finally:
            demo.close()


if __name__ == "__main__":
    unittest.main()
