"""#163: the read for the Use Cases page. One project's use cases as the editor shows them, and nothing else.

`make_read(data_for, client_ids)` gives the `use_cases` seam the server calls for GET /api/use-cases?project=<CODE> (the server wraps
the list in {"ok": true, "project": code, "use_cases": [...]}). It only reads: it
takes the project's rows from the store's own read (`Store.data_for`, a read-only connection) and writes nothing, to the
database or to a file. It is the editor's view, so it carries what the editor shows and a client never sees (the eye, the
items that are not client visible); the published file's Use Cases tab is built by `publish.select` instead, which is the one
function that decides what a client is given.

Each use case in the answer has:
  id, ref, name, headline (where it stands, in a line), status, standing (rich text, cleaned), on_dashboard (true when the published file carries it, by the injected rule `client_ids`; not the stored eye),
  linked (all its work items), open (the open ones), next_steps (its actions that are open), milestones (the milestones its open next steps point at).
A next step carries id, description, owner, due_date, status, client_visible. A milestone carries id, name, baseline_date,
forecast_date, status, client_visible. Archived use cases, work items and milestones are left out. Counts and lists use the
glance rules (`glance.is_open`), so the page and the published figures cannot count differently.

Text is cleaned as the other text fields are: the rich text through the allow-list (sanitise.clean_html), every plain field
with control, surrogate and invisible formatting characters removed. Plain text is never cut, so the editor shows the file's
own words; a missing owner or date is null. Standing text longer than the cleaner allows comes back empty, so the page must
not save a use case from this payload. The page escapes text it draws.

When the server is given `history_of` (the launcher does), each use case also carries `history`: what was done to it, newest
first, at most HISTORY_MAX lines, each {at, who, how, field, before, after, made, undo}. `at` is the stored UTC time (the page shows
it in the person's own time), `how` is the route the step came by ("dashboard", "assistant", "excel", "undo", ...), `field` is one of
HISTORY_FIELDS (or "id" for the step that made the use case), and `before` and `after` are short plain values (never the standing
text, which is only ever "edited"). A history that cannot be read leaves `history` an empty list; it never fails the read.

Standard library only, Python 3.9.
"""
import unicodedata

from clark import glance, sanitise

NEXT_STEP_FIELDS = ("id", "description", "owner", "due_date", "status")
MILESTONE_FIELDS = ("id", "name", "baseline_date", "forecast_date", "status")
NULLABLE = frozenset(("owner", "due_date", "baseline_date", "forecast_date"))     # a missing value is null, not ""
_UNSEEN = frozenset({"Cf", "Co", "Zl", "Zp"})       # invisible formatting: a right-to-left override, a zero-width space


def plain(value, nullable=False):
    """`value` as plain text, whole: control, surrogate and invisible formatting characters removed (as publish.reason_text
    does for the file), never cut, so the editor shows the file's own text. Anything that isn't text is '' (None when
    `nullable` and the value is missing)."""
    if value is None and nullable:
        return None
    if not isinstance(value, str):
        return ""
    return "".join(c for c in sanitise.CONTROL.sub("", value) if unicodedata.category(c) not in _UNSEEN)


def _fields(row, names):
    return {f: row.get(f) if f == "id" else plain(row.get(f), f in NULLABLE) for f in names}


def rich(value):
    """`value` through the rich-text allow-list; text the cleaner refuses (too long) comes back as ''."""
    try:
        return sanitise.clean_html(value)
    except sanitise.SanitiseError:
        return ""


def _order(row):
    """Sort key: sort_order (a whole number; anything else counts as 0), then id."""
    n = row.get("sort_order")
    return (n if isinstance(n, int) and not isinstance(n, bool) else 0, str(row.get("id")))


def _live(rows):
    return [r for r in rows or () if not r.get("archived")]


def _step(row):
    out = _fields(row, NEXT_STEP_FIELDS)
    out["client_visible"] = bool(row.get("client_visible", 0))
    return out


