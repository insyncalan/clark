"""Text and image (F1, #96): the content of a section of type 'textimage'. Words beside one picture, with a caption and a
description of the picture for someone who can't see it.

This module also holds the picture rules the four picture templates share (textimage, imagecap, gallery, headline: the Pictures
group). They live here, not in a module of their own, because every module in this folder is one store type (the registry test
reads the folder); the other three import them from here. Pure: no file, no database, nothing from clark but this folder.

The stored body (canonical JSON, `{"v": 1, ...}`):
- `words`: the paragraphs, a list of plain text (a line break starts a new paragraph); `caption`, `alt`: one line each;
  `side`: "left", or nothing for the default (the picture on the right).
- `pictures`: {slot: "data:image/png|jpeg|webp;base64,..."}. A picture is never sent with the words: POST /api/change keeps the
  stored pictures (changes.py), and only POST /api/section-image sets or clears one, through `with_picture` (one step, one Undo).

A picture (`picture`) is a data address of a PNG, a JPEG or a WebP only (never SVG or GIF), its base64 strict and canonical, its
first bytes those of the type it names, no larger than the template's PICTURE_MAX, and with no camera details left in it: a JPEG
with an Exif or XMP block, a WebP with an EXIF or XMP chunk and a PNG with an eXIf chunk are refused. The page draws every
picture again on a canvas before it sends it, which drops them, so anything that still has them did not come from the page.
"""
import base64
import binascii
import re

from clark.section_kinds.base import Bad

READY = True
PICTURE_MAX = 1024 * 1024           # the most bytes one picture may take (decoded); the page shrinks to well under this
TEXT_LIMIT = 65536                  # the most bytes POST /api/change may send of the body: the words, never the pictures
LIMIT = 1600 * 1024                 # the stored body: one picture at PICTURE_MAX in base64 (1.37 MB) and the words
EMPTY = ""
SLOTS = ("image",)

PICTURES = "pictures"
WORDS_MAX = 20                      # paragraphs
PARAGRAPH_MAX = 2000                # characters in one paragraph
LINE_MAX = 300                      # characters in a caption, a description or one line
SIDES = ("right", "left")

NOT_CONTENT = "That content isn't in the shape this section keeps. Reload the page and try again."
UNKNOWN_FIELD = "That content has a field this section doesn't keep. Reload the page and try again."
OLD_VERSION = "That content was saved by a newer version. Update and try again."
TOO_MANY_WORDS = f"The text can be {WORDS_MAX} paragraphs at most. Shorten it and try again."
LONG_PARAGRAPH = f"A paragraph can be {PARAGRAPH_MAX} characters at most. Split it or shorten it, then try again."
LONG_LINE = f"A caption or a description can be {LINE_MAX} characters at most. Shorten it and try again."
NOT_A_LINE = "Use plain text, with no line breaks or hidden characters."
BAD_SIDE = "A picture sits on the left or the right. Choose one and try again."
BAD_SLOT = "That picture's place isn't in this section. Reload the page and try again."
NOT_A_PICTURE = "That picture can't be used. Add a PNG, JPEG or WebP picture."
BIG_PICTURE = "That picture is too large. Add a smaller one."
CAMERA_DETAILS = ("That picture still carries details from the camera, such as where it was taken. Add it again with Add a "
                  "picture, which removes them.")
PICTURES_OWN_WAY = "Pictures are added with Add a picture, not with the text. Reload the page and try again."

_DATA = re.compile(r"data:image/(png|jpeg|webp);base64,([A-Za-z0-9+/]+={0,2})\Z")
_PNG = b"\x89PNG\r\n\x1a\n"


# ── The shared picture rules ──────────────────────────────────────────────────

def _jpeg_has_details(raw):
    """True when a JPEG carries an Exif or XMP block (an APP1 segment) before its picture data; Bad when its markers can't be
    read."""
    i = 2
    while i + 1 < len(raw):
        if raw[i] != 0xFF:
            raise Bad(NOT_A_PICTURE)
        marker = raw[i + 1]
        if marker == 0xFF:                           # a fill byte
            i += 1
            continue
        if marker == 0x01 or 0xD0 <= marker <= 0xD8:  # markers with no length
            i += 2
            continue
        if marker in (0xDA, 0xD9):                   # the picture data starts (or the file ends): no block is read after it
            return False
        if i + 4 > len(raw):
            raise Bad(NOT_A_PICTURE)
        n = int.from_bytes(raw[i + 2:i + 4], "big")
        if n < 2 or i + 2 + n > len(raw):
            raise Bad(NOT_A_PICTURE)
        if marker == 0xE1:                           # APP1: Exif, or XMP
            return True
        i += 2 + n
    raise Bad(NOT_A_PICTURE)


def _chunks_have(raw, at, read, names, step):
    """True when a chunked file (PNG or WebP) has a chunk named in `names`; Bad when its chunks can't be read."""
    i = at
    while i < len(raw):
        if i + 8 > len(raw):
            raise Bad(NOT_A_PICTURE)
        name, n = read(raw, i)
        if name in names:
            return True
        i = step(i, n)
        if i > len(raw):
            raise Bad(NOT_A_PICTURE)
    return False


def _png_chunk(raw, i):
    return raw[i + 4:i + 8], int.from_bytes(raw[i:i + 4], "big")


def _webp_chunk(raw, i):
    return raw[i:i + 4], int.from_bytes(raw[i + 4:i + 8], "little")


