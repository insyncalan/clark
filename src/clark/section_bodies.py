"""A section that carries content: the checker registry (the shared base for 'Needs from you' and 'Progress tracker').

A section of type `needs` or `tracker` keeps its content as JSON text in the section's `body` column. This module is pure (it
reads no file and no database, and imports nothing from clark): store.py calls it from the section rules, so every write of a
body, including an Undo that puts one back, passes through the same walls; publish.py calls it again at publish time.

What this base decides, and nothing more:
- the content is one JSON object or one JSON list, no longer than the type's byte limit (checked before it is parsed);
- every key and every text value is plain text (the store's own text rules: nothing a person can't see, no line breaks, no
  right-to-left override, no lone surrogate); markup is never read as markup, it is only text;
- no number with a fraction, no NaN or Infinity, no very long number, no repeated key, nothing nested deeper than MAX_DEPTH;
- what is stored is the CANONICAL text (sorted keys, no spaces, ASCII escapes), rebuilt from what was parsed, never the
  request's own text. The same content therefore always makes the same text, and saving it again changes nothing.

What the base does NOT decide: the content's own shape. That is each item's job, in its checker:
- #121 (needs) fills `_checked_needs` (below: rows of what is needed, what kind, who from, by when); #189 (tracker) fills
  `_checked_tracker`, still a stub here: it accepts whatever passed the generic check above. #189's open question (is a line's number 0 to 100, or a share of the whole, and is the overall
  figure the sum of the group totals) is NOT decided here.

The plug-in points (a later item changes only these, never store.py, changes.py or history.py):
- CHECKERS[type](value, rules) -> value: given the parsed content (already through the generic check), return the content
  rebuilt field by field, or raise Bad in plain words that never quote the value. `rules` offers rules.plain(text) and
  rules.visible(text), the store's text rules (see Rules).
- EMPTY[type]: the body a new section of that type starts with. Chosen by the store, never taken from the request.
- LIMITS[type]: the most bytes the stored text may take.
- published(type, value): what a published file carries of a checked body (a dict that is merged into the section's entry), or
  None to leave the section out. Needs publishes its shown rows; the tracker publishes nothing of its content yet (see published).
"""
import json
import unicodedata

NEEDS, TRACKER = "needs", "tracker"
BODY_TYPES = (NEEDS, TRACKER)            # the section types (besides text) that carry content
MAX_DEPTH = 8                            # lists and objects inside each other, at most
MAX_DIGITS = 15                          # a whole number of more digits is refused before Python reads it (slow on 3.9)
DEFAULT_LIMIT = 262144                   # bytes of stored text, unless LIMITS says less
LIMITS = {NEEDS: 262144, TRACKER: 262144}      # needs: 100 rows of the longest text, each character written as six ASCII bytes, still fits


class Bad(ValueError):
    """The content can't be saved. The message is plain words for a person and never quotes the value."""


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


# ── 'Needs from you' (#121) ───────────────────────────────────────────────────
# The content is one object: {"v": 1, "rows": [row, ...]}, a row being {"what", "kind", "from", "by", "hidden"}. The list's order is
# the order shown; a row has no id. `kind` says what is needed. `by` is empty or a real day, stored YYYY-MM-DD.
NEEDS_VERSION = 1
NEEDS_KINDS = ("decision", "information", "date")
NEEDS_MAX_ROWS = 100
NEEDS_WHAT_MAX = 300
NEEDS_FROM_MAX = 100
NEEDS_YEARS = (2000, 2100)               # the first and last year a "by" date may name
NEEDS_ROW_KEYS = ("what", "kind", "from", "by", "hidden")

NEEDS_SHAPE = "Needs from you holds a list of rows."
NEEDS_TOO_MANY = f"Needs from you can have at most {NEEDS_MAX_ROWS} rows."
NEEDS_ROW_SHAPE = "A row holds what is needed, what kind it is, who it is from, the date it is needed by, and whether it is left out."
NEEDS_WHAT_MISSING = "Say what is needed."
NEEDS_WHAT_LONG = f"What is needed can be {NEEDS_WHAT_MAX} characters at most."
NEEDS_KIND = "Choose whether it is a decision, information or a date."
NEEDS_FROM_LONG = f"From can be {NEEDS_FROM_MAX} characters at most."
NEEDS_FROM_BAD = "From must be a name or a team, or empty."
NEEDS_BY = f"By must be a real day between {NEEDS_YEARS[0]} and {NEEDS_YEARS[1]}, or empty."
NEEDS_HIDDEN = "A row is either shown or left out."


def _real_day(text):
    """`text` when it is a real calendar day written YYYY-MM-DD (years NEEDS_YEARS), else None. Never a time zone, never a clock."""
    if not (isinstance(text, str) and len(text) == 10 and text[4] == "-" and text[7] == "-"
            and text[:4].isascii() and text[5:7].isascii() and text[8:].isascii()
            and text[:4].isdigit() and text[5:7].isdigit() and text[8:].isdigit()):
        return None
    year, month, day = int(text[:4]), int(text[5:7]), int(text[8:])
    if not NEEDS_YEARS[0] <= year <= NEEDS_YEARS[1] or not 1 <= month <= 12:
        return None
    leap = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
    last = (31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)[month - 1]
    return text if 1 <= day <= last else None


