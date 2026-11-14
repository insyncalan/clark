"""Row 853 (PR 1356) mutation hunt: the edges of word_brand that test_word_brand left open (the ids the report brings, the app part,
the numbering and picture parts a template lacks, the template's own name for its numbering part, the size limits, a body-less
template, and what counts as a template file in the folder).

Run: python3 dev/run_tests.py test_word_brand_edges      No browser; the templates are made in the test from made-up text.
"""
import io
import os
import re
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from _paths import ROOT   # noqa: F401

import _publish_fixture as fx
from clark import docx_build, docx_read, publish, word_brand
from clark.docx_read import WordRefused
from test_word_brand import BUILT, HEAD, REL, W, parts, template


def rebuilt(data, change):
    """The zip `data` with each part passed through change(name, bytes) -> bytes, or None to drop the part."""
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for n, d in parts(data).items():
            d = change(n, d)
            if d is not None:
                z.writestr(zipfile.ZipInfo(n, (2020, 1, 1, 0, 0, 0)), d, zipfile.ZIP_DEFLATED)
    return out.getvalue()


class Ids(unittest.TestCase):
    def test_every_id_the_report_brings_has_the_brand_prefix(self):
        out = parts(word_brand.wrap(template(), BUILT))
        doc = out["word/document.xml"].decode()
        used = set(re.findall(r'r:(?:id|embed)="([^"]+)"', doc)) - {"rId7"}       # rId7 is the template's own header
        self.assertTrue(used, "the report has links or pictures")
        for rid in used:
            self.assertTrue(rid.startswith(word_brand.PREFIX), rid)
        self.assertEqual(word_brand.PREFIX, "rIdBrand")


class TemplateNumbering(unittest.TestCase):
    OLD = (HEAD + f'<w:numbering xmlns:w="{W}"><w:abstractNum w:abstractNumId="0"><w:lvl w:ilvl="0"><w:numFmt w:val="decimal"/>'
           '<w:lvlText w:val="%1."/></w:lvl></w:abstractNum><w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num></w:numbering>')

    def test_the_templates_own_lists_stay_and_the_reports_come_after_them(self):
        extra = f'<Relationship Id="rId8" Type="{REL}/numbering" Target="numbering.xml"/>'
        plant = publish.select(fx.inputs(None))
        plant["data"]["use_cases"][0]["standing"] = "<ul><li>ZQ-A</li></ul><ol><li>ZQ-B</li></ol>"
        out = parts(word_brand.wrap(template(rels_extra=extra, extra=[("word/numbering.xml", self.OLD)]), docx_build.build(plant)))
        num = out["word/numbering.xml"].decode()
        self.assertRegex(num, r'<w:abstractNum w:abstractNumId="0">.*?<w:numFmt w:val="decimal"/>')           # numId 1 is still decimal
        self.assertRegex(num, r'<w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num>')
        ids = [int(v) for v in re.findall(r'<w:num w:numId="(\d+)"', num)]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertGreater(len(ids), 1)
        used = {int(v) for v in re.findall(r'<w:numId w:val="(\d+)"', out["word/document.xml"].decode())}
        self.assertTrue(used and used <= set(ids) - {1}, used)                  # the report's bullets and numbers use only its own ids
        self.assertTrue(re.search(r'<w:abstractNum w:abstractNumId="1".*?bullet', num, re.S))


