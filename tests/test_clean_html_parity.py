"""#66: the page's cleanHtml (src/clark/page/src/logic/cleanHtml.js) against the authoritative sanitise.clean_html, byte for byte.

Run: python3 dev/run_tests.py test_clean_html_parity   (CLARK_PARITY_RANDOM=80000 for the reviewer's size; the default is 20,000)
Design: docs/handoff/design-66-editor-wiring.md. Python is the authority at the store; the page's copy only shows what will be kept,
so the two must never disagree. The corpus is built here, outputs are computed by Python inside the test and handed to Chrome
(the pinned esbuild bundles cleanHtml.js alone; no page, no server), which runs cleanHtml and plainText over every input and
compares. Needs Google Chrome and is required: it fails, never skips, without it.
The corpus: (i) every string in tests/test_sanitise.py (every literal, its address and clean lists, its three seeded fuzzes);
(ii) hand-written hostile cases (the reviewer's 78, from an 80,078-input review of #66a, and ours); (iii) seeded random token soup (the
same generator and seed as the reviewer's, so with CLARK_PARITY_RANDOM=80000 it is their corpus); (iv) every code point in an address and
beside a space. Known differences are named in KNOWN_DIFFERENCES with the reason, and checked to still differ: none is hidden.
"""
import ast
import os
import random
import re
import sys
import unittest

from _paths import ROOT, TOOLS

sys.path.insert(0, str(TOOLS))
import sanitise_tables  # noqa: E402
from _clean_html import Page  # noqa: E402
from test_server import chrome  # noqa: E402

import test_sanitise as ts  # noqa: E402  (its lists and fuzz pieces are part of the corpus)
from clark import sanitise  # noqa: E402

RANDOM = int(os.environ.get("CLARK_PARITY_RANDOM", "20000"))

# Name -> (reason, predicate on the input). A difference whose input matches a predicate is listed, not hidden: the test fails if
# an input is listed here and no longer differs, or differs in any other way. Empty when the port is exact on the whole corpus.
KNOWN_DIFFERENCES = {}


# ===== The corpus =====
# The #66 attack corpus: the reviewer's hand-written cases, copied from their gen2.py, with leave: the classic mutation-XSS and nesting payloads and the fixes' cases. Control characters are written as escapes, never raw bytes.
REVIEWER_CASES = [
    '<a href="https://x.example/?a=1&region=eu&copy=2&copy;3&amp=4&notit;x">q</a>', '<embed src=x><p>after embed</p>', '<embed><b>x</b>',
    '<svg/><p>after</p>', '<svg />p', '<math/>x<p>y</p>', 'a<div>b</div>c<td>d</td>e', '<p>one</p><div>two</div>three', 'x<pre>y</pre>z',
    '<a href="http://a.example/\U000e0001x">t</a>', '<a href="http://a.example/\u0890x">t</a>', '<a href="http://a.example/\ufdd0">t</a>',
    '<a href="http://a.example/\U0001fffe">t</a>', '<a href="http://a.example/\u00ad">t</a>', '<a href="http://a.example/\u2028">t</a>',
    '<a href="http://a.example/\u00a0">t</a>', '<a href="mailto:a@b.example?subject=x&amp;body=y">m</a>', '<a href="#frag">f</a>',
    '<a href="HTTPS://X.EXAMPLE">u</a>', '<a href="https://">t</a>', '<a href="https:///x">t</a>', '<a href="https://\\evil.example">t</a>',
    '<a href="https:\\\\evil.example">t</a>', '<a href="//evil.example">t</a>', '<a href="mailto:">t</a>', '<a href="#">t</a>',
    '<input type="checkbox" checked disabled><input TYPE=" CheckBox ">', '<input type=checkbox/checked>', '<p/>x', '<li>a<li>b</ul>',
    '<ol><li>x<ul><li>y</ol>z', '<blockquote><p>a</blockquote>b', '<h1>a<p>b</h1>c', '<strong><em>a</strong>b</em>c',
    '<a href="http://a.example"><strong>x</a>y</strong>', '<table><td><a href="https://a.example">x</a></table>',
    '<noscript><a href="https://a.example">x</a></noscript>', '<textarea><a href="https://a.example">x</a></textarea>y',
    '<title><b>x</b></title>z', '<select><option>a<option>b</select>', '<template><b>x</b></template>y', '<head><b>x</b></head>y',
    '&lt;b&gt; &#60;b&#62; &amp;lt;', '&nbsp;a&nbsp;', 'a\xa0b', 'x &#0; y &#xD800; z &#x110000; w &#128512;', '<p>\U0001f600 emoji</p>',
    '<a href="https://a.example/%E0%A4%A">x</a>', '<svg><style><img src=x onerror=alert(1)>',
    '<math><mtext><table><mglyph><style><img src=x onerror=alert(1)>', '<noscript><p title="</noscript><img src=x onerror=alert(1)>">',
    '<form><math><mtext></form><form><mglyph><style></math><img src onerror=alert(1)>', '<a href="javascript:alert(1)">x</a>',
    '<a href=" jav&#x09;ascript:alert(1)">x</a>', '<p><svg><desc><img src=x onerror=alert(1)></desc></svg>',
    '<svg></p><style><a id="</style><img src=1 onerror=alert(1)>">', '<select><template><iframe><script></script></iframe></template></select>',
    '<!--><img src=x onerror=alert(1)>-->', '<![CDATA[<img src=x onerror=alert(1)>]]>', '<xmp><img src=x onerror=alert(1)></xmp>',
    '<listing><img src=x onerror=alert(1)>', '<plaintext><img src=x onerror=alert(1)>', '<a href="x"><a href="javascript:alert(1)">y</a></a>',
    '<p>a<p>b<ul><li>c<li>d</ul>', '<input type=checkbox checked onclick=alert(1)>', '<input type=text value=x>',
    '<scr<script>ipt>alert(1)</scr</script>ipt>', '<img src=x onerror=alert(1)//', "<a href='javascript:alert(1)'\u0000>x</a>",
    'x<br/>y<hr/>z', '<h1><h2>nested</h2></h1>', '<table><tr><td><a href="http://example.com">t</a></td></tr></table>',
    '<a href="https://example.com/?a=1&copy=2&amp;b=3">q</a>', '&lt;script&gt;alert(1)&lt;/script&gt;', '<style>@import "x";</style>visible',
    '<title>t</title><b>bold</b>', '<svg/onload=alert(1)>', '<math href="javascript:alert(1)">x</math>']

