"""Mutation hunt (second pass): source_name rules the earlier tests left loose, and the file: link rewrite in pdf.scrub.
Run: python3 dev/run_tests.py test_source_name_pdf_uri_mut
"""
import re
import unittest

from _paths import SRC  # noqa: F401

from clark import pdf
from clark.source_name import source_name, FILE_EXTENSIONS, CAP
from test_pdf import build_pdf

CAT = {1: b"<</Type /Catalog /Pages 2 0 R>>", 2: b"<</Type /Pages /Kids [] /Count 0>>", 3: b"<</Creator (x)>>"}


def scrubbed(uri_object):
    return pdf.scrub(build_pdf({**CAT, 4: uri_object}, info=3), "T")


class SourceNameRules(unittest.TestCase):
    def test_a_drive_letter_or_a_colon_path_is_not_plain_words(self):
        self.assertEqual(source_name("C:plan.docx"), "plan.docx")           # not plain, so only the file name goes
        self.assertEqual(source_name("C:plan"), "")
        self.assertEqual(source_name("Macintosh HD:Users:name:Folder:file.xlsx"), "file.xlsx")
        self.assertEqual(source_name("Plan: v2"), "Plan: v2")
        self.assertEqual(source_name("Plan:2"), "Plan:2")
        self.assertEqual(source_name("at 12:30"), "at 12:30")
        self.assertEqual(source_name("Plan:"), "Plan:")
        self.assertEqual(source_name("C:5"), "")                            # a drive letter, even with a digit after the colon

    def test_a_host_name_with_an_at_sign_is_no_file_name(self):
        self.assertEqual(source_name("name@host.example"), "")
        self.assertEqual(source_name("a/name@host.docx"), "")
        self.assertEqual(source_name("a/b@c/host.docx"), "host.docx")

    def test_the_published_name_is_wholly_a_file_name(self):
        pub = lambda s: source_name(s, published=True)
        self.assertEqual(pub("x, plan.docx, y"), "plan.docx")
        self.assertEqual(pub("old.xlsx, new.csv"), "new.csv")               # the last one wins
        self.assertEqual(pub("Jo. Confidential.Salary.docx"), "")           # a sentence beside a dot
        self.assertEqual(pub("Jo .Confidential.docx"), "")
        self.assertEqual(pub("notes.txt"), "")                              # not a known extension
        self.assertEqual(pub("plan.DOCX"), "plan.DOCX")
        self.assertEqual(pub(".docx"), "")                                  # no stem
        self.assertEqual(pub("/a/b/plan.docx"), "plan.docx")
        self.assertEqual(pub("/a/b/plan.txt"), "")
        self.assertEqual(pub("name@host.docx"), "")
        self.assertEqual(source_name("/a/b/plan.txt"), "plan.txt")          # the peek is not held to the list

    def test_every_listed_extension_publishes_and_the_list_is_the_known_seven(self):
        self.assertEqual(FILE_EXTENSIONS, {"xlsx", "xlsm", "xls", "csv", "docx", "doc", "pdf"})
        for ext in FILE_EXTENSIONS:
            self.assertEqual(source_name("x, a." + ext, published=True), "a." + ext)

    def test_escapes_split_by_hidden_characters_are_joined_and_decoded(self):
        self.assertEqual(source_name("a%2F​b.docx"), "b.docx")
        self.assertEqual(source_name("a%​2Fb.docx"), "b.docx")
        self.assertEqual(source_name("a%u002Fb.docx"), "b.docx")
        self.assertEqual(source_name("a%252Fb.docx"), "b.docx")             # decoded until nothing changes
        self.assertEqual(source_name("a&#47;b.docx"), "b.docx")
        self.assertEqual(source_name("a&sol;b.docx"), "b.docx")
        self.assertEqual(source_name("R&D"), "R&D")
        self.assertEqual(source_name("a%u00\u200b2Fb.docx"), "b.docx")       # a five-character escape with a hidden one inside
        self.assertEqual(source_name("a&#xzz"), "")                         # a left-over entity is never plain words
        self.assertEqual(source_name("100%"), "")

    def test_a_date_is_shown_day_first_only_when_it_is_a_real_day(self):
        self.assertEqual(source_name("on 2026-11-11"), "on 11-11-2026")
        self.assertEqual(source_name("on 2026-02-30"), "on 2026-02-30")
        self.assertEqual(source_name("on 12026-11-11"), "on 12026-11-11")
        self.assertEqual(source_name("2026-11-11-5"), "2026-11-11-5")

    def test_the_ellipsis_cut_is_exactly_at_the_cap(self):
        self.assertEqual(CAP, 120)
        self.assertEqual(source_name("a" * 120), "a" * 120)
        self.assertEqual(source_name("a" * 121), "a" * 119 + "…")
        self.assertEqual(source_name("a" * 118 + " b"), "a" * 118 + " b")
        self.assertEqual(source_name("a" * 118 + "  " + "b" * 5), "a" * 118 + "\u2026")   # two spaces become one, then the cut leaves a trailing space that goes

    def test_a_value_that_is_not_text_has_nothing(self):
        for bad in (None, 5, b"plan.docx", ["plan.docx"]):
            self.assertEqual(source_name(bad), "")


