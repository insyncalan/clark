"""#66a: the rich-text cleaner (src/clark/sanitise.py): clean_html and plain_text.

Run: python3 dev/run_tests.py test_sanitise
Every string is made up: hostile markup written from the usual XSS evasion patterns, addresses at example.com or the
reserved .invalid, no real names or data. What is asserted, for every hostile input: the output holds only the allow-list
(tags and attributes, checked by parsing it again), every `<` in it starts an allowed tag, tags are balanced, no link
points anywhere but http:, https:, mailto: or #; cleaning the output again changes nothing; and it takes well under a second.
"""
import inspect
import random
import re
import sys
import time
import unittest
from html.parser import HTMLParser

from _paths import ROOT   # noqa: F401  (puts src/ on the path)
from clark import sanitise
from clark.sanitise import MAX_CHARS, MAX_DEPTH, SanitiseError, clean_html, plain_text
from _growth import assert_growth

TAGS = {"p", "br", "strong", "em", "s", "h1", "h2", "h3", "ul", "ol", "li", "blockquote", "hr", "a", "input"}
VOID = {"br", "hr", "input"}
LINK = re.compile(r"(?:https?://[^/?#\s]|mailto:\S|#)", re.I)


class Audit(HTMLParser):
    """Reads cleaned output the way a browser's parser would and notes everything that should not be there."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.problems, self.tags = [], [], 0

    def handle_starttag(self, tag, attrs):
        self.tags += 1
        names = [n for n, _ in attrs]
        given = dict(attrs)
        if tag not in TAGS:
            self.problems.append(f"tag {tag} is not allowed")
        elif tag == "a":
            if names != ["href", "rel"] or given["rel"] != "noopener noreferrer" or not LINK.match(given["href"]):
                self.problems.append(f"bad link {attrs}")
            compact = re.sub(r"[\s\x00-\x20]", "", given.get("href") or "").lower()
            if re.match(r"(javascript|vbscript|data|file|livescript):|//", compact):
                self.problems.append(f"script-capable link {attrs}")
        elif tag == "input":
            if given.get("type") != "checkbox" or names[0] != "type" or not set(names) <= {"type", "checked", "disabled"}:
                self.problems.append(f"bad input {attrs}")
        elif names:
            self.problems.append(f"{tag} has attributes {attrs}")
        if tag not in VOID:
            self.stack.append(tag)

    def handle_startendtag(self, tag, attrs):
        self.problems.append(f"self-closing {tag}")

    def handle_endtag(self, tag):
        self.tags += 1
        if tag in VOID or not self.stack or self.stack.pop() != tag:
            self.problems.append(f"end tag {tag} does not match")

    def handle_comment(self, data):
        self.problems.append("comment")

    def handle_decl(self, decl):
        self.problems.append("declaration")

    def handle_pi(self, data):
        self.problems.append("processing instruction")

    def unknown_decl(self, data):
        self.problems.append("marked section")


def audit(out):
    """The problems found in `out` (an empty list if it is clean)."""
    a = Audit()
    a.feed(out)
    a.close()
    problems = a.problems + [f"{t} left open" for t in a.stack]
    if out.count("<") != a.tags:
        problems.append("a < that is not a tag")
    if re.search("[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]", out):
        problems.append("control character")
    return problems


class Base(unittest.TestCase):
    def assertSafe(self, source, gone=(), label=None):
        started = time.monotonic()
        out = clean_html(source)
        took = time.monotonic() - started
        label = label or repr(source)[:90]
        self.assertEqual(audit(out), [], f"{label} -> {out!r}")
        self.assertEqual(clean_html(out), out, f"not idempotent: {label} -> {out!r}")
        self.assertLess(took, 1.0, label)
        low = out.lower()
        for word in ((gone,) if isinstance(gone, str) else gone):
            self.assertNotIn(word.lower(), low, f"{word!r} survived: {label} -> {out!r}")
        return out


# ===== Hostile markup: (input, text that must not survive). Most cases end up as nothing or as plain text. =====
SCRIPTS = [
    "<script>alert(1)</script>",
    "<SCRIPT SRC=https://example.com/xss.js></SCRIPT>",
    "<ScRiPt>alert(1)</sCrIpT>",
    "<script >alert(1)</script >",
    "<script\n>alert(1)</script\n>",
    "<script\t>alert(1)</script>",
    "<script/xss src=https://example.com/x.js>alert(1)</script>",
    "<script/>alert(1)</script>",
    "<script>alert(1)",                                           # never closed: the rest of the field goes
    "<script>alert(1)</script>after",
    "<script>alert('</script>')</script>",
    "<script type=text/plain>alert(1)</script>",
    "<script language=javascript>alert(1)</script>",
    "<scr\x00ipt>alert(1)</script>",
    "<script\x00>alert(1)</script>",
    "<scr\x01ipt>alert(1)</scr\x02ipt>",
    "<<script>alert(1)//<</script>",
    "<scr<script>ipt>alert(1)</scr</script>ipt>",
    "<scr<script>ipt>alert(1)</script>",
    "</script><script>alert(1)</script>",
    "<script>a<script>alert(1)</script>b</script>c",
    "<a href=\"https://example.com/\"><script>alert(1)</script>link</a>",
    "<p>one<script>alert(1)</script>two</p>",
    "<script>document.write('<img src=x onerror=alert(1)>')</script>",
    "<script src=data:text/javascript,alert(1)></script>",
    "<script>/*</script><p>shown</p><script>*/alert(1)</script>",
]
STYLES = [
    "<style>body{background:url(javascript:alert(1))}</style>",
    "<style>@import 'https://example.com/x.css';p{color:red}</style>",
    "<STYLE>li {list-style-image: url(\"javascript:alert(1)\");}</STYLE>",
    "<style>p{behavior:url(x.htc);expression(alert(1))}</style>",
    "<style></style><p>x</p>",
    "<p style=\"background:url(javascript:alert(1))\">x</p>",
    "<p style='expression(alert(1))'>x</p>",
    "<strong style=\"color:red\">x</strong>",
    "<xss style=\"behavior:url(x.htc)\">x</xss>",
    "<style>p{}</style",
]
EVENTS = [
    "<img src=x onerror=alert(1)>",
    "<img src=\"x\" onerror=\"alert(1)\"//",
    "<img/src=x/onerror=alert(1)>",
    "<img src=x onerror=alert(1)//",
    "<IMG SRC=\"javascript:alert('XSS');\">",
    "<IMG SRC=javascript:alert('XSS')>",
    "<IMG SRC=JaVaScRiPt:alert('XSS')>",
    "<IMG SRC=javascript:alert(&quot;XSS&quot;)>",
    "<IMG SRC=`javascript:alert(\"XSS\")`>",
    "<IMG SRC=&#106;&#97;&#118;&#97;&#115;&#99;&#114;&#105;&#112;&#116;&#58;&#97;&#108;&#101;&#114;&#116;&#40;&#39;XSS&#39;&#41;>",
    "<IMG DYNSRC=\"javascript:alert('XSS')\">",
    "<IMG LOWSRC=\"javascript:alert('XSS')\">",
    "<body onload=alert(1)>text",
    "<body background=\"javascript:alert(1)\">text",
    "<p onclick=alert(1)>x</p>",
    "<p ONCLICK=alert(1)>x</p>",
    "<p onmouseover=\"alert(1)\" class=a id=b data-x=c>x</p>",
    "<p onclick = 'alert(1)' >x</p>",
    "<p\nonclick\n=\nalert(1)>x</p>",
    "<p/onclick=alert(1)>x</p>",
    "<em onmouseover=alert(1)>x</em>",
    "<li onclick=alert(1)>x</li>",
    "<a href=\"https://example.com/\" onmouseover=\"alert(1)\">x</a>",
    "<a href=\"https://example.com/\" target=_blank onclick=alert(1) style=x download>x</a>",
    "<a href='https://example.com/\" onmouseover=\"alert(1)'>x</a>",
    "<a href=https://example.com/ onfocus=alert(1) autofocus>x</a>",
    "<input type=checkbox onfocus=alert(1) autofocus>",
    "<input type=checkbox checked onclick=alert(1)>",
    "<input type=checkbox value=x name=y id=z class=w style=v>",
    "<input type=image src=x onerror=alert(1)>",
    "<input type=text value=x onfocus=alert(1) autofocus>",
    "<input type=\"checkbox\" formaction=\"javascript:alert(1)\">",
    "<input>",
    "<input type=checkbox/>",
    "<details open ontoggle=alert(1)>x</details>",
    "<marquee onstart=alert(1)>x</marquee>",
    "<video><source onerror=alert(1)></video>",
    "<audio src=x onerror=alert(1)>",
    "<video poster=javascript:alert(1)>",
    "<div onpointerover=alert(1)>x</div>",
    "<table background=javascript:alert(1)><tr><td>x</td></tr></table>",
    "<button formaction=javascript:alert(1)>x</button>",
    "<select onfocus=alert(1) autofocus><option>x</option></select>",
    "<keygen onfocus=alert(1) autofocus>",
    "<isindex action=javascript:alert(1) type=image>",
    "<bgsound src=javascript:alert(1)>",
    "<layer src=https://example.com/x.html></layer>",
]
FRAMES = [
    "<iframe src=\"javascript:alert(1)\"></iframe>",
    "<iframe srcdoc=\"<script>alert(1)</script>\"></iframe>",
    "<iframe src=https://example.com/></iframe>after",
    "<iframe><script>alert(1)</script></iframe>",
    "<IFRAME SRC=# onmouseover=\"alert(document.cookie)\"></IFRAME>",
    "<iframe>alert(1)",
    "<frameset onload=alert(1)><frame src=x></frameset>",
    "<object data=\"javascript:alert(1)\"></object>",
    "<object data=\"data:text/html,<script>alert(1)</script>\">alert(1)</object>",
    "<embed src=\"javascript:alert(1)\">",
    "<embed src=data:image/svg+xml;base64,PHN2Zz48L3N2Zz4=>",
    "<applet code=Evil.class>alert(1)</applet>",
    "<form action=\"javascript:alert(1)\"><input type=submit>alert(1)</form>",
    "<form><button formaction=javascript:alert(1)>alert(1)</button></form>",
    "<meta http-equiv=\"refresh\" content=\"0;url=javascript:alert(1)\">text",
    "<meta charset=utf-7>+ADw-script+AD4-alert(1)+ADw-/script+AD4-",
    "<link rel=stylesheet href=\"javascript:alert(1)\">text",
    "<link rel=import href=https://example.com/x.html>text",
    "<base href=\"javascript:alert(1)//\"><a href=x>x</a>",
    "<base href=https://example.com/><p>x</p>",
    "<head><title>alert(1)</title></head><p>x</p>",
    "<title>alert(1)</title>",
    "<textarea><script>alert(1)</script></textarea>",
    "<textarea>alert(1)",
    "<xmp><script>alert(1)</script></xmp>",
    "<plaintext><script>alert(1)</script>",
    "<noembed><script>alert(1)</script></noembed>",
    "<noframes><script>alert(1)</script></noframes>",
]
FOREIGN = [
    "<svg onload=alert(1)>",
    "<svg/onload=alert(1)>x",
    "<svg><script>alert(1)</script></svg>",
    "<svg><script href=data:,alert(1) /></svg>",
    "<svg><animate onbegin=alert(1) attributeName=x dur=1s></svg>",
    "<svg><a xlink:href=\"javascript:alert(1)\"><text x=0 y=20>alert(1)</text></a></svg>",
    "<svg><foreignObject><iframe srcdoc=\"<script>alert(1)</script>\"></iframe></foreignObject></svg>",
    "<svg><style>*{x:y}</style><img src=x onerror=alert(1)></svg>",
    "<svg><set attributeName=onmouseover to=alert(1)></svg>",
    "<svg><use href=\"data:image/svg+xml,<svg id='x' xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>#x\"></svg>",
    "<svg/>alert(1)",
    "<svg><svg/>alert(1)</svg>",
    "<math><mi xlink:href=\"javascript:alert(1)\">alert(1)</mi></math>",
    "<math href=\"javascript:alert(1)\">alert(1)</math>",
    "<math><maction actiontype=statusline#http://example.com xlink:href=\"javascript:alert(1)\">alert(1)</maction></math>",
    "<x:script xmlns:x=\"http://www.w3.org/1999/xhtml\">alert(1)</x:script>",
    "<html:script xmlns:html=\"http://www.w3.org/1999/xhtml\">alert(1)</html:script>",
    "<svg:script>alert(1)</svg:script>",
    "<script:foo>alert(1)</script:foo>",
    "<p xmlns=\"http://www.w3.org/1999/xhtml\" xmlns:xlink=\"http://www.w3.org/1999/xlink\">x</p>",
    "<p xml:base=\"javascript:\">x</p>",
]
MUTATION = [
    "<svg></p><style><a id=\"</style><img src=1 onerror=alert(1)>\">",
    "<math><mtext><table><mglyph><style><!--</style><img title=\"--&gt;&lt;img src=1 onerror=alert(1)&gt;\">",
    "<form><math><mtext></form><form><mglyph><style></math><img src onerror=alert(1)>",
    "<noscript><p title=\"</noscript><img src=x onerror=alert(1)>\">",
    "<noscript><style></noscript><img src=x onerror=alert(1)>",
    "<template><script>alert(1)</script></template>",
    "<template><img src=x onerror=alert(1)></template>",
    "<p title=\"<script>alert(1)</script>\">x</p>",
    "<a title='\"><script>alert(1)</script>'>x</a>",
    "<a href=\"https://example.com/\" title=\"</a><script>alert(1)</script>\">x</a>",
    "<table><tr><td><style></table><img src=x onerror=alert(1)></style>",
    "<select><template><select><img src=x onerror=alert(1)></select></template></select>",
    "<listing><img src=x onerror=alert(1)></listing>",
    "<p><svg><p><style><img src=x onerror=alert(1)></style></p></svg></p>",
    "<a href=\"x\" id=\"</a><img src=x onerror=alert(1)>\">y</a>",
    "<div><style><div></style><img src=x onerror=alert(1)>",
    "<img src=x onerror=alert(1) <p>text</p>",
    "<p <script>alert(1)</script>>text</p>",
    "<p\">alert(1)<script>alert(2)</script>",
    "<a href=\"https://example.com/\"<script>alert(1)</script>>x</a>",
]
COMMENTS = [
    "<!--<script>alert(1)</script>-->after",
    "<!--[if gte IE 4]><script>alert(1)</script><![endif]-->after",
    "<!--><script>alert(1)</script>-->after",
    "<!---><script>alert(1)</script>-->after",
    "<!-- --!><script>alert(1)</script>-->after",
    "<!-- unclosed <script>alert(1)</script>",
    "<!--",
    "<!---",
    "<!-- a -- b -->after",
    "<![CDATA[<script>alert(1)</script>]]>after",
    "<![CDATA[ unclosed <script>alert(1)</script>",
    "<![if !IE]><script>alert(1)</script><![endif]>after",
    "<![endif]-->after",
    "<![",
    "<?php echo '<script>alert(1)</script>'; ?>after",
    "<?xml version=\"1.0\"?><script>alert(1)</script>",
    "<?",
    "<!DOCTYPE html><p>x</p>",
    "<!DOCTYPE html [<!ENTITY x \"<script>alert(1)</script>\">]>&x;",
    "<!ENTITY x SYSTEM \"file:///etc/passwd\">&x;",
    "<!>after",
    "</>after",
    "</ script>alert(1)",
    "</ >after",
    "</p/><script>alert(1)</script>",
]
SHAPES = [
    "<p><strong><em>x",
    "<p>one<p>two<p>three",
    "<ul><li>one<li>two<ul><li>three</ul><li>four",
    "<ol><li><p>a<li><p>b</ol>",
    "<h1>a<h2>b<h3>c",
    "<p><h1>a</h1>b</p>",
    "<p><ul><li>a</li></ul></p>",
    "<blockquote><p>a<blockquote><p>b</blockquote>",
    "</p></li></ul></strong></a>text",
    "<a href=\"https://example.com/\"><a href=\"https://example.org/\">x</a></a>",
    "<strong><em>a</strong></em>b",
    "<strong>a<p>b</strong>c</p>",
    "<br/><br /><br></br><hr/>",
    "<hr><hr/><hr />",
    "<p/>text</p/>",
    "<p>a</p></p></p>",
    "<li>orphan",
    "<>",
    "< script>alert(1)</ script>",
    "<a<b>c",
    "<a href=\"https://example.com/",
    "<a href=\"https://example.com/\"",
    "<p class=\"a",
    "<p class=a",
    "<p",
    "<scr",
    "<s",
    "<",
    "<<",
    "<<<>>>",
    "a < b > c",
    "<p>1 < 2 and 3 > 2</p>",
    "<!",
    "<p>a</p\n",
    "<p =\"x\">a</p>",
    "<p \"=x>a</p>",
]
ENCODED = [
    "&lt;script&gt;alert(1)&lt;/script&gt;",
    "&#60;script&#62;alert(1)&#60;/script&#62;",
    "&#x3c;script&#x3e;alert(1)&#x3c;/script&#x3e;",
    "&amp;lt;script&amp;gt;alert(1)&amp;lt;/script&amp;gt;",
    "&lt;img src=x onerror=alert(1)&gt;",
    "&lt;a href=\"javascript:alert(1)\"&gt;x&lt;/a&gt;",
    "&#0000060script&#0000062alert(1)",
    "&lt",
    "&#",
    "&#x",
    "&#99999999999999999999;&#x9999999999999999;",
    "&#" + "9" * 6000 + ";",
    "&#xD800;&#xDFFF;&#0;&#1;&#x7f;&#x80;&NotARealEntity;&amp",
    "\ud800\udfff\ud800",
    "<p>a\x00b\x01c\x7fd</p>",
    "+ADw-script+AD4-alert(1)+ADw-/script+AD4-",
    "<p>\u202ereversed\u202c</p>",
    "<p>\u0000\u0000</p>",
]

HOSTILE = SCRIPTS + STYLES + EVENTS + FRAMES + FOREIGN + MUTATION + COMMENTS + SHAPES + ENCODED

class HostileMarkup(Base):
    def test_every_case_is_safe(self):
        """The count is part of the test: a quiet edit of the lists above must not shrink the coverage."""
        self.assertGreaterEqual(len(HOSTILE), 200)
        for source in HOSTILE:
            self.assertSafe(source)

    def test_no_event_handler_style_or_script_text_survives_in_a_tag(self):
        """Not just allowed tags: no attribute value of any kind comes through except a link's address and a checkbox's flags."""
        for source in SCRIPTS + STYLES + EVENTS + FRAMES + FOREIGN + MUTATION + COMMENTS:
            out = re.sub(r'href="[^"]*"', 'href=""', clean_html(source))        # a link's address is checked on its own
            for word in ("onerror=", "onclick=", "onload=", "onmouseover=", "onfocus=", "style=", "srcdoc=", "class=", "id=",
                         "formaction=", "target=", "xlink", "<script", "<style", "<img", "<svg", "<iframe", "<object",
                         "<embed", "<form", "<meta", "<link", "<base", "<math"):
                self.assertNotIn(word, out.lower(), f"{source!r} -> {out!r}")

    def test_code_inside_dropped_elements_is_gone_not_shown(self):
        for source in ("<script>alert(1)</script>", "<SCRIPT>alert(1)</SCRIPT>x", "<style>p{x:expression(alert(1))}</style>x",
                       "<svg><script>alert(1)</script></svg>", "<iframe><script>alert(1)</script></iframe>",
                       "<noscript><script>alert(1)</script></noscript>", "<template><script>alert(1)</script></template>",
                       "<math><mtext>alert(1)</mtext></math>", "<form><b>alert(1)</b></form>", "<textarea>alert(1)</textarea>",
                       "<object>alert(1)</object>", "<title>alert(1)</title>", "<xmp>alert(1)</xmp>",
                       "<script>alert(1)", "<style>alert(1)", "<!--alert(1)-->", "<![CDATA[alert(1)]]>", "<?alert(1)?>"):
            out = self.assertSafe(source, gone="alert")
            self.assertIn(out, ("", "x"), source)

    def test_exact_results_for_the_common_attacks(self):
        clean = clean_html
        self.assertEqual(clean("<script>alert(1)</script>"), "")
        self.assertEqual(clean("<SCRIPT>zq()</SCRIPT>x"), "x")
        self.assertEqual(clean("<script>a<script>b</script>c</script>d"), "c" + "d",
                         "a script ends at its first end tag, as in a browser; what follows is text")
        self.assertEqual(clean("<svg><script>a</script><circle/></svg>x"), "x")
        self.assertEqual(clean("<p>a</p><form action=x><input name=a>say</form><p>c</p>"), "<p>a</p><p>c</p>")
        self.assertEqual(clean("<link rel=stylesheet href=https://x.invalid/a.css><meta http-equiv=refresh>t"), "t")
        self.assertEqual(clean("<p style='color:red' onclick='x()' class=c id=i data-a=b>t</p>"), "<p>t</p>")
        self.assertEqual(clean("<img src=x onerror=alert(1)>t"), "t")
        self.assertEqual(clean('<img src="data:image/png;base64,iVBORw0KGgo=" alt="dot">t'), "t", "no images in the allow-list")
        self.assertEqual(clean("<p>one<b>two</b></p>"), "<p>onetwo</p>", "b is not strong: the tag goes, the text stays")
        self.assertEqual(clean("<p>one<strong>two"), "<p>one<strong>two</strong></p>", "an open tag is closed")
        self.assertEqual(clean("a</strong>b"), "ab", "a stray end tag goes")
        self.assertEqual(clean("<scr<script>ipt>alert(1)</script>"), "ipt&gt;alert(1)",
                         "`scr<script` is not a tag name we know: its tag goes and the rest is escaped text, harmless")
        self.assertEqual(clean("<!--<script>-->k"), "k")
        self.assertEqual(clean("<![if IE]>x<![endif]>"), "x")
        self.assertEqual(clean("<?php echo 1 ?>z"), "z")
        self.assertEqual(clean("<noscript><p>x</p></noscript>y"), "y")
        self.assertEqual(clean("<template><p>x</p></template>y"), "y")
        self.assertEqual(clean("<div><span class=a>text</span></div>"), "text", "unknown tags unwrap")
        self.assertEqual(clean("<table><tr><td>cell</td></tr></table>"), "cell")
        self.assertEqual(clean("<p>a</p><p>b"), "<p>a</p><p>b</p>")
        self.assertEqual(clean("<p>a<p>b"), "<p>a</p><p>b</p>", "a p ends at the next p")
        self.assertEqual(clean("<ul><li>a<li>b</ul>"), "<ul><li>a</li><li>b</li></ul>", "an li ends at the next li")
        self.assertEqual(clean("<p>a<ul><li>b</li></ul>"), "<p>a</p><ul><li>b</li></ul>", "a list ends the p")
        self.assertEqual(clean("<ul><li>a<ul><li>b</ul><li>c</ul>"),
                         "<ul><li>a<ul><li>b</li></ul></li><li>c</li></ul>", "a nested list keeps its parent item open")
        self.assertEqual(clean("<br/><br /><hr/>"), "<br><br><hr>")
        self.assertEqual(clean("<h4>x</h4><h6>y</h6>"), "x\ny", "only h1 to h3 stay as tags; the others leave a line break")
        self.assertEqual(clean("<a href=\"https://example.com/\"><a href=\"https://example.org/\">x</a></a>"),
                         '<a href="https://example.com/" rel="noopener noreferrer"></a>'
                         '<a href="https://example.org/" rel="noopener noreferrer">x</a>',
                         "an a inside an a closes the first, as in a browser")

    def test_text_is_escaped_and_comes_back_as_text(self):
        clean = clean_html
        self.assertEqual(clean("&lt;script&gt;alert(1)&lt;/script&gt;"), "&lt;script&gt;alert(1)&lt;/script&gt;",
                         "text that looks like markup stays text")
        self.assertEqual(clean("&#60;script&#62;"), "&lt;script&gt;")
        self.assertEqual(clean("&amp;lt;"), "&amp;lt;")
        self.assertEqual(clean("a & b"), "a &amp; b")
        self.assertEqual(clean("a &amp b"), "a &amp; b")
        self.assertEqual(clean("a < b > c"), "a &lt; b &gt; c")
        self.assertEqual(clean("5<6"), "5&lt;6")
        self.assertEqual(clean("\"quoted\" and 'single'"), "\"quoted\" and 'single'", "quotes are fine in text")
        self.assertEqual(clean("a\xa0b"), "a&nbsp;b")
        self.assertEqual(clean("a&nbsp;b"), "a&nbsp;b")
        self.assertEqual(clean("caf\u00e9 \u2013 \u65e5\u672c\u8a9e \U0001f600"), "caf\u00e9 \u2013 \u65e5\u672c\u8a9e \U0001f600")
        self.assertEqual(clean("&copy;&eacute;&#233;&#xe9;"), "\u00a9\u00e9\u00e9\u00e9")
        self.assertEqual(clean("a\x00b\x01c\x7fd"), "abcd", "control characters go")
        self.assertEqual(clean("a\tb\nc\r\nd"), "a\tb\nc\r\nd", "tab, newline and carriage return stay")
        self.assertEqual(clean("&#0;&#1;&#x7f;x"), "\ufffdx", "a decoded NUL is U+FFFD (as in a browser); other controls go")
        self.assertEqual(clean("&#99999999999999999999;"), "\ufffd")
        self.assertEqual(clean("\ud800x"), "x", "a lone surrogate would break the UTF-8 file: it goes")

    def test_a_tag_never_carries_a_second_value_out(self):
        out = clean_html("<a href='https://example.com/\" onmouseover=\"alert(1)'>x</a>")
        self.assertEqual(out, '<a href="https://example.com/&quot;%20onmouseover=&quot;alert(1)" rel="noopener noreferrer">x</a>')
        self.assertEqual(audit(out), [])
        out = clean_html('<a href="https://example.com/?a=1&b=2&amp;c=3">x</a>')
        self.assertEqual(out, '<a href="https://example.com/?a=1&amp;b=2&amp;c=3" rel="noopener noreferrer">x</a>')
        out = clean_html('<a href=https://example.com/<b>>x</a>')
        self.assertEqual(audit(out), [])


# ===== Links =====
BAD_HREFS = [
    "javascript:alert(1)", "JAVASCRIPT:alert(1)", "JaVaScRiPt:alert(1)", " javascript:alert(1)", "\tjavascript:alert(1)",
    "\n\r javascript:alert(1)", "\x01javascript:alert(1)", "\x00javascript:alert(1)", "\x1fjavascript:alert(1)",
    "\x0bjavascript:alert(1)", "\x0cjavascript:alert(1)", "java\x00script:alert(1)", "java\tscript:alert(1)",
    "java\nscript:alert(1)", "java\rscript:alert(1)", "j\ta\nv\ra\x00s\tcript:alert(1)", "jav&#x09;ascript:alert(1)",
    "jav&#x0A;ascript:alert(1)", "jav&#x0D;ascript:alert(1)", "jav&#9;ascript:alert(1)", "jav&#10;ascript:alert(1)",
    "jav&#13;ascript:alert(1)", "jav&Tab;ascript:alert(1)", "jav&NewLine;ascript:alert(1)", "&#106;avascript:alert(1)",
    "&#x6A;avascript:alert(1)", "&#X6a;avascript:alert(1)", "&#0000106avascript:alert(1)", "&#x00006Aavascript:alert(1)",
    "&#106&#97&#118&#97&#115&#99&#114&#105&#112&#116&#58alert(1)",
    "&#x6A&#x61&#x76&#x61&#x73&#x63&#x72&#x69&#x70&#x74&#x3A alert(1)", "javascript&colon;alert(1)",
    "javascript&#58;alert(1)", "javascript&#x3a;alert(1)", "javascript&#0000058alert(1)", "&#14;javascript:alert(1)",
    "&#1;javascript:alert(1)", "&#32;javascript:alert(1)", "java&#0;script:alert(1)", "javascript\\u003aalert(1)",
    "\\u006aavascript:alert(1)", "\\x6aavascript:alert(1)", "%6aavascript:alert(1)", "java%0ascript:alert(1)",
    "java script:alert(1)", "\u00a0javascript:alert(1)", "\ufeffjavascript:alert(1)", "\u200bjavascript:alert(1)",
    "java\u200bscript:alert(1)", "java\u00adscript:alert(1)", "\u2028javascript:alert(1)", "\u3000javascript:alert(1)",
    "\uff4aavascript:alert(1)", "javascript\uff1aalert(1)", "javascript:", "vbscript:msgbox(1)", "VBScript:x",
    "livescript:alert(1)", "mocha:alert(1)", "jar:https://example.com/x.jar!/", "data:text/html,<script>alert(1)</script>",
    "data:text/html;base64,PHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pg==", "DATA:text/html,x", " data:text/html,x", "data:image/svg+xml,<svg/>",
    "file:///etc/passwd", "FILE:///C:/x", "ftp://example.com/x", "gopher://example.com/", "ws://example.com/", "blob:https://example.com/x",
    "about:blank", "view-source:https://example.com/", "chrome://settings", "tel:+441234567890", "sms:+441234567890", "callto:x",
    "//example.com/x", "///example.com/x", "\\\\example.com\\x", "/\\example.com", "\\/example.com", "/relative/path",
    "relative/path", "../up", "?q=1", ".", "x", "http:", "http:example.com", "https:", "https://", "https:///", "mailto:", "http:\\\\example.com",
    "", " ", "\t\n", "\x00", "https://example.com/\u200b", "https://example.com/a\u2028b",
    "https://example.com/a\u00a0b", "https://example.com/a\u2029b", "https://example.com/a" + "b" * 9000,
]
GOOD_HREFS = [
    ("https://example.com/", "https://example.com/"),
    ("http://example.com/a/b?c=d#e", "http://example.com/a/b?c=d#e"),
    ("HTTPS://EXAMPLE.COM/A", "HTTPS://EXAMPLE.COM/A"),
    ("  https://example.com/  ", "https://example.com/"),
    ("\thttps://example.com/\n", "https://example.com/"),
    ("https://exam\nple.com/pa\tth", "https://example.com/path"),
    ("https://example.com/a b", "https://example.com/a%20b"),
    ("https://example.com/caf\u00e9", "https://example.com/caf\u00e9"),
    ("https://example.com", "https://example.com"),
    ("https://example.com?x=1", "https://example.com?x=1"),
    ("https://example.com#top", "https://example.com#top"),
    ("https://user@example.com:8443/x", "https://user@example.com:8443/x"),
    ("http://127.0.0.1:8000/x", "http://127.0.0.1:8000/x"),
    ("mailto:team@example.com", "mailto:team@example.com"),
    ("MAILTO:team@example.com?subject=Hello%20there", "MAILTO:team@example.com?subject=Hello%20there"),
    ("#next", "#next"),
    ("#", "#"),
    ("#section-2", "#section-2"),
    ("https://example.com/?a=1&amp;b=2", "https://example.com/?a=1&b=2"),
    ("https://example.com/?x=javascript:alert(1)", "https://example.com/?x=javascript:alert(1)"),
    ("&#104;ttps://example.com/", "https://example.com/"),
    ("https://exa\x00mple.com/ok\x01", "https://example.com/ok"),
    ("https://example.com/a\x7fb\x85c", "https://example.com/abc"),
]


class Links(Base):
    def test_unsafe_addresses_leave_the_text_and_no_link(self):
        for href in BAD_HREFS:
            for quoted in ('"%s"', "'%s'"):
                if quoted == "'%s'" and ("'" in href):
                    continue
                source = "<a href=%s>text</a>" % (quoted % (href if quoted[0] == '"' else href))
                out = self.assertSafe(source, label=repr(href)[:80])
                self.assertEqual(out, "text", repr(href)[:80])
        self.assertGreaterEqual(len(BAD_HREFS), 100)

    def test_unquoted_and_unusual_attribute_forms(self):
        for source in ("<a href=javascript:alert(1)>text</a>", "<a href = javascript:alert(1) >text</a>", "<a HREF=JAVASCRIPT:x>text</a>",
                       "<a href=\"javascript:alert(1)\" href=\"https://example.com/\">text</a>", "<a href>text</a>", "<a href=>text</a>",
                       "<a href=\"\">text</a>", "<a>text</a>", "<a name=x>text</a>", "<a xlink:href=https://example.com/>text</a>",
                       "<a src=https://example.com/>text</a>", "<a data-href=https://example.com/>text</a>",
                       "<a href/=https://example.com/>text</a>"):
            self.assertEqual(self.assertSafe(source), "text", source)

    def test_the_first_of_a_repeated_href_counts(self):
        self.assertEqual(clean_html('<a href="https://example.com/a" href="javascript:x">t</a>'),
                         '<a href="https://example.com/a" rel="noopener noreferrer">t</a>')
        self.assertEqual(clean_html('<a href="javascript:x" href="https://example.com/a">t</a>'), "t")

    def test_safe_addresses_stay_with_rel_and_nothing_else(self):
        for given, expected in GOOD_HREFS:
            out = self.assertSafe('<a href="%s">t</a>' % given)
            self.assertEqual(out, '<a href="%s" rel="noopener noreferrer">t</a>' % expected.replace("&", "&amp;"), given)

    def test_other_link_attributes_are_dropped_and_rel_is_ours(self):
        out = clean_html('<a href="https://example.com/" target="_blank" rel="opener" title="t" class="c" style="x" download '
                         'onclick="x()" data-a="b" hreflang="en" ping="https://example.org/">text</a>')
        self.assertEqual(out, '<a href="https://example.com/" rel="noopener noreferrer">text</a>')

    def test_link_with_formatting_inside(self):
        out = clean_html('<p><a href="https://example.com/"><strong>bold</strong> and <em>em</em></a></p>')
        self.assertEqual(out, '<p><a href="https://example.com/" rel="noopener noreferrer"><strong>bold</strong> and <em>em</em></a></p>')

    def test_names_without_a_semicolon_stay_as_written_in_an_address(self):
        """The HTML rule for attributes: `&region=eu` is not (R)ion=eu. html.unescape would decode it, and differs by Python."""
        base = "https://example.com/?a=1&region=eu&timestamp=2&copy=3&shy=1"
        out = self.assertSafe('<a href="%s">t</a>' % base)
        self.assertEqual(out, '<a href="%s" rel="noopener noreferrer">t</a>' % base.replace("&", "&amp;"))
        self.assertEqual(self.assertSafe('<a href="%s">t</a>' % base.replace("&", "&amp;")), out, "the saved form reads back the same")
        self.assertEqual(self.assertSafe("<a href=%s>t</a>" % base), out, "unquoted")
        self.assertEqual(self.assertSafe("<a href='%s'>t</a>" % base), out, "single quoted")
        self.assertEqual(self.assertSafe('<a href="mailto:a@example.com?subject=hi&copy=1&reg=2">t</a>'),
                         '<a href="mailto:a@example.com?subject=hi&amp;copy=1&amp;reg=2" rel="noopener noreferrer">t</a>')
        for given, expected in (
                ("&copy=3", "&copy=3"),                         # next is =
                ("&copyx", "&copyx"), ("&copyX", "&copyX"), ("&copy1", "&copy1"), ("&COPY=1", "&COPY=1"),   # next is a letter or digit
                ("&notit;", "&notit;"), ("&reg0", "&reg0"), ("&amp=1", "&amp=1"), ("&lt=1", "&lt=1"), ("&sect=", "&sect="),
                ("&copy-x", "\u00a9-x"), ("&copy/x", "\u00a9/x"), ("&copy.", "\u00a9."), ("&copy", "\u00a9"),   # anything else: decoded
                ("&copy&x", "\u00a9&x"), ("&copy#x", "\u00a9#x"), ("&amp.", "&."), ("&reg~", "\u00ae~"),
                ("&copy;", "\u00a9"), ("&copy;x", "\u00a9x"), ("&copy;=1", "\u00a9=1"), ("&amp;region=eu", "&region=eu"),   # with a semicolon
                ("&para;b", "\u00b6b"), ("&AMP;x", "&x"), ("&not;", "\u00ac"),
                ("&#38;region=eu", "&region=eu"), ("&#x26;copy=3", "&copy=3"), ("&#169x", "\u00a9x"), ("&#xA9=", "\u00a9="),   # numeric
                ("&#169;1", "\u00a91"), ("&#38copy=3", "&copy=3"),
                ("&unknown=1", "&unknown=1"), ("&;", "&;"), ("&", "&"), ("&=", "&="), ("a&b", "a&b")):
            got = sanitise.decode(given, True)
            self.assertEqual(got, expected, given)
            self.assertSafe('<a href="https://example.com/?q=%s">t</a>' % given, label=given)
            self.assertEqual(clean_html('<a href="https://example.com/?q=%s">t</a>' % given),
                             '<a href="https://example.com/?q=%s" rel="noopener noreferrer">t</a>' % expected.replace("&", "&amp;"), given)
        self.assertEqual(len(sanitise.LEGACY), 106, "html.entities' own table of names a browser reads without their semicolon")

    def test_text_still_decodes_the_old_forms(self):
        self.assertEqual(sanitise.decode("&copy=1 &region=eu &shy"), "\u00a9=1 \u00aeion=eu \u00ad")
        self.assertEqual(clean_html("<p>&copy=1 &amp &lt</p>"), "<p>\u00a9=1 &amp; &lt;</p>")
        self.assertEqual(plain_text("<p>&copy=1</p>"), "\u00a9=1")

    def test_the_rules_still_apply_after_decoding_an_address(self):
        for given in ("javascript:x?a=1&region=eu", "&#106;avascript:alert(1)&copy=1", "javascript&colon;alert(1)", "java&Tab;script:x",
                      "&#x6a;avascript&#58;x", "data:text/html,x&copy=1", "&copy=1", "//example.com/?a=1&copy=1"):
            self.assertEqual(self.assertSafe('<a href="%s">t</a>' % given), "t", given)

    def test_unassigned_characters_in_an_address_give_one_answer_on_every_python(self):
        """unicodedata's table is a different Unicode version on each Python. U+1FAE9 is unassigned in Unicode 13 (Python 3.9) and
        assigned later: the link is accepted on both. U+0890 and U+13439 are format characters assigned in Unicode 14 and 15:
        refused on both. Noncharacters are refused, and so are the format and control characters of every version."""
        for text in ("\U0001fae9", "\u0378", "\U000e0080", "\U0002fffd", "\u00e9\u65e5"):
            self.assertEqual(self.assertSafe('<a href="https://example.com/%s">t</a>' % text),
                             '<a href="https://example.com/%s" rel="noopener noreferrer">t</a>' % text, ascii(text))
        for text in ("\u0890", "\u0891", "\U00013439", "\U0001343f", "\U00013430", "\ufdd0", "\ufdef", "\ufffe", "\uffff",
                     "\U0001fffe", "\U0010ffff", "\U0010fffe", "\u200b", "\u00ad", "\U000e0001", "\ue000", "\U000f0000", "\u2028",
                     "\u3000", "\u00a0"):
            self.assertEqual(self.assertSafe('<a href="https://example.com/%s">t</a>' % text), "t", ascii(text))
        self.assertEqual(clean_html('<a href="https://example.com/a b">t</a>'),
                         '<a href="https://example.com/a%20b" rel="noopener noreferrer">t</a>', "a plain space is still allowed")


# ===== Checklist items =====
class Checklist(Base):
    def test_checkbox_keeps_only_checked_and_disabled(self):
        self.assertEqual(clean_html("<ul><li><input type=checkbox>a</li></ul>"), '<ul><li><input type="checkbox">a</li></ul>')
        self.assertEqual(clean_html('<input type="CheckBox" checked="checked" disabled="disabled" name=n value=v id=i class=c onclick=x>'),
                         '<input type="checkbox" checked disabled>')
        self.assertEqual(clean_html("<input checked type=checkbox>"), '<input type="checkbox" checked>')
        self.assertEqual(clean_html("<input type=checkbox disabled>"), '<input type="checkbox" disabled>')
        self.assertEqual(clean_html("<input type=' checkbox '>"), '<input type="checkbox">')
        self.assertEqual(clean_html("<input type=checkbox type=text>"), '<input type="checkbox">', "the first type counts")
        self.assertEqual(clean_html("<input type=text type=checkbox>"), "")

    def test_other_inputs_and_a_checkbox_with_content_are_dropped(self):
        for source in ("<input>", "<input type=text>", "<input type=radio>", "<input type=image src=x>", "<input type=hidden value=x>",
                       "<input type=file>", "<input type=submit value=x>", "<input type=password>", "<input type=button>", "<INPUT TYPE=IMAGE>"):
            self.assertEqual(self.assertSafe(source), "", source)
        self.assertEqual(clean_html("<input type=checkbox>text</input>"), '<input type="checkbox">text')

    def test_the_tiptap_task_list_shape_loses_its_wrappers(self):
        """label, div and span are not on the allow-list (#66): the item is its input and its paragraph."""
        out = clean_html('<ul data-type="taskList"><li data-checked="true" data-type="taskItem"><label><input type="checkbox" '
                         'checked="checked"><span></span></label><div><p>Done</p></div></li></ul>')
        self.assertEqual(out, '<ul><li><input type="checkbox" checked><p>Done</p></li></ul>')


# ===== Already clean text =====
CLEAN = [
    "",
    "plain text, no tags",
    "<p>One paragraph.</p>",
    "<p>one</p><p>two &amp; three</p>",
    "<p></p>",
    "<p>caf\u00e9 \u2013 \u65e5\u672c\u8a9e \U0001f600</p>",
    "<h1>Heading one</h1><h2>Two</h2><h3>Three</h3><p>Body</p>",
    "<p>a<br>b<br>c</p><hr><p>d</p>",
    "<p><strong>bold</strong>, <em>italic</em>, <s>struck</s> and <strong><em>both</em></strong></p>",
    "<ul><li>one</li><li>two<ul><li>nested</li></ul></li></ul>",
    "<ol><li><p>first</p></li><li><p>second</p></li></ol>",
    "<blockquote><p>quoted</p><blockquote><p>twice</p></blockquote></blockquote>",
    '<p><a href="https://example.com/a?b=1&amp;c=2" rel="noopener noreferrer">link</a> and '
    '<a href="mailto:team@example.com" rel="noopener noreferrer">mail</a> and <a href="#next" rel="noopener noreferrer">here</a></p>',
    '<ul><li><input type="checkbox"><p>open</p></li><li><input type="checkbox" checked><p>done</p></li>'
    '<li><input type="checkbox" checked disabled><p>locked</p></li></ul>',
    "<p>5 &lt; 6 &amp;&amp; 7 &gt; 6, a&nbsp;b, \"quotes\" and 'single'</p>",
    "<p>&lt;script&gt;alert(1)&lt;/script&gt; is only text</p>",
    "<p>line one</p>\n<p>line two</p>\n",
    "  leading and trailing  ",
    "<p>tab\there</p>",
    "<h2>Status</h2>\n<ul>\n<li>On track</li>\n<li>Pilot live 12 November</li>\n</ul>\n",
]


class AlreadyClean(Base):
    def test_clean_fields_come_back_byte_for_byte(self):
        for source in CLEAN:
            self.assertEqual(clean_html(source), source, repr(source))
            self.assertEqual(audit(source), [], repr(source))

    def test_the_demo_style_fields(self):
        for source in ("<p>Pilot is live with <strong>two</strong> teams.</p><ul><li>Training done</li></ul>",
                       "<p>The client signed off the design on 14 October.</p>"):
            self.assertEqual(clean_html(source), source)

    def test_none_and_empty(self):
        self.assertEqual(clean_html(None), "")
        self.assertEqual(clean_html(""), "")
        self.assertEqual(plain_text(None), "")
        self.assertEqual(plain_text(""), "")

    def test_not_text(self):
        for value in (5, b"<p>x</p>", ["<p>x</p>"], {"a": 1}, 1.5, True):
            with self.assertRaises(SanitiseError):
                clean_html(value)
        self.assertTrue(issubclass(SanitiseError, ValueError))


# ===== Limits =====
class Limits(Base):
    def test_length(self):
        just = "a" * MAX_CHARS
        self.assertEqual(clean_html(just), just)
        with self.assertRaises(SanitiseError) as caught:
            clean_html(just + "a")
        self.assertIn("too long", str(caught.exception))
        self.assertIn("200,000", str(caught.exception))
        self.assertEqual(MAX_CHARS, 200_000)
        with self.assertRaises(SanitiseError):
            plain_text(just + "a")

    def test_the_message_says_which_count_it_is(self):
        """The number is the text as written, or the text once cleaned (150,000 ampersands are 750,000 once written as &amp;)."""
        for call in (clean_html, plain_text):
            with self.assertRaises(SanitiseError) as caught:
                call("a" * (MAX_CHARS + 1))
            message = str(caught.exception)
            self.assertIn("200,001 characters as written", message)
            self.assertIn("200,000", message)
            self.assertNotIn("tidied", message)
            with self.assertRaises(SanitiseError) as caught:
                call("&" * 50_000)
            message = str(caught.exception)
            self.assertIn("250,000 characters once it is tidied up", message)
            self.assertIn("200,000", message)
            self.assertNotIn("as written", message)

    def test_the_result_is_bounded_too(self):
        """150,000 ampersands are 750,000 once escaped: refused, so what is saved can always be cleaned again."""
        with self.assertRaises(SanitiseError):
            clean_html("&" * 150_000)
        self.assertEqual(clean_html("&" * 30_000), "&amp;" * 30_000)

    def test_nesting_ten_thousand_levels_deep(self):
        for tag in ("blockquote", "ul", "strong", "em", "li", "ol", "a", "p", "div", "span", "b", "table", "svg", "form", "script"):
            attrs = ' href="#"' if tag == "a" else ""
            for source in (f"<{tag}{attrs}>" * 10_000 + "deep text" + f"</{tag}>" * 10_000, f"<{tag}{attrs}>" * 10_000 + "deep text"):
                if len(source) > MAX_CHARS:                                       # <blockquote> closed is 250,000 characters
                    continue
                try:
                    out = self.assertSafe(source, label=tag)
                except SanitiseError:
                    self.assertEqual(tag, "a", "only 10,000 links, each closed by the next, are over the limit once written out")
                    continue
                self.assertLessEqual(self.depth(out), MAX_DEPTH + 1, tag)
                if tag not in ("svg", "form", "script"):
                    self.assertIn("deep text", out, tag)

    def test_mixed_nesting_and_a_deep_list(self):
        self.assertSafe("<ul><li>" * 10_000 + "x" + "</li></ul>" * 10_000)
        self.assertSafe("<blockquote><ul><li><strong><em>" * 2_500 + "x")
        self.assertSafe("<div><p><span>" * 3_000 + "x" + "</span></p></div>" * 3_000)
        self.assertSafe("<!--" * 10_000 + "<p>x</p>")

    @staticmethod
    def depth(out):
        deepest = now = 0
        for m in re.finditer(r"<(/?)([a-z0-9]+)", out):
            if m.group(2) in VOID:
                continue
            now += -1 if m.group(1) else 1
            deepest = max(deepest, now)
        return deepest

    def test_no_recursion(self):
        """The cleaner reads and writes in loops: with a recursion limit just above the test's own depth it still works."""
        source = "<ul><li>" * 10_000 + "x" + "</li></ul>" * 10_000
        saved = sys.getrecursionlimit()
        sys.setrecursionlimit(len(inspect.stack()) + 40)
        try:
            out = clean_html(source)
            clean_html(out)
            plain_text(source)
        finally:
            sys.setrecursionlimit(saved)

    def test_pathological_inputs_stay_fast(self):
        """Each of these, at the longest length allowed, made the old Python 3.9 html.parser rescan for minutes. The old check was a
        wall-clock limit (1.5 s a shape, 15 s in all); each shape is now judged by the growth in CPU time from half the longest length to the
        longest (growth_ratio), and the cleaner must still refuse it or leave nothing the audit finds, at both sizes."""
        def shapes(n):
            return {
                "open tags": "<a " * (n // 3), "open comments": "<!--" * (n // 4), "open marked sections": "<![CDATA[" * (n // 9),
                "open attributes": '<a href="' * (n // 9), "open attribute quotes": "<a b='" * (n // 6), "bangs": "<!-" * (n // 3),
                "question marks": "<?" * (n // 2), "declarations": "<!" * (n // 2), "end tags": "</" * (n // 2),
                "unclosed end tags": "</a " * (n // 4), "if sections": "<![if" * (n // 5), "nested raw text": "<script>" * (n // 8),
                "textareas": "<textarea>" * (n // 10), "long comment": "<!--" + "-" * (n - 4), "long name": "<" + "a" * (n - 1),
                "long attribute name": "<a " + "b" * (n - 3), "many attributes": "<a " + "b=c " * (n // 4 - 1) + ">",
                "equals": "<a " + "=" * (n - 3), "slashes": "<a" + "/" * (n - 2), "quotes": "<a b=" + '"' * (n - 5),
                "angle brackets": "<" * n, "pairs": "<>" * (n // 2), "reversed": ">" * n, "ampersands": "&" * (n // 6),
                "entities": "&amp;" * (n // 5), "numeric entities": "&#" * (n // 2), "long number": "&#" + "9" * (n - 2),
                "long hex": "&#x" + "f" * (n - 3), "half entities": "&am" * (n // 3), "brs": "<br>" * (n // 4), "empty ps": "<p>" * (n // 4),
                "list items": "<li>" * (n // 4), "links": '<a href="https://example.com/">x</a>' * (n // 40), "end then start": "</p><p>" * (n // 7),
                "nul": "\x00" * n, "controls": "<\x01p\x02>" * (n // 6), "a in a": "<a href=#>" * (n // 10),
                "headings": "<h1>a<h2>b<h3>c" * (n // 15), "sections": "<svg/><math/>" * (n // 13), "doctype": "<!DOCTYPE " + "a " * (n // 2 - 10),
            }

        # Only the cleaner is timed: both sizes of every shape are built first, and the audit runs after the timing, on the last output.
        sizes = (MAX_CHARS // 2, MAX_CHARS)
        built = {size: shapes(size) for size in sizes}
        for label in built[MAX_CHARS]:
            outputs = {}

            def work(size, label=label):
                source = built[size][label][:size]
                try:
                    outputs[size] = clean_html(source)
                except SanitiseError:
                    outputs[size] = None                                         # refused: fine, and fast
            assert_growth(self, work, MAX_CHARS // 2, label, tries=5)
            for size in sizes:
                if outputs[size] is not None:
                    self.assertEqual(audit(outputs[size]), [], "%s at %d" % (label, size))


# ===== plain_text =====
class PlainText(Base):
    def test_tags_go_and_entities_are_decoded(self):
        self.assertEqual(plain_text("<p>a &amp; b</p>"), "a & b")
        self.assertEqual(plain_text("<p>5 &lt; 6</p>"), "5 < 6")
        self.assertEqual(plain_text("<p>a&nbsp;b</p>"), "a\xa0b")
        self.assertEqual(plain_text("<p><strong>bold</strong> <em>it</em> <s>s</s></p>"), "bold it s")
        self.assertEqual(plain_text('<a href="https://example.com/">link</a>'), "link")
        self.assertEqual(plain_text("no tags"), "no tags")

    def test_blocks_become_lines(self):
        self.assertEqual(plain_text("<p>one</p><p>two</p>"), "one\ntwo")
        self.assertEqual(plain_text("<p>a<br>b</p>"), "a\nb")
        self.assertEqual(plain_text("<ul><li>x</li><li>y</li></ul><h2>z</h2>"), "x\ny\nz")
        self.assertEqual(plain_text("<ul><li><input type=checkbox checked><p>done</p></li></ul>"), "done")

    def test_dropped_things_never_count(self):
        self.assertEqual(plain_text("<script>alert(1)</script><p>x</p><style>p{}</style>"), "x")
        self.assertEqual(plain_text("<p>a</p><!-- hidden --><p>b</p>"), "a\nb")
        self.assertEqual(plain_text("<div>a</div><span>b</span>"), "a\nb")      # was "ab": a div ends a line, a span does not
        self.assertEqual(plain_text("<span>a</span><span>b</span>"), "ab")

    def test_escaped_markup_is_text_not_tags(self):
        self.assertEqual(plain_text("&lt;script&gt;alert(1)&lt;/script&gt;"), "<script>alert(1)</script>")
        self.assertEqual(plain_text("<p>&lt;b&gt;x&lt;/b&gt;</p>"), "<b>x</b>")

    def test_length_check_use(self):
        self.assertEqual(len(plain_text("<p>" + "word " * 100 + "</p>")), 499)


# ===== Dropped tags: void elements, block tags and the rest =====
VOID_ELEMENTS = ("area", "base", "basefont", "bgsound", "br", "col", "embed", "frame", "hr", "img", "input", "keygen", "link", "meta",
                 "param", "source", "track", "wbr")
BLOCK_TAGS = ("address", "article", "aside", "caption", "center", "dd", "details", "dialog", "dir", "div", "dl", "dt", "fieldset",
              "figcaption", "figure", "footer", "h4", "h5", "h6", "header", "hgroup", "legend", "listing", "main", "menu", "nav",
              "optgroup", "option", "pre", "section", "summary", "table", "tbody", "td", "tfoot", "th", "thead", "tr")


class DroppedTags(Base):
    def test_a_void_element_never_swallows_what_follows(self):
        """embed was dropped with content: with no end tag to wait for, everything after it went."""
        self.assertEqual(self.assertSafe("<p>a</p><embed src=x><p>b</p>"), "<p>a</p><p>b</p>")
        self.assertEqual(self.assertSafe("<p>a</p><embed src=x/><p>b</p>"), "<p>a</p><p>b</p>")
        self.assertEqual(self.assertSafe("<p>a</p><embed src=javascript:alert(1)>b"), "<p>a</p>b")
        self.assertEqual(self.assertSafe("<embed>alert(1)</embed>", gone="<embed"), "alert(1)", "its text is text, escaped and harmless")
        for tag in VOID_ELEMENTS:
            out = self.assertSafe("<p>a</p><%s src=x><p>b</p>" % tag, label=tag)
            self.assertEqual(plain_text(out), "a\nb", tag)
            self.assertEqual(self.assertSafe("a<%s>b" % tag, label=tag).replace("<br>", "").replace("<hr>", ""), "ab", tag)
        self.assertFalse(set(sanitise.DROP_WITH_CONTENT) & set(VOID_ELEMENTS), "a void element has no end tag to wait for")

    def test_removed_block_tags_leave_a_line_break(self):
        for tag in BLOCK_TAGS:
            source = "<{0}>one</{0}><{0}>two</{0}>".format(tag)
            self.assertEqual(self.assertSafe(source, label=tag), "one\ntwo", tag)
            self.assertEqual(plain_text(source), "one\ntwo", tag)
            self.assertEqual(self.assertSafe("<{0}>a<{0}>b".format(tag), label=tag), "a\nb", tag)
            self.assertEqual(self.assertSafe("x<%s>y" % tag, label=tag), "x\ny", tag)
            self.assertEqual(self.assertSafe("<%s>only</%s>" % (tag, tag), label=tag), "only", "nothing before or after")
        self.assertEqual(self.assertSafe("a<form>x</form>b"), "a\nb", "a form is a block that goes with its content")
        self.assertEqual(clean_html("<div>one</div><div>two</div>"), "one\ntwo")
        self.assertEqual(plain_text("<div>one</div><div>two</div>"), "one\ntwo")
        self.assertEqual(clean_html("<table><tr><td>a</td><td>b</td></tr><tr><td>c</td></tr></table>"), "a\nb\nc")
        self.assertEqual(plain_text("<table><tr><td>a</td><td>b</td></tr><tr><td>c</td></tr></table>"), "a\nb\nc")

    def test_a_line_break_is_written_only_where_words_would_join(self):
        for source, expected in (
                ("<div>one</div>two", "one\ntwo"),
                ("one<div>two</div>", "one\ntwo"),
                ("<div>one</div><strong>two</strong>", "one\n<strong>two</strong>"),
                ("<strong>one</strong><div>two</div>", "<strong>one</strong>\ntwo"),
                ("<div>one</div><em><a href=\"https://example.com/\">two</a></em>",
                 'one\n<em><a href="https://example.com/" rel="noopener noreferrer">two</a></em>'),
                ("<ul><li><input type=checkbox><div>one</div></li></ul>", '<ul><li><input type="checkbox">\none</li></ul>'),
                ("<p>a</p><div>b</div>", "<p>a</p>b"),
                ("<div>a</div><p>b</p>", "a<p>b</p>"),
                ("<p>a</p><div>b</div><p>c</p>", "<p>a</p>b<p>c</p>"),
                ("<p>a<div>b</div></p>", "<p>a\nb</p>"),
                ("<div><div>a</div></div>", "a"),
                ("<div>a</div>\n<div>b</div>", "a\nb"),
                ("<div>a</div> <div>b</div>", "a \nb"),
                ("<span>one</span><span>two</span>", "onetwo"),
                ("<div></div>a", "a"),
                ("a<div></div>b", "a\nb"),
                ("<ul><li>a</li><li>b</li></ul>", "<ul><li>a</li><li>b</li></ul>"),
                ("<br>a<div>b</div>", "<br>a\nb")):
            out = self.assertSafe(source)
            self.assertEqual(out, expected, source)
            self.assertEqual(plain_text(source), plain_text(expected), source)
        self.assertEqual(plain_text("<div>one</div><div>two</div><div>three</div>"), "one\ntwo\nthree")
        self.assertEqual(plain_text("<p>a</p><div>b</div><p>c</p>"), "a\nb\nc", "one line break, not two")

    def test_an_end_br_is_a_line_break(self):
        """A browser reads `</br>` as `<br>`."""
        self.assertEqual(self.assertSafe("a</br>b"), "a<br>b")
        self.assertEqual(self.assertSafe("<p>a</br>b</p>"), "<p>a<br>b</p>")
        self.assertEqual(plain_text("a</br>b"), "a\nb")
        self.assertEqual(self.assertSafe("<script></br></script>x"), "x")

    def test_what_is_still_dropped_with_everything_inside(self):
        self.assertEqual(self.assertSafe("<form><form>x</form>LEAK</form>z", gone="LEAK"), "z", "a nested one of the same name")
        self.assertEqual(self.assertSafe("<form><form><form>x</form></form>LEAK</form>z", gone="LEAK"), "z")
        self.assertEqual(self.assertSafe("<form>x</form>shown</form>z"), "shown\nz", "a stray end tag after it is not part of it")
        self.assertEqual(self.assertSafe("<svg><text>LEAK</text></svg>", gone="LEAK"), "")
        self.assertEqual(self.assertSafe("<svg><svg>x</svg>LEAK</svg>z", gone="LEAK"), "z")
        self.assertEqual(self.assertSafe("<svg/>x"), "x", "an empty element, as in a browser")
        self.assertEqual(self.assertSafe("<math/>x"), "x")
        self.assertEqual(self.assertSafe("<p><svg/>a<svg />b<math/>c</p>"), "<p>abc</p>")
        self.assertEqual(self.assertSafe("<svg>LEAK</svg>x"), "x")
        self.assertEqual(self.assertSafe("<svg/>LEAK</svg>x", gone="<svg"), "LEAKx", "`<svg/>` opened nothing, so this end tag is a stray")


# ===== Idempotence and a seeded fuzz =====
PIECES = ["<p>", "</p>", "<strong>", "</strong>", "<em>", "</em>", "<s>", "</s>", "<a href=\"https://example.com/\">", "<a href=javascript:x>",
          "</a>", "<ul>", "</ul>", "<ol>", "</ol>", "<li>", "</li>", "<h1>", "<h2>", "</h2>", "<blockquote>", "</blockquote>", "<br>", "<hr>",
          "<input type=checkbox checked>", "<input type=text>", "<script>", "</script>", "<style>", "</style>", "<svg>", "</svg>", "<svg/>",
          "<form>", "</form>", "<noscript>", "</noscript>", "<textarea>", "</textarea>", "<iframe>", "</iframe>", "<template>", "</template>",
          "<math>", "</math>", "<div>", "</div>", "<span class=a>", "</span>", "<img src=x onerror=x>", "<!--", "-->", "--!>", "<![CDATA[", "]]>",
          "<![if x]>", "<?php", "?>", "<!DOCTYPE x>", "<!", "</", "<", ">", "/", "=", "\"", "'", "&", "&amp;", "&lt;", "&#60;", "&#x3c;", "&#",
          "&nbsp;", " ", "\n", "\t", "\x00", "\x01", "word", "text", "alert(1)", "onerror=", "javascript:", "<p ", "<a ", " href=", " onclick=x",
          "<scr", "ipt>", "<p/>", "</ p>", "</>", "<x:y>", "</x:y>", "\u00e9", "\u200b", "\ud800", "\U0001f600"]


class Fuzz(Base):
    def test_random_markup_is_always_safe_and_stable(self):
        rng = random.Random(66)
        for n in range(6000):
            source = "".join(rng.choice(PIECES) for _ in range(rng.randint(1, 30)))
            self.assertSafe(source, label=f"fuzz {n}: {source!r}")

    def test_random_characters(self):
        rng = random.Random(661)
        alphabet = "<>/!?-=\"' &#;:abcpsulihrx0123\n\t\x00\u00a0"
        for n in range(3000):
            source = "".join(rng.choice(alphabet) for _ in range(rng.randint(1, 60)))
            self.assertSafe(source, label=f"chars {n}: {source!r}")

    def test_already_cleaned_output_of_every_case_is_a_fixed_point(self):
        for source in HOSTILE + CLEAN + [h for h, _ in GOOD_HREFS]:
            once = clean_html(source)
            self.assertEqual(clean_html(once), once)
            self.assertEqual(clean_html(clean_html(once)), once)

    def test_control_characters_from_references_go_from_text_and_stay_gone(self):
        for source, expected in (("&#x81;", ""), ("&#x8d;", ""), ("a&#x81;b&#x8d;c", "abc"), ("<p>&#x90;&#x9d;&#1;&#x7f;x</p>", "<p>x</p>"),
                                 ("&#x80;&#x85;", "\u20ac\u2026"), ("<p>a&#x8d;</p><p>&#x81;b</p>", "<p>a</p><p>b</p>")):
            out = self.assertSafe(source)
            self.assertEqual(out, expected, source)
            self.assertEqual(clean_html(out), out, "cleaning the output again changes nothing")
            self.assertEqual(plain_text(source), plain_text(expected), source)

    def test_new_pieces_are_safe_and_stable(self):
        pieces = ["<div>", "</div>", "<td>", "</td>", "<tr>", "<h4>", "</h4>", "<pre>", "</pre>", "<section>", "</br>", "<br>", "<embed>",
                  "<embed src=x>", "</embed>", "<img src=x>", "<form>", "</form>", "<svg>", "</svg>", "<svg/>", "<math/>", "<p>", "</p>",
                  "<strong>", "</strong>", "<li>", "<ul>", "</ul>", "<a href=\"https://example.com/?a=1&region=eu&copy=2\">", "</a>",
                  "<a href=\"https://example.com/\U0001fae9\u0890\">", "<input type=checkbox>", "&region=eu", "&#x81;", "&copy=1", "word",
                  " ", "\n", "<script>", "</script>", "&", "&amp;", "<", ">"]
        rng = random.Random(660)
        for n in range(3000):
            source = "".join(rng.choice(pieces) for _ in range(rng.randint(1, 25)))
            out = self.assertSafe(source, label=f"new {n}: {source!r}")
            self.assertEqual(clean_html(clean_html(out)), out)
            self.assertEqual(plain_text(out), plain_text(source), f"new {n}: {source!r}")

    def test_plain_text_matches_after_cleaning(self):
        for source in HOSTILE[:150]:
            self.assertEqual(plain_text(clean_html(source)), plain_text(source), repr(source)[:80])


class Module(unittest.TestCase):
    def test_standard_library_only(self):
        text = (ROOT / "src" / "clark" / "sanitise.py").read_text(encoding="utf-8")
        imports = set(re.findall(r"^(?:import|from) (\w+)", text, re.M))
        self.assertEqual(imports, {"html", "re", "unicodedata"})

    def test_the_allow_list_is_the_one_in_the_issue(self):
        self.assertEqual(set(sanitise.ALLOWED), TAGS)
        self.assertEqual(set(sanitise.VOID), VOID)


if __name__ == "__main__":
    unittest.main()
