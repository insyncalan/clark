"""Image with caption (H2, #96; row 1223): the content of a section of type 'imagecap'. Two bodies live under the one type.

VERSION 1 (the Image with caption template, unchanged): `{"v": 1, "caption", "alt", "pictures": {"image": ...}}`. One picture with a
caption under it and a description for someone who can't see it. The picture and text rules are the Pictures group's, in textimage.py:
a picture comes only through POST /api/section-image (with_picture), never with the words. It opens and publishes exactly as it
always did (its limits are the old ones: V1_PICTURE_MAX, one picture of 1 MiB).

VERSION 2 (row 1223, the Full width image template): `{"v": 2, ...}`, one image across the whole width of the section, framed as
the person chooses, with an optional caption and a description. Server side only: the checks, the framed copy and what is published.
Pure: standard library only (a PNG reader and writer live here, because no image library is installed and a template module may not
import anything from clark). The body keys are `caption`, `alt` and `pictures` as in version 1, and:
- the framing, all numbers clark validates (never a file name, never a file from the page): `shape` "whole" (default), "16:9",
  "banner" (3:1) or "free"; `ratio` (width over height, in thousandths, 250 to 4000: nothing flatter than 4:1) only with "free";
  `fx`, `fy` the focus, 0 to 1000 of the original (default 500); `crop` [x0, y0, x1, y1], 0 to 1000 of the original, each side at
  least 10 apart; `fit` "centre" (default) or "stretch" and `fill` "blur" (default), "brand" or "plain", both only for the page
  to draw a small image; `from_w`, the width the image had before it was made smaller (a note for the page).
- `pictures`: {"original": ..., "image": ...}. `original` is what the person added (PNG, JPEG or WebP, no camera details; a PNG
  wider than 3,000 px is made 3,000 px wide by clark). `image` is the FRAMED COPY, made here by clark from the original and the
  numbers above, never accepted from a request: it is the crop, then the shape cut around the focus, then (only if wider than
  3,000 px) made smaller; never enlarged. Made as PNG with no camera details. A frame that changes nothing (whole image, not wider
  than 3,000 px) uses the original itself as the framed copy, so a JPEG or WebP can be used as it is.
- The framed copy of a PNG carries a tEXt note holding a digest of the original and the numbers it was made from. check and
  published compare it, so a framed copy that does not belong to the stored original and framing is made again (check) or never
  published (published). The words (/api/section-body) never send pictures; only POST /api/section-image sets or clears the original.

Published (version 2): ONLY the framed copy, never the original, so the part cropped away is not in the report file. No image: not
published. The content carries `full: 1` so the page and the Word export draw it as a full width image.
"""
import base64
import hashlib
import re
import struct
import zlib

from clark.section_kinds.base import Bad
from clark.section_kinds.textimage import (BIG_PICTURE, NOT_A_PICTURE, NOT_CONTENT, OLD_VERSION, PICTURES, TEXT_LIMIT, UNKNOWN_FIELD, frame, line,
                                           picture, pictures_of, put, set_picture)
from clark.section_kinds.textimage import PICTURE_MAX as V1_PICTURE_MAX

READY = True
MIB = 1024 * 1024
WIDTH_MAX = 3000                       # px: 300 dpi across a full landscape page; a wider image is made this wide
PICTURE_MAX = 8 * MIB                  # bytes one image may take when it is SENT (decoded; the route's limit allows its base64); a v:1 picture is held to V1_PICTURE_MAX
ORIGINAL_MAX = 3 * MIB                 # bytes the stored original may take (decoded), after a wide PNG is made smaller
FRAMED_MAX = 3 * MIB                   # bytes the framed copy may take (decoded): 4 MiB in base64, so one image fits in the 5 MiB a published page may hold
PIXELS_MAX = 40_000_000                # a PNG of more pixels is refused before it is inflated
LIMIT = (ORIGINAL_MAX + FRAMED_MAX) * 4 // 3 + 64 * 1024   # the stored body (either version): both images in base64, and the words (v:1 stays under 1,600 KiB by its own picture limit)
V1_LIMIT = 1600 * 1024                 # what a version 1 body may take, as before
EMPTY = ""
START = '{"v":2}'                      # the body a new Full width image section starts with (changes.py accepts this one body for a new imagecap section)
SLOTS = ("image", "original")
V1_SLOTS = ("image",)
SHAPES = ("whole", "16:9", "banner", "free")
RATIOS = {"16:9": 1778, "banner": 3000}
FRAMING = ("shape", "ratio", "fx", "fy", "crop", "fit", "fill")
FITS = ("centre", "stretch")
FILLS = ("blur", "brand", "plain")
__all__ = ("READY", "LIMIT", "EMPTY", "START", "SLOTS", "PICTURE_MAX", "TEXT_LIMIT", "WIDTH_MAX", "check", "with_picture", "published")

