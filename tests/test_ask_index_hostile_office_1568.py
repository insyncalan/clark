"""Row 1568 (leftovers of the ask index spike, row 1368): hostile Excel, PowerPoint and HTML files.
The index reads stored cell values, slide text and visible page text only: nothing is run and nothing is fetched. Made-up files only."""
import io
import socket
import unittest
import zipfile
from unittest import mock

from _paths import SRC  # noqa: F401

from test_ask_index_1366 import Base, ix
from test_ask_index_types_1366 import xlsx, pptx

URL = "http://127.0.0.1:9/"
REL = ('<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
       '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/%s" Target="%s" TargetMode="External"/>'
       '</Relationships>')


def with_members(raw, extra):
    out = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(raw)) as src, zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for info in src.infolist():
            z.writestr(info.filename, src.read(info.filename))
        for name, data in extra.items():
            z.writestr(name, data)
    return out.getvalue()


class Hostile(Base):
    def setUp(self):
        super().setUp()
        self.connects = []
        def refuse(*a, **k):
            self.connects.append(a)
            raise OSError("blocked")
        for owner, name in ((socket.socket, "connect"), (socket.socket, "connect_ex"), (socket, "create_connection")):
            p = mock.patch.object(owner, name, refuse)
            p.start()
            self.addCleanup(p.stop)

    def status(self):
        return ix.status(self.data, "P1", [self.box])

    def test_xlsm_with_macro_and_external_link_reads_cell_values_only(self):
        raw = with_members(xlsx({"Plan": [["item"], ["zqxlcell"]]}), {
            "xl/vbaProject.bin": b"zzvbamarker",
            "xl/externalLinks/externalLink1.xml": b'<externalLink xmlns="x"/>',
            "xl/externalLinks/_rels/externalLink1.xml.rels": (REL % ("externalLinkPath", URL + "zzext")).encode()})
        self.put("macro.xlsm", raw, binary=True)
        self.build()
        s = self.status()
        self.assertEqual((s["indexed"], s["type"], s["safety"]), (1, 0, 0))
        self.assertEqual(len(self.found("zqxlcell")), 1)
        self.assertFalse(self.found("zzvbamarker"))
        self.assertFalse(self.found("zzext"))
        self.assertEqual(self.connects, [])

    def test_a_workbook_left_out_as_type_is_counted_and_listed(self):
        self.put("bad.xlsx", b"PK\x03\x04 not really", binary=True)
        self.build()
        s = self.status()
        self.assertEqual((s["indexed"], s["type"], s["safety"]), (0, 1, 0))
        left = ix.mod().files_left_out(self.data, "P1", 200)
        self.assertEqual(left["files"], [("saved/bad.xlsx", ix.mod().REASON_TYPE)])
        self.assertEqual(left["more"], 0)
        self.assertFalse(self.found("PK"))

    def test_pptx_with_macro_part_and_external_link_reads_slide_text_only(self):
        raw = pptx({1: ["zqpptx"]}, extra={
            "ppt/vbaProject.bin": b"zzvbappt",
            "ppt/slides/_rels/slide1.xml.rels": (REL % ("hyperlink", URL + "zzpptext")).encode()})
        self.put("deck.pptx", raw, binary=True)
        self.build()
        self.assertEqual(self.status()["indexed"], 1)
        self.assertEqual(len(self.found("zqpptx")), 1)
        for w in ("zzvbappt", "zzpptext"):
            self.assertFalse(self.found(w), w)
        self.assertEqual(self.connects, [])

    def test_html_with_script_injection_and_odd_encodings_gives_visible_text_only(self):
        page = (b"<p>zqhtml</p><script>zzscr()</script><a href=\"javascript:zzjs()\">zqlink</a>"
                b"<img src=\"" + URL.encode() + b"zzimg\" onerror=\"zzerr()\">"
                b"<p>+ADw-script+AD4-zzutf7</p><p>zqbad \xff\xfe</p>"
                b"<iframe src=\"" + URL.encode() + b"zzframe\">zziframe</iframe>")
        self.put("evil.html", page, binary=True)
        self.build()
        self.assertEqual(self.status()["indexed"], 1)
        self.assertEqual(len(self.found("zqhtml")), 1)
        self.assertEqual(len(self.found("zqlink")), 1)
        for w in ("zzscr", "zzjs", "zzimg", "zzerr", "zzframe", "zziframe"):
            self.assertFalse(self.found(w), w)
        self.assertIn("+ADw-script+AD4-zzutf7", self.found("zzutf7")[0][1])
        self.assertIn("zqbad ��", self.found("zqbad")[0][1])
        self.assertEqual(self.connects, [])


if __name__ == "__main__":
    unittest.main()