class WhatATemplateLacks(unittest.TestCase):
    def test_a_template_with_no_numbering_part_gets_one_and_a_relationship_to_it(self):
        out = parts(word_brand.wrap(template(), BUILT))
        self.assertIn("word/numbering.xml", out)
        self.assertRegex(out["word/_rels/document.xml.rels"].decode(), r'Type="[^"]*/numbering" Target="numbering.xml"')
        self.assertIn('PartName="/word/numbering.xml"', out["[Content_Types].xml"].decode())

    def test_a_template_that_names_its_numbering_part_differently_keeps_that_name(self):
        extra = f'<Relationship Id="rId8" Type="{REL}/numbering" Target="lists2.xml"/>'
        out = parts(word_brand.wrap(template(rels_extra=extra, extra=[("word/lists2.xml", b"<old/>")]), BUILT))
        self.assertNotIn("word/numbering.xml", out)
        self.assertNotEqual(out["word/lists2.xml"], b"<old/>")                    # the report's own list definitions
        self.assertIn('PartName="/word/lists2.xml"', out["[Content_Types].xml"].decode())
        self.assertEqual(out["word/_rels/document.xml.rels"].decode().count("/numbering\""), 1)

    def test_a_template_with_no_picture_type_gets_png_declared_for_the_reports_pictures(self):
        t = rebuilt(template(), lambda n, d: d.replace(b'<Default Extension="png" ContentType="image/png"/>', b"") if n == "[Content_Types].xml" else d)
        self.assertNotIn(b'Extension="png"', parts(t)["[Content_Types].xml"])
        out = parts(word_brand.wrap(t, BUILT))
        self.assertIn('<Default Extension="png" ContentType="image/png"/>', out["[Content_Types].xml"].decode())

    def test_a_template_whose_root_does_not_name_the_relationship_space_gets_it(self):
        t = rebuilt(template(sect=""), lambda n, d: d.replace(f' xmlns:r="{docx_build.NS_R}"'.encode(), b"") if n == "word/document.xml" else d)
        self.assertNotIn(b"xmlns:r=", parts(t)["word/document.xml"])
        doc = parts(word_brand.wrap(t, BUILT))["word/document.xml"].decode()
        self.assertEqual(len(re.findall(r'xmlns:r="', doc)), 1)
        self.assertIn(f'xmlns:r="{docx_build.NS_R}"', doc)

    def test_the_company_in_the_templates_app_part_is_replaced_by_clarks(self):
        t = template(extra=[("docProps/app.xml", b"<Properties><Company>A Brand Company</Company></Properties>")])
        out = parts(word_brand.wrap(t, BUILT))
        self.assertNotIn(b"A Brand Company", out["docProps/app.xml"])

    def test_a_template_with_no_body_is_refused_in_words(self):
        t = rebuilt(template(), lambda n, d: re.sub(rb"<w:body>.*</w:body>", b"", d, flags=re.S) if n == "word/document.xml" else d)
        with self.assertRaises(WordRefused) as e:
            word_brand.wrap(t, BUILT)
        self.assertIn("it has no body", str(e.exception))

    def test_a_doctype_in_a_relationships_part_is_refused(self):
        evil = HEAD + '<!DOCTYPE r [<!ENTITY e "boom">]><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>'
        with self.assertRaises(WordRefused):
            word_brand.wrap(template(extra=[("word/_rels/header1.xml.rels", evil)]), BUILT)

    def test_a_report_over_the_size_limit_is_refused_in_words(self):
        with mock.patch.object(docx_build, "MAX_BYTES", 1000):
            with self.assertRaises(docx_build.WordError) as e:
                word_brand.wrap(template(), BUILT)
        self.assertIn("over the", str(e.exception))
        self.assertTrue(word_brand.wrap(template(), BUILT))


class FindEdges(unittest.TestCase):
    def folder(self, d):
        base = Path(d) / "brand"
        (base / "word").mkdir(parents=True)
        return base, base / "word" / "template.docx"

    def test_a_folder_called_template_docx_is_no_template(self):
        with tempfile.TemporaryDirectory() as d:
            base, found = self.folder(d)
            found.mkdir()
            self.assertIsNone(word_brand.find(base))

    def test_a_link_to_a_file_inside_the_folder_is_not_followed_either(self):
        with tempfile.TemporaryDirectory() as d:
            base, found = self.folder(d)
            (base / "real.docx").write_bytes(b"x")
            os.symlink(base / "real.docx", found)
            self.assertIsNone(word_brand.find(base))

    def test_a_file_exactly_at_the_readers_limit_is_found_and_one_byte_over_is_not(self):
        with tempfile.TemporaryDirectory() as d:
            base, found = self.folder(d)
            found.write_bytes(b"x" * 10)
            with mock.patch.object(docx_read, "MAX_FILE_BYTES", 10):
                self.assertEqual(word_brand.find(base), found.resolve())
            with mock.patch.object(docx_read, "MAX_FILE_BYTES", 9):
                self.assertIsNone(word_brand.find(base))


if __name__ == "__main__":
    unittest.main()
