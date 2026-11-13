"""Row 853 mutation sweep, leftovers of word_brand: conditions the first three test files left unpinned (the body's own section
properties in odd layouts, external and absolute relationship targets, the drop of a part's relationships under another letter case,
the numbering part found by a reversed attribute order, content types not declared twice, the size limit at its exact byte, the zip
entries' attributes, a styles part that holds the closing tag twice or is not UTF-8, a path find() cannot read).
Run: python3 dev/run_tests.py test_word_brand_survivors      No browser; made-up text only (markers start ZQS5).
"""
import io
import os
import re
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from unittest import mock

from _paths import ROOT   # noqa: F401

from clark import docx_build, word_brand
from clark.docx_read import WordRefused
from test_word_brand import BUILT, HEAD, REL, SECT, W, parts, template
from test_word_brand_edges import rebuilt
from test_word_brand_leftovers import COMMENTS, assert_no_dangling, with_leftovers

END = SECT + "</w:body></w:document>"


def doc_changed(fn):
    return rebuilt(template(), lambda n, d: fn(d.decode()).encode() if n == "word/document.xml" else d)


def add_rels(extra, base=None):
    return rebuilt(base or template(), lambda n, d: d.replace(b"</Relationships>", extra.encode() + b"</Relationships>")
                   if n == "word/_rels/document.xml.rels" else d)


class BodySection(unittest.TestCase):
    def tail(self, data):
        return parts(word_brand.wrap(data, BUILT))["word/document.xml"].decode().rstrip()

    def test_a_section_with_a_nested_whole_section_in_a_tracked_change_is_taken_whole(self):
        nested = SECT.replace("</w:sectPr>", '<w:sectPrChange w:id="3" w:author="ZQS5"><w:sectPr><w:pgSz w:w="1111" w:h="2222"/></w:sectPr></w:sectPrChange></w:sectPr>')
        out = self.tail(doc_changed(lambda d: d.replace(SECT, nested)))
        self.assertTrue(out.endswith(nested + "</w:body></w:document>"))

    def test_a_section_with_an_empty_section_inside_it_is_taken_whole(self):
        nested = SECT.replace("</w:sectPr>", '<w:sectPrChange w:id="3" w:author="ZQS5"><w:sectPr/></w:sectPrChange></w:sectPr>')
        out = self.tail(doc_changed(lambda d: d.replace(SECT, nested)))
        self.assertTrue(out.endswith(nested + "</w:body></w:document>"))

    def test_the_page_set_up_is_found_whatever_white_space_or_missing_end_tag_surrounds_it(self):
        for label, change in (("no closing document tag", lambda d: d.replace("</w:document>", "")),
                              ("a line after the document", lambda d: d + "\n \n"),
                              ("a line before the body ends", lambda d: d.replace("</w:body>", "\n</w:body>")),
                              ("spaces before the body ends", lambda d: d.replace("</w:body>", "   </w:body>"))):
            with self.subTest(label):
                self.assertTrue(self.tail(doc_changed(change)).endswith(END), label)

    def test_a_template_with_a_body_start_but_no_body_end_is_refused(self):
        with self.assertRaises(WordRefused) as e:
            word_brand.wrap(doc_changed(lambda d: d.replace("</w:body>", "")), BUILT)
        self.assertIn("it has no body", str(e.exception))

    def test_a_template_with_a_body_end_but_no_body_start_is_refused(self):
        with self.assertRaises(WordRefused) as e:
            word_brand.wrap(doc_changed(lambda d: d.replace("<w:body>", "")), BUILT)
        self.assertIn("it has no body", str(e.exception))


class Relationships(unittest.TestCase):
    def wrapped(self, data):
        return parts(word_brand.wrap(data, BUILT))

    def test_an_external_link_whose_target_looks_like_a_dropped_part_is_kept_in_any_letter_case(self):
        data = add_rels(f'<Relationship Id="rIdE1" Type="{REL}/hyperlink" Target="../customXml/item1.xml" TargetMode="External"/>'
                        f'<Relationship Id="rIdE2" Type="{REL}/hyperlink" Target="../customXml/item1.xml" TargetMode="EXTERNAL"/>',
                        with_leftovers())
        rels = self.wrapped(data)["word/_rels/document.xml.rels"].decode()
        self.assertIn('Id="rIdE1"', rels)
        self.assertIn('Id="rIdE2"', rels)
        self.assertNotIn('Id="rIdX2"', rels)        # the internal one to the same part is gone

    def test_an_absolute_a_dotted_and_a_backslash_target_to_a_dropped_part_are_all_removed(self):
        data = add_rels(f'<Relationship Id="rIdA1" Type="{REL}/customXml" Target="/customXml/item1.xml"/>'
                        f'<Relationship Id="rIdA2" Type="{REL}/comments" Target="./comments.xml"/>'
                        f'<Relationship Id="rIdA3" Type="{REL}/customXml" Target="..\\customXml\\item1.xml"/>', with_leftovers())
        out = self.wrapped(data)
        rels = out["word/_rels/document.xml.rels"].decode()
        for rid in ("rIdA1", "rIdA2", "rIdA3"):
            self.assertNotIn(f'Id="{rid}"', rels)
        assert_no_dangling(self, out)

    def test_a_child_that_is_no_relationship_or_override_is_not_taken_for_one(self):
        p = parts(with_leftovers())
        p["word/_rels/document.xml.rels"] = p["word/_rels/document.xml.rels"].replace(b"</Relationships>", b'<Note Target="comments.xml"/></Relationships>')
        p["[Content_Types].xml"] = p["[Content_Types].xml"].replace(b"</Types>", b'<Note PartName="/word/comments.xml"/></Types>')
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
            for n, d in p.items():
                z.writestr(zipfile.ZipInfo(n, (2020, 1, 1, 0, 0, 0)), d, zipfile.ZIP_DEFLATED)
        got = self.wrapped(out.getvalue())
        self.assertIn(b'<Note Target="comments.xml"', got["word/_rels/document.xml.rels"])
        self.assertIn(b'<Note PartName="/word/comments.xml"', got["[Content_Types].xml"])

    def test_the_relationships_of_a_dropped_part_go_with_it_whatever_the_case_of_its_name(self):
        rels = HEAD + '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"></Relationships>'
        data = template(extra=[("word/Comments.xml", COMMENTS), ("word/_rels/comments.xml.rels", rels)])
        out = self.wrapped(data)
        self.assertNotIn("word/_rels/comments.xml.rels", out)
        self.assertNotIn("word/Comments.xml", out)

    def test_a_rewritten_part_keeps_its_xml_declaration_and_default_namespace(self):
        for name in ("word/_rels/document.xml.rels", "[Content_Types].xml"):
            text = self.wrapped(with_leftovers())[name].decode()
            self.assertTrue(text.startswith("<?xml"), name)
            self.assertNotIn("ns0", text, name)
        self.assertIn('<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"',
                      self.wrapped(with_leftovers())["word/_rels/document.xml.rels"].decode())