# Ours: the places where JavaScript and Python could part (case folding, white space, code points, entities, limits, odd syntax).
OURS = [
    '<a href="http://x.example/">k</a>', '<a href="ma\u0131lto:a@b.example">dotless i</a>', '<a href="MA\u0130LTO:a@b.example">dotted I</a>',
    '<a href="http\u017f://x.example/">long s</a>', '<a href="HTTP\u017f://x.example/">long s upper</a>', '<a href="http\u212a://x.example/">kelvin</a>',
    '<\u017fcript>alert(1)</\u017fcript>x', '<scr\u0130pt>alert(1)</scr\u0130pt>x', '<scr\u0131pt>alert(1)</scr\u0131pt>x', '<script>a</scr\u0131pt>b</script>c',
    '<script>a</\u017fcript>b</script>c', '<STYLE>a</style\t>b', '<style>a</style/>b', '<style>a</styleX>b</style>c', '<TITLE>a</t\u0131tle>b</title>c',
    '<p>\ufeff</p>', '\ufeff<p>x</p>\ufeff', ' \u2003x\u2003 ', '<p>\u0085x\u0085</p>', '&#x85;x&#x85;', '&#x1c;x&#x1c;', '\x1cx\x1c',
    '<input type="\ufeffcheckbox">', '<input type="\u2003checkbox\u2003">', '<input type="&#x1c;checkbox">', '<input type="CHECKBOX">',
    '<input type="checkbox" checked="" disabled=0>', '<input type=checkbox CHECKED DISABLED>',
    '<p>\U0001f600\U0001f600</p>', '<p>a\ud83d</p>', '<p>\ude00a</p>', '&#xD83D;&#xDE00;', '&#55357;&#56832;', '&#x1F600;', '&#128512',
    '&#0;', '&#13;', '&#10;', '&#9;', '&#x80;&#x81;&#x8d;&#x9f;', '&#xFDD0;&#xFFFE;&#x10FFFF;&#x1FFFE;', '&#x110000;', '&#99999999;',
    '&#999999999;', '&#x1000000000;', '&#00000000065;', '&#x0000000041;', '&#X41;', '&#x41', '&#65', '&#;', '&#x;', '&;', '&',
    '&&&&', '&amp', '&ampx', '&amp=', '&amp;amp;', '&AMP', '&Amp;', '&lt', '&ltx', '&notit;', '&notin;', '&notinva;', '&not', '&nbsp',
    '&nbspx', '&nbsp;x', '&frac12', '&frac12;', '&frac34x', '&sup2', '&sup4', '&para=1', '&paraX', '&copy', '&copy;', '&copyr', '&reg1',
    '&NewLine;', '&Tab;', '&colon;', '&excl;', '&fjlig;', '&ThickSpace;', '&nvlt;', '&bne;', '&' + 'a' * 40 + ';', '&' + 'a' * 33,
    '&\U0001f600;', '&amp\U0001f600', '&' + '\U0001f600' * 40, '&constructor;', '&__proto__;', '&toString;', '&hasOwnProperty;',
    '<a href="https://x.example/?a=1&amp=2&copy=3&copy;4&region=5&reg=6&regx=7&reg;=8&notin=9&not=10&amp;=11">q</a>',
    '<a href="https://x.example/?&\U0001f600=1&para\U0001f600=2&copy\u00e9">q</a>', '<a href="https://x.example/?&amp\U0001f600">q</a>',
    '<a href="https://x.example/?a=1&#x26;b=2&#38;c=3&#38">q</a>', '<a href=https://x.example/?a=1&b=2>unquoted</a>',
    '<a href=https://x.example/ title=x>t</a>', '<a href="https://x.example/ \u3000">t</a>', '<a href="https://x.example/\u180e">t</a>',
    '<a href="https://x.example/\u061c">t</a>', '<a href="https://x.example/\u2066">t</a>', '<a href="https://x.example/\U000e0020">t</a>',
    '<a href="https://x.example/\ue000">t</a>', '<a href="https://x.example/\U000f0000">t</a>', '<a href="https://x.example/\u0378">t</a>',
    '<a href="https://x.example/\U0001d173">t</a>', '<a href="https://x.example/\U00013439">t</a>', '<a href="https://x.example/\u0891">t</a>',
    '<a href="https://x.example/\ud800">t</a>', '<a href="https://x.example/\udfff">t</a>', '<a href="https://x.example/\ufffe">t</a>',
    '<a href="https://x.example/a\tb">t</a>', '<a href="https://x.example/a\nb">t</a>', '<a href="https://x.example/a\u000bb">t</a>',
    '<a href="https://x.example/a b  c">t</a>', '<a href="\u0001https://x.example/">t</a>', '<a href="\u2003https://x.example/">t</a>',
    '<a href="mailto:\n">t</a>', '<a href="mailto:\u2028">t</a>', '<a href="mailto:\u0085">t</a>', '<a href="#\u2028">t</a>',
    '<a href="https://' + 'a' * 7990 + '">t</a>', '<a href="https://' + 'a' * 7993 + '">t</a>', '<a href="https://' + 'a' * 8000 + '">t</a>',
    '<a href="https://' + '\U0001f600' * 3996 + '">t</a>', '<a href="https://' + '\U0001f600' * 3998 + '">t</a>',
    '<a href="https://x.example/' + ' ' * 9000 + 'y">t</a>',
    '<a href="http://x.example/">one</a><a href="http://y.example/">two</a>', '<a href="http://x.example/"><a href="http://y.example/">n</a></a>',
    '<A HREF="http://x.example/" TARGET="_blank" REL="x" onclick="y" class="z">t</A>',
    '<a href="http://x.example/" href="javascript:x">t</a>', '<a href="javascript:x" href="http://x.example/">t</a>',
    '<a Href=http://x.example/ HREF=javascript:x>t</a>',
    '<p>a</p>\n<p>b</p>', '<p>a<br>b<BR/>c</br>d</BR >e', '<br/>', '</br>', '</br/>', '<br\n/>', '< br>', '<br <br>', '<p<p>x',
    '<p\u0000>x</p>', '<p\x0b>x</p>', '<p\fclass=a>x</p>', '<p\tclass=a>x</p>', '<p/class=a>x</p>', '<p /class=a/>x', '<p class="a>x</p>',
    "<p class='a>x</p>", '<p class=>x</p>', '<p class= >x</p>', '<p =x>y</p>', '<p ==x>y</p>', '<p a=b=c>y</p>', '<p "a">y</p>', "<p 'a'>y</p>",
    '<p a="1"b="2">y</p>', '<p a="1"/b>y</p>', '<p a=1/>y</p>', '<p a=1 />y</p>', '<p a/>y</p>', '<p/>y</p>', '<p//>y</p>', '<p / / >y</p>',
    '<hr/>x', '<hr />x', '<hr/ >x', '<li/>x', '<ul/>x<li>y', '<input/>', '<input type=checkbox/>', '<input type=checkbox />x',
    '<!-->x', '<!--->x', '<!---->x', '<!--x-->y', '<!--x--!>y', '<!--x--->y', '<!--x', '<!--x-', '<!--x--', '<!--x-->', '<!-- -- >y -->z',
    '<!', '<!x>y', '<!x', '<?', '<?x>y', '<?x', '</', '</>', '</>x', '</ >x', '</1>x', '</-a>x', '</a', '</a x', '<a', '<a ', '<a x', '<a x=',
    '<a x="', "<a x='", '<a x="y', '<a x="y"', '<a x="y" ', '<a x=y', '<1>x', '<->x', '< p>x', '<p x>y', '<:a>x', '<a:b>x</a:b>', '<a-b>x</a-b>',
    '<![CDATA[x]]>y', '<![CDATA[x', '<![if x]>y<![endif]>', '<!DOCTYPE html>x', '<!doctype html>x', '<!DOCTYPE', '<!--[if x]>y<![endif]-->z',
    '<script>x', '<script>x</script', '<script>x</script >y', '<script>x</script\n>y', '<script>x</script/>y', '<script/>x</script>y', '<script />x',
    '<SCRIPT>x</SCRIPT>y', '<script>x</script><script>y</script>z', '<script><script>x</script>y</script>z', '<script><!--</script>x-->y',
    '<style>x', '<textarea><p>x</p></textarea>y', '<title>a<b>b</b></title>c', '<xmp><p>x</p></xmp>y', '<iframe><p>x</p></iframe>y',
    '<noembed><p>x</p></noembed>y', '<noframes><p>x</p></noframes>y', '<noscript><p>x</p></noscript>y', '<plaintext>a<p>b', 'a<plaintext>b</plaintext>',
    '<select><option>a</option></select>b', '<form>a<form>b</form>c</form>d', '<form>a</form>b', '</form>a', '<object>a<object>b</object>c</object>d',
    '<applet>a</applet>b', '<head>a</head>b', '<math>a<math>b</math>c</math>d', '<svg>a<svg>b</svg>c</svg>d', '<template>a<template>b</template>c</template>d',
    '<svg><svg/>x</svg>y', '<svg/><svg/>x', '<svg />x</svg>y', '<math/>x</math>y', '<form/>x</form>y', '<p><form>x</form>y</p>',
    'a<address>b</address>c', 'a<dd>b</dd>c', 'a<DIV>b</DIV>c', 'a<div>\nb</div>c', 'a<div> b</div>c', 'a <div>b</div> c', '<p>a</p><div>b</div><p>c</p>',
    '<strong>a</strong><div>b</div>', '<a href="http://x.example/">a</a><div>b</div>', '<div><div>a</div></div>b', 'a<td>b<td>c', 'a<tr>b<tr>c',
    '<h4>a</h4><h5>b</h5><h6>c</h6>d', 'a<pre>\nb\n</pre>c', 'a<nav><ul><li>b</li></ul></nav>c', 'a<details><summary>b</summary>c</details>d',
    '<p>one<p>two<p>three', '<h1>a<h2>b<h3>c', '<h1>a<p>b</h1>c', '<p>a<ul><li>b</ul>c', '<p>a<blockquote>b</blockquote>c', '<p>a<hr>b',
    '<p><strong>a<p>b</strong>c', '<strong><p>a</p></strong>', '<a href="http://x.example/"><p>a</p></a>', '<em><s><strong>a</em></s></strong>',
    '<li>a<li>b<li>c', '<ul><li>a<ul><li>b<li>c</ul><li>d</ul>', '<ol><li>a<ol><li>b</ol></ol>', '<blockquote><li>a<li>b</blockquote>',
    '<ul><li><p>a<li><p>b</ul>', '<li><ul><li>a</ul><li>b', '</li>x', '</ul>x', '</p>x', '</p></p>x', '</strong>x', '</a>x', '</s>x',
    '<ul>' * 60 + 'x' + '</ul>' * 60, '<blockquote>' * 51 + 'x', '<blockquote>' * 50 + 'x', '<p>' * 200 + 'x', '<strong>' * 100 + 'x' + '</strong>' * 100,
    '<li>' * 100, '<ul><li>' * 70 + 'x', '<a href="http://x.example/">' * 60 + 'x', '<em>' * 49 + '<strong>y</strong>z', '<em>' * 50 + '<strong>y</strong>z',
    '<br>' * 100, '<hr>' * 100, '<input type=checkbox>' * 100, '<svg>' * 100 + 'x', '<script>' * 100 + 'x',
    'plain text only', 'Tom & Jerry <tom@example.com>', 'needs a<b review before go-live', 'if x <y then stop. Next line stays',
    'use <select> from the list. More text', 'Budget < 5k and > 2k', '5 &lt; 6 &amp;&amp; 7 &gt; 6', '<<p>>x', '<p>>x', '<>', '<<', '>>', 'a<',
    'a<b', 'a<b>c', 'a<b/>c', 'a</b>c', '\x00', '\x00<p>x</p>', '<scr\x00ipt>x</script>y', '<p>\x00x\x01y\x7fz\x9f</p>', '<p>\u2028x\u2029</p>', '\r\n', 'a\rb\r\nc',
    '<p>a\u00a0b</p>', '<p>&nbsp;</p>', '<p> </p>', '\u00a0', '\u00a0<p>x</p>\u00a0', '<p>\u200b</p>', '<p>\u200bx\u200b</p>',
    '<ul><li><input type="checkbox" checked><p>done</p></li></ul>', '<ul data-type="taskList"><li data-checked="true"><label><input type="checkbox" checked><span></span></label><div><p>x</p></div></li></ul>',
    '<p>x</p><p></p><p>y</p>', '<h2>Status</h2>\n<ul>\n<li>On track</li>\n<li>Pilot live 12 November</li>\n</ul>\n',
    '<p><b>b</b> <i>i</i> <u>u</u> <code>c</code> <pre>p</pre> <del>d</del> <mark>m</mark> <span>s</span> <font>f</font></p>',
    '<img src="https://x.example/a.png" alt="a">x', '<video src=x></video>y', '<audio>a</audio>', '<button>b</button>', '<label>l</label>', '<canvas>c</canvas>',
    '<base href="http://x.example/"><meta http-equiv="refresh" content="0;url=http://evil.example/"><link rel=stylesheet href=x>x',
    '<p onclick="x" style="color:red" class="c" id="i" data-x="y">t</p>', '<p style="background:url(javascript:alert(1))">t</p>',
]

