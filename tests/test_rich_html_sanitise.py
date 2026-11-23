"""#66: the readiness check's "Clean HTML" cases, run in the page's cleanHtml and in Python's sanitise.clean_html alike.

Run: python3 dev/run_tests.py test_rich_html_sanitise
`<script>`, `<style>`, `onerror` and `onclick`, `javascript:` and `data:` links, `<iframe>` and `data-raw` chips go in; only the allowed
list comes out (p, br, strong, em, s, h1 to h3, ul, ol, li, blockquote, hr, a with http, https, mailto or #, and a checkbox input);
a field that is already clean comes back byte for byte. The expected text is written out here, and checked on both sides.
The corpus-wide comparison of the two is tests/test_clean_html_parity.py. Needs Google Chrome and is required.
Left for when #65 is on main and the editor is built: the one-editor gate, `injectCSS: false` and the `<style>` count, the per-key
behaviour tests, the layout at 1400 and 900 px, and the check that a hostile string planted in the database is absent from the
published file (Design: docs/handoff/design-66-editor-wiring.md, section 6).
"""
import json
import re
import unittest

from _clean_html import Page
from test_server import chrome

import test_sanitise as ts
from clark import sanitise

CASES = [
    ("script", '<p>Hello</p><script>alert(1)</script><p>after</p>', '<p>Hello</p><p>after</p>'),
    ("style", '<p>a</p><style>p{color:red}</style><p>b</p>', '<p>a</p><p>b</p>'),
    ("event handlers and style", '<p onclick="alert(1)" onmouseover=x style="color:red" class="c">hi</p>', '<p>hi</p>'),
    ("onerror", '<img src=x onerror=alert(1)><p>t</p>', '<p>t</p>'),
    ("javascript: link", '<a href="javascript:alert(1)">click</a>', 'click'),
    ("data: link", '<a href="data:text/html,<script>alert(1)</script>">click</a>', 'click'),
    ("link keeps only href and our rel", '<a href="https://example.com/" onclick="alert(1)" target="_blank" class="x">ok</a>',
     '<a href="https://example.com/" rel="noopener noreferrer">ok</a>'),
    ("iframe", '<p>x</p><iframe src="https://example.com/"></iframe><p>y</p>', '<p>x</p><p>y</p>'),
    ("iframe text is gone, not shown", '<iframe>LEAK</iframe>', ''),
    ("data-raw chip", '<span data-raw="[[item:A-12]]" class="chip" contenteditable="false">A-12</span>', 'A-12'),
    ("data-raw on a paragraph", '<p data-md-html data-raw="<b>x</b>">hi</p>', '<p>hi</p>'),
    ("Tiptap's link", '<a target="_blank" rel="noopener noreferrer nofollow" class="link" href="https://example.com/a?b=1&amp;c=2">link</a>',
     '<a href="https://example.com/a?b=1&amp;c=2" rel="noopener noreferrer">link</a>'),
    ("Tiptap's task list", '<ul data-type="taskList"><li data-checked="true"><label><input type="checkbox" checked="checked"><span></span>'
     '</label><div><p>done</p></div></li></ul>', '<ul><li><input type="checkbox" checked><p>done</p></li></ul>'),
    ("marks and blocks the allow-list lacks keep their text", '<p><b>b</b><i>i</i><u>u</u><code>c</code></p><pre>p</pre>', '<p>biuc</p>p'),
    ("table", '<table><tr><td>a</td><td>b</td></tr></table>', 'a\nb'),
    ("object and embed", '<object data=x>t</object><embed src=x>u', 'u'),
    ("form", '<form action=x><input name=n></form>after', 'after'),
    ("plain text is escaped, not read as a tag", 'a &lt;b&gt; &amp; c', 'a &lt;b&gt; &amp; c'),
]
ALLOWED = {"p", "br", "strong", "em", "s", "h1", "h2", "h3", "ul", "ol", "li", "blockquote", "hr", "a", "input", "span"}
SIX = ["rt-c-grey", "rt-c-brand", "rt-c-red", "rt-c-amber", "rt-c-green", "rt-c-blue"]      # row 1364: the font colour classes, the only thing a span may carry
TAG = re.compile(r"<(/?)([A-Za-z][^\s/>]*)([^>]*)>")
ATTR = re.compile(r'\s+([a-z-]+)(?:="([^"]*)")?')
WRITTEN = {"a": {"href", "rel"}, "input": {"type", "checked", "disabled"}, "span": {"class"}}


def allowed_only(out):
    """Problems with `out`: a tag, or an attribute, that is not on the allow-list (empty when it is clean)."""
    problems = []
    for closing, name, rest in TAG.findall(out):
        if name not in ALLOWED:
            problems.append(f"tag {name}")
        for attr, value in ATTR.findall(rest):
            if attr not in WRITTEN.get(name, set()):
                problems.append(f"attribute {attr} on {name}")
            if name == "span" and attr == "class" and value not in SIX:
                problems.append(f"span class {value[:30]}")
            if name == "a" and attr == "href" and not re.match(r"(https?://|mailto:|#)", value, re.I):
                problems.append(f"address {value[:30]}")
    return problems


