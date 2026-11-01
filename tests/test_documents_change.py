"""#74 Supporting documents, first slice: add, edit, hide and show a document link through POST /api/change, each one step with
one Undo (src/clark/changes.py and src/clark/store.py; guarded). Move and archive from the page are a later slice; archive and
restore of a document by the route are #126's and stay as they were.

Run: python3 dev/run_tests.py test_documents_change
Each test makes a real store in a temporary folder (fictional data, example.com only) and calls the same functions the server calls.
"""
import json
import re
import sqlite3
import unittest

from _demo import USER, DemoStore
from _paths import SRC
from clark import changes, doclinks, store as store_module

LINK = "https://example.com/minutes/week-1"


def new(project="ABC", **values):
    base = {"title": "Steering minutes", "kind": "Minutes", "url": LINK, "date": "2030-01-10"}
    return {"project": project, "kind": "documents", "op": "new", "values": {**base, **values}, "place": "report"}


def edit(ref, project="ABC", **changes_):
    return {"project": project, "kind": "documents", "op": "update", "id": ref, "changes": changes_, "place": "report"}


def eye(op, ref, project="ABC"):
    return {"project": project, "kind": "report_hidden", "op": op, "id": ref, "place": "eye"}


class Base(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store
        self.path = self.s.path
        self.change = changes.make_change(self.path, [], USER)
        self.undo = changes.make_undo(self.path, [], USER)

    def ok(self, request):
        status, body = self.change(request)
        self.assertEqual((status, body.get("message")), (200, None), body)
        return body

    def snapshot(self):
        con = sqlite3.connect(str(self.path))
        try:
            return tuple(con.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
                         for t in ("applies", "change_log", "documents", "report_hidden"))
        finally:
            con.close()

    def refused(self, request, words, status=400):
        before = self.snapshot()
        got = self.change(request)
        self.assertEqual((got[0], got[1]["ok"], got[1]["message"]), (status, False, words), request)
        self.assertEqual(self.snapshot(), before, "nothing was written")

    def back(self, apply_id, project="ABC"):
        status, body = self.undo({"project": project, "apply_id": apply_id})
        self.assertEqual(status, 200, body)
        return body

    def doc(self, ref, project="ABC"):
        return self.s.read("documents", ref=f"{project}|{ref}")

    def log_rows(self, apply_id):
        return [dict(r) for r in self.s.con.execute("SELECT tbl, item_id, field FROM change_log WHERE apply_id = ?", (apply_id,))]


class Add(Base):
    def test_add_is_one_step_with_an_id_that_never_reads_as_a_work_item(self):
        body = self.ok(new())
        self.assertEqual(body["ref"], "ABC-L-001")
        self.assertIsNone(store_module.ITEM_ID.fullmatch(body["ref"]), "a document id is never a work item id")
        self.assertIsNone(store_module.item_table(body["ref"]))
        row = self.doc("ABC-L-001")
        self.assertEqual((row["title"], row["kind"], row["url"], row["date"], row["archived"]),
                         ("Steering minutes", "Minutes", LINK, "2030-01-10", 0))
        self.assertEqual(body["item"]["id"], "ABC-L-001")
        self.assertTrue(body["undoable"])
        self.assertEqual({r["tbl"] for r in self.log_rows(body["apply_id"])}, {"documents"})
        second = self.ok(new(title="Action list", kind="Actions list"))
        self.assertEqual(second["ref"], "ABC-L-002")
        self.assertGreater(self.doc("ABC-L-002")["sort_order"], row["sort_order"], "a new document goes at the end")

    def test_undo_of_an_add_takes_the_document_away_and_its_number_is_never_used_again(self):
        body = self.ok(new())
        self.back(body["apply_id"])
        self.assertIsNone(self.doc("ABC-L-001"))
        self.assertEqual(self.ok(new())["ref"], "ABC-L-002", "an undone add never frees its number")

    def test_the_link_is_kept_as_the_one_link_rule_gives_it(self):
        self.ok(new(url="  HTTPS://Example.COM/A/b  "))
        self.assertEqual(self.doc("ABC-L-001")["url"], "https://example.com/A/b")

    def test_an_empty_date_is_kept_as_no_date(self):
        self.ok(new(date=""))
        self.assertIsNone(self.doc("ABC-L-001")["date"])
        self.ok(new(date=None))
        self.assertIsNone(self.doc("ABC-L-002")["date"])

    def test_every_refused_link_is_said_in_the_link_rules_own_words(self):
        cases = {"javascript:alert(1)": doclinks.NOT_USABLE, "JaVaScRiPt:alert(1)": doclinks.NOT_USABLE,
                 "java\tscript:alert(1)": doclinks.HIDDEN, "data:text/html,x": doclinks.NOT_USABLE,
                 "vbscript:x": doclinks.NOT_USABLE, "file:///etc/passwd": doclinks.NOT_USABLE, "blob:https://example.com/x": doclinks.NOT_USABLE,
                 "ftp://example.com/x": doclinks.NOT_USABLE, "//example.com/x": doclinks.NOT_USABLE, "example.com": doclinks.NOT_USABLE,
                 "": doclinks.EMPTY, "https://user:pw@example.com/": doclinks.CREDENTIALS}
        for url, words in cases.items():
            with self.subTest(url=url):
                self.refused(new(url=url), words)

    def test_title_kind_and_date_rules(self):
        self.refused(new(title=""), "A title can't be blank.")
        self.refused(new(title="x" * 121), "A title can be at most 120 characters.")
        self.refused(new(title="Minutes‮"), "A title can't hold control or invisible characters.")
        self.refused(new(title="portal.example.net"), doclinks.TITLE_ELSEWHERE)
        self.refused(new(kind="Memo"), changes.DOC_KIND_WORDS)
        self.refused(new(kind=None), changes.DOC_KIND_WORDS)
        self.refused(new(date="2030-02-31"), changes.NOT_A_DATE)
        self.refused(new(date="soon"), changes.NOT_A_DATE)
        self.ok(new(title="example.com minutes", url="https://portal.example.com/m"))      # the link's own site in its title is fine

    def test_a_title_with_markup_is_kept_as_text(self):
        self.ok(new(title="<b>x</b>"))
        self.assertEqual(self.doc("ABC-L-001")["title"], "<b>x</b>")

    def test_a_request_cannot_name_another_field(self):
        for field in ("project", "id", "sort_order", "archived"):
            with self.subTest(field=field):
                request = new()
                request["values"][field] = "ABC-L-009" if field == "id" else 1
                self.refused(request, f"The field '{field}' can't be set here.")

    def test_an_archived_project_takes_no_new_document(self):
        with self.s.step("dashboard", USER) as st:
            st.archive("projects", "ABC")
        self.refused(new(), changes.PROJECT_NOT_ACTIVE)

    def test_the_store_itself_holds_the_rules_whoever_writes(self):
        with self.assertRaises(store_module.Invalid):
            with self.s.step("dashboard", USER) as st:
                st.create("documents", {"project": "ABC", "title": "X", "kind": "Minutes", "url": "javascript:alert(1)"})
        with self.assertRaises(store_module.Invalid):
            with self.s.step("dashboard", USER) as st:
                st.create("documents", {"project": "ABC", "title": "X", "kind": "Memo", "url": LINK})
        self.assertEqual(self.s.read("documents", "ABC"), [])


class Edit(Base):
    def setUp(self):
        super().setUp()
        self.ref = self.ok(new())["ref"]

    def test_edit_is_one_step_and_undo_puts_each_field_back(self):
        body = self.ok(edit(self.ref, title="Board minutes", kind="Report", url="https://example.com/board", date=""))
        row = self.doc(self.ref)
        self.assertEqual((row["title"], row["kind"], row["url"], row["date"]), ("Board minutes", "Report", "https://example.com/board", None))
        self.assertEqual(body["item"]["title"], "Board minutes")
        self.assertEqual({r["field"] for r in self.log_rows(body["apply_id"])}, {"title", "kind", "url", "date"})
        self.back(body["apply_id"])
        row = self.doc(self.ref)
        self.assertEqual((row["title"], row["kind"], row["url"], row["date"]), ("Steering minutes", "Minutes", LINK, "2030-01-10"))

    def test_an_edit_that_changes_nothing_has_no_undo(self):
        body = self.ok(edit(self.ref, title="Steering minutes"))
        self.assertIsNone(body["apply_id"])

    def test_an_edit_meets_the_same_rules(self):
        self.refused(edit(self.ref, url="javascript:alert(1)"), doclinks.NOT_USABLE)
        self.refused(edit(self.ref, title=" "), "A title can't be blank.")
        self.refused(edit(self.ref, kind="Memo"), changes.DOC_KIND_WORDS)
        self.refused(edit(self.ref, title="evil.example.net"), doclinks.TITLE_ELSEWHERE)
        self.refused(edit(self.ref), "Say what to change.")

    def test_another_projects_document_and_a_missing_one_get_the_same_words(self):
        with self.s.step("dashboard", USER) as st:
            st.create("projects", {"code": "XYZ", "name": "Second Programme", "health": "On track"})
        theirs = self.ok(new(project="XYZ"))["ref"]
        self.refused(edit(theirs, title="Mine now"), changes.DOC_NOT_MINE)
        self.refused(edit("ABC-L-099", title="Mine now"), changes.DOC_NOT_MINE)
        self.refused(edit("ABC|ABC-L-001", title="Mine now"), changes.DOC_NOT_MINE)
        self.refused(edit(["x"], title="Mine now"), changes.DOC_NOT_MINE)
        self.assertEqual(self.doc(theirs, "XYZ")["title"], "Steering minutes")

    def test_an_archived_document_is_not_edited(self):
        self.ok({"project": "ABC", "kind": "documents", "op": "archive", "id": f"ABC|{self.ref}"})
        self.refused(edit(self.ref, title="Later"), changes.BULK_ARCHIVED)

    def test_a_later_change_is_left_as_it_is_by_an_older_undo(self):
        first = self.ok(edit(self.ref, title="First"))
        self.ok(edit(self.ref, title="Second"))
        status, body = self.undo({"project": "ABC", "apply_id": first["apply_id"]})
        self.assertEqual(status, 200, body)
        self.assertEqual(self.doc(self.ref)["title"], "Second")
        self.assertTrue(body["skipped"])
        self.assertNotIn("ABC-L-001", body["words"], "a document is named by its title, never its id")


class Hide(Base):
    def setUp(self):
        super().setUp()
        self.ref = self.ok(new())["ref"]

    def hidden(self):
        return sorted(r["item_id"] for r in self.s.read("report_hidden", "ABC"))

    def test_hide_and_show_each_one_step_with_undo_through_the_hidden_rows_record(self):
        hid = self.ok(eye("new", self.ref))
        self.assertEqual((self.hidden(), hid["hidden"]), ([self.ref], [self.ref]))
        self.assertIn("hidden", [c[1] for c in self.s.con.execute("PRAGMA table_info(report_sections)")])
        self.assertNotIn("hidden", [c[1] for c in self.s.con.execute("PRAGMA table_info(documents)")], "no new column")
        self.back(hid["apply_id"])
        self.assertEqual(self.hidden(), [])
        hid = self.ok(eye("new", self.ref))
        shown = self.ok(eye("delete", self.ref))
        self.assertEqual(self.hidden(), [])
        self.back(shown["apply_id"])
        self.assertEqual(self.hidden(), [self.ref])

    def test_the_eye_takes_only_this_projects_documents(self):
        with self.s.step("dashboard", USER) as st:
            st.create("projects", {"code": "XYZ", "name": "Second Programme", "health": "On track"})
        theirs = self.ok(new(project="XYZ"))["ref"]
        for ref in (theirs, "ABC-L-099", "ABC|ABC-L-001", "ABC-L-1"):
            with self.subTest(ref=ref):
                self.refused(eye("new", ref), changes.ITEM_NOT_MINE)
        with self.assertRaises(store_module.Invalid):
            with self.s.step("dashboard", USER) as st:
                st.create("report_hidden", {"project": "ABC", "item_id": theirs})

    def test_an_archived_document_may_still_be_hidden_and_shown(self):
        self.ok({"project": "ABC", "kind": "documents", "op": "archive", "id": f"ABC|{self.ref}"})
        self.ok(eye("new", self.ref))
        self.ok(eye("delete", self.ref))

    def test_the_picker_add_puts_a_hidden_document_back(self):
        self.ok(eye("new", self.ref))
        body = self.ok({"project": "ABC", "kind": "report_hidden", "op": "pick", "ids": [self.ref], "place": "report"})
        self.assertEqual((body["added"], body["shown_to_client"], self.hidden()), ([self.ref], [], []))
        self.back(body["apply_id"])
        self.assertEqual(self.hidden(), [self.ref])


class Read(Base):
    def test_the_page_reads_live_documents_in_order(self):
        a = self.ok(new(title="One"))["ref"]
        b = self.ok(new(title="Two"))["ref"]
        self.ok({"project": "ABC", "kind": "documents", "op": "archive", "id": f"ABC|{b}"})
        got = self.s.data_for("ABC")["documents"]
        self.assertEqual([d["id"] for d in got], [a])
        self.assertEqual(set(got[0]), {"id", "title", "kind", "url", "date", "sort_order", "archived"})
        self.assertEqual([d["id"] for d in self.s.data_for("ABC", archived="only")["documents"]], [b])


class OneList(unittest.TestCase):
    def test_the_page_offers_the_same_kinds_as_the_store_takes(self):
        text = (SRC / "clark" / "page" / "src" / "logic" / "documents.js").read_text(encoding="utf-8")
        found = re.search(r"export const KINDS = (\[[^\]]*\]);", text)
        self.assertEqual(tuple(json.loads(found.group(1))), doclinks.KINDS)


if __name__ == "__main__":
    unittest.main()