# The #66 attack corpus, the reviewer's generator (gen2.py), verbatim in behaviour (its \x00 and lone control characters are escapes here, never raw bytes): with the same seed and count it gives their corpus, input for input.
W_TAGS = ["p", "a", "svg", "math", "style", "script", "noscript", "template", "table", "tr", "td", "select", "option", "form", "input", "img",
          "iframe", "textarea", "title", "mglyph", "mtext", "annotation-xml", "foreignObject", "desc", "plaintext", "xmp", "listing", "button",
          "details", "strong", "em", "s", "h1", "ul", "li", "blockquote", "br", "hr", "b", "i", "div", "span", "object", "embed", "base", "link",
          "meta", "frameset", "image", "video", "audio", "source", "a:b", "svg:a", "style/"]
W_ATTRS = ["href", "onerror", "onclick", "src", "type", "style", "xlink:href", "srcdoc", "formaction", "action", "data", "checked", "disabled",
           "rel", "target", "class", "id", "name", "onload", "autofocus", "onfocus", "content", "is"]
W_VALS = ["javascript:alert(1)", "JaVaScRiPt:alert(1)", "  javascript:alert(1)", "jav&#9;ascript:alert(1)", "&#106;avascript:alert(1)",
          "&#x6A;avascript&colon;alert(1)", "data:text/html,<script>alert(1)</script>", "vbscript:x", "http://example.com/a?b=1&c=2",
          "https://example.com", "mailto:a@example.com", "#frag", "//example.com", "x\"onerror=\"alert(1)", "x' onerror='alert(1)",
          "`onerror=alert(1)`", "checkbox", "text", "<script>", "</a>", "\u2028javascript:1", "java\x00script:1", "java\nscript:1", "HTTP://EXAMPLE.COM",
          "https://", "http:///x", "&amp;", "&lt;img src=x onerror=alert(1)&gt;"]
