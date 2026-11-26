"""Row 1252: History names an added page and its fields, not "Other" and a bare code."""
import unittest
from _demo import USER, DemoStore
from clark import changes, history


class AddedPageHistory(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store
        self.change = changes.make_change(self.s.path, [], USER)

    def rows(self):
        return history.rows_for_project(self.s.con, "ABC")

    def test_created_changed_and_removed_pages_are_named(self):
        st, b = self.change({"project": "ABC", "kind": "added_pages", "op": "new", "values": {"name": "Notes", "starter": "blank"}})
        ref = b["ref"]
        self.change({"project": "ABC", "kind": "added_pages", "op": "update", "id": ref, "changes": {"name": "Renamed", "hidden": 1}})
        self.change({"project": "ABC", "kind": "added_pages", "op": "delete", "id": ref})
        mine = [r for r in self.rows() if r["table"] == "added_pages"]
        self.assertEqual([(r["kind"], r["field"]) for r in mine],
                         [("Removed", "Page"), ("Changed", "Hidden"), ("Changed", "Page name"), ("Created", "Page")])
        self.assertTrue(all(r["title"] == "Renamed" for r in mine))

    def test_field_names(self):
        self.assertEqual(history.field_name("added_pages", "client"), "Shown to the client")
        self.assertEqual(history.field_name("added_pages", "sort_order"), "Place")
        self.assertEqual(history.THING["added_pages"], "Page")


if __name__ == "__main__":
    unittest.main()
