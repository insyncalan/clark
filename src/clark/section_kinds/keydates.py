"""Key dates (H6, #96): the content of a section of type 'keydates', a short list of dates, each one either a milestone taken by
its id (what it is called, its date and its state are read live from the milestone) or typed (a label and a day).

Stored: {"v": 1, "items": [{"milestone": "ABC-M-001"} | {"label": "Go live", "date": "2030-02-01"}, ...]}, at most MAX_ITEMS.
A milestone is a reference by id only, never a copy of its name. Published: the same shape, but only the milestones the file keeps
(not hidden, not archived, not cancelled, and only while the Milestones section is in the file) and every typed date; nothing left
means the section stays out of the file.
"""
from clark.section_kinds.base import Bad

READY = True
LIMIT = 24576    # twelve labels of 120 characters, each stored as ASCII escapes (an emoji takes twelve bytes)
EMPTY = ""
MAX_ITEMS = 12
LABEL_MAX = 120
ALNUM = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"

NOT_DATES = "Key dates must be a short list of dates. Check it and try again."
TOO_MANY = f"Key dates can hold {MAX_ITEMS} dates at most. Remove one and try again."
BAD_LABEL = f"A date's label must be 1 to {LABEL_MAX} characters of plain text. Check it and try again."
BAD_DAY = "A date must be a real day. Check it and try again."
BAD_MILESTONE = "A milestone must be named by its ID. Choose it from the list and try again."
TWICE = "A milestone can be in Key dates once. Remove the repeat and try again."


def _milestone_id(text):
    """ABC-M-001: a project code (3 to 7 capitals or digits, a capital first), -M-, then 3 to 6 digits. By hand: this folder imports
    nothing outside the registry."""
    code, mid, num = text.partition("-M-")
    return (mid == "-M-" and 3 <= len(code) <= 7 and code[0] in ALNUM[:26] and all(c in ALNUM for c in code)
            and 3 <= len(num) <= 6 and num.isascii() and num.isdigit())


def _real_day(text):
    """YYYY-MM-DD, a day that is on the calendar (year 1 to 9999)."""
    if len(text) != 10 or text[4] != "-" or text[7] != "-":
        return False
    y, m, d = text[:4], text[5:7], text[8:]
    if not all(p.isascii() and p.isdigit() for p in (y, m, d)):
        return False
    y, m, d = int(y), int(m), int(d)
    leap = y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)
    last = (31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)[m - 1] if 1 <= m <= 12 else 0
    return y >= 1 and 1 <= d <= last


def _item(item, rules, seen):
    if type(item) is not dict:
        raise Bad(NOT_DATES)
    if set(item) == {"milestone"}:
        mid = item["milestone"]
        if not isinstance(mid, str) or not _milestone_id(mid):
            raise Bad(BAD_MILESTONE)
        if mid in seen:
            raise Bad(TWICE)
        seen.add(mid)
        return {"milestone": mid}
    if set(item) == {"label", "date"}:
        label, day = item["label"], item["date"]
        if not isinstance(label, str) or label != label.strip() or not 1 <= len(label) <= LABEL_MAX or not rules.visible(label):
            raise Bad(BAD_LABEL)
        if not isinstance(day, str) or not _real_day(day):
            raise Bad(BAD_DAY)
        return {"label": label, "date": day}
    raise Bad(NOT_DATES)


def check(value, rules):
    if type(value) is not dict or set(value) != {"v", "items"} or value["v"] != 1 or type(value["v"]) is bool:
        raise Bad(NOT_DATES)
    items = value["items"]
    if type(items) is not list:
        raise Bad(NOT_DATES)
    if len(items) > MAX_ITEMS:
        raise Bad(TOO_MANY)
    seen = set()
    return {"v": 1, "items": [_item(i, rules, seen) for i in items]}


def published(value, ctx):
    live = {r["id"] for r in ctx.rows.get("milestones", ()) if r.get("status") != "Cancelled"}
    items = [i for i in value.get("items", ()) if "label" in i or i["milestone"] in live]
    return {"v": 1, "items": items} if items else None
