"""Row 1193-10: a new project's Decisions is a Work items list on the open decisions view (kind decision, open, soonest due first, 10 rows).
Only new projects get it: a project that already exists keeps its built-in section.

Run: python3 dev/run_tests.py test_default_decisions_list_1193
"""
import json
import unittest

from _demo import DemoStore
from clark import changes, default_sections, order, store as store_module
from clark.section_kinds import workitems as wi

TODAY = "2030-01-15"
ROWS = [
    {"id": "A-1", "kind": "action", "title": "a", "status": "Open", "due": "2030-01-10"},
    {"id": "R-1", "kind": "risk", "title": "c", "status": "Open", "due": "2030-03-01"},
    {"id": "D-1", "kind": "decision", "title": "f", "status": "Pending", "due": "2030-03-04"},
    {"id": "D-2", "kind": "decision", "title": "g", "status": "Made", "due": "2030-02-04"},
]


class DefaultDecisionsList(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.s = self.demo.store
        self.addCleanup(self.demo.close)

    def test_the_default_entry_is_one_work_items_list_with_a_body(self):
        entry = [e for e in default_sections.DEFAULT_SECTIONS if e["title"] == "Decisions"]
        self.assertEqual([(e["type"], e["body"]) for e in entry], [("workitems", default_sections.DECISIONS_LIST)])
        self.assertNotIn("decisions", [e["type"] for e in default_sections.DEFAULT_SECTIONS])

    def test_the_body_is_the_lists_start_body_with_the_kind_set_and_lists_pending_decisions_only(self):
        self.assertEqual(default_sections.DECISIONS_LIST, wi.START.replace('"kinds":[]', '"kinds":["decision"]', 1))
        value = json.loads(default_sections.DECISIONS_LIST)
        self.assertEqual(wi.check(value, store_module.BODY_RULES), value)
        self.assertEqual((value["kinds"], value["mode"]), (["decision"], "open"))
        self.assertEqual(wi.matching(value, ROWS, TODAY), ["D-1"])

    def test_a_new_project_stores_the_list_in_the_same_place(self):
        rows = [r for r in order.in_order(self.s.read("report_sections", "ABC")) if r["title"] == "Decisions"]
        self.assertEqual([(r["type"], r["id"], r["sort_order"], r["hidden"]) for r in rows], [("workitems", "ABC-S-009", order.GAP * 9, 0)])
        self.assertEqual(json.loads(rows[0]["body"]), json.loads(default_sections.DECISIONS_LIST))

    def test_the_built_in_decisions_section_stays_re_addable_under_its_title(self):
        self.assertEqual(changes.BUILT_IN_TITLES["decisions"], "Decisions")
        self.assertNotIn("workitems", changes.BUILT_IN_TITLES)
        self.assertIn("workitems", changes.NEW_SECTION_TYPES)


if __name__ == "__main__":
    unittest.main()
