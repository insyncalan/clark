"""#439: the project switcher's "N open items": launcher.projects_of gives each live project the number of its work items (actions, risks
and issues, decisions) that are open and not archived, and only a number. The archived list carries none. Fictional data.

Run: python3 dev/run_tests.py test_project_open_items
"""
import unittest

from _demo import USER, DemoStore
from clark import __main__ as launcher

CLOSED = ("Closed", "Cancelled", "Made", "Withdrawn")


class OpenItems(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store
        self.a1, self.a2 = self.demo.action(description="One"), self.demo.action(description="Two")
        with self.s.step("dashboard", USER) as st:
            st.create("raid", {"project": "ABC", "type": "Risk", "description": "Key person leaves", "raised": "2026-10-01",
                               "impact": "High", "likelihood": "Medium", "source": "demo"})
            st.create("decisions", {"project": "ABC", "decision": "Use the shared drive", "date": "2026-10-02", "status": "Made", "source": "demo"})
            st.create("decisions", {"project": "ABC", "decision": "Pick a supplier", "status": "Pending", "source": "demo"})

    def expected(self, code="ABC"):
        return sum(1 for kind in ("actions", "raid", "decisions") for r in self.s.read(kind, project=code)
                   if r["status"] not in CLOSED and not r["archived"])

    def test_each_live_project_carries_its_count_and_nothing_else(self):
        rows = launcher.projects_of(self.s.path, [])()
        self.assertTrue(rows)
        for r in rows:
            self.assertEqual(sorted(r), ["code", "name", "open"])
            self.assertIs(type(r["open"]), int)
        abc = next(r for r in rows if r["code"] == "ABC")
        self.assertEqual(abc["open"], 5 - 1, "two actions, a risk, a pending decision; the made decision is not open")
        self.assertEqual(abc["open"], self.expected())

    def test_a_closed_item_is_not_counted_and_closing_one_lowers_the_count(self):
        before = next(r for r in launcher.projects_of(self.s.path, [])() if r["code"] == "ABC")["open"]
        with self.s.step("dashboard", USER) as st:
            st.update("actions", self.a1, {"status": "Closed"})
        after = next(r for r in launcher.projects_of(self.s.path, [])() if r["code"] == "ABC")["open"]
        self.assertEqual(after, before - 1)
        self.assertEqual(after, self.expected())

    def test_the_archived_list_has_no_count(self):
        for r in launcher.projects_of(self.s.path, [])(archived=True):
            self.assertNotIn("open", r)


if __name__ == "__main__":
    unittest.main()
