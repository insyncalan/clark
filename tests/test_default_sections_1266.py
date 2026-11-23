"""Row 1266 acceptance points AP4, AP7 and AP11 (published page): the new default sections as a new project gets them.

AP4: Header has no hint entry (the editor's starting text shows), This week and Next week keep theirs.
AP7: a project with rows in the documents table still shows them in its report (the Documents section, type doclinks).
AP11 (published page): the page built for a new project carries the new section titles, in order. AP11 (Word) and AP11 (Excel Cover): the file of a new project names the Header section, not Current state.
Fictional data only (tests/_demo.py). Run: python3 dev/run_tests.py test_default_sections_1266"""
import unittest

from _demo import USER, DemoStore
from _paths import SRC  # noqa: F401  (puts src/ on the path)
from clark import default_sections, docx_build, docx_read, excel_cover, publish


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


    def words(self, title, text):
        sec = next(s for s in self.store.data_for("ABC")["report_sections"] if s["title"] == title)
        with self.store.step("dashboard", USER) as st:
            st.update("report_sections", sec["id"], {"body": text})

    def test_ap11_word_file_of_a_new_project_names_the_header_section_and_not_current_state(self):
        self.words("Header", "<p>Scanning is two thirds done.</p>")
        built = publish.build(self.store, "ABC", now="2030-01-15")
        heads = [b["text"] for b in docx_read.read(docx_build.build(built["published"]), "r.docx").blocks if b["kind"] == "heading"]
        self.assertIn("Header", heads)
        for gone in ("Current state", "Use case summary", "Summary"):
            self.assertNotIn(gone, heads)

    def test_ap11_excel_cover_of_a_new_project_names_the_header_section_and_not_current_state(self):
        self.words("Header", "<p>Scanning is two thirds done.</p>")
        data = self.store.data_for("ABC")
        got = excel_cover.lines(project=data["project"], sections=data["report_sections"], tiles=[], exported="01-06-2030 20:30 (UTC+04:00)",
                                by="Sam Example", owner="Kim Example", email="kim.example@example.com", internal="INTERNAL")
        texts = [x.get("text", "") for x in got]
        self.assertIn("Header", texts)
        for gone in ("Current state", "Use case summary", "Summary"):
            self.assertNotIn(gone, texts)


if __name__ == "__main__":
    unittest.main()
