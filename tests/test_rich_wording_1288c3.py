"""Row 1288 part c3: an item row's Client wording (actions, risks and issues, decisions) held one line of plain text and is now the one
rich editor and stores HTML. Old plain text still reads: on a save, a publish and an export it comes out as the words it always was (no markup showing,
no lost line, nothing doubled), whatever it holds (<, &, quotes, newlines, nothing, a very long text, text that already is HTML).
Sanitised when written AND again when published; the file and the Word and Excel copies carry words. Real change route, real
publish.select; every row is made up.

Run: python3 dev/run_tests.py test_rich_wording_1288c3
"""
import io
import json
import unittest
import zipfile

from _demo import USER, DemoStore
from _paths import ROOT   # noqa: F401
import _publish_fixture as fx
from clark import changes, client_filters, docx_build, excel, excel_client, history, publish, sanitise, section_bodies, store as store_module

LEGACY = 'Line one: a < b & "c" it\'s <b>not bold</b>\nLine two\n\nLine four'
LEGACY_HTML = '<p>Line one: a &lt; b &amp; "c" it\'s &lt;b&gt;not bold&lt;/b&gt;</p><p>Line two</p><p></p><p>Line four</p>'
HOSTILE = ('<p onclick="x()">hi <script>alert(1)</script><a href="javascript:alert(2)">bad</a> <img src=x onerror=alert(3)>'
           '<style>p{}</style><iframe src="https://e.example"></iframe></p>')
BAD_PARTS = ("<script", "onclick", "onerror", "javascript:", "<img", "<style", "<iframe", "alert")
TITLE = {"actions": "description", "raid": "description", "decisions": "decision"}


def rules():
    return section_bodies.Rules(plain=store_module._plain_ok, visible=store_module._visible_ok, html=None)