def picture(text, most=PICTURE_MAX):
    """`text` when it is a picture a section may hold (see the module's note), else Bad in plain words."""
    if not isinstance(text, str):
        raise Bad(NOT_A_PICTURE)
    if len(text) > (most + 2) // 3 * 4 + 64:
        raise Bad(BIG_PICTURE)                       # over the limit already: nothing is decoded
    m = _DATA.match(text)
    if not m:
        raise Bad(NOT_A_PICTURE)
    kind, data = m.group(1), m.group(2)
    if len(data) % 4:
        raise Bad(NOT_A_PICTURE)
    try:
        raw = base64.b64decode(data, validate=True)
    except (binascii.Error, ValueError):
        raise Bad(NOT_A_PICTURE) from None
    if base64.b64encode(raw).decode("ascii") != data:
        raise Bad(NOT_A_PICTURE)                     # one picture has one spelling
    if len(raw) > most:
        raise Bad(BIG_PICTURE)
    if kind == "png":
        if not raw.startswith(_PNG):
            raise Bad(NOT_A_PICTURE)
        details = _chunks_have(raw, 8, _png_chunk, (b"eXIf",), lambda i, n: i + 12 + n)
    elif kind == "jpeg":
        if not raw.startswith(b"\xff\xd8\xff"):
            raise Bad(NOT_A_PICTURE)
        details = _jpeg_has_details(raw)
    else:
        if len(raw) < 12 or raw[:4] != b"RIFF" or raw[8:12] != b"WEBP":
            raise Bad(NOT_A_PICTURE)
        details = _chunks_have(raw, 12, _webp_chunk, (b"EXIF", b"XMP "), lambda i, n: i + 8 + n + (n & 1))
    if details:
        raise Bad(CAMERA_DETAILS)
    return text


def pictures_of(value, slots, most=PICTURE_MAX):
    """The `pictures` field rebuilt: only the slots named in `slots`, each a picture. Empty when there are none."""
    given = value.get(PICTURES, {})
    if given is None:
        return {}
    if type(given) is not dict:
        raise Bad(NOT_CONTENT)
    out = {}
    for slot, text in given.items():
        if slot not in slots:
            raise Bad(BAD_SLOT)
        out[slot] = picture(text, most)
    return out


def set_picture(value, slot, image, slots, first):
    """`value` (a checked body, or None for none yet) with the picture in `slot` set to `image`, or taken out when `image` is
    None. Every other field is kept as it is; `first` is the body a section with no content yet starts from."""
    if not isinstance(slot, str) or slot not in slots:
        raise Bad(BAD_SLOT)
    out = dict(value) if type(value) is dict else dict(first)
    pics = dict(out.get(PICTURES) or {})
    if image is None:
        pics.pop(slot, None)
    else:
        pics[slot] = image
    if pics:
        out[PICTURES] = pics
    else:
        out.pop(PICTURES, None)
    return out


# ── The shared text rules ─────────────────────────────────────────────────────

def frame(value, keys):
    """The body's frame: an object of version 1 with only the fields in `keys` (and v). Returns the new body to fill."""
    if type(value) is not dict:
        raise Bad(NOT_CONTENT)
    for k in value:
        if k != "v" and k not in keys:
            raise Bad(UNKNOWN_FIELD)
    v = value.get("v", 1)
    if type(v) is not int:
        raise Bad(NOT_CONTENT)
    if v != 1:
        raise Bad(OLD_VERSION)
    return {"v": 1}


def line(value, key, most=LINE_MAX, words=LONG_LINE):
    """One line of plain text from `value[key]`, trimmed; '' when it is missing or blank."""
    text = value.get(key, "")
    if text is None:
        return ""
    if not isinstance(text, str):
        raise Bad(NOT_A_LINE)
    text = text.strip()
    if len(text) > most:
        raise Bad(words)
    return text


def paragraphs(value, key):
    """The paragraphs from `value[key]`: a list of plain text, blank ones left out."""
    given = value.get(key, [])
    if given is None:
        return []
    if type(given) is not list:
        raise Bad(NOT_CONTENT)
    out = []
    for p in given:
        if not isinstance(p, str):
            raise Bad(NOT_A_LINE)
        p = p.strip()
        if len(p) > PARAGRAPH_MAX:
            raise Bad(LONG_PARAGRAPH)
        if p:
            out.append(p)
    if len(out) > WORDS_MAX:
        raise Bad(TOO_MANY_WORDS)
    return out


def put(out, key, value):
    """Set `out[key]` only when it holds something, so the same content always stores as the same text."""
    if value:
        out[key] = value
    return out


# ── This template ─────────────────────────────────────────────────────────────

def check(value, rules):
    out = frame(value, ("words", "caption", "alt", "side", PICTURES))
    put(out, "words", paragraphs(value, "words"))
    put(out, "caption", line(value, "caption"))
    put(out, "alt", line(value, "alt"))
    side = value.get("side", "right")
    if side not in SIDES:
        raise Bad(BAD_SIDE)
    if side != "right":
        out["side"] = side
    put(out, PICTURES, pictures_of(value, SLOTS))
    return out


def with_picture(value, slot, image):
    """The body with its one picture set or taken out (POST /api/section-image, through changes.py)."""
    return set_picture(value, slot, image, SLOTS, {"v": 1})


def published(value, ctx):
    """The words and the picture (its caption and description only with it); None when there are neither."""
    if type(value) is not dict:
        return None
    image = (value.get(PICTURES) or {}).get("image", "")
    words = value.get("words") or []
    if not image and not words:
        return None
    content = {"words": list(words), "side": value.get("side", "right")}
    if image:
        content.update({"image": image, "caption": value.get("caption", ""), "alt": value.get("alt", "")})
    return {"content": content}
