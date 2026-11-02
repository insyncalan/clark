"""At a glance tiles, the health pill and the use case summary strip: the pure rules (#45; BRD FR-20, FR-21, FR-30 to FR-32).

No page, no server, no database and no clock: every function takes the rows it works on and "today" (YYYY-MM-DD) and gives
back plain dicts, so the same numbers come out every time and a test can fix the date. Standard library only, Python 3.9.
Rows are dicts with the columns of the tables in schema.sql, as `Store.data_for(code)` returns them.

Copied from creaite v2.6.9 (db5adb2), cut down to what fits clark: the four figures of the At a glance section and the
rule that a project's health is not changed without a reason (creaite report_doc `_w_glance` for the overdue, high risks and
decisions needed figures; report `decisions_needed` for the oldest needed-by date). creaite's "Next milestone" figure is not
health, overdue, risks and decisions in `glance_tiles`. The due, overdue and pill rules are the Work items list's
(src/clark/page/src/workItems.js, #36), rewritten here in Python so the tiles and the list can never count differently;
the tests run the list's own fixture cases through them. Each function copied or ported says so as (creaite ...) or
(workItems.js ...).

What the rules are
- Health is On track, At risk or Off track (green, amber, red; the words always travel with the colour). Changing it needs a
  reason, exactly as the writer checks it (store.py `_check_project`): a changed health must come with a health_reason that is
  not blank. A health picked with the reason as it stands is therefore refused when that reason is empty. No hint of the
  "better than the dates suggest" kind is given: the store has no such rule for a project's health (creaite's has one, and
  the AI suggestion waits for v0.3).
- Open means not Closed, Cancelled, Made or Withdrawn (so Delayed and Pending are open). Overdue means open and due before
  today; due today is not overdue; a due date that is not a real day is never overdue. A pending decision is due on its
  needed-by date.
- A risk's or issue's colour is its priority (D-12): Urgent and High red, Medium amber, Low green.
- Archived rows are never counted. The client version (`for_client=True`) counts exactly the rows the published page
  carries, and no others: `kept_rows` runs `publish.select` (#39), the one function that decides what is published, and the
  client tiles, the use case strip and the use case detail (`use_case_items`) are all worked out from its output. So a row
  that is not client_visible, is left off the page (`report_hidden`), carries a Sensitive label (or any label set to
  exclude, whatever its capitals) or belongs to a hidden section is in no client number. There is no second filter in this
  module; a client can never read a count the page cannot explain, nor learn that a Sensitive item exists. Hidden tiles are
  absent (not dimmed), and the output is built from a whitelist of fields, so no other field of a row can reach it.
- A tile whose section is hidden in the published page is left out of the client version: Overdue actions when the Actions
  section is hidden, High risks and issues when Risks and issues is, Decisions needed when Decisions is. (A summary of a
  section the reader cannot see would be a count they cannot check.) Project health has no section and always stays.

Decisions taken where the board item was open (each can be changed in one place)
- The Overdue actions tile counts open actions only (the board's Done-when, BRD FR-20 and the prototype); open RAID items and
  pending decisions past due are reported beside it as `parts` and `all_overdue`, not added in.
- The High risks and issues tile's value is the number of open risks and issues rated Urgent or High; `open` is all open
  risks and issues, and the tile's colour is the highest priority colour among the open ones.
- Decisions needed is hidden unless its `glance_tiles` row says otherwise (the board's Done-when).
- The client version shows the project's health reason, as the prototype's published page does. Health, Overdue and the
  other tiles use the same words for a client: there is no client word for them (creaite's "Expected later" and "Late" are
  for milestones only).

Where the tiles are computed (decision on the board item's review, 28-10-2026)
- This module is Python and the page is JavaScript, so the rules exist in two places and must never be a third. The EDITOR's
  tiles are computed in the page, in JavaScript, from workItems.js's rules, and nothing else: the page imports no copy of
  these rules and the server does not return tiles in /api/data. This module is the reference implementation. Both are run
  over the SAME fixture file, tests/fixtures/work-items-list-cases.json (#36): the Python side in tests/test_glance.py
  (`test_the_work_items_lists_own_cases`), the JavaScript side in the work items list's own test; so if the two ever
  disagree, one of those tests fails.
- The CLIENT's numbers are computed here, on the server, at publish time, from the rows `publish.select` keeps, because the
  published file is static and its numbers cannot be worked out again in a browser from rows the file does not hold.

Gaps, in plain words
- `Store.data_for` does not return `glance_tiles` or `report_hidden`, and the writer has no step kind for them yet (#65).
  Until then the page part passes them in as `rows_by_table["glance_tiles"]` and `["report_hidden"]`.
"""
import re
from datetime import date

