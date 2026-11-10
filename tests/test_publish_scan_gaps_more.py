"""#112: the second half of the Gaps cases (the spellings of an address the scan must find).

Run: python3 dev/run_tests.py test_publish_scan_gaps_more
The bad/good checks and the real page are in _scan_gaps.py; the file was split from test_publish_scan_gaps.py (one file took 5 minutes).
"""
import unittest

import _paths  # noqa: F401

from _scan_gaps import GapsChecks  # noqa: E402


class GapsMore(GapsChecks, unittest.TestCase):
    # (a) script and relative src, letter case
    def test_a_script_src_in_any_case_or_spacing(self):
        self.bad("<SCRIPT SRC=a.js>", "<Script SrC='x.js'>", "<SCRIPT SRC=file:///etc/x>", '<script src = "a.js"></script>',
                 "<script\nsrc=a.js></script>", "<script/src=a.js></script>", '<script type="module" src="./a.js"></script>')

    # (b) entity-encoded addresses
    def test_entity_encoded_addresses(self):
        self.bad('<img src="&#47;&#47;x.invalid/a.png">', '<img src="&#x2F;&#x2F;x.invalid/a.png">', '<img src="&#X2f;&#X2F;x.invalid">',
                 '<base href="&#47;&#47;x.invalid">', '<img src="&#47&#47x.invalid">', '<img src="&sol;&sol;x.invalid">',
                 '<img src="https&colon;//x.invalid/a.png">', '<img src="h&#116;tps://x.invalid/a.png">',
                 '<script src="&#47;&#47;x.invalid/a.js"></script>', '<a href="&#47;&#9;&#47;x.invalid">x</a>',
                 '<img src="&amp;#47;&amp;#47;x.invalid/a.png">', '<img src="&amp;amp;#47;&amp;amp;#47;x.invalid">',
                 '<meta http-equiv="&#114;efresh" content="0;url=a.html">', '<meta http-equiv="&#x72;efresh" content="0">',
                 '<img SRC="&#47;&#47;x.invalid">')

    # (c) meta refresh spacing
    def test_meta_refresh_with_spacing_or_odd_quoting(self):
        self.bad('<meta http-equiv = "refresh" content="0">', "<meta http-equiv\n=\nrefresh content=0>", "<META HTTP-EQUIV='Refresh'>",
                 '<meta content="0" http-equiv=refresh>', '<meta http-equiv=" refresh " content="0">', '<meta/http-equiv=refresh>')

    # (d) srcset: every candidate
    def test_every_srcset_candidate_is_checked(self):
        self.bad('<img srcset="data:image/png;base64,AAAA 1x, //x.invalid/a.png 2x">',
                 '<img srcset="data:image/png;base64,AAAA 1x,https://x.invalid/a.png 2x">',
                 '<img srcset="data:image/png;base64,AAAA 1x, data:image/png;base64,BBBB 2x, //x.invalid/c.png 3x">',
                 '<img srcset="//x.invalid/a.png 1x">', '<source srcset="&#47;&#47;x.invalid/a.png 1x">',
                 '<img srcset="a.png 1x,\n//x.invalid/b.png 2x">', '<img srcset="\\\\x.invalid/a.png 1x">')

    # (e) style attributes
    def test_style_attributes_are_scanned(self):
        self.bad('<div style="background:url(//x.invalid)">x</div>', "<div style='background:url(https://x.invalid/a.png)'>x</div>",
                 "<div style=background:url(//x.invalid)>x</div>", '<div STYLE="background:URL( //x.invalid )">x</div>',
                 '<div style="background:url(&#47;&#47;x.invalid)">x</div>', '<div style="background:url(&quot;//x.invalid&quot;)">x</div>',
                 '<div style="@import url(//x.invalid/a.css)">x</div>', '<div style = "background : url(a.png)">x</div>',
                 '<div style="background:image-set(&quot;//x.invalid/a.png&quot; 1x)">x</div>',
                 '<div style="background:u\\72l(//x.invalid)">x</div>')

    # Control: after "=", HTML white space (tab, LF, FF, CR, space) IS skipped, so the quote is real and holds one value.
    def test_html_white_space_after_equals_still_reads_a_real_quote(self):
        for ch in ("\t", "\n", "\x0c", "\r", " "):
            with self.subTest(repr(ch)):
                self.good(f"<div x={ch}'a style=background:url(https://evil.example/a.png) b'>x</div>")

    # extra bypasses of my own
    def test_backslash_and_odd_addresses(self):
        self.bad('<a href="\\\\x.invalid">x</a>', '<a href="/\\x.invalid">x</a>', '<a href="\\/x.invalid">x</a>', '<a href=" //x.invalid">x</a>',
                 '<a href="\t//x.invalid">x</a>', '<a href="/\n/x.invalid">x</a>', '<a href="HTTP://x.invalid">x</a>',
                 '<a href="http:x.invalid">x</a>', '<img src="https:\\\\x.invalid">', '<a href=//x.invalid>x</a>')

    def test_script_and_html_urls_in_href_and_src(self):
        self.bad('<a href="javascript:alert(1)">x</a>', '<a href="JaVaScRiPt:alert(1)">x</a>', '<a href=" javascript:alert(1)">x</a>',
                 '<a href="jav&#x09;ascript:alert(1)">x</a>', '<a href="jav\tascript:alert(1)">x</a>', '<a href="java&Tab;script:alert(1)">x</a>',
                 '<a href="vbscript:x">x</a>', '<a href="data:text/html,<b>x</b>">x</a>', '<img src="data:text/html;base64,AAAA">',
                 '<a href="DATA:text/html;base64,AAAA">x</a>', '<iframe src="data:text/html,x"></iframe>', '<a href="data:application/xhtml+xml,x">x</a>')

    def test_a_null_byte_or_comment_in_an_address_does_not_hide_it(self):
        self.bad('<img src="/\x00/x.invalid">', "<style>a{background:url(\x00//x.invalid)}</style>", "<style>a{background:u\x00rl(//x.invalid)}</style>",
                 "<style>@\x00import 'x.css';</style>")

    def test_more_spellings_found_by_hand(self):
        for css in ('a{background:image-set( "//x.invalid" 1x)}', 'a{background:image-set(url(data:image/png;base64,AAAA) 1x, "//x.invalid" 2x)}',
                    'a{background:image-set(\n"//x.invalid"\n1x)}', 'a{background:src( "//x.invalid" )}', "\\@import 'x.css';",
                    "/* c */@import 'x.css';", "a{background:URL(//x.invalid)}", "a{background:url(\n//x.invalid)}",
                    'a{background:-moz-image-set("//x.invalid" 1x)}', 'a{background:IMAGE-SET("//x.invalid" 1x)}',
                    "a{background:u\\000072l(//x.invalid)}", "a{background:image-set(image-set(\"//x.invalid\" 1x) 1x)}"):
            self.bad(f"<style>{css}</style>", css=True)
        self.bad('<a href="&NewLine;//x.invalid">x</a>', '<a href="&#x6A;avascript:1">x</a>', '<a href="JAVASCRIPT:1">x</a>',
                 '<a href="&#0000106;avascript:1">x</a>', '<a href="\x01//x.invalid">x</a>', '<img src="&#x20;&#x20;//x.invalid">',
                 '<img\x00src="//x.invalid">', "<img/src='//x.invalid'/>", '<IMG SRC=JaVaScRiPt:1>', '<a href="file:///etc/hosts">x</a>',
                 '<a href="ftp://x.invalid/">x</a>', '<a href="blob:null/x">x</a>', '<img srcset="&#47;&#47;x.invalid 1x">',
                 "<div style='background:url(&#x2f;&#x2f;x.invalid)'>x</div>", '<div style="background:url(&amp;#47;&amp;#47;x.invalid)">x</div>',
                 "<!-- <img src=//x.invalid> -->")

if __name__ == "__main__":
    unittest.main()
