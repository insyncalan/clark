"""Item 613: a workbook's external links are never fetched or opened by Import workbook (excel_route.py and the excel_import reader
it uses). Fictional data only. Run: python3 dev/run_tests.py test_excel_import_no_fetch

The workbook is a real clark export with these added by hand with zipfile: two external workbook links
(xl/externalLinks/externalLinkN.xml and their _rels, one to an https address and one to file:///etc/passwd), a hyperlink with an
http Target on the Actions sheet, an image in a drawing whose relationship is TargetMode="External", and an OLE object relationship
with TargetMode="External". The check and the apply run through the route's real seam while every way out is watched:
socket.socket.connect, socket.create_connection, urllib.request.urlopen, http.client.HTTPConnection.request, and builtins.open (and
io.open, which pathlib uses) for any path outside the temporary folders.

What is asserted: nothing connects anywhere, nothing opens a link's target, and the import does what it does today: it SUCCEEDS
and ignores the links (the one edited row is listed and applied as ONE step, as for a workbook with no links).
"""
import builtins
import http.client
import io
import socket
import tempfile
import unittest
import urllib.request
import zipfile
from pathlib import Path
from unittest import mock

import _paths  # noqa: F401
from openpyxl import load_workbook
from test_excel_route import Base

REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
WEB_BOOK = "https://example.invalid/x.xlsx"
FILE_BOOK = "file:///etc/passwd"
WEB_PAGE = "http://example.invalid/page"
WEB_IMAGE = "https://example.invalid/picture.png"
OLE_FILE = "file:///etc/passwd"
TARGETS = (WEB_BOOK, FILE_BOOK, WEB_PAGE, WEB_IMAGE, OLE_FILE)
MARKS = ("example.invalid", "/etc/passwd")          # what any touch of a target would carry, as a URL, a host or a path


def _external_link(rid):
    return ('<externalLink xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="' + REL + '">'
            f'<externalBook r:id="{rid}"><sheetNames><sheetName val="Sheet1"/></sheetNames><sheetDataSet><sheetData sheetId="0">'
            '<row r="1"><cell r="A1"><v>1</v></cell></row></sheetData></sheetDataSet></externalBook></externalLink>').encode()


def _rels(*rels):
    body = "".join(f'<Relationship Id="{i}" Type="{REL}/{kind}" Target="{target}"{mode}/>' for i, kind, target, mode in rels)
    return ('<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' + body
            + "</Relationships>").encode()


EXT = ' TargetMode="External"'
DRAWING = ('<xdr:wsDr xmlns:xdr="http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing" '
           'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="' + REL + '"><xdr:oneCellAnchor>'
           '<xdr:from><xdr:col>0</xdr:col><xdr:colOff>0</xdr:colOff><xdr:row>0</xdr:row><xdr:rowOff>0</xdr:rowOff></xdr:from>'
           '<xdr:ext cx="100000" cy="100000"/><xdr:pic><xdr:nvPicPr><xdr:cNvPr id="2" name="Picture 1"/><xdr:cNvPicPr/>'
           '</xdr:nvPicPr><xdr:blipFill><a:blip r:link="rIdImg"/><a:stretch><a:fillRect/></a:stretch></xdr:blipFill><xdr:spPr>'
           '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></xdr:spPr></xdr:pic><xdr:clientData/></xdr:oneCellAnchor></xdr:wsDr>'
           ).encode()


def add_external_links(path, sheet="xl/worksheets/sheet2.xml"):
    """Rewrite the workbook at `path` with the external links of this module added (`sheet` is the Actions sheet of an export)."""
    with zipfile.ZipFile(path) as z:
        parts = {n: z.read(n) for n in z.namelist()}
    for n, target in ((1, WEB_BOOK), (2, FILE_BOOK)):
        parts[f"xl/externalLinks/externalLink{n}.xml"] = _external_link("rId1")
        parts[f"xl/externalLinks/_rels/externalLink{n}.xml.rels"] = _rels(("rId1", "externalLinkPath", target, EXT))
    parts["xl/_rels/workbook.xml.rels"] = parts["xl/_rels/workbook.xml.rels"].replace(b"</Relationships>", (
        f'<Relationship Id="rIdX1" Type="{REL}/externalLink" Target="externalLinks/externalLink1.xml"/>'
        f'<Relationship Id="rIdX2" Type="{REL}/externalLink" Target="externalLinks/externalLink2.xml"/></Relationships>').encode())
    book = parts["xl/workbook.xml"]
    assert b"</sheets>" in book and b"xmlns:r=" in book
    parts["xl/workbook.xml"] = book.replace(b"</sheets>", b'</sheets><externalReferences><externalReference r:id="rIdX1"/>'
                                            b'<externalReference r:id="rIdX2"/></externalReferences>')
    ws = parts[sheet]
    root = ws[:ws.index(b">") + 1]
    if b"xmlns:r=" not in root:                      # the export binds r only on the elements that use it
        ws = ws.replace(b"<worksheet ", f'<worksheet xmlns:r="{REL}" '.encode(), 1)
    assert b"<pageMargins" in ws
    ws = ws.replace(b"<pageMargins", b'<hyperlinks><hyperlink ref="A1" r:id="rIdLink"/></hyperlinks><pageMargins', 1)
    at = ws.find(b"<legacyDrawing")
    at = at if at >= 0 else ws.rindex(b"</worksheet>")
    ws = ws[:at] + b'<drawing r:id="rIdDraw"/>' + ws[at:]
    parts[sheet] = ws
    rels_name = sheet.replace("worksheets/", "worksheets/_rels/") + ".rels"
    mine = (f'<Relationship Id="rIdLink" Type="{REL}/hyperlink" Target="{WEB_PAGE}"{EXT}/>'
            f'<Relationship Id="rIdDraw" Type="{REL}/drawing" Target="/xl/drawings/drawing1.xml"/>'
            f'<Relationship Id="rIdOle" Type="{REL}/oleObject" Target="{OLE_FILE}"{EXT}/>').encode()
    parts[rels_name] = (parts[rels_name].replace(b"</Relationships>", mine + b"</Relationships>") if rels_name in parts
                        else _rels().replace(b"</Relationships>", mine + b"</Relationships>"))
    parts["xl/drawings/drawing1.xml"] = DRAWING
    parts["xl/drawings/_rels/drawing1.xml.rels"] = _rels(("rIdImg", "image", WEB_IMAGE, EXT))
    types = "".join(f'<Override PartName="/xl/externalLinks/externalLink{n}.xml" ContentType="application/vnd.openxmlformats-'
                    'officedocument.spreadsheetml.externalLink+xml"/>' for n in (1, 2))
    types += ('<Override PartName="/xl/drawings/drawing1.xml" ContentType="application/vnd.openxmlformats-officedocument.'
              'drawing+xml"/>')
    parts["[Content_Types].xml"] = parts["[Content_Types].xml"].replace(b"</Types>", types.encode() + b"</Types>")
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for n, b in parts.items():
            z.writestr(n, b)


