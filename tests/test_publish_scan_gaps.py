"""#112: gaps in the publish scan (publish.outside_addresses, check_brand; #43's check_copy runs the same scan).

Run: python3 dev/run_tests.py test_publish_scan_gaps
Every bad fragment is spliced into a real finished file straight before its data block, as a hostile report or a hostile client
folder file would carry it. Each must give a finding from outside_addresses and from to_client.check_copy; CSS ones also make
check_brand refuse. The controls: the real file, the three pinned icon links, and ordinary good fragments, stay clean.
"""
import unittest

import _paths  # noqa: F401

from _scan_gaps import GapsChecks, real, spliced  # noqa: E402
from clark import publish  # noqa: E402
from test_publish import ICON_LINK, TOUCH_LINK  # noqa: E402


class Gaps(GapsChecks, unittest.TestCase):
    def test_the_controls_are_clean(self):
        self.assertEqual(publish.outside_addresses(real()), [])
        publish.check_brand(real())
        links = real().count("<link ")
        self.assertEqual(links, 3, "the three pinned icon links are in the real file")
        self.assertIn(ICON_LINK, real())
        self.assertIn(TOUCH_LINK, real())
        self.good('<img src="data:image/png;base64,AAAA" alt="x">', '<a href="#top">x</a>', '<a href="mailto:a@b.invalid">x</a>',
                  "<p>AT&amp;T and &lt;script src=a.js&gt; shown as text</p>", '<a href="a.html">x</a>',
                  '<div style="color:red;background:url(data:image/png;base64,AAAA)">x</div>',
                  '<img srcset="data:image/png;base64,AAAA 1x, data:image/png;base64,BBBB 2x" src="data:image/png;base64,AAAA">',
                  "<style>@font-face{font-family:X;src:url(data:font/woff2;base64,AAAA) format('woff2')}</style>",
                  '<style>a{background:image-set("data:image/png;base64,AAAA" 1x)}</style>')

    # #112 H1: an unquoted value ends only at HTML white space (tab, LF, FF, CR, space, >). Python's \s also matches these, so a
    # value like style=a<char>;background:url(...) must still be read to the url. One fragment per character class.
    def test_unquoted_style_value_ends_only_at_html_white_space(self):
        classes = {"vertical tab": "\x0b", "file separator": "\x1c", "group separator": "\x1d", "record separator": "\x1e",
                   "unit separator": "\x1f", "next line": "\x85", "no-break space": "\xa0", "line separator": " ",
                   "ideographic space": "　", "ogham space": " ", "en quad": " ", "hair space": " ",
                   "paragraph separator": " ", "narrow no-break space": " ", "medium mathematical space": " "}
        for name, ch in classes.items():
            with self.subTest(name):
                self.bad(f"<div style=a{ch};background:url(https://x.invalid/a.png)>x</div>")

    # #112 H2: after "=" a browser skips only tab, LF, FF, CR and space before the value. Any other character (a vertical tab, NUL,
    # a no-break space, 1c to 1f, U+0085, U+2028, U+3000 and the rest) starts an UNQUOTED value, which ends at the next space. So in
    # x=<char>'a style=background:url(...) b' the quote is not a quote: the browser reads style=... as a real attribute and fetches
    # the outside address. The scan must not treat that quote as one and hide what is inside it.
    def test_odd_white_space_after_equals_is_not_a_quote(self):
        chars = {"vertical tab": "\x0b", "NUL": "\x00", "no-break space": "\xa0", "file separator": "\x1c", "group separator": "\x1d",
                 "record separator": "\x1e", "unit separator": "\x1f", "next line": "\x85", "line separator": "\u2028",
                 "paragraph separator": "\u2029", "ideographic space": "\u3000", "ogham space": "\u1680", "en quad": "\u2000",
                 "hair space": "\u200a", "narrow no-break space": "\u202f", "medium mathematical space": "\u205f"}
        for name, ch in chars.items():
            with self.subTest(name + " (style)"):
                self.bad(f"<div x={ch}'a style=background:url(https://evil.example/a.png) b'>x</div>")
            with self.subTest(name + " (img)"):
                self.bad(f"<img x={ch}'a src=&#47;/evil.example/a.png b'>")
        with self.subTest("script and meta"):
            self.bad("<script x=\x0b'a src=a.js b'></script>", "<meta x=\x0b'a http-equiv=refresh content=0;url=a.html b'>")

    # (f) CSS escapes, image-set and friends
    def test_css_escapes_and_image_functions(self):
        for css in ("a{background:\\75rl(//x.invalid)}", "a{background:u\\72l(//x.invalid)}", "a{background:\\000075rl(//x.invalid)}",
                    "@\\69mport 'x.css';", "@\\000069mport url(x.css);", "@im\\70ort 'x.css';", 'a{background:image-set("//x.invalid" 1x)}',
                    "a{background:-webkit-image-set(url(//x.invalid) 1x)}", "a{background:image-set('x.png' 1x)}",
                    'a{background:src("//x.invalid/a.png")}', 'a{background:image("//x.invalid/a.png")}',
                    'a{background:cross-fade("//x.invalid/a.png", red)}', "a{background:u/**/rl(//x.invalid)}",
                    "a{background:url(//x.invalid", "@/**/import 'x.css';", "a{background:url(\\2f\\2f x.invalid)}",
                    'a{background:image-set("\\2f\\2f x.invalid" 1x)}', "a{background:\\55RL(//x.invalid)}", "@IMPORT\\ 'x.css';", "\\40 import 'x.css';", "\\000040import 'x.css';"):
            self.bad(f"<style>{css}</style>", css=True)

    def test_other_elements_and_attributes_that_load_things(self):
        self.bad('<object data="//x.invalid/a.swf"></object>', '<embed src="//x.invalid/a.swf">', '<form action="//x.invalid/p"></form>',
                 '<a ping="//x.invalid/p">x</a>', '<a ping="#a //x.invalid/p">x</a>', '<a ping="#a   https://x.invalid/p">x</a>',
                 '<svg xmlns:xlink="http://www.w3.org/1999/xlink"><use xlink:href="//x.invalid/a.svg#i"/></svg>',
                 '<use XLINK:HREF="//x.invalid/a.svg#i"/>', '<video poster="//x.invalid/p.png"></video>', '<button formaction="//x.invalid">x</button>',
                 '<table background="//x.invalid/a.png"></table>', '<iframe src="a.html"></iframe>', '<iframe srcdoc="x"></iframe>',
                 '<frame src="a.html">', '<object data="a.swf"></object>', '<embed src="a.swf">', '<base href="x/">',
                 '<link rel=stylesheet href=a.css>', '<link rel="stylesheet" href="data:text/css,a{}">',
                 '<audio src="//x.invalid/a.mp3"></audio>', '<video><source src="//x.invalid/a.mp4"></video>', '<track src="//x.invalid/a.vtt">')