class FileUriInPdf(unittest.TestCase):
    F = b"file:///tmp/clark-pdf-ab_12/"

    def test_a_nested_relative_path_and_spacing_forms_are_kept_relative(self):
        for head in (b"/URI (", b"/URI(", b"/URI   ("):
            out = scrubbed(b"<</A <</S /URI " + head + self.F + b"a/b/c.pdf)>>>>")
            self.assertIn(b"a/b/c.pdf)", out, head)
            self.assertNotIn(b"clark-pdf-", out)
            self.assertNotIn(b"file:", out)

    def test_a_lower_case_scheme_and_an_escaped_bracket_are_still_found(self):
        out = scrubbed(b"<</A <</S /URI /URI (FILE:///tmp/clark-pdf-q/x\\)y.pdf)>>>>")
        self.assertIn(b"/URI (x\\)y.pdf)", out)
        self.assertNotIn(b"clark-pdf", out)

    def test_two_links_in_one_object_are_both_cleaned(self):
        out = scrubbed(b"<</A <</URI (" + self.F + b"a.pdf)>> /B <</URI /URI (" + self.F + b"b.pdf)>>>>")
        self.assertIn(b"(a.pdf)", out)
        self.assertIn(b"(b.pdf)", out)
        self.assertEqual(out.count(b"clark-pdf-"), 0)

    def test_a_folder_that_is_not_ours_leaves_no_address(self):
        for other in (b"file:///tmp/other-ab/x.pdf", b"file:///tmp/clark-pdfx/x.pdf", b"file:///tmp/clark-pdf-a-b/x.pdf", b"file:///tmp/clark-pdf-ab/", b"file:///tmp/xclark-pdf-ab/x.pdf"):
            out = scrubbed(b"<</A <</S /URI /URI (" + other + b")>>>>")
            self.assertIn(b"/URI ()", out, other)
            self.assertNotIn(b"file:", out)

    def test_a_link_that_is_not_a_file_link_is_untouched(self):
        for keep in (b"https://e.example/file:x", b"mailto:a@b.example", b"xfile:///tmp/clark-pdf-ab/x.pdf"):
            self.assertIn(b"(" + keep + b")", scrubbed(b"<</A <</S /URI /URI (" + keep + b")>>>>"))

    def test_the_left_over_pattern_sees_both_forms_and_only_file_links(self):
        L = pdf.FILE_URI_LEFT
        self.assertTrue(L.search(b"/URI (file:///x)"))
        self.assertTrue(L.search(b"/URI ( FILE:///x)"))
        self.assertTrue(L.search(b"/URI <" + b"file:".hex().encode() + b"2f>"))
        self.assertTrue(L.search(b"/uri < " + b"FILE:".hex().upper().encode() + b">") or L.search(b"/uri < " + b"file:".hex().encode() + b">"))
        self.assertFalse(L.search(b"/URI (https://x/file:)"))
        self.assertFalse(L.search(b"/URI <" + b"http".hex().encode() + b">"))


if __name__ == "__main__":
    unittest.main()
