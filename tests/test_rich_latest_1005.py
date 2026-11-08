"""Item 1005 (PR 1): an item's Latest update and a milestone's Description are on the one rich editor. Both keep their column: new
rows hold the editor's HTML (cleaned by the server), old rows hold plain text and still read. Real change route, real publish.select,
no mock; every row is made up.

Run: python3 dev/run_tests.py test_rich_latest_1005
Per field: a plain legacy value (newlines, <, &, quotes) reads and publishes escaped; hostile HTML is cleaned when it is written AND
again when it is published (even if it was written past the store); a limit counts the words; blank clears; the plain-text readers
(history, the client's filters, the card words, the Word and Excel copies) get words, not tags.
"""
import unittest

from _demo import USER, DemoStore
from clark import changes, client_filters, history, publish, sanitise
from clark.section_kinds import raid3

LEGACY = 'Line one: a < b & "c" it\'s <b>not bold</b>\nLine two\n\nLine four'
LEGACY_HTML = '<p>Line one: a &lt; b &amp; "c" it\'s &lt;b&gt;not bold&lt;/b&gt;</p><p>Line two</p><p></p><p>Line four</p>'
HOSTILE = ('<p onclick="x()">hi <script>alert(1)</script><a href="javascript:alert(2)">bad</a> <img src=x onerror=alert(3)>'
           '<style>p{}</style><iframe src="https://e.example"></iframe></p>')
FIELDS = (("actions", "latest_update", 1000), ("milestones", "description", 2000))


