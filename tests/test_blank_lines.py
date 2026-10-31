"""#84: blank lines from the editor are kept, from save to the published page.

Run: python3 dev/run_tests.py test_blank_lines
"line breaks in the editor should be respected and reflected when we're out of edit mode". The prototype
(system/prototype/selftest.js, 'empty lines are kept') writes <p>One.</p><p></p><p></p><p>Two.</p> and expects four
paragraphs with a visible gap. The prototype does not trim leading or trailing blank lines, and neither does clark.
What is tested: the cleaner keeps an empty paragraph (and one holding only a line break), keeps two as two, caps a run
(MAX_BLANK_RUN) and does so safely and fast for hostile input; the published file's data carries them; the page's styles give
an empty paragraph a height; plain text turns each one into a blank line. Every string is made up.
"""
import re
import time
import unittest

from _paths import ROOT, SRC   # noqa: F401  (puts src/ on the path)
from clark import page, publish
from clark.sanitise import MAX_BLANK_RUN, MAX_CHARS, clean_html, plain_text

import _publish_fixture as fx

BLANK = "<p></p>"


class Kept(unittest.TestCase):
    def test_an_empty_paragraph_survives(self):
        self.assertEqual(clean_html("<p>One.</p><p></p><p>Two.</p>"), "<p>One.</p><p></p><p>Two.</p>")

    def test_two_blank_lines_stay_two(self):
        text = "<p>One.</p><p></p><p></p><p>Two.</p>"
        self.assertEqual(clean_html(text), text)

    def test_a_paragraph_with_only_a_line_break_survives(self):
        text = "<p>One.</p><p><br></p><p>Two.</p>"
        self.assertEqual(clean_html(text), text)

    def test_leading_and_trailing_blank_lines_are_kept_like_the_prototype(self):
        text = "<p></p><p>One.</p><p></p>"
        self.assertEqual(clean_html(text), text)

    def test_a_paragraph_of_only_spaces_becomes_an_empty_one(self):
        self.assertEqual(clean_html("<p>a</p><p> </p><p>\n</p><p>b</p>"), "<p>a</p><p></p><p></p><p>b</p>")

    def test_a_blank_line_inside_a_list_item_or_quote_is_kept(self):
        text = "<blockquote><p>a</p><p></p><p>b</p></blockquote>"
        self.assertEqual(clean_html(text), text)

    def test_cleaning_again_changes_nothing(self):
        once = clean_html("<p>a</p>" + BLANK * 40 + "<p>b</p>")
        self.assertEqual(clean_html(once), once)


