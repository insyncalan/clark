"""Work items list (F10 and H9, #96): the content of a section of type 'workitems'.

The section holds a saved filter, never rows: which work items to list (kinds, open or closed, status, due, owner, workstream,
use case, priority), how to sort them, how many at most, which columns to show at full width, and an optional caption. The rows
are live: they are chosen again from the project's records each time the page is drawn or published.

Stored (canonical JSON, every key present once checked):
  {"v": 1, "kinds": [..], "mode": "open"|"closed"|"all", "status": [..], "due": [..], "owner": [..], "workstream": [..],
   "use_case": [..], "priority": [..], "sort": "due"|"priority"|"id", "max": 1..50, "columns": [..], "caption": ".."}
An empty list is "any". "(none)" in owner, workstream, use_case or priority matches a row that has none. There is no
"client visible" choice: a row that is not client visible never publishes (D-3), so it could only ever give an empty list.

Published: {"items": [ids, in order], "columns": [..], "caption": ".."}; the ids are chosen from ctx only (what publish.select
already kept), so an archived, client-hidden, eye-hidden or Sensitive item can never be in the list. With no item left the
section is left out of the file (an empty match says so in Edit only). The filter itself is never published.

The filter and the sort are the same rules as the page's (page/src/templates/workItemsList.js); tests/test_tpl_workitems.py
runs the two over the same rows. Pure, and (as every template module) it imports nothing but the contract.
"""
from clark.section_kinds.base import Bad

READY = True
LIMIT = 8192
EMPTY = ""

VERSION = 1
KINDS = ("action", "risk", "issue", "assumption", "dependency", "decision")
MODES = ("open", "closed", "all")
STATUSES = ("Open", "Delayed", "Pending", "Closed", "Cancelled", "Made", "Withdrawn")
DUE = ("overdue", "soon", "none", "later")
NONE = "(none)"
PRIORITIES = ("Urgent", "High", "Medium", "Low")
SORTS = ("due", "priority", "id")
COLUMNS = ("type", "id", "owner", "due", "status", "workstream")      # the title is always shown
DEFAULT_COLUMNS = ("type", "id", "owner", "due", "status")
MAX_ROWS = 50
DEFAULT_MAX = 10
MAX_VALUES = 30                     # names in one filter
MAX_TEXT = 120                      # characters in one owner or workstream name
MAX_CAPTION = 200
CLOSED = ("Closed", "Cancelled", "Made", "Withdrawn")
KEYS = ("v", "kinds", "mode", "status", "due", "owner", "workstream", "use_case", "priority", "sort", "max", "columns", "caption")
FILTERS = ("kinds", "status", "due", "owner", "workstream", "use_case", "priority")

NOT_A_FILTER = "That list's filter could not be read. Choose its filter again."
UNKNOWN_FIELD = "That list's filter has a choice it doesn't know. Choose its filter again."
BAD_CHOICE = "That list's filter has a value it can't use. Choose from the values offered."
TOO_MANY = f"A filter can hold at most {MAX_VALUES} values. Remove some first."
BAD_MAX = f"Show between 1 and {MAX_ROWS} work items."
NO_COLUMNS = "Choose at least one column to show."
LONG_CAPTION = f"The caption can be at most {MAX_CAPTION} characters. Shorten it and save again."
LONG_NAME = f"A name in the filter can be at most {MAX_TEXT} characters. Choose from the values offered."


def _choices(value, allowed):
    """A list of distinct values, each one of `allowed`, kept in `allowed`'s order."""
    if not isinstance(value, list):
        raise Bad(BAD_CHOICE)
    if any(not isinstance(v, str) or v not in allowed for v in value):
        raise Bad(BAD_CHOICE)
    return [a for a in allowed if a in value]


def _use_case_id(v):
    """CODE-U-NNN: a project code (3 to 7 capitals or digits, a capital first), -U-, 3 to 6 digits."""
    parts = v.split("-")
    if len(parts) != 3 or parts[1] != "U":
        return False
    code, num = parts[0], parts[2]
    return (3 <= len(code) <= 7 and "A" <= code[0] <= "Z" and all("A" <= c <= "Z" or "0" <= c <= "9" for c in code)
            and 3 <= len(num) <= 6 and all("0" <= c <= "9" for c in num))


def _names(value, rules, ids=False):
    """A list of distinct plain names (or "(none)"), in the order given, spaces tidied."""
    if not isinstance(value, list):
        raise Bad(BAD_CHOICE)
    if len(value) > MAX_VALUES:
        raise Bad(TOO_MANY)
    out = []
    for v in value:
        if not isinstance(v, str):
            raise Bad(BAD_CHOICE)
        v = " ".join(v.split())
        if not v or not rules.visible(v):
            raise Bad(BAD_CHOICE)
        if len(v) > MAX_TEXT:
            raise Bad(LONG_NAME)
        if ids and v != NONE and not _use_case_id(v):
            raise Bad(BAD_CHOICE)
        if v not in out:
            out.append(v)
    return out


