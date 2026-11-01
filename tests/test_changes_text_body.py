"""A text section's body (Summary, This week, Next week) through the change route (src/clark/changes.py; guarded): the write is
cleaned by the server, is one step with one Undo, is recorded in the history, and is refused in plain words when it is too long
or not text. A reply never carries the body.

Run: python3 dev/run_tests.py test_changes_text_body
"""
import json
import re
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

from _demo import USER, DemoStore
from clark import changes, publish, sanitise, server as sv
from test_changes import Api, KIND

SUMMARY, THIS_WEEK, NEXT_WEEK = "ABC-S-005", "ABC-S-006", "ABC-S-007"
DIRTY = ('<p onclick="x()">Words <strong>bold</strong> <em>soft</em></p>'
         '<script>window.ZQ_RAN=1</script><style>p{color:red}</style><img src="x" onerror="window.ZQ_RAN=1">'
         '<a href="javascript:window.ZQ_RAN=1">ZQ-BAD-LINK</a><a href="&#106;avascript:window.ZQ_RAN=1">ZQ-ENC-LINK</a>'
         '<a href="https://example.com/notes" onmouseover="x()" target="_blank">ZQ-SAFE-LINK</a><ul><li>one</li></ul>')


class TextBody(Api):
    def write(self, ref, body, **more):
        return self.change(self.req("update", id=ref, changes={"body": body}, **more))

    def stored(self, ref):
        return self.s.read(KIND, ref=ref)["body"]

    def state(self):
        con = sqlite3.connect(str(self.path))
        try:
            return (con.execute("SELECT count(*) FROM applies").fetchone()[0], con.execute("SELECT count(*) FROM change_log").fetchone()[0],
                    con.execute("SELECT group_concat(id || type || title || body || sort_order || beside || hidden) FROM report_sections").fetchone()[0])
        finally:
            con.close()

    def refused_body(self, ref, body, words=None):
        before = self.state()
        status, got = self.write(ref, body)
        self.assertEqual((status, got["ok"]), (400, False))
        if words is not None:
            self.assertEqual(got["message"], words)
        self.assertEqual(self.state(), before, "nothing was written")
        return got["message"]


