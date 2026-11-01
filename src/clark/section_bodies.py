"""A section that carries content: the checker registry (the shared base for 'Needs from you' and 'Progress tracker').

A section of type `needs` or `tracker`, or of one of the section template types (#96, the registry in section_kinds/), keeps its
content as JSON text in the section's `body` column. This module is pure (it reads no file and no database, and imports nothing
from clark but the registry, which is pure too): store.py calls it from the section rules, so every write of a body, including
an Undo that puts one back, passes through the same walls; publish.py calls it again at publish time.

What this base decides, and nothing more:
- the content is one JSON object or one JSON list, no longer than the type's byte limit (checked before it is parsed);
- every key and every text value is plain text (the store's own text rules: nothing a person can't see, no line breaks, no
  right-to-left override, no lone surrogate); markup is never read as markup, it is only text;
- no number with a fraction, no NaN or Infinity, no very long number, no repeated key, nothing nested deeper than MAX_DEPTH;
- what is stored is the CANONICAL text (sorted keys, no spaces, ASCII escapes), rebuilt from what was parsed, never the
  request's own text. The same content therefore always makes the same text, and saving it again changes nothing.

What the base does NOT decide: the content's own shape. That is each item's job, in its checker:
- #121 (needs) fills `_checked_needs`; #189 (tracker) fills `_checked_tracker`. Both are stubs here: they accept whatever
  passed the generic check above. #189's open question (is a line's number 0 to 100, or a share of the whole, and is the overall
  figure the sum of the group totals) is NOT decided here.

The plug-in points (a later item changes only these, never store.py, changes.py or history.py):
- CHECKERS[type](value, rules) -> value: given the parsed content (already through the generic check), return the content
  rebuilt field by field, or raise Bad in plain words that never quote the value. `rules` offers rules.plain(text) and
  rules.visible(text), the store's text rules (see Rules).
- EMPTY[type]: the body a new section of that type starts with. Chosen by the store, never taken from the request.
- LIMITS[type]: the most bytes the stored text may take.
- published(type, value, ctx): what a published file carries of a checked body (a dict that is merged into the section's entry),
  or None to leave the section out. The base publishes nothing of the content (see published).

A section template (#96) is NOT added here: each one is a module in section_kinds/ (its READY, LIMIT, EMPTY, check and
published; the contract is section_kinds/base.py), and the tables below are built from that registry, which is filled with all
eighteen types up front. A template's builder changes only its own module.
"""
import json
import unicodedata

from clark.section_kinds import REGISTRY as TEMPLATES, TYPES as TEMPLATE_TYPES
from clark.section_kinds.base import Bad, Context

NEEDS, TRACKER = "needs", "tracker"
BODY_TYPES = (NEEDS, TRACKER) + TEMPLATE_TYPES   # the section types (besides text) that carry content
MAX_DEPTH = 8                            # lists and objects inside each other, at most
MAX_DIGITS = 15                          # a whole number of more digits is refused before Python reads it (slow on 3.9)
DEFAULT_LIMIT = 262144                   # bytes of stored text, unless LIMITS says less
LIMITS = {NEEDS: 65536, TRACKER: 262144, **{t: m.LIMIT for t, m in TEMPLATES.items()}}


class Rules:
    """The store's text rules, handed in (this module has none of its own, so there is one set of rules for text).
    plain(text): True when the text can be saved and a person can read it (no control, format, private-use, surrogate or
    separator character). visible(text): True when it also holds at least one visible letter, number or symbol."""

    def __init__(self, plain, visible):
        self.plain, self.visible = plain, visible


NOT_TEXT = "That content must be a list or an object, sent as text."
TOO_BIG = "That content is too long to save."
NOT_READABLE = "That content could not be read. Check it and try again."
TOO_DEEP = "That content is nested too deeply."
BAD_NUMBER = "That content has a number that can't be saved. Use whole numbers."
REPEATED = "That content names one field twice."
BAD_TEXT = "That content can't hold control or invisible characters."
BAD_VALUE = "That content has something that isn't text, a whole number, yes or no, or empty."
NOT_SAVED_YET = "That kind of section can't hold content."


def _refuse_constant(name):
    raise Bad(BAD_NUMBER)                # NaN, Infinity, -Infinity


def _refuse_float(text):
    raise Bad(BAD_NUMBER)


def _whole_number(text):
    if len(text.lstrip("-")) > MAX_DIGITS:
        raise Bad(BAD_NUMBER)
    return int(text)


def _no_repeats(pairs):
    seen = {}
    for k, v in pairs:
        if k in seen:
            raise Bad(REPEATED)
        seen[k] = v
    return seen


