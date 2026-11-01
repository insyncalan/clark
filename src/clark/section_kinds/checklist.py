"""Checklist (H5, #96): the content of a section of type 'checklist', a short list of lines, each one typed (words and a ticked
box) or linked to a work item by its id (its words and whether it is done are read live from the work item).

Stored: {"v": 1, "items": [{"text": "Send the plan", "done": 0 | 1} | {"item": "ABC-A-001"}, ...]}, at most MAX_ITEMS.
A linked line is a reference by id only, never a copy of the work item's words. Published: the same shape, but only the typed
lines and the linked lines whose work item the file keeps (an action, a RAID item or a decision that is not hidden or archived,
client visible, with no label that keeps it out); nothing left means the section stays out of the file.
"""
from clark.section_kinds.base import Bad

READY = True
LIMIT = 49152    # twenty lines of 200 characters, each stored as ASCII escapes (an emoji takes twelve bytes)
EMPTY = ""
MAX_ITEMS = 20
TEXT_MAX = 200
ALNUM = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
KINDS = ("actions", "raid", "decisions")

NOT_LIST = "A checklist must be a short list of lines. Check it and try again."
TOO_MANY = f"A checklist can hold {MAX_ITEMS} lines at most. Remove one and try again."
BAD_TEXT = f"A line must be 1 to {TEXT_MAX} characters of plain text. Check it and try again."
BAD_TICK = "A line is either ticked or not. Check it and try again."
BAD_ITEM = "A work item must be named by its ID. Choose it from the list and try again."
TWICE = "A work item can be in a checklist once. Remove the repeat and try again."


def _work_item_id(text):
    """ABC-A-001 (an action), ABC-D-001 (a decision) or ABC-001 (a RAID item): a project code (3 to 7 capitals or digits, a capital
    first), an optional A- or D-, then 3 to 6 digits. By hand: this folder imports nothing outside the registry."""
    parts = text.split("-")
    if len(parts) not in (2, 3) or (len(parts) == 3 and parts[1] not in ("A", "D")):
        return False
    code, num = parts[0], parts[-1]
    return (3 <= len(code) <= 7 and code[0] in ALNUM[:26] and all(c in ALNUM for c in code)
            and 3 <= len(num) <= 6 and num.isascii() and num.isdigit())


def _line(line, rules, seen):
    if type(line) is not dict:
        raise Bad(NOT_LIST)
    if set(line) == {"item"}:
        wid = line["item"]
        if not isinstance(wid, str) or not _work_item_id(wid):
            raise Bad(BAD_ITEM)
        if wid in seen:
            raise Bad(TWICE)
        seen.add(wid)
        return {"item": wid}
    if set(line) == {"text", "done"}:
        text, done = line["text"], line["done"]
        if not isinstance(text, str) or text != text.strip() or not 1 <= len(text) <= TEXT_MAX or not rules.visible(text):
            raise Bad(BAD_TEXT)
        if type(done) is not int or done not in (0, 1):
            raise Bad(BAD_TICK)
        return {"text": text, "done": done}
    raise Bad(NOT_LIST)


def check(value, rules):
    if type(value) is not dict or set(value) != {"v", "items"} or value["v"] != 1 or type(value["v"]) is bool:
        raise Bad(NOT_LIST)
    items = value["items"]
    if type(items) is not list:
        raise Bad(NOT_LIST)
    if len(items) > MAX_ITEMS:
        raise Bad(TOO_MANY)
    seen = set()
    return {"v": 1, "items": [_line(i, rules, seen) for i in items]}


def published(value, ctx):
    live = set().union(*(ctx.ids.get(k, frozenset()) for k in KINDS))
    items = [i for i in value.get("items", ()) if "text" in i or i["item"] in live]
    return {"v": 1, "items": items} if items else None