from clark import publish        # select(): the one function that chooses what a client may see (#39)

HEALTHS = ("On track", "At risk", "Off track")                       # (projects.health, schema.sql)
HEALTH_COLOUR = {"On track": "green", "At risk": "amber", "Off track": "red"}
COLOUR_CLASS = {"green": "g", "amber": "a", "red": "r", "grey": "n", None: "n"}   # the Work items list's class letters (grey: a Done use case)
TILES = ("health", "overdue", "risks", "decisions")                  # glance_tiles.tile, in the default order
TILE_TITLES = {"health": "Project health", "overdue": "Overdue actions", "risks": "High risks and issues",
               "decisions": "Decisions needed"}
DEFAULT_HIDDEN = frozenset({"decisions"})
SECTION_OF_TILE = {"overdue": "actions", "risks": "raid", "decisions": "decisions"}   # the published section a tile summarises
OUTLINE_COLOUR = {"R": "red", "A": "amber", "G": "green", "N": None}  # glance_tiles.outline; "" is automatic
USE_CASE_STATUSES = ("On track", "Flag", "High risk", "Done")         # (use_cases.status, schema.sql)
USE_CASE_COLOUR = {"On track": "green", "Flag": "amber", "High risk": "red", "Done": "grey"}
CLOSED = ("Closed", "Cancelled", "Made", "Withdrawn")                 # (workItems.js CLOSED)
HIGH = ("Urgent", "High")
SOON_DAYS = 7
DASH = "—"
_ISO = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
_RANK = {None: 0, "green": 1, "amber": 2, "red": 3}


# ── Dates and words ───────────────────────────────────────────────────────────

def day_number(iso):
    """A day number for a real calendar day, None for anything else (including 2026-02-30). (workItems.js dayNumber)"""
    if not isinstance(iso, str) or not _ISO.fullmatch(iso):
        return None
    try:
        return date(int(iso[0:4]), int(iso[5:7]), int(iso[8:10])).toordinal()
    except ValueError:
        return None


def show_date(iso):
    """DD-MM-YYYY; text that is not a stored day is shown as stored; no date is a dash. (workItems.js showDate)"""
    if not iso:
        return DASH
    text = str(iso)
    return f"{text[8:10]}-{text[5:7]}-{text[0:4]}" if _ISO.fullmatch(text) else text


def plural(n, one, many):
    """'1 action', '2 actions', '0 actions'."""
    return f"{n} {one if n == 1 else many}"


def _need_today(today):
    if day_number(today) is None:
        raise ValueError(f"today must be a real day written YYYY-MM-DD (got {today!r})")


# ── The Work items list's rules, in Python (workItems.js) ─────────────────────

def colour_of_priority(priority):
    """D-12: Urgent and High are red, Medium amber, Low green; anything else is not rated (None). (workItems.js colourOf)"""
    if priority in HIGH:
        return "red"
    return {"Medium": "amber", "Low": "green"}.get(priority)


def is_open(row):
    """(workItems.js isOpen)"""
    return row.get("status") not in CLOSED


def due_field(row):
    """The date that counts as due: a decision's is the date it is needed by while pending, otherwise the date it was made.
    (workItems.js dueField)"""
    if row.get("kind") == "decision":
        return row.get("needed_by") if row.get("status") == "Pending" else row.get("date")
    return row.get("due_date")


def is_overdue(row, today):
    """Open, and due before today. Due today is not overdue. (workItems.js dueCell: tone "late")"""
    a, b = day_number(due_field(row)), day_number(today)
    return a is not None and b is not None and is_open(row) and a < b


