"""The client page's Work items filters: the pure model (#69; BRD FR-90a, after the editor's filters, FR-41).

No page, no server, no database and no clock: every function takes the published rows and "today" (YYYY-MM-DD) and gives back
plain dicts and lists, so the same answer comes out every time and a test can fix the date. Standard library only, Python 3.9.

This is the REFERENCE MODEL. The published file is static and has no server, so the page runs the same rules in JavaScript over
the rows in its own data block; the JavaScript contract is written out in the section "The page's contract" below, and the page
part (#69's second half, after #64 and #39) must give the same answers on tests/fixtures/client-filter-cases.json.

Published rows only
- Everything here is worked out from `publish.select`'s output (the "data" of the published file) and nothing else. `rows_of`
  takes that data, `client_rows` takes the editor's tables and runs `glance.kept_rows` (which runs `publish.select`) first. There
  is no second filter that decides what a client may see: a row that was not client_visible, was left off the page, carries a
  Sensitive label (or any label set to exclude), is archived or belongs to a hidden section is not in `publish.select`'s output
  and so is in no count, no option list, no chip and no group. `rows_of` also refuses, as a second lock that cannot loosen the
  first, any row that still carries `client_visible` off or `archived` on, and it copies a whitelist of fields only.
- No Client filter and no eye: everything on the page is already the client's.
- Option lists hold only values that some published row has, so a filter can never name something the client may not see.

The model
- A row: {id, kind (action, risk, issue, assumption, dependency, decision), type ("A", "R", "D"), title, owner, workstream,
  status, priority, due (the due date, or for a decision the needed-by date while Pending and otherwise the date it was made),
  bucket, use_case, milestone, latest_update}. A missing owner, workstream, use case or milestone reads "(none)" in a filter.
- A state: {type: "all"|"A"|"R"|"D", show: "open"|"closed"|"all", f: {dimension: [values]}, not: {dimension: bool},
  q: search text, group: a key of GROUPS}. Dimensions (FILTER_DIMENSIONS): ws, status, due, owner, priority, uc, ms. Open means
  not Closed, Cancelled, Made or Withdrawn (so Delayed and Pending are open). A dimension with values is active; with `not` on
  it keeps the rows that do NOT have one of the values. Several values in one dimension are "any of"; dimensions are "all of".
- Due buckets: Overdue (open and before today), Due in 7 days (today to 7 days ahead), Later, No date, and Earlier (a closed row
  dated before today: a finished item is never "overdue"; the editor's own list would call it overdue, a departure noted here).
- `apply_state` gives one answer: the rows that match, the counts (type and Open/Closed/All, each worked out with every other
  control applied but its own, so a count says what a click on it would show), each dimension's options with counts and an
  `active` flag, the chips, and the groups. Clear all (`clear_all`) empties the dimension filters and the search; it leaves
  the type, Open/Closed/All and Group by alone.
- Search is a case-folded substring of the id, title, owner, update, client message and use case id, as the editor's.
- Order is stable: rows in the file's order (actions, then risks and issues, then decisions, each by id as published); option
  lists in a fixed order (statuses and priorities in their natural order, due buckets in their fixed order, the rest sorted
  by case-folded name, "(none)" last); groups in their option order.
- Remembered choices: the client's own browser only (`remember` -> a storage key and a JSON text; `recall` reads one back).
  Only type, show, f, not and group are kept, as the editor keeps them; the search text is not. Unknown keys, a wrong version,
  bad JSON, unknown values and values no published row has any more are ignored, so a stale choice can never empty the list
  without a chip to clear. Nothing is sent anywhere: there is no network call in this module, and the key holds the project code.

The page's contract (for the JavaScript)
- Data: the published data block's actions, raid and decisions, read once into rows exactly as `rows_of` does; "today" is the
  block's as-at day, never the browser's clock, so a report read next week still says what it said when it was published.
- Functions to mirror, by name: rows_of, bucket_of, apply_state, clear_all, remember, recall, normalise. State is the object above.
- Storage: localStorage key STORAGE_PREFIX + project code, in a try/catch (it can be blocked); value the JSON `remember` gives.
- Controls: the type switch and Open/Closed/All are two groups of buttons with counts; Filter by is one quiet row with a dot on
  an active dimension; a click on a second dimension opens it at once; chips beside the count each remove one filter, and
  Clear all removes them all; changing a filter redraws only the list and the labels, never the buttons, so nothing moves.
"""
import json
from datetime import date, timedelta

from clark import glance

