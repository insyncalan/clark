"""Image gallery (F5, #96): the content of a section of type 'gallery'. Up to six pictures in a grid, each with a caption and a
description for someone who can't see it.

The stored body: `{"v": 1, "items": {slot: {"caption", "alt"}}, "pictures": {slot: ...}}`, the slots "1" to "6" in the order
they are shown. The picture and text rules are the Pictures group's, in textimage.py: a picture comes only through POST
/api/section-image (with_picture), never with the words, and taking a picture out takes its caption and description with it.
Six pictures share one section's limit, so each may be smaller than in the one-picture templates (PICTURE_MAX; the page shrinks
gallery pictures further).
"""
from clark.section_kinds.base import Bad
from clark.section_kinds.textimage import NOT_CONTENT, BAD_SLOT, PICTURES, TEXT_LIMIT, frame, line, pictures_of, put, set_picture

READY = True
SLOTS = ("1", "2", "3", "4", "5", "6")
PICTURE_MAX = 400 * 1024            # each of six (decoded); in base64 about 534 KB, so six fit the limit with their words
LIMIT = 3 * 1024 * 1024 + 256 * 1024     # six pictures at PICTURE_MAX in base64 (3.1 MB) and their words
EMPTY = ""
__all__ = ("READY", "LIMIT", "EMPTY", "SLOTS", "PICTURE_MAX", "TEXT_LIMIT", "check", "with_picture", "published")


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
        one = frame(item, ("caption", "alt"))
        one.pop("v")
        put(one, "caption", line(item, "caption"))
        put(one, "alt", line(item, "alt"))
        if one:
            out[slot] = one
    return out


def check(value, rules):
    out = frame(value, ("items", PICTURES))
    put(out, "items", _items(value))
    put(out, PICTURES, pictures_of(value, SLOTS, PICTURE_MAX))
    return out


def with_picture(value, slot, image):
    """The body with the picture in `slot` set or taken out; taking it out takes its caption and description too."""
    out = set_picture(value, slot, image, SLOTS, {"v": 1})
    if image is None and type(out.get("items")) is dict and slot in out["items"]:
        items = {k: v for k, v in out["items"].items() if k != slot}
        if items:
            out["items"] = items
        else:
            out.pop("items")
    return out


def published(value, ctx):
    """The pictures in slot order, each with its caption and description; None while there is no picture."""
    if type(value) is not dict:
        return None
    pics = value.get(PICTURES) or {}
    items = value.get("items") or {}
    shown = [{"image": pics[s], "caption": (items.get(s) or {}).get("caption", ""), "alt": (items.get(s) or {}).get("alt", "")}
             for s in SLOTS if pics.get(s)]
    return {"content": {"pictures": shown}} if shown else None