def pill_of(row, today):
    """The state pill's words and class letter (r a g b n). (workItems.js pillOf)"""
    s, kind = row.get("status"), row.get("kind")
    if kind == "decision":
        return {"text": s, "class": "g" if s == "Made" else "n" if s == "Withdrawn" else "b"}
    if s in ("Closed", "Cancelled"):
        return {"text": s, "class": "n"}
    if kind in ("risk", "issue"):
        c = colour_of_priority(row.get("priority"))
        return {"text": {"red": "Red", "amber": "Amber", "green": "Green"}.get(c, "Not rated"), "class": COLOUR_CLASS[c]}
    if kind == "action":
        n, t = day_number(row.get("due_date")), day_number(today)
        if n is not None and t is not None and n < t:
            return {"text": "Overdue", "class": "r"}
        if s == "Delayed":
            return {"text": "Delayed", "class": "a"}
        if n is not None and t is not None and n - t <= SOON_DAYS:
            return {"text": "Due soon", "class": "a"}
    return {"text": "Open", "class": "b"}


_CLASS_COLOUR = {"r": "red", "a": "amber", "g": "green"}


def work_rows(rows_by_table):
    """One flat list of the project's work items from `data_for`'s tables: actions, then RAID (its type lower-cased is the
    kind), then decisions. Only the fields the counts need are kept, so the list holds no text of a work item. Archived rows
    are left out. (workItems.js rowsOf)"""
    out = []
    for table, kind_of in (("actions", lambda r: "action"), ("raid", lambda r: str(r.get("type")).lower()),
                           ("decisions", lambda r: "decision")):
        for r in rows_by_table.get(table) or []:
            if r.get("archived"):
                continue
            out.append({"id": r.get("id"), "kind": kind_of(r), "status": r.get("status"), "priority": r.get("priority"),
                        "due_date": r.get("due_date"), "needed_by": r.get("needed_by"), "date": r.get("date"),
                        "use_case": r.get("use_case"), "client_visible": bool(r.get("client_visible", 1))})
    return out


def _left_off(rows_by_table):
    """The ids the editor left off the published page (report_hidden rows, or plain ids)."""
    return {(h.get("item_id") if isinstance(h, dict) else h) for h in rows_by_table.get("report_hidden") or []}


def kept_rows(rows_by_table, today, sections=None, label_rules=None):
    """What a client may see, worked out by `publish.select`, the one function that decides what is published, and nothing
    else. `rows_by_table` is `data_for`'s output plus, when the page has them, `report_hidden`, `report_sections` and
    `label_rules` rows (`sections` and `label_rules` given here win). Returns
    {"data": select's published data, "rows": work_rows of the kept actions, RAID and decisions, "use_cases": the kept use
    cases, "hidden_types": the section types hidden in the page}. `today` is the report's as-at day (select needs one)."""
    _need_today(today)
    sections = rows_by_table.get("report_sections") if sections is None else sections
    rules = rows_by_table.get("label_rules") if label_rules is None else label_rules
    chosen = publish.select({"data": rows_by_table, "hidden": sorted(_left_off(rows_by_table), key=str), "sections": sections,
                             "label_rules": rules, "as_at": today})
    return kept_from(chosen, sections)


def kept_from(chosen, sections=None):
    """The same reduction as `kept_rows`, from what `publish.select` has already chosen (its output), so the publish path does
    not run select twice (#45). `sections` are the report's section rows (select's own default sections when none)."""
    # select keeps this set to itself; the same one line, with the same default sections. A test checks they agree.
    hidden_types = {s.get("type") for s in (sections or publish.DEFAULT_SECTIONS) if s.get("hidden")}
    return {"data": chosen["data"], "rows": work_rows(chosen["data"]), "use_cases": chosen["data"]["use_cases"],
            "hidden_types": hidden_types}


def use_case_items(kept, use_case_id):
    """The work items linked to one use case that the published page carries: what the use case detail counts and lists
    for a client. A use case linked only to rows the page leaves out has none ('no linked work items')."""
    return [r for r in kept["rows"] if r.get("use_case") == use_case_id]


# ── Health: the pill and the pick ─────────────────────────────────────────────

def health_pill(health):
    """The pill's words and colour. The colour is always named in `label`, so it is never the only signal. A project with no
    health yet reads 'Not set'."""
    colour = HEALTH_COLOUR.get(health)
    words = health if colour else "Not set"
    return {"health": health if colour else None, "words": words, "colour": colour, "class": COLOUR_CLASS[colour],
            "label": f"Project health: {words}" + (f", {colour}" if colour else "")}


