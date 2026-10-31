"""#112: gaps in the publish scan (publish.outside_addresses, check_brand; #43's check_copy runs the same scan).

Run: python3 dev/run_tests.py test_publish_scan_gaps
Every bad fragment is spliced into a real finished file straight before its data block, as a hostile report or a hostile client
folder file would carry it. Each must give a finding from outside_addresses and from to_client.check_copy; CSS ones also make
check_brand refuse. The controls: the real file, the three pinned icon links, and ordinary good fragments, stay clean.
"""
import base64
import sys
import time
import unittest

from _paths import ROOT, SRC, TOOLS  # noqa: F401

from clark import page, publish, to_client  # noqa: E402
from clark.publish import PublishError  # noqa: E402
from test_publish import ICON_LINK, TOUCH_LINK, made  # noqa: E402

OPENER = '<script type="application/json" id="clark-data">'
_BASE = []


def real():
    if not _BASE:
        _BASE.append(made()[2])
    return _BASE[0]


def spliced(bad):
    text = real()
    assert text.count(OPENER) == 1
    return text.replace(OPENER, bad + OPENER, 1)


class Gaps(unittest.TestCase):
    def bad(self, *fragments, css=False):
        for frag in fragments:
            text = spliced(frag)
            self.assertTrue(publish.outside_addresses(text), f"outside_addresses passes {frag!r}")
            self.assertTrue(to_client.check_copy(text.encode("utf-8"), markers=()), f"check_copy passes {frag!r}")
            if css:
                with self.assertRaises(PublishError, msg=f"check_brand passes {frag!r}"):
                    publish.check_brand(text)

    def good(self, *fragments):
        for frag in fragments:
            self.assertEqual(publish.outside_addresses(spliced(frag)), [], frag)

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

    # Control: after "=", HTML white space (tab, LF, FF, CR, space) IS skipped, so the quote is real and holds one value.
    def test_html_white_space_after_equals_still_reads_a_real_quote(self):
        for ch in ("\t", "\n", "\x0c", "\r", " "):
            with self.subTest(repr(ch)):
                self.good(f"<div x={ch}'a style=background:url(https://evil.example/a.png) b'>x</div>")

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

    def test_other_elements_and_attributes_that_load_things(self):
        self.bad('<object data="//x.invalid/a.swf"></object>', '<embed src="//x.invalid/a.swf">', '<form action="//x.invalid/p"></form>',
                 '<a ping="//x.invalid/p">x</a>', '<a ping="#a //x.invalid/p">x</a>', '<a ping="#a   https://x.invalid/p">x</a>',
                 '<svg xmlns:xlink="http://www.w3.org/1999/xlink"><use xlink:href="//x.invalid/a.svg#i"/></svg>',
                 '<use XLINK:HREF="//x.invalid/a.svg#i"/>', '<video poster="//x.invalid/p.png"></video>', '<button formaction="//x.invalid">x</button>',
                 '<table background="//x.invalid/a.png"></table>', '<iframe src="a.html"></iframe>', '<iframe srcdoc="x"></iframe>',
                 '<frame src="a.html">', '<object data="a.swf"></object>', '<embed src="a.swf">', '<base href="x/">',
                 '<link rel=stylesheet href=a.css>', '<link rel="stylesheet" href="data:text/css,a{}">',
                 '<audio src="//x.invalid/a.mp3"></audio>', '<video><source src="//x.invalid/a.mp4"></video>', '<track src="//x.invalid/a.vtt">')

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

    def test_the_new_scans_are_linear(self):
        n = 30000
        for name, frag in (("open tags", "<a " * n), ("open quotes", '<a b="' * n), ("entities", '<img src="' + "&#47;" * (2 * n) + 'x">'),
                           ("comment openers in style", "<style>" + "/*" * n + "</style>"), ("url openers", "<style>" + "url(" * n + "</style>"),
                           ("escapes", "<style>" + "\\\\" * n + "</style>"), ("hex escapes", "<style>" + "\\75 " * n + "</style>"),
                           ("srcset commas", '<img srcset="' + "," * n + '">'), ("srcset words", '<img srcset="' + "a " * n + '">'),
                           ("style attrs", '<a style="' * n), ("ampersands", '<a href="' + "&" * n + '">'), ("image-set", "<style>" + "image-set(" * n + "</style>")):
            began = time.perf_counter()
            publish.outside_addresses(frag)
            self.assertLess(time.perf_counter() - began, 3.0, name)


FOREIGN = ("<svg><style><![CDATA[ /* </style> */ @import url(//evil/x.css); ]]></style></svg>",
           "<svg><style><!-- </style> --> @import url(//evil/x.css); </style></svg>", "<svg></svg>", "<math></math>", "<![CDATA[x]]>",
           "<SVG>", "<Math>", "<svg>", '<svg><style>&#64;import "//e";</style></svg>', "<svg><style>a{background:u&#114;l(//e)}</style></svg>",
           "<![cdata[x]]>")


def positions(bad):
    """The fragment `bad` in each place a hostile file could carry it, as whole files."""
    text, out = real(), []
    out.append(text.replace(OPENER, bad + OPENER, 1))                              # before the data block
    out.append(text.replace("</body>", bad + "</body>"))                           # after it (the block is then page markup)
    out.append(text + bad)                                                         # after </html>
    out.append(text.replace("<head>", "<head>" + bad, 1))                          # in the head
    out.append(text.replace(OPENER, "<!--" + bad + "-->" + OPENER, 1))             # in a comment
    out.append(text.replace(OPENER, "<script>/*" + bad + "*/</script>" + OPENER, 1))     # in a script
    out.append(text.replace(OPENER, "<template>" + bad + "</template>" + OPENER, 1))     # in a template
    return out


