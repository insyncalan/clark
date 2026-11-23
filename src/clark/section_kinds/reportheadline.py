"""Report headline (#1261, slice 1): the content of a section of type 'reportheadline'. The one line a report opens with, with the
project's health beside it and a supporting sentence under it. A NEW type, not a variant of the headline band (headline.py).

Stored (canonical JSON, checked by section_bodies before and after this): {"v": 1, "health": "on_track" | "at_risk" | "off_track",
"headline": text, "sentence": text, "pill": false}. "pill" (row 1261, the eye) is only ever stored as false, the pill hidden;
a body without it shows the pill, so every page written before the eye keeps drawing it. A field that is missing reads as its default (health '' = not set, the words ''), and a field that
holds nothing is not stored, so one content always stores as the same text. Typed only: it holds no reference to a work item. Fields are
picked by name and an unknown one is refused. The headline has no length limit of its own (the owner's ruling, 16-11); the whole body is
held to LIMIT bytes like any other. Nothing is empty but a body with no headline and no sentence and no health: it starts as '' and stays
out of the published file.
"""
from clark.section_kinds.base import Bad

READY = True
LIMIT = 32768
EMPTY = ""
START = '{"pill":false,"v":1}'      # the body a new Report headline starts with when At a glance already shows the health (changes.py accepts this one body for a new reportheadline section; row 1261: health shows once); canonical, as the store writes it

HEALTHS = ("on_track", "at_risk", "off_track")
WORDS = {"": "Not set", "on_track": "On track", "at_risk": "At risk", "off_track": "Off track"}
KEYS = ("v", "health", "headline", "sentence", "pill")

NOT_OBJECT = "A report headline must be one set of fields. Check it and try again."
BAD_FIELD = "A report headline field has the wrong kind of value. Check it and try again."
UNKNOWN_FIELD = "A report headline has a field it does not keep. Reload the page and try again."
BAD_HEALTH = "The health is on track, at risk or off track, or not set. Choose one of those."
TOO_LONG = f"The report headline is too long to keep ({LIMIT // 1024} KB at most in all). Shorten it and try again."


def upgrade(value):
    """The body with every field present at its default (version 1 is the only one so far), for a reader that needs them all. A body
    that is not an object, or that holds a wrong kind of value, comes back as the empty defaults."""
    v = value if type(value) is dict else {}
    health = v.get("health")
    return {"v": 1, "health": health if health in HEALTHS else "", "pill": v.get("pill") is not False,
            "headline": v["headline"].strip() if isinstance(v.get("headline"), str) else "",
            "sentence": v["sentence"].strip() if isinstance(v.get("sentence"), str) else ""}


def _text(value, key):
    text = value.get(key)
    if text is None:
        return ""
    if not isinstance(text, str):
        raise Bad(BAD_FIELD)
    return text.strip()


def check(value, rules):
    """The report headline rebuilt field by field, or Bad in plain words that never quote it."""
    if not isinstance(value, dict) or value.get("v") != 1:
        raise Bad(NOT_OBJECT)
    if any(k not in KEYS for k in value):
        raise Bad(UNKNOWN_FIELD)
    health = value.get("health")
    if health is None or health == "":
        health = ""
    elif not isinstance(health, str) or health not in HEALTHS:
        raise Bad(BAD_HEALTH)
    pill = value.get("pill")
    if pill is not None and not isinstance(pill, bool):
        raise Bad(BAD_FIELD)
    out = {"v": 1}
    if pill is False:
        out["pill"] = False
    for k, v in (("health", health), ("headline", _text(value, "headline")), ("sentence", _text(value, "sentence"))):
        if v:
            out[k] = v
    if len(str(out).encode("utf-8")) > LIMIT:
        raise Bad(TOO_LONG)
    return out


def published(value, ctx):
    """What the file carries: {"content": {health, headline, sentence, pill}} with every field present, or None when there is nothing to show."""
    u = upgrade(value)
    if not ((u["health"] and u["pill"]) or u["headline"] or u["sentence"]):      # a health with its pill hidden shows nothing
        return None
    return {"content": {"health": u["health"], "headline": u["headline"], "sentence": u["sentence"], "pill": u["pill"]}}