def _answer(change, errors, message, reused_reason=False):
    return {"change": change, "errors": errors, "message": message, "reused_reason": reused_reason}


def health_pick(current, wanted, reason=None):
    """What picking `wanted` on the health pill should do. `current` is the project's row (it needs `code`; `health` and
    `health_reason` are read). `reason` is the reason typed; None means the reason as it stands (the board item's Open 1).

    Returns {"change": request or None, "errors": [plain words], "message": plain words, "reused_reason": bool}.
    `reused_reason` is True when the health changes and the reason sent is the one already on the project (it was not
    typed afresh, or was typed unchanged), so the page can ask for a one-line confirmation ('Is this reason still right for
    At risk?') before it saves (the board item's Open 1). The change is still returned; the page decides when to ask. A request is
    {"table": "projects", "ref": code, "changes": {"health": ..., "health_reason": ...}}, ready for
    Store.step(...).update(request["table"], request["ref"], request["changes"]). The rule is the writer's
    (store.py _check_project): a changed health is refused unless the same change carries a reason that is not blank. The
    same health as now is not a change, so there is no request and no error."""
    have = current.get("health")
    if wanted not in HEALTHS:
        if isinstance(wanted, str) and wanted.strip():
            return _answer(None, [f"\"{wanted}\" is not a health. Choose On track, At risk or Off track."], "")
        return _answer(None, ["Choose a health: On track, At risk or Off track."], "")
    if not current.get("code"):
        return _answer(None, ["Say which project the health is for."], "")
    if wanted == have:
        return _answer(None, [], f"The health is already {wanted}. Nothing to change.")
    text = current.get("health_reason") if reason is None else reason
    if not str(text or "").strip():
        return _answer(None, [f"Say why in a line or two before the health becomes {wanted}. "
                              "clark keeps the reason with the health."], "")
    change = {"table": "projects", "ref": current["code"], "changes": {"health": wanted, "health_reason": text}}
    reused = bool(have) and str(text).strip() == str(current.get("health_reason") or "").strip()
    return _answer(change, [], f"Health changed from {have} to {wanted}." if have else f"Health set to {wanted}.", reused)


def reason_change(current, reason):
    """Editing the reason alone. The same text is not a change. The writer does not need a reason for this, so none is
    asked for; the request has the reason only."""
    text = "" if reason is None else str(reason)
    if not current.get("code"):
        return _answer(None, ["Say which project the reason is for."], "")
    if text == (current.get("health_reason") or ""):
        return _answer(None, [], "The reason is the same. Nothing to change.")
    return _answer({"table": "projects", "ref": current["code"], "changes": {"health_reason": text}}, [],
                   "Reason saved." if text.strip() else "Reason cleared.")


# ── At a glance tiles ─────────────────────────────────────────────────────────

def tile_settings(glance_rows):
    """The order, hidden set and outline colours from `glance_tiles` rows (project, tile, hidden, outline, sort_order).
    A tile with no row comes after those with one, in the default order, and is hidden only if it is hidden by default.
    A row for any other tile (the milestone tiles that were taken out) is ignored."""
    rows = [r for r in glance_rows or [] if r.get("tile") in TILES]
    rows.sort(key=lambda r: (r.get("sort_order") or 0, TILES.index(r["tile"])))
    order = list(dict.fromkeys(r["tile"] for r in rows))
    have = set(order)
    order += [t for t in TILES if t not in have]
    by = {r["tile"]: r for r in rows}
    hidden = {t for t in TILES if (bool(by[t].get("hidden")) if t in by else t in DEFAULT_HIDDEN)}
    outlines = {t: by[t].get("outline") or "" for t in by}
    return {"order": order, "hidden": hidden, "outlines": outlines}


def _order(tile_order):
    known = [t for t in dict.fromkeys(tile_order or ()) if t in TILES]
    return known + [t for t in TILES if t not in known]


def _label(title, value, detail, colour):
    return ", ".join([f"{title}: {value}"] + ([detail] if detail else []) + ([colour] if colour else []))


