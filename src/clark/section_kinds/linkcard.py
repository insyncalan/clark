"""Link preview (F7, #96): the content of a section of type 'linkcard', a web page shown as a card. A card, not a live embed:
every word on it is typed, and clark never fetches the page (no address is ever opened by clark, here or at publish). The link
rule is Documents and links' (doclinks.py). See base.py.

The stored content (canonical JSON, checked field by field; anything else is refused):

    {"v": 1, "href": LINK, "title": TEXT, "site": TEXT, "text": [LINE, ...]}

`href` an https:// or mailto: link; `title` the card's heading (at most LABEL_MAX characters; '' shows the link); `site` the
small line above it, such as the site's name ('' leaves it out); `text` at most TEXT_LINES lines of at most LINE_MAX characters.
Published: those fields, picked by name; nothing until there is a link.
"""
from clark.section_kinds import doclinks as files

READY = True
LIMIT = 8192
EMPTY = ""
TEXT_LINES = 3
LINE_MAX = 400
BAD_TEXT = f"The words on the card can be {TEXT_LINES} paragraphs of {LINE_MAX} characters at most. Shorten them and try again."


def check(value, rules):
    value = files.fields(value, ("v", "href", "title", "site", "text"), ("v",))
    files.version(value)
    out = {"v": 1, "title": files.words(value.get("title", ""), rules), "site": files.words(value.get("site", ""), rules),
           "text": files.paragraphs(value.get("text", []), rules, TEXT_LINES, LINE_MAX, BAD_TEXT)}
    if value.get("href") not in (None, ""):
        out["href"] = files.link(value["href"])
    return out


def published(value, ctx):
    """The link and the card's words. None until there is a link."""
    href = value.get("href") if isinstance(value, dict) else None
    if not href:
        return None
    return {"content": {"href": href, "title": value.get("title", ""), "site": value.get("site", ""),
                        "text": list(value.get("text") or [])}}
