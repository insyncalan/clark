"""Row 853: the Word report on the brand's own Word template (src/clark/word_brand.py).

Run: python3 dev/run_tests.py test_word_brand
No browser. The template is made in the test from made-up text. Asserted: the report's body is in the template's file; the
template's page set-up, header, footer, picture and style are the template's own bytes; the report's styles fill only the
gaps; links and pictures come across under their own ids; a template that is unsafe is refused in words; a folder with no
template, a link out of the folder or a missing folder gives None.
"""
import io
import os
import re
import tempfile
import unittest
import zipfile
from pathlib import Path

from _paths import ROOT   # noqa: F401

import _publish_fixture as fx
from clark import docx_build, docx_read, publish, word_brand
from clark.docx_read import WordRefused
from test_word_client_held_back import Setup

W = docx_build.NS_W
R = docx_build.NS_R
HEAD = docx_build.HEAD
MAIN = "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
SECT = ('<w:sectPr><w:headerReference w:type="default" r:id="rId7"/><w:pgSz w:w="12240" w:h="15840"/>'
        '<w:pgMar w:top="2000" w:right="900" w:bottom="900" w:left="900" w:header="400" w:footer="400" w:gutter="0"/></w:sectPr>')
LOGO = b"\x89PNG\r\n\x1a\nmade-up-logo-bytes"
STYLES = (HEAD + f'<w:styles xmlns:w="{W}"><w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/>'
          '<w:rPr><w:color w:val="AA0000"/></w:rPr></w:style></w:styles>')


