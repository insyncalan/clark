"""#112: foreign content (svg, math, CDATA) and a quote that swallows a tag, at every place a hostile file could carry them.

Run: python3 dev/run_tests.py test_publish_scan_foreign
The bad/good checks and the real page are in _scan_gaps.py; the file was split from test_publish_scan_gaps.py (one file took 5 minutes).
"""
import unittest

from _paths import SRC

from _scan_gaps import OPENER, GapsChecks, real  # noqa: E402
from clark import page, publish, to_client  # noqa: E402
from clark.publish import PublishError  # noqa: E402


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


class Desync(unittest.TestCase):
    """#112 H4: a quote that swallows a < must not hide the tags inside it, and `=` may start an attribute name."""
    bad = GapsChecks.bad

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

if __name__ == "__main__":
    unittest.main()
