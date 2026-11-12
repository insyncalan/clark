"""Client-leak hunt B4: a brand's Word template (word/template.docx) carries parts the report never draws: review comments and
the people who wrote them, custom properties (a sensitivity label, an internal id), the preview picture of the template's first page,
custom XML, a glossary. The report is built on that file (word_brand.wrap) and goes to the client, so none of them may travel with it,
and nothing left behind may point at a part that was dropped (Word calls such a file damaged). The header, footer, styles, theme,
numbering and pictures of the template are kept (test_word_brand has those). Made-up words only: every marker starts ZQB4.

Run: python3 dev/run_tests.py test_word_brand_leftovers
"""
import io
import re
import unittest
import zipfile

from _paths import ROOT   # noqa: F401

from test_word_brand import BUILT, HEAD, REL, W, parts, template
from clark import word_brand

COMMENTS = HEAD + f'<w:comments xmlns:w="{W}"><w:comment w:id="0" w:author="Insider"><w:p><w:r><w:t>ZQB4-comment</w:t></w:r></w:p></w:comment></w:comments>'
LEFT = {                                    # part name -> bytes holding a marker
    "word/comments.xml": COMMENTS.encode(),
    "word/commentsExtended.xml": b"<x>ZQB4-ext</x>",
    "word/people.xml": b"<people>ZQB4-people insider@corp.example</people>",
    "docProps/custom.xml": b"<Properties>ZQB4-custom-label</Properties>",
    "docProps/thumbnail.jpeg": b"\xff\xd8\xffZQB4-thumbnail",
    "customXml/item1.xml": b"<x>ZQB4-customxml</x>",
    "customXml/itemProps1.xml": b"<x>ZQB4-itemprops</x>",
    "word/glossary/document.xml": b"<g>ZQB4-glossary</g>",
}
KEPT = {"word/header1.xml": b"Brand header", "word/media/image1.png": None}


def with_leftovers():
    """The plain test template plus every LEFT part, with the content types and relationships that name them."""
    p = parts(template())
    p.update(LEFT)
    types = "".join(f'<Override PartName="/{n}" ContentType="application/xml"/>' for n in LEFT if n.endswith(".xml"))
    p["[Content_Types].xml"] = p["[Content_Types].xml"].replace(b"</Types>", types.encode() + b"</Types>")
    doc = "".join(f'<Relationship Id="rIdX{i}" Type="{REL}/{kind}" Target="{target}"/>' for i, (kind, target) in enumerate(
        (("comments", "comments.xml"), ("people", "people.xml"), ("customXml", "../customXml/item1.xml"), ("glossaryDocument", "glossary/document.xml"))))
    p["word/_rels/document.xml.rels"] = p["word/_rels/document.xml.rels"].replace(b"</Relationships>", doc.encode() + b"</Relationships>")
    top = (f'<Relationship Id="rIdT1" Type="{REL}/custom-properties" Target="docProps/custom.xml"/>'
           f'<Relationship Id="rIdT2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/thumbnail" Target="docProps/thumbnail.jpeg"/>')
    p["_rels/.rels"] = p["_rels/.rels"].replace(b"</Relationships>", top.encode() + b"</Relationships>")
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for n, d in p.items():
            z.writestr(zipfile.ZipInfo(n, (2020, 1, 1, 0, 0, 0)), d, zipfile.ZIP_DEFLATED)
    return out.getvalue()


class Leftovers(unittest.TestCase):
    def setUp(self):
        self.out = parts(word_brand.wrap(with_leftovers(), BUILT))

    def test_no_byte_of_the_file_holds_a_marker_from_a_part_the_report_never_draws(self):
        for name, data in self.out.items():
            self.assertNotIn(b"ZQB4", data, name)
            self.assertNotIn(b"insider@corp", data, name)

    def test_those_parts_are_not_in_the_file(self):
        for name in LEFT:
            self.assertNotIn(name, self.out)

    def test_nothing_left_names_a_part_that_is_gone(self):
        for name, data in self.out.items():
            if not name.endswith(".rels"):
                continue
            base = name.replace("_rels/", "").rsplit("/", 1)[0] if "/" in name.replace("_rels/", "") else ""
            for target, mode in re.findall(rb'Target="([^"]*)"(?: TargetMode="(\w+)")?', data):
                if mode == b"External":
                    continue
                path = target.decode().lstrip("/") if target.startswith(b"/") else "/".join(
                    x for x in (base + "/" + target.decode()).split("/") if x)
                parts_ = []
                for seg in path.split("/"):
                    if seg == "..":
                        parts_ and parts_.pop()
                    elif seg:
                        parts_.append(seg)
                self.assertIn("/".join(parts_), self.out, f"{name} points at {target!r}")
        types = self.out["[Content_Types].xml"].decode()
        for part in re.findall(r'PartName="/([^"]+)"', types):
            self.assertIn(part, self.out, f"[Content_Types].xml names {part}")

    def test_the_templates_own_look_is_kept(self):
        kept = parts(template())
        for name in ("word/header1.xml", "word/media/image1.png", "word/styles.xml"):
            self.assertIn(name, self.out)
        self.assertEqual(self.out["word/header1.xml"], kept["word/header1.xml"])
        self.assertEqual(self.out["word/media/image1.png"], kept["word/media/image1.png"])


if __name__ == "__main__":
    unittest.main()