def _rebuilt(value, rules, depth):
    """`value` rebuilt: the same list, object and values, each text made NFC, and anything but a list, object, text, whole
    number, true, false or null refused. Text is checked with the store's rules; a key is text too."""
    if depth > MAX_DEPTH:
        raise Bad(TOO_DEEP)
    if value is None or type(value) is bool or type(value) is int:
        return value
    if isinstance(value, str):
        if not rules.plain(value):
            raise Bad(BAD_TEXT)
        return unicodedata.normalize("NFC", value)
    if type(value) is list:
        return [_rebuilt(v, rules, depth + 1) for v in value]
    if type(value) is dict:
        out = {}
        for k, v in value.items():
            key = _rebuilt(k, rules, depth + 1)
            if key in out:
                raise Bad(REPEATED)      # two keys that are one after NFC
            out[key] = _rebuilt(v, rules, depth + 1)
        return out
    raise Bad(BAD_VALUE)


def canonical(value):
    """The one text a content is stored as: sorted keys, no spaces, ASCII only (so a lone surrogate or a line separator can
    never be in the file)."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def _generic(body, kind, rules):
    """The generic shape check: text, within the byte limit (before parsing), JSON, an object or a list, plain text inside,
    whole numbers only. Returns the rebuilt value."""
    if not isinstance(body, str):
        raise Bad(NOT_TEXT)
    limit = LIMITS.get(kind, DEFAULT_LIMIT)
    if len(body) > limit:
        raise Bad(TOO_BIG)               # a character takes at least one byte: over the limit already, nothing is parsed
    try:
        size = len(body.encode("utf-8"))
    except UnicodeEncodeError:
        raise Bad(BAD_TEXT) from None    # a lone surrogate can't be saved
    if size > limit:
        raise Bad(TOO_BIG)
    try:
        value = json.loads(body, parse_constant=_refuse_constant, parse_float=_refuse_float, parse_int=_whole_number,
                           object_pairs_hook=_no_repeats)
    except Bad:
        raise
    except RecursionError:
        raise Bad(TOO_DEEP) from None
    except ValueError:
        raise Bad(NOT_READABLE) from None
    if type(value) not in (dict, list):
        raise Bad(NOT_TEXT)
    try:
        return _rebuilt(value, rules, 1)
    except RecursionError:
        raise Bad(TOO_DEEP) from None


def _checked_needs(value, rules):
    """The 'Needs from you' content's own shape. STUB: #121 fills this (rows of what is needed, from whom, by when; limits;
    a real date; hidden rows). Until then it accepts what passed the generic check."""
    return value


def _checked_tracker(value, rules):
    """The 'Progress tracker' content's own shape. STUB: #189 fills this (groups of lines with whole-tenth numbers; limits;
    the reading of the numbers is #189's open question). Until then it accepts what passed the generic check."""
    return value


CHECKERS = {NEEDS: _checked_needs, TRACKER: _checked_tracker, **{t: m.check for t, m in TEMPLATES.items()}}
EMPTY = {NEEDS: "", TRACKER: "", **{t: m.EMPTY for t, m in TEMPLATES.items()}}   # a new section starts with no content at all; an item may give a richer start


def check(kind, body, rules):
    """The content of a `kind` section as it is stored: the canonical text, or Bad. An empty text is no content (stored as
    ''). A kind with no checker has no content, so any body is refused."""
    checker = CHECKERS.get(kind)
    if checker is None:
        raise Bad(NOT_SAVED_YET)
    if body is None or body == "":
        return ""
    value = checker(_generic(body, kind, rules), rules)
    if type(value) not in (dict, list):
        raise Bad(NOT_READABLE)          # a checker that hands back something else is a fault, never stored
    text = canonical(value)
    if len(text.encode("ascii")) > LIMITS.get(kind, DEFAULT_LIMIT):
        raise Bad(TOO_BIG)
    return text


def published(kind, value, ctx=None):
    """What the published file carries of a checked body, as a dict merged into the section's entry; None leaves the section
    out ('an empty template stays out'). A section template answers for itself (its module's published, given `ctx`, what
    publish already kept: a Context); a stub answers None, so it is never in a file. BASE, for needs and tracker: nothing of
    the content is published, so the section keeps its place and title only. #121 and #189 each add their own table here:
    fields picked by name from the checked value, hidden rows left out."""
    if kind in TEMPLATES:
        out = TEMPLATES[kind].published(value, ctx if ctx is not None else Context())
        return out if isinstance(out, dict) and out else None
    return {}
