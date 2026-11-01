"""Callout (H1, #96): the content of a section of type 'callout': one thing the reader must see. READY.

Stored (canonical JSON, checked by section_bodies before and after this): {"v": 1, "tone": "info" | "decision" | "warning",
"title": text, "paras": [text, ...]}. Typed only: it holds no reference to a work item, so nothing here can leak a hidden one.
Fields are picked by name and rebuilt; an unknown field is dropped. A callout with no title and no paragraph is empty: it
starts as '' (no content) and stays out of the published file.
"""
from clark.section_kinds.base import Bad

READY = True
LIMIT = 8192
EMPTY = ""

TONES = ("info", "decision", "warning")
TITLE_MAX, PARA_MAX, PARAS_MAX = 120, 600, 6

NOT_OBJECT = "A callout must be one set of fields. Check it and try again."
BAD_FIELD = "A callout field has the wrong kind of value. Check it and try again."
BAD_TONE = "A callout is information, a decision needed or a warning. Choose one of the three."
TOO_LONG_TITLE = f"A callout title can be {TITLE_MAX} characters at most. Shorten it and try again."
TOO_LONG_PARA = f"A callout paragraph can be {PARA_MAX} characters at most. Shorten it or split it in two."
TOO_MANY = f"A callout can have {PARAS_MAX} paragraphs at most. Remove one and try again."


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
    """The callout rebuilt field by field (empty paragraphs dropped), or Bad in plain words that never quote it."""
    if not isinstance(value, dict) or value.get("v") != 1:
        raise Bad(NOT_OBJECT)
    tone = value.get("tone", "info")
    if tone not in TONES:
        raise Bad(BAD_TONE)
    title = _text(value.get("title"), TITLE_MAX, TOO_LONG_TITLE)
    paras = value.get("paras", [])
    if paras is None:
        paras = []
    if type(paras) is not list:
        raise Bad(BAD_FIELD)
    paras = [p for p in (_text(p, PARA_MAX, TOO_LONG_PARA) for p in paras) if p]
    if len(paras) > PARAS_MAX:
        raise Bad(TOO_MANY)
    return {"v": 1, "tone": tone, "title": title, "paras": paras}


def published(value, ctx):
    """What the file carries: {"content": {tone, title, paras}}, or None when there is nothing to show."""
    if not value.get("title") and not value.get("paras"):
        return None
    return {"content": {"tone": value["tone"], "title": value["title"], "paras": list(value["paras"])}}