STORAGE_PREFIX = "clark.work."
VERSION = 1
NONE = "(none)"
TYPES = ("all", "A", "R", "D")
TYPE_LABELS = {"all": "All", "A": "Actions", "R": "Risks and issues", "D": "Decisions"}
SHOWS = ("open", "closed", "all")
SHOW_LABELS = {"open": "Open", "closed": "Closed", "all": "All"}
KIND_TYPE = {"action": "A", "decision": "D"}      # every other kind is a RAID kind: "R"
FILTER_DIMENSIONS = ("ws", "status", "due", "owner", "priority", "uc", "ms")
DIMENSION_LABELS = {"ws": "Workstream", "status": "Status", "due": "Due", "owner": "Owner", "priority": "Priority",
                    "uc": "Use case", "ms": "Milestone"}
BUCKETS = ("overdue", "soon", "later", "none", "past")
BUCKET_LABELS = {"overdue": "Overdue", "soon": "Due in 7 days", "later": "Later", "none": "No date", "past": "Earlier"}
STATUS_ORDER = ("Open", "Delayed", "Pending", "Closed", "Made", "Cancelled", "Withdrawn")
PRIORITY_ORDER = ("Urgent", "High", "Medium", "Low")
# Group by: the table's choices in the editor (its board-only choices are not here: the client page has a list).
GROUPS = {"ws": "Workstream", "status": "Status", "due": "Due", "owner": "Owner", "priority": "Priority",
          "ms": "Milestone", "type": "Type", "none": "Nothing"}
DEFAULT_GROUP = "ws"
GROUP_DUE = (("overdue", "Overdue"), ("week", "This week"), ("next", "Next week"), ("later", "Later"), ("none", "No date"),
             ("past", "Earlier"))
REMEMBERED = ("type", "show", "f", "not", "group")
# The row field is "latest_update", never "update...": the repo's guard test flags any string starting with "update" as SQL, and
# the JSON cases file and the page's JavaScript use this same name. The published data's own field may still be called either
# (the row reads latest_update, then the client message).
ROW_FIELDS = ("id", "kind", "type", "title", "owner", "workstream", "status", "priority", "due", "bucket", "use_case",
              "milestone", "latest_update")


class Refused(ValueError):
    """A row that must not be here (it is not the client's) or an input that is not published data."""


# ── Rows ──────────────────────────────────────────────────────────────────────

def bucket_of(row, today):
    """The Due bucket of a row (one of BUCKETS)."""
    a, b = glance.day_number(row.get("due")), glance.day_number(today)
    if a is None or b is None:
        return "none"
    if glance.is_open(row):
        return "overdue" if a < b else "soon" if a - b <= 7 else "later"
    return "past" if a < b else "later"


def _row(kind, r, today):
    out = {"id": r.get("id"), "kind": kind, "type": KIND_TYPE.get(kind, "R"),
           "title": r.get("decision") if kind == "decision" else r.get("description"),
           "owner": r.get("made_by") if kind == "decision" else r.get("owner"),
           "workstream": r.get("workstream"), "status": r.get("status"), "priority": r.get("priority"),
           "use_case": r.get("use_case"), "milestone": r.get("milestone"),
           "latest_update": r.get("latest_update") or r.get("client_message") or ""}
    out["due"] = glance.due_field({"kind": kind, "status": r.get("status"), "due_date": r.get("due_date"),
                                   "needed_by": r.get("needed_by"), "date": r.get("date")})
    out["bucket"] = bucket_of(out, today)
    # the search also reads the client message when the update is a different text
    out["_search"] = " ".join(str(x) for x in (r.get("client_message"), r.get("latest_update")) if x)
    return out


def rows_of(published, today):
    """The work items of the published data (`publish.select(...)["data"]`): actions, then risks and issues, then decisions,
    in the order the file holds them. Refuses a row that is still marked not the client's."""
    glance._need_today(today)
    out = []
    for table, kind_of in (("actions", lambda r: "action"), ("raid", lambda r: str(r.get("type")).lower()),
                           ("decisions", lambda r: "decision")):
        for r in published.get(table) or []:
            if r.get("archived") or ("client_visible" in r and r.get("client_visible") not in (1, True)):
                raise Refused("A row that should not be on this page reached the filters, so nothing is shown. Publish the report again; if it still happens, check the row's Shown to client setting in the editor.")
            out.append(_row(kind_of(r), r, today))
    return out