W_PIECES = ["<", ">", "</", "/>", "<!--", "-->", "--!>", "<![CDATA[", "]]>", "<?php ", "?>", "<!DOCTYPE html>", "\"", "'", "=", "`", " ", "\t", "\n",
            "\x00", "\u2028", "\xa0", "&lt;", "&gt;", "&amp;", "&#60;", "&#x3c;", "&NewLine;", "&Tab;", "&colon;", "&#0;", "&#x110000;", "&#99999999999;",
            "&copy=", "&amp", "hello", "text", "x"]


def reviewer_corpus(rng, count):
    def attr():
        a, r, v = rng.choice(W_ATTRS), rng.random(), rng.choice(W_VALS)
        if r < .4:
            return f'{a}="{v}"'
        if r < .6:
            return f"{a}='{v}'"
        if r < .8:
            return f"{a}={v.replace(' ', '')}"
        return a

    def piece():
        r = rng.random()
        if r < .30:
            return f"<{rng.choice(W_TAGS)} {' '.join(attr() for _ in range(rng.randint(0, 3)))}>"
        if r < .42:
            return f"</{rng.choice(W_TAGS)}>"
        if r < .50:
            return f"<{rng.choice(W_TAGS)}/>"
        if r < .56:
            return f"<{rng.choice(W_TAGS)}"
        return rng.choice(W_PIECES)

    return ["".join(piece() for _ in range(rng.randint(2, 40))) for _ in range(count)]


