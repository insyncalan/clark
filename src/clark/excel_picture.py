"""The brand logo on the Excel Cover, with no Pillow and no committed picture (#133).

The logo is part of the user's own brand (system/branding, which git ignores and which is not in the public copy). When an export
runs it looks for the logo there, the same place the page finds its brand tokens (clark.page.local_tokens): `logo.png`, or
`design-system/logo.png`, in system/branding. If there is none, the Cover has its navy band and title only.

openpyxl's Image needs Pillow, so the picture is put in after openpyxl has saved, by editing the saved .xlsx (a zip) with the
standard library only: embed() adds xl/media/<name>.png, a drawing part, the Cover's <drawing r:id/> element, the Cover's and
the drawing's relationships and the content types. Reading a workbook back without Pillow drops pictures (openpyxl's
reader/drawings.py), and the import reads no Cover anyway, so the import never sees the logo.

Safe by design: the file is read as bytes and the pixels are never decoded. It is refused unless it is no bigger than 1 MB, starts
with the PNG signature, has the header chunk (IHDR) first and in full, and is between 1 and 2000 pixels each way. A refused logo
does not stop the export: the Cover is written without it, and the export logs a warning that says why. (A logo is a nicety on
a local file; losing someone's work items export over it would be the worse outcome.)
"""
import logging
import re
import struct
import zlib
from pathlib import Path
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape

SIGNATURE = b"\x89PNG\r\n\x1a\n"
MAX_BYTES = 1024 * 1024
MAX_PIXELS = 2000
LOCAL_LOGOS = ("logo.png", "design-system/logo.png")     # in the brand folder; the first that exists

MARK_HEIGHT = 40                # pixels: the logo is scaled to this, inside a title row of COVER_ROW_POINTS
COVER_ROW_POINTS = 36
B_WIDTH_PIXELS = 100 * 7 + 5    # column B at width 100 (Excel's 7 pixels a character, plus 5)
MARK_MARGIN = 10
EMU = 9525                      # EMUs in a pixel

LOG = logging.getLogger("clark.excel")

NS_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_PKG_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
NS_CT = "http://schemas.openxmlformats.org/package/2006/content-types"
REL_DRAWING = NS_REL + "/drawing"
REL_IMAGE = NS_REL + "/image"
CT_DRAWING = "application/vnd.openxmlformats-officedocument.drawing+xml"


class PictureRefused(ValueError):
    """The picture was not used; the message says why, in plain words."""


def read_size(data, name="the picture"):
    """(width, height) from a PNG's bytes, or PictureRefused. Reads the header only."""
    if len(data) > MAX_BYTES:
        raise PictureRefused(f"{name} is too big ({len(data) // 1024} KB; the most is {MAX_BYTES // 1024} KB).")
    if data[:8] != SIGNATURE:
        raise PictureRefused(f"{name} is not a PNG picture.")
    if len(data) < 33:
        raise PictureRefused(f"{name} is cut short: its PNG header is incomplete.")
    length, kind = struct.unpack(">I4s", data[8:16])
    if kind != b"IHDR" or length != 13:
        raise PictureRefused(f"{name} is not a well-formed PNG: the header block does not come first.")
    width, height = struct.unpack(">II", data[16:24])
    if not (1 <= width <= MAX_PIXELS and 1 <= height <= MAX_PIXELS):
        raise PictureRefused(f"{name} is {width} by {height} pixels; each side must be between 1 and {MAX_PIXELS}.")
    _check_chunks(data, name)
    return width, height


def _check_chunks(data, name):
    """Walk every chunk to the end (IEND), checking each one's length and CRC. Only the chunk framing is read: no pixel data is
    ever decompressed or decoded. A file that is damaged, cut short or has bytes after IEND is refused."""
    at = 8
    while True:
        if at + 12 > len(data):
            raise PictureRefused(f"{name} is cut short: it ends in the middle of the picture.")
        length, kind = struct.unpack(">I4s", data[at:at + 8])
        end = at + 8 + length
        if end + 4 > len(data):
            raise PictureRefused(f"{name} is cut short: it ends in the middle of the picture.")
        if zlib.crc32(data[at + 4:end]) & 0xFFFFFFFF != struct.unpack(">I", data[end:end + 4])[0]:
            raise PictureRefused(f"{name} is damaged: one of its parts doesn't match its check value.")
        at = end + 4
        if kind == b"IEND":
            break
    if at != len(data):
        raise PictureRefused(f"{name} has extra data after the end of the picture.")


