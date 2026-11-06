"""Row 815: the brand scan ends a CSS string at CR and FF as well as LF (CSS reads CR, CRLF and FF as a newline, and a string
left open ends at an unescaped newline). A later image-set or src string address, url(), or @import must not hide behind it.

Run: python3 dev/run_tests.py test_publish_brand_cr_ff
Hosts are invented (example.invalid). The same text goes through a style block, a brand tokens.css (page.page_html) and the page.
"""
import tempfile
import unittest
from pathlib import Path

from _paths import ROOT, SRC, TOOLS  # noqa: F401

from clark import page, publish  # noqa: E402
from clark.publish import PublishError  # noqa: E402

ENDS = {"CR": "\r", "FF": "\f", "CRLF": "\r\n", "LF": "\n"}
BAD = {
    "image-set string": ('a{background:image-set("http://example.invalid/a.png" 1x)}', publish.ADDRESS_FOUND),
    "src string": ("a{background:src('//example.invalid/a.png')}", publish.ADDRESS_FOUND),
    "image-set url": ("a{background:image-set(url(http://example.invalid/a.png) 1x)}", publish.ADDRESS_FOUND),
    "src url": ("a{background:src(url(http://example.invalid/a.png))}", publish.ADDRESS_FOUND),
    "url": ("a{background:url(//example.invalid/a.png)}", publish.ADDRESS_FOUND),
    "import": ("@import 'http://example.invalid/a.css';", publish.IMPORT_FOUND),
}
OPEN = ('a{content:"x', "a{content:'x")
SENTENCE = {publish.IMPORT_FOUND: "uses @import", publish.ADDRESS_FOUND: "names a font or image by address"}


