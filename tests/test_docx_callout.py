"""Row 1272 (1291): the Word report writes a callout's category, colour name and icon name as words, with its title and words.

Run: python3 dev/run_tests.py test_docx_callout
A callout section is added to the published rows (as publish.select() makes it: section_bodies.published) and the file is read back
with docx_read and as a zip."""
import copy
import io
import re
import unittest
import zipfile

from _paths import ROOT   # noqa: F401  (puts src/ on the path)

import _publish_fixture as fx
from clark import docx_build, docx_read, publish, section_bodies


def with_callout(value, title="Heads up", sid="s-callout"):
    p = publish.select(fx.inputs())
    content = section_bodies.published("callout", {"v": 1, "tone": "info", "title": "", "paras": [], **value}, None)
    if content is not None:
        p["sections"].append({"id": sid, "type": "callout", "title": title, "beside": 0, **content})
    else:
        p["sections"].append({"id": sid, "type": "callout", "title": title, "beside": 0})
    return p


def document(data):
    return zipfile.ZipFile(io.BytesIO(data)).read("word/document.xml").decode("utf-8")


def texts(data):
    out = []
    for b in docx_read.read(data, "r.docx").blocks:
        out += [c for r in b["rows"] for c in r] if b["kind"] == "table" else [b.get("text", "")]
    return out


FULL = {"category": "Policy", "colour": "amber", "icon": "flag", "title": "Freeze on 5 Dec", "html": "<p>ZQ-WORDS no merges</p>"}