class Base(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store
        self.change = changes.make_change(self.s.path, [], USER)
        a = self.demo.action(description="An action", client_message="A note for the client")
        with self.s.step("dashboard", USER) as st:
            r = st.create("raid", {"project": "ABC", "type": "Risk", "description": "Supplier slips", "impact": "High", "likelihood": "Medium",
                                   "raised": "2026-10-01", "client_message": "A note for the client", "source": "demo"})
            d = st.create("decisions", {"project": "ABC", "decision": "Use the new tool", "status": "Pending", "needed_by": "2030-01-05",
                                        "client_message": "A note for the client", "source": "demo"})
        self.ref = {"actions": a, "raid": r, "decisions": d}

    def send(self, table, value):
        return self.change({"project": "ABC", "kind": table, "op": "update", "id": self.ref[table], "changes": {"client_message": value}, "place": "peek"})

    def stored(self, table):
        return self.s.read(table, ref=self.ref[table])["client_message"]

    def raw_write(self, table, value):
        with self.s.step("dashboard", USER) as st:
            st.update(table, self.ref[table], {"client_message": value})

    def inputs(self):
        return publish.read_inputs(self.s, "ABC", "2026-10-29")

    def published(self, table):
        data = publish.select(self.inputs())["data"]
        return next(r["client_message"] for r in data[table] if r["id"] == self.ref[table])


class ItemWordingWrite(Base):
    def test_the_editor_html_is_stored_clean_for_every_table(self):
        for table in self.ref:
            with self.subTest(table):
                status, body = self.send(table, "<p>Hello <strong>there</strong></p><ul><li>one</li></ul>")
                self.assertEqual(status, 200, body)
                self.assertEqual(self.stored(table), "<p>Hello <strong>there</strong></p><ul><li>one</li></ul>")

    def test_hostile_html_is_stored_cleaned(self):
        for table in self.ref:
            with self.subTest(table):
                status, body = self.send(table, HOSTILE)
                self.assertEqual(status, 200, body)
                got = self.stored(table)
                for bad in BAD_PARTS:
                    self.assertNotIn(bad, got, bad)
                self.assertIn("hi", got)

    def test_plain_text_from_an_older_caller_is_stored_as_it_always_was(self):
        for table in self.ref:
            with self.subTest(table):
                status, body = self.send(table, "Plain words, a < b & c")
                self.assertEqual(status, 200, body)
                self.assertEqual(self.stored(table), "Plain words, a < b & c")

    def test_blank_html_clears(self):
        for table in self.ref:
            for blank in ("<p></p>", "<p> </p><p><br></p>"):
                with self.subTest(table=table, blank=blank):
                    self.assertEqual(self.send(table, "<p>x</p>")[0], 200)
                    status, body = self.send(table, blank)
                    self.assertEqual(status, 200, body)
                    self.assertEqual(self.stored(table), "")

    def test_the_limit_counts_the_words_not_the_markup(self):
        limit = 200
        for table in self.ref:
            with self.subTest(table):
                self.assertEqual(self.send(table, "<p><strong>%s</strong></p>" % ("a" * limit))[0], 200)
                self.assertEqual(self.send(table, "<p><strong>%s</strong></p>" % ("a" * (limit + 1)))[0], 400)

    def test_hidden_characters_and_markup_bombs_are_refused(self):
        for table in self.ref:
            with self.subTest(table):
                for bad in ("<p>a‮b</p>", "<p>a​b</p>", "<p>x</p>" * 20000):
                    self.assertEqual(self.send(table, bad)[0], 400, repr(bad)[:40])

    def test_a_save_twice_is_the_same_value(self):
        for table in self.ref:
            with self.subTest(table):
                self.send(table, "<p>a &amp; b</p>")
                once = self.stored(table)
                self.send(table, once)
                self.assertEqual(self.stored(table), once)


class ItemWordingPublish(Base):
    def test_the_file_carries_clean_html_of_a_new_value(self):
        for table in self.ref:
            with self.subTest(table):
                self.send(table, "<p>Fine <em>words</em></p>")
                self.assertEqual(self.published(table), "<p>Fine <em>words</em></p>")

    def test_an_old_plain_value_is_published_as_escaped_paragraphs_and_stays_plain_in_the_store(self):
        for table in self.ref:
            with self.subTest(table):
                self.raw_write(table, LEGACY)
                self.assertEqual(self.stored(table), LEGACY)
                self.assertEqual(self.published(table), LEGACY_HTML)

    def test_empty_and_very_long_and_already_html_old_values(self):
        for table in self.ref:
            with self.subTest(table):
                self.raw_write(table, "")
                self.assertEqual(self.published(table), "")
                long_text = "w " * 3000
                self.raw_write(table, long_text)
                self.assertEqual(" ".join(sanitise.rich_plain_text(self.published(table)).split()), long_text.strip())
                self.raw_write(table, "<p>Already <strong>html</strong></p>")
                self.assertEqual(self.published(table), "<p>Already <strong>html</strong></p>")
                self.assertEqual(sanitise.rich_or_plain(self.published(table)), self.published(table))

    def test_a_hostile_value_written_past_the_store_is_cleaned_when_published(self):
        for table in self.ref:
            with self.subTest(table):
                self.raw_write(table, HOSTILE)
                out = self.published(table)
                for bad in BAD_PARTS:
                    self.assertNotIn(bad, out, bad)
                self.raw_write(table, "<script>alert(1)</script>plain <b>x</b>")
                self.assertEqual(self.published(table), "<p>&lt;script&gt;alert(1)&lt;/script&gt;plain &lt;b&gt;x&lt;/b&gt;</p>")

    def test_a_row_whose_wording_is_only_markup_is_a_row_with_no_wording(self):
        """Row 560: no client wording, title only: the latest update is left out. Markup with no words in it is no wording."""
        for table in ("actions", "raid"):
            with self.subTest(table):
                self.raw_write(table, "<p> </p>")
                with self.s.step("dashboard", USER) as st:
                    st.update(table, self.ref[table], {"latest_update": "<p>secret update</p>"})
                data = publish.select(self.inputs())["data"]
                row = next(r for r in data[table] if r["id"] == self.ref[table])
                self.assertFalse(row["latest_update"])

    def card_text(self, own=None, source="client"):
        card = {"id": self.ref["raid"], "source": source}
        if own is not None:
            card["own"] = own
        self.demo.plant_builtin_sections()
        with self.s.step("dashboard", USER) as st:
            sec = st.create("report_sections", {"project": "ABC", "type": "raid3", "title": "Cards", "sort_order": 999,
                                                "body": section_bodies.check("raid3", json.dumps({"v": 1, "cards": [card]}), rules())})
        got = next(s for s in publish.select(self.inputs())["sections"] if s["id"] == sec)
        return got["cards"][0]["text"]

    def test_a_card_reads_the_words_of_an_items_html_wording(self):
        """Through the real publish: the pure RAID template is handed words (as for a milestone), never the item's markup."""
        self.send("raid", "<p>Fine &amp; <em>clear</em></p><p>second</p>")
        self.assertEqual(self.card_text(), "Fine & clear\nsecond")


class ItemWordingReaders(Base):
    def test_history_filters_and_the_client_workbook_read_the_words(self):
        for table in self.ref:
            self.assertEqual(history.shown_value(table, "client_message", "<p>a &amp; b</p><p>c</p>"), "a & b\nc")
            self.assertEqual(history.shown_value(table, "client_message", LEGACY), sanitise.rich_plain_text(LEGACY))
        row = client_filters._row("action", {"id": "ABC-A-001", "description": "t", "client_message": "<p>Moved &amp; fixed</p>"}, "2026-10-29")
        self.assertIn("Moved & fixed", row["_search"])
        self.assertNotIn("<p>", row["_search"])

    def test_the_editor_export_and_the_client_workbook_are_words(self):
        for table in self.ref:
            self.assertIn((table, "client_message"), excel.RICH_WORDS)
            self.assertIn((table, "client_message"), publish.LEGACY_RICH)
            self.assertIn("client_message", publish.RICH[table])
            self.assertEqual(excel_client.value_of(table, {TITLE[table]: "t", "client_message": "<p>a &amp; b</p>"}, "client_message"), "a & b")
            self.assertEqual(excel_client.value_of(table, {TITLE[table]: "t", "client_message": "a < b"}, "client_message"), "a < b")
            self.assertEqual(excel_client.value_of(table, {TITLE[table]: "t", "client_message": "<p> </p>"}, "_words"), "t")


class WordAndExcel(unittest.TestCase):
    """The Word report and the client workbook, from the #39 plant with the three items' wording set."""

    WORDS = {"PUB-A-001": "<p>Agreed <strong>plan</strong> &amp; dates</p><ul><li>first step</li></ul>", "PUB-A-002": LEGACY}

    def plant(self, said):
        p = fx.load()
        for r in p["data"]["actions"]:
            if r["id"] in said:
                r["client_message"] = said[r["id"]]
        return p

    def text(self, data):
        z = zipfile.ZipFile(io.BytesIO(data))
        return " ".join(z.read(n).decode("utf-8", "replace") for n in z.namelist() if n.startswith("word/") and n.endswith(".xml"))

    def test_word_prints_the_words_of_a_new_and_of_an_old_wording(self):
        p = publish.select(fx.inputs(self.plant(self.WORDS)))
        data = docx_build.build(p)
        text = self.text(data)
        for words in ("Agreed", "plan", "&amp; dates", "first step", "Line two", "Line four"):
            self.assertIn(words, text)
        for markup in ("&lt;p&gt;", "&lt;strong&gt;", "&lt;ul&gt;"):
            self.assertNotIn(markup, text)
        self.assertIn("a &lt; b &amp;", text)          # the old text's own < and & are words, written as the XML needs them

    def test_the_client_workbook_has_the_words(self):
        from openpyxl import load_workbook
        p = publish.select(fx.inputs(self.plant(self.WORDS)))
        book = load_workbook(io.BytesIO(excel_client.workbook_bytes(p)))
        cells = [str(c.value) for ws in book.worksheets for row in ws.iter_rows() for c in row if c.value is not None]
        every = "\n".join(cells)
        self.assertIn("Agreed plan & dates", every.replace("\n", " "))
        self.assertIn("first step", every)
        self.assertIn("Line two", every)
        self.assertNotIn("<p>", every)
        self.assertNotIn("<strong>", every)


if __name__ == "__main__":
    unittest.main()
