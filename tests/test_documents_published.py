"""#74 Supporting documents in the published file (src/clark/publish.py; guarded): only live, visible documents with a link that
passes the one link rule reach the file. Rows are planted past the editor (straight into the database) and a real file is built,
then searched for every planted title, kind, date and address in each spelling it could take.

Run: python3 dev/run_tests.py test_documents_published
"""
import json
import re
import sqlite3
import unittest

from _demo import USER, DemoStore
from _publish_fixture import spellings
from clark import changes, publish

ADDRESS = re.compile(r"(?:https?://|mailto:)[^\"'\\\s<>)]+", re.I)
REFUSED = ("javascript:alert('ZQ-JS')", "JaVaScRiPt:alert(1)", "java\tscript:alert(1)", "data:text/html,ZQ-DATA",
           "vbscript:ZQ-VB", "file:///ZQ-FILE", "blob:https://zq-blob.example.com/x", "ftp://zq-ftp.example.com/x",
           "//zq-relative.example.com/x", "zq-bare.example.com", "https://zq:" + "pw@zq-cred.example.com/")


class Published(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store
        self.change = changes.make_change(self.s.path, [], USER)
        self.n = 0

    def plant(self, title, url, kind="Report", date="2030-01-02", archived=0, project="ABC"):
        """A document written past the writer: none of the store's rules are asked."""
        self.n += 1
        ref = f"{project}-L-{self.n:03d}"
        con = sqlite3.connect(str(self.s.path))
        con.execute("INSERT INTO documents (project, id, title, kind, url, date, sort_order, archived) VALUES (?,?,?,?,?,?,?,?)",
                    (project, ref, title, kind, url, date, self.n * 1024, archived))
        con.commit()
        con.close()
        return ref

    def hide(self, ref):
        con = sqlite3.connect(str(self.s.path))
        con.execute("INSERT INTO report_hidden (project, item_id) VALUES ('ABC', ?)", (ref,))
        con.commit()
        con.close()

    def hide_section(self):
        con = sqlite3.connect(str(self.s.path))
        con.execute("UPDATE report_sections SET hidden = 1 WHERE project = 'ABC' AND type = 'docs'")
        con.commit()
        con.close()

    def built(self):
        return publish.build(self.s, "ABC", now="2030-01-15")

    def text(self):
        return self.built()["body"].decode("utf-8")

    def absent(self, text, *markers):
        for marker in markers:
            for form in spellings(marker):
                self.assertNotIn(form, text, marker)

    def addresses(self, text):
        return set(ADDRESS.findall(text))


class Absent(Published):
    def test_hidden_archived_and_refused_documents_never_reach_the_file(self):
        first = self.text()
        baseline, api_before = self.addresses(first), first.count("/api/")
        shown = self.plant("ZQ-SHOWN-TITLE", "https://shown.example.com/minutes", kind="Minutes", date="2030-01-03")
        mail = self.plant("ZQ-MAIL-TITLE", "mailto:pmo@example.com", kind="Plan", date=None)
        hidden = self.plant("ZQ-HIDDEN-TITLE", "https://zq-hidden.example.com/secret", kind="Slides", date="2031-07-07")
        self.hide(hidden)
        self.plant("ZQ-ARCHIVED-TITLE", "https://zq-archived.example.com/old", kind="Other", date="2031-08-08", archived=1)
        for n, url in enumerate(REFUSED):
            self.plant(f"ZQ-REFUSED-{n}", url, date=f"2032-01-{n + 10:02d}")
        text = self.text()
        self.absent(text, "ZQ-HIDDEN-TITLE", "zq-hidden.example.com", "2031-07-07", "07-07-2031",
                    "ZQ-ARCHIVED-TITLE", "zq-archived.example.com", "2031-08-08", "08-08-2031", hidden)
        for n, url in enumerate(REFUSED):
            self.absent(text, f"ZQ-REFUSED-{n}", f"2032-01-{n + 10:02d}", url)
        for word in ("ZQ-JS", "ZQ-DATA", "ZQ-VB", "ZQ-FILE", "zq-blob", "zq-ftp", "zq-relative", "zq-bare", "zq-cred"):
            self.assertNotIn(word.lower(), text.lower())
        published = self.built()["published"]["data"]["documents"]
        self.assertEqual(published, [{"title": "ZQ-SHOWN-TITLE", "kind": "Minutes", "url": "https://shown.example.com/minutes", "date": "2030-01-03"},
                                     {"title": "ZQ-MAIL-TITLE", "kind": "Plan", "url": "mailto:pmo@example.com", "date": None}])
        self.assertEqual(self.addresses(text) - baseline, {"https://shown.example.com/minutes", "mailto:pmo@example.com"},
                         "no outside address but the visible documents' links")
        self.assertNotIn(shown, text, "a document's id is not carried")
        self.assertNotIn(mail, text)
        self.assertEqual(publish.outside_addresses(text), [], "nothing in the markup reaches outside")
        self.assertEqual(text.count("/api/"), api_before, "the documents add no /api/ text (the view page's own count is unchanged)")
        self.assertNotIn("data-doc-", text)

    def test_a_hidden_documents_section_carries_no_document(self):
        self.plant("ZQ-IN-HIDDEN-SECTION", "https://zq-section.example.com/x", date="2033-03-03")
        self.hide_section()
        text = self.text()
        self.absent(text, "ZQ-IN-HIDDEN-SECTION", "zq-section.example.com", "2033-03-03")
        self.assertEqual(self.built()["published"]["data"]["documents"], [])
        self.assertNotIn("docs", [s["type"] for s in self.built()["published"]["sections"]])

    def test_a_section_with_no_visible_document_is_left_out(self):
        self.assertNotIn("docs", [s["type"] for s in self.built()["published"]["sections"]])
        self.plant("Steering minutes", "https://example.com/m")
        self.assertIn("docs", [s["type"] for s in self.built()["published"]["sections"]])

    def test_a_planted_title_that_names_another_site_bad_kind_and_bad_date_are_not_published_as_given(self):
        self.plant("ZQ-ELSEWHERE portal.zq-elsewhere.example.net", "https://example.com/x")
        self.plant("Fine", "https://example.com/y", kind="<script>ZQ-KIND</script>", date="ZQ-DATE")
        self.plant("Hidden‮characters", "https://example.com/z", date="2030-02-31")
        text = self.text()
        self.absent(text, "ZQ-ELSEWHERE", "zq-elsewhere", "ZQ-KIND", "ZQ-DATE", "‮", "2030-02-31")
        got = self.built()["published"]["data"]["documents"]
        self.assertEqual(got, [{"title": "Fine", "kind": "", "url": "https://example.com/y", "date": None},
                               {"title": "Hiddencharacters", "kind": "Report", "url": "https://example.com/z", "date": None}])

    def test_markup_in_a_title_stays_text_and_a_quote_in_a_link_stays_inside_the_data(self):
        self.plant("<b>ZQ-BOLD</b>", "https://example.com/a'b`c")
        text = self.text()
        self.assertNotIn("<b>ZQ-BOLD</b>", text)
        block = re.search(r'<script type="application/json" id="clark-data">([^<]*)</script>', text).group(1)
        docs = json.loads(block)["data"]["documents"]
        self.assertEqual(docs[0]["title"], "<b>ZQ-BOLD</b>")
        self.assertEqual(docs[0]["url"], "https://example.com/a'b`c")

    def test_a_document_added_and_hidden_through_the_route_is_absent(self):
        status, body = self.change({"project": "ABC", "kind": "documents", "op": "new", "place": "report",
                                    "values": {"title": "ZQ-ROUTE-TITLE", "kind": "Slides", "url": "https://zq-route.example.com/deck", "date": "2034-04-04"}})
        self.assertEqual(status, 200, body)
        self.assertIn("ZQ-ROUTE-TITLE", self.text())
        status, _ = self.change({"project": "ABC", "kind": "report_hidden", "op": "new", "id": body["ref"], "place": "eye"})
        self.assertEqual(status, 200)
        self.absent(self.text(), "ZQ-ROUTE-TITLE", "zq-route.example.com", "2034-04-04")


if __name__ == "__main__":
    unittest.main()