def client_rows(rows_by_table, today, sections=None, label_rules=None):
    """The editor's tables to the client's rows: `glance.kept_rows` (and so `publish.select`) decides what is kept."""
    return rows_of(glance.kept_rows(rows_by_table, today, sections, label_rules)["data"], today)


def public(row):
    """A row as the page gets it: the whitelisted fields only (no search text)."""
    return {k: row[k] for k in ROW_FIELDS}


# ── Values, options, labels ───────────────────────────────────────────────────

def value_of(row, dim):
    """The value a row has for a dimension: the key a filter stores."""
    if dim == "ws":
        return row["workstream"] or NONE
    if dim == "status":
        return row["status"] or NONE
    if dim == "due":
        return row["bucket"]
    if dim == "owner":
        return row["owner"] or NONE
    if dim == "priority":
        return row["priority"] or NONE
    if dim == "uc":
        return row["use_case"] or NONE
    if dim == "ms":
        return row["milestone"] or NONE
    raise KeyError(dim)


def _rank(order):
    return lambda v: (0, order.index(v), "") if v in order else (1, 0, str(v).casefold()) if v != NONE else (2, 0, "")


def _sort_values(dim, values):
    if dim == "due":
        return [b for b in BUCKETS if b in values]
    if dim == "status":
        return sorted(values, key=_rank(STATUS_ORDER))
    if dim == "priority":
        return sorted(values, key=_rank(PRIORITY_ORDER))
    return sorted(values, key=_rank(()))


def value_label(dim, value, rows=()):
    if dim == "due":
        return BUCKET_LABELS.get(value, value)
    if value == NONE:
        return {"ws": "No workstream", "owner": "No owner", "uc": "No use case", "ms": "No milestone",
                "status": "No status", "priority": "No priority"}[dim]
    return value


def options(rows, dim):
    """Every value some row has for `dim`, in the fixed order (no counts)."""
    return _sort_values(dim, {value_of(r, dim) for r in rows})


# ── State ─────────────────────────────────────────────────────────────────────

def new_state():
    return {"type": "all", "show": "open", "f": {}, "not": {}, "q": "", "group": DEFAULT_GROUP}


def normalise(state, rows):
    """A state made safe against the published rows: unknown keys dropped, wrong values put back to the default, filter values
    no row has any more dropped, a dimension left with no value inactive. Never raises on odd input."""
    s = new_state()
    st = state if isinstance(state, dict) else {}
    if st.get("type") in TYPES:
        s["type"] = st["type"]
    if st.get("show") in SHOWS:
        s["show"] = st["show"]
    if isinstance(st.get("group"), str) and st["group"] in GROUPS:
        s["group"] = st["group"]
    if isinstance(st.get("q"), str):
        s["q"] = st["q"]
    f = st.get("f") if isinstance(st.get("f"), dict) else {}
    nt = st.get("not") if isinstance(st.get("not"), dict) else {}
    for dim in FILTER_DIMENSIONS:
        vs = f.get(dim)
        if not isinstance(vs, (list, tuple)):
            continue
        have = {value_of(r, dim) for r in rows}
        keep = []
        for v in vs:
            if isinstance(v, str) and v in have and v not in keep:
                keep.append(v)
        if keep:
            s["f"][dim] = [v for v in _sort_values(dim, keep)]
            if nt.get(dim) is True:
                s["not"][dim] = True
    return s


def clear_all(state):
    """Clear all: the dimension filters and the search go; the type, Open/Closed/All and Group by stay."""
    s = dict(state)
    s.update(f={}, **{"not": {}}, q="")
    return s


def _is_open_row(row):
    return glance.is_open(row)


def _matches(row, state, skip=()):
    if "type" not in skip and state["type"] != "all" and row["type"] != state["type"]:
        return False
    if "show" not in skip and state["show"] != "all" and (state["show"] == "open") != _is_open_row(row):
        return False
    for dim in FILTER_DIMENSIONS:
        vs = state["f"].get(dim)
        if dim in skip or not vs:
            continue
        if (value_of(row, dim) in vs) == bool(state["not"].get(dim)):
            return False
    q = state["q"].strip().casefold()
    if "q" not in skip and q:
        hay = " ".join(str(x) for x in (row["id"], row["title"], row["owner"], row["latest_update"], row["_search"],
                                        row["use_case"]) if x).casefold()
        if q not in hay:
            return False
    return True


def week_end(today, n=0):
    """The Sunday that ends this week (n=0) or next (n=1) as YYYY-MM-DD; a Sunday is its own week's end (the editor's weekEnd)."""
    y, m, d = (int(x) for x in today.split("-"))
    t = date(y, m, d)
    return (t + timedelta(days=(6 - t.weekday()) % 7 + 7 * n)).isoformat()