class Words(unittest.TestCase):
    def test_the_category_colour_and_icon_are_written_as_words(self):
        data = docx_build.build(with_callout(FULL))
        self.assertIn("Policy · Amber · Flag", "\n".join(texts(data)))

    def test_the_title_and_the_words_are_written(self):
        got = "\n".join(texts(docx_build.build(with_callout(FULL))))
        self.assertIn("Freeze on 5 Dec", got)
        self.assertIn("ZQ-WORDS no merges", got)

    def test_the_section_heading_is_written_when_its_heading_is_on(self):
        heads = [b["text"] for b in docx_read.read(docx_build.build(with_callout(FULL)), "r.docx").blocks if b["kind"] == "heading"]
        self.assertIn("Heads up", heads)

    def test_heading_off_writes_no_heading(self):
        heads = [b["text"] for b in docx_read.read(docx_build.build(with_callout({**FULL, "heading": False})), "r.docx").blocks if b["kind"] == "heading"]
        self.assertNotIn("Heads up", heads)

    def test_a_section_without_a_title_is_headed_callout(self):
        heads = [b["text"] for b in docx_read.read(docx_build.build(with_callout(FULL, title="")), "r.docx").blocks if b["kind"] == "heading"]
        self.assertIn("Callout", heads)

    def box(self, **value):
        xml = document(docx_build.build(with_callout({**FULL, **value})))
        at = xml.index("Policy")
        return xml[xml.rindex("<w:tbl>", 0, at):at]

    def test_each_colour_shades_the_box_in_the_pages_token(self):
        for colour, token in (("violet", "blue"), ("amber", "amber"), ("red", "red"), ("green", "green"), ("grey", "grey")):
            fill = docx_build.palette()[docx_build.colours_table.COLOURS[token][0]]
            self.assertIn(f'w:fill="{fill}"', self.box(colour=colour), colour)

    def test_the_colours_are_told_apart(self):
        fills = {re.search(r'w:fill="(\w+)"', self.box(colour=c)).group(1) for c in ("violet", "amber", "red", "green", "grey")}
        self.assertEqual(len(fills), 5)

    def test_plain_box_has_no_fill(self):
        self.assertNotIn("w:fill=", self.box(colour="plain"))

    def test_the_category_line_is_bold(self):
        xml = document(docx_build.build(with_callout(FULL)))
        at = xml.index("Policy")
        self.assertIn("<w:b/>", xml[xml.rindex("<w:r>", 0, at):at])

    def test_the_title_alone_is_written(self):
        got = "\n".join(texts(docx_build.build(with_callout({"title": "Only a title"}))))
        self.assertIn("Only a title", got)

    def test_the_words_alone_are_written(self):
        got = "\n".join(texts(docx_build.build(with_callout({"html": "<p>Only words</p>"}))))
        self.assertIn("Only words", got)

    def test_tile_off_keeps_the_heading(self):
        heads = [b["text"] for b in docx_read.read(docx_build.build(with_callout({**FULL, "tile": False})), "r.docx").blocks if b["kind"] == "heading"]
        self.assertIn("Heads up", heads)

    def test_a_content_without_tile_or_heading_has_both_on(self):
        p = with_callout(FULL)
        for k in ("tile", "heading"):
            del p["sections"][-1]["content"][k]
        data = docx_build.build(p)
        self.assertIn("Heads up", [b["text"] for b in docx_read.read(data, "r.docx").blocks if b["kind"] == "heading"])
        self.assertEqual(document(data).count("<w:tbl>"), document(docx_build.build(with_callout(FULL))).count("<w:tbl>"))

    def test_tile_off_has_no_box(self):
        xml = document(docx_build.build(with_callout({**FULL, "tile": False})))
        self.assertNotIn("Policy ·", xml[:0])
        self.assertIn("Policy · Amber · Flag", "\n".join(texts(docx_build.build(with_callout({**FULL, "tile": False})))))
        self.assertEqual(xml.count("<w:tbl>"), document(docx_build.build(publish.select(fx.inputs()))).count("<w:tbl>"))

    def test_plain_and_no_icon_say_nothing_extra(self):
        got = "\n".join(texts(docx_build.build(with_callout({**FULL, "colour": "plain", "icon": "none"}))))
        self.assertIn("Policy", got)
        self.assertNotIn("Plain", got)
        self.assertNotIn("No icon", got)

    def test_plain_has_no_fill(self):
        xml = document(docx_build.build(with_callout({**FULL, "colour": "plain", "icon": "none", "category": ""})))
        base = document(docx_build.build(publish.select(fx.inputs()))).count("<w:shd ")
        self.assertEqual(xml.count("<w:shd "), base + 0)

    def test_an_older_callout_prints_its_tone_word(self):
        got = "\n".join(texts(docx_build.build(with_callout({"tone": "decision", "title": "Choose", "paras": ["Pick one."]}))))
        self.assertIn("Decision needed · Amber · Question", got)
        self.assertIn("Pick one.", got)

    def test_paragraphs_are_written_when_there_is_no_html(self):
        got = "\n".join(texts(docx_build.build(with_callout({"title": "T", "paras": ["First para", "Second para"]}))))
        self.assertIn("First para", got)
        self.assertIn("Second para", got)

    def test_an_empty_callout_adds_nothing(self):
        self.assertNotIn("Heads up", "\n".join(texts(docx_build.build(with_callout({})))))

    def test_a_published_section_with_no_content_adds_nothing(self):
        p = publish.select(fx.inputs())
        p["sections"].append({"id": "s-c", "type": "callout", "title": "Zed heading", "beside": 0, "content": "bad"})
        self.assertNotIn("Zed heading", "\n".join(texts(docx_build.build(p))))

    def test_the_same_rows_give_the_same_bytes(self):
        self.assertEqual(docx_build.build(with_callout(FULL)), docx_build.build(with_callout(FULL)))

    def test_two_callouts_are_two_blocks_in_order(self):
        p = with_callout(FULL)
        p2 = with_callout({**FULL, "title": "Second one", "category": "Zeta cat"}, sid="s-callout2")
        p["sections"].append(p2["sections"][-1])
        got = "\n".join(texts(docx_build.build(p)))
        self.assertLess(got.index("Policy"), got.index("Zeta cat"))

    def test_html_is_written_as_text_not_markup(self):
        data = docx_build.build(with_callout({**FULL, "html": "<p>a <b>bold</b> word</p>"}))
        self.assertIn("a bold word", "\n".join(texts(data)))
        self.assertNotIn("&lt;b&gt;", document(data))


if __name__ == "__main__":
    unittest.main()
