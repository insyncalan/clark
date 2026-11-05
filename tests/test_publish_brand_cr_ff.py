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
    def three_ways(self, css):
        """The css as a style block, as a brand tokens.css layered into the real page, and spliced into the page's own style."""
        yield "style", "<style>" + css + "</style>"
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "tokens.css").write_text(css, encoding="utf-8", newline="")
            yield "tokens", page.page_html(tmp)
        html = page.PAGE.read_text(encoding="utf-8")
        yield "page", html.replace("</style>", css + "\n</style>", 1)

    def refuse(self, css, found):
        for how, text in self.three_ways(css):
            with self.subTest(how=how, css=css):
                with self.assertRaises(PublishError) as ctx:
                    publish.check_brand(text)
                self.assertIn(SENTENCE[found], str(ctx.exception))

    def test_an_open_string_ended_by_cr_ff_or_crlf_does_not_hide_a_later_address(self):
        for opener in OPEN:
            for end_name, end in ENDS.items():
                for name, (tail, found) in BAD.items():
                    with self.subTest(end=end_name, tail=name):
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

    def test_the_old_cases_still_behave(self):
        self.refuse('a{content:"x\nb{background:url(//example.invalid/a)}', publish.ADDRESS_FOUND)
        self.refuse('a{background:image-set("http://example.invalid/a" 1x)', publish.ADDRESS_FOUND)
        self.refuse("/* c */ @import 'http://example.invalid/a.css';", publish.IMPORT_FOUND)
        self.assertEqual(publish.css_findings('a{content:"never closed'), set())
        self.assertEqual(publish.css_findings("/* a\f b */ a{color:red}\r\n"), set())


if __name__ == "__main__":
    unittest.main()