class Parts(unittest.TestCase):
    def test_a_numbering_relationship_with_target_before_type_names_the_numbering_part(self):
        data = add_rels(f'<Relationship Id="rIdN" Target="num2.xml" Type="{REL}/numbering"/>')
        out = parts(word_brand.wrap(data, BUILT))
        self.assertIn("word/num2.xml", out)
        self.assertNotIn("word/numbering.xml", out)

    def test_content_types_already_declared_are_not_declared_twice(self):
        data = rebuilt(template(), lambda n, d: d.replace(
            b"</Types>", b'<Override PartName="/word/styles.xml" ContentType="x"/><Override PartName="/word/numbering.xml" ContentType="y"/></Types>')
            if n == "[Content_Types].xml" else d)
        ct = parts(word_brand.wrap(data, BUILT))["[Content_Types].xml"].decode()
        self.assertEqual(ct.count('PartName="/word/styles.xml"'), 1)
        self.assertEqual(ct.count('PartName="/word/numbering.xml"'), 1)
        self.assertEqual(ct.count('Extension="png"'), 1)

    def test_no_core_or_app_part_is_added_when_the_template_has_none_and_the_templates_stay_when_the_report_has_none(self):
        out = parts(word_brand.wrap(template(), BUILT))
        self.assertNotIn("docProps/core.xml", out)
        self.assertNotIn("docProps/app.xml", out)
        mine = parts(BUILT)
        self.assertIn("docProps/app.xml", mine)
        bare = rebuilt(BUILT, lambda n, d: None if n.startswith("docProps/") else d)
        t = template(extra=[("docProps/app.xml", HEAD + '<Properties xmlns="x"><Company>ZQS5</Company></Properties>')])
        got = parts(word_brand.wrap(t, bare))
        self.assertIn(b"ZQS5", got["docProps/app.xml"])

    def test_every_entry_is_a_deflated_unix_file_with_mode_644(self):
        with zipfile.ZipFile(io.BytesIO(word_brand.wrap(with_leftovers(), BUILT))) as z:
            for i in z.infolist():
                self.assertEqual((i.create_system, i.external_attr >> 16, i.compress_type), (3, 0o644, zipfile.ZIP_DEFLATED), i.filename)

    def test_a_report_exactly_at_the_size_limit_is_made_and_one_byte_over_is_refused_with_its_size_in_megabytes(self):
        size = len(word_brand.wrap(template(), BUILT))
        with mock.patch.object(docx_build, "MAX_BYTES", size):
            self.assertEqual(len(word_brand.wrap(template(), BUILT)), size)
        with mock.patch.object(docx_build, "MAX_BYTES", size - 1):
            with self.assertRaises(docx_build.WordError) as e:
                word_brand.wrap(template(), BUILT)
        self.assertIn(f"The report is {size / 1048576:.1f} MB,", str(e.exception))

    def test_a_styles_part_that_holds_the_closing_tag_twice_gets_the_gaps_before_the_last_one(self):
        styles = STYLES_WITH_COMMENT
        out = parts(word_brand.wrap(template(styles=styles), BUILT))
        root = ET.fromstring(out["word/styles.xml"])
        ids = [s.get(f"{{{W}}}styleId") for s in root]
        self.assertIn("Heading1", ids)

    def test_a_styles_part_that_is_not_utf8_is_refused_in_words(self):
        with self.assertRaises(WordRefused) as e:
            word_brand.wrap(template(styles=b"\xff\xfe<w:styles/>"), BUILT)
        self.assertIn("can't be read", str(e.exception))


STYLES_WITH_COMMENT = (HEAD + f'<w:styles xmlns:w="{W}"><!-- </w:styles> --><w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/>'
                       '</w:style></w:styles>')


class FindUnreadable(unittest.TestCase):
    def test_a_path_with_a_null_byte_is_no_template(self):
        self.assertIsNone(word_brand.find("brand\0folder"))

    def test_a_folder_that_links_to_itself_is_no_template(self):
        with tempfile.TemporaryDirectory() as d:
            loop = Path(d) / "loop"
            os.symlink(loop, loop)
            self.assertIsNone(word_brand.find(loop))

    def test_an_error_in_reading_the_size_is_no_template(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d) / "brand"
            (base / "word").mkdir(parents=True)
            (base / "word" / "template.docx").write_bytes(b"x")
            with mock.patch.object(Path, "stat", side_effect=OSError("denied")):
                self.assertIsNone(word_brand.find(base))


if __name__ == "__main__":
    unittest.main()
