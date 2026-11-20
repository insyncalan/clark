"""Image gallery (F5, #96; row 1233): the content of a section of type 'gallery'. Up to six images in a grid, each with a caption and a
description for someone who can't see it. Two bodies live under the one type (the type name stays, so the store and its schema are
untouched).

VERSION 1 (1.0.7, unchanged): `{"v": 1, "items": {slot: {"caption", "alt"}}, "pictures": {slot: ...}}`, the slots "1" to "6" in the
order they are shown. The picture and text rules are the Pictures group's, in textimage.py: a picture comes only through POST
/api/section-image (with_picture), never with the words, and taking a picture out takes its caption and description with it. Each
picture is held to V1_PICTURE_MAX, as before; a stored version 1 gallery always opens and publishes.

VERSION 2 (row 1233, the redesign on the Full width image's framing, which this reuses from imagecap.py): `{"v": 2, ...}`. A version 1
gallery becomes version 2 by the words alone (the pictures it holds are slots "1" to "6" of a version 2 body too), so nothing is
migrated. The fields:
- `columns` 2 or 3 (default 3, left out when 3): how many across at full width. The page shows two across at half width and at 900 px.
- `shape` for ALL the images: "4:3" (default, left out), "square", "16:9" or "whole" (never the default). A shape other than "whole" is
  cut here, by clark, from a PNG. A version 1 body has none and is published exactly as 1.0.7 did (no columns, no shape: the page draws
  it 4:3 as before); only a version 2 body publishes `columns` and `shape`, always both.
- `order`: the slots in the order shown, all six (only when it is not the plain order 1 to 6). Dragging an image changes this and nothing
  else, so its caption, description, framing and image move with it. All six slots are listed (the pictures stay where they are).
- `items[slot]`: `caption` and `alt` (the description), and that image's own framing, all numbers clark validates (the Image
  template's): `fx`, `fy` the focus dot (0 to 1000, default 500), `crop` [x0, y0, x1, y1], `fit` and `fill`, `from_w` (the width the
  image had before it was made smaller).
- `pictures`: slot "N" is the FRAMED COPY of image N, made here by clark (the crop, then the shape cut around the focus, then, if
  wider than WIDTH_MAX, made smaller; never enlarged), never accepted from a request. Slot "oN" is the ORIGINAL (so Reset works); it
  is stored only when the framed copy is not the original itself. Neither carries camera details. A framed PNG carries a tEXt note
  holding a digest of its original and the numbers it was made from; check and published compare it, so a framed copy that does not
  belong to its original and framing is made again (check) or never published (published). The words never send pictures; only POST
  /api/section-image sets or clears an image, and only with a slot "1" to "6" (an "o" slot, or a seventh, is refused).

Sizes (decided here, stated for the report file, the Word export and the backup): an image is made at most WIDTH_MAX (1,600 px) wide
(300 dpi at two across on a full landscape page); each framed copy holds at most FRAMED_MAX (512 KiB) and each original at most
ORIGINAL_MAX (1 MiB), decoded. A picture may be sent up to PICTURE_MAX (10 MiB, the gallery's own). Six framed copies are 4.0 MiB as text, inside the 5 MiB a published report may take; the stored section
may reach LIMIT (12.7 MB: six framed copies and six originals), which is what a backup of the project can grow by.

Published (version 2): ONLY the framed copies, in `order`, with their captions and descriptions, `columns` and `shape`; never an original,
so a cropped part is not in the report file. No image: not published.
"""
from clark.section_kinds import imagecap
from clark.section_kinds.base import Bad
from clark.section_kinds.textimage import (BAD_SLOT, NOT_A_PICTURE, NOT_CONTENT, OLD_VERSION, PICTURES, TEXT_LIMIT, UNKNOWN_FIELD, frame, line,
                                           picture, pictures_of, put, set_picture)