def _checked_needs_row(row, rules):
    """One row rebuilt field by field, or Bad. Text is trimmed; `from` and `by` may be empty; `hidden` is 0 or 1 (a row with none
    is shown). Nothing the row names is kept that this does not know."""
    if type(row) is not dict or set(row) - set(NEEDS_ROW_KEYS) or not {"what", "kind"} <= set(row):
        raise Bad(NEEDS_ROW_SHAPE)
    what, kind, who = row["what"], row["kind"], row.get("from", "")
    by, hidden = row.get("by", ""), row.get("hidden", 0)
    if not isinstance(what, str):
        raise Bad(NEEDS_WHAT_MISSING)
    what = what.strip()
    if not what or not rules.visible(what):
        raise Bad(NEEDS_WHAT_MISSING)
    if len(what) > NEEDS_WHAT_MAX:
        raise Bad(NEEDS_WHAT_LONG)
    if not isinstance(kind, str) or kind not in NEEDS_KINDS:
        raise Bad(NEEDS_KIND)
    if not isinstance(who, str):
        raise Bad(NEEDS_FROM_BAD)
    who = who.strip()
    if who and not rules.visible(who):
        raise Bad(NEEDS_FROM_BAD)
    if len(who) > NEEDS_FROM_MAX:
        raise Bad(NEEDS_FROM_LONG)
    if by is None:
        by = ""
    if by != "" and _real_day(by) is None:
        raise Bad(NEEDS_BY)
    if type(hidden) is not int or hidden not in (0, 1):
        raise Bad(NEEDS_HIDDEN)
    return {"what": what, "kind": kind, "from": who, "by": by, "hidden": hidden}


def _checked_needs(value, rules):
    """The 'Needs from you' content's own shape: {"v": 1, "rows": [...]} with at most NEEDS_MAX_ROWS rows, each rebuilt by
    _checked_needs_row. Any other key, another version, or a list in place of the object is refused in plain words."""
    if type(value) is not dict or set(value) - {"v", "rows"} or "rows" not in value:
        raise Bad(NEEDS_SHAPE)
    if "v" in value and (type(value["v"]) is not int or value["v"] != NEEDS_VERSION):
        raise Bad(NEEDS_SHAPE)
    rows = value["rows"]
    if type(rows) is not list:
        raise Bad(NEEDS_SHAPE)
    if len(rows) > NEEDS_MAX_ROWS:
        raise Bad(NEEDS_TOO_MANY)
    return {"v": NEEDS_VERSION, "rows": [_checked_needs_row(r, rules) for r in rows]}


def _shown_needs_row(row):
    """A published row: {"what", "kind", "from", "by"} with `by` written DD-MM-YYYY, or None when the row is hidden or does not
    have the checked shape (published never trusts what it is given more than it must; nothing is copied that is not named here)."""
    if type(row) is not dict or type(row.get("hidden")) is not int or row["hidden"] != 0:
        return None
    what, kind, who, by = row.get("what"), row.get("kind"), row.get("from"), row.get("by")
    if not (isinstance(what, str) and what and isinstance(who, str) and isinstance(by, str) and kind in NEEDS_KINDS):
        return None
    if by != "" and _real_day(by) is None:
        return None
    return {"what": what, "kind": kind, "from": who, "by": f"{by[8:]}-{by[5:7]}-{by[:4]}" if by else ""}


def _checked_tracker(value, rules):
    """The 'Progress tracker' content's own shape. STUB: #189 fills this (groups of lines with whole-tenth numbers; limits;
    the reading of the numbers is #189's open question). Until then it accepts what passed the generic check."""
    return value


CHECKERS = {NEEDS: _checked_needs, TRACKER: _checked_tracker}
EMPTY = {NEEDS: "", TRACKER: ""}         # a new section starts with no content at all (for needs that is the same as an empty list: nothing shows, nothing is published)


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


def published(kind, value):
    """What the published file carries of a checked body, as a dict merged into the section's entry; None leaves the section
    out ('an empty template stays out').
    needs (#121): {"rows": [{"what", "kind", "from", "by"}]}, the rows that show (a hidden row is absent, not marked), `by` written
    DD-MM-YYYY; None when no row shows. Fields are picked by name, never copied whole, and text only.
    tracker: nothing of the content is published yet, so the section keeps its place and title only (#189 adds its table)."""
    if kind == NEEDS:
        rows = [r for r in (_shown_needs_row(r) for r in (value.get("rows") if type(value) is dict and type(value.get("rows")) is list else [])) if r]
        return {"rows": rows} if rows else None
    return {}