MADE_HERE = "The framed image is made by clark from the original. Add the image again with Choose an image."
BAD_FRAME = "That framing isn't in the shape this section keeps. Reload the page and try again."
CANT_FRAME = ("That image can't be cropped or shaped here. Add a PNG image, or use the whole image (the page sends a PNG when "
              "you crop).")
TOO_WIDE = "That image is wider than 3,000 px and can't be made smaller here. Add a PNG image, or make it smaller first."
TOO_MANY_PIXELS = "That image has too many pixels. Add a smaller one."
STILL_BIG = "That image is too large even after it is made smaller. Add a smaller one."
NOT_ALONE = "An image can only be added with Choose an image. Reload the page and try again."

_PNG = b"\x89PNG\r\n\x1a\n"
_DATA = re.compile(r"data:image/(png|jpeg|webp);base64,([A-Za-z0-9+/]+={0,2})\Z")


# ── Reading and writing a PNG (8 bits, no interlace) ──────────────────────────

def _chunks(raw):
    i = 8
    while i + 8 <= len(raw):
        n = int.from_bytes(raw[i:i + 4], "big")
        if i + 12 + n > len(raw):
            raise Bad(NOT_A_PICTURE)
        yield raw[i + 4:i + 8], raw[i + 8:i + 8 + n]
        i += 12 + n


def png_size(raw):
    """(width, height) from a PNG's header, without inflating anything."""
    if not raw.startswith(_PNG) or raw[12:16] != b"IHDR" or len(raw) < 33:
        raise Bad(NOT_A_PICTURE)
    w, h = struct.unpack(">II", raw[16:24])
    if w < 1 or h < 1:
        raise Bad(NOT_A_PICTURE)
    return w, h


def _jpeg_size(raw):
    i = 2
    while i + 9 < len(raw):
        if raw[i] != 0xFF:
            raise Bad(NOT_A_PICTURE)
        m = raw[i + 1]
        if m == 0xFF:
            i += 1
            continue
        if m == 0x01 or 0xD0 <= m <= 0xD8:
            i += 2
            continue
        if m == 0xDA or m == 0xD9:
            return None
        n = int.from_bytes(raw[i + 2:i + 4], "big")
        if 0xC0 <= m <= 0xCF and m not in (0xC4, 0xC8, 0xCC):
            return int.from_bytes(raw[i + 7:i + 9], "big"), int.from_bytes(raw[i + 5:i + 7], "big")
        i += 2 + n
    return None


def _webp_size(raw):
    kind = raw[12:16]
    if kind == b"VP8X" and len(raw) >= 30:
        return int.from_bytes(raw[24:27], "little") + 1, int.from_bytes(raw[27:30], "little") + 1
    if kind == b"VP8 " and len(raw) >= 30:
        return int.from_bytes(raw[26:28], "little") & 0x3FFF, int.from_bytes(raw[28:30], "little") & 0x3FFF
    if kind == b"VP8L" and len(raw) >= 25:
        bits = int.from_bytes(raw[21:25], "little")
        return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
    return None


def _decode_data(text):
    m = _DATA.match(text)
    return m.group(1), base64.b64decode(m.group(2), validate=True)


def _encode_data(raw):
    return "data:image/png;base64," + base64.b64encode(raw).decode("ascii")