def _milestone(row):
    out = _fields(row, MILESTONE_FIELDS)
    out["client_visible"] = bool(row.get("client_visible", 0))
    return out


def milestones_of(steps, milestones):
    """The milestones that belong to a use case: those its next steps (its open actions) point at, in sort order. A milestone has
    no use case of its own, so this is the one place in the route that says how they belong, and `use_cases_of` calls nothing
    else for it. It is the same rule the published file uses (only open next steps name a milestone); when #168 lands, the
    launcher points the route at its function and this one is removed."""
    named = {r.get("milestone") for r in steps}
    return [m for m in milestones if m["id"] in named]


def use_cases_of(data, shown):
    """The list of use cases for `data` (Store.data_for's output), in the page's order (sort_order, then id). `shown` is the set of ids on the dashboard."""
    ucs = sorted(_live(data.get("use_cases")), key=_order)
    work = [(kind, r) for kind, table in (("action", "actions"), ("raid", "raid"), ("decision", "decisions"))
            for r in _live(data.get(table))]
    milestones = sorted(_live(data.get("milestones")), key=_order)
    out = []
    for u in ucs:
        mine = [(k, r) for k, r in work if r.get("use_case") == u["id"]]
        open_ = [(k, r) for k, r in mine if glance.is_open(r)]
        steps = [r for k, r in open_ if k == "action"]
        out.append({"id": u["id"], "ref": plain(u.get("ref")), "name": plain(u.get("title")),
                    "headline": plain(u.get("headline")), "status": plain(u.get("status")),
                    "standing": rich(u.get("standing")), "on_dashboard": u["id"] in shown,
                    "linked": len(mine), "open": len(open_),
                    "next_steps": [_step(r) for r in steps],
                    "milestones": [_milestone(m) for m in milestones_of(steps, milestones)]})
    return out


HISTORY_MAX = 40
HISTORY_FIELDS = ("title", "headline", "status", "standing", "client_visible", "archived")
SHORT = 120


def history_lines(events, ref):
    """A use case's history lines from history.history's events (newest first): one line for the step that made it, and one for
    each change of a field the page can change. Writes nothing; text is cleaned like every other field here."""
    out = []
    for e in events or ():
        if not isinstance(e, dict) or e.get("table") != "use_cases" or e.get("ref") != ref:
            continue
        made, field = e.get("op") == "insert", e.get("field")
        if made and field != "id" or not made and field not in HISTORY_FIELDS:
            continue
        keep = field not in ("standing", "id")
        out.append({"at": plain(e.get("at")), "who": plain(e.get("by_user")), "how": plain(e.get("route")), "field": field,
                    "before": plain(e.get("before"))[:SHORT] if keep and e.get("before") is not None else None,
                    "after": plain(e.get("after"))[:SHORT] if keep and e.get("after") is not None else None,
                    "made": made, "undo": bool(e.get("is_undo"))})
    return out[:HISTORY_MAX]


def make_read(data_for, client_ids, history_of=None):
    """The `use_cases` seam: `read(code)` is the list of the project's use cases, or None when there is no such project.
    `data_for(code)` is the store's read of one project. `client_ids(code)` is the injected rule: the set of use case ids the
    published file carries (what `publish.client_use_cases` decides); this module holds no copy of it. `history_of(refs)` is
    optional: {ref: history.history events} for those use cases, read on one connection. Nothing is written."""
    def read(code):
        data = data_for(code)
        if data is None:
            return None
        out = use_cases_of(data, client_ids(code))
        if history_of is not None and out:
            try:
                events = history_of([u["id"] for u in out])
            except Exception:  # noqa: BLE001  the history is extra: a read that fails leaves it empty, never the list
                events = {}
            for u in out:
                u["history"] = history_lines((events or {}).get(u["id"]), u["id"])
        return out
    return read