READY = True
SLOTS = ("1", "2", "3", "4", "5", "6")
ORIGINALS = tuple("o" + s for s in SLOTS)
KIB = 1024
V1_PICTURE_MAX = 400 * KIB          # each of six in a version 1 body (decoded), as in 1.0.7
PICTURE_MAX = 10 * 1024 * KIB       # bytes one image may take when it is SENT (decoded): 10 MB, the gallery's own (the Image template keeps 8 MiB); the route's limit allows its base64 (server.IMAGE_FILE_MB, a test keeps them equal)
WIDTH_MAX = 1600                    # px: 300 dpi at two across on a full landscape page; a wider image is made this wide
FRAMED_MAX = 512 * KIB              # bytes one framed copy may take (decoded): six in base64 are 4.0 MiB, inside the 5 MiB a published report may hold
ORIGINAL_MAX = 1024 * KIB           # bytes one stored original may take (decoded), after a wide PNG is made smaller
V1_LIMIT = 3 * 1024 * KIB + 256 * KIB    # what a version 1 body may take, as before (six pictures at V1_PICTURE_MAX in base64 and their words)
LIMIT = 6 * ((FRAMED_MAX + 2) // 3 * 4 + (ORIGINAL_MAX + 2) // 3 * 4) + 64 * KIB     # the stored body (either version): six framed copies, six originals and the words
EMPTY = ""
START = '{"v":2}'                   # the body a version 2 gallery starts from (and what upgrades a version 1 gallery: its pictures are kept)
COLUMNS = (2, 3)                    # Row 1233: how many across; the view draws two across at half width and at 900 px whatever is said
SHAPES = ("4:3", "square", "16:9", "whole")     # one shape for every image; none said is 4:3 (a new gallery and 1.0.7 alike), "whole" is never the default
DEFAULT_COLUMNS = 3
DEFAULT_SHAPE = "4:3"
RATIOS = {"4:3": 1333, "square": 1000, "16:9": 1778}      # width over height, in thousandths (the Image template's "free" shape)
WORDS = ("caption", "alt")
FRAMING = ("fx", "fy", "crop", "fit", "fill", "from_w")
__all__ = ("READY", "LIMIT", "EMPTY", "START", "SLOTS", "PICTURE_MAX", "TEXT_LIMIT", "WIDTH_MAX", "check", "with_picture", "published")

BAD_LAYOUT = "That layout isn't one this section keeps. Reload the page and try again."
NOT_ALONE = imagecap.NOT_ALONE
STILL_BIG = imagecap.STILL_BIG
TOO_WIDE = "That image is wider than 1,600 px and can't be made smaller here. Add a PNG image, or make it smaller first."


# ── Version 1 (1.0.7) ─────────────────────────────────────────────────────────

def _items(value):
    given = value.get("items", {})
    if given is None:
        return {}
    if type(given) is not dict:
        raise Bad(NOT_CONTENT)
    out = {}
    for slot, item in given.items():
        if slot not in SLOTS:
            raise Bad(BAD_SLOT)
        if type(item) is not dict:
            raise Bad(NOT_CONTENT)
        one = frame(item, WORDS)
        one.pop("v")
        put(one, "caption", line(item, "caption"))
        put(one, "alt", line(item, "alt"))
        if one:
            out[slot] = one
    return out


# ── Version 2 ─────────────────────────────────────────────────────────────────

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
    return text.replace("a picture", "an image").replace("picture", "image").replace("Picture", "Image")


def _in_words_of_images(fn, *args):
    """A version 2 refusal says "image", never "picture" (the version 1 texts, in textimage.py, are unchanged)."""
    try:
        return fn(*args)
    except Bad as e:
        words = _say_image(str(e))
        if words == str(e):
            raise
        raise Bad(words) from None


def _items_v2(value):
    given = value.get("items", {})
    if given is None:
        return {}
    if type(given) is not dict:
        raise Bad(NOT_CONTENT)
    out = {}
    for slot, item in given.items():
        if slot not in SLOTS:
            raise Bad(BAD_SLOT)
        if type(item) is not dict:
            raise Bad(NOT_CONTENT)
        for k in item:
            if k not in WORDS + FRAMING:
                raise Bad(UNKNOWN_FIELD)
        one = {}
        put(one, "caption", line(item, "caption"))
        put(one, "alt", line(item, "alt"))
        one.update(imagecap._frame_numbers({k: item[k] for k in FRAMING if k in item}))      # the Image template's own checks of the numbers
        if one:
            out[slot] = one
    return out


def _order(value):
    """The slots in the order shown: the given order (distinct, each a slot), then the slots it leaves out, in slot order. All six are
    always listed, so the words alone (which carry no pictures) can say it and the pictures stay put."""
    given = value.get("order")
    if given is None:
        given = []
    if type(given) is not list or any(type(s) is not str or s not in SLOTS for s in given) or len(set(given)) != len(given):
        raise Bad(BAD_LAYOUT)
    return given + [s for s in SLOTS if s not in given]


def _numbers(item, shape, image):
    """The framing of one image as the Image template's code takes it: its own numbers and the one shape for all. The default shape does
    not cut a JPEG or a WebP (clark cuts only a PNG): such an image stays as it is and the page draws it in 4:3, as 1.0.7 did, so a
    version 1 gallery that holds one is upgraded by its words alone without losing it."""
    numbers = {k: item[k] for k in ("fx", "fy", "crop") if k in item}
    if shape != "whole" and not (shape == DEFAULT_SHAPE and imagecap._decode_data(image)[0] != "png"):
        numbers["shape"], numbers["ratio"] = "free", RATIOS[shape]
    return numbers


def _make(original, numbers):
    return imagecap._make_framed(original, numbers, WIDTH_MAX, FRAMED_MAX)


def _check_v2(value):
    for k in value:
        if k not in ("v", "items", "columns", "shape", "order", PICTURES):
            raise Bad(UNKNOWN_FIELD)
    out = {"v": 2}
    columns = value.get("columns", DEFAULT_COLUMNS)
    if type(columns) is not int or columns not in COLUMNS:
        raise Bad(BAD_LAYOUT)
    if columns != DEFAULT_COLUMNS:
        out["columns"] = columns
    shape = value.get("shape", DEFAULT_SHAPE)
    if shape not in SHAPES:
        raise Bad(BAD_LAYOUT)
    if shape != DEFAULT_SHAPE:
        out["shape"] = shape
    items = _items_v2(value)
    pics = pictures_of(value, SLOTS + ORIGINALS, ORIGINAL_MAX)
    for slot in SLOTS:
        framed, original = pics.get(slot), pics.get("o" + slot)
        if original and not framed:
            raise Bad(NOT_ALONE)
        if not framed:
            continue
        source = original or framed                       # with no original kept, the copy is its own original
        numbers = _numbers(items.get(slot, {}), shape, source)
        if not imagecap._framed_belongs(source, framed, numbers):
            framed = _make(source, numbers)               # the framing changed (or the copy is not ours): made again here
            original = source
        elif len(imagecap._decode_data(framed)[1]) > FRAMED_MAX:
            raise Bad(STILL_BIG)
        if framed == original:
            original = None                               # one copy of the same image is kept
        pics[slot] = framed
        if original:
            pics["o" + slot] = original
        else:
            pics.pop("o" + slot, None)
    put(out, "items", items)
    put(out, PICTURES, pics)
    order = _order(value)
    if order != list(SLOTS):
        out["order"] = order
    return out


def check(value, rules):
    if _version(value) == 2:
        return _in_words_of_images(_check_v2, value)
    out = frame(value, ("items", PICTURES))
    put(out, "items", _items(value))
    put(out, PICTURES, pictures_of(value, SLOTS, V1_PICTURE_MAX))
    return out


def with_picture(value, slot, image):
    """The body with the picture in `slot` set or taken out. Version 1 (or none yet): as it always was; taking a picture out takes
    its caption and description too. Version 2: `slot` is "1" to "6" (never an original's slot); the image is checked, made at most
    1,600 px wide and framed here, and kept as an original only when the framed copy differs. A new image replacing one starts from
    no framing of its own (the words stay); taking one out takes its caption, description, framing and original with it."""
    if type(value) is dict and value.get("v") == 2:
        return _in_words_of_images(_with_image, value, slot, image)
    if image is not None:
        picture(image, V1_PICTURE_MAX)                       # the route allows this type's larger send; a version 1 picture keeps its old size
    out = set_picture(value, slot, image, SLOTS, {"v": 1})
    if image is None and type(out.get("items")) is dict and slot in out["items"]:
        items = {k: v for k, v in out["items"].items() if k != slot}
        if items:
            out["items"] = items
        else:
            out.pop("items")
    return out


def _with_image(value, slot, image):
    if not isinstance(slot, str) or slot not in SLOTS:
        raise Bad(BAD_SLOT)
    out = dict(value)
    pics = dict(out.get(PICTURES) or {})
    items = dict(out.get("items") or {})
    if image is None:
        for key in (slot, "o" + slot):
            pics.pop(key, None)
        items.pop(slot, None)
        _put_back(out, pics, items)
        return out
    picture(image, PICTURE_MAX)                              # a type or text that is not an image is refused in words before it is read
    kind, raw = imagecap._decode_data(image)
    item = dict(items.get(slot) or {})
    for key in FRAMING:
        item.pop(key, None)                                  # another image does not keep the framing of the one it replaces
    if kind == "png":
        w, h = imagecap.png_size(raw)
        if w > WIDTH_MAX:                                    # made 1,600 px wide (never enlarged)
            pw, ph, ch, rows = imagecap._read_png(raw)
            rows, nw, nh = imagecap._smaller(rows, pw, ph, ch, WIDTH_MAX)
            image = imagecap._encode_data(imagecap._write_png(rows, nw, nh, ch, ""))
            item["from_w"] = pw
    else:
        size = imagecap._jpeg_size(raw) if kind == "jpeg" else imagecap._webp_size(raw)
        if size is None:
            raise Bad(NOT_A_PICTURE)
        if size[0] > WIDTH_MAX:
            raise Bad(TOO_WIDE)
    image = picture(image, ORIGINAL_MAX)
    framed = _make(image, _numbers(item, out.get("shape", DEFAULT_SHAPE), image))
    pics[slot] = framed
    if framed == image:
        pics.pop("o" + slot, None)
    else:
        pics["o" + slot] = image
    if item:
        items[slot] = item
    else:
        items.pop(slot, None)
    _put_back(out, pics, items)
    return out


def _put_back(out, pics, items):
    for key, got in ((PICTURES, pics), ("items", items)):
        if got:
            out[key] = got
        else:
            out.pop(key, None)
    if "order" in out and not pics and not items:
        out.pop("order")                                     # nothing left to put in order


def published(value, ctx):
    """The images in the order shown, each with its caption and description; None while there is no image. Version 2 adds `columns` and
    `shape`, and publishes only the framed copy (never an original), and only when it is the one made from the stored original and
    framing."""
    if type(value) is not dict:
        return None
    pics = value.get(PICTURES) or {}
    items = value.get("items") or {}
    if value.get("v") != 2:
        shown = [{"image": pics[s], "caption": (items.get(s) or {}).get("caption", ""), "alt": (items.get(s) or {}).get("alt", "")}
                 for s in SLOTS if pics.get(s)]
        if not shown:
            return None
        content = {"pictures": shown}                        # a version 1 body: exactly as 1.0.7 and the first view published it
        if value.get("columns") in COLUMNS:
            content["columns"] = value["columns"]
        if value.get("shape") in SHAPES:
            content["shape"] = value["shape"]
        return {"content": content}
    shape = value.get("shape", DEFAULT_SHAPE)
    shown = []
    try:
        if shape not in SHAPES:
            return None
        order = [s for s in value.get("order") or [] if s in SLOTS] + list(SLOTS)
        for s in dict.fromkeys(order):
            framed = pics.get(s)
            if not framed:
                continue
            item = items.get(s) or {}
            source = pics.get("o" + s) or framed
            if not imagecap._framed_belongs(source, framed, _numbers(item, shape, source)):
                continue
            one = {"image": framed, "caption": item.get("caption", ""), "alt": item.get("alt", "")}
            for key in ("fit", "fill"):
                if key in item:
                    one[key] = item[key]
            shown.append(one)
    except (Bad, ValueError):
        return None
    if not shown:
        return None
    columns = value.get("columns", DEFAULT_COLUMNS)
    if columns not in COLUMNS:
        return None
    return {"content": {"pictures": shown, "columns": columns, "shape": shape}}
