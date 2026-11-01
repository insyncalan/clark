"""Key figures, four (#96, F3): the content of a section of type 'figures4': 4 places, each a typed figure or a live one
(the same figures as the At a glance tiles). The shared rules below also serve figures3 (Key figures, three).

Pure: no file, no database; it imports nothing from clark at load time (the publish path imports the registry), and reaches glance
only inside published(), when publish has already loaded it.

Stored body, one object: {"v": 1, "figures": [slot, ...]}, at most as many slots as the template has places (4 or 3).
A slot is {"mode": "typed", "label", "value", "detail", "asof"} (plain text; asof a real day YYYY-MM-DD or "") or
{"mode": "live", "metric": "overdue" | "risks" | "decisions"}: the same three figures as the At a glance tiles, counted by
glance.py (the reference) from the rows publish kept, so a hidden, archived, not client-visible or Sensitive item is never
counted. A typed slot is published only with both a label and a value; with neither it is empty, with one it waits (saved, left out).

The file carries, per figure, only: mode, label, value, detail, rag (g a r n) and, for a typed one, asof. A live figure is worked
out at publish time as at the report's day; it is left out when the project has no row of its kind to count (a hidden section or
none at all), so a count of nothing the page can show is never printed.
"""
from clark.section_kinds.base import Bad

LIMIT = 8192
EMPTY = ""
VERSION = 1
METRICS = ("overdue", "risks", "decisions")
KIND_OF_METRIC = {"overdue": "actions", "risks": "raid", "decisions": "decisions"}
LABEL_MAX, VALUE_MAX, DETAIL_MAX = 60, 30, 80

TOO_MANY = "That template has fewer places than that. Remove a figure and try again."
BAD_SHAPE = "The figures could not be read. Check them and try again."
BAD_MODE = "A figure is typed or live. Choose one."
BAD_METRIC = "A live figure is Overdue actions, High risks and issues or Decisions needed. Choose one."
BAD_DAY = "The date must be a real day, written as DD-MM-YYYY."
TOO_LONG = "A figure's label, number or note is too long."


def real_day(text):
    """A real calendar day written YYYY-MM-DD (no imports here: the registry's modules import only from clark.section_kinds)."""
    if not isinstance(text, str) or len(text) != 10 or text[4] != "-" or text[7] != "-":
        return False
    y, m, d = text[0:4], text[5:7], text[8:10]
    if not all(c in "0123456789" for c in y + m + d):
        return False
    y, m, d = int(y), int(m), int(d)
    leap = y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)
    days = (31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
    return y >= 1 and 1 <= m <= 12 and 1 <= d <= days[m - 1]


def _text(slot, field, limit, rules):
    got = slot.get(field, "")
    if got is None:
        got = ""
    if type(got) is int:
        got = str(got)                    # a typed number may arrive as a number: stored as the text a person typed
    if not isinstance(got, str):
        raise Bad(BAD_SHAPE)
    got = got.strip()
    if len(got) > limit:
        raise Bad(TOO_LONG)
    if got and not rules.visible(got):
        raise Bad(BAD_SHAPE)
    return got


def checker(places):
    def check(value, rules):
        if type(value) is not dict or value.get("v") != VERSION or set(value) - {"v", "figures"}:
            raise Bad(BAD_SHAPE)
        slots = value.get("figures", [])
        if type(slots) is not list:
            raise Bad(BAD_SHAPE)
        if len(slots) > places:
            raise Bad(TOO_MANY)
        out = []
        for slot in slots:
            if type(slot) is not dict:
                raise Bad(BAD_SHAPE)
            mode = slot.get("mode")
            if mode == "live":
                if set(slot) - {"mode", "metric"}:
                    raise Bad(BAD_SHAPE)
                if slot.get("metric") not in METRICS:
                    raise Bad(BAD_METRIC)
                out.append({"mode": "live", "metric": slot["metric"]})
            elif mode == "typed":
                if set(slot) - {"mode", "label", "value", "detail", "asof"}:
                    raise Bad(BAD_SHAPE)
                one = {"mode": "typed", "label": _text(slot, "label", LABEL_MAX, rules),
                       "value": _text(slot, "value", VALUE_MAX, rules), "detail": _text(slot, "detail", DETAIL_MAX, rules),
                       "asof": _text(slot, "asof", 10, rules)}
                if one["asof"] and not real_day(one["asof"]):
                    raise Bad(BAD_DAY)
                out.append(one)
            else:
                raise Bad(BAD_MODE)
        return {"v": VERSION, "figures": out}
    return check


def _live(ctx):
    """The live figures by metric, from what publish kept: {metric: (title, value, detail, letter)}."""
    if not real_day(ctx.as_at):
        return {}
    glance = __import__("clark.glance", fromlist=["tiles"])      # at call time: publish has loaded it; a load-time import would loop
    rows = {t: ctx.rows.get(t) or [] for t in ("actions", "raid", "decisions")}
    kept = {"rows": glance.work_rows(rows), "hidden_types": set()}
    shown = glance.tiles({"project": {}}, ctx.as_at, hidden=set(), for_client=True, kept=kept)
    return {t["tile"]: (t["title"], t["value"], t["detail"], t["class"]) for t in shown
            if t["tile"] in METRICS and rows[KIND_OF_METRIC[t["tile"]]]}


def publisher(places):
    def published(value, ctx):
        live = None
        out = []
        for slot in (value.get("figures") if isinstance(value, dict) else None) or []:
            if len(out) >= places:
                break
            if slot.get("mode") == "live":
                live = _live(ctx) if live is None else live
                got = live.get(slot.get("metric"))
                if got:
                    out.append({"mode": "live", "label": got[0], "value": got[1], "detail": got[2], "rag": got[3], "asof": ""})
            elif slot.get("mode") == "typed" and slot.get("label") and slot.get("value"):
                out.append({"mode": "typed", "label": slot["label"], "value": slot["value"], "detail": slot.get("detail") or "",
                            "rag": "n", "asof": slot.get("asof") or ""})
        return {"figures": out} if out else None
    return published


READY = True
PLACES = 4
check = checker(PLACES)
published = publisher(PLACES)