class ForeignContent(unittest.TestCase):
    """#112 H1: an svg, math or CDATA section hides real CSS from the style scan, so each is refused, wherever it stands."""

    def test_each_is_refused_by_all_three_checks_at_every_position(self):
        for bad in FOREIGN:
            for n, text in enumerate(positions(bad)):
                label = f"{bad!r} at position {n}"
                self.assertIn(publish.FOREIGN_FOUND, publish.outside_addresses(text), label)
                self.assertIn(publish.FOREIGN_FOUND, to_client.check_copy(text.encode("utf-8"), markers=()), label)
                with self.assertRaises(PublishError, msg=label):
                    publish.check_brand(text)

    def test_the_real_page_and_its_parts_have_none(self):
        self.assertEqual(publish.outside_addresses(real()), [])
        publish.check_brand(real())
        self.assertIsNone(publish.FOREIGN.search(publish.without_data_block(real())))

    def test_the_built_page_bundles_pass_the_brand_check(self):
        for name in ("page.html", "page-view.html"):
            text = (SRC / "clark" / "page" / name).read_text(encoding="utf-8")
            publish.check_brand(text)
            self.assertNotIn(publish.FOREIGN_FOUND, publish.outside_addresses(text), name)

    def test_a_less_than_before_math_in_a_script_is_no_tag(self):
        for code in ("s<Math.min(a,b)", "a<math.x", "if(a<svg.length)b()", "x<Math", "x<svg"):
            page = "<html><body><script>" + code + "</script></body></html>"
            publish.check_brand(page)
            self.assertNotIn(publish.FOREIGN_FOUND, publish.outside_addresses(page), code)

    def test_real_tags_are_found_before_every_html_boundary(self):
        for tag in ("<math>", "<MATH x>", "<svg>", "<SVG ", "<math/>", "<svg\tx>", "<svg\nx>", "<svg\fx>", "<svg\rx>"):
            page = "<html><body>" + tag + "</body></html>"
            self.assertIn(publish.FOREIGN_FOUND, publish.outside_addresses(page), repr(tag))
            with self.assertRaises(PublishError, msg=repr(tag)):
                publish.check_brand(page)


class UrlOutside(unittest.TestCase):
    """#112 H3: _url_outside matches in place (no slice per url( ); the answers are the old ones."""

    def test_the_answers(self):
        f = publish._url_outside
        for text in ("url(data:x)", "url( 'data:x')", 'url("DATA:x")', "url(data:a", "a{b:url(data:a) url(data:b)}", ""):
            self.assertFalse(f(text), text)
        for text in ("url(a)", "url(  ", "url() data:x", "url(data:a) url(b)", "url(//x)", "url(", "url(x data:)"):
            self.assertTrue(f(text), text)


class Desync(unittest.TestCase):
    """#112 H4: a quote that swallows a < must not hide the tags inside it, and `=` may start an attribute name."""
    bad = Gaps.bad

    def test_entity_encoded_addresses_after_a_quote_that_swallows_a_tag(self):
        img = '<img src="&#47;&#47;evil.invalid/a.png">'
        self.bad('<!-- <a title=" -->' + img, "<!-- <a title=' -->" + img.replace('"', "'"), "<!-- <a title=' -->" + img,
                 '<textarea><a title="</textarea>' + img, "<textarea><a title='</textarea>" + img,
                 '<title><a title="</title>' + img, "<title><a title='</title>" + img,
                 '<xmp><a title="</xmp>' + img, '<a title=">' + img, '<a title="x<a title=">' + img,
                 '<a b="' + img, '<a b="<a c="' + img)

    def test_a_bracket_inside_an_unquoted_value_or_name_is_part_of_it(self):
        # a browser keeps < in an unquoted value: style=a<b;background:url(...) has a first declaration that is skipped and a
        # second that loads. Cutting the value at < (round 3's proposed fix) would lose this; the reader keeps it and stays
        # linear by not re-reading a run it has read.
        self.bad('<a style=a<b;background:url(http://e.example/i.png)>x</a>',
                 '<p style=x<q;background:url(//e.example/i.png)>x</p>',
                 '<div style=<x;background:url(https://e.example/i.png) class=y>x</div>')

    def test_an_equals_sign_may_start_an_attribute_name(self):
        self.bad('<a ="x" href="&#47;&#47;evil.invalid">x</a>', '<a =x href="&#47;&#47;evil.invalid">x</a>',
                 '<a = href="&#47;&#47;evil.invalid">x</a>', '<a ==x href=&#47;&#47;evil.invalid>x</a>',
                 "<a ='x' src='&#47;&#47;evil.invalid'>x</a>", '<img =" src="&#47;&#47;evil.invalid">')

    def test_the_reader_finds_the_tags_a_swallowing_quote_holds(self):
        self.assertEqual([n for n, _ in publish.tags('<a title="<b><i>">')], ["a", "b", "i"])
        self.assertEqual(list(publish.tags('<a =x y=1>')), [("a", [("=x", ""), ("y", "1")])])


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