class UrlOutside(unittest.TestCase):
    """#112 H3: _url_outside matches in place (no slice per url( ); the answers are the old ones."""

    def test_the_answers(self):
        f = publish._url_outside
        for text in ("url(data:x)", "url( 'data:x')", 'url("DATA:x")', "url(data:a", "a{b:url(data:a) url(data:b)}", ""):
            self.assertFalse(f(text), text)
        for text in ("url(a)", "url(  ", "url() data:x", "url(data:a) url(b)", "url(//x)", "url(", "url(x data:)"):
            self.assertTrue(f(text), text)


class StyleJoin(unittest.TestCase):
    """A stray quote in one <style> must not swallow the next one: a browser reads each style on its own."""

    def test_a_stray_quote_in_one_style_does_not_hide_the_next_styles_address(self):
        for q in ('"', "'"):
            for tail in ('image-set(%s//e.example/a%s 1x)' % (q, q), "url(//e.example/a.png)", "url(http://e.example/a.png)"):
                text = "<style>%s</style><style>a{background:%s}</style>" % (q, tail)
                with self.subTest(text):
                    self.assertTrue(publish.outside_addresses(text), text)
                    self.assertTrue(publish.outside_addresses(spliced(text)))

    def test_two_clean_styles_stay_clean(self):
        self.assertEqual(publish.outside_addresses('<style>"</style><style>a{color:red}</style>'), [])

if __name__ == "__main__":
    unittest.main()
