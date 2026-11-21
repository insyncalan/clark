"""Row 1193-8: the default report's Risks and issues section is a Work items list on a saved filter (risks and issues, open),
not the built-in raid section. Only new projects get it: a project that already exists keeps what it has.

Run: python3 dev/run_tests.py test_default_risks_list_1193
"""
import json
import unittest

from _demo import DemoStore
from clark import default_sections, order
from clark.section_kinds import workitems
from clark.section_kinds.base import Bad


class Rules:
    @staticmethod
    def visible(_text):
        return True


class DefaultRisksList(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.s = self.demo.store
        self.addCleanup(self.demo.close)

    def risks(self):
        return [r for r in order.in_order(self.s.read("report_sections", "ABC")) if r["title"] == "Risks and issues"]

    def test_the_default_entry_is_a_work_items_list_with_a_saved_filter(self):
        entry = [e for e in default_sections.DEFAULT_SECTIONS if e["title"] == "Risks and issues"]
        self.assertEqual(len(entry), 1)
        self.assertEqual(entry[0]["type"], "workitems")
        self.assertTrue(entry[0]["body"])

    def test_the_filter_is_valid_canonical_and_lists_open_risks_and_issues_only(self):
        body = [e for e in default_sections.DEFAULT_SECTIONS if e["title"] == "Risks and issues"][0]["body"]
        checked = workitems.check(json.loads(body), Rules)
        self.assertEqual(json.dumps(checked, separators=(",", ":")), body)
        self.assertEqual((checked["kinds"], checked["mode"], checked["status"]), (["risk", "issue"], "open", []))
        self.assertGreaterEqual(checked["max"], 50)           # every open one, as the built-in section showed
        self.assertEqual((checked["sort"], checked["max"]), ("priority", 50))
        self.assertEqual(checked["columns"], ["type", "id", "owner", "due", "status", "priority"])

    def test_a_new_project_stores_the_list_in_the_same_place_with_its_filter(self):
        rows = self.risks()
        self.assertEqual([(r["type"], r["id"], r["sort_order"]) for r in rows], [("workitems", "ABC-S-007", order.GAP * 7)])
        self.assertEqual(json.loads(rows[0]["body"])["kinds"], ["risk", "issue"])
        self.assertEqual(rows[0]["hidden"], 0)

    def test_the_other_rows_are_unchanged(self):
        types = [r["type"] for r in order.in_order(self.s.read("report_sections", "ABC"))]
        self.assertEqual(types[:6] + types[7:], ["text", "glance", "usecases", "milestones", "text", "text", "workitems", "workitems", "docs"])

    def test_every_other_default_body_is_still_empty(self):
        self.assertEqual([e.get("body", "") for e in default_sections.DEFAULT_SECTIONS if e["title"] not in ("Risks and issues", "Open actions", "Decisions")], [""] * 7)

    def test_a_work_items_list_is_not_a_built_in_so_more_can_be_added_with_their_own_titles(self):
        from clark import changes
        self.assertNotIn("workitems", changes.BUILT_IN_TYPES)
        self.assertIn("workitems", changes.NEW_SECTION_TYPES)
        self.assertEqual(changes.BUILT_IN_TITLES["raid"], "Risks and issues")      # the older built-in stays re-addable under its own title

    def test_every_built_in_keeps_its_title_whatever_the_defaults_hold(self):
        from clark import changes
        self.assertEqual(changes.BUILT_IN_TITLES, {"current": "Current state", "glance": "At a glance", "usecases": "Use cases", "milestones": "Milestones",
                                                    "raid": "Risks and issues", "actions": "Open actions", "decisions": "Decisions", "docs": "Supporting documents"})


if __name__ == "__main__":
    unittest.main()
