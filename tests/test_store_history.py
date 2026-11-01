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


class HistoryManyIds(unittest.TestCase):
    """#252: history_many finds an item's rows by the ID alone, not by a project code cut off at the first hyphen."""

    def test_ids_without_a_hyphen_and_ids_that_are_prefixes_of_each_other(self):
        from clark import history
        demo = DemoStore()
        try:
            s = demo.store
            a, b = demo.action(), demo.action(description="Second")
            demo.update("actions", a, {"owner": "Sam Example"})
            with s.step("dashboard", USER) as st:
                st.update("actions", b, {"labels": "Sensitive"})
                st.create("links", {"from_item": a, "to_item": b, "source": "demo"})
            # a store's IDs always have a hyphen today, so rename the log's IDs by hand: the item row, its label row ("id|label")
            # and its link row ("from|to|kind") follow. "AB" is a prefix of "ABC" and of "ABC-7" (which has no rows); the first two have no hyphen to cut at.
            for old, new in ((a, "AB"), (b, "ABC")):
                s.con.execute("UPDATE change_log SET item_id = replace(item_id, ?, ?)", (old, new))
            s.con.commit()
            ids = ["AB", "ABC", "ABC-7"]
            many = history.history_many(s.con, ids)
            for i in ids:
                with self.subTest(item=i):
                    self.assertEqual(many[i], history.history(s.con, i))
            self.assertTrue(len(many["AB"]) >= 2 and len(many["ABC"]) >= 2, "the hyphenless IDs got no history")
            self.assertIn("links", {e["table"] for e in many["AB"]})
            self.assertIn("links", {e["table"] for e in many["ABC"]})
        finally:
            demo.close()

    def test_a_thousand_ids_without_a_hyphen_do_not_break_the_query(self):
        """#252 (Hawkeye): each bare ID used to add three OR terms and three parameters; about 400 hit SQLite's limits."""
        from clark import history
        demo = DemoStore()
        try:
            s = demo.store
            a, b = demo.action(), demo.action(description="Second")
            demo.update("actions", a, {"owner": "Sam Example"})
            with s.step("dashboard", USER) as st:
                st.update("actions", b, {"labels": "Sensitive"})
                st.create("links", {"from_item": a, "to_item": b, "source": "demo"})
            for old, new in ((a, "AB"), (b, "ABC")):
                s.con.execute("UPDATE change_log SET item_id = replace(item_id, ?, ?)", (old, new))
            s.con.commit()
            # AB and ABC sit in different chunks, so the link row "AB|ABC|.." is matched by both and must be read once
            ids = ["AB", "ABC-7"] + ["NOHYPHEN%d" % n for n in range(1000)] + ["ABD", "AB", "ABC"]
            many = history.history_many(s.con, ids)
            self.assertEqual(set(many), set(ids))
            for i in ["AB", "ABC", "ABC-7", "ABD", "NOHYPHEN0", "NOHYPHEN999"]:
                with self.subTest(item=i):
                    self.assertEqual(many[i], history.history(s.con, i))
            self.assertTrue(len(many["AB"]) >= 2 and len(many["ABC"]) >= 2, "the hyphenless IDs got no history")
        finally:
            demo.close()


if __name__ == "__main__":
    unittest.main()