def _add_rows(a, b, n):
    """(a + b) mod 256, byte by byte, for two rows of n bytes at once (carry-free, through whole integers)."""
    hi = int.from_bytes(b"\x80" * n, "big")
    x, y = int.from_bytes(a, "big"), int.from_bytes(b, "big")
    return (((x & ~hi) + (y & ~hi)) ^ ((x ^ y) & hi)).to_bytes(n, "big")


def _read_png(raw):
    """(width, height, channels, rows) of an 8-bit, non-interlaced PNG, as RGB (3) or RGBA (4) rows of bytes; Bad when it is
    anything else or does not inflate to exactly its size."""
    w, h = png_size(raw)
    if w * h > PIXELS_MAX:
        raise Bad(TOO_MANY_PIXELS)
    depth, ctype, _comp, _filt, interlace = struct.unpack(">BBBBB", raw[24:29])
    if depth != 8 or interlace != 0 or ctype not in (0, 2, 3, 4, 6):
        raise Bad(CANT_FRAME)
    plte = trns = b""
    idat = []
    for name, data in _chunks(raw):
        if name == b"PLTE":
            plte = data
        elif name == b"tRNS":
            trns = data
        elif name == b"IDAT":
            idat.append(data)
    ch = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[ctype]
    stride = w * ch
    want = (stride + 1) * h
    inflater = zlib.decompressobj()
    try:
        flat = inflater.decompress(b"".join(idat), want + 1)
    except zlib.error:
        raise Bad(NOT_A_PICTURE) from None
    if len(flat) != want or inflater.unconsumed_tail:
        raise Bad(NOT_A_PICTURE)
    rows, prev = [], bytes(stride)
    for y in range(h):
        f, cur = flat[y * (stride + 1)], flat[y * (stride + 1) + 1:(y + 1) * (stride + 1)]
        if f == 0:
            row = cur
        elif f == 2:
            row = _add_rows(cur, prev, stride)
        else:
            row = bytearray(cur)
            for i in range(stride):
                a = row[i - ch] if i >= ch else 0
                b = prev[i]
                if f == 1:
                    p = a
                elif f == 3:
                    p = (a + b) >> 1
                elif f == 4:
                    c = prev[i - ch] if i >= ch else 0
                    pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                    p = a if pa <= pb and pa <= pc else (b if pb <= pc else c)
                else:
                    raise Bad(NOT_A_PICTURE)
                row[i] = (row[i] + p) & 255
            row = bytes(row)
        rows.append(row)
        prev = row
    return (w, h) + _to_rgb(rows, w, ctype, plte, trns)[::-1]


def _to_rgb(rows, w, ctype, plte, trns):
    """(rows, channels) with every row as RGB or RGBA."""
    if ctype in (2, 6):
        return rows, (3 if ctype == 2 else 4)
    out = []
    if ctype == 3:
        if len(plte) % 3 or not plte:
            raise Bad(NOT_A_PICTURE)
        n = len(plte) // 3
        tables = [bytes(plte[c::3]) + bytes(256 - n) for c in range(3)]
        alpha = bytes(trns) + b"\xff" * (256 - len(trns)) if trns else None
        for row in rows:
            if max(row) >= n:
                raise Bad(NOT_A_PICTURE)
            px = bytearray(w * (4 if alpha else 3))
            step = 4 if alpha else 3
            for c in range(3):
                px[c::step] = row.translate(tables[c])
            if alpha:
                px[3::4] = row.translate(alpha)
            out.append(bytes(px))
        return out, (4 if alpha else 3)
    for row in rows:                                       # grey (1 channel) or grey with alpha (2)
        step = 3 if ctype == 0 else 4
        px = bytearray(w * step)
        g = row[0::1] if ctype == 0 else row[0::2]
        for c in range(3):
            px[c::step] = g
        if ctype == 4:
            px[3::4] = row[1::2]
        out.append(bytes(px))
    return out, (3 if ctype == 0 else 4)


def _write_png(rows, w, h, ch, note):
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    body = b"".join(b"\x00" + r for r in rows)
    return (_PNG + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2 if ch == 3 else 6, 0, 0, 0))
            + chunk(b"tEXt", b"clarkframe\x00" + note.encode("ascii")) + chunk(b"IDAT", zlib.compress(body, 6)) + chunk(b"IEND", b""))