# Ours: a second soup, of the odd characters and references the port could read differently (Unicode, entities, white space).
O_PIECES = ["<p>", "</p>", "<a href=\"", "\">", "</a>", "<script>", "</script>", "<style>", "</style", "</\u017fcript>", "</scr\u0131pt>", "<svg>", "</svg>", "<div>",
            "</div>", "<td>", "<h5>", "</h5>", "<li>", "<ul>", "</ul>", "<input type=checkbox>", "<input type=\"\ufeffcheckbox\">", "<br>", "</br>",
            "http://x.example/", "https://x.example/?a=1", "mailto:a@b.example", "javascript:x", "ma\u0131lto:a@b.example", "http\u017f://x.example/",
            "\u0130", "\u0131", "\u017f", "\u212a", "\u00e9", "\u0085", "\ufeff", "\u2003", "\u2028", "\u3000", "\u00a0", "\u200b", "\u00ad", "\ue000",
            "\U0001f600", "\U000e0001", "\U0001fffe", "\ud800", "\udc00", "\x1c", "\x7f", "\x00", "\t", "\n", "\r", "\f", "\x0b", " ", "  ",
            "&", "&amp", "&amp;", "&copy", "&copy=", "&copy;", "&region=1", "&reg", "&regx", "&not", "&notin;", "&notit;", "&nbsp", "&para",
            "&#0;", "&#13;", "&#x80;", "&#x85;", "&#x1c;", "&#xD800;", "&#x110000;", "&#9999999999;", "&#xFFFE;", "&#128512;", "&#x1F600", "&#38;", "&#x26;",
            "&NewLine;", "&Tab;", "&fjlig;", "&bne;", "&AMP", "&constructor;", "=", "\"", "'", "/", ">", "<", "<!--", "-->", "--!>", "<![CDATA[", "<?", "<!",
            " href=", " type=", " CHECKED", "word", "a", "text"]


