"""Mutation-sweep survivors of publish.select (row 1022 follow-up): two field/gate facts nothing pinned.

1. A published decision carries who made it (PUBLISH_FIELDS["decisions"] holds made_by): dropping the column from the list was
   not noticed by any test.
2. An archived workstream is not in the file, even while a published row still names it (select's workstreams filter: the
   archived gate): dropping the gate was not noticed by any test.
All rows are fictional.

Run: python3 dev/run_tests.py test_publish_mutwave
"""
import unittest

from _demo import USER, DemoStore
from clark import publish

WHO = "zz-made-by-role-1022"


class Pinned(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store

    def data(self):
        return publish.select(publish.read_inputs(self.s, "ABC", "2026-10-29"))["data"]

    def test_a_published_decision_carries_who_made_it(self):
        with self.s.step("dashboard", USER) as st:
            st.create("decisions", {"project": "ABC", "decision": "Use the shared calendar", "status": "Made", "date": "2026-10-01", "made_by": WHO,
                                    "client_visible": 1, "source": "demo"})
        got = self.data()["decisions"]
        self.assertEqual([d["made_by"] for d in got], [WHO])

    def test_an_archived_workstream_is_not_in_the_file_though_a_published_row_names_it(self):
        self.demo.action(description="Plan the build", workstream="Build", client_visible=1)
        names = [w["name"] for w in self.data()["workstreams"]]
        self.assertEqual(names, ["Build"])                      # the live workstream is there (so the test can fail)
        self.s.con.execute("UPDATE workstreams SET archived=1 WHERE name='Build'")      # the store has no archive for a workstream: set as an old row would be
        self.s.con.commit()
        self.assertEqual(self.data()["workstreams"], [])
        self.assertEqual([a["workstream"] for a in self.data()["actions"]], ["Build"])      # the row still names it


if __name__ == "__main__":
    unittest.main()
