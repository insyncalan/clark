"""Row 1066: every section in the client's published page is one the editor dashboard lists, in the editor's order (a subset: a
section with nothing to show may be left out, but none is added). A section the editor does not have is not in the file: not even
'Needs from you' when a work item is flagged as needed from the client. Over a real store and the real build. Fictional data.

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

    def test_a_stored_needs_section_with_rows_and_a_flagged_item_is_not_in_the_file(self):
        """Item 1158: a Needs from you section already stored simply stops showing; it stays stored."""
        body = json.dumps({"v": 1, "rows": [{"what": "Typed row", "kind": "decision", "from": "", "by": "", "hidden": 0}]})
        with self.s.step("dashboard", USER) as st:
            ref = st.create("report_sections", {"project": "ABC", "type": section_bodies.NEEDS, "title": "Needs from you", "body": body,
                                                "sort_order": 1, "beside": 0, "hidden": 0})
        self.flag()
        built = publish.build(self.s, "ABC", now=NOW)
        self.assertNotIn("needs", [s["type"] for s in built["published"]["sections"]])
        self.assertNotIn(b"Typed row", built["body"])
        self.assertEqual(json.loads(self.s.read("report_sections", ref=ref)["body"]), json.loads(body), "the stored section is untouched")

    def test_a_stored_needs_section_between_two_sections_does_not_stop_them_pairing(self):
        """Item 1158 gap: the editor drops a stored Needs section before it reads rows, so A (beside) and C sit in one row. The file pairs them too."""
        def text(title, order, beside):
            return {"project": "ABC", "type": "text", "title": title, "body": f"<p>{title} words</p>", "sort_order": order, "beside": beside, "hidden": 0}
        body = json.dumps({"v": 1, "rows": [{"what": "Typed row", "kind": "decision", "from": "", "by": "", "hidden": 0}]})
        for old in self.s.read("report_sections", project="ABC"):
            with self.s.step("dashboard", USER) as st:
                st.update("report_sections", old["id"], {"hidden": 1})       # rows are never deleted; hidden ones sit after the three below
        with self.s.step("dashboard", USER) as st:
            st.create("report_sections", text("Alpha", -3, 1))
            st.create("report_sections", {"project": "ABC", "type": section_bodies.NEEDS, "title": "Needs from you", "body": body,
                                          "sort_order": -2, "beside": 0, "hidden": 0})
            st.create("report_sections", text("Gamma", -1, 0))
        got = {s["title"]: s["beside"] for s in publish.build(self.s, "ABC", now=NOW)["published"]["sections"]}
        self.assertEqual(got, {"Alpha": 1, "Gamma": 0}, "the editor's rows: Alpha beside Gamma")


if __name__ == "__main__":
    unittest.main()
