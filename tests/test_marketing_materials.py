"""The marketing files (#706 overview, #707 getting started): they are all there, they open, they are the size they say, the words are plain.

Only the committed files are checked. Nothing here starts Chrome: dev/tools/marketing_pdf.py makes the PDFs and the PNG from the two
HTML files, and is run by hand when the words or the look change. No PDF library is used: a page is counted by reading the PDF's own
page objects (and the /Count of its page tree, which must agree).

Run: python3 dev/run_tests.py test_marketing_materials
"""
import html
import re
import struct
import unittest

from _paths import ROOT
from test_no_real_names import banned_across, banned_in

FOLDER = ROOT / "docs" / "marketing"
OVERVIEW_HTML = FOLDER / "clark-overview.html"
OVERVIEW_PDF = FOLDER / "clark-overview.pdf"
OVERVIEW_PNG = FOLDER / "clark-overview.png"
START_HTML = FOLDER / "clark-getting-started.html"
START_PDF = FOLDER / "clark-getting-started.pdf"
MB = 1024 * 1024

# The words the project does not use in text a person reads (the list tests/test_help_navigation.py keeps for Help, with "refused").
BANNED_WORDS = re.compile(r"(?i)\b(apply|applied|applies|applying|staged|staging|proposal|proposals|sweep|tracker|trackers|vault|"
                          r"extract|extracted|extracts|refused|refuse|refuses|AI)\b|Draft with|Claude|ChatGPT")
ISO_DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
NEEDS_ONLY_MAC = re.compile(r"(?i)\b(windows|linux)\b")


def pdf_pages(path):
    """(page objects, the /Count of the page tree) read from the file's own bytes."""
    data = path.read_bytes()
    objects = len(re.findall(rb"/Type\s*/Page(?![s\w])", data))
    counts = [int(n) for n in re.findall(rb"/Type\s*/Pages\b[^>]*?/Count\s+(\d+)", data)] or \
             [int(n) for n in re.findall(rb"/Count\s+(\d+)", data)]
    return objects, max(counts) if counts else 0


def words_of(path):
    """The text a reader sees in an HTML file: no style, no tags, entities read."""
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"(?s)<style.*?</style>|<script.*?</script>", " ", text)
    return html.unescape(re.sub(r"<[^>]+>", " ", text))


def alt_texts(path):
    return [html.unescape(a) for a in re.findall(r'\balt="([^"]*)"', path.read_text(encoding="utf-8"))]


class Files(unittest.TestCase):
    def test_every_file_is_there(self):
        for f in (OVERVIEW_HTML, OVERVIEW_PDF, OVERVIEW_PNG, START_HTML, START_PDF, ROOT / "dev" / "tools" / "marketing_pdf.py"):
            self.assertTrue(f.is_file(), f.name)

    def test_every_picture_the_pages_name_is_there(self):
        for page in (OVERVIEW_HTML, START_HTML):
            source = page.read_text(encoding="utf-8")
            named = set(re.findall(r'src="([^"]+)"', source)) | set(re.findall(r"url\(([^)]+)\)", source))
            self.assertTrue(named, page.name)
            for name in named:
                self.assertFalse(re.match(r"(?i)(https?:|//|data:)", name), "%s fetches or embeds %s" % (page.name, name[:30]))
                self.assertTrue((FOLDER / name).is_file(), "%s names %s" % (page.name, name))

    def test_the_pages_fetch_nothing(self):
        for page in (OVERVIEW_HTML, START_HTML):
            source = page.read_text(encoding="utf-8")
            self.assertNotRegex(source, r"(?i)<link|@import|<script|@font-face")
            self.assertNotRegex(source, r"https?://(?!localhost)")
            self.assertNotIn("branding", source.lower())      # the client's own brand is never used


class Pdfs(unittest.TestCase):
    def test_the_pdfs_open(self):
        for f in (OVERVIEW_PDF, START_PDF):
            data = f.read_bytes()
            self.assertTrue(data.startswith(b"%PDF-"), f.name)
            self.assertIn(b"%%EOF", data[-1024:], f.name)

    def test_the_overview_is_exactly_one_page(self):
        self.assertEqual(pdf_pages(OVERVIEW_PDF), (1, 1))

    def test_the_getting_started_pdf_has_the_pages_it_says(self):
        objects, counted = pdf_pages(START_PDF)
        self.assertEqual(objects, counted)
        self.assertTrue(5 <= objects <= 8, objects)
        text = words_of(START_HTML)
        pages = [int(n) for n in re.findall(r"page (\d+)", re.search(r"Contents:[^\n]*", text).group(0))]
        self.assertTrue(pages and max(pages) <= objects and min(pages) == 1, pages)
        self.assertRegex(START_HTML.read_text(encoding="utf-8"), r"counter\(page\)")      # the numbers on each page

    def test_both_are_a4(self):
        for f in (OVERVIEW_PDF, START_PDF):
            box = re.search(rb"/MediaBox\s*\[\s*0\s+0\s+([\d.]+)\s+([\d.]+)\s*\]", f.read_bytes())
            self.assertIsNotNone(box, f.name)
            self.assertAlmostEqual(float(box.group(1)), 595, delta=2)
            self.assertAlmostEqual(float(box.group(2)), 842, delta=2)

    def test_the_overview_png_is_two_times_a4(self):
        data = OVERVIEW_PNG.read_bytes()
        self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(struct.unpack(">II", data[16:24]), (2480, 3508))


class Sizes(unittest.TestCase):
    def test_the_files_stay_small(self):
        self.assertLess(OVERVIEW_PDF.stat().st_size, 1.5 * MB)
        self.assertLess(START_PDF.stat().st_size, 6 * MB)
        self.assertLess(OVERVIEW_PNG.stat().st_size, 1.5 * MB)


class Words(unittest.TestCase):
    def test_no_banned_word(self):
        for page in (OVERVIEW_HTML, START_HTML):
            text = words_of(page)
            self.assertEqual([m.group(0) for m in BANNED_WORDS.finditer(text)], [], page.name)

    def test_no_person_name(self):
        for page in (OVERVIEW_HTML, START_HTML):
            text = page.read_text(encoding="utf-8")
            self.assertEqual(banned_in(text), [], page.name)
            self.assertFalse(banned_across(text), page.name)

    def test_no_date_in_iso_form(self):
        for page in (OVERVIEW_HTML, START_HTML):
            self.assertEqual(ISO_DATE.findall(words_of(page)), [], page.name)

    def test_the_picture_descriptions_are_plain_too(self):
        for page in (OVERVIEW_HTML, START_HTML):
            for alt in alt_texts(page):
                self.assertIsNone(BANNED_WORDS.search(alt), alt)
                self.assertIsNone(ISO_DATE.search(alt), alt)

    def test_nothing_is_promised_that_is_not_shipped(self):
        for page in (OVERVIEW_HTML, START_HTML):
            text = words_of(page)
            for line in re.split(r"(?<=[.!?])\s+", text):
                if NEEDS_ONLY_MAC.search(line):
                    self.assertRegex(line, r"(?i)later", line)       # Windows and Linux only ever as "come later"
            self.assertNotRegex(text, r"(?i)\b(sign in with|connect (to )?(chatgpt|claude)|update(s)? (clark )?from inside)\b")
            self.assertNotRegex(text, r"\b(20\d\d|Q[1-4])\b")       # no year, no quarter: no dates are promised


if __name__ == "__main__":
    unittest.main()