def _note_of(raw):
    """The digest a framed PNG carries ('' when it has none)."""
    try:
        for name, data in _chunks(raw):
            if name == b"tEXt" and data.startswith(b"clarkframe\x00"):
                return data[11:].decode("ascii", "replace")
            if name == b"IDAT":
                break
    except Bad:
        pass
    return ""


def _smaller(rows, w, h, ch, new_w):
    """The rows made `new_w` wide (never wider than they are), by averaging the pixels each new pixel covers."""
    if new_w >= w:
        return rows, w, h
    new_h = max(1, round(h * new_w / w))
    ys = [(oy * h // new_h, max(oy * h // new_h + 1, -(-(oy + 1) * h // new_h))) for oy in range(new_h)]
    xs = [(ox * w // new_w, max(ox * w // new_w + 1, -(-(ox + 1) * w // new_w))) for ox in range(new_w)]
    out = []
    for a, b in ys:
        if b - a == 1:
            r = rows[a]
        else:
            n = b - a
            r = bytes(sum(t) // n for t in zip(*rows[a:b]))
        px = bytearray(new_w * ch)
        for c in range(ch):
            chan = r[c::ch]
            px[c::ch] = bytes(sum(chan[p:q]) // (q - p) for p, q in xs)
        out.append(bytes(px))
    return out, new_w, new_h


# ── The framing ───────────────────────────────────────────────────────────────

def _frame_numbers(value):
    """The validated framing from a body: a dict with only the keys that differ from the defaults."""
    out = {}
    shape = value.get("shape", "whole")
    if shape not in SHAPES:
        raise Bad(BAD_FRAME)
    if shape != "whole":
        out["shape"] = shape
    for key in ("fx", "fy"):
        n = value.get(key, 500)
        if type(n) is not int or not 0 <= n <= 1000:
            raise Bad(BAD_FRAME)
        if n != 500:
            out[key] = n
    crop = value.get("crop")
    if crop is not None:
        if (type(crop) is not list or len(crop) != 4 or any(type(n) is not int or not 0 <= n <= 1000 for n in crop)
                or crop[2] - crop[0] < 10 or crop[3] - crop[1] < 10):
            raise Bad(BAD_FRAME)
        out["crop"] = list(crop)
    ratio = value.get("ratio")
    if ratio is not None:
        if shape != "free" or type(ratio) is not int or not 250 <= ratio <= 4000:
            raise Bad(BAD_FRAME)
        out["ratio"] = ratio
    for key, allowed in (("fit", FITS), ("fill", FILLS)):
        word = value.get(key, allowed[0])
        if word not in allowed:
            raise Bad(BAD_FRAME)
        if word != allowed[0]:
            out[key] = word
    from_w = value.get("from_w")
    if from_w is not None:
        if type(from_w) is not int or not 1 <= from_w <= 1_000_000:
            raise Bad(BAD_FRAME)
        out["from_w"] = from_w
    return out


def _window(w, h, numbers):
    """(x0, y0, x1, y1) in pixels of the part of a w x h original the framed copy shows."""
    x0, y0, x1, y1 = numbers.get("crop", (0, 0, 1000, 1000))
    x0, x1 = x0 * w // 1000, max(x0 * w // 1000 + 1, -(-x1 * w // 1000))
    y0, y1 = y0 * h // 1000, max(y0 * h // 1000 + 1, -(-y1 * h // 1000))
    shape = numbers.get("shape", "whole")
    if shape == "whole":
        return x0, y0, x1, y1
    ratio = numbers.get("ratio", 1778) if shape == "free" else RATIOS[shape]       # width over height, thousandths
    bw, bh = x1 - x0, y1 - y0
    if bw * 1000 > bh * ratio:
        ww, wh = max(1, bh * ratio // 1000), bh
    else:
        ww, wh = bw, max(1, bw * 1000 // ratio)
    cx, cy = numbers.get("fx", 500) * w // 1000, numbers.get("fy", 500) * h // 1000
    wx = min(max(cx - ww // 2, x0), x1 - ww)
    wy = min(max(cy - wh // 2, y0), y1 - wh)
    return wx, wy, wx + ww, wy + wh


def _digest(original, numbers):
    keys = ("shape", "fx", "fy", "crop", "ratio")
    text = original + "|" + "|".join(repr(numbers.get(k)) for k in keys)
    return hashlib.sha256(text.encode("ascii")).hexdigest()


def _same_as_original(numbers):
    """True when the framing changes nothing about the original (the whole image, no shape): shape and crop both absent."""
    return "shape" not in numbers and "crop" not in numbers


def _make_framed(original, numbers, width_max=None, framed_max=None):
    """The framed copy (a data address) of `original`; the original itself when nothing is cut and it is not too wide.
    `width_max` and `framed_max` are this template's limits; the Image gallery (row 1233) passes its own and shares the rest."""
    width_max, framed_max = width_max or WIDTH_MAX, framed_max or FRAMED_MAX      # read when called (a test may change the module's limits)
    kind, raw = _decode_data(original)
    if _same_as_original(numbers):
        size = png_size(raw) if kind == "png" else (_jpeg_size(raw) if kind == "jpeg" else _webp_size(raw))
        if size is not None and size[0] <= width_max and len(raw) <= framed_max:
            return original
    if kind != "png":
        raise Bad(CANT_FRAME)
    w, h, ch, rows = _read_png(raw)
    x0, y0, x1, y1 = _window(w, h, numbers)
    rows = [r[x0 * ch:x1 * ch] for r in rows[y0:y1]]
    rows, nw, nh = _smaller(rows, x1 - x0, y1 - y0, ch, width_max)
    made = _write_png(rows, nw, nh, ch, _digest(original, numbers))
    if len(made) > framed_max:
        raise Bad(STILL_BIG)
    return _encode_data(made)


def _framed_belongs(original, image, numbers):
    """True when `image` is what _make_framed would make of `original` and `numbers` (compared by the digest, not by remaking it)."""
    if _same_as_original(numbers):
        return image == original or (_decode_data(image)[0] == "png" and _note_of(_decode_data(image)[1]) == _digest(original, numbers))
    return _decode_data(image)[0] == "png" and _note_of(_decode_data(image)[1]) == _digest(original, numbers)




# ── The checks ────────────────────────────────────────────────────────────────

def _version(value):
    if type(value) is not dict:
        raise Bad(NOT_CONTENT)
    v = value.get("v", 1)
    if type(v) is not int:
        raise Bad(NOT_CONTENT)
    if v not in (1, 2):
        raise Bad(OLD_VERSION)
    return v


def _say_image(text):
    """A version 2 refusal says "image", never "picture" (the version 1 texts, in textimage.py, are unchanged)."""
    return text.replace("a picture", "an image").replace("picture", "image").replace("Picture", "Image")


def _in_words_of_images(fn, *args):
    try:
        return fn(*args)
    except Bad as e:
        words = _say_image(str(e))
        if words == str(e):
            raise
        raise Bad(words) from None


def _size(value):
    """Characters a body's text takes, near enough (the words and the images, which are plain text)."""
    if isinstance(value, str):
        return len(value) + 2
    if type(value) is dict:
        return 2 + sum(_size(k) + 1 + _size(v) + 1 for k, v in value.items())
    if type(value) is list:
        return 2 + sum(_size(v) + 1 for v in value)
    return 5


def check(value, rules):
    if _version(value) == 2:
        return _in_words_of_images(_check_full, value)
    if _size(value) > V1_LIMIT:                                      # the old body keeps its old size
        raise Bad(BIG_PICTURE)
    out = frame(value, ("caption", "alt", PICTURES))             # version 1: as it always was
    put(out, "caption", line(value, "caption"))
    put(out, "alt", line(value, "alt"))
    put(out, PICTURES, pictures_of(value, V1_SLOTS, V1_PICTURE_MAX))
    return out


def _check_full(value):
    for k in value:
        if k != "v" and k not in ("caption", "alt", "shape", "ratio", "fx", "fy", "crop", "fit", "fill", "from_w", PICTURES):
            raise Bad(UNKNOWN_FIELD)
    out = {"v": 2}
    put(out, "caption", line(value, "caption"))
    put(out, "alt", line(value, "alt"))
    numbers = _frame_numbers(value)
    out.update(numbers)
    pics = pictures_of(value, SLOTS, ORIGINAL_MAX)
    original, image = pics.get("original"), pics.get("image")
    if image and not original:
        raise Bad(NOT_ALONE)
    if original:
        if not image or not _framed_belongs(original, image, numbers):
            image = _make_framed(original, numbers)           # the framing changed (or the copy is not ours): made again here
        elif len(_decode_data(image)[1]) > FRAMED_MAX:
            raise Bad(STILL_BIG)
        pics["image"] = image
    put(out, PICTURES, pics)
    return out


def with_picture(value, slot, image):
    """The body with its picture set or taken out (POST /api/section-image, through changes.py). A version 1 body (or none yet) has
    its one `image` slot, as it always did. A version 2 body takes only `original` (the framed copy is made from it and the body's
    framing, or taken out with it; a new original replacing one starts from no framing, and the words stay)."""
    if type(value) is dict and value.get("v") == 2:
        return _in_words_of_images(_with_original, value, slot, image)
    if image is not None:
        picture(image, V1_PICTURE_MAX)                           # the route allows this type's larger send; a version 1 picture keeps its old size
    return set_picture(value, slot, image, V1_SLOTS, {"v": 1})


def _with_original(value, slot, image, view=None):
    """`view(body)` (row 1232) gives the numbers of the framing in this template's own spelling; Full width image reads its body as it is."""
    view = view or (lambda body: body)
    if slot != "original":
        raise Bad(MADE_HERE)
    had = bool((value.get(PICTURES) or {}).get("original"))
    out = set_picture(value, slot, image, SLOTS, {"v": 2})
    out.pop("from_w", None)
    if had or image is None:                                 # another image (or none) is not framed like the one it replaces: it starts from no framing
        for key in FRAMING:
            out.pop(key, None)
    if image is None:
        out.get(PICTURES, {}).pop("image", None)
        if not out.get(PICTURES):
            out.pop(PICTURES, None)
        return out
    picture(image, PICTURE_MAX)                              # a type or text that is not an image is refused in words before it is read
    kind, raw = _decode_data(image)
    if kind == "png":
        w, h = png_size(raw)
        if w > WIDTH_MAX:                                    # made 3,000 px wide, as the original too
            pw, ph, ch, rows = _read_png(raw)
            rows, nw, nh = _smaller(rows, pw, ph, ch, WIDTH_MAX)
            image = _encode_data(_write_png(rows, nw, nh, ch, ""))
            out["from_w"] = pw
    else:
        size = _jpeg_size(raw) if kind == "jpeg" else _webp_size(raw)
        if size is None:
            raise Bad(NOT_A_PICTURE)
        if size[0] > WIDTH_MAX:
            raise Bad(TOO_WIDE)
    image = picture(image, ORIGINAL_MAX)
    out[PICTURES] = dict(out.get(PICTURES) or {}, original=image)
    numbers = _frame_numbers(view(out))
    out[PICTURES]["image"] = _make_framed(image, numbers)
    return out


def published(value, ctx):
    """Version 1: the picture with its caption and description; None while there is no picture (a caption alone is not shown).
    Version 2: the framed copy with its caption, description and look (`full: 1`); None while there is no image, or when the framed
    copy is not the one made from the stored original and framing. The original is never published."""
    if type(value) is not dict:
        return None
    if value.get("v") != 2:
        image = (value.get(PICTURES) or {}).get("image", "")
        if not image:
            return None
        return {"content": {"image": image, "caption": value.get("caption", ""), "alt": value.get("alt", "")}}
    pics = value.get(PICTURES) or {}
    original, image = pics.get("original", ""), pics.get("image", "")
    if not original or not image:
        return None
    try:
        numbers = _frame_numbers(value)
        if not _framed_belongs(original, image, numbers):
            return None
    except (Bad, ValueError):
        return None
    content = {"image": image, "caption": value.get("caption", ""), "alt": value.get("alt", ""), "full": 1}
    for key in ("fit", "fill"):
        if key in numbers:
            content[key] = numbers[key]
    return {"content": content}
