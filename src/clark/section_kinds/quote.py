"""Quote (H3, item 96; row 1271): the content of a section of type 'quote': up to six quotations, each with who said it. READY.

Stored (canonical JSON): {"v": 1, "quote": text, "by": text, "role": text} is the older one-quote shape and is read and kept unchanged.
Row 1271 adds these optional fields: "quotes" ([{"quote", "by", "role"}, ...], six at most; it replaces the three top-level fields when
present), "align" ("left" | "centre"; left is the default), "perRow" (2 | 3; 2 is the default), "tile" and "heading" (true or false).
`upgrade` gives a reader every field filled in (an older quote is one quote, left, two per row, tile and heading on); nothing is rewritten
in the store. Typed only. A quote with no words is empty: it stays in the store while it is being typed, and stays out of the published
file, whatever its attribution. A section with no quote that has words is not published.
"""
from clark.section_kinds.base import Bad

READY = True
LIMIT = 65536      # six quotes at their longest (6 x 840 characters), each an emoji stored as a 12-byte escape pair: about 60.5 KB, well under the change route (516 KB)
EMPTY = ""

QUOTE_MAX, NAME_MAX = 600, 120
QUOTES_MAX = 6
ALIGNS = ("left", "centre")
PER_ROWS = (2, 3)

NOT_OBJECT = "A quote must be one set of fields. Check it and try again."
BAD_FIELD = "A quote field has the wrong kind of value. Check it and try again."
TOO_LONG = f"A quote can be {QUOTE_MAX} characters at most. Shorten it and try again."
TOO_LONG_NAME = f"Who said it, and their role, can each be {NAME_MAX} characters at most. Shorten it and try again."


def _text(value, most, words):
    if value is None:
        return ""
    if not isinstance(value, str):
        raise Bad(BAD_FIELD)
    value = value.strip()
    if len(value) > most:
        raise Bad(words)
    return value


def _one(value):
    """One quote rebuilt field by field."""
    if not isinstance(value, dict):
        raise Bad(BAD_FIELD)
    return {"quote": _text(value.get("quote"), QUOTE_MAX, TOO_LONG), "by": _text(value.get("by"), NAME_MAX, TOO_LONG_NAME),
            "role": _text(value.get("role"), NAME_MAX, TOO_LONG_NAME)}


def check(value, rules):
    """The quote rebuilt field by field, or Bad in plain words that never quote it. The older shape stays the older shape."""
    if not isinstance(value, dict) or value.get("v") != 1:
        raise Bad(NOT_OBJECT)
    if value.get("quotes") is not None:
        quotes = value["quotes"]
        if type(quotes) is not list or len(quotes) > QUOTES_MAX or not quotes:
            raise Bad(BAD_FIELD)
        out = {"v": 1, "quotes": [_one(q) for q in quotes]}
    else:
        out = {"v": 1, **_one(value)}
    if value.get("align") is not None:
        if value["align"] not in ALIGNS:
            raise Bad(BAD_FIELD)
        out["align"] = value["align"]
    if value.get("perRow") is not None:
        if type(value["perRow"]) is not int or value["perRow"] not in PER_ROWS:
            raise Bad(BAD_FIELD)
        out["perRow"] = value["perRow"]
    for name in ("tile", "heading"):
        if value.get(name) is not None:
            if type(value[name]) is not bool:
                raise Bad(BAD_FIELD)
            out[name] = value[name]
    return out


def upgrade(value):
    """The stored quote with every field filled in: {"quotes": [{quote, by, role}], "align", "perRow", "tile", "heading"}. The older one-quote
    shape is its one quote. The stored text is not changed; a reader asks here."""
    quotes = value["quotes"] if "quotes" in value else [{"quote": value.get("quote", ""), "by": value.get("by", ""), "role": value.get("role", "")}]
    return {"quotes": [dict(q) for q in quotes], "align": value.get("align", "left"), "perRow": value.get("perRow", 2),
            "tile": value.get("tile", True), "heading": value.get("heading", True)}


def published(value, ctx):
    """{"content": {quotes, align, perRow, tile, heading, quote, by, role}} with only the quotes that have words (quote, by and role are the
    first of them, as an older reader reads them), or None when no quote has words."""
    v = upgrade(value)
    kept = [q for q in v["quotes"] if q["quote"]]
    if not kept:
        return None
    return {"content": {"quotes": kept, "align": v["align"], "perRow": v["perRow"], "tile": v["tile"], "heading": v["heading"], **kept[0]}}