def ours_corpus(rng, count):
    return ["".join(rng.choice(O_PIECES) for _ in range(rng.randint(1, 30))) for _ in range(count)]


def from_test_sanitise():
    """(i) every string literal in tests/test_sanitise.py, its address cases written as links, and its three seeded fuzzes."""
    tree = ast.parse((ROOT / "tests" / "test_sanitise.py").read_text(encoding="utf-8"))
    literals = sorted({n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)})
    links = []
    for href in ts.BAD_HREFS + [h for h, _ in ts.GOOD_HREFS]:
        links += ['<a href="%s">text</a>' % href, "<a href='%s'>text</a>" % href, "<a href=%s>text</a>" % href]
    fuzz = []
    rng = random.Random(66)
    fuzz += ["".join(rng.choice(ts.PIECES) for _ in range(rng.randint(1, 30))) for _ in range(6000)]
    rng = random.Random(661)
    alphabet = "<>/!?-=\"' &#;:abcpsulihrx0123\n\t\x00\u00a0"
    fuzz += ["".join(rng.choice(alphabet) for _ in range(rng.randint(1, 60))) for _ in range(3000)]
    return literals + list(ts.HOSTILE) + list(ts.CLEAN) + links + fuzz


def systematic():
    """Every tag with every attribute kind and address scheme, quoted and not (the shape of the first review's 7,000)."""
    tags = ["a", "p", "input", "img", "svg", "math", "style", "script", "iframe", "form", "td", "li", "h1", "strong", "br", "embed", "object"]
    attrs = ["href", "src", "onclick", "onerror", "style", "type", "checked", "disabled", "rel", "target", "xlink:href", "formaction", "ping", "id"]
    values = ["javascript:alert(1)", "https://example.com/", "mailto:a@example.com", "data:text/html,x", "checkbox", "#frag", "x"]
    out = []
    for t in tags:
        for a in attrs:
            for v in values:
                out += [f'<{t} {a}="{v}">x</{t}>', f"<{t} {a}={v}>x", f"<{t} {a}='{v}'/>y"]
    return out


def code_points():
    """(iv) one input per code point: in an address, and as the white space around words (what strip and the address rule see)."""
    cps = list(range(0x10000)) + list(range(0x10000, 0x20000)) + list(range(0xE0000, 0xE1000))
    for plane in range(2, 17):
        base = plane << 16
        cps += [base, base + 1, base + 0xFFFD, base + 0xFFFE, base + 0xFFFF]
    cps += [0x10FFFF, 0x1FFFF, 0x3FFFE]
    out = []
    for n in cps:
        c = chr(n)
        out.append('<a href="https://x.example/a%sb">t</a>' % c)
        out.append('<a href="%shttps://x.example/%s">t</a>' % (c, c))
        out.append("<p>%sx%s</p>" % (c, c))
        out.append('<input type="%scheckbox%s">' % (c, c))
    return out


