"""A section's content (needs, tracker) is never shown in History or the Activity tab (src/clark/history.py; guarded): not as 'Text',
not before or after, not when a removed section is unpacked.

Run: python3 dev/run_tests.py test_history_section_bodies
"""
import json
import unittest

from _demo import USER
from clark import history
from test_changes import Api, KIND

MARK = "ZQ-HISTORY-MARK"
OTHER = "ZQ-HISTORY-OTHER"


def body(word):
    return json.dumps({"v": 1, "rows": [{"what": word, "kind": "decision", "from": "Example team", "by": "", "hidden": 0}]})


class Shown(Api):
    def write(self, ref, word):
        status, got = self.change(self.req("update", id=ref, changes={"body": body(word)}))
        self.assertEqual(status, 200, got)
        return got

    def rows(self):
        return history.view_for_project(self.s.con, "ABC")["rows"]

    def activity(self):
        return history.activity_for_project(self.s.con, "ABC")["rows"]

    def everything_shown(self):
        return json.dumps([self.rows(), self.activity()])

    def check_nothing_leaks(self):
        shown = self.everything_shown()
        for word in (MARK, OTHER, '"rows"', "Example team"):
            self.assertNotIn(word, shown)

    def section(self, kind):
        return self.ok("new", values={"type": kind, "title": "Needs from you" if kind == "needs" else "Progress"})["ref"]


class ContentIsRedacted(Shown):
    def test_a_body_change_says_only_that_the_content_changed_for_a_needs_and_a_tracker_section(self):
        for kind in ("needs", "tracker"):
            with self.subTest(kind=kind):
                ref = self.section(kind)
                self.write(ref, MARK)
                self.write(ref, OTHER)
                rows = [r for r in self.rows() if r["item_id"] == ref and r["field"] == history.CONTENT_FIELD]
                self.assertEqual(len(rows), 2)
                for r in rows:
                    self.assertEqual((r["kind"], r["from"], r["to"]), ("Changed", "", history.CONTENT_CHANGED))
                self.check_nothing_leaks()

    def test_an_undo_of_a_body_change_is_redacted_too(self):
        ref = self.section("needs")
        self.write(ref, MARK)
        second = self.write(ref, OTHER)
        self.undone(second["apply_id"])
        undone = [r for r in self.rows() if r["kind"] == "Undone" and r["item_id"] == ref]
        self.assertEqual([(r["field"], r["from"], r["to"]) for r in undone], [(history.CONTENT_FIELD, "", history.CONTENT_CHANGED)])
        self.check_nothing_leaks()

    def test_a_removed_section_does_not_unpack_its_content(self):
        ref = self.section("tracker")
        self.write(ref, MARK)
        deleted = self.ok("delete", id=ref)
        removed = [r for r in self.rows() if r["kind"] == "Removed" and r["item_id"] == ref]
        self.assertEqual(len(removed), 1)
        self.assertIn("Title: Progress", removed[0]["from"])
        self.assertNotIn("Text:", removed[0]["from"])
        self.assertNotIn("Content:", removed[0]["from"])
        self.check_nothing_leaks()
        self.undone(deleted["apply_id"])                                  # and the Undo of the removal
        self.check_nothing_leaks()
        self.assertTrue(all(r["field"] != "Text" for r in self.rows()))

    def test_the_diff_never_carries_content(self):
        ref = self.section("needs")
        self.write(ref, MARK + " one two three four")
        self.write(ref, OTHER + " one two three five")
        for r in self.activity():
            self.assertFalse(r.get("diff"), r)

    def test_a_created_section_shows_only_its_title(self):
        ref = self.section("needs")
        self.write(ref, MARK)
        created = [r for r in self.rows() if r["kind"] == "Created" and r["item_id"] == ref]
        self.assertEqual([(r["field"], r["to"]) for r in created], [("Section", "Needs from you")])

    def test_the_sheet_and_page_rows_share_the_same_redaction(self):
        ref = self.section("needs")
        self.write(ref, MARK)
        self.assertNotIn(MARK, json.dumps(history.rows_for_project(self.s.con, "ABC")))

    def test_other_fields_of_a_section_still_show_as_before(self):
        ref = self.section("needs")
        self.ok("update", id=ref, changes={"title": "Needed from the client", "hidden": 1})
        fields = {r["field"]: (r["from"], r["to"]) for r in self.rows() if r["item_id"] == ref and r["kind"] == "Changed"}
        self.assertEqual(fields["Title"], ("Needs from you", "Needed from the client"))
        self.assertEqual(fields["Hidden"], ("No", "Yes"))
        self.assertNotIn(history.CONTENT_FIELD, fields)


class TheFieldWordIsUnchangedElsewhere(unittest.TestCase):
    def test_text_is_still_the_word_for_a_body_in_other_tables(self):
        self.assertEqual(history.field_name("comments", "body"), "Text")
        self.assertEqual(history._unpack('{"id": "x", "body": "kept"}', "comments"), "ID: x, Text: kept")
        self.assertEqual(history._unpack('{"id": "x", "body": "dropped"}', "report_sections"), "ID: x")


if __name__ == "__main__":
    unittest.main()
