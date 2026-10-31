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


if __name__ == "__main__":
    unittest.main()
