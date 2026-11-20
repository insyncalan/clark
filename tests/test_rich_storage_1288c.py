"""Row 1288 part c: three places that held one line of plain text become the one rich editor and store HTML: an item row's Client
wording (actions, risks and issues, decisions), a picture's caption (Text and image, Image with caption, Image gallery) and a RAID card's
own words. Old plain text still reads: on a save, a publish and an export it comes out as the words it always was (no markup showing,
no lost line, nothing doubled), whatever it holds (<, &, quotes, newlines, nothing, a very long text, text that already is HTML).
Sanitised when written AND again when published; the file and the Word and Excel copies carry words. Real change route, real
publish.select, real section checkers; every row is made up.

Run: python3 dev/run_tests.py test_rich_storage_1288c
"""
import copy
import io
import json
import unittest
import zipfile

from _demo import USER, DemoStore
from _paths import ROOT   # noqa: F401
import _publish_fixture as fx
from clark import changes, client_filters, docx_build, excel, excel_client, history, publish, sanitise, section_bodies, store as store_module
from clark.section_kinds import raid3, raid4

LEGACY = 'Line one: a < b & "c" it\'s <b>not bold</b>\nLine two\n\nLine four'
LEGACY_HTML = '<p>Line one: a &lt; b &amp; "c" it\'s &lt;b&gt;not bold&lt;/b&gt;</p><p>Line two</p><p></p><p>Line four</p>'
HOSTILE = ('<p onclick="x()">hi <script>alert(1)</script><a href="javascript:alert(2)">bad</a> <img src=x onerror=alert(3)>'
           '<style>p{}</style><iframe src="https://e.example"></iframe></p>')
BAD_PARTS = ("<script", "onclick", "onerror", "javascript:", "<img", "<style", "<iframe", "alert")
TITLE = {"actions": "description", "raid": "description", "decisions": "decision"}


def rules():
    return section_bodies.Rules(plain=store_module._plain_ok, visible=store_module._visible_ok, html=None)


class Flat(unittest.TestCase):
    """sanitise.flat_line: the words of a stored rich-or-plain value on ONE line, as text (never markup)."""

    def test_words_on_one_line(self):
        self.assertEqual(sanitise.flat_line("<p>a</p><p>b  c</p>"), "a b c")
        self.assertEqual(sanitise.flat_line("<ul><li>x</li><li>y</li></ul>"), "x y")

    def test_text_is_text_not_entities(self):
        self.assertEqual(sanitise.flat_line("<p>a &lt; b &amp; c</p>"), "a < b & c")
        self.assertEqual(sanitise.flat_line("a < b & c"), "a < b & c")

    def test_legacy_plain_gives_its_words(self):
        self.assertEqual(sanitise.flat_line(LEGACY), 'Line one: a < b & "c" it\'s <b>not bold</b> Line two Line four')

    def test_nothing_gives_nothing(self):
        for v in (None, "", "   ", "\n\n", "<p></p>", "<p> </p><p><br></p>"):
            self.assertEqual(sanitise.flat_line(v), "", repr(v))

    def test_hostile_markup_is_never_in_the_words(self):
        got = sanitise.flat_line(HOSTILE)
        for bad in ("<script", "onclick", "<img", "<iframe", "<style", "javascript:"):
            self.assertNotIn(bad, got)
        self.assertIn("hi", got)

    def test_very_long_text_loses_nothing(self):
        text = "word " * 5000
        self.assertEqual(sanitise.flat_line(text), text.strip())

    def test_idempotent(self):
        for v in (LEGACY, HOSTILE, "<p>x</p>", "a < b"):
            once = sanitise.flat_line(v)
            self.assertEqual(sanitise.flat_line(once), once, repr(v))


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
                self.assertEqual(sanitise.flat_line(self.published(table)), long_text.strip())
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

    def test_a_card_reads_the_words_of_an_items_html_wording_and_of_its_own_html_words(self):
        """Through the real publish: the pure RAID template is handed words (as for a milestone), never the item's markup."""
        self.send("raid", "<p>Fine &amp; <em>clear</em></p><p>second</p>")
        self.assertEqual(self.card_text(), "Fine & clear\nsecond")
        self.assertEqual(self.card_text("<p>Own <strong>words</strong> &amp; more</p>", "own"), "Own words & more")


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


