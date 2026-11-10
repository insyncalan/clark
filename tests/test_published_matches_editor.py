"""Row 1066: the client's published page lists the same sections as the editor dashboard (read only). A section the editor does not
have is not in the file: not even 'Needs from you' when a work item is flagged as needed from the client. Over a real store and the
real build. Fictional data.

Run: python3 dev/run_tests.py test_published_matches_editor
"""
import json
import unittest

import _paths  # noqa: F401
from _demo import USER, DemoStore
from clark import publish, section_bodies

NOW = "2030-01-15"


class Matches(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store

    def editor_sections(self):
        """What the editor dashboard lists for the project: the stored sections that are not hidden, in order."""
        rows = self.s.read("report_sections", project="ABC")
        return [(r["type"], r["title"]) for r in sorted(rows, key=lambda r: r["sort_order"]) if not r["hidden"]]

    def published_sections(self):
        return [(s["type"], s["title"]) for s in publish.build(self.s, "ABC", now=NOW)["published"]["sections"]]

    def flag(self):
        self.demo.action(description="Send the access list", client_message="Send the access list", client_action=1)

    def test_a_flagged_item_does_not_add_a_needs_section_the_editor_does_not_have(self):
        self.assertNotIn("needs", [t for t, _ in self.editor_sections()])
        self.flag()
        self.assertNotIn("needs", [t for t, _ in self.published_sections()])

    def test_every_published_section_is_one_the_editor_lists_and_in_its_order(self):
        self.flag()
        editor = self.editor_sections()
        got = self.published_sections()
        self.assertEqual([x for x in got if x in editor], got, "nothing in the file that the editor does not list")
        self.assertEqual([x for x in editor if x in got], got, "the same order")

    def test_a_needs_section_the_editor_has_still_gets_the_flagged_rows(self):
        with self.s.step("dashboard", USER) as st:
            st.create("report_sections", {"project": "ABC", "type": section_bodies.NEEDS, "title": "Needs from you", "body": "",
                                          "sort_order": 1, "beside": 0, "hidden": 0})
        self.flag()
        got = [s for s in publish.build(self.s, "ABC", now=NOW)["published"]["sections"] if s["type"] == "needs"]
        self.assertEqual([r["what"] for r in got[0]["rows"]], ["Send the access list"])


if __name__ == "__main__":
    unittest.main()
