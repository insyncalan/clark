"""Item 1005: the page's richOrPlain and richWords (logic/richOrPlain.js, logic/richWords.js) against sanitise.rich_or_plain and the words
of it, byte for byte, over legacy plain texts (newlines, <, &, quotes, control characters, blank lines), the editor's HTML and hostile
markup. Python is the authority at the store and the published file; the page's copy only decides what the editor shows.

Run: python3 dev/run_tests.py test_rich_or_plain_parity
Needs Google Chrome (headless): it fails, never skips, without it. The bundle is the one test_clean_html_parity uses, with the two files added.
"""
import json
import random
import sys
import unittest

from _paths import ROOT, TOOLS

sys.path.insert(0, str(TOOLS))
import _clean_html  # noqa: E402
from _clean_html import Page  # noqa: E402
from test_server import chrome  # noqa: E402

from clark import sanitise  # noqa: E402

LOGIC = ROOT / "src" / "clark" / "page" / "src" / "logic"
_clean_html.ENTRY = _clean_html.ENTRY + 'export { richOrPlain, legacyToHtml } from %s;\nexport { richWords } from %s;\n' % (
    json.dumps(str(LOGIC / "richOrPlain.js")), json.dumps(str(LOGIC / "richWords.js")))

HAND = [
    "", "x", "  ", "\n", "a\nb", "a\r\nb", "a\rb", "\n\na\n\n", "a\n\n\nb", 'Line one: a < b & "c" it\'s', "<b>not bold</b>", "<script>alert(1)</script>x",
    "a & b &amp; c &lt; d", "&nbsp;", "a\u00a0b", "a\x00b", "a\tb", "a\x0bb\x7fc\x85d", "\ufeff", " \ufeff ", "\u2028", "a\u200bb", "a\ud800b",
    "<p>hi</p>", "  <p>hi</p>", "\n<p>hi</p>", "<P>hi</P>", "<p>", "<p/>x", "<pre>x</pre>", "<ul><li>a</li></ul>", "<ol><li>a", "<h1>t</h1>x", "<h4>t</h4>",
    "<blockquote>q</blockquote>", "<hr>", "<hr/>x", "<br>x", "<strong>x</strong>", "<a href=\"https://x.example\">l</a>", "<p>a</p>text",
    '<p onclick="x()">hi <script>alert(1)</script><a href="javascript:alert(2)">bad</a> <img src=x onerror=alert(3)></p>',
    "<p>a</p><p></p><p></p><p></p><p></p><p></p><p></p><p>b</p>", "<p> </p>", "<p>&nbsp;</p>", "<p><br></p>", "<p>a &amp; b</p><p>c &lt; d</p>",
    "a\n" * 30, ("<p>x</p>" * 50), "x" * 3000, "<p>" + "x" * 3000 + "</p>",
]


def corpus():
    rng = random.Random(1005)
    bits = ["a", "b c", "<", ">", "&", "&amp;", '"', "'", "\n", "\n\n", "\r\n", "\r", "<p>", "</p>", "<b>", "</b>", "<br>", "<script>", "</script>", "<ul>", "<li>",
            "<h1>", "<hr>", "<blockquote>", " ", "\t", "\u00a0", "\u200b", "\x00", "\ufeff", "<a href=x>", "</a>", "é", "\U0001f600", "&nbsp;", "<!--", "-->"]
    return HAND + ["".join(rng.choice(bits) for _ in range(rng.randint(1, 14))) for _ in range(6000)]


def answer(fn, x):
    try:
        return fn(x)
    except sanitise.SanitiseError as e:
        return {"error": str(e)}


class Parity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.items = [[t, answer(sanitise.rich_or_plain, t)] for t in corpus()]

    def test_the_corpus_has_both_legacy_and_html_values_and_refusals_are_not_the_whole_of_it(self):
        html = [i for i in self.items if isinstance(i[1], str) and sanitise.HTML_START.match(i[0])]
        legacy = [i for i in self.items if isinstance(i[1], str) and i[0] and not sanitise.HTML_START.match(i[0])]
        self.assertGreater(len(html), 300)
        self.assertGreater(len(legacy), 3000)

    def test_richOrPlain_equals_sanitise_rich_or_plain_over_the_corpus(self):
        with Page(chrome, {"ITEMS": self.items}) as page:
            got = page.ev("""(() => { const bad = []; let n = 0;
              ITEMS.forEach((it, i) => { let g; try { g = CH.richOrPlain(it[0]); } catch (e) { g = { error: e.message }; }
                const w = it[1], same = typeof w === 'string' ? w === g : (typeof g === 'object' && g !== null && w.error === g.error);
                if (!same) { n++; if (bad.length < 20) bad.push({ i, input: it[0].slice(0, 200), want: w, got: g }); } });
              return { n, bad, total: ITEMS.length }; })()""")
        self.assertEqual(got["bad"], [], f"{got['n']} of {got['total']} differ")
        self.assertEqual(got["total"], len(self.items))

    def test_richWords_gives_the_words_python_reads_from_the_same_value(self):
        pairs = []
        for text, _ in self.items:
            if len(text) > 2000:
                continue
            try:
                html = sanitise.rich_or_plain(text)              # richWords is given what the server stores or the file carries: clean HTML, or the old plain text
            except sanitise.SanitiseError:
                continue
            pairs.append([html, sanitise.plain_text(html)])
            if not sanitise.HTML_START.match(text):
                pairs.append([text, text])                       # an old plain text comes back as it is
        with Page(chrome, {"PAIRS": pairs}) as page:
            got = page.ev("""(() => { const bad = []; let n = 0;
              PAIRS.forEach((p, i) => { const flat = (t) => t.split(/\\s+/).filter(Boolean).join(' '), g = flat(CH.richWords(p[0])), w = flat(p[1]);
                if (g !== w) { n++; if (bad.length < 20) bad.push({ i, input: p[0].slice(0, 200), want: w, got: g }); } });
              return { n, bad, total: PAIRS.length }; })()""")
        self.assertEqual(got["bad"], [], f"{got['n']} of {got['total']} differ")


if __name__ == "__main__":
    unittest.main()