# ---- picture captions and a RAID card's own words ----------------------------------------------------------------------

PIC = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="


def check(kind, value):
    return json.loads(section_bodies.check(kind, json.dumps(value), rules()))


def published(kind, value, ctx=None):
    return section_bodies.published(kind, value, ctx)


def card(own, id="ABC-001"):
    return {"v": 1, "cards": [{"id": id, "source": "own", "own": own}]}


def textimage(caption):
    return {"words": ["x"], "caption": caption, "pictures": {"image": PIC}}


def imagecap(caption):
    return {"v": 1, "caption": caption, "pictures": {"image": PIC}}


def gallery(caption):
    return {"v": 1, "items": {"1": {"caption": caption}}, "pictures": {"1": PIC}}


# kind, body maker, where the line is in the stored body, where the file carries it
LINES = (("textimage", textimage, lambda v: v["caption"], lambda c: c["content"]["caption"]),
         ("imagecap", imagecap, lambda v: v["caption"], lambda c: c["content"]["caption"]),
         ("gallery", gallery, lambda v: v["items"]["1"]["caption"], lambda c: c["content"]["pictures"][0]["caption"]),
         ("raid3", card, lambda v: v["cards"][0]["own"], lambda c: c["cards"][0]["text"]),
         ("raid4", card, lambda v: v["cards"][0]["own"], lambda c: c["cards"][0]["text"]))