def local_logo(branding=None):
    """The path of the user's own brand logo, or None when there isn't one. `branding` defaults to system/branding."""
    from clark import page          # the page's own idea of where the local brand lives
    base = Path(branding) if branding is not None else page.BRANDING
    for name in LOCAL_LOGOS:
        p = base / name
        if p.is_file():
            return p
    return None


NOT_USED = "The brand logo was not used, so the Cover has no logo: {why}"


def load(branding=None, warnings=None):
    """(bytes, width, height) for the local brand logo, or None: no logo, or one that is refused. A refusal never stops the
    export: the reason, in plain words (NOT_USED), is logged and, when `warnings` is a list, added to it, so the screen that
    started the export can tell the person why the logo is missing (#133 LOW). Never raises for a bad logo."""
    path = local_logo(branding)
    if path is None:
        return None
    try:
        try:
            with open(path, "rb") as f:
                data = f.read(MAX_BYTES + 1)            # bounded: a file that grows, or never ends, is never read whole
        except OSError as e:
            raise PictureRefused(f"{path.name} could not be read ({e.strerror or 'unreadable'}).") from None
        width, height = read_size(data, path.name)
    except PictureRefused as e:
        text = NOT_USED.format(why=e)
        LOG.warning("%s", text)
        if warnings is not None:
            warnings.append(text)
        return None
    return data, width, height


def layout(width, height):
    """(x, y, cx, cy) in EMUs for a logo of width by height pixels: scaled to MARK_HEIGHT, kept inside column B, at its right
    edge, centred up and down in the title row. x is the offset from column B's left edge."""
    w, h = width * MARK_HEIGHT / height, MARK_HEIGHT
    room = B_WIDTH_PIXELS - 2 * MARK_MARGIN
    if w > room:
        w, h = room, h * room / w
    w, h = max(1, round(w)), max(1, round(h))
    x = max(0, B_WIDTH_PIXELS - w - MARK_MARGIN)
    y = max(0, (COVER_ROW_POINTS * 4 // 3 - h) // 2)
    return x * EMU, y * EMU, w * EMU, h * EMU


def drawing_xml(width, height, rid="rId1", name="Brand logo"):
    x, y, cx, cy = layout(width, height)
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<xdr:wsDr xmlns:xdr="http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing" '
        'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        f'xmlns:r="{NS_REL}">'
        f'<xdr:oneCellAnchor><xdr:from><xdr:col>1</xdr:col><xdr:colOff>{x}</xdr:colOff><xdr:row>0</xdr:row>'
        f'<xdr:rowOff>{y}</xdr:rowOff></xdr:from><xdr:ext cx="{cx}" cy="{cy}"/>'
        f'<xdr:pic><xdr:nvPicPr><xdr:cNvPr id="2" name="{escape(name)}" descr="{escape(name)}"/>'
        '<xdr:cNvPicPr><a:picLocks noChangeAspect="1"/></xdr:cNvPicPr></xdr:nvPicPr>'
        f'<xdr:blipFill><a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch></xdr:blipFill>'
        f'<xdr:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>'
        '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></xdr:spPr></xdr:pic><xdr:clientData/></xdr:oneCellAnchor></xdr:wsDr>'
    ).encode("utf-8")


def _next_free(names, pattern):
    n = 1
    while pattern.format(n) in names:
        n += 1
    return pattern.format(n)


def _rels_xml(items):
    body = "".join(f'<Relationship Id="{i}" Type="{t}" Target="{g}"/>' for i, t, g in items)
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            f'<Relationships xmlns="{NS_PKG_REL}">{body}</Relationships>').encode("utf-8")


