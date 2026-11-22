"""Row 1266, AP7 and AP11: the last default section is Documents (Files and links), a report that already has documents keeps them, and the
published file, the Word report and the Excel cover of a new project carry the new section titles.

Run: python3 dev/run_tests.py test_default_sections_ap_1266
Data only (no layout, so no width check). The data is the fictional store of tests/_demo.py.
"""
import sqlite3
import unittest

from _demo import USER, DemoStore
from clark import default_sections, docx_build, docx_read, excel_cover, publish

TITLES = ("Headline", "At a glance", "Header", "This week", "Next week", "Milestones", "Use cases", "Risks and issues", "Open actions", "Decisions", "Documents")


class Base(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store

    def say(self, title, body):
        row = next(r for r in self.s.data_for("ABC")["report_sections"] if r["title"] == title)
        with self.s.step("dashboard", USER) as st:
            st.update("report_sections", row["id"], {"body": body})

    def plant_document(self, title="ZQ Plan"):
        con = sqlite3.connect(str(self.s.path))
        con.execute("INSERT INTO documents (project, id, title, kind, url, date, sort_order, archived) VALUES (?,?,?,?,?,?,?,?)",
                    ("ABC", "ABC-L-001", title, "Report", "https://example.com/plan", "2030-01-02", 1024, 0))
        con.commit()
        con.close()

    def built(self):
        return publish.build(self.s, "ABC", now="2030-01-15")["published"]

    def headings(self):
        return [b["text"] for b in docx_read.read(docx_build.build(self.built()), "r.docx").blocks if b["kind"] == "heading"]


class AP7Documents(Base):
    def test_ap7_the_last_section_is_documents_of_type_doclinks_and_a_new_project_gets_it(self):
        self.assertEqual((default_sections.DEFAULT_SECTIONS[-1]["type"], default_sections.DEFAULT_SECTIONS[-1]["title"]), ("doclinks", "Documents"))
        last = self.s.data_for("ABC")["report_sections"][-1]
        self.assertEqual((last["type"], last["title"], last["body"]), ("doclinks", "Documents", ""))

    def test_ap7_a_project_that_already_has_document_rows_still_shows_them_in_its_report(self):
        """An existing report keeps its built-in documents section (new projects only get Files and links), and its rows reach the file and the Word report."""
        self.demo.builtin_docs()
        self.plant_document()
        self.assertEqual([d["title"] for d in self.built()["data"]["documents"]], ["ZQ Plan"])
        self.assertIn("docs", [x["type"] for x in self.built()["sections"]])
        self.assertEqual(self.s.data_for("ABC")["report_sections"][-1]["title"], "Supporting documents", "its own section keeps its own name")
        self.assertEqual(self.s.data_for("ABC")["report_sections"][-1]["type"], "docs")


class AP11Exports(Base):
    def test_ap11_the_published_file_carries_the_new_titles(self):
        got = [x["title"] for x in self.built()["sections"]]
        self.assertEqual(got, ["Header", "This week", "Next week", "Milestones", "Use cases"], "the sections with something to show, by their new names")
        self.assertNotIn("Current state", got)
        self.assertNotIn("Use case summary", got)
        self.assertEqual([x["title"] for x in self.s.data_for("ABC")["report_sections"]], list(TITLES), "all eleven are in the report")

    def test_ap11_the_word_report_carries_the_new_titles(self):
        self.assertEqual(self.headings()[1:], ["Milestones", "Use cases"])
        for t in ("Header", "This week", "Next week"):
            self.say(t, "<p>Scanning is two thirds done.</p>")
        self.assertEqual(self.headings()[1:], ["Header", "This week", "Next week", "Milestones", "Use cases"])
        self.assertNotIn("Current state", self.headings())

    def test_ap11_the_excel_cover_carries_the_new_titles(self):
        def lines():
            data = self.s.data_for("ABC")
            return [x["text"] for x in excel_cover.lines(project=data["project"], sections=data["report_sections"], tiles=[], exported="01-06-2030 20:30 (UTC+04:00)",
                                                         by="Sam Example", owner="Kim Example", email="kim.example@example.com", internal="INTERNAL")]
        self.say("Header", "<p>Scanning is two thirds done.</p>")
        self.assertIn("Header", lines())
        self.assertNotIn("Current state", lines())


if __name__ == "__main__":
    unittest.main()