class Watch:
    """Every network call, and every open of a path outside the temporary folders, made while it is on."""

    def __init__(self, test):
        self.network, self.opened = [], []
        temp = str(Path(tempfile.gettempdir()).resolve())
        real_open = builtins.open

        def spy(name, kind):
            def call(*args, **kwargs):
                self.network.append((name, repr(args[1:] if kind == "method" else args), repr(kwargs)))
                raise OSError("no network in this test")
            return call

        def watched_open(file, *args, **kwargs):
            if not isinstance(file, int):
                shown = str(file)
                try:
                    inside = str(Path(shown).resolve()).startswith(temp)
                except (OSError, ValueError):
                    inside = False
                if not inside:
                    self.opened.append(shown)
            return real_open(file, *args, **kwargs)

        for p in (mock.patch.object(socket.socket, "connect", spy("socket.connect", "method")),
                  mock.patch.object(socket, "create_connection", spy("socket.create_connection", "function")),
                  mock.patch.object(urllib.request, "urlopen", spy("urllib.request.urlopen", "function")),
                  mock.patch.object(http.client.HTTPConnection, "request", spy("HTTPConnection.request", "method")),
                  mock.patch.object(builtins, "open", watched_open),
                  mock.patch.object(io, "open", watched_open)):
            p.start()
            test.addCleanup(p.stop)

    def touched_a_target(self):
        return [o for o in self.opened if any(m in o for m in MARKS)]


class ExternalLinksAreNeverFetched(Base):
    def setUp(self):
        super().setUp()
        self.edit("Actions", self.a1, Description="Draft the cut-over plan, version two")
        add_external_links(self.path)

    def test_the_workbook_really_holds_the_links(self):
        with zipfile.ZipFile(self.path) as z:
            text = b"".join(z.read(n) for n in z.namelist() if n.endswith((".rels", ".xml")))
        for target in TARGETS:
            self.assertIn(target.encode(), text)
        self.assertEqual(text.count(b'TargetMode="External"'), 5)
        wb = load_workbook(str(self.path))                 # the reader the import uses sees the links (so the test is not empty)
        try:
            self.assertEqual(sorted(link.file_link.Target for link in wb._external_links), sorted((WEB_BOOK, FILE_BOOK)))
            self.assertEqual(wb["Actions"]["A1"].hyperlink.target, WEB_PAGE)
        finally:
            wb.close()

    def test_a_check_and_an_apply_never_connect_or_open_a_link_and_import_the_row_as_without_links(self):
        before = self.steps()
        watch = Watch(self)
        status, got = self.check()
        self.assertEqual((status, got["ok"]), (200, True), got)
        self.assertEqual([(i["n"], i["kind"], i["table"]) for i in got["items"]], [(1, "changed", "actions")])
        self.assertEqual((got["problems"], got["unrecorded"]), ([], False))
        status, done = self.apply(got["plan"])
        self.assertEqual((status, done["ok"]), (200, True), done)
        self.assertEqual(self.steps(), before + 1)
        self.assertEqual(self.description_of(self.a1), "Draft the cut-over plan, version two")
        self.assertEqual(watch.network, [])
        self.assertEqual(watch.touched_a_target(), [])
        for target in TARGETS:                             # no reply carries a link's address back to the page
            self.assertNotIn(target, repr((got, done)))

    def test_the_watch_would_see_a_fetch_and_an_open(self):
        watch = Watch(self)
        with self.assertRaises(OSError):
            urllib.request.urlopen(WEB_BOOK)
        with self.assertRaises(OSError):
            socket.create_connection(("example.invalid", 443))
        with self.assertRaises(OSError):
            http.client.HTTPConnection("example.invalid").request("GET", "/x.xlsx")
        try:
            open("/etc/passwd", "rb").close()
        except OSError:
            pass
        self.assertEqual(len(watch.network), 3)
        self.assertEqual(watch.touched_a_target(), ["/etc/passwd"])


if __name__ == "__main__":
    unittest.main()