def check(value, rules):
    """The saved filter rebuilt field by field, with every key present; Bad in plain words otherwise."""
    if type(value) is not dict:
        raise Bad(NOT_A_FILTER)
    if any(k not in KEYS for k in value):
        raise Bad(UNKNOWN_FIELD)
    if value.get("v", VERSION) != VERSION or type(value.get("v", VERSION)) is not int:
        raise Bad(NOT_A_FILTER)
    mode, sort = value.get("mode", "open"), value.get("sort", "due")
    if not isinstance(mode, str) or mode not in MODES or not isinstance(sort, str) or sort not in SORTS:
        raise Bad(BAD_CHOICE)
    most = value.get("max", DEFAULT_MAX)
    if type(most) is not int or not 1 <= most <= MAX_ROWS:
        raise Bad(BAD_MAX)
    columns = _choices(value.get("columns", list(DEFAULT_COLUMNS)), COLUMNS)
    if not columns:
        raise Bad(NO_COLUMNS)
    caption = value.get("caption", "")
    if not isinstance(caption, str):
        raise Bad(BAD_CHOICE)
    caption = " ".join(caption.split())
    if len(caption) > MAX_CAPTION:
        raise Bad(LONG_CAPTION)
    if caption and not rules.visible(caption):
        raise Bad(BAD_CHOICE)
    return {
        "v": VERSION,
        "kinds": _choices(value.get("kinds", []), KINDS),
        "mode": mode,
        "status": _choices(value.get("status", []), STATUSES),
        "due": _choices(value.get("due", []), DUE),
        "owner": _names(value.get("owner", []), rules),
        "workstream": _names(value.get("workstream", []), rules),
        "use_case": _names(value.get("use_case", []), rules, ids=True),
        "priority": _choices(value.get("priority", []), PRIORITIES + (NONE,)),
        "sort": sort,
        "max": most,
        "columns": columns,
        "caption": caption,
    }


# ===== The live rows: the same rules as the page's (templates/workItemsList.js) =====

def day_number(iso):
    """A day number for a real YYYY-MM-DD day (days from 1970-01-01, as the page's dayNumber), None for anything else."""
    if not isinstance(iso, str) or len(iso) != 10 or iso[4] != "-" or iso[7] != "-":
        return None
    digits = iso[:4] + iso[5:7] + iso[8:]
    if not all("0" <= c <= "9" for c in digits):
        return None
    y, m, d = int(iso[:4]), int(iso[5:7]), int(iso[8:])
    leap = y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)
    days_in = (31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
    if not 1 <= m <= 12 or not 1 <= d <= days_in[m - 1]:
        return None
    yy = y - (1 if m <= 2 else 0)                       # days from civil (H. Hinnant), 1970-01-01 is 0
    era = (yy if yy >= 0 else yy - 399) // 400
    yoe = yy - era * 400
    doy = (153 * (m + (-3 if m > 2 else 9)) + 2) // 5 + d - 1
    doe = yoe * 365 + yoe // 4 - yoe // 100 + doy
    return era * 146097 + doe - 719468


def rows_of(rows):
    """One flat list from the kept rows (ctx.rows): actions, then RAID (its type, lower case, is the kind), then decisions."""
    out = []
    for r in rows.get("actions") or ():
        out.append({"id": r.get("id"), "kind": "action", "status": r.get("status"), "owner": r.get("owner"),
                    "workstream": r.get("workstream"), "use_case": r.get("use_case"), "priority": r.get("priority"),
                    "due": r.get("due_date")})
    for r in rows.get("raid") or ():
        out.append({"id": r.get("id"), "kind": str(r.get("type") or "").lower(), "status": r.get("status"), "owner": r.get("owner"),
                    "workstream": r.get("workstream"), "use_case": r.get("use_case"), "priority": r.get("priority"),
                    "due": r.get("due_date")})
    for r in rows.get("decisions") or ():
        out.append({"id": r.get("id"), "kind": "decision", "status": r.get("status"), "owner": r.get("made_by"),
                    "workstream": None, "use_case": r.get("use_case"), "priority": None,
                    "due": r.get("needed_by") if r.get("status") == "Pending" else r.get("date")})
    return out


def _open(row):
    return row.get("status") not in CLOSED


def _bucket(row, today):
    a, t = day_number(row.get("due")), day_number(today)
    if a is None or t is None:
        return "none"
    if not _open(row):
        return ""
    return "overdue" if a < t else "soon" if a - t <= 7 else "later"


def _text(v):
    return " ".join(v.split()) if isinstance(v, str) else ""


def _member(row, field, chosen, today):
    if not chosen:
        return True
    if field == "kinds":
        return row["kind"] in chosen
    if field == "status":
        return row.get("status") in chosen
    if field == "due":
        return _bucket(row, today) in chosen
    return (_text(row.get(field)) or NONE) in chosen


def _due_key(row):
    return (0, row["due"]) if day_number(row.get("due")) is not None else (1, "")


def matching(value, rows, today):
    """The ids of `rows` (rows_of's shape) that the checked filter `value` lists, sorted and cut to its max."""
    hits = [r for r in rows if isinstance(r.get("id"), str) and r["id"]
            and (value["mode"] == "all" or (value["mode"] == "open") == _open(r))
            and all(_member(r, f, value[f], today) for f in FILTERS)]
    rank = {p: i for i, p in enumerate(PRIORITIES)}
    if value["sort"] == "id":
        hits.sort(key=lambda r: r["id"])
    elif value["sort"] == "priority":
        hits.sort(key=lambda r: (not _open(r), rank.get(r.get("priority"), len(PRIORITIES)), _due_key(r), r["id"]))
    else:
        hits.sort(key=lambda r: (not _open(r), _due_key(r), r["id"]))
    return [r["id"] for r in hits[:value["max"]]]


def published(value, ctx):
    """The ordered ids the filter keeps from what publish already kept, the columns and the caption; None when nothing matches."""
    if type(value) is not dict or set(value) != set(KEYS):
        return None
    kept = ctx.ids.get("actions", frozenset()) | ctx.ids.get("raid", frozenset()) | ctx.ids.get("decisions", frozenset())
    items = [i for i in matching(value, rows_of(ctx.rows), ctx.as_at) if i in kept]
    if not items:
        return None
    return {"items": items, "columns": list(value["columns"]), "caption": value["caption"]}
