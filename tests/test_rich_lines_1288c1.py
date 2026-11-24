"""Row 1288 part c1: a picture's caption (Text and image, Image with caption, Image gallery) held one line of plain text and is now the one
rich editor and stores HTML. Old plain text still reads: on a save, a publish and an export it comes out as the words it always was (no markup showing,
no lost line, nothing doubled), whatever it holds (<, &, quotes, newlines, nothing, a very long text, text that already is HTML).
Sanitised when written AND again when published; the file and the Word and Excel copies carry words. Real change route, real
publish.select, real section checkers; every row is made up.

Run: python3 dev/run_tests.py test_rich_lines_1288c1
"""
import json
import unittest

from _paths import ROOT   # noqa: F401
from clark import sanitise, section_bodies, store as store_module

LEGACY = 'Line one: a < b & "c" it\'s <b>not bold</b>\nLine two\n\nLine four'
LEGACY_HTML = '<p>Line one: a &lt; b &amp; "c" it\'s &lt;b&gt;not bold&lt;/b&gt;</p><p>Line two</p><p></p><p>Line four</p>'
HOSTILE = ('<p onclick="x()">hi <script>alert(1)</script><a href="javascript:alert(2)">bad</a> <img src=x onerror=alert(3)>'
           '<style>p{}</style><iframe src="https://e.example"></iframe></p>')
BAD_PARTS = ("<script", "onclick", "onerror", "javascript:", "<img", "<style", "<iframe", "alert")


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


# ---- picture captions ----------------------------------------------------------------------

PIC = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="


def check(kind, value):
    return json.loads(section_bodies.check(kind, json.dumps(value), rules()))


def published(kind, value, ctx=None):
    return section_bodies.published(kind, value, ctx)


def textimage(caption):
    return {"words": ["x"], "caption": caption, "pictures": {"image": PIC}}


def imagecap(caption):
    return {"v": 1, "caption": caption, "pictures": {"image": PIC}}


def gallery(caption):
    return {"v": 1, "items": {"1": {"caption": caption}}, "pictures": {"1": PIC}}


# kind, body maker, where the line is in the stored body, where the file carries it
LINES = (("textimage", textimage, lambda v: v["caption"], lambda c: c["content"]["caption"]),
         ("imagecap", imagecap, lambda v: v["caption"], lambda c: c["content"]["caption"]),
         ("gallery", gallery, lambda v: v["items"]["1"]["caption"], lambda c: c["content"]["pictures"][0]["caption"]))


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
            limit = 300
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
        self.assertEqual(set(section_bodies.RICH_LINES), {"textimage", "imagecap", "gallery"})


if __name__ == "__main__":
    unittest.main()
