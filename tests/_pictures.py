"""Shared by the Pictures group's tests (#96: test_tpl_textimage, test_tpl_imagecap, test_tpl_gallery, test_tpl_headline): small
pictures made byte by byte (a real PNG; a JPEG and a WebP with only the parts the checks read), with and without camera details,
and the steps that put one into a section. Fictional data only.
"""
import base64
import json
import struct
import zlib

from clark import changes, publish, section_bodies
from clark import store as store_module


def png(extra_chunk=None, w=2, h=2):
    """A real PNG of w x h grey pixels; `extra_chunk` (name, data) is put before the picture data."""
    def chunk(name, data):
        return struct.pack(">I", len(data)) + name + data + struct.pack(">I", zlib.crc32(name + data) & 0xFFFFFFFF)
    raw = b"".join(b"\x00" + b"\x80" * (w * 3) for _ in range(h))
    out = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
    if extra_chunk:
        out += chunk(*extra_chunk)
    return out + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


def jpeg(app1=None, pad=0):
    """A JPEG's header as the checks read it: SOI, a JFIF APP0, an optional APP1 (b'Exif\\0\\0...' or XMP), then the picture data."""
    out = b"\xff\xd8" + b"\xff\xe0" + struct.pack(">H", 16) + b"JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    if app1 is not None:
        out += b"\xff\xe1" + struct.pack(">H", len(app1) + 2) + app1
    return out + b"\xff\xdb" + struct.pack(">H", 67) + b"\x00" + b"\x01" * 64 + b"\xff\xda" + b"\x00" * (8 + pad) + b"\xff\xd9"


def webp(extra=None):
    """A WebP's frame as the checks read it: RIFF, WEBP, a VP8 chunk, and an optional chunk (name, data)."""
    body = b"WEBP" + b"VP8 " + struct.pack("<I", 10) + b"\x00" * 10
    if extra:
        name, data = extra
        body += name + struct.pack("<I", len(data)) + data + (b"\x00" if len(data) & 1 else b"")
    return b"RIFF" + struct.pack("<I", len(body)) + body


def data(raw, kind="png"):
    return f"data:image/{kind};base64," + base64.b64encode(raw).decode("ascii")


GOOD = data(png())
GOOD_JPEG = data(jpeg(), "jpeg")
GOOD_WEBP = data(webp(), "webp")
EXIF = data(jpeg(b"Exif\x00\x00MM\x00*fictional camera"), "jpeg")
XMP = data(jpeg(b"http://ns.adobe.com/xap/1.0/\x00<x/>"), "jpeg")
WEBP_EXIF = data(webp((b"EXIF", b"MM\x00*fictional")), "webp")
PNG_EXIF = data(png((b"eXIf", b"MM\x00*fictional")), "png")
BAD = [5, "", "data:image/svg+xml;base64,PHN2Zz4=", "data:image/gif;base64,R0lGODlhAQABAAAAACw=",
       "https://example.org/a.png", "data:image/png;base64," + base64.b64encode(b"not a png at all").decode(),
       "data:image/jpeg;base64," + base64.b64encode(png()).decode(), "data:image/png;base64,iVBOR w0KGgo=",
       GOOD + "=", GOOD[:-2] + "A", "DATA:image/png;base64," + GOOD.split(",")[1], GOOD + "\n",
       data(jpeg()[:30], "jpeg"), data(webp()[:10], "webp")]
CAMERA = [EXIF, XMP, WEBP_EXIF, PNG_EXIF]


def check(kind, value):
    """The store's check of a body (what a write meets), as text in and the canonical value out; raises store.Invalid."""
    text = store_module.check_section_body(kind, json.dumps(value))
    return json.loads(text) if text else None


def published(kind, value):
    return section_bodies.published(kind, value)


class PictureSteps:
    """Mixed into a test_changes.Api test: make a section, set a picture through the seam, read the stored body."""

    def setUp(self):
        super().setUp()
        self.image = changes.make_section_image(self.path, [], "Fictional Person")

    def made(self, kind, title="Fictional pictures", after=None, beside=None):
        more = {"beside": beside} if beside is not None else {}
        return self.ok("new", values={"type": kind, "title": title}, after=after, **more)["ref"]

    def put(self, ref, slot, image, **more):
        return self.image({"project": "ABC", "section": ref, "slot": slot, "image": image, "place": "report", **more})

    def body(self, ref):
        row = next(r for r in self.s.read("report_sections", "ABC") if r["id"] == ref)
        return json.loads(row["body"]) if row["body"] else None

    def words(self, ref, value):
        return self.change(self.req(changes.UPDATE, id=ref, changes={"body": json.dumps(value)}, place="report"))

    def file(self):
        built = publish.build(self.s, "ABC", now="2030-01-15")
        return {s["id"]: s for s in built["published"]["sections"]}, built["body"].decode("utf-8")