class Base(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store
        self.change = changes.make_change(self.s.path, [], USER)
        self.ref = {"actions": self.demo.action(description="An action"), "milestones": self.demo.milestone}

    def send(self, table, field, value):
        return self.change({"project": "ABC", "kind": table, "op": "update", "id": self.ref[table], "changes": {field: value}, "place": "peek"})

    def stored(self, table, field):
        return self.s.read(table, ref=self.ref[table])[field]

    def raw_write(self, table, field, value):
        with self.s.step("dashboard", USER) as st:
            st.update(table, self.ref[table], {field: value})

    def published(self, table, field):
        data = publish.select(publish.read_inputs(self.s, "ABC", "2026-10-29"))["data"]
        return next(r[field] for r in data[table] if r["id"] == self.ref[table])


class Helpers(unittest.TestCase):
    def test_legacy_plain_text_is_escaped_into_paragraphs(self):
        self.assertEqual(sanitise.rich_or_plain(LEGACY), LEGACY_HTML)

    def test_html_is_cleaned_and_a_clean_value_is_a_fixed_point(self):
        self.assertEqual(sanitise.rich_or_plain("<p>a</p><script>x</script>"), "<p>a</p>")
        self.assertEqual(sanitise.rich_or_plain(LEGACY_HTML), LEGACY_HTML)
        self.assertEqual(sanitise.rich_or_plain(sanitise.rich_or_plain(HOSTILE)), sanitise.rich_or_plain(HOSTILE))

    def test_none_and_blank_give_nothing_and_the_words_are_lines(self):
        for v in (None, "", "  \n  "):
            self.assertEqual(sanitise.rich_or_plain(v), "")
        self.assertEqual(sanitise.rich_plain_text(LEGACY), 'Line one: a < b & "c" it\'s <b>not bold</b>\nLine two\n\nLine four')
        self.assertEqual(sanitise.rich_plain_text("<p>a &amp; b</p><p>c</p>"), "a & b\nc")


class Fields(Base):
    def test_every_field_stores_clean_html_from_the_editor(self):
        for table, field, _ in FIELDS:
            with self.subTest(field):
                status, body = self.send(table, field, "<p>Hello <strong>there</strong></p>")
                self.assertEqual(status, 200, body)
                self.assertEqual(self.stored(table, field), "<p>Hello <strong>there</strong></p>")

    def test_every_field_stores_hostile_html_cleaned(self):
        for table, field, _ in FIELDS:
            with self.subTest(field):
                status, body = self.send(table, field, HOSTILE)
                self.assertEqual(status, 200, body)
                got = self.stored(table, field)
                for bad in ("<script", "onclick", "onerror", "javascript:", "<img", "<style", "<iframe", "alert"):
                    self.assertNotIn(bad, got, bad)
                self.assertIn("hi", got)

    def test_plain_text_from_an_older_caller_is_stored_as_paragraphs(self):
        for table, field, _ in FIELDS:
            with self.subTest(field):
                status, body = self.send(table, field, LEGACY)
                self.assertEqual(status, 200, body)
                self.assertEqual(self.stored(table, field), LEGACY_HTML)

    def test_blank_clears_and_the_limit_counts_the_words(self):
        for table, field, limit in FIELDS:
            with self.subTest(field):
                self.assertEqual(self.send(table, field, "<p>x</p>")[0], 200)
                for blank in ("", "<p></p>", "<p> </p><p><br></p>", None):
                    self.assertEqual(self.send(table, field, "<p>x</p>")[0], 200)
                    status, body = self.send(table, field, blank)
                    self.assertEqual(status, 200, body)
                    self.assertFalse(self.stored(table, field), repr(blank))
                self.assertEqual(self.send(table, field, "<p>%s</p>" % ("a" * limit))[0], 200)
                self.assertEqual(self.send(table, field, "<p><strong>%s</strong></p>" % ("a" * (limit + 1)))[0], 400)

    def test_hidden_characters_and_non_text_are_refused(self):
        for table, field, _ in FIELDS:
            with self.subTest(field):
                for bad in ("<p>a\u202eb</p>", "a\u200bb", 7, ["x"], {"a": 1}, True):
                    status, _ = self.send(table, field, bad)
                    self.assertEqual(status, 400, repr(bad))

    def test_markup_alone_cannot_pass_the_size_limit(self):
        for table, field, _ in FIELDS:
            with self.subTest(field):
                self.assertEqual(self.send(table, field, "<p>x</p>" * 20000)[0], 400)


    # What is sent -> what is stored. A combining mark right after a tag's '<', '>' or name (U+0338 after '>' makes U+226F, another mark makes
    # another letter) is dropped so the tag stays a tag and the words inside it survive; every other mark is composed (NFC) BEFORE the cleaner.
    COMPOSING = {
        "<p\u0338>x</p>": "<p>x</p>",
        "<p>a</p>\u0338": "<p>a</p>",
        "<p>a</p><p>b</p>\u0338": "<p>a</p><p>b</p>",
        "<p>a</p><p>\u0338text</p>": "<p>a</p><p>text</p>",
        "<p>a</p><p\u0301>text</p>": "<p>a</p><p>text</p>",
        "<ul><li\u0338>q</li></ul>": "<ul><li>q</li></ul>",
        "<p>e\u0301 &#x301;</p>": "<p>\u00e9 \u0301</p>",
        "<p>&lt;\u0338 q</p>": "<p>&lt;\u0338 q</p>",
        "x <\u0338 y": "<p>x &lt; y</p>",
        "e\u0301": "<p>\u00e9</p>",
    }

    def test_a_mark_that_composes_with_a_tag_keeps_the_words_and_the_stored_markup_clean(self):
        """NFC runs BEFORE the cleaner, and a mark that would compose into a tag does not cost the words inside it (exact stored values)."""
        for table, field, _ in FIELDS:
            with self.subTest(field):
                for sent, want in self.COMPOSING.items():
                    status, body = self.send(table, field, sent)
                    self.assertEqual(status, 200, (sent, body))
                    got = self.stored(table, field)
                    self.assertEqual(got, want, ascii(sent))
                    self.assertEqual(sanitise.rich_or_plain(got), got)
                    self.assertNotIn("\u226f", got)
                    self.assertEqual(self.published(table, field), got)

    def test_direct_call_stores_the_words_and_composes_before_the_cleaner(self):
        """Fails if NFC is moved after the cleaner (the tag becomes '<p' + U+226F), if NFC is dropped ('e' + U+0301 stays two characters), or if the mark is not dropped (the words are lost)."""
        for sent, want in self.COMPOSING.items():
            self.assertEqual(changes._rich_field(sent, 100, "long", "hidden"), want, ascii(sent))
        got = changes._rich_field("<p>a</p><p>\u0338text</p>", 100, "long", "hidden")
        self.assertEqual(sanitise.plain_text(got), "a\ntext", "the words survive")
        self.assertEqual(sanitise.plain_text(changes._rich_field("<p>e\u0301</p>", 100, "long", "hidden")), "\u00e9", "composed: one character")

    def test_the_limit_counts_the_final_stored_words_after_nfc_and_cleaning(self):
        """Issue 548: U+0344 written as an entity becomes two characters when composed (NFC), so a text at the limit can end over it. The count is of what is stored."""
        for table, field, limit in FIELDS:
            with self.subTest(field):
                status, body = self.send(table, field, "<p>" + "a" * (limit - 2) + "1&#x344;</p>")
                self.assertEqual(status, 400, "limit characters as written, limit + 1 once the mark is composed into two")
                status, body = self.send(table, field, "<p>" + "a" * (limit - 3) + "1&#x344;</p>")
                self.assertEqual(status, 200, body)
                got = self.stored(table, field)
                self.assertLessEqual(len(sanitise.plain_text(got)), limit)
                self.assertEqual(sanitise.rich_or_plain(got), got)

    def test_a_carriage_return_inside_html_is_a_line_break_not_a_hidden_character(self):
        for table, field, _ in FIELDS:
            with self.subTest(field):
                for sent in ("<p>a\rb</p>", "<p>a\r\nb</p>", "<p>a</p>\r<p>b</p>"):
                    status, body = self.send(table, field, sent)
                    self.assertEqual(status, 200, (sent, body))
                    self.assertNotIn("\r", self.stored(table, field))


class Legacy(Base):
    def test_a_legacy_plain_value_is_published_as_escaped_paragraphs(self):
        for table, field, _ in FIELDS:
            with self.subTest(field):
                self.raw_write(table, field, LEGACY)
                self.assertEqual(self.stored(table, field), LEGACY)
                self.assertEqual(self.published(table, field), LEGACY_HTML)

    def test_a_hostile_value_written_past_the_store_is_cleaned_when_published(self):
        for table, field, _ in FIELDS:
            with self.subTest(field):
                self.raw_write(table, field, HOSTILE)
                out = self.published(table, field)
                for bad in ("<script", "onclick", "onerror", "javascript:", "<img", "<style", "<iframe", "alert"):
                    self.assertNotIn(bad, out, bad)
                self.raw_write(table, field, "<script>alert(1)</script>plain <b>x</b>")      # legacy text that only looks like markup: escaped, never markup
                self.assertEqual(self.published(table, field), "<p>&lt;script&gt;alert(1)&lt;/script&gt;plain &lt;b&gt;x&lt;/b&gt;</p>")

    def test_a_new_value_is_published_clean_and_the_file_never_holds_the_raw_text(self):
        for table, field, _ in FIELDS:
            with self.subTest(field):
                self.send(table, field, "<p>Fine <em>words</em></p>")
                self.assertEqual(self.published(table, field), "<p>Fine <em>words</em></p>")
                body = publish.build(self.s, "ABC", now="2026-10-29")["body"].decode("utf-8")
                self.assertIn("Fine <em>words</em>", body.replace("\\u003c", "<").replace("\\u003e", ">"))


class PlainReaders(Base):
    def test_history_shows_the_words_of_a_legacy_and_of_a_new_value(self):
        self.assertEqual(history.shown_value("actions", "latest_update", LEGACY), sanitise.rich_plain_text(LEGACY))
        self.assertEqual(history.shown_value("actions", "latest_update", "<p>a &amp; b</p>"), "a & b")
        self.assertEqual(history.shown_value("milestones", "description", "<p>x</p><p>y</p>"), "x\ny")

    def test_the_card_words_are_the_words_of_either_kind(self):
        self.assertEqual(raid3._words({"source": "latest"}, {"latest_update": "<p>Done &amp; dusted</p>"}), "Done & dusted")
        self.assertEqual(raid3._words({"source": "latest"}, {"latest_update": "old < new"}), "old < new")

    def test_the_client_filters_read_the_words(self):
        row = client_filters._row("action", {"id": "ABC-A-001", "description": "t", "latest_update": "<p>Moved &amp; fixed</p>"}, "2026-10-29")
        self.assertEqual(row["latest_update"], "Moved & fixed")
        self.assertIn("Moved & fixed", row["_search"])
        row = client_filters._row("action", {"id": "ABC-A-001", "description": "t", "latest_update": "a < b"}, "2026-10-29")
        self.assertEqual(row["latest_update"], "a < b")


if __name__ == "__main__":
    unittest.main()