class Writing(TextBody):
    def test_the_three_sections_take_a_body_and_store_it_cleaned(self):
        for ref in (SUMMARY, THIS_WEEK, NEXT_WEEK):
            with self.subTest(ref=ref):
                self.assertEqual(self.s.read(KIND, ref=ref)["type"], "text")
                status, got = self.write(ref, "<p>Hello <strong>there</strong></p>")
                self.assertEqual((status, got["ok"]), (200, True), got)
                self.assertEqual(self.stored(ref), "<p>Hello <strong>there</strong></p>")

    def test_dirty_html_comes_back_stripped_and_what_is_stored_is_the_cleaned_text(self):
        status, got = self.write(SUMMARY, DIRTY)
        self.assertEqual(status, 200, got)
        stored = self.stored(SUMMARY)
        self.assertEqual(stored, sanitise.clean_html(DIRTY), "the server's own cleaner decides, never the page's")
        for never in ("<script", "ZQ_RAN", "onerror", "onclick", "onmouseover", "javascript:", "avascript:", "<style", "color:red", "<img", "target="):
            self.assertNotIn(never, stored, never)
        for kept in ("ZQ-BAD-LINK", "ZQ-ENC-LINK", "ZQ-SAFE-LINK", "<strong>bold</strong>", "<li>one</li>"):
            self.assertIn(kept, stored, kept)
        self.assertEqual(re.findall(r'href="([^"]*)"', stored), ["https://example.com/notes"])

    def test_a_reply_never_carries_the_body(self):
        status, got = self.write(SUMMARY, "<p>ZQ-IN-A-BODY</p>")
        self.assertEqual(status, 200)
        self.assertNotIn("ZQ-IN-A-BODY", json.dumps(got))
        self.assertNotIn("body", got["sections"][0])
        self.assertEqual([r["id"] for r in got["sections"]], [r["id"] for r in self.rows()])

    def test_one_save_is_one_step_and_one_undo_puts_the_old_body_back(self):
        self.write(SUMMARY, "<p>First</p>")
        steps = self.snapshot()[0]
        status, got = self.write(SUMMARY, "<p>Second</p>")
        self.assertEqual(status, 200)
        self.assertEqual(self.snapshot()[0], steps + 1, "one save, one step")
        self.assertEqual(self.undone(got["apply_id"])[0], 200)
        self.assertEqual(self.stored(SUMMARY), "<p>First</p>")
        self.assertEqual(self.undone(got["apply_id"])[0], 409, "the same step can't be undone twice")

    def test_a_save_is_recorded_in_the_history_without_the_words_themselves(self):
        status, got = self.write(SUMMARY, "<p>ZQ-HISTORY-WORDS</p>")
        self.assertEqual(status, 200)
        rows = self.s.con.execute("SELECT item_id, field FROM change_log WHERE apply_id = ?", (got["apply_id"],)).fetchall()
        self.assertEqual([(r["item_id"], r["field"]) for r in rows], [(SUMMARY, "body")])
        words = self.undone(got["apply_id"])[1]["words"]
        self.assertIn("the content of", words)
        self.assertNotIn("ZQ-HISTORY-WORDS", words)

    def test_saving_the_same_text_again_makes_no_step_and_saving_twice_keeps_the_body(self):
        first = self.write(SUMMARY, "<p>Same</p>")[1]
        self.assertIsNotNone(first["apply_id"])
        before = self.snapshot()
        again = self.write(SUMMARY, "<p>Same</p>")[1]
        self.assertIsNone(again["apply_id"], "nothing changed: no Undo")
        self.assertEqual(self.snapshot(), before)
        self.write(SUMMARY, "<p>Same</p><p>More</p>")
        self.assertEqual(self.stored(SUMMARY), "<p>Same</p><p>More</p>")

    def test_a_save_leaves_the_other_sections_and_fields_alone(self):
        self.write(THIS_WEEK, "<p>Other</p>")
        row = self.s.read(KIND, ref=SUMMARY)
        title, beside = row["title"], row["beside"]
        self.write(SUMMARY, "<p>Mine</p>")
        self.assertEqual(self.stored(THIS_WEEK), "<p>Other</p>")
        row = self.s.read(KIND, ref=SUMMARY)
        self.assertEqual((row["title"], row["beside"], row["type"]), (title, beside, "text"))

    def test_the_title_and_the_body_can_change_in_one_step(self):
        status, got = self.change(self.req("update", id=SUMMARY, changes={"title": "Overview", "body": "<p>x</p>"}))
        self.assertEqual(status, 200, got)
        self.assertEqual((self.s.read(KIND, ref=SUMMARY)["title"], self.stored(SUMMARY)), ("Overview", "<p>x</p>"))

    def test_an_empty_body_is_kept_as_empty(self):
        self.write(SUMMARY, "<p>x</p>")
        status, got = self.write(SUMMARY, "")
        self.assertEqual(status, 200, got)
        self.assertEqual(self.stored(SUMMARY), "")