def template(sect=SECT, styles=STYLES, extra=(), rels_extra="", body="<w:p><w:r><w:t>Letterhead words</w:t></w:r></w:p>"):
    entries = [("[Content_Types].xml", HEAD + '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                '<Default Extension="xml" ContentType="application/xml"/><Default Extension="png" ContentType="image/png"/>'
                f'<Override PartName="/word/document.xml" ContentType="{MAIN}"/></Types>'),
               ("_rels/.rels", HEAD + '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                f'<Relationship Id="rId1" Type="{REL}/officeDocument" Target="word/document.xml"/></Relationships>'),
               ("word/document.xml", HEAD + f'<w:document xmlns:w="{W}" xmlns:r="{R}"><w:body>{body}{sect}</w:body></w:document>'),
               ("word/_rels/document.xml.rels", HEAD + '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                f'<Relationship Id="rId7" Type="{REL}/header" Target="header1.xml"/>'
                f'<Relationship Id="rId5" Type="{REL}/image" Target="media/image1.png"/>' + rels_extra + "</Relationships>"),
               ("word/header1.xml", HEAD + f'<w:hdr xmlns:w="{W}"><w:p><w:r><w:t>Brand header</w:t></w:r></w:p></w:hdr>'),
               ("word/media/image1.png", LOGO)]
    if styles:
        entries.append(("word/styles.xml", styles))
    entries += list(extra)
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for n, d in entries:
            z.writestr(zipfile.ZipInfo(n, (2020, 1, 1, 0, 0, 0)), d, zipfile.ZIP_DEFLATED)
    return out.getvalue()


def parts(data):
    z = zipfile.ZipFile(io.BytesIO(data))
    return {i.filename: z.read(i.filename) for i in z.infolist()}


BUILT = docx_build.build(publish.select(fx.inputs(None)))


class Wrap(unittest.TestCase):
    def setUp(self):
        self.t = template()
        self.out = parts(word_brand.wrap(self.t, BUILT))
        self.doc = self.out["word/document.xml"].decode()

    def test_the_report_body_is_in_the_templates_file_and_the_page_set_up_is_the_templates(self):
        built = parts(BUILT)["word/document.xml"].decode()
        title = re.search(r"<w:p>.*?</w:p>", built[built.index("<w:body>"):]).group(0)
        self.assertIn(title, self.doc)
        self.assertTrue(self.doc.rstrip().endswith(SECT + "</w:body></w:document>"))
        self.assertNotIn("Letterhead words", self.doc)               # the template's own body text is not the report
        self.assertNotIn('w:w="11906"', self.doc)

    def test_header_picture_and_styles_of_the_template_are_kept_and_the_gaps_filled(self):
        t = parts(self.t)
        self.assertEqual(self.out["word/header1.xml"], t["word/header1.xml"])
        self.assertEqual(self.out["word/media/image1.png"], LOGO)
        styles = self.out["word/styles.xml"].decode()
        self.assertEqual(styles.count('w:styleId="Title"'), 1)
        self.assertIn('w:val="AA0000"', styles)
        for sid in ("Heading1", "TableText", "ListParagraph", "Hyperlink"):
            self.assertIn(f'w:styleId="{sid}"', styles)

    def test_the_reports_pictures_and_links_get_ids_the_template_cannot_use(self):
        rels = self.out["word/_rels/document.xml.rels"].decode()
        ids = re.findall(r'Id="([^"]+)"', rels)
        self.assertEqual(len(ids), len(set(ids)))
        for used in set(re.findall(r'r:(?:id|embed)="([^"]+)"', self.doc)):
            self.assertIn(used, ids)
        self.assertIn("rId7", ids)
        self.assertTrue(any(n.startswith("word/media/clark-image") for n in self.out))
        for n in (n for n in self.out if n.startswith("word/media/clark-")):
            self.assertIn(n.split("/", 1)[1], rels)
        self.assertIn('Extension="png"', self.out["[Content_Types].xml"].decode())

    def test_every_part_is_well_formed_and_the_file_reads_back_as_the_reports_words(self):
        import xml.dom.minidom
        for n, d in self.out.items():
            if n.endswith((".xml", ".rels")):
                xml.dom.minidom.parseString(d)
        got = docx_read.read(word_brand.wrap(self.t, BUILT), "x.docx")
        want = docx_read.read(BUILT, "y.docx")
        self.assertEqual([b for b in got.blocks], [b for b in want.blocks])

    def test_the_same_inputs_give_the_same_bytes(self):
        self.assertEqual(word_brand.wrap(self.t, BUILT), word_brand.wrap(self.t, BUILT))

    def test_a_template_with_no_page_set_up_or_styles_still_makes_a_file(self):
        out = parts(word_brand.wrap(template(sect="", styles=None), BUILT))
        self.assertNotIn("footerReference", out["word/document.xml"].decode())
        self.assertIn('w:styleId="Heading1"', out["word/styles.xml"].decode())
        self.assertIn("styles", out["word/_rels/document.xml.rels"].decode())

    def test_the_author_is_clark_not_the_templates(self):
        t = template(extra=[("docProps/core.xml", b"<core>A Person</core>")])
        out = parts(word_brand.wrap(t, BUILT))
        self.assertNotIn(b"A Person", out["docProps/core.xml"])
        self.assertIn(b"clark", out["docProps/core.xml"])


class Refuses(unittest.TestCase):
    def test_a_macro_template_is_refused_in_words_naming_it(self):
        with self.assertRaises(WordRefused) as e:
            word_brand.wrap(template(extra=[("word/vbaProject.bin", b"x")]), BUILT)
        self.assertIn("The Word template in the branding folder", str(e.exception))

    def test_a_linked_template_is_refused(self):
        bad = f'<Relationship Id="rId9" Type="{REL}/attachedTemplate" Target="http://x.invalid/t.dotm" TargetMode="External"/>'
        with self.assertRaises(WordRefused):
            word_brand.wrap(template(rels_extra=bad), BUILT)

    def test_not_a_zip_is_refused(self):
        with self.assertRaises(WordRefused):
            word_brand.wrap(b"not a word file", BUILT)


class Find(unittest.TestCase):
    def test_found_only_as_a_plain_file_inside_the_folder(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d) / "brand"
            (base / "word").mkdir(parents=True)
            self.assertIsNone(word_brand.find(base))
            (base / "word" / "template.docx").write_bytes(b"x")
            self.assertEqual(word_brand.find(base), (base / "word" / "template.docx").resolve())
            self.assertIsNone(word_brand.find(os.devnull))
            self.assertIsNone(word_brand.find(Path(d) / "missing"))

    def test_a_link_to_a_file_outside_is_not_followed(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d) / "brand"
            (base / "word").mkdir(parents=True)
            (Path(d) / "outside.docx").write_bytes(b"x")
            os.symlink(Path(d) / "outside.docx", base / "word" / "template.docx")
            self.assertIsNone(word_brand.find(base))

    def test_a_linked_word_folder_is_not_followed(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d) / "brand"
            base.mkdir()
            (Path(d) / "elsewhere" / "").mkdir()
            (Path(d) / "elsewhere" / "template.docx").write_bytes(b"x")
            os.symlink(Path(d) / "elsewhere", base / "word")
            self.assertIsNone(word_brand.find(base))


class Route(Setup, unittest.TestCase):
    """The export through the route: the brand folder's template is used, a bad one stops the export, none leaves it as it was."""

    def setUp(self):
        super().setUp()
        self.brand = Path(tempfile.mkdtemp(prefix="clark-853-"))
        self.addCleanup(__import__("shutil").rmtree, self.brand, True)
        (self.brand / "word").mkdir()

    def plant(self):
        pass

    def export(self):
        from unittest import mock
        from clark import word_route
        from test_word_client_held_back import TODAY, USER
        seam = word_route.make_word_export(self.store.path, [], USER, today=lambda: TODAY,
                                           choose_folder=lambda prompt: str(self.word_local))
        with mock.patch("clark.publish_flow.brand_of", return_value=self.brand):
            return seam({"project": "ABC", "to_client": False})

    def saved(self):
        (name,) = self.names(self.word_local)
        return parts((self.word_local / name).read_bytes())

    def test_a_template_in_the_brand_folder_is_the_file_the_report_is_saved_on(self):
        (self.brand / "word" / "template.docx").write_bytes(template())
        status, got = self.export()
        self.assertEqual((status, got["ok"]), (200, True), got)
        out = self.saved()
        self.assertEqual(out["word/header1.xml"], parts(template())["word/header1.xml"])
        self.assertIn("<w:pgSz w:w=\"12240\"", out["word/document.xml"].decode())

    def test_no_template_leaves_the_report_as_built(self):
        status, got = self.export()
        self.assertEqual((status, got["ok"]), (200, True), got)
        self.assertNotIn("word/header1.xml", self.saved())

    def test_a_template_that_cannot_be_used_stops_the_export_in_words_and_saves_nothing(self):
        (self.brand / "word" / "template.docx").write_bytes(b"not a word file")
        status, got = self.export()
        self.assertFalse(got["ok"], got)
        self.assertTrue(got["message"].startswith("The Word template in the branding folder can't be used"), got)
        self.assertTrue(got["message"].endswith("Nothing was saved."), got)
        self.assertEqual(self.names(self.word_local), [])


if __name__ == "__main__":
    unittest.main()
