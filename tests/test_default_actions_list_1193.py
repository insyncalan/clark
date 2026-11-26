"""Row 1193-9: a new project's Open actions is a Work items list with its own saved filter (open actions, soonest due first).
Only new projects get it: a project that already exists keeps its built-in section.

Run: python3 dev/run_tests.py test_default_actions_list_1193
"""
import json
import unittest

from _demo import DemoStore
from clark import changes, default_sections, order, store as store_module
from clark.section_kinds import workitems as wi

TODAY = "2030-01-15"
ROWS = [
    {"id": "A-1", "kind": "action", "title": "a", "status": "Open", "due": "2030-01-10"},
    {"id": "A-2", "kind": "action", "title": "b", "status": "Closed", "due": "2030-01-01"},
    {"id": "R-1", "kind": "risk", "title": "c", "status": "Open", "due": "2030-03-01"},
    {"id": "D-1", "kind": "decision", "title": "f", "status": "Pending", "due": "2030-03-04"},
]


class DefaultActionsList(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.s = self.demo.store
        self.addCleanup(self.demo.close)

    def rows(self):
        return [r for r in order.in_order(self.s.read("report_sections", "ABC")) if r["title"] == "Open actions"]

    def test_the_default_entry_is_one_work_items_list_with_a_body(self):
        entry = [e for e in default_sections.DEFAULT_SECTIONS if e["title"] == "Open actions"]
        self.assertEqual([(e["type"], e["body"]) for e in entry], [("workitems", default_sections.OPEN_ACTIONS_BODY)])

    def test_the_other_defaults_keep_their_types(self):
        types = [e["type"] for e in default_sections.DEFAULT_SECTIONS]
        self.assertEqual(types, ["reportheadline", "glancetemplate", "text", "text", "text", "milestones", "usecases", "workitems", "workitems", "workitems", "doclinks"])

    def test_the_body_is_canonical_and_lists_open_actions_only(self):
        value = wi.check(json.loads(default_sections.OPEN_ACTIONS_BODY), store_module.BODY_RULES)
        self.assertEqual(json.dumps(value, separators=(",", ":"), sort_keys=True), default_sections.OPEN_ACTIONS_BODY)
        self.assertEqual((value["kinds"], value["mode"], value["sort"], value["max"]), (["action"], "open", "due", 50))
        self.assertEqual(value["columns"], ["type", "id", "owner", "due", "priority"])
        self.assertEqual(wi.matching(value, ROWS, TODAY), ["A-1"])

    def test_a_new_project_stores_the_list_in_the_same_place_with_its_filter(self):
        rows = self.rows()
        self.assertEqual([(r["type"], r["id"], r["sort_order"], r["hidden"], r["body"]) for r in rows],
                         [("workitems", "ABC-S-009", order.GAP * 9, 0, default_sections.OPEN_ACTIONS_BODY)])

    def test_the_built_in_actions_section_stays_re_addable_under_its_title(self):
        self.assertEqual(changes.BUILT_IN_TITLES["actions"], "Open actions")
        self.assertNotIn("workitems", changes.BUILT_IN_TITLES)
        self.assertIn("actions", changes.BUILT_IN_TYPES)
        self.assertIn("workitems", changes.NEW_SECTION_TYPES)


if __name__ == "__main__":
    unittest.main()
