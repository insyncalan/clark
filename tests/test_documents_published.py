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
from clark import changes, publish, publish_flow, to_client

ADDRESS = re.compile(r"(?:https?://|mailto:)[^\"'\\\s<>)]+", re.I)
AROUND = 80          # characters of the file shown either side of a marker that was found


def check_in_file(test, text, marker, present, what, ignore_case=False):
    """Fail, in short, unless `marker` is (present=True) or is not (present=False) in the published file `text`.
    The report names the marker and shows about AROUND characters either side of where it was found, or says it was not found
    and how long the file is. It never carries the whole file (about a megabyte of HTML)."""
    hay, needle = (text.lower(), marker.lower()) if ignore_case else (text, marker)
    at = hay.find(needle)
    if (at >= 0) == present:
        return
    if at >= 0:
        shown = hay[max(0, at - AROUND):at + len(needle) + AROUND]
        found = f"found at character {at} of {len(hay)}, around: ...{shown!r}..."
    else:
        found = f"not found; the file is {len(hay)} characters long"
    test.fail(f"{what}\nmarker {marker!r}: {found}")


REFUSED = ("javascript:alert('ZQ-JS')", "JaVaScRiPt:alert(1)", "java\tscript:alert(1)", "data:text/html,ZQ-DATA",
           "vbscript:ZQ-VB", "file:///ZQ-FILE", "blob:https://zq-blob.example.com/x", "ftp://zq-ftp.example.com/x",
           "//zq-relative.example.com/x", "zq-bare.example.com", "https://zq:" + "pw@zq-cred.example.com/",
           "http://10.0.0.1/x", "http://0.0.0.0/x")


class SearchHelper(unittest.TestCase):
    """check_in_file itself: a failing search says what was looked for and shows a short excerpt, never the whole file."""

    def failure(self, text, marker, present, **kw):
        with self.assertRaises(AssertionError) as caught:
            check_in_file(self, text, marker, present, "the reason", **kw)
        return str(caught.exception)

    def test_it_stays_quiet_when_the_search_comes_out_as_expected(self):
        check_in_file(self, "abc ZQ-X def", "ZQ-X", True, "x is there")
        check_in_file(self, "abc def", "ZQ-X", False, "x is not there")
        check_in_file(self, "abc zq-x def", "ZQ-X", True, "x is there in any letter case", ignore_case=True)

    def test_a_marker_that_was_found_is_reported_with_a_short_excerpt_not_the_file(self):
        text = "A" * 5000 + "ZQ-MARKER" + "B" * 5000
        said = self.failure(text, "ZQ-MARKER", False)
        self.assertIn("ZQ-MARKER", said, msg="the report names the marker")
        self.assertIn("the reason", said, msg="the report carries the reason it was given")
        self.assertIn("character 5000", said, msg="the report says where the marker was found")
        self.assertIn("A" * AROUND + "ZQ-MARKER" + "B" * AROUND, said, msg="the report shows the text around the marker")
        self.assertLess(len(said), 600, msg="the report is short; it does not carry the whole file")

    def test_a_marker_that_was_missing_is_reported_without_the_file(self):
        said = self.failure("C" * 5000, "ZQ-MARKER", True)
        self.assertIn("ZQ-MARKER", said, msg="the report names the marker")
        self.assertIn("not found", said, msg="the report says the marker was not found")
        self.assertLess(len(said), 300, msg="the report is short; it does not carry the whole file")


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

    def in_file(self, text, marker, what):
        check_in_file(self, text, marker, True, what)

    def not_in_file(self, text, marker, what, ignore_case=False):
        check_in_file(self, text, marker, False, what, ignore_case)

    def absent(self, text, *markers):
        for marker in markers:
            for form in spellings(marker):
                self.not_in_file(text, form, f"{marker!r} belongs to a document that must not be published, so no spelling of it may be in the file")

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
            self.not_in_file(text, word, f"{word!r} belongs to a refused link, so it may not be in the file in any letter case", ignore_case=True)
        published = self.built()["published"]["data"]["documents"]
        self.assertEqual(published, [{"title": "ZQ-SHOWN-TITLE", "kind": "Minutes", "url": "https://shown.example.com/minutes", "date": "2030-01-03"},
                                     {"title": "ZQ-MAIL-TITLE", "kind": "Plan", "url": "mailto:pmo@example.com", "date": None}],
                         msg="only the two visible documents are published, in order, each with its title, kind, link and date")
        self.assertEqual(self.addresses(text) - baseline, {"https://shown.example.com/minutes", "mailto:pmo@example.com"},
                         msg="no outside address but the visible documents' links")
        self.not_in_file(text, shown, "a document's id is not carried")
        self.not_in_file(text, mail, "a document's id is not carried (the one with the mail link)")
        self.assertEqual(publish.outside_addresses(text), [], msg="nothing in the markup reaches outside")
        self.assertEqual(text.count("/api/"), api_before, msg="the documents add no /api/ text (the view page's own count is unchanged)")
        self.not_in_file(text, "data-doc-", "the file carries none of the page's data-doc- editing markers")

    def test_a_hidden_documents_section_carries_no_document(self):
        self.plant("ZQ-IN-HIDDEN-SECTION", "https://zq-section.example.com/x", date="2033-03-03")
        self.hide_section()
        text = self.text()
        self.absent(text, "ZQ-IN-HIDDEN-SECTION", "zq-section.example.com", "2033-03-03")
        self.assertEqual(self.built()["published"]["data"]["documents"], [], msg="a hidden documents section publishes no document")
        self.assertNotIn("docs", [s["type"] for s in self.built()["published"]["sections"]], msg="a hidden documents section is not published")

    def test_a_section_with_no_visible_document_is_left_out(self):
        self.assertNotIn("docs", [s["type"] for s in self.built()["published"]["sections"]], msg="with no visible document the documents section is left out")
        self.plant("Steering minutes", "https://example.com/m")
        self.assertIn("docs", [s["type"] for s in self.built()["published"]["sections"]], msg="with one visible document the documents section is published")

    def test_a_planted_title_that_names_another_site_bad_kind_and_bad_date_are_not_published_as_given(self):
        self.plant("ZQ-ELSEWHERE portal.zq-elsewhere.example.net", "https://example.com/x")
        self.plant("Fine", "https://example.com/y", kind="<script>ZQ-KIND</script>", date="ZQ-DATE")
        self.plant("Hidden‮characters", "https://example.com/z", date="2030-02-31")
        text = self.text()
        self.absent(text, "ZQ-ELSEWHERE", "zq-elsewhere", "ZQ-KIND", "ZQ-DATE", "‮", "2030-02-31")
        got = self.built()["published"]["data"]["documents"]
        self.assertEqual(got, [{"title": "Fine", "kind": "", "url": "https://example.com/y", "date": None},
                               {"title": "Hiddencharacters", "kind": "Report", "url": "https://example.com/z", "date": None}],
                         msg="a bad kind and a bad date are published as no kind and no date, and hidden characters are taken out of a title")

    def test_markup_in_a_title_stays_text_and_a_quote_in_a_link_stays_inside_the_data(self):
        self.plant("<b>ZQ-BOLD</b>", "https://example.com/a'b`c")
        text = self.text()
        self.not_in_file(text, "<b>ZQ-BOLD</b>", "a title with markup is never in the file as markup")
        block = re.search(r'<script type="application/json" id="clark-data">([^<]*)</script>', text).group(1)
        docs = json.loads(block)["data"]["documents"]
        self.assertEqual(docs[0]["title"], "<b>ZQ-BOLD</b>", msg="the title reads back from the data block as the text that was typed")
        self.assertEqual(docs[0]["url"], "https://example.com/a'b`c", msg="the link with a quote in it reads back whole from the data block")

    def test_a_document_added_and_hidden_through_the_route_is_absent(self):
        status, body = self.change({"project": "ABC", "kind": "documents", "op": "new", "place": "report",
                                    "values": {"title": "ZQ-ROUTE-TITLE", "kind": "Slides", "url": "https://zq-route.example.com/deck", "date": "2034-04-04"}})
        self.assertEqual(status, 200, msg=f"adding a document through the route should give status 200; it gave {status} {body}")
        self.in_file(self.text(), "ZQ-ROUTE-TITLE", "a document added through the route is in the published file")
        status, _ = self.change({"project": "ABC", "kind": "report_hidden", "op": "new", "id": body["ref"], "place": "eye"})
        self.assertEqual(status, 200, msg="hiding the document through the route should give status 200")
        self.absent(self.text(), "ZQ-ROUTE-TITLE", "zq-route.example.com", "2034-04-04")

    def test_another_projects_document_is_not_in_this_projects_file(self):
        with self.s.step("dashboard", USER) as st:
            st.create("projects", {"code": "XYZ", "name": "Second Programme", "health": "On track"})
        self.plant("ZQ-OTHER-PROJECT", "https://zq-other.example.com/x", project="XYZ")
        text = self.text()
        self.absent(text, "ZQ-OTHER-PROJECT", "zq-other.example.com", "XYZ-L-001")


