"""#912: the second half of the Gaps class of test_publish_scan_gaps, in a file of its own so CI spreads the load. Same cases, same helper.
Run: python3 dev/run_tests.py test_publish_scan_gaps_more
"""
import sys
import unittest

from _paths import ROOT, SRC, TOOLS  # noqa: F401

from clark import publish, to_client  # noqa: E402
from clark.publish import PublishError  # noqa: E402
from _growth import assert_growth  # noqa: E402
import test_publish_scan_gaps as base  # noqa: E402
from test_publish_scan_gaps import real, spliced  # noqa: E402


class Gaps(unittest.TestCase):
    bad = base.Gaps.bad
    good = base.Gaps.good

    # (e) style attributes
    def test_style_attributes_are_scanned(self):
        self.bad('<div style="background:url(//x.invalid)">x</div>', "<div style='background:url(https://x.invalid/a.png)'>x</div>",
                 "<div style=background:url(//x.invalid)>x</div>", '<div STYLE="background:URL( //x.invalid )">x</div>',
                 '<div style="background:url(&#47;&#47;x.invalid)">x</div>', '<div style="background:url(&quot;//x.invalid&quot;)">x</div>',
                 '<div style="@import url(//x.invalid/a.css)">x</div>', '<div style = "background : url(a.png)">x</div>',
                 '<div style="background:image-set(&quot;//x.invalid/a.png&quot; 1x)">x</div>',
                 '<div style="background:u\\72l(//x.invalid)">x</div>')

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

    def test_script_and_html_urls_in_href_and_src(self):
        self.bad('<a href="javascript:alert(1)">x</a>', '<a href="JaVaScRiPt:alert(1)">x</a>', '<a href=" javascript:alert(1)">x</a>',
                 '<a href="jav&#x09;ascript:alert(1)">x</a>', '<a href="jav\tascript:alert(1)">x</a>', '<a href="java&Tab;script:alert(1)">x</a>',
                 '<a href="vbscript:x">x</a>', '<a href="data:text/html,<b>x</b>">x</a>', '<img src="data:text/html;base64,AAAA">',
                 '<a href="DATA:text/html;base64,AAAA">x</a>', '<iframe src="data:text/html,x"></iframe>', '<a href="data:application/xhtml+xml,x">x</a>')

    def test_other_elements_and_attributes_that_load_things(self):
        self.bad('<object data="//x.invalid/a.swf"></object>', '<embed src="//x.invalid/a.swf">', '<form action="//x.invalid/p"></form>',
                 '<a ping="//x.invalid/p">x</a>', '<a ping="#a //x.invalid/p">x</a>', '<a ping="#a   https://x.invalid/p">x</a>',
                 '<svg xmlns:xlink="http://www.w3.org/1999/xlink"><use xlink:href="//x.invalid/a.svg#i"/></svg>',
                 '<use XLINK:HREF="//x.invalid/a.svg#i"/>', '<video poster="//x.invalid/p.png"></video>', '<button formaction="//x.invalid">x</button>',
                 '<table background="//x.invalid/a.png"></table>', '<iframe src="a.html"></iframe>', '<iframe srcdoc="x"></iframe>',
                 '<frame src="a.html">', '<object data="a.swf"></object>', '<embed src="a.swf">', '<base href="x/">',
                 '<link rel=stylesheet href=a.css>', '<link rel="stylesheet" href="data:text/css,a{}">',
                 '<audio src="//x.invalid/a.mp3"></audio>', '<video><source src="//x.invalid/a.mp4"></video>', '<track src="//x.invalid/a.vtt">')

    def test_the_new_scans_are_linear(self):
        # The old check was a wall-clock limit (3 s for 30,000 repeats); it is now the growth from 30,000 to 120,000 repeats in CPU time.
        for name, make in (("open tags", lambda n: "<a " * n), ("open quotes", lambda n: '<a b="' * n),
                           ("entities", lambda n: '<img src="' + "&#47;" * (2 * n) + 'x">'),
                           ("comment openers in style", lambda n: "<style>" + "/*" * n + "</style>"),
                           ("url openers", lambda n: "<style>" + "url(" * n + "</style>"),
                           ("escapes", lambda n: "<style>" + "\\\\" * n + "</style>"), ("hex escapes", lambda n: "<style>" + "\\75 " * n + "</style>"),
                           ("srcset commas", lambda n: '<img srcset="' + "," * n + '">'), ("srcset words", lambda n: '<img srcset="' + "a " * n + '">'),
                           ("style attrs", lambda n: '<a style="' * n), ("ampersands", lambda n: '<a href="' + "&" * n + '">'),
                           ("image-set", lambda n: "<style>" + "image-set(" * n + "</style>")):
            assert_growth(self, lambda size, make=make: publish.outside_addresses(make(size)), 30000, name)


if __name__ == "__main__":
    unittest.main()