def _group_key(row, group, today):
    if group == "ws":
        return row["workstream"] or NONE
    if group == "status":
        return row["status"] or NONE
    if group == "owner":
        return row["owner"] or NONE
    if group == "priority":
        return row["priority"] or NONE
    if group == "ms":
        return row["milestone"] or NONE
    if group == "type":
        return row["type"]
    if group == "due":
        b = row["bucket"]
        if b in ("none", "past", "overdue"):
            return b
        return "week" if row["due"] <= week_end(today, 0) else "next" if row["due"] <= week_end(today, 1) else "later"
    return ""


def _group_order(group, keys):
    if group == "due":
        return [k for k, _ in GROUP_DUE if k in keys]
    if group == "type":
        return [k for k in ("A", "R", "D") if k in keys]
    if group == "none":
        return [""] if keys else []
    return _sort_values({"ws": "ws", "status": "status", "owner": "owner", "priority": "priority", "ms": "ms"}[group], keys)


def _group_label(group, key):
    if group == "due":
        return dict(GROUP_DUE)[key]
    if group == "type":
        return TYPE_LABELS[key]
    if group == "none":
        return "All items"
    return value_label({"ws": "ws", "status": "status", "owner": "owner", "priority": "priority", "ms": "ms"}[group], key)


def apply_state(rows, state, today):
    """The one answer for a state. `rows` is `rows_of`'s output, `state` is normalised against it first. Returns
    {state, items, count, counts: {type: {...}, show: {...}}, dimensions: [{dim, label, active, negated, options:
    [{value, label, count, selected}]}], chips, groups: [{key, label, count, items}]}. Items are `public` rows."""
    glance._need_today(today)
    s = normalise(state, rows)
    shown = [r for r in rows if _matches(r, s)]
    counts = {"type": {t: sum(1 for r in rows if _matches(r, dict(s, type=t))) for t in TYPES},
              "show": {k: sum(1 for r in rows if _matches(r, dict(s, show=k))) for k in SHOWS}}
    dims = []
    for dim in FILTER_DIMENSIONS:
        scope = [r for r in rows if _matches(r, s, skip=(dim,))]
        have = options(rows, dim)
        chosen = s["f"].get(dim, [])
        dims.append({"dim": dim, "label": DIMENSION_LABELS[dim], "active": bool(chosen), "negated": bool(s["not"].get(dim)),
                     "options": [{"value": v, "label": value_label(dim, v), "count": sum(1 for r in scope if value_of(r, dim) == v),
                                  "selected": v in chosen} for v in have]})
    chips = [{"dim": d["dim"], "label": d["label"], "negated": d["negated"],
              "values": [{"value": o["value"], "label": o["label"]} for o in d["options"] if o["selected"]]}
             for d in dims if d["active"]]
    if s["q"].strip():
        chips.append({"dim": "q", "label": "Search", "negated": False, "values": [{"value": s["q"].strip(), "label": s["q"].strip()}]})
    by = {}
    for r in shown:
        by.setdefault(_group_key(r, s["group"], today), []).append(r)
    groups = [{"key": k, "label": _group_label(s["group"], k), "count": len(by[k]), "items": [public(r) for r in by[k]]}
              for k in _group_order(s["group"], set(by))]
    return {"state": s, "items": [public(r) for r in shown], "count": len(shown), "counts": counts, "dimensions": dims,
            "chips": chips, "groups": groups}


# ── Remembered choices (the client's own browser) ─────────────────────────────

def storage_key(code):
    """The localStorage key for a project: STORAGE_PREFIX + its code."""
    return STORAGE_PREFIX + str(code)


def remember(state, code):
    """(key, JSON text) to keep in the client's browser: type, show, f, not and group only (never the search text, and
    nothing else a state or a row holds)."""
    s = state if isinstance(state, dict) else {}
    body = {k: s[k] for k in REMEMBERED if k in s}
    body["v"] = VERSION
    return storage_key(code), json.dumps(body, sort_keys=True, separators=(",", ":"))


def recall(text, rows):
    """A state from stored text, made safe against `rows`: anything wrong gives the default state; unknown keys are ignored."""
    try:
        got = json.loads(text) if isinstance(text, str) else None
    except ValueError:
        got = None
    if not isinstance(got, dict) or got.get("v") != VERSION:
        return new_state()
    return normalise({k: got[k] for k in REMEMBERED if k in got}, rows)