class Markers(Published):
    """The second barrier (publish_flow.markers_for): the text of a document that must not be in the file is looked for in the
    finished bytes, so a leak that got past publish.select is still held back before a copy goes to the client."""

    def markers(self):
        return publish_flow.markers_for(self.s, "ABC", self.built()["published"])

    def test_a_left_out_documents_id_title_and_link_are_markers_and_a_shown_ones_are_not(self):
        shown = self.plant("ZQ-SHOWN-MARK", "https://zq-shown-mark.example.com/a")
        hidden = self.plant("ZQ-HIDDEN-MARK", "https://zq-hidden-mark.example.com/b")
        self.hide(hidden)
        archived = self.plant("ZQ-ARCHIVED-MARK", "https://zq-archived-mark.example.com/c", archived=1)
        got = list(self.markers())
        for text in (hidden, "ZQ-HIDDEN-MARK", "https://zq-hidden-mark.example.com/b", archived, "ZQ-ARCHIVED-MARK", "https://zq-archived-mark.example.com/c"):
            self.assertIn(text, got, msg=f"{text!r} of a left-out document should be a marker")
        for text in ("ZQ-SHOWN-MARK", "https://zq-shown-mark.example.com/a"):
            self.assertNotIn(text, got, msg=f"{text!r} is published, so it is not a marker")
        self.assertIn(shown, got, msg="an id is always a marker (no document id is published)")

    def test_a_file_that_carries_a_hidden_documents_title_is_refused_by_the_copy_check(self):
        hidden = self.plant("ZQ-LEAKED-TITLE", "https://zq-leaked.example.com/x")
        self.hide(hidden)
        body = self.built()["body"].replace(b"</body>", b"<p>ZQ-LEAKED-TITLE</p></body>")
        problems = to_client.check_copy(body, markers=self.markers(), folder=None)
        self.assertTrue(problems, msg="a file that carries a hidden document's title must be refused")
        clean = to_client.check_copy(self.built()["body"], markers=self.markers(), folder=None)
        self.assertEqual(clean, [], msg="the file as built carries none of them")


if __name__ == "__main__":
    unittest.main()
