"""Quote (H3, #96): the content of a section of type 'quote': one quotation and who said it. READY.

Stored (canonical JSON): {"v": 1, "quote": text, "by": text, "role": text}. Typed only. A quote with no words is empty: it
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


def check(value, rules):
    """The quote rebuilt field by field, or Bad in plain words that never quote it."""
    if not isinstance(value, dict) or value.get("v") != 1:
        raise Bad(NOT_OBJECT)
    return {"v": 1, "quote": _text(value.get("quote"), QUOTE_MAX, TOO_LONG), "by": _text(value.get("by"), NAME_MAX, TOO_LONG_NAME),
            "role": _text(value.get("role"), NAME_MAX, TOO_LONG_NAME)}


def published(value, ctx):
    """{"content": {quote, by, role}}, or None when there are no words to show."""
    if not value.get("quote"):
        return None
    return {"content": {"quote": value["quote"], "by": value.get("by", ""), "role": value.get("role", "")}}