class Cases(unittest.TestCase):
    def three_ways(self, css, wide=True):
        """The css as a style block, as a brand tokens.css layered into the real page, and spliced into the page's own style.
        (wide=False: the style block alone; building the page takes about a second.) A tokens.css is built into the page with its
        comments cut out, so what the scan reads there is what the browser reads: the comment cases are the style block's and the page's."""
        yield "style", "<style>" + css + "</style>"
        if not wide:
            return
        if "/*" not in css:
            with tempfile.TemporaryDirectory() as tmp:
                with open(Path(tmp) / "tokens.css", "w", encoding="utf-8", newline="") as fh:      # Python 3.9: Path.write_text has no newline argument before 3.10
                    fh.write(css)
                yield "tokens", page.page_html(tmp)
        html = page.PAGE.read_text(encoding="utf-8")
        yield "page", html.replace("</style>", css + "\n</style>", 1)

    def refuse(self, css, found, wide=True):
        for how, text in self.three_ways(css, wide):
            with self.subTest(how=how, css=css):
                with self.assertRaises(PublishError) as ctx:
                    publish.check_brand(text)
                self.assertIn(SENTENCE[found], str(ctx.exception))

    def test_an_open_string_ended_by_cr_ff_or_crlf_does_not_hide_a_later_address(self):
        for opener in OPEN:
            for end_name, end in ENDS.items():
                for name, (tail, found) in BAD.items():
                        self.refuse(opener + end + tail, found, wide=(name in ("image-set string", "import") and opener[-2] == "\""))
                        self.refuse(opener + end + tail, found)

    def test_the_scan_pieces_stop_at_cr_and_ff(self):
        for end in ("\r", "\f"):
            css = 'a{content:"x' + end + 'image-set("http://example.invalid/a" 1x)}'
            self.assertIn(publish.ADDRESS_FOUND, publish.css_findings(css))

    def test_closed_strings_crlf_files_and_ff_in_a_comment_are_published(self):
        good = [
            'a{content:"x";\r\n color:red}\r\n b{content:\'y\'}\r\n',
            'a{content:"x"}\f b{color:red}',
            '/* a\fcomment\r\n */ a{color:red}\r\n',
            ':root{--n:"a b";--m:\'c\'}\r\n@font-face{font-family:F;src:url(data:font/woff2;base64,AAAA)}\r\n',
            'a{background:image-set("data:image/png;base64,AAAA" 1x)}'.replace("image-set(", "x(") + "\r\n",
        ]
        for css in good:
            for how, text in self.three_ways(css):
                with self.subTest(how=how, css=css):
                    publish.check_brand(text)

    def test_an_open_string_ended_by_cr_still_leaves_a_data_url_alone(self):
        for end in ("\r", "\f", "\r\n"):
            css = 'a{content:"x' + end + '}@font-face{font-family:F;src:url(data:font/woff2;base64,AAAA)}'
            for how, text in self.three_ways(css):
                with self.subTest(how=how, end=repr(end)):
                    publish.check_brand(text)

    def test_an_open_string_ended_by_cr_or_ff_does_not_hide_an_embedded_picture(self):
        for opener in OPEN:
            for end in ("\r", "\f", "\r\n"):
                css = opener + end + 'b{background:image-set("data:image/png;base64,AAAA" 1x)}'
                for how, text in self.three_ways(css):
                    with self.subTest(how=how, css=css):
                        with self.assertRaises(PublishError) as ctx:
                            publish.check_brand(text)
                        self.assertIn("embeds a picture in its style", str(ctx.exception))

    def tails(self, q):
        return {
            "url": "url(//example.invalid/a)",
            "import": "@import %s//example.invalid/a%s;" % (q, q),
            "image-set": "image-set(%s//example.invalid/a%s 1x)" % (q, q),
        }

    def found_for(self, name):
        return publish.IMPORT_FOUND if name == "import" else publish.ADDRESS_FOUND

    def test_family_1_cr_and_ff_end_a_string_for_the_comment_cutter_too(self):
        # a string opened before the line end, a quote inside a later string that is no comment, and a real address between them
        for end_name, end in ENDS.items():
            for q in ('"', "'"):
                for name, tail in self.tails(q).items():
                    wide = q == '"' and name == "image-set" and end_name in ("CR", "FF")
                    with self.subTest(end=end_name, q=q, tail=name):
                        self.refuse("a{x:%s%s} b{y:%s/*%s} c{background:%s} d{z:%s*/%s}" % (q, end, q, q, tail, q, q), self.found_for(name), wide)
                        self.refuse("a{x:%s%s%s /* %s %s /* */}" % (q, end, q, q, tail), self.found_for(name), wide)

    def test_family_2_a_comment_is_a_break_between_tokens(self):
        for end_name, end in ENDS.items():
            for q in ('"', "'"):
                for name, tail in self.tails(q).items():
                    wide = q == '"' and name == "image-set" and end_name in ("CR", "FF")
                    with self.subTest(end=end_name, q=q, tail=name):
                        self.refuse("a{background:red%s/**/%s}" % (end, tail), self.found_for(name), wide)
                        self.refuse("a{background:red/**/%s}" % tail, self.found_for(name), wide)
                        self.refuse("a{background:no-repeat/**/src(%s//example.invalid/a%s)}" % (q, q), publish.ADDRESS_FOUND, wide)
                        self.refuse("a{background:u/**/rl(src(/**/%s//example.invalid/a%s)}" % (q, q), publish.ADDRESS_FOUND, wide)

    def test_family_3_an_escape_never_turns_into_a_quote_or_a_line_end(self):
        for end_name, end in ENDS.items():
            for q in ('"', "'"):
                for name, tail in self.tails(q).items():
                    wide = q == '"' and name == "image-set" and end_name in ("CR", "FF")
                    for esc in ("\\27", "\\22", "\\27 ", "\\000022"):
                        with self.subTest(end=end_name, q=q, tail=name, esc=esc):
                            self.refuse("a{b:%s%s;background:%s}" % (esc, end, tail), self.found_for(name), wide)
                            self.refuse("a{b:x%s%sy;background:%s}" % (esc, end, tail), self.found_for(name), wide)
                    with self.subTest(end=end_name, q=q, tail=name, kind="other escapes"):
                        self.refuse("a{b:\\%s;background:%s}" % (q, tail), self.found_for(name), wide)            # an escaped quote outside a string
                        self.refuse("a{b:%s\\a %s;background:%s}" % (q, q, tail), self.found_for(name), wide)      # an escaped line end inside one
                        self.refuse("a{b:%s\\\\%s;background:%s}" % (q, q, tail), self.found_for(name), wide)      # an escaped backslash
                        self.refuse("a{b:red\\%s;background:%s}" % (end, tail), self.found_for(name), wide)       # backslash, line end, outside a string
                        self.refuse("a{background:red\\%simage-set(%s//example.invalid/a%s 1x)}" % (end, q, q), publish.ADDRESS_FOUND, wide)

    def test_a_comment_is_read_both_ways_for_an_embedded_picture_too(self):
        for css in ('a{background:u/**/rl(data:image/png;base64,AAAA)}', 'a{background:red/**/image-set("data:image/png;base64,AAAA" 1x)}'):
            for how, text in self.three_ways(css, wide=False):
                with self.subTest(how=how, css=css):
                    with self.assertRaises(PublishError) as ctx:
                        publish.check_brand(text)
                    self.assertIn("embeds a picture in its style", str(ctx.exception))

    def test_the_escape_cases_that_are_fine_are_published(self):
        good = ['a{content:"\\"x\\"";color:red}', "a{content:'\\'x\\'';color:red}", 'a{content:"\\27 \\22 ";color:red}',
                'a{content:"x\\\r\ny";color:red}', 'a{b:red/**/blue;c:red /* x */ green}\r\n',
                'a{content:"\\\\"}b{color:red}', ':root{--n:\\27 a\\27 }']
        for css in good:
            for how, text in self.three_ways(css):
                with self.subTest(how=how, css=css):
                    publish.check_brand(text)

    def test_the_old_cases_still_behave(self):
        self.refuse('a{content:"x\nb{background:url(//example.invalid/a)}', publish.ADDRESS_FOUND)
        self.refuse('a{background:image-set("http://example.invalid/a" 1x)', publish.ADDRESS_FOUND)
        self.refuse("/* c */ @import 'http://example.invalid/a.css';", publish.IMPORT_FOUND)
        self.assertEqual(publish.css_findings('a{content:"never closed'), set())
        self.assertEqual(publish.css_findings("/* a\f b */ a{color:red}\r\n"), set())


if __name__ == "__main__":
    unittest.main()