class Refusing(TextBody):
    def test_an_unknown_section_and_another_projects_section_are_refused_alike(self):
        for ref in ("ABC-S-999", "XYZ-S-005", "", "nothing"):
            with self.subTest(ref=ref):
                self.refused(self.req("update", id=ref, changes={"body": "<p>x</p>"}), changes.NOT_MINE)

    def test_a_body_that_is_not_text_is_refused_in_plain_words(self):
        for bad in (None, 5, ["<p>x</p>"], {"a": 1}):
            with self.subTest(body=bad):
                self.refused(self.req("update", id=SUMMARY, changes={"body": bad}), changes.BODY_NOT_TEXT)

    def test_a_body_over_its_limit_is_refused_in_words_and_nothing_is_written(self):
        words = self.refused_body(SUMMARY, "<p>" + "a" * changes.TEXT_BODY_MAX + "</p>")
        self.assertEqual(words, changes.WORDS_TOO_LONG)
        self.assertNotIn("Traceback", words)
        self.assertIn("too long", words)

    def test_the_limit_counts_what_is_stored_and_the_edge_is_accepted(self):
        edge = "a" * (changes.TEXT_BODY_MAX - len("<p></p>"))
        self.assertEqual(self.write(SUMMARY, f"<p>{edge}</p>")[0], 200)
        self.assertEqual(len(self.stored(SUMMARY).encode("utf-8")), changes.TEXT_BODY_MAX)
        self.refused_body(SUMMARY, f"<p>{edge}a</p>", changes.WORDS_TOO_LONG)

    def test_the_limit_counts_bytes_so_wide_letters_cannot_get_past_it(self):
        wide = "é" * (changes.TEXT_BODY_MAX // 2)           # two bytes each: over the limit in bytes, under it in characters
        self.refused_body(SUMMARY, f"<p>{wide}</p>", changes.WORDS_TOO_LONG)

    def test_text_the_cleaner_refuses_is_refused_in_the_same_words(self):
        self.refused_body(SUMMARY, "a" * (sanitise.MAX_CHARS + 1), changes.WORDS_TOO_LONG)

    def test_the_limit_is_the_one_the_change_route_carries(self):
        self.assertEqual(changes.TEXT_BODY_MAX, sv.SECTION_BODY_MAX)

    def test_a_section_of_another_type_is_still_refused_a_text_body(self):
        for row in self.rows():
            if row["type"] in ("text", "needs", "tracker"):
                continue
            with self.subTest(type=row["type"]):
                self.refused_body(row["id"], "<p>x</p>", changes.NO_BODY_HERE)


class Publishing(TextBody):
    def test_the_published_file_shows_the_saved_body_and_a_hidden_section_stays_out(self):
        self.write(SUMMARY, DIRTY)
        self.write(NEXT_WEEK, "<p>ZQ-NEXT-WORDS</p>")
        self.write(THIS_WEEK, "<p>ZQ-HIDDEN-WORDS</p>")
        self.ok("update", id=THIS_WEEK, changes={"hidden": 1})
        folder = tempfile.mkdtemp(prefix="clark-pub-")
        self.addCleanup(shutil.rmtree, folder, True)
        done = publish.publish(self.s, "ABC", folder, by_user=USER, now="2026-10-28", branding=tempfile.mkdtemp(prefix="clark-no-brand-"))
        text = Path(done["path"]).read_text(encoding="utf-8")
        self.assertIn("ZQ-NEXT-WORDS", text)
        self.assertIn("ZQ-SAFE-LINK", text)
        for never in ("ZQ-HIDDEN-WORDS", "ZQ_RAN", "onerror", "onclick", "javascript:", "avascript:"):
            self.assertNotIn(never, text, never)

    def test_the_published_body_is_the_stored_text_for_what_the_editor_writes(self):
        body = ('<h2>Heading</h2><p>A <strong>bold</strong> and <em>soft</em> and <s>struck</s> line<br>next</p>'
                '<ul><li>one</li><li>two</li></ul><ol><li>first</li></ol><blockquote><p>quoted</p></blockquote><hr>'
                '<p>See <a href="https://example.com/a" rel="noopener noreferrer">the notes</a></p>')
        self.assertEqual(sanitise.clean_html(body), body, "the sample is already clean, so it is what the editor writes")
        self.write(SUMMARY, body)
        published = publish.clean_html(self.stored(SUMMARY))
        self.assertEqual(published, self.stored(SUMMARY), "the file draws the saved text exactly as View does")


if __name__ == "__main__":
    unittest.main()
