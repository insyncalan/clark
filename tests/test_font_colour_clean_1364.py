"""Row 1364: the rich-text cleaners keep ONE span, with one of six fixed colour classes, and nothing else; the four copies agree.

Run: python3 dev/run_tests.py test_font_colour_clean_1364
Covers: sanitise.clean_html, the publish cleaner and the page's cleanHtml.js / richHtml.js sources (the byte-for-byte parity of cleanHtml with
sanitise is test_clean_html_parity, which carries the span cases too).
"""
import re
import unittest

from _paths import ROOT

from clark import publish, sanitise

NAMES = ("grey", "brand", "red", "amber", "green", "blue")
PAGE = ROOT / "src" / "clark" / "page" / "src"


def span(name, words="x"):
    return f'<p><span class="rt-c-{name}">{words}</span></p>'


class Sanitise(unittest.TestCase):
    def test_each_of_the_six_classes_is_kept_exactly(self):
        for n in NAMES:
            with self.subTest(n):
                self.assertEqual(sanitise.clean_html(span(n)), span(n))

    def test_the_set_is_these_six_and_no_other(self):
        self.assertEqual(sanitise.FONT_COLOURS, NAMES)
        self.assertEqual(sanitise.COLOUR_CLASSES, {f"rt-c-{n}" for n in NAMES})

    def test_any_other_span_is_only_its_words(self):
        for bad in ('<span>x</span>', '<span class="rt-c-pink">x</span>', '<span class="rt-c-red other">x</span>', '<span class="RT-C-RED">x</span>',
                    '<span class=" rt-c-red">x</span>', '<span class="">x</span>', '<span class>x</span>', '<span style="color:red">x</span>',
                    '<span style="color:#ff0000">x</span>', '<span id="a" class="x">x</span>', '<span class="chip" contenteditable="false">x</span>'):
            with self.subTest(bad):
                self.assertEqual(sanitise.clean_html(f"<p>{bad}</p>"), "<p>x</p>")

    def test_a_style_or_other_attribute_on_a_good_span_is_dropped(self):
        self.assertEqual(sanitise.clean_html('<p><span style="color:#f00" class="rt-c-red" onclick="x()" id="a">x</span></p>'), span("red"))

    def test_no_hex_colour_ever_survives(self):
        out = sanitise.clean_html('<p><span style="color:#ff0000">a</span><font color="#00ff00">b</font><span class="rt-c-red" style="color:#0000ff">c</span></p>')
        self.assertNotIn("#", out)
        self.assertNotIn("style", out)
        self.assertNotIn("color", out.replace("rt-c-", ""))

    def test_the_colour_nests_with_bold_link_and_cleaning_again_changes_nothing(self):
        for html in ('<p><span class="rt-c-green"><strong>a</strong> b</span></p>',
                     '<p><a href="https://example.com" rel="noopener noreferrer"><span class="rt-c-blue"><em>a</em></span></a></p>',
                     '<ul><li><p>a <span class="rt-c-amber">b</span></p></li></ul>', '<h2><span class="rt-c-brand">Head</span></h2>'):
            with self.subTest(html):
                once = sanitise.clean_html(html)
                self.assertEqual(once, html)
                self.assertEqual(sanitise.clean_html(once), once)

    def test_a_span_across_paragraphs_closes_where_a_browser_would(self):
        self.assertEqual(sanitise.clean_html('<p><span class="rt-c-red">a<p>b</span>'), '<p><span class="rt-c-red">a</span></p><p>b</p>')

    def test_the_words_of_a_coloured_span_read_as_plain_text(self):
        self.assertEqual(sanitise.plain_text(f'<p>a {span("red", "b")[3:-4]} c</p>'), "a b c")


class PublishCleaner(unittest.TestCase):
    def test_the_six_classes_survive_and_a_style_or_other_class_does_not(self):
        for n in NAMES:
            self.assertEqual(publish.clean_html(span(n)), span(n))
        self.assertEqual(publish.clean_html('<p><span class="rt-c-red" style="color:#f00">x</span></p>'), span("red"))
        self.assertEqual(publish.clean_html('<p><span class="rt-c-pink" style="color:#f00">x</span></p>'), "<p><span>x</span></p>")
        self.assertEqual(publish.clean_html('<p><span class="rt-c-red other">x</span></p>'), "<p><span>x</span></p>")
        self.assertNotIn("#", publish.clean_html('<p><span style="color:#f00">x</span></p>'))


class FourCopies(unittest.TestCase):
    """sanitise.py, publish.py (which reads sanitise's set), cleanHtml.js and richHtml.js (which reads cleanHtml's set) name the same six."""

    def test_the_page_cleaner_lists_the_same_names_in_the_same_order(self):
        js = (PAGE / "logic" / "cleanHtml.js").read_text(encoding="utf-8")
        m = re.search(r"export const FONT_COLOURS = \[([^\]]*)\]", js)
        self.assertIsNotNone(m)
        self.assertEqual(re.findall(r'"(\w+)"', m.group(1)), list(sanitise.FONT_COLOURS))
        self.assertIn('`rt-c-${c}`', js)

    def test_the_editor_writer_and_the_mark_use_that_one_list(self):
        self.assertIn("FONT_COLOURS.includes(c)", (PAGE / "core" / "richHtml.js").read_text(encoding="utf-8"))
        mark = (PAGE / "core" / "fontColour.js").read_text(encoding="utf-8")
        self.assertIn('import { FONT_COLOURS } from "../logic/cleanHtml.js"', mark)
        self.assertEqual(re.findall(r'\["(\w+)", "(\w+)"\]', mark.split("SWATCHES = ")[1].split("\n")[0]),
                         [("grey", "Grey"), ("brand", "Brand"), ("red", "Red"), ("amber", "Amber"), ("green", "Green"), ("blue", "Blue")])

    def test_publish_reads_the_class_set_from_the_sanitiser(self):
        self.assertIn("sanitise.COLOUR_CLASSES", (ROOT / "src" / "clark" / "publish.py").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