class TheRunLimit(unittest.TestCase):
    def test_the_cap_is_a_sensible_small_number(self):
        self.assertTrue(3 <= MAX_BLANK_RUN <= 10, MAX_BLANK_RUN)

    def test_a_run_up_to_the_cap_is_kept_whole(self):
        text = "<p>a</p>" + BLANK * MAX_BLANK_RUN + "<p>b</p>"
        self.assertEqual(clean_html(text), text)

    def test_a_longer_run_is_cut_to_the_cap(self):
        self.assertEqual(clean_html("<p>a</p>" + BLANK * (MAX_BLANK_RUN + 1) + "<p>b</p>"),
                         "<p>a</p>" + BLANK * MAX_BLANK_RUN + "<p>b</p>")
        self.assertEqual(clean_html("<p>a</p>" + BLANK * 500 + "<p>b</p>"), "<p>a</p>" + BLANK * MAX_BLANK_RUN + "<p>b</p>")

    def test_each_run_is_capped_on_its_own(self):
        text = "<p>a</p>" + BLANK * 30 + "<p>b</p>" + BLANK * 30 + "<p>c</p>"
        self.assertEqual(clean_html(text), "<p>a</p>" + BLANK * MAX_BLANK_RUN + "<p>b</p>" + BLANK * MAX_BLANK_RUN + "<p>c</p>")

    def test_breaks_and_spaces_count_in_the_run(self):
        mixed = "<p></p><p><br></p><p> </p>" * 20
        self.assertLessEqual(clean_html(mixed).count("<p>"), MAX_BLANK_RUN)

    def test_leading_and_trailing_runs_are_capped_too(self):
        self.assertEqual(clean_html(BLANK * 50 + "<p>a</p>" + BLANK * 50), BLANK * MAX_BLANK_RUN + "<p>a</p>" + BLANK * MAX_BLANK_RUN)

    def test_only_blank_paragraphs(self):
        self.assertEqual(clean_html(BLANK * 1000), BLANK * MAX_BLANK_RUN)

    def test_a_field_full_of_empty_paragraphs_is_fast(self):
        start = time.time()
        out = clean_html(BLANK * (MAX_CHARS // len(BLANK)))
        self.assertEqual(out, BLANK * MAX_BLANK_RUN)
        out = clean_html("<p><br></p>" * (MAX_CHARS // 11))
        self.assertLessEqual(out.count("<p>"), MAX_BLANK_RUN)
        self.assertLess(time.time() - start, 2)


class Hostile(unittest.TestCase):
    """The empty-paragraph shape widens nothing: the allow-list is the same, and blank lines are the only thing the cap touches."""

    def test_handlers_and_scripts_between_blank_lines_still_go(self):
        out = clean_html('<p>a</p><p onclick="x()"></p><script>zq()</script><p style="color:red"></p><p>b</p>')
        self.assertEqual(out, "<p>a</p><p></p><p></p><p>b</p>")

    def test_unclosed_paragraphs_are_closed_and_counted_as_blank_lines(self):
        out = clean_html("<p>a<p><p><p>b")
        self.assertEqual(out, "<p>a</p><p></p><p></p><p>b</p>")
        self.assertEqual(clean_html("<p><p>" * 1000), BLANK * MAX_BLANK_RUN)

    def test_blank_lines_hold_no_attributes_even_when_given_many(self):
        out = clean_html('<p class="x" id="y" onmouseover="z()" data-a="1"></p>' * 30)
        self.assertEqual(out, BLANK * MAX_BLANK_RUN)

    def test_nesting_does_not_hide_a_run_from_the_cap(self):
        out = clean_html("<blockquote>" + BLANK * 100 + "</blockquote>")
        self.assertEqual(out, "<blockquote>" + BLANK * MAX_BLANK_RUN + "</blockquote>")
        out = clean_html("<div><div><p></p></div></div>" * 100)
        self.assertLessEqual(out.count("<p>"), MAX_BLANK_RUN * 100)
        self.assertNotIn("<div", out)

    def test_entities_make_text_not_a_blank_paragraph_and_never_markup(self):
        self.assertEqual(clean_html("<p>&lt;/p&gt;&lt;p&gt;</p>"), "<p>&lt;/p&gt;&lt;p&gt;</p>")
        self.assertEqual(clean_html("<p>&nbsp;</p>" * 3), "<p>&nbsp;</p>" * 3, "a real space character is text, not an empty paragraph")
        self.assertEqual(clean_html("&lt;script&gt;" + BLANK * 20), "&lt;script&gt;" + BLANK * MAX_BLANK_RUN)

    def test_a_blank_run_cut_never_leaves_a_tag_open_or_text_lost(self):
        out = clean_html("<p>a</p>" + "<p></p><p><br></p>" * 30 + "<strong>b</strong>")
        self.assertTrue(out.startswith("<p>a</p>") and out.endswith("<strong>b</strong>"), out[-40:])
        self.assertEqual(out.count("<p>"), out.count("</p>") )

    def test_text_between_blank_lines_is_never_dropped(self):
        out = clean_html("".join(f"<p>line {i}</p>" + BLANK * 20 for i in range(5)))
        for i in range(5):
            self.assertIn(f"<p>line {i}</p>", out)


class Published(unittest.TestCase):
    def test_the_published_data_carries_the_blank_lines(self):
        plant = fx.load()
        plant["data"]["project"]["current_state"] = "<p>One.</p><p></p><p></p><p>Two.</p>"
        pub = publish.select(fx.inputs(plant))
        self.assertEqual(pub["data"]["project"]["current_state"], "<p>One.</p><p></p><p></p><p>Two.</p>")

    def test_a_text_section_keeps_them_too(self):
        plant = fx.load()
        sec = next(s for s in plant["sections"] if s["type"] == "text")
        sec["body"] = "<p>One.</p><p></p><p>Two.</p>"
        pub = publish.select(fx.inputs(plant))
        self.assertIn("<p>One.</p><p></p><p>Two.</p>", next(s["body"] for s in pub["sections"] if s["type"] == "text"))


class Styles(unittest.TestCase):
    def test_an_empty_paragraph_has_a_height_in_the_page(self):
        css = (SRC / "clark" / "page" / "shell.css").read_text(encoding="utf-8")
        m = re.search(r"\.prose p:empty\s*\{([^}]*)\}", css)
        self.assertTrue(m, "no rule gives an empty paragraph a height")
        self.assertRegex(m.group(1), r"min-height:\s*1\.5em")
        self.assertIn(".prose p:empty", page.PAGE.read_text(encoding="utf-8"), "the built page has the rule")


class Hardening(unittest.TestCase):
    """Reviewer LOWs on #84."""
    def test_L1_spaces_and_newlines_between_blank_lines_do_not_step_round_the_cap(self):
        for gap in ("\n", " ", "\r\n", " \t\n"):
            out = clean_html("<p>a</p>" + (BLANK + gap) * 1000 + "<p>b</p>")
            self.assertLessEqual(out.count("<p></p>"), MAX_BLANK_RUN, repr(gap))
            self.assertIn("<p>a</p>", out)
            self.assertIn("<p>b</p>", out)
            self.assertEqual(clean_html(out), out)

    def test_L1_a_short_run_with_gaps_is_untouched_and_text_is_never_lost(self):
        text = "<p>a</p>" + (BLANK + "\n") * MAX_BLANK_RUN + "<p>b</p>"
        self.assertEqual(clean_html(text), text)
        self.assertEqual(plain_text(clean_html(("<p></p> " * 50) + "<p>x</p>")).strip(), "x")

    def test_L1_a_long_gapped_run_is_fast(self):
        start = time.time()
        clean_html((BLANK + " ") * (MAX_CHARS // 8))
        clean_html((BLANK + "\n\n  \n") * (MAX_CHARS // 12) + "x")
        self.assertLess(time.time() - start, 2)
    def test_L4_a_paragraph_of_only_wide_or_invisible_spaces_is_text_not_blank(self):
        for ch in ("\u3000", "\u2003", "\u200b"):
            text = "<p>a</p>" + ("<p>%s</p>" % ch) * 7 + "<p>b</p>"
            self.assertEqual(clean_html(text), text, repr(ch))
    def test_L3_a_nbsp_only_paragraph_is_a_blank_line_in_plain_text(self):
        self.assertEqual(plain_text("<p>a</p><p>&nbsp;</p><p>b</p>"), "a\n\nb")
        self.assertEqual(plain_text("<p>a</p><p>&nbsp; &nbsp;</p><p>b</p>"), "a\n\nb")
        self.assertEqual(plain_text("<p>a&nbsp;b</p>"), "a\xa0b")
        self.assertEqual(plain_text("<p>a</p><p>\u200b</p><p>b</p>"), "a\n\u200b\nb")      # zero-width is text, not blank

    def test_L5_the_docstrings_say_what_the_cap_does_and_does_not_do(self):
        from clark import sanitise
        for doc in (sanitise.clean_html.__doc__, sanitise.plain_text.__doc__):
            self.assertIn("blank", doc.lower())
        self.assertIn("not a limit", sanitise.limit_blank_lines.__doc__)


class PlainText(unittest.TestCase):
    def test_each_blank_line_is_a_blank_line(self):
        self.assertEqual(plain_text("<p>One.</p><p></p><p>Two.</p>"), "One.\n\nTwo.")
        self.assertEqual(plain_text("<p>One.</p><p></p><p></p><p>Two.</p>"), "One.\n\n\nTwo.")
        self.assertEqual(plain_text("<p>One.</p><p><br></p><p>Two.</p>"), "One.\n\nTwo.")

    def test_leading_and_trailing_blank_lines_are_trimmed(self):
        self.assertEqual(plain_text("<p></p><p>One.</p><p></p>"), "One.")

    def test_a_long_run_is_capped(self):
        out = plain_text("<p>a</p>" + BLANK * 500 + "<p>b</p>")
        self.assertEqual(out, "a" + "\n" * (MAX_BLANK_RUN + 1) + "b")

    def test_paragraphs_without_blank_lines_are_as_before(self):
        self.assertEqual(plain_text("<p>one</p><p>two</p>"), "one\ntwo")


if __name__ == "__main__":
    unittest.main()
