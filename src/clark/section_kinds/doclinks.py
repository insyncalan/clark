"""Documents and links (F4, #96): the content of a section of type 'doclinks', and the file and link rules the other two Files and
links templates (onedoc.py, linkcard.py) use, so the three never drift apart. See base.py for the contract.

The stored content (canonical JSON, checked field by field; anything else is refused):

    {"v": 1, "items": [ITEM, ...]}          at most MAX_ITEMS items, in the order the reader sees them
    ITEM = {"kind": "file", "name": NAME, "rel": "Report files/" + NAME, "bytes": N, "label": TEXT}    label may be ""
         | {"kind": "link", "href": LINK, "label": TEXT}                                              label may be ""

- A file is one the server copied into the client folder's "Report files" folder (POST /api/section-file): its name, the
  address relative to the report ("Report files/<name>", so it opens from the client's copy of the report, beside which that
  folder sits) and its size. A name is one file name: no folder, no character Windows, OneDrive or SharePoint refuse.
- A link is https:// or mailto: only (as publish.safe_href allows; never javascript:, data:, http: or a relative address),
  with nothing hidden in it (no space or control character), at most LINK_MAX characters.
- Words (a label) are plain text on one line, at most LABEL_MAX characters. No item is ever a copy of a work item.
- A field this section does not use is dropped, never stored (the content is rebuilt from the fields named here only).

Published: the same items, fields picked by name; nothing when there is no item (an empty template stays out of the file). The
page draws them from the file's own data block (page/src/templates/DocLinks.jsx).
"""
from clark.section_kinds.base import Bad

READY = True
LIMIT = 32768                       # bytes of stored text: twenty items with long names and links fit with room to spare
EMPTY = ""
MAX_ITEMS = 20
LABEL_MAX = 120                     # characters of a label, a title or a site name
NAME_MAX = 120                      # platform.MAX_NAME: every file name clark makes is this short or shorter
LINK_MAX = 2000                     # the Supporting Documents rule's longest link (clark/doclinks.py MAX_LENGTH)
BYTES_MAX = 2 ** 40                 # a file's size, at most (a terabyte)
FILES_FOLDER = "Report files"       # the folder beside the client's copy of the report (page/src/templates/safe.js FILES_FOLDER)

RESERVED = set('<>:"/\\|?*\x7f') | {chr(n) for n in range(32)}      # platform.RESERVED_CHARS, and DEL
SPACES = {chr(n) for n in range(33)} | {"\x7f", "\\"}                 # nothing hidden in a link, and no backslash

NOT_OBJECT = "That content can't be read as this section. Reload the page and try again."
BAD_VERSION = "That content was saved by a different version of clark. Reload the page and try again."
TOO_MANY = f"A Documents and links section can hold {MAX_ITEMS} files and links at most. Remove one, then add the new one."
BAD_KIND = "Each entry must be a file or a link. Reload the page and try again."
BAD_LABEL = f"Words for a file or link must be one line of {LABEL_MAX} characters at most. Shorten them and try again."
BAD_LINK = "That link can't be used. It must start with https:// or mailto: and have no spaces. Paste the whole address and try again."
BAD_FILE = "That file entry can't be used. Add the file again with Add a file."


def fields(value, allowed, required=()):
    """`value` as a dict of only its `allowed` keys (any other is dropped), holding every `required` one, or Bad."""
    if type(value) is not dict or any(k not in value for k in required):
        raise Bad(NOT_OBJECT)
    return {k: value[k] for k in allowed if k in value}


def version(value):
    """The content's shape number: 1, a whole number (never True)."""
    if type(value.get("v")) is not int or value.get("v") != 1:
        raise Bad(BAD_VERSION)


def words(value, rules, limit=LABEL_MAX, refusal=BAD_LABEL):
    """One line of plain text, at most `limit` characters ('' is allowed), or Bad. The generic check already refused control and
    invisible characters; spaces at either end are dropped, and words with nothing visible in them are ''."""
    if not isinstance(value, str) or not rules.plain(value):
        raise Bad(refusal)
    value = value.strip()
    if len(value) > limit:
        raise Bad(refusal)
    return value if value and rules.visible(value) else ""


