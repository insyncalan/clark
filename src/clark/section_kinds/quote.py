"""Quote (H3, #96): the content of a section of type 'quote': one quotation and who said it. READY.

Stored (canonical JSON): {"v": 1, "quote": text, "by": text, "role": text} and, only when off, "tile": false and/or "heading": false
(row 1271: Tile and Heading are two independent switches, both on when the field is missing, so every older quote reads as before). Typed only. A quote with no words is empty: it
starts as '' (no content) and stays out of the published file, whatever its attribution.
"""
from clark.section_kinds.base import Bad

READY = True
LIMIT = 4096
EMPTY = ""

QUOTE_MAX, NAME_MAX = 600, 120

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


def _switch(value, name):
    """True when the switch is on (missing or None is on); Bad when it is not a true or false."""
    got = value.get(name)
    if got is None:
        return True
    if type(got) is not bool:
        raise Bad(BAD_FIELD)
    return got


def check(value, rules):
    """The quote rebuilt field by field, or Bad in plain words that never quote it."""
    if not isinstance(value, dict) or value.get("v") != 1:
        raise Bad(NOT_OBJECT)
    out = {"v": 1, "quote": _text(value.get("quote"), QUOTE_MAX, TOO_LONG), "by": _text(value.get("by"), NAME_MAX, TOO_LONG_NAME),
           "role": _text(value.get("role"), NAME_MAX, TOO_LONG_NAME)}
    for name in ("tile", "heading"):
        if not _switch(value, name):
            out[name] = False                  # only an off switch is stored: a body with both on is the body it always was
    return out


def published(value, ctx):
    """{"content": {quote, by, role, and tile / heading false when off}}, or None when there are no words to show."""
    if not value.get("quote"):
        return None
    content = {"quote": value["quote"], "by": value.get("by", ""), "role": value.get("role", "")}
    content.update({name: False for name in ("tile", "heading") if value.get(name) is False})   # the file says so only when a switch is off
    return {"content": content}