def _health_tile(project):
    pill = health_pill(project.get("health"))
    reason = str(project.get("health_reason") or "")
    return {"tile": "health", "title": TILE_TITLES["health"], "value": pill["words"], "detail": "", "health": pill["health"],
            "reason": reason, "pill": pill, "auto_colour": pill["colour"],
            "label": pill["label"] + (f". {reason}" if reason.strip() else "")}


def _overdue_tile(rows, today):
    actions = [r for r in rows if r["kind"] == "action" and is_open(r)]
    late = [r for r in actions if is_overdue(r, today)]
    parts = {"actions": len(late),
             "raid": sum(1 for r in rows if r["kind"] not in ("action", "decision") and is_overdue(r, today)),
             "decisions": sum(1 for r in rows if r["kind"] == "decision" and is_overdue(r, today))}
    detail = f"of {plural(len(actions), 'open action', 'open actions')}" if actions else "No open actions"
    return {"tile": "overdue", "title": TILE_TITLES["overdue"], "value": len(late), "words": f"{len(late)} overdue",
            "detail": detail, "open": len(actions), "parts": parts, "all_overdue": sum(parts.values()),
            "auto_colour": "red" if late else "green"}


def _risks_tile(rows):
    open_ = [r for r in rows if r["kind"] in ("risk", "issue") and is_open(r)]
    high = [r for r in open_ if r.get("priority") in HIGH]
    worst = max((colour_of_priority(r.get("priority")) for r in open_), key=_RANK.get, default=None)
    if not open_:
        detail = "None open"
    elif len(open_) == 1:
        detail = "of 1 open risk or issue"
    else:
        detail = f"of {len(open_)} open risks and issues"
    return {"tile": "risks", "title": TILE_TITLES["risks"], "value": len(high), "detail": detail, "open": len(open_),
            "high": len(high), "auto_colour": worst or "green"}


def _decisions_tile(rows):
    pending = [r for r in rows if r["kind"] == "decision" and r.get("status") == "Pending"]
    dated = sorted(r["needed_by"] for r in pending if day_number(r.get("needed_by")) is not None)
    oldest = dated[0] if dated else None
    if not pending:
        detail = "None waiting"
    elif oldest:
        detail = f"Oldest needed by {show_date(oldest)}"
    else:
        detail = "No date needed by"
    return {"tile": "decisions", "title": TILE_TITLES["decisions"], "value": len(pending), "detail": detail,
            "oldest": oldest, "oldest_shown": show_date(oldest) if oldest else "", "auto_colour": "amber" if pending else "green"}


def tiles(rows_by_table, today, tile_order=None, hidden=None, outlines=None, for_client=False, kept=None):
    """The At a glance tiles, in order. `rows_by_table` is `data_for`'s output (project, actions, raid, decisions), plus
    `glance_tiles` and `report_hidden` rows when the page has them. `tile_order`, `hidden` (tile names) and `outlines`
    ({tile: 'R'|'A'|'G'|'N'|''}) default to what the `glance_tiles` rows say, and to the default order with Decisions needed
    hidden when there are none. (creaite report_doc _w_glance, for the figures)

    Each tile is a dict with tile, title, value, detail, colour (the colour shown: the right-click choice if there is one,
    otherwise automatic), class (r a g n), label (words for a screen reader, the colour named) and the fields of its kind.
    The editor's tiles also carry hidden, outline and auto_colour, and hidden tiles are kept (to be dimmed). The client's
    leave hidden tiles out, and tiles whose published section is hidden, carry no setting, and count only the rows
    `publish.select` keeps (`kept=kept_rows(...)`; worked out here from `rows_by_table` when not given)."""
    _need_today(today)
    settings = tile_settings(rows_by_table.get("glance_tiles"))
    order = _order(tile_order if tile_order is not None else settings["order"])
    off = set(hidden) if hidden is not None else settings["hidden"]
    choice = dict(outlines) if outlines is not None else settings["outlines"]
    if for_client:
        kept = kept or kept_rows(rows_by_table, today)
        rows = kept["rows"]
    else:
        rows = work_rows(rows_by_table)
    project = rows_by_table.get("project") or {}
    made = {"health": lambda: _health_tile(project), "overdue": lambda: _overdue_tile(rows, today),
            "risks": lambda: _risks_tile(rows), "decisions": lambda: _decisions_tile(rows)}
    out = []
    for name in order:
        if for_client and (name in off or SECTION_OF_TILE.get(name) in kept["hidden_types"]):
            continue
        t = made[name]()
        outline = choice.get(name) or ""
        colour = OUTLINE_COLOUR[outline] if outline in OUTLINE_COLOUR else t["auto_colour"]
        t["colour"], t["class"] = colour, COLOUR_CLASS[colour]
        if "label" not in t:
            t["label"] = _label(t["title"], t["value"], t["detail"], colour)
        else:
            t["label"] = t["label"] if colour == t["auto_colour"] else f"{t['label']}, outline {colour or 'none'}"
        if for_client:
            del t["auto_colour"]
        else:
            t["hidden"], t["outline"] = name in off, outline
        out.append(t)
    return out