# #84: blank lines. Hand-written cases for the cap on a run of empty paragraphs and for plain text, then a generator over the same pieces.
BLANK = (['<p></p>' * n for n in range(0, 9)] + ['<p><br></p>' * n for n in range(0, 9)] + ['<p></p><p><br></p>' * n for n in range(1, 6)] +
         ['a' + '<p></p>' * n + 'b' for n in (1, 4, 5, 6, 7, 20)] + ['<p>a</p>' + '<p></p>' * n + '<p>b</p>' for n in (1, 5, 6, 7)] +
         ['<p></p>' * 6 + '<p>x</p>' + '<p></p>' * 6, '<p></p>' * 5 + ' ' * 3 + '<p></p>', '<p></p>' * 5 + '\n' + '<p></p>', '<p></p>\n' * 6,
          '<p></p> \t\n\r\f <p></p>' * 3, '<p></p>\u00a0<p></p>' * 6, '<p></p>&nbsp;<p></p>' * 6, '<p></p>x<p></p>' * 6,
          '<p> </p>', '<p>   </p>', '<p>\n</p>', '<p>\t\r\f</p>', '<p> </p>' * 8, '<p> </p><p></p><p><br></p>' * 3, '<p>&nbsp;</p>', '<p>&nbsp;</p>' * 8,
          '<p>\u00a0</p>', '<p>&nbsp; &nbsp;</p>', '<p>&#160;&#32;&#9;</p>', '<p> <br> </p>', '<p><br><br></p>', '<p><br><br></p>' * 8, '<p><br> </p>',
          '<p>\u200b</p>', '<p>\u200b</p>' * 8, '<p>\u2003</p>', '<p>\u3000</p>', '<p>\u2028</p>', '<p>\u0085</p>', '<p>\ufeff</p>', '<p>\x1c</p>',
          '<p>&#x200b;</p>', '<p>&ensp;</p>', '<p>&emsp;</p>', '<p>&thinsp;</p>', '<p> x </p>', '<p>&nbsp;x</p>',
          '<p>a</p><p></p><p>b</p>', '<p>a</p><p> </p><p>b</p>', '<p>a</p><p>&nbsp;</p><p>b</p>', '<p>a</p><p><br></p><p>b</p>', '<p></p><p>a</p>', '<p>a</p><p></p>',
          '<p></p>', '<p><br></p>', '<p> </p>\n<p> </p>', '<h1></h1><p></p>', '<ul><li></li></ul><p></p>' * 3, '<blockquote><p></p><p></p></blockquote>',
          '<li><p></p><p></p><p></p><p></p><p></p><p></p><p></p></li>', '<p>a<br></p>', '<p><br>a</p>', '<p><strong></strong></p>', '<p><strong> </strong></p>',
          '<p></p><br><p></p>', '<hr><p></p>', '<p/>', '<p/>' * 8, '<p></p' + '>' * 1, '<P></P>' * 7, '<p></P>' * 7, '<p class=x></p>' * 7, '<p\n></p>' * 7,
          '<p>&#0;</p>' * 7, '<p>\x00</p>' * 7, '<p><!-- c --></p>' * 7, '<p><script>x</script></p>' * 7, '<p><span></span></p>' * 7, '<p><a href="#"></a></p>' * 7,
          '<p><input type=text></p>' * 7, '<p></p>' * 3000, '<p><br></p>' * 3000, '<p> </p>' * 3000])
B_PIECES = ["<p></p>", "<p><br></p>", "<p> </p>", "<p>&nbsp;</p>", "<p>\u00a0</p>", "<p>\u200b</p>", "<p>\u2003</p>", "<p><br><br></p>", "<p>x</p>", "<p>a b</p>",
            " ", "\n", "\t", "\r", "\f", "\u00a0", "&nbsp;", "<br>", "<br/>", "<h2>h</h2>", "<ul><li>i</li></ul>", "<li>", "</li>", "<ul>", "</ul>", "<p>", "</p>",
            "<strong></strong>", "<em> </em>", "<blockquote>", "</blockquote>", "<hr>", "\u200b", "\ufeff", "&#x200b;", "&#160;", "&#32;", "<!--c-->", "<script>x</script>"]


def blank_corpus(rng, count):
    """Runs of blank lines of every length and kind, with the gaps and odd paragraphs between them: lengths 4 to 8 are where the cap bites."""
    out = []
    for _ in range(count):
        n = rng.randint(1, 12)
        out.append("".join(rng.choice(B_PIECES[:8]) if rng.random() < .6 else rng.choice(B_PIECES) for _ in range(n * rng.randint(1, 2))))
    return out


def no_pairs(s):
    """A Python str may hold a surrogate pair as two code points; JavaScript reads that as one character. Keep lone ones lone."""
    return re.sub("([\ud800-\udbff])(?=[\udc00-\udfff])", "\\1x", s)


def answer(fn, text):
    try:
        return fn(text)
    except sanitise.SanitiseError as e:
        return {"error": str(e)}