class CleanHtml(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        hostile = [h for _, h, _ in CASES] + list(ts.HOSTILE)
        cls.hostile = hostile
        cls.clean = list(ts.CLEAN) + [out for _, _, out in CASES]
        cls.page = Page(chrome)
        cls.page.__enter__()
        cls.addClassCleanup(cls.page.__exit__, None, None, None)

    def js(self, inputs):
        return self.page.ev("%s.map(function (x) { return CH.run(CH.cleanHtml, x); })" % json.dumps(inputs))

    def test_each_case_gives_the_written_answer_in_the_page_and_in_python(self):
        got = self.js([h for _, h, _ in CASES])
        for (name, source, want), page_out in zip(CASES, got):
            with self.subTest(name):
                self.assertEqual(sanitise.clean_html(source), want, "Python")
                self.assertEqual(page_out, want, "the page")

    def test_only_the_allowed_list_comes_out_of_every_hostile_input(self):
        page_outs = self.js(self.hostile)
        for source, page_out in zip(self.hostile, page_outs):
            for who, out in (("Python", sanitise.clean_html(source)), ("the page", page_out)):
                self.assertEqual(allowed_only(out), [], f"{who}: {source[:80]!r} gave {out[:120]!r}")
        self.assertGreater(len(self.hostile), 200)

    def test_nothing_dangerous_survives_as_text_inside_a_tag(self):
        for source, out in zip(self.hostile, self.js(self.hostile)):
            for needle in ("onerror", "onclick", "onload", "javascript:", "<script", "<style", "<iframe", "data:text"):
                for tag in TAG.findall(out):
                    self.assertNotIn(needle, tag[2].lower(), f"{source[:80]!r}")

    def test_an_untouched_field_comes_back_byte_for_byte_in_the_page_and_in_python(self):
        for source, page_out in zip(self.clean, self.js(self.clean)):
            self.assertEqual(sanitise.clean_html(source), source, "Python")
            self.assertEqual(page_out, source, f"the page changed {source[:80]!r}")

    def test_cleaning_twice_changes_nothing_in_the_page(self):
        once = self.js(self.hostile)
        self.assertEqual(self.js(once), once)

    def test_span_fixed_colour_classes_only(self):
        """Row 1364 (AP12): a span stays as ONE span with exactly one of the six classes, no style attribute, no other class; in Python and in the page."""
        for c in SIX:
            with self.subTest(c):
                self.assertEqual(sanitise.clean_html(f'<p>a <span class="{c}">b</span> c</p>'), f'<p>a <span class="{c}">b</span> c</p>', "Python keeps it")
                self.assertEqual(self.page.call("cleanHtml", f'<p>a <span class="{c}">b</span> c</p>'), f'<p>a <span class="{c}">b</span> c</p>', "the page keeps it")
        # inline: it sits inside a paragraph with strong, em, s and a link around or inside it, and the words stay in order
        nested = '<p><a href="https://example.com/" rel="noopener noreferrer"><span class="rt-c-red"><strong><em><s>x</s></em></strong></span></a></p>'
        self.assertEqual(sanitise.clean_html(nested), nested)
        self.assertEqual(self.page.call("cleanHtml", nested), nested)
        self.assertEqual(sanitise.INLINE & {"span"}, {"span"}, "span is in the inline set")
        self.assertEqual(set(sanitise.COLOUR_CLASSES), set(SIX))

    def test_free_class_style_and_hex_dropped(self):
        """Row 1364 (AP13): a free class, a style attribute, a pasted hex colour, an extra class and an extra attribute all leave the words and no span."""
        drops = [
            '<span class="rt-c-pink">x</span>', '<span class="chip">x</span>', '<span style="color:#ff0000">x</span>',
            '<span class="rt-c-red x">x</span>', '<span class="x rt-c-red">x</span>', '<span class="RT-C-RED">x</span>', '<span class=" rt-c-red">x</span>', '<span class="">x</span>',
            '<span>x</span>', '<span color="#ff0000">x</span>', '<font color="#ff0000">x</font>', '<span data-raw="[[item:A-1]]" class="chip">x</span>',
        ]
        for source in drops:
            with self.subTest(source):
                for who, out in (("Python", sanitise.clean_html(f"<p>{source}</p>")), ("the page", self.page.call("cleanHtml", f"<p>{source}</p>"))):
                    self.assertEqual(out, "<p>x</p>", who)
        both = sanitise.clean_html('<p><span class="rt-c-red" style="color:#f00" onclick="x()" id="a">x</span></p>')
        self.assertEqual(both, '<p><span class="rt-c-red">x</span></p>', "a kept span loses every other attribute")
        self.assertEqual(self.page.call("cleanHtml", '<p><span class="rt-c-red" style="color:#f00" onclick="x()" id="a">x</span></p>'), both)
        for out in (both, sanitise.clean_html('<p style="color:#123456">y</p>')):
            self.assertNotIn("style", out)
            self.assertNotIn("#", out)

    def test_empty_and_missing_give_an_empty_string(self):
        self.assertEqual(self.page.ev("[CH.cleanHtml(''), CH.cleanHtml(null), CH.cleanHtml(undefined)]"), ["", "", ""])

    def test_a_too_long_field_is_refused_in_words_by_both(self):
        text = "x" * 200001
        self.assertEqual(self.page.call("cleanHtml", text), {"error": str(self.refusal(text))})
        self.assertIn("200,001 characters as written", str(self.refusal(text)))

    @staticmethod
    def refusal(text):
        try:
            sanitise.clean_html(text)
        except sanitise.SanitiseError as e:
            return e
        raise AssertionError("Python accepted it")


if __name__ == "__main__":
    unittest.main()
