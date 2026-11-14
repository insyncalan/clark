"""Row 1176 (python level): selecting a project scopes work items, milestones and project data to it, and the brand follows it.
Store.data_for(code) is what GET /api/data?project=CODE answers. Selecting A then B: each read holds only that project's rows,
B's items never appear under A, and the project's own brand (else generic, the inherited default) is what the read carries.

Run: python3 dev/run_tests.py test_project_scope_1176
"""
import unittest

from _demo import USER, DemoStore

KINDS = ("milestones", "actions", "raid", "decisions", "use_cases")


class Scope(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.store = self.demo.store
        with self.store.step("dashboard", USER) as st:
            st.create("projects", {"code": "BBB", "name": "Second Programme", "health": "On track", "brand": "generic"})
            st.create("milestones", {"project": "BBB", "name": "Second only milestone", "baseline_date": "2030-05-01", "source": "demo"})
            st.create("use_cases", {"project": "BBB", "title": "Second only use case", "status": "On track", "source": "demo"})
            st.create("actions", {"project": "BBB", "title": "Second only action", "source": "demo"})
        with self.store.step("dashboard", USER) as st:
            st.update("projects", "ABC", {"brand": "example-brand"})

    def names(self, data):
        out = []
        for k in KINDS:
            for r in data.get(k, []):
                out.append(r.get("name") or r.get("title") or "")
        return out

    def test_A_then_B_each_read_holds_only_its_own_project(self):
        a = self.store.data_for("ABC")
        b = self.store.data_for("BBB")
        self.assertEqual(a["project"]["code"], "ABC")
        self.assertEqual(b["project"]["code"], "BBB")
        for k in KINDS:
            self.assertTrue(all(r["project"] == "ABC" for r in a.get(k, [])), k + " under A are all A's")
            self.assertTrue(all(r["project"] == "BBB" for r in b.get(k, [])), k + " under B are all B's")
        self.assertIn("Pilot live", self.names(a))
        self.assertNotIn("Second only milestone", self.names(a), "B's milestone never appears under A")
        self.assertNotIn("Second only use case", self.names(a))
        self.assertNotIn("Second only action", self.names(a))
        self.assertIn("Second only milestone", self.names(b))
        self.assertNotIn("Pilot live", self.names(b), "A's milestone never appears under B")
        self.assertNotIn("Invoice matching", self.names(b))

    def test_B_items_never_appear_under_A_by_id(self):
        a_ids = {r["id"] for k in KINDS for r in self.store.data_for("ABC").get(k, [])}
        b_ids = {r["id"] for k in KINDS for r in self.store.data_for("BBB").get(k, [])}
        self.assertTrue(a_ids and b_ids)
        self.assertFalse(a_ids & b_ids, "no row is in both projects' reads")

    def test_project_data_is_the_selected_projects(self):
        self.assertEqual(self.store.data_for("ABC")["project"]["name"], "Example Programme")
        self.assertEqual(self.store.data_for("BBB")["project"]["name"], "Second Programme")

    def test_the_brand_changes_with_the_project(self):
        self.assertEqual(self.store.data_for("ABC")["project"]["brand"], "example-brand", "A's own assignment")
        self.assertEqual(self.store.data_for("BBB")["project"]["brand"], "generic", "no own assignment, no client brand: generic")
        self.assertEqual(self.store.data_for("ABC")["project"]["brand"], "example-brand", "back to A, A's brand again")

    def test_a_project_with_no_assignment_is_generic(self):
        with self.store.step("dashboard", USER) as st:
            st.create("projects", {"code": "CCC", "name": "Third Programme"})
        self.assertEqual(self.store.data_for("CCC")["project"]["brand"], "generic")

    def test_no_such_project_is_none(self):
        self.assertIsNone(self.store.data_for("NOPE"))


if __name__ == "__main__":
    unittest.main()
