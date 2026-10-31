"""#126: reads that know about archive. Default reads are unchanged; filters leave archived rows out (or find only them)."""
import unittest

from _demo import USER, DemoStore
from clark import __main__ as launcher
from clark.store import Invalid


class ArchiveReads(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.s = self.demo.store
        self.a1, self.a2 = self.demo.action(), self.demo.action()
        self.s.con.execute("INSERT INTO documents (project, id, title, url, sort_order) VALUES ('ABC', 'd1', 'Plan', 'https://example.org/a', 1)")
        self.s.con.execute("INSERT INTO documents (project, id, title, url, sort_order) VALUES ('ABC', 'd2', 'Old', 'https://example.org/b', 2)")
        with self.s.step("dashboard", USER) as st:
            st.archive("actions", self.a2)
            st.archive("documents", "ABC|d2")

    def tearDown(self):
        self.demo.close()

    def ids(self, kind, **kw):
        return sorted(r["id"] for r in self.s.read(kind, "ABC", **kw))

    def test_read_modes(self):
        self.assertIn(self.a2, self.ids("actions"))                       # None: today's, every row
        self.assertIn(self.a1, self.ids("actions"))
        self.assertEqual(self.ids("actions", archived=False).count(self.a2), 0)
        self.assertIn(self.a1, self.ids("actions", archived=False))
        self.assertEqual(self.ids("actions", archived=True), [self.a2])

    def test_read_without_a_project_and_by_ref(self):
        self.assertEqual([r["id"] for r in self.s.read("actions", archived=True)], [self.a2])
        self.assertEqual(self.s.read("actions", ref=self.a2)["archived"], 1)     # by ref: whatever its flag

    def test_documents_reader_leaves_archived_out(self):
        self.assertEqual(self.ids("documents", archived=False), ["d1"])
        self.assertEqual(self.ids("documents", archived=True), ["d2"])
        self.assertEqual(self.ids("documents"), ["d1", "d2"])

    def test_a_kind_without_the_flag_and_a_bad_value_are_refused(self):
        with self.assertRaises(Invalid):
            self.s.read("links", archived=False)
        with self.assertRaises(Invalid):
            self.s.read("actions", archived="yes")

    def test_data_for_modes(self):
        live = [r["id"] for r in self.s.data_for("ABC")["actions"]]
        self.assertIn(self.a1, live)
        self.assertNotIn(self.a2, live)
        self.assertEqual([r["id"] for r in self.s.data_for("ABC", archived="only")["actions"]], [self.a2])
        both = [r["id"] for r in self.s.data_for("ABC", archived="show")["actions"]]
        self.assertTrue({self.a1, self.a2} <= set(both))
        with self.assertRaises(Invalid):
            self.s.data_for("ABC", archived="all")

    def test_data_for_leaves_out_a_link_whose_end_is_archived(self):
        live = self.demo.action()
        with self.s.step("dashboard", USER) as st:
            st.create("links", {"from_item": live, "to_item": self.a1, "source": "demo"})
        with self.s.step("dashboard", USER) as st:
            st.archive("actions", self.a1)
        pair = lambda mode: [(r["from_item"], r["to_item"]) for r in self.s.data_for("ABC", archived=mode)["links"]]   # noqa: E731
        self.assertEqual(pair("hide"), [])
        self.assertEqual(pair("show"), [(live, self.a1)])
        self.assertEqual(pair("only"), [(live, self.a1)])

    def test_data_for_an_archived_project_returns_its_children_and_the_flag(self):
        with self.s.step("dashboard", USER) as st:
            st.archive("projects", "ABC")
        data = self.s.data_for("ABC")
        self.assertEqual(data["project"]["archived"], 1)
        self.assertTrue({self.a1, self.a2} <= {r["id"] for r in data["actions"]})
        self.assertTrue(all(r["archived"] == 1 for r in data["actions"]))

    def test_only_project_ignores_an_archived_project(self):
        self.assertEqual(launcher.only_project(self.s), "ABC")
        with self.s.step("dashboard", USER) as st:
            st.archive("projects", "ABC")
        self.assertIsNone(launcher.only_project(self.s))

    def test_projects_of_archived_option(self):
        with self.s.step("dashboard", USER) as st:
            st.archive("projects", "ABC")
        projects = launcher.projects_of(self.s.path, [])
        self.assertEqual(projects(), [])
        self.assertEqual([p["code"] for p in projects(archived=True)], ["ABC"])

    def test_publish_select_still_drops_archived_rows(self):
        from clark import publish
        shown = publish.select(publish.read_inputs(self.s, "ABC"))["data"]["actions"]
        ids = [r["id"] for r in shown]
        self.assertNotIn(self.a2, ids)


if __name__ == "__main__":
    unittest.main()
