"""Hostile cases for src/clark/word_brand.py (row 853). Run: python3 dev/run_tests.py test_hostile_h1293. No browser."""
import io
import re
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from _paths import ROOT   # noqa: F401

from clark import docx_build, word_brand
from clark.docx_read import WordRefused
from test_word_brand import BUILT, REL, SECT, STYLES, W, template, parts


def zip_of(entries):
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for n, d in entries:
            z.writestr(zipfile.ZipInfo(n, (2020, 1, 1, 0, 0, 0)), d, zipfile.ZIP_DEFLATED)
    return out.getvalue()


def swap(data, name, new):
    p = parts(data)
    p[name] = new
    return zip_of(list(p.items()))


class Hostile(unittest.TestCase):
    def test_find_size_boundary(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            (base / "word").mkdir()
            f = base / "word" / "template.docx"
            f.write_bytes(b"x" * 10)
            with mock.patch.object(word_brand._r, "MAX_FILE_BYTES", 10):
                self.assertEqual(word_brand.find(base), f.resolve())
            with mock.patch.object(word_brand._r, "MAX_FILE_BYTES", 9):
                self.assertIsNone(word_brand.find(base))

    def test_find_directory_named_template_and_bad_arguments(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "word" / "template.docx").mkdir(parents=True)
            self.assertIsNone(word_brand.find(d))
        self.assertIsNone(word_brand.find("\0bad"))

    def test_on_template_without_template_returns_the_same_bytes(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIs(word_brand.on_template(BUILT, d), BUILT)

    def test_result_over_the_size_limit_is_a_word_error(self):
        with mock.patch.object(docx_build, "MAX_BYTES", 100):
            with self.assertRaises(docx_build.WordError):
                word_brand.wrap(template(), BUILT)

    def test_template_without_body_is_refused(self):
        bad = swap(template(), "word/document.xml", f'<w:document xmlns:w="{W}"></w:document>'.encode())
        with self.assertRaises(WordRefused) as e:
            word_brand.wrap(bad, BUILT)
        self.assertIn("no body", str(e.exception))

    def test_template_document_not_utf8_is_refused(self):
        bad = swap(template(), "word/document.xml", b"\xff\xfe<w:document/>")
        with self.assertRaises(WordRefused):
            word_brand.wrap(bad, BUILT)

    def test_template_without_document_part_is_refused(self):
        p = parts(template())
        del p["word/document.xml"]
        with self.assertRaises(WordRefused):
            word_brand.wrap(zip_of(list(p.items())), BUILT)

    def test_unicode_in_template_header_survives_and_body_text_is_dropped(self):
        t = swap(template(body="<w:p><w:r><w:t>Briefkopf é中\U0001f600</w:t></w:r></w:p>"),
                 "word/header1.xml", ('<w:hdr xmlns:w="%s"><w:p><w:r><w:t>中文\U0001f600</w:t></w:r></w:p></w:hdr>' % W).encode())
        out = parts(word_brand.wrap(t, BUILT))
        self.assertIn("中文\U0001f600".encode(), out["word/header1.xml"])
        self.assertNotIn("Briefkopf".encode(), out["word/document.xml"])

    def test_document_root_without_namespaces_gets_w_and_r(self):
        t = swap(template(), "word/document.xml",
                 ('<w:document><w:body><w:p/>%s</w:body></w:document>' % SECT).replace("<w:document>", '<w:document xmlns:w="%s">' % W).encode())
        head = parts(word_brand.wrap(t, BUILT))["word/document.xml"].decode()
        self.assertIn("xmlns:r=", head)
        self.assertIn("xmlns:w=", head)

    def test_template_style_with_same_id_is_not_duplicated_and_extra_ids_not_repeated(self):
        out = parts(word_brand.wrap(template(), BUILT))["word/styles.xml"].decode()
        ids = re.findall(r'w:styleId="([^"]+)"', out)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(out.rstrip().endswith("</w:styles>"))

    def test_style_ids_with_attributes_in_other_order_are_still_recognised(self):
        styles = (STYLES.replace('<w:style w:type="paragraph" w:styleId="Title">',
                                 '<w:style w:styleId="Heading1" w:default="0" w:type="paragraph">'))
        out = parts(word_brand.wrap(template(styles=styles), BUILT))["word/styles.xml"].decode()
        self.assertEqual(out.count('w:styleId="Heading1"'), 1)

    def test_numbering_goes_to_the_templates_own_numbering_target(self):
        rels = f'<Relationship Id="rId3" Type="{REL}/numbering" Target="num-custom.xml"/>'
        ex = [("word/num-custom.xml", f'<w:numbering xmlns:w="{W}"/>')]
        out = parts(word_brand.wrap(template(rels_extra=rels, extra=ex), BUILT))
        self.assertEqual(out["word/num-custom.xml"], parts(BUILT)["word/numbering.xml"])
        self.assertNotIn("word/numbering.xml", out)
        self.assertEqual(out["word/_rels/document.xml.rels"].decode().count("/numbering"), 1)

    def test_numbering_target_before_type_attribute_order_is_found(self):
        rels = f'<Relationship Id="rId3" Target="n2.xml" Type="{REL}/numbering"/>'
        out = parts(word_brand.wrap(template(rels_extra=rels, extra=[("word/n2.xml", f'<w:numbering xmlns:w="{W}"/>')]), BUILT))
        self.assertEqual(out["word/n2.xml"], parts(BUILT)["word/numbering.xml"])

    def test_no_numbering_relationship_adds_one_and_a_content_type_override(self):
        out = parts(word_brand.wrap(template(), BUILT))
        self.assertIn("word/numbering.xml", out)
        self.assertRegex(out["word/_rels/document.xml.rels"].decode(), r'Type="[^"]*/numbering" Target="numbering.xml"')
        ct = out["[Content_Types].xml"].decode()
        self.assertIn('PartName="/word/numbering.xml"', ct)
        self.assertIn('PartName="/word/styles.xml"', ct)

    def test_content_type_overrides_not_duplicated_when_template_has_them(self):
        t = parts(template())
        ct = t["[Content_Types].xml"].decode().replace(
            "</Types>", f'<Override PartName="/word/styles.xml" ContentType="{docx_build.DOC_TYPE}.styles+xml"/></Types>')
        t["[Content_Types].xml"] = ct.encode()
        out = parts(word_brand.wrap(zip_of(list(t.items())), BUILT))["[Content_Types].xml"].decode()
        self.assertEqual(out.count('PartName="/word/styles.xml"'), 1)

    def test_png_default_not_added_twice_and_added_when_missing(self):
        ct = parts(word_brand.wrap(template(), BUILT))["[Content_Types].xml"].decode()
        self.assertEqual(ct.count('Extension="png"'), 1)
        t = parts(template())
        t["[Content_Types].xml"] = t["[Content_Types].xml"].replace(b'<Default Extension="png" ContentType="image/png"/>', b"")
        out = parts(word_brand.wrap(zip_of(list(t.items())), BUILT))
        if any(n.startswith("word/media/clark-") for n in out):
            self.assertEqual(out["[Content_Types].xml"].decode().count('Extension="png"'), 1)

    def test_template_sectpr_last_one_is_used_when_several(self):
        first = '<w:p><w:pPr><w:sectPr><w:pgSz w:w="1111" w:h="2222"/></w:sectPr></w:pPr></w:p>'
        t = template(body=first)
        doc = parts(word_brand.wrap(t, BUILT))["word/document.xml"].decode()
        self.assertNotIn('w:w="1111"', doc)
        self.assertIn('w:w="12240"', doc)

    def test_no_sectpr_in_template_strips_footer_reference_of_the_report(self):
        doc = parts(word_brand.wrap(template(sect=""), BUILT))["word/document.xml"].decode()
        self.assertNotIn("footerReference", doc)
        self.assertIn("<w:sectPr", doc)
        self.assertTrue(doc.endswith("</w:body></w:document>"))

    def test_existing_styles_relationship_is_not_added_twice(self):
        rels = f'<Relationship Id="rId2" Type="{REL}/styles" Target="styles.xml"/>'
        out = parts(word_brand.wrap(template(rels_extra=rels), BUILT))["word/_rels/document.xml.rels"].decode()
        self.assertEqual(len(re.findall(r'/styles"', out)), 1)
        self.assertNotIn("rIdBrandStyles", out)

    def test_no_sectpr_template_gets_the_reports_page_size_but_no_footer_part_reference(self):
        doc = parts(word_brand.wrap(template(sect=""), BUILT))["word/document.xml"].decode()
        self.assertRegex(doc, r"<w:pgSz [^>]*/>")
        self.assertNotRegex(doc, r"footerReference")

    def test_report_relationship_ids_are_all_prefixed_and_none_leak_unprefixed(self):
        out = parts(word_brand.wrap(template(), BUILT))
        doc = out["word/document.xml"].decode()
        body = doc[doc.index("<w:body>"):doc.rindex("<w:sectPr")]
        for used in re.findall(r'r:(?:id|embed)="([^"]+)"', body):
            self.assertTrue(used.startswith(word_brand.PREFIX), used)

    def test_docprops_of_the_report_replace_template_only_when_both_exist(self):
        out = parts(word_brand.wrap(template(extra=[("docProps/app.xml", b"<Properties><Company>Other Co</Company></Properties>")]), BUILT))
        self.assertNotIn(b"Other Co", out["docProps/app.xml"])
        out2 = parts(word_brand.wrap(template(), BUILT))
        self.assertEqual(out2["docProps/core.xml"] if "docProps/core.xml" in out2 else b"", out2.get("docProps/core.xml", b""))

    def test_output_is_a_valid_zip_with_template_order_first_and_no_duplicates(self):
        data = word_brand.wrap(template(), BUILT)
        names = zipfile.ZipFile(io.BytesIO(data)).namelist()
        self.assertEqual(len(names), len(set(names)))
        self.assertEqual(names[0], "[Content_Types].xml")
        self.assertIsNone(zipfile.ZipFile(io.BytesIO(data)).testzip())


if __name__ == "__main__":
    unittest.main()