def paragraphs(value, rules, most, each, refusal):
    """A list of at most `most` lines of plain text of at most `each` characters each; empty lines dropped."""
    if type(value) is not list or len(value) > most:
        raise Bad(refusal)
    return [p for p in (words(p, rules, each, refusal) for p in value) if p]


def link(value):
    """A link a reader may follow: https://<site>... or mailto:<someone>, with no space or control character anywhere, at most
    LINK_MAX characters; kept as typed. Else Bad."""
    if not isinstance(value, str) or not value or len(value) > LINK_MAX or any(c in SPACES for c in value):
        raise Bad(BAD_LINK)
    low = value.lower()
    if low.startswith("https://"):
        rest = value[8:]
        host = rest[:min([rest.index(c) for c in "/?#" if c in rest] or [len(rest)])]
        if not host or "@" in host or host.startswith((".", ":")):
            raise Bad(BAD_LINK)       # no site, or a user name in front of it (which hides where the link goes)
        return value
    if low.startswith("mailto:") and len(value) > 7:
        return value
    raise Bad(BAD_LINK)


def file_name(value):
    """One file name as clark makes it (platform.safe_name): no folder, no reserved character, not hidden (a leading dot), no
    space or dot at the end, at most NAME_MAX characters. Else Bad."""
    if (not isinstance(value, str) or not value or len(value) > NAME_MAX or any(c in RESERVED for c in value) or value != value.strip()
            or value.endswith(".") or value.startswith(".")):
        raise Bad(BAD_FILE)
    return value


def file_entry(value):
    """{name, rel, bytes}, the address always "Report files/<name>". Else Bad."""
    value = fields(value, ("name", "rel", "bytes"), ("name", "rel", "bytes"))
    name = file_name(value["name"])
    if value["rel"] != f"{FILES_FOLDER}/{name}":
        raise Bad(BAD_FILE)
    size = value["bytes"]
    if type(size) is not int or size < 0 or size > BYTES_MAX:
        raise Bad(BAD_FILE)
    return {"name": name, "rel": value["rel"], "bytes": size}


def _item(value, rules):
    if type(value) is not dict:
        raise Bad(BAD_KIND)
    kind = value.get("kind")
    if kind == "file":
        value = fields(value, ("kind", "name", "rel", "bytes", "label"), ("kind", "name", "rel", "bytes"))
        return {"kind": "file", **file_entry({k: value[k] for k in ("name", "rel", "bytes")}),
                "label": words(value.get("label", ""), rules)}
    if kind == "link":
        value = fields(value, ("kind", "href", "label"), ("kind", "href"))
        return {"kind": "link", "href": link(value["href"]), "label": words(value.get("label", ""), rules)}
    raise Bad(BAD_KIND)


def check(value, rules):
    value = fields(value, ("v", "items"), ("v",))
    version(value)
    items = value.get("items", [])
    if type(items) is not list:
        raise Bad(NOT_OBJECT)
    if len(items) > MAX_ITEMS:
        raise Bad(TOO_MANY)
    return {"v": 1, "items": [_item(i, rules) for i in items]}


def published(value, ctx):
    """The items, each picked by name. None when there is none: an empty template stays out of the file."""
    items = []
    for i in (value.get("items") or []) if isinstance(value, dict) else []:
        if i.get("kind") == "file":
            items.append({"kind": "file", "name": i["name"], "rel": i["rel"], "bytes": i["bytes"], "label": i.get("label", "")})
        elif i.get("kind") == "link":
            items.append({"kind": "link", "href": i["href"], "label": i.get("label", "")})
    return {"content": {"items": items}} if items else None


def add_file(value, entry):
    """The content with the file `entry` ({name, rel, bytes}, made by the server) added at the end: what POST /api/section-file
    stores, in one step. `value` is the checked content, or None for a section with none yet. Bad when the section is full."""
    items = list((value or {}).get("items") or [])
    if len(items) >= MAX_ITEMS:
        raise Bad(TOO_MANY)
    items.append({"kind": "file", **file_entry(entry), "label": ""})
    return {"v": 1, "items": items}