class RichLines(unittest.TestCase):
    def ctx(self):
        return section_bodies.Context({"raid": [{"id": "ABC-001", "description": "t", "client_message": ""}]})

    def stored(self, kind, make, where, text):
        return where(check(kind, make(text)))

    def test_html_is_stored_clean(self):
        for kind, make, where, _ in LINES:
            with self.subTest(kind):
                self.assertEqual(self.stored(kind, make, where, "<p>Hello <strong>there</strong></p>"), "<p>Hello <strong>there</strong></p>")

    def test_old_plain_text_is_stored_as_it_was_and_read_as_the_same_words(self):
        for kind, make, where, file_of in LINES:
            for plain in ("a < b & c", 'say "hi" it\'s', "x", "Fictional plan"):
                with self.subTest(kind=kind, plain=plain):
                    self.assertEqual(self.stored(kind, make, where, plain), plain)
                    self.assertEqual(file_of(published(kind, make(plain), self.ctx())), plain)

    def test_text_that_looks_like_markup_is_html_and_cleaned(self):
        for kind, make, where, _ in LINES:
            with self.subTest(kind=kind):
                got = self.stored(kind, make, where, "<p>half")
                self.assertEqual(got, "<p>half</p>")
                self.assertEqual(self.stored(kind, make, where, got), got, "saved again it is the same")
                self.assertEqual(self.stored(kind, make, where, "<b>not a block</b>"), "<b>not a block</b>")

    @staticmethod
    def html_of(n):
        """Clean HTML of exactly n characters, with few enough words for every limit."""
        return "<p>" + "<em>a</em>" * 190 + "a" * (n - 7 - 10 * 190) + "</p>"

    def test_the_html_limit_is_2000_characters_on_a_save_and_a_publish_leaves_a_longer_one_out(self):
        for kind, make, where, file_of in LINES:
            with self.subTest(kind):
                self.assertEqual(len(self.stored(kind, make, where, self.html_of(2000))), 2000, "2000 is kept")
                self.assertTrue(file_of(published(kind, make(self.html_of(2000)), self.ctx())), "and published")
                with self.assertRaises(section_bodies.Bad):
                    check(kind, make(self.html_of(2001)))
                self.assertEqual(file_of(published(kind, make(self.html_of(2001)), self.ctx())), "", "one over is left out of the file, not shown as markup")

    def test_a_text_too_big_to_clean_is_refused_on_a_save_and_left_out_of_a_publish(self):
        big = "<p>" + "a" * (sanitise.MAX_CHARS + 1) + "</p>"
        for kind, make, where, file_of in LINES:
            with self.subTest(kind):
                with self.assertRaises(section_bodies.Bad):
                    check(kind, make(big))
                self.assertEqual(file_of(published(kind, make(big), self.ctx())), "")

    def test_hostile_html_is_stored_cleaned(self):
        for kind, make, where, _ in LINES:
            with self.subTest(kind):
                got = self.stored(kind, make, where, HOSTILE)
                for bad in BAD_PARTS:
                    self.assertNotIn(bad, got, bad)

    def test_the_limit_counts_the_words_not_the_markup(self):
        for kind, make, where, _ in LINES:
            limit = raid3.OWN_MAX if kind.startswith("raid") else 300
            with self.subTest(kind):
                self.assertTrue(self.stored(kind, make, where, "<p><strong>%s</strong></p>" % ("a" * limit)))
                with self.assertRaises(section_bodies.Bad):
                    check(kind, make("<p><strong>%s</strong></p>" % ("a" * (limit + 1))))

    def test_paragraphs_in_a_one_line_place_become_one_line_of_words(self):
        for kind, make, where, _ in LINES:
            with self.subTest(kind):
                got = self.stored(kind, make, where, "<p>one</p><p>two</p><ul><li>three</li></ul>")
                self.assertEqual(sanitise.flat_line(got), "one two three")

    def test_blank_html_is_no_text(self):
        for kind, make, where, _ in LINES:
            for blank in ("", "<p></p>", "<p> </p><p><br></p>"):
                with self.subTest(kind=kind, blank=blank):
                    out = check(kind, make(blank))
                    with self.assertRaises((KeyError, IndexError)):
                        where(out)

    def test_hidden_characters_are_refused(self):
        for kind, make, where, _ in LINES:
            with self.subTest(kind):
                for bad in ("<p>a‮b</p>", "a​b"):
                    with self.assertRaises(section_bodies.Bad):
                        check(kind, make(bad))

    def test_a_markup_bomb_is_refused(self):
        for kind, make, where, _ in LINES:
            with self.subTest(kind):
                with self.assertRaises(section_bodies.Bad):
                    check(kind, make("<p>x</p>" * 2000))

    def test_the_file_carries_the_words_on_one_line_never_markup(self):
        for kind, make, where, file_of in LINES:
            with self.subTest(kind):
                stored = json.loads(section_bodies.check(kind, json.dumps(make("<p>Fine &amp; <em>clear</em></p><p>two</p>")), rules()))
                self.assertEqual(file_of(published(kind, stored, self.ctx())), "Fine & clear two")

    def test_an_old_plain_text_is_published_as_its_words_even_if_never_re_saved(self):
        for kind, make, where, file_of in LINES:
            with self.subTest(kind):
                self.assertEqual(file_of(published(kind, make("a < b & c \"q\""), self.ctx())), 'a < b & c "q"')

    def test_a_hostile_stored_value_is_cleaned_again_at_publish(self):
        for kind, make, where, file_of in LINES:
            with self.subTest(kind):
                got = file_of(published(kind, make(HOSTILE), self.ctx()))
                for bad in BAD_PARTS:
                    self.assertNotIn(bad, got, bad)
                self.assertIn("hi", got)

    def test_a_stored_value_that_cannot_be_cleaned_is_left_out_not_the_whole_section(self):
        for kind, make, where, file_of in LINES:
            with self.subTest(kind):
                got = published(kind, make("<p>x</p>" * 400000), self.ctx())
                self.assertTrue(got is None or not file_of(got))

    def test_a_text_that_is_not_text_is_refused(self):
        for kind, make, where, _ in LINES:
            with self.subTest(kind):
                for bad in (7, ["x"], {"a": 1}):
                    with self.assertRaises(section_bodies.Bad):
                        check(kind, make(bad))


class Overlaps(unittest.TestCase):
    def test_the_other_rich_keys_are_kept(self):
        self.assertEqual(section_bodies.RICH_KEYS["textimage"], ("html",))

    def test_each_place_is_listed(self):
        self.assertEqual(set(section_bodies.RICH_LINES), {"textimage", "imagecap", "gallery", "raid3", "raid4"})


if __name__ == "__main__":
    unittest.main()
