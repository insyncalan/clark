"""Image with caption (H2, #96): the content of a section of type 'imagecap'. One picture with a caption under it and a
description for someone who can't see it.

The stored body: `{"v": 1, "caption", "alt", "pictures": {"image": ...}}`. The picture and text rules are the Pictures group's,
in textimage.py: a picture comes only through POST /api/section-image (with_picture), never with the words.
"""
from clark.section_kinds.textimage import PICTURES, PICTURE_MAX, TEXT_LIMIT, frame, line, pictures_of, put, set_picture

READY = True
LIMIT = 1600 * 1024                 # one picture at PICTURE_MAX in base64 and its words
EMPTY = ""
SLOTS = ("image",)
__all__ = ("READY", "LIMIT", "EMPTY", "SLOTS", "PICTURE_MAX", "TEXT_LIMIT", "check", "with_picture", "published")


def check(value, rules):
    out = frame(value, ("caption", "alt", PICTURES))
    put(out, "caption", line(value, "caption"))
    put(out, "alt", line(value, "alt"))
    put(out, PICTURES, pictures_of(value, SLOTS, PICTURE_MAX))
    return out


def with_picture(value, slot, image):
    """The body with its one picture set or taken out (POST /api/section-image, through changes.py)."""
    return set_picture(value, slot, image, SLOTS, {"v": 1})


def published(value, ctx):
    """The picture with its caption and description; None while there is no picture (a caption alone is not shown)."""
    if type(value) is not dict:
        return None
    image = (value.get(PICTURES) or {}).get("image", "")
    if not image:
        return None
    return {"content": {"image": image, "caption": value.get("caption", ""), "alt": value.get("alt", "")}}
