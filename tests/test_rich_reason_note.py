"""Item 1005: the At a glance Reason (projects.health_reason) is on the one rich editor: the column keeps its name, new rows hold the
editor's HTML (cleaned on write by the store's own check, cleaned again on the way into the file), old rows hold plain text and still read.
The Movement Internal note (milestones.internal_note) has the same rule; its own files (test_movement_hostile, test_changes_milestones,
test_movement_never_published) hold its hostile and never-published cases.

Run: python3 dev/run_tests.py test_rich_reason_note
"""
import unittest

from _demo import USER, DemoStore
from clark import ask_data, changes, glance, sanitise, store as clark_store

HOSTILE = ('<p onclick="x()">ZQ-REASON-1005 <a href="javascript:alert(1)">link</a></p><script>alert(2)</script>'
           '<img src=x onerror=alert(3)><style>p{}</style><iframe src=//evil></iframe><ul><li>one</li></ul>')
LEGACY = 'Late: <b>supplier</b> & "QA" \'soon\'\nsecond line a < b'


class Base(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store
        self.change = changes.make_change(self.s.path, [], USER)
        self.undo = changes.make_undo(self.s.path, [], USER)

    def proj(self, **fields):
        return {"project": "ABC", "kind": "projects", "op": "update", "changes": fields}

    def send(self, **fields):
        return self.change(self.proj(**fields))

    def reason(self):
        return self.s.read("projects", ref="ABC")["health_reason"]

    def raw_write(self, text):                     # written around the change route, as an old row is
        with self.s.step("dashboard", USER) as st:
            st.update("projects", "ABC", {"health": "On track", "health_reason": text})


class WriteSide(Base):
    def test_the_editors_html_is_stored_cleaned_and_cleaning_it_again_changes_nothing(self):
        status, got = self.send(health="At risk", health_reason=HOSTILE)
        self.assertEqual(status, 200, got)
        stored = self.reason()
        for bad in ("onclick", "javascript:", "<script", "<img", "onerror", "<style", "<iframe", "alert"):
            self.assertNotIn(bad, stored, bad)
        self.assertEqual(stored, "<p>ZQ-REASON-1005 link</p><ul><li>one</li></ul>")
        self.assertEqual(sanitise.clean_html(stored), stored)
        self.assertEqual(got["project"]["health_reason"], stored, "the reply says what is stored")

    def test_plain_text_from_an_older_caller_is_stored_as_escaped_paragraphs(self):
        status, got = self.send(health="At risk", health_reason=LEGACY)
        self.assertEqual(status, 200, got)
        self.assertEqual(self.reason(), "<p>Late: &lt;b&gt;supplier&lt;/b&gt; &amp; \"QA\" 'soon'</p><p>second line a &lt; b</p>")
        self.assertEqual(sanitise.rich_plain_text(self.reason()), LEGACY)

    def test_the_words_are_counted_not_the_markup_and_hidden_characters_are_refused(self):
        limit = clark_store.REASON_LIMIT
        self.assertEqual(self.send(health="At risk", health_reason="<p>" + "x" * limit + "</p>")[0], 200)
        for bad, words in (("<p>" + "x" * (limit + 1) + "</p>", clark_store.REASON_TOO_LONG), ("x" * (limit + 1), clark_store.REASON_TOO_LONG),
                           ("<p>a\x00b</p>", clark_store.REASON_BAD_CHARS), ("<p>a‮b</p>", clark_store.REASON_BAD_CHARS),
                           ("<p>a​b</p>", clark_store.REASON_BAD_CHARS), ("a\x00b", clark_store.REASON_BAD_CHARS)):
            before = self.reason()
            status, got = self.send(health_reason=bad)
            self.assertEqual((status, got.get("message")), (400, words), bad[:20])
            self.assertEqual(self.reason(), before)
        self.assertEqual(self.send(health_reason=["x"])[0], 400)

    def test_no_words_is_no_reason(self):
        self.assertEqual(self.send(health="At risk", health_reason="First")[0], 200)
        for empty in ("<p></p>", "<p><br></p>", "<p>  </p>", "", "  \n "):
            status, got = self.send(health="Off track", health_reason=empty)
            self.assertEqual((status, got.get("message")), (400, changes.HEALTH_NEEDS_REASON), repr(empty))
        self.assertEqual(self.send(health="On track", health_reason="Fine again")[0], 200)
        self.assertEqual(self.send(health_reason="<p></p>")[0], 200)          # on track, the reason may be cleared
        self.assertIsNone(self.reason())

    def test_one_undo_puts_back_an_old_plain_reason_as_it_was(self):
        self.raw_write(LEGACY)
        status, got = self.send(health_reason="<p>New words</p>")
        self.assertEqual(status, 200, got)
        status, back = self.undo({"project": "ABC", "apply_id": got["apply_id"]})
        self.assertEqual(status, 200, back)
        self.assertEqual(self.reason(), LEGACY, "the old plain text comes back as it was, and still reads")


class ReadSide(Base):
    def test_an_old_plain_reason_reads_as_its_words_in_the_tile_and_the_ask_lines(self):
        self.raw_write(LEGACY)
        project = self.s.read("projects", ref="ABC")
        tile = next(t for t in glance.tiles({"project": project}, "2026-11-01") if t["tile"] == "health")
        self.assertEqual(tile["reason"], LEGACY)
        self.assertIn(LEGACY, tile["label"])
        lines = "\n".join(ask_data.project_lines(project))
        self.assertIn("Late: supplier & \"QA\" 'soon'", lines)
        self.assertNotIn("<b>", lines)

    def test_html_reads_as_words_with_no_tags_in_the_tile_and_the_ask_lines(self):
        self.assertEqual(self.send(health="At risk", health_reason="<p>First line</p><ul><li>second</li></ul>")[0], 200)
        project = self.s.read("projects", ref="ABC")
        tile = next(t for t in glance.tiles({"project": project}, "2026-11-01") if t["tile"] == "health")
        self.assertEqual(tile["reason"], "First line\nsecond")
        self.assertNotIn("<", tile["label"])
        self.assertNotIn("<p>", "\n".join(ask_data.project_lines(project)))


if __name__ == "__main__":
    unittest.main()
