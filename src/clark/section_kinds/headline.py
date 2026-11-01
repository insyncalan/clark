"""Headline band (F2, #96): the content of a section of type 'headline'. A band that opens the report with a message (a
milestone reached, a go-live), an optional picture and an optional button that links on.

The stored body: `{"v": 1, "words", "label", "href", "alt", "pictures": {"image": ...}}`: `words` one paragraph of plain text;
`label` and `href` the button (it is shown only when both are there); `alt` the picture's description. A link is https:, mailto:
or a place on the page (#), as publish.safe_href allows. The picture and text rules are the Pictures group's, in textimage.py: a
picture comes only through POST /api/section-image (with_picture), never with the words.
"""
from clark.section_kinds.base import Bad
from clark.section_kinds.textimage import PICTURES, PICTURE_MAX, TEXT_LIMIT, frame, line, pictures_of, put, set_picture

READY = True
LIMIT = 1600 * 1024                 # one picture at PICTURE_MAX in base64 and its words
EMPTY = ""
SLOTS = ("image",)
WORDS_MAX = 400                     # characters in the band's message
LABEL_MAX = 40                      # characters on the button
HREF_MAX = 2000
__all__ = ("READY", "LIMIT", "EMPTY", "SLOTS", "PICTURE_MAX", "TEXT_LIMIT", "check", "with_picture", "published", "link")

LONG_WORDS = f"The message can be {WORDS_MAX} characters at most. Shorten it and try again."
LONG_LABEL = f"A button's words can be {LABEL_MAX} characters at most. Shorten them and try again."
BAD_LINK = "A button's link must start with https:// or mailto:, or go to a place on the page (#). Check the link and try again."
_SPACES = "".join(chr(c) for c in range(0x21))


def link(text):
    """Whether `text` is a link a reader may follow from the published page: publish.safe_href's rule (https:, mailto: or #)."""
    v = "".join(c for c in text if c not in _SPACES).lower()
    return v.startswith(("https://", "mailto:", "#"))


def check(value, rules):
    out = frame(value, ("words", "label", "href", "alt", PICTURES))
    put(out, "words", line(value, "words", WORDS_MAX, LONG_WORDS))
    put(out, "label", line(value, "label", LABEL_MAX, LONG_LABEL))
    href = line(value, "href", HREF_MAX, BAD_LINK)
    if href and not link(href):
        raise Bad(BAD_LINK)
    put(out, "href", href)
    put(out, "alt", line(value, "alt"))
    put(out, PICTURES, pictures_of(value, SLOTS, PICTURE_MAX))
    return out


def with_picture(value, slot, image):
    """The body with its one picture set or taken out (POST /api/section-image, through changes.py)."""
    return set_picture(value, slot, image, SLOTS, {"v": 1})


def published(value, ctx):
    """The message, the button (only with both its words and its link) and the picture (with its description); None when there
    is none of them."""
    if type(value) is not dict:
        return None
    content = {}
    put(content, "words", value.get("words", ""))
    if value.get("label") and value.get("href"):
        content.update({"label": value["label"], "href": value["href"]})
    image = (value.get(PICTURES) or {}).get("image", "")
    if image:
        content.update({"image": image, "alt": value.get("alt", "")})
    return {"content": content} if content else None