def _cover_part(files, sheet_name):
    """The part name of the sheet called `sheet_name` (xl/worksheets/sheet1.xml), or None."""
    wb = ET.fromstring(files["xl/workbook.xml"])
    rid = None
    for s in wb.iter(f"{{{NS_MAIN}}}sheet"):
        if s.get("name") == sheet_name:
            rid = s.get(f"{{{NS_REL}}}id")
    if rid is None:
        return None
    for r in ET.fromstring(files["xl/_rels/workbook.xml.rels"]):
        if r.get("Id") == rid:
            target = r.get("Target")
            return target.lstrip("/") if target.startswith("/") else "xl/" + target
    return None


def embed(files, png, sheet_name="Cover"):
    """`files` ({member name: bytes} of a saved .xlsx) with the PNG `png` added to the sheet called `sheet_name`: returns
    (replacements, additions), two dicts of member name to bytes, for the caller to write. Nothing is changed in `files`. Raises
    PictureRefused if the workbook has no such sheet or is not laid out as openpyxl lays it out."""
    width, height = read_size(png)
    part = _cover_part(files, sheet_name)
    if part is None or part not in files:
        raise PictureRefused(f"the workbook has no {sheet_name} sheet to put the logo on.")
    names = set(files)
    media = _next_free(names, "xl/media/image{}.png")
    drawing = _next_free(names, "xl/drawings/drawing{}.xml")
    drawing_rels = "xl/drawings/_rels/" + drawing.rsplit("/", 1)[1] + ".rels"
    sheet_rels = part.rsplit("/", 1)[0] + "/_rels/" + part.rsplit("/", 1)[1] + ".rels"
    replace, add = {}, {}
    add[media] = png
    add[drawing] = drawing_xml(width, height)
    add[drawing_rels] = _rels_xml([("rId1", REL_IMAGE, "../media/" + media.rsplit("/", 1)[1])])

    # The sheet's relationships: a new file, or one more entry in the existing one.
    target = "../drawings/" + drawing.rsplit("/", 1)[1]
    if sheet_rels in files:
        text = files[sheet_rels].decode("utf-8")
        ids = set(re.findall(r'Id="([^"]*)"', text))
        n = 1
        while f"rId{n}" in ids:
            n += 1
        rid = f"rId{n}"
        entry = f'<Relationship Id="{rid}" Type="{REL_DRAWING}" Target="{target}"/>'
        if "</Relationships>" not in text:
            raise PictureRefused("the Cover's relationships are not laid out as expected.")
        replace[sheet_rels] = text.replace("</Relationships>", entry + "</Relationships>", 1).encode("utf-8")
    else:
        rid = "rId1"
        add[sheet_rels] = _rels_xml([(rid, REL_DRAWING, target)])

    # The sheet's <drawing r:id/>, in schema order: before legacyDrawing, tableParts and extLst if the sheet has them.
    xml = files[part].decode("utf-8")
    if "<drawing " in xml:
        raise PictureRefused("the Cover already has a drawing.")
    element = f'<drawing xmlns:r="{NS_REL}" r:id="{rid}"/>'
    m = re.search(r"<(legacyDrawing|legacyDrawingHF|drawingHF|picture|oleObjects|controls|webPublishItems|tableParts|extLst)[ />]", xml)
    if m:
        xml = xml[:m.start()] + element + xml[m.start():]
    elif "</worksheet>" in xml:
        xml = xml.replace("</worksheet>", element + "</worksheet>", 1)
    else:
        raise PictureRefused("the Cover sheet is not laid out as expected.")
    replace[part] = xml.encode("utf-8")

    # [Content_Types].xml: a Default for .png and an Override for the drawing.
    ct = files["[Content_Types].xml"].decode("utf-8")
    if "</Types>" not in ct:
        raise PictureRefused("the workbook's content types are not laid out as expected.")
    extra = ""
    if not re.search(r'<Default[^>]*Extension="png"', ct, re.I):
        extra += '<Default Extension="png" ContentType="image/png"/>'
    extra += f'<Override PartName="/{drawing}" ContentType="{CT_DRAWING}"/>'
    replace["[Content_Types].xml"] = ct.replace("</Types>", extra + "</Types>", 1).encode("utf-8")
    return replace, add