# ── The use case summary strip ────────────────────────────────────────────────

def _worst(rows, today):
    colours = [_CLASS_COLOUR.get(pill_of(r, today)["class"]) for r in rows if is_open(r)]
    return max(colours, key=_RANK.get, default=None)


def use_case_strip(use_cases, work_rows_, today, for_client=False, kept=None):
    """The strip and the slim rows. `use_cases` are use_cases rows; `work_rows_` is `work_rows(...)`'s list (a work item's
    `use_case` is the id of the use case it belongs to). Rows come sorted by sort_order, then id. Archived use cases are left
    out. The client version takes BOTH lists from `kept` (`kept_rows(...)`, which is `publish.select`'s output), so the
    two arguments are ignored (pass None) and a use case or linked work item the page leaves out is never counted; `kept`
    is required. Only a whitelist of fields is carried: id, ref, title, headline, status,
    colour and the counts. 'Where it stands' and the detail are the page's own reading of the row, not part of the strip.

    Returns {"total", "total_words", "counts": [{status, colour, class, count}] (statuses with none are left out, in the
    schema's order; the page draws the meter from the counts), "rows": [...]}. Each row: id, ref, title, headline, status,
    colour, class, linked (all its work items), open, overdue, next_steps (open actions), worst (the worst colour among its
    open items: red, amber, green or None) and words ('No linked work items', 'No open work items', '2 open, 1 overdue')."""
    _need_today(today)
    if for_client:
        if kept is None:
            raise ValueError("the client version is counted from the rows the page keeps: pass kept=kept_rows(...)")
        use_cases, work_rows_ = kept["use_cases"], kept["rows"]
    ucs = [u for u in use_cases if not u.get("archived")]
    items = [w for w in work_rows_ if w.get("use_case")]
    ucs.sort(key=lambda u: (u.get("sort_order") or 0, str(u.get("id"))))
    rows = []
    for u in ucs:
        mine = [w for w in items if w["use_case"] == u["id"]]
        open_ = [w for w in mine if is_open(w)]
        late = [w for w in open_ if is_overdue(w, today)]
        steps = [w for w in open_ if w["kind"] == "action"]
        status = u.get("status")
        colour = USE_CASE_COLOUR.get(status)
        words = ("No linked work items" if not mine else "No open work items" if not open_
                 else f"{len(open_)} open" + (f", {len(late)} overdue" if late else ""))
        row = {"id": u["id"], "ref": u.get("ref") or "", "title": u.get("title") or "", "headline": u.get("headline") or "",
               "status": status, "colour": colour, "class": COLOUR_CLASS[colour], "linked": len(mine), "open": len(open_),
               "overdue": len(late), "next_steps": len(steps), "worst": _worst(mine, today), "words": words,
               "steps_words": plural(len(steps), "next step", "next steps") if steps else "No open steps"}
        if not for_client:
            row["client_visible"] = bool(u.get("client_visible", 1))
        rows.append(row)
    counts = [{"status": s, "colour": USE_CASE_COLOUR[s], "class": COLOUR_CLASS[USE_CASE_COLOUR[s]], "count": n}
              for s in USE_CASE_STATUSES for n in [sum(1 for r in rows if r["status"] == s)] if n]
    return {"total": len(rows), "total_words": plural(len(rows), "use case", "use cases") if rows else "No use cases",
            "counts": counts, "rows": rows}
