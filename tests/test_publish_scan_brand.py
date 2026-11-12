"""#112: pictures in style text: check_brand refuses an address or a data picture, but not the logo rule, the circle or a font.

Run: python3 dev/run_tests.py test_publish_scan_brand
The bad/good checks and the real page are in _scan_gaps.py; the file was split from test_publish_scan_gaps.py (one file took 5 minutes).
"""
import tempfile
import unittest
from pathlib import Path

import _paths  # noqa: F401

from _scan_gaps import real, spliced  # noqa: E402
from clark import page, publish  # noqa: E402
from clark.publish import PublishError  # noqa: E402
from test_publish import EMPTY_BRANDING, made  # noqa: E402


class BrandPictures(unittest.TestCase):
    """#321: check_brand refuses a picture in style text whether it is named by address (url(x.png)) or embedded as data
    (url(data:image/...)), except clark's own logo rule and an embedded font. outside_addresses is unchanged: an embedded image is no
    address, so only the brand check, and the page build that runs it, refuse."""

    def style(self, css):
        return "<style>" + css + "</style>"

    def test_a_picture_by_address_is_refused(self):
        for css in ("a{background:url(x.png)}", "a{background:URL( 'x.png' )}", 'a{background:image-set("x.png" 1x)}'):
            with self.assertRaises(PublishError, msg=css):
                publish.check_brand(self.style(css))

    def test_a_picture_as_data_is_refused_in_every_spelling(self):
        for css in ("a{background:url(data:image/png;base64,AAAA)}", 'a{background:url("data:image/gif;base64,AAAA")}',
                    "a{background:URL( 'DATA:image/jpeg;base64,AAAA' )}", 'a{background:image-set("data:image/png;base64,AAAA" 1x)}',
                    "a{list-style-image:url(data:image/webp;base64,AAAA)}", "a::before{content:url(data:image/svg+xml;base64,AAAA)}",
                    "a{background:\\75rl(d\\61ta:image/png;base64,AAAA)}", "a{background:u/**/rl(data:image/png;base64,AAAA)}",
                    "a{background:url(data:text/html;base64,AAAA)}",
                    ".logo-icon{background-image:url(data:image/png;base64,AAAA)}", ".logo-icon{background-image:url(data:image/svg+xml;base64,AAAA);color:red}",
                    ".card{background-image:url(data:image/svg+xml;base64,AAAA)}"):
            with self.assertRaises(PublishError, msg=css):
                publish.check_brand(self.style(css))

    def test_a_null_byte_in_the_logo_rule_is_refused(self):
        """#493: a browser reads a null byte as U+FFFD, so s\0vg and backg\0round-image are not the logo rule's words."""
        good = '.logo-icon{background-image:url(data:image/svg+xml;base64,PHN2Zz4=)}'
        publish.check_brand(self.style(good))
        for bad in (good.replace("svg", "s\0vg"), good.replace("background-image", "backg\0round-image"),
                    good.replace("logo-icon", "logo\0icon"), good.replace("base64,", "base\x0064,")):
            with self.subTest(bad):
                with self.assertRaises(PublishError):
                    publish.check_brand(self.style(bad))

    def test_a_picture_as_data_in_a_second_style_or_a_spliced_page_is_refused(self):
        with self.assertRaises(PublishError):
            publish.check_brand(self.style("a{color:red}") + self.style("b{background:url(data:image/png;base64,AAAA)}"))
        with self.assertRaises(PublishError):
            publish.check_brand(spliced(self.style("a{background:url(data:image/png;base64,AAAA)}")))

    def test_the_logo_rule_and_an_embedded_font_pass(self):
        publish.check_brand(real())
        publish.check_brand(self.style('.logo-icon { background-image: url("data:image/svg+xml;base64,PHN2Zz4="); }'))
        publish.check_brand(self.style("@font-face{font-family:X;src:url(data:font/woff2;base64,AAAA) format('woff2')}"))
        publish.check_brand(self.style('a{color:red}a[href^="x"]{background:none}'))

    LOGO = '.logo-icon{background-image:url("data:image/svg+xml;base64,PHN2Zz4=")}'

    def test_the_real_built_page_passes_the_brand_check(self):
        """The page itself, with the logo rule and its CSS escapes (the tick), not a finished file: it once refused every publish."""
        publish.check_brand(page.page_html(EMPTY_BRANDING))

    def test_an_escape_elsewhere_in_the_style_does_not_void_the_logo_rule(self):
        publish.check_brand(self.style(self.LOGO + '.x::before{content:"\\2713"}'))
        publish.check_brand(self.style('.x::before{content:"\\2713"}' + self.LOGO))
        publish.check_brand(self.style('.x::before{content:"\\2713 "}\n  ' + self.LOGO + '\n.y{content:"\\2714"}'))
        publish.check_brand(self.style('.x::before{content:"\\2713"}') + self.style(self.LOGO))

    def test_an_escape_elsewhere_does_not_void_a_look_picture(self):
        tick = '.x::before{content:"\\2713"}'
        for name in ("--art-home", "--image-cover", "--image-fade"):
            for value in ("url(%s)", 'url("%s")', "URL( '%s' )"):
                rule = ":root{%s:%s}" % (name, value % "data:image/png;base64,AAAA")
                publish.check_brand(self.style(tick + rule))
                publish.check_brand(self.style(rule + tick))
                publish.check_brand(self.style(tick + rule + tick + self.LOGO + tick))

    def test_an_escape_inside_the_logo_rule_still_refuses_it(self):
        svg = 'data:image/svg+xml;base64,PHN2Zz4='
        for rule in ('.l\\6fgo-icon{background-image:url("%s")}' % svg,
                     '.logo\\-icon{background-image:url("%s")}' % svg,
                     '\\.logo-icon{background-image:url("%s")}' % svg,
                     '.logo\\2d icon{background-image:url("%s")}' % svg,
                     '.logo-icon{background-image:u\\72l("%s")}' % svg,
                     '.logo-icon{background-image:url("%s")}' % svg.replace("data", "d\\61ta"),
                     '.logo-icon{background-image:url("%s")}' % svg.replace("svg+xml", "svg\\2bxml"),
                     '.logo-icon{background-image:url("%s")}' % svg.replace("PHN2", "PH\\4e2"),
                     '.logo-icon{b\\61ckground-image:url("%s")}' % svg,
                     '.logo-icon{background-image:url("%s");color:red}' % svg,
                     '/* %s */.l\\6fgo-icon{background-image:url("%s")}' % (self.LOGO, svg)):
            for css in (rule, '.x::before{content:"\\2713"}' + rule, rule + '.x::before{content:"\\2713"}'):
                with self.assertRaises(PublishError, msg=css):
                    publish.check_brand(self.style(css))

    def test_an_escape_inside_a_look_picture_still_refuses_it(self):
        pic = "data:image/png;base64,AAAA"
        for decl in ("--art\\-home:url(%s)" % pic, "--art-h\\6fme:url(%s)" % pic, "--art-home:u\\72l(%s)" % pic,
                     "--art-home:url(%s)" % pic.replace("data", "d\\61ta"), "--art-home:url(%s)" % pic.replace("png", "p\\6eg"),
                     "--art-home:url(%s)" % pic.replace("AAAA", "A\\41AA"), "--art-home:url(%s\\29" % pic):
            for css in (":root{%s}" % decl, '.x::before{content:"\\2713"}:root{%s}' % decl):
                with self.assertRaises(PublishError, msg=css):
                    publish.check_brand(self.style(css))

    def test_an_escape_elsewhere_does_not_spare_anything_else(self):
        tick = '.x::before{content:"\\2713"}'
        for css in ("", tick):
            for body in (".logo-icon{background-image:url(data:image/png;base64,AAAA)}",
                         ".logo-icon{background-image:url(data:image/svg+xml;base64,PHN2Zz4=);color:red}",
                         self.LOGO + self.LOGO.replace(".logo-icon", ".card"), "@media print{" + self.LOGO + "}", ".a," + self.LOGO,
                         ".card{background:url(data:image/png;base64,AAAA)}", ".card{background-image:url(data:image/svg+xml;base64,PHN2Zz4=)}",
                         ":root{--art-home:url(data:image/png;base64,AAAA),url(data:image/png;base64,AAAA)}",
                         ":root{--art-home-x:url(data:image/png;base64,AAAA)}"):
                with self.assertRaises(PublishError, msg=css + body):
                    publish.check_brand(self.style(css + body))

    LOOK_PICTURE = "data:image/png;base64,AAAA"

    def test_each_picture_variable_the_design_docs_name_may_hold_a_data_picture(self):
        for name in ("--art-home", "--image-cover", "--image-fade"):
            for value in ("url(%s)", 'url("%s")', "URL( '%s' )"):
                publish.check_brand(self.style(":root{%s:%s}" % (name, value % self.LOOK_PICTURE)))
        publish.check_brand(self.style(":root { --brand-navy: #123; --art-home: url(data:image/svg+xml;base64,PHN2Zz4=); --art-home-height: 80px; }"))
        publish.check_brand(self.style(":root{--image-cover:url(data:image/jpeg;base64,AAAA)}") + self.style("a{color:red}"))

    def test_the_same_picture_on_another_property_or_selector_is_refused(self):
        pic = self.LOOK_PICTURE
        for css in (":root{--other:url(%s)}" % pic, ":root{--art-home-height:url(%s)}" % pic, ":root{--Art-Home:url(%s)}" % pic,
                    ":root{--logo-icon:url(%s)}" % pic, ".card{--art-home-x:url(%s)}" % pic,
                    ".card{background:url(%s)}" % pic, ".card{background-image:var(--x),url(%s)}" % pic,
                    ":root{--art-home:url(%s),url(%s)}" % (pic, pic), ":root{--art-home:none,url(%s)}" % pic,
                    ":root{--art-home:image-set(url(%s) 1x)}" % pic, ':root{--art-home:image-set("%s" 1x)}' % pic,
                    ":root{--art-home:url(data:text/html;base64,AAAA)}", ":root{--art-home:url(data:image/bmp;base64,AAAA)}",
                    ":root{--art-home:url(data:application/octet-stream;base64,AAAA)}",
                    ":root{--art-home:url(%s);--other:url(%s)}" % (pic, pic), "a{--art-home:foo(data:x;--art-home:url(%s)}" % pic,
                    ":root{--art-home:u\\72l(%s)}" % pic, ":root{--art-home:url(%s)}" % pic.replace("data", "d\\61ta")):
            with self.assertRaises(PublishError, msg=css):
                publish.check_brand(self.style(css))

    def test_the_older_font_types_pass_as_fonts(self):
        for mime in ("application/font-woff", "application/font-woff2", "application/x-font-ttf", "application/x-font-otf",
                     "application/vnd.ms-fontobject", "APPLICATION/X-FONT-TTF", "font/ttf", "font/otf"):
            publish.check_brand(self.style("@font-face{font-family:X;src:url(data:%s;base64,AAAA) format('woff')}" % mime))
            publish.check_brand(self.style('@font-face{font-family:X;src:url("data:%s;base64,AAAA")}' % mime))

    def test_octet_stream_passes_only_as_a_font_face_src(self):
        publish.check_brand(self.style("@font-face{font-family:X;src:url(data:application/octet-stream;base64,AAAA) format('woff2')}"))
        publish.check_brand(self.style("a{color:red}@font-face { font-family: X; font-weight: 400; src: local(X), url('data:application/octet-stream;base64,AAAA'); }"))
        for css in ("a{background:url(data:application/octet-stream;base64,AAAA)}",
                    "@font-face{font-family:X;font-feature-settings:url(data:application/octet-stream;base64,AAAA)}",
                    "@media print{a{src:url(data:application/octet-stream;base64,AAAA)}}",
                    ":root{--art-home:url(data:application/octet-stream;base64,AAAA)}",
                    "@font-face{src:url(data:application/octet-stream;base64,AAAA)}a{background:url(data:application/octet-stream;base64,AAAA)}"):
            with self.assertRaises(PublishError, msg=css):
                publish.check_brand(self.style(css))

    def test_data_that_is_no_url_passes(self):
        for css in (".metadata:hover{color:red}", 'a::before{content:"Data: "}', 'a::before{content:"data:image/png"}',
                    ".data:hover{color:red}", "a{font-family:data}", "a[data-x]{color:red}", 'a[href^="data:"]{color:red}',
                    "/* data:image/png;base64,AAAA */ a{color:red}", "a{--note:data:image/png}",
                    'a{background:foo("data:image/png;base64,AAAA")}'):
            publish.check_brand(self.style(css))

    def test_every_earlier_refused_variant_is_still_refused(self):
        pic = "data:image/png;base64,AAAA"
        for css in ("a{background:url(%s)}" % pic, 'a{background:url("%s")}' % pic, "a{background:url('%s')}" % pic,
                    "a{background:URL( %s )}" % pic, "a{background:UrL(\n %s)}" % pic, "a{background:url(DATA:image/png;base64,AAAA)}",
                    "a{background:/* x */url(%s)}" % pic, "a{background:u/**/rl(%s)}" % pic, "a{background:url(/**/%s)}" % pic,
                    "a{background:\\75rl(%s)}" % pic, "a{background:url(d\\61ta:image/png;base64,AAAA)}",
                    "a{background:u\\72l(%s)}" % pic, "a{background:url(%s)}" % pic.replace("data", "d\\\nata"),
                    'a{background:image-set("%s" 1x)}' % pic, "a{background:image-set('%s' 1x)}" % pic,
                    'a{background:image-set(url(%s) 1x)}' % pic, 'a{background:-webkit-image-set("%s" 1x)}' % pic,
                    'a{background:image-set("x.png" 1x, "%s" 2x)}' % pic, 'a{background:image-set(  "%s" 1x)}' % pic,
                    'a{background:cross-fade(url(%s), url(%s))}' % (pic, pic), 'a{background:image("%s")}' % pic,
                    "a{list-style-image:url(%s)}" % pic, "a::before{content:url(%s)}" % pic, "a{cursor:url(%s),auto}" % pic,
                    "a{border-image-source:url(%s)}" % pic, "a{mask:url(%s)}" % pic, "a{filter:url(data:image/svg+xml;base64,AAAA#f)}",
                    ".card .logo-icon{background-image:url(data:image/svg+xml;base64,PHN2Zz4=)}",
                    ".logo-icon{background-image:url(%s)}" % pic, "a{color:red}.logo-icon{background-image:url(%s)}" % pic):
            with self.assertRaises(PublishError, msg=css):
                publish.check_brand(self.style(css))
        with self.assertRaises(PublishError):
            publish.check_brand(self.style("a{color:red}") + self.style("b{background:url(%s)}" % pic))
        with self.assertRaises(PublishError):
            publish.check_brand("<style>a{color:red}</style><style>b{background:url(%s)}" % pic)    # no end tag: read to the end
        with self.assertRaises(PublishError):
            publish.check_brand(spliced(self.style("a{background:url(%s)}" % pic)))
        with self.assertRaises(PublishError):
            publish.check_brand(self.style(":root{--art-home:url(%s)}" % pic) + self.style("a{background:url(%s)}" % pic))

    def test_the_logo_rule_must_stand_alone_at_the_top_level(self):
        logo = ".logo-icon{background-image:url(data:image/svg+xml;base64,PHN2Zz4=)}"
        publish.check_brand(self.style(logo))
        publish.check_brand(self.style("a{color:red}\n" + logo + "\nb{color:blue}"))
        publish.check_brand(self.style("a{color:red;}" + logo))
        for css in (".card .logo-icon{background-image:url(data:image/svg+xml;base64,PHN2Zz4=)}",
                    ".card>.logo-icon{background-image:url(data:image/svg+xml;base64,PHN2Zz4=)}",
                    "x.logo-icon{background-image:url(data:image/svg+xml;base64,PHN2Zz4=)}",
                    ".logo-icon,.card{background-image:url(data:image/svg+xml;base64,PHN2Zz4=)}",
                    ".card{" + logo + "}", "@media print{" + logo + "}", "a{b:c;.card " + logo + "}",
                    ".logo-icon{background-image:url(data:image/svg+xml;base64,PHN2Zz4=);width:9px}"):
            with self.assertRaises(PublishError, msg=css):
                publish.check_brand(self.style(css))

    def test_a_brand_with_a_picture_as_data_stops_the_build(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        (Path(tmp.name) / "tokens.css").write_text("a { background: url(data:image/png;base64,AAAA); }", encoding="utf-8")
        with self.assertRaisesRegex(PublishError, "embeds a picture"):
            made(branding=tmp.name)


class BrandCircleAndComments(unittest.TestCase):
    """The brand's still circle picture (`.logo { background: url(data:image/...;base64,...) }`) is data, so it is accepted in its
    one place; an address of any kind is still refused; and url() or @import text inside a CSS comment reaches nothing, but a
    comment never hides a real address outside it. Every refusal leaves nothing published (render raises before any file is made).
    The picture bytes here are invented."""

    PIC = "data:image/png;base64,iVBORw0KGgo="
    EVIL = "http://evil.example/x.png"

    def style(self, css):
        return "<style>" + css + "</style>"

    def circle(self, value=None, selector=".logo", prop="background", tail=" left center / contain no-repeat"):
        return "%s { width: 5px; height: 2px; %s: url(%s)%s; }" % (selector, prop, value or self.PIC, tail)

    def test_the_circle_picture_is_accepted(self):
        for css in (self.circle(), self.circle(prop="background-image", tail=""), self.circle(value='"%s"' % self.PIC),
                    self.circle(selector=".LOGO"), self.circle(value=self.PIC.replace("png", "jpeg")),
                    self.circle(value=self.PIC.replace("png", "webp")), self.circle(value=self.PIC.replace("png", "gif")),
                    self.circle(value=self.PIC.replace("png", "svg+xml")), self.circle().replace("url(", "URL( ").replace(")", " )"),
                    "/* the circle: url(http://evil.example/a.png) */\n" + self.circle()):
            with self.subTest(css):
                publish.check_brand(self.style(css))
                self.assertEqual(publish.outside_addresses(self.style(css)), [])

    def test_the_circle_picture_is_accepted_in_a_real_finished_page(self):
        publish.check_brand(spliced(self.style(self.circle())))

    def refused(self, css, words):
        with self.assertRaises(PublishError, msg=css) as caught:
            publish.check_brand(self.style(css))
        self.assertIn(words, str(caught.exception), css)

    def test_a_picture_in_any_other_form_or_place_is_still_refused_as_a_picture(self):
        too_big = "data:image/png;base64," + "A" * (publish.CIRCLE_MAX + 4)
        for css in (self.circle(selector=".card"), self.circle(selector=".logo-icon"), self.circle(selector=".logo .wm"),
                    self.circle(selector=".a, .logo"), self.circle(selector="a.logo"), self.circle(prop="list-style-image", tail=""),
                    self.circle(prop="content", tail=""), self.circle(prop="mask", tail=""),
                    self.circle(value=self.PIC.replace("png", "html")), self.circle(value=self.PIC.replace("png", "x-icon")),
                    self.circle(value=too_big), self.circle(value=self.PIC.replace("base64,", "")),
                    self.circle(value=self.PIC.replace("iVBORw0KGgo=", "not base64!")),
                    "@media print{%s}" % self.circle(), "@media print{.a{x:y}} .b{%s}" % self.circle().replace(".logo {", ""),
                    self.circle(tail=", url(%s)" % self.PIC), self.circle(tail=" url(%s)" % self.PIC),
                    self.circle(selector=".l\\6fgo"),
                    self.circle().replace("background", "backg\\72ound"), self.circle().replace("url(", "u\\72l("),
                    ".logo{background:image-set(\"%s\" 1x)}" % self.PIC, ".logo{background:cross-fade(url(%s), red)}" % self.PIC):
            with self.subTest(css[:80]):
                self.refused(css, "embeds a picture")

    def test_an_escaped_data_word_is_no_circle(self):
        with self.assertRaises(PublishError):
            publish.check_brand(self.style(self.circle(value=self.PIC.replace("data", "d\\61ta"))))

    def test_an_address_is_refused_in_every_spelling(self):
        for bad in ("http://evil.example/x.png", "https://evil.example/x.png", "HTTPS://EVIL.EXAMPLE/x.png", "//evil.example/x.png",
                    "javascript:alert(1)", "file:///etc/passwd", "ftp://evil.example/x", "evil.example/x.png", "x.png", "/x.png",
                    "blob:abc", "about:blank"):
            for form in ("url(%s)", 'url("%s")', "url('%s')", "url( %s )", "URL(%s)", "u\\72l(%s)", "\\75rl(%s)", "url(%s",
                         "u/**/rl(%s)"):
                css = ".a{background:" + form % bad + "}"
                with self.subTest(css):
                    with self.assertRaises(PublishError, msg=css):
                        publish.check_brand(self.style(css))
        for css in ("@import 'x.css';", '@import url("https://evil.example/x.css");', "@IMPORT url(//evil.example/x.css);",
                    "@/**/import 'x.css';", "@\\69mport 'x.css';", "@font-face{src:url(https://evil.example/f.woff2)}",
                    ".logo{background:url(//evil.example/x.png)}", ".logo{background:url(%s)}" % self.EVIL,
                    ".logo{background:url(DATA:image/png;base64,AAAA ) , url(%s)}" % self.EVIL,
                    ".a{background:image-set('//evil.example/x.png' 1x)}", ".a{background:src('http://evil.example/x.png')}"):
            with self.subTest(css):
                self.refused(css, "would reach outside the file")

    def test_a_circle_does_not_make_an_address_next_to_it_pass(self):
        for css in (self.circle() + ".a{background:url(%s)}" % self.EVIL, ".a{background:url(%s)}" % self.EVIL + self.circle(),
                    self.circle(tail=" url(%s)" % self.EVIL), self.circle(tail="; background: url(%s)" % self.EVIL)):
            with self.subTest(css[:80]):
                with self.assertRaises(PublishError):
                    publish.check_brand(self.style(css))

    def test_text_inside_a_comment_reaches_nothing(self):
        for css in (".a{} /* url(%s) */" % self.EVIL, "/* url(%s) */ .a{}" % self.EVIL, ".a{ /* url(//evil.example/x) */ color:red}",
                    "/* @import url(//evil.example/x.css); */ .a{}", "/* @import 'x.css' */", ".a{color:red} /*\nurl(%s)\n*/" % self.EVIL,
                    "/* /* url(%s) */ .a{}" % self.EVIL, "/*/ url(%s) */ .a{}" % self.EVIL, "/**/ .a{} /***/",
                    "/* url( */ .a{} /* ) */"):
            with self.subTest(css):
                publish.check_brand(self.style(css))
                self.assertEqual(publish.outside_addresses(self.style(css)), [])

    def test_a_comment_never_hides_a_real_address_outside_it(self):
        e = self.EVIL
        for css in ("/* x */ .a{background:url(%s)}" % e, ".a{background:url(%s)} /* x */" % e, ".a{background:/* x */url(%s)}" % e,
                    ".a{background:url(/* x */%s)}" % e, "/* a */ /* b */ .a{background:url(%s)}" % e,
                    "/* url(%s) */ .a{background:url(%s)}" % (e, e),
                    ".a{} /* url(x) */ @import 'x.css'; /* y */",
                    # a comment that is not closed: what follows is still read (stricter than a browser)
                    ".a{} /* url(%s)" % e, ".a{background:url(%s)} /*" % e,
                    # nested-looking: the first */ ends it, so the address after it is outside the comment
                    "/* /* x */ .a{background:url(%s)} /* y */" % e, "/* /* */ url(%s) */" % e,
                    # a /* inside a string is no comment, so it cannot hide an address up to a later */
                    '.a{content:"/*"} .b{background:url(%s)} /* */' % e, ".a{content:'/*'} .b{background:url(%s)} /* */" % e,
                    '.a{content:"\\""} .b{content:"/*"} .c{background:url(%s)} /* */' % e,
                    '.a{content:"x\\\n/*"} .b{background:url(%s)} /* */' % e,
                    # an escaped slash is no comment opener; an escape cannot spell a comment or hide an address in one
                    ".a{content:\\/*} .b{background:url(%s)} /* */" % e, ".a{x:\\2f*} .b{background:url(%s)} /* */" % e,
                    '.a{content:"/*"} .b{background:\\75rl(%s)} /* */' % e, ".a{x:\\2f* y} .b{background:\\75rl(%s)} /* */" % e,
                    # a /* inside an unquoted url( is part of its address
                    ".a{background:url(a/*)} .b{background:url(%s)} /* */" % e, ".a{background:\\75rl(a/*)} .b{background:url(%s)} /* */" % e,
                    ".a{background:URL( a/*)} .b{background:url(%s)} /* */" % e,
                    ):
            with self.subTest(css):
                with self.assertRaises(PublishError, msg=css):
                    publish.check_brand(self.style(css))
                self.assertTrue(publish.outside_addresses(self.style(css)), css)
                self.assertTrue(publish.outside_addresses(spliced(self.style(css))), css)

    def test_a_comment_in_a_style_attribute_or_a_second_style_follows_the_same_rule(self):
        e = self.EVIL
        self.assertEqual(publish.outside_addresses('<p style="color:red /* url(%s) */">x</p>' % e), [])
        self.assertTrue(publish.outside_addresses('<p style="/* x */ background:url(%s)">x</p>' % e))
        self.assertTrue(publish.outside_addresses('<style>/* a</style><style>b{background:url(%s)}</style>' % e))

    def test_a_refused_brand_publishes_nothing(self):
        """render() is what makes the file; check_brand raises before any text of the file is made."""
        for css in (".a{background:url(%s)}" % self.EVIL, self.circle(selector=".card"), "@import 'x.css';",
                    '.a{content:"/*"} .b{background:url(%s)} /* */' % self.EVIL):
            text = real().replace("</style>", css + "</style>", 1)
            with self.subTest(css[:60]):
                with self.assertRaises(PublishError):
                    publish.render({"data": {}, "sections": [], "tabs": []}, text, "2026-10-28", "t")

if __name__ == "__main__":
    unittest.main()