def build():
    """The corpus as [[input, python's clean, python's plain_text], ...] (duplicates dropped, order kept), with each part's size."""
    parts = [("test_sanitise", from_test_sanitise()), ("hand-written (reviewer 78)", REVIEWER_CASES), ("hand-written (ours)", OURS),
             ("systematic", systematic()), ("random (the reviewer's generator)", reviewer_corpus(random.Random(66), RANDOM)),
             ("random (ours)", ours_corpus(random.Random(67), max(RANDOM // 4, 1000))),
             ("blank lines (#84)", BLANK), ("random blank lines (#84)", blank_corpus(random.Random(84), max(RANDOM // 4, 5000))), ("code points", code_points())]
    seen, items, sizes = set(), [], {}
    for name, inputs in parts:
        sizes[name] = len(inputs)
        for text in inputs:
            text = no_pairs(text)
            if text not in seen:
                seen.add(text)
                items.append([text, answer(sanitise.clean_html, text), answer(sanitise.plain_text, text)])
    return items, sizes


# The limits, written out (a Python str is built here, so these are exact).
LIMITS = [("x" * 200000), ("x" * 200001), ("x" * 250000), ("&" * 50000), ("&" * 40000), ("&" * 39999), ("<" * 40000), ("<" * 66666),
          ("\U0001f600" * 100001), ("\U0001f600" * 200000), ("\U0001f600" * 200001), ("\U0001f600" * 100000 + "&" * 99999),
          ("a" * 199999 + "&"), ("a" * 199998 + "&" + "\x00" * 3), ("<p>" + "x" * 199990 + "</p>"), ("<p>" * 66667), ("<br>" * 50000),
          ("&nbsp;" * 33334), ("\xa0" * 40000), ("\xa0" * 30000), "<a <a <a " * 22000, "<!--" * 50000, "<![CDATA[" * 22000, "&#" * 100000,
          "&#9" * 66000, "<p " * 66000, '<a href="' * 22000, "<script>" * 25000, "<svg>" * 40000, "<ul><li>" * 25000, "<blockquote>" * 16000]


class Parity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.items, cls.sizes = build()
        cls.limits = [[t, answer(sanitise.clean_html, t), answer(sanitise.plain_text, t)] for t in LIMITS]

    def compare(self, items):
        with Page(chrome, {"ITEMS": items}) as page:
            return page.ev("CH.compare(ITEMS, 25)")

    def test_the_tables_the_page_uses_are_the_ones_python_makes(self):
        self.assertEqual(sanitise_tables.main(["--check"]), 0, "run python3 dev/tools/sanitise_tables.py and commit the result")

    def test_the_corpus_is_big_enough_and_has_every_part(self):
        self.assertGreaterEqual(len(self.items), 20000 + 5000)
        self.assertTrue(all(n > 0 for n in self.sizes.values()), self.sizes)

    def test_cleanHtml_and_plainText_equal_the_python_module_over_the_whole_corpus(self):
        got = self.compare(self.items)
        self.assertEqual(got["total"], len(self.items))
        unexplained = [b for b in got["bad"] if not any(pred(b["input"]) for _, pred in KNOWN_DIFFERENCES.values())]
        self.assertEqual(unexplained, [], f"{got['count']} of {got['total']} inputs differ (first {len(got['bad'])} shown); corpus {self.sizes}")
        # `bad` holds only the first few; the full count must equal what the known differences account for, so a later one cannot hide.
        listed = [i for i in self.items if any(pred(i[0]) for _, pred in KNOWN_DIFFERENCES.values())]
        explained = self.compare(listed)["count"] if listed else 0
        self.assertEqual(got["count"], explained, f"{got['count']} inputs differ but the known differences account for {explained}")

    def test_blank_lines_are_capped_and_kept_the_same_in_both(self):
        """#84: a run of more than five empty paragraphs is cut to five, a paragraph of only spaces or &nbsp; is a blank line, a zero-width one is text."""
        cases = [t for t in BLANK if len(t) < 100000]
        items = [[t, answer(sanitise.clean_html, t), answer(sanitise.plain_text, t)] for t in cases]
        self.assertEqual(self.compare(items)["count"], 0)
        with Page(chrome) as page:
            self.assertEqual(page.call("cleanHtml", "<p></p>" * 9), "<p></p>" * 5)
            self.assertEqual(page.call("cleanHtml", "<p> </p>"), "<p></p>")
            self.assertEqual(page.call("plainText", "<p>a</p><p>&nbsp;</p><p>b</p>"), sanitise.plain_text("<p>a</p><p>&nbsp;</p><p>b</p>"))
            self.assertEqual(page.call("plainText", "<p>\u200b</p>"), sanitise.plain_text("<p>\u200b</p>"))

    def test_the_limits_agree_including_the_messages_and_code_point_counts(self):
        got = self.compare(self.limits)
        self.assertEqual(got["bad"], [], "limits")
        refused = [i for i, t in enumerate(self.limits) if isinstance(t[1], dict)]
        self.assertTrue(len(refused) >= 8 and len(refused) < len(self.limits), "the limit cases must include both answers")

    def test_a_non_string_is_refused_and_none_and_undefined_give_nothing(self):
        with Page(chrome) as page:
            self.assertEqual(page.ev("[CH.cleanHtml(null), CH.cleanHtml(undefined), CH.cleanHtml('')]"), ["", "", ""])
            for value, name in ((7, "int"), (1.5, "float"), (True, "bool"), ([], "list"), ({}, "dict")):
                self.assertEqual(page.call("cleanHtml", value), {"error": f"Rich text must be text, not {name}."})
                with self.assertRaises(sanitise.SanitiseError) as cm:
                    sanitise.clean_html(value)
                self.assertEqual(str(cm.exception), f"Rich text must be text, not {name}.")

    def test_a_clean_result_is_a_fixed_point_in_the_page_too(self):
        outputs = sorted({i[1] for i in self.items if isinstance(i[1], str)})
        got = self.compare([[o, o, sanitise.plain_text(o)] for o in outputs])
        self.assertEqual(got["bad"], [], "cleaning a Python result in the page changed it")

    def test_every_known_difference_still_differs_and_has_a_reason(self):
        for name, (reason, pred) in KNOWN_DIFFERENCES.items():
            self.assertTrue(reason.strip(), name)
            hits = [i for i in self.items if pred(i[0])]
            self.assertTrue(hits, f"{name}: no input in the corpus shows it")
            self.assertTrue(self.compare(hits)["count"] > 0, f"{name}: it no longer differs, so remove it")


if __name__ == "__main__":
    unittest.main()
