"""Row 1266 acceptance points AP4, AP7 and AP11 (published page): the new default sections as a new project gets them.

AP4: Header has no hint entry (the editor's starting text shows), This week and Next week keep theirs.
AP7: a project with rows in the documents table still shows them in its report (the Documents section, type doclinks).
AP11 (published page): the page built for a new project carries the new section titles, in order. Excel and Word of a new project: not covered here.
Fictional data only (tests/_demo.py). Run: python3 dev/run_tests.py test_default_sections_1266"""
import unittest

from _demo import USER, DemoStore
from _paths import SRC  # noqa: F401  (puts src/ on the path)
from clark import default_sections, publish


class DefaultSections1266(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.store = self.demo.store

    def test_ap4_header_has_no_hint_entry_and_the_other_two_keep_theirs(self):
        self.assertNotIn("Header", default_sections.SECTION_HINTS)
        self.assertEqual(sorted(default_sections.SECTION_HINTS), ["Next week", "This week"])

    def test_ap7_a_project_with_document_rows_keeps_them_in_its_report(self):
        link = "https://example.org/plan"
        with self.store.step("dashboard", USER) as st:
            st.create("documents", {"project": "ABC", "title": "Delivery plan", "kind": "Plan", "url": link, "sort_order": 1})
        data = self.store.data_for("ABC")
        self.assertEqual([d["title"] for d in data["documents"]], ["Delivery plan"])
        self.assertEqual(data["report_sections"][-1]["type"], "doclinks")

    def test_ap11_the_published_page_of_a_new_project_carries_the_new_sections_in_order(self):
        built = publish.build(self.store, "ABC", now="2030-01-15")
        titles = [s["title"] for s in built["published"]["sections"]]
        # the empty text sections and the template sections without rows are left out of a new project's file (the empty-part rule)
        self.assertEqual(titles, ["Header", "This week", "Next week", "Milestones", "Use cases"])
        for gone in ("Current state", "Use case summary", "Supporting documents", "Summary"):
            self.assertNotIn(gone, titles)


if __name__ == "__main__":
    unittest.main()
