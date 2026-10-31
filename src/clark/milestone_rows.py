"""The Milestones view's data, without the page (#44a Plan and #44b Movement; BRD FR-50 to FR-54).

Pure functions over milestone rows (the `milestones` table's columns, as dicts) and over the events `history.history()` reports.
Nothing here touches the database, the clock (give `today`) or the page. Standard library only.

  milestone_rows(rows, today, workstreams, events)  -> one display dict per milestone, sorted
  for_client(rows, hidden_ids)                       -> the same, cut down to what a published page may say
  movement(events, milestone_id)                     -> what changed, newest first (internal only: it carries the internal
                                                        note's changes, so it must never feed anything published)
  timeline_span / clamp_zoom / buckets / calendar_chips / legend  -> the timeline axis, the Calendar and the Legend
  rebaseline_request(row, ...)                       -> the arguments for Step.update(..., rebaseline=...), or plain-words errors

The state, the client word and the slip come from milestones.py (#32), unchanged. Dates are YYYY-MM-DD in every value and
DD-MM-YYYY in every sentence. Marks follow FR-51 and the prototype: a solid mark on the agreed date (the achieved date once
achieved; the forecast when there is no agreed date), and, for a milestone that has slipped, a ghost mark on its expected date
joined to the solid one by a dashed line.

(creaite v2.6.9 db5adb2, build_dashboard.py milestone_detail) the Movement log's shape: one entry per change in each step, the
rebaseline entry that folds in the forecast moved with it, its decision found by the ID in the step's note, and the reason shown
with each. Not copied: the weekly history, and the forecast ranges from forecast.py (the draft doesn't ask for them).
"""
import re
from datetime import date, timedelta

from clark import milestones as ms
from clark.timefmt import local_text

CANCELLED = "Cancelled"

# State -> (colour name, mark shape name, what it means). Colours and shapes are the prototype's (core.js msMark, MS_CLS), which
# are creaite's marks on the line; the page maps the names to the design system's tokens.
LOOK = {
    "Achieved": ("green", "tick-circle", "Done, on the date it was achieved"),
    "On track": ("green", "dot", "Expected on its agreed date"),
    "At risk": ("amber", "triangle", "Marked at risk by the project team"),
    "Slipped": ("red", "diamond", "Now expected after its agreed date"),
    "Overdue": ("red", "cross-circle", "Its agreed date has passed"),
    "Forecast": ("blue", "dashed-circle", "A date not yet agreed"),
    CANCELLED: ("grey", "dash", "No longer going ahead"),
}
LEGEND_STATES = ms.STATES            # Cancelled is never on the legend: a Cancelled milestone is not drawn on a published page

ZOOM_MIN, ZOOM_MAX = 0.7, 3.0        # "70% to 300%" (the draft)
LEAD_DAYS, TAIL_DAYS = 20, 45        # room before the first and after the last date on the timeline (the prototype's)


# ── dates ────────────────────────────────────────────────────────────────────

def shown(iso):
    """YYYY-MM-DD as DD-MM-YYYY, for anything a person reads."""
    return "%s-%s-%s" % (iso[8:10], iso[5:7], iso[0:4]) if iso and len(iso) >= 10 else (iso or "")


def parse_date(text):
    """A date typed as YYYY-MM-DD or DD-MM-YYYY, as YYYY-MM-DD; None when it isn't a real date."""
    text = str(text or "").strip()
    for pattern, order in ((r"^(\d{4})-(\d{2})-(\d{2})$", (0, 1, 2)), (r"^(\d{2})-(\d{2})-(\d{4})$", (2, 1, 0))):
        m = re.match(pattern, text)
        if m:
            parts = [int(m.group(i + 1)) for i in order]
            try:
                return date(*parts).isoformat()
            except ValueError:
                return None
    return None


def _d(iso):
    return date.fromisoformat(iso)


def _plural(n, word):
    return "%d %s%s" % (n, word, "" if abs(n) == 1 else "s")


# ── the rows ─────────────────────────────────────────────────────────────────

def expected_date(row, on=None):
    """The date a Planned milestone is now expected: the later of its forecast (or agreed date) and, once the agreed date has
    passed, today. The same sum as milestones.slip_days, which is this date less the agreed date. None when slip_days is None."""
    if ms.slip_days(row, on) is None:
        return None
    on = on or ms.today()
    base = row["baseline_date"]
    return max(row.get("forecast_date") or base, on if base < on else base)


def original_from_events(events, current=None):
    """The Original date from a milestone's history events (any order): the first agreed date written that is still in force
    (not undone, not an undo), else `current`. The same rule as history.original_date, which reads the database."""
    for e in sorted(events or (), key=lambda e: e["event_id"]):
        if (e.get("table") == "milestones" and e.get("field") == "baseline_date" and e.get("after") is not None
                and not e.get("is_undo") and e.get("in_force")):
            return e["after"]
    return current


def _marks(row, state, slip, expected):
    """The mark data for the timeline: {solid, ghost, line}. Each is None or a dict with a date; `solid` also says what the date
    is ("achieved", "agreed" or "forecast"). Only a Planned milestone with a slip shows a ghost and a line; a Forecast or an
    achieved one never does (FR-50)."""
    base, fc, done = row.get("baseline_date"), row.get("forecast_date"), row.get("actual_date")
    if row.get("status") == "Done" and (done or base):
        solid = {"date": done or base, "kind": "achieved" if done else "agreed"}
    elif base:
        solid = {"date": base, "kind": "agreed"}
    elif fc:
        solid = {"date": fc, "kind": "forecast"}
    else:
        solid = None
    ghost = line = None
    if slip and slip > 0 and state != ms.FORECAST and solid and solid["kind"] == "agreed":
        ghost = {"date": expected, "label": "Expected " + shown(expected)}
        line = {"from": base, "to": expected, "days": slip}
    return {"solid": solid, "ghost": ghost, "line": line}


def _achieved_note(row):
    """Plain words for how an achieved milestone compares with its agreed date; "" when it isn't achieved or has no date."""
    done, base = row.get("actual_date"), row.get("baseline_date")
    if row.get("status") != "Done" or not done:
        return ""
    if not base:
        return "Achieved on %s" % shown(done)
    late = (_d(done) - _d(base)).days
    if late == 0:
        return "Achieved on the agreed date"
    return "Achieved %s %s the agreed date" % (_plural(late, "day"), "after") if late > 0 else \
        "Achieved %s early" % _plural(-late, "day")


def _workstream_name(value, workstreams):
    """The workstream's name as the workstreams list spells it (matched without regard to case); else as given."""
    value = str(value or "").strip()
    for w in workstreams or ():
        name = w.get("name") if isinstance(w, dict) else w
        if name and str(name).strip().lower() == value.lower():
            return str(name).strip()
    return value


def _sort_key(r):
    d = r["baseline"] or r["forecast"]
    return (d is None, d or "", r["sort_order"], r["id"])


def milestone_rows(rows, today=None, workstreams=None, events=None):
    """Display dicts for the Milestones view, sorted by agreed date (a milestone with none sorts by its forecast, then last),
    then sort_order, then id. Archived rows are left out; Cancelled ones are kept, with the state "Cancelled" and no slip.

    `rows` are milestone rows; `today` is YYYY-MM-DD (default: today); `workstreams` are the project's workstream rows or names
    (to spell each milestone's workstream as the workstream does); `events` is {milestone id: history events} and gives each row
    its Original date and whether it was rebaselined. When `events` is passed but has none for a milestone, its Original date is
    its current agreed date (as history.original_date does when nothing was ever written); when `events` is None the Original
    date isn't known and `original` is None, so the page part must pass events.

    Keys: id, name, description, workstream, owner, status, state, client_word, colour, mark, baseline (the agreed date),
    forecast, original, rebaselined, achieved, achieved_note (plain words, from the achieved and agreed dates), percent, slip (days, or None: a Forecast, achieved or Cancelled milestone has
    none), slip_text ("N days later" or None), expected (the date it's now expected, when it has slipped), marks, state_set,
    state_reason, internal_note, client_visible, client_message, movement, sort_order."""
    on = today or ms.today()
    out = []
    for r in rows:
        if r.get("archived"):
            continue
        cancelled = r.get("status") == CANCELLED
        state = CANCELLED if cancelled else ms.milestone_state(r, on)
        slip = None if cancelled or state == ms.FORECAST else ms.slip_days(r, on)     # FR-50: a Forecast has no slip
        expected = expected_date(r, on) if slip else None
        colour, mark, _ = LOOK[state]
        original = None if events is None else original_from_events(events.get(r["id"]), r.get("baseline_date"))
        out.append({
            "id": r["id"], "name": r["name"], "description": r.get("description") or "",
            "workstream": _workstream_name(r.get("workstream"), workstreams), "owner": r.get("owner") or "",
            "status": r.get("status") or "Planned", "state": state,
            "client_word": CANCELLED if cancelled else ms.client_word(state), "colour": colour, "mark": mark,
            "baseline": r.get("baseline_date"), "forecast": r.get("forecast_date"), "original": original,
            "rebaselined": bool(original and r.get("baseline_date") and original != r["baseline_date"]),
            "achieved": r.get("actual_date") if r.get("status") == "Done" else None,
            "achieved_note": _achieved_note(r),
            "percent": r.get("percent_complete"), "slip": slip,
            "slip_text": "%s later" % _plural(slip, "day") if slip else None, "expected": expected,
            "marks": _marks(r, state, slip, expected),
            "state_set": bool(r.get("state_set")), "state_reason": r.get("state_reason") or "",
            "internal_note": r.get("internal_note") or "", "client_visible": bool(r.get("client_visible")),
            "client_message": r.get("client_message") or "", "movement": r.get("movement"),
            "sort_order": r.get("sort_order") or 0,
        })
    return sorted(out, key=_sort_key)


def for_client(rows, hidden_ids=()):
    """What a published page may know about the milestones in `rows` (milestone_rows' output). Built from a short list of
    fields, so nothing else gets through: no internal note, state reason, Movement choice, original date or rebaseline. Rows
    that aren't client-visible, and Cancelled ones, are left out. `state` is the client's word (Expected later, Late, ...).

    `hidden_ids` are the ids the report's eye has hidden (the `report_hidden` table, #67), which this module never sees: the
    page part must pass them, and a row whose id is in them is left out even when it is client-visible. The Legend and the
    timeline and Calendar helpers count only the rows they are given, so give them this function's output."""
    hidden = set(hidden_ids or ())
    out = []
    for r in rows:
        if (not r.get("client_visible") or r.get("status") == CANCELLED or r.get("state") == CANCELLED
                or r.get("id") in hidden):
            continue
        out.append({
            "id": r["id"], "name": r["name"], "workstream": r["workstream"], "owner": r["owner"], "status": r["status"],
            "state": r["client_word"], "colour": r["colour"], "mark": r["mark"],
            "baseline": r["baseline"], "forecast": r["forecast"], "achieved": r["achieved"], "percent": r["percent"],
            "slip": r["slip"], "slip_text": r["slip_text"], "expected": r["expected"],
            "marks": {k: (dict(v) if v else None) for k, v in r["marks"].items()},
            "client_message": r["client_message"],
        })
    return out


# ── Movement ─────────────────────────────────────────────────────────────────

DECISION_ID = re.compile(r"\b[A-Z][A-Z0-9]{2,6}-D-\d{3}\b")      # (creaite) how a rebaseline's decision is found in its note
MOVEMENT_FIELDS = ("baseline_date", "forecast_date", "actual_date", "status", "state", "state_reason", "movement",
                   "internal_note", "note")


def _last_decision(text):
    """The decision ID the store wrote at the end of a rebaseline's note ("... Decision ABC-D-001"). The reason may name other
    decisions earlier on, so it is the last ID in the text, not the first. "" when there is none."""
    found = DECISION_ID.findall(text or "")
    return found[-1] if found else ""


def _entry(step, kind, text, evs, **more):
    last = max(evs, key=lambda e: e["event_id"])
    return {"step": step, "event_id": last["event_id"], "at": last["at"], "at_text": local_text(last["at"]), "by": last["by_user"], "kind": kind, "text": text,
            "why": "", "decision": "", "undone": not any(e["in_force"] for e in evs), "internal": kind == "internal_note", **more}


def _moved(label, before, after):
    if before and after:
        return "%s moved from %s to %s" % (label, shown(before), shown(after))
    if after:
        return "%s set to %s" % (label, shown(after))
    return "%s cleared (it was %s)" % (label, shown(before))


def movement(events, milestone_id, include_undone=True):
    """The Movement list for one milestone, newest first, from `history.history()` events: each agreed-date change (a
    rebaseline, with its reason and decision), forecast change, achieved date, status and state change, Movement choice and
    note, with who and when (`by`; `at`, UTC as the history gives it, for sorting; `at_text`, the same time on the user's own clock as
    DD-MM-YYYY HH:MM, for showing).

    History reports an undo as events of its own (is_undo) and marks what it reversed as not in force. Undo events are left out
    here; the change they reversed stays in the list with `undone` True (or goes, when include_undone is False), so the record
    shows what was tried. The creation of the milestone is not a movement. A note written with a change is that entry's `why`;
    a note in a step with no other entry stands alone, and follows its step if the step was undone.

    Internal only: the entries include the internal note's changes (kind "internal_note", internal True). Never publish them."""
    steps = {}
    created = {e["step"] for e in events or () if e.get("field") == "id" and e.get("ref") == milestone_id}   # only a creation logs the id
    for e in sorted(events or (), key=lambda e: e["event_id"]):
        if (e.get("table", "milestones") != "milestones" or e.get("ref", milestone_id) != milestone_id or e.get("is_undo")
                or e.get("field") not in MOVEMENT_FIELDS or e["step"] in created):
            continue
        steps.setdefault(e["step"], {}).setdefault(e["field"], []).append(e)
    out = []
    for step, f in steps.items():
        notes = f.pop("note", [])
        why = " ".join(n["after"] for n in notes if n.get("after"))
        entries = []
        if "baseline_date" in f:
            b, a = f["baseline_date"][0]["before"], f["baseline_date"][-1]["after"]
            if b and a and b != a:
                text = "Rebaselined: agreed date moved from %s to %s" % (shown(b), shown(a))
                if "forecast_date" in f and f["forecast_date"][-1]["after"] not in (None, a):
                    text += ", forecast now %s" % shown(f["forecast_date"][-1]["after"])
                dm = _last_decision(why)
                entries.append(_entry(step, "rebaseline", text, f["baseline_date"] + f.get("forecast_date", []),
                                      from_date=b, to_date=a, decision=dm))
                f.pop("forecast_date", None)
            elif a != b:
                entries.append(_entry(step, "agreed", _moved("Agreed date", b, a), f["baseline_date"], from_date=b, to_date=a))
        if "forecast_date" in f:
            b, a = f["forecast_date"][0]["before"], f["forecast_date"][-1]["after"]
            if a != b:
                days = (_d(a) - _d(b)).days if a and b else None
                text = _moved("Forecast", b, a) + (" (%s%s)" % ("+" if days > 0 else "", _plural(days, "day")) if days else "")
                entries.append(_entry(step, "forecast", text, f["forecast_date"], from_date=b, to_date=a, days=days))
        if "status" in f:
            b, a = f["status"][0]["before"], f["status"][-1]["after"]
            if a == "Done":
                got = f.get("actual_date", [{"after": None}])[-1]["after"]
                entries.append(_entry(step, "achieved", "Achieved" + (" on %s" % shown(got) if got else ""),
                                      f["status"] + f.get("actual_date", [])))
            elif b in ("Done", CANCELLED):
                entries.append(_entry(step, "reopened", "Reopened", f["status"]))
            elif a == CANCELLED:
                entries.append(_entry(step, "cancelled", "Cancelled", f["status"]))
        elif "actual_date" in f and f["actual_date"][-1]["after"] != f["actual_date"][0]["before"]:
            entries.append(_entry(step, "achieved", _moved("Achieved date", f["actual_date"][0]["before"],
                                                           f["actual_date"][-1]["after"]), f["actual_date"]))
        if "state" in f and "status" not in f and f["state"][0]["before"] != f["state"][-1]["after"]:      # Done clears a state itself
            b, a = f["state"][0]["before"] or "following the dates", f["state"][-1]["after"] or "following the dates"
            reason = (f.get("state_reason") or [{"after": ""}])[-1]["after"] or ""
            entries.append(_entry(step, "state", "State changed from %s to %s" % (b, a), f["state"] + f.get("state_reason", []),
                                  why=reason))
        if "movement" in f:
            a = f["movement"][-1]["after"]
            entries.append(_entry(step, "movement", "Movement choice: %s" % (a.capitalize() if a else "cleared"), f["movement"]))
        if "internal_note" in f:
            entries.append(_entry(step, "internal_note", "Internal note changed", f["internal_note"],
                                  detail=f["internal_note"][-1]["after"] or ""))
        if why:
            if entries:
                entries[0]["why"] = entries[0]["why"] or why
            else:
                entries.append(_entry(step, "note", why, notes, undone=False))
        out.extend(entries)
    out.sort(key=lambda en: en["event_id"], reverse=True)
    return [en for en in out if include_undone or not en["undone"]]


def moves(entries):
    """How many times the agreed date or the forecast moved, not counting what was undone (the peek's "Moved N times")."""
    return sum(1 for en in entries if en["kind"] in ("rebaseline", "forecast") and not en["undone"])


# ── the timeline axis, Calendar and Legend ───────────────────────────────────

def clamp_zoom(z):
    """A zoom between 70% and 300% (0.7 to 3.0); 1.0 when it isn't a number."""
    try:
        return max(ZOOM_MIN, min(ZOOM_MAX, float(z)))
    except (TypeError, ValueError):
        return 1.0


YEAR_MIN, YEAR_MAX, MAX_TICKS = 2000, 2100, 200


def in_range(iso):
    """True for a real day in the years 2000 to 2100. Anything else (a typo such as 0026 or 2126, a year past 9999, text that
    is not a date) is not drawn on the axis or in the Calendar; the Timeline names it in a plain note instead."""
    try:
        d = date.fromisoformat(iso) if isinstance(iso, str) and len(iso) == 10 else None
    except ValueError:
        d = None
    return d is not None and YEAR_MIN <= d.year <= YEAR_MAX


def mark_dates(rows):
    """Every date the rows draw: solid marks and ghosts (milestone_rows' or for_client's output), in the years 2000 to 2100."""
    return [m["date"] for r in rows for m in (r["marks"]["solid"], r["marks"]["ghost"]) if m and in_range(m["date"])]


def far_rows(rows):
    """The rows with a mark outside the range: the Timeline leaves them off its axis and names them in a note."""
    return [r for r in rows if any(m and not in_range(m["date"]) for m in (r["marks"]["solid"], r["marks"]["ghost"]))]


def timeline_span(rows, today):
    """(start, end) of the timeline's axis as YYYY-MM-DD, both the first of a month: 20 days before the earliest mark (or today)
    and 45 days after the latest, as the prototype draws it. `end` is exclusive."""
    dates = sorted(mark_dates(rows) + [today])
    start = (_d(dates[0]) - timedelta(days=LEAD_DAYS)).replace(day=1)
    end = (_d(dates[-1]) + timedelta(days=TAIL_DAYS)).replace(day=1)
    return start.isoformat(), end.isoformat()


def _month_end(y, m):
    return (date(y + (m == 12), m % 12 + 1, 1) - timedelta(days=1))


def bucket_key(kind, iso):
    """The key of the bucket (see `buckets`) that holds the date `iso`."""
    d = _d(iso)
    if kind == "week":
        return (d - timedelta(days=d.weekday())).isoformat()
    if kind == "month":
        return iso[:7]
    if kind == "quarter":
        return "%d-Q%d" % (d.year, (d.month - 1) // 3 + 1)
    raise ValueError("kind must be week, month or quarter")


def buckets(kind, start, end):
    """The weeks, months or quarters that hold any day from `start` to `end` (both YYYY-MM-DD, inclusive), in order, each whole:
    [{key, start, end, label}] with start and end inclusive. A week runs Monday to Sunday and is keyed by its Monday ("Week of
    DD-MM-YYYY"); a month by "YYYY-MM" ("October 2026"); a quarter by "YYYY-Qn" ("Q4 2026", with its three month keys in
    `months`)."""
    if kind not in ("week", "month", "quarter"):
        raise ValueError("kind must be week, month or quarter")
    if _d(start) > _d(end):
        return []
    out, key, last = [], bucket_key(kind, start), bucket_key(kind, end)
    while True:
        if kind == "week":
            s = _d(key)
            b = {"key": key, "start": key, "end": (s + timedelta(days=6)).isoformat(), "label": "Week of " + shown(key)}
            nxt = (s + timedelta(days=7)).isoformat()
        elif kind == "month":
            y, m = int(key[:4]), int(key[5:7])
            b = {"key": key, "start": "%s-01" % key, "end": _month_end(y, m).isoformat(),
                 "label": "%s %d" % (MONTHS[m - 1], y)}
            nxt = "%04d-%02d" % (y + (m == 12), m % 12 + 1)
        else:
            y, q = int(key[:4]), int(key[-1])
            first = (q - 1) * 3 + 1
            b = {"key": key, "start": "%04d-%02d-01" % (y, first), "end": _month_end(y, first + 2).isoformat(),
                 "label": "Q%d %d" % (q, y), "months": ["%04d-%02d" % (y, first + i) for i in range(3)]}
            nxt = "%d-Q%d" % (y + (q == 4), q % 4 + 1)
        out.append(b)
        if key == last:
            return out
        key = nxt


MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November",
          "December")


def calendar_chips(rows):
    """{YYYY-MM-DD: [chip, ...]} for the Calendar: a chip on each milestone's solid mark, and a ghost chip ("Expected: ...") on
    the expected date of one that has slipped. A chip: id, name, state, colour, mark, ghost. Solid chips come before ghosts."""
    out = {}
    for ghost in (False, True):
        for r in rows:
            m = r["marks"]["ghost" if ghost else "solid"]
            if m:
                out.setdefault(m["date"], []).append({"id": r["id"], "name": r["name"], "state": r["state"], "colour": r["colour"],
                                                      "mark": r["mark"], "ghost": ghost})
    return out


def legend(client=False):
    """The Legend as data: the six states in order, then Expected and Today. `word` is what the page says (the client's word
    when `client`), with `colour`, `mark` and what it `means`."""
    out = [{"state": s, "word": ms.client_word(s) if client else s, "colour": LOOK[s][0], "mark": LOOK[s][1], "means": LOOK[s][2]}
           for s in LEGEND_STATES]
    out.append({"state": "Expected", "word": "Expected", "colour": None, "mark": "ghost",
                "means": "Where a slipped milestone is now expected; a dashed line joins it to its agreed date"})
    out.append({"state": "Today", "word": "Today", "colour": None, "mark": "today-line",
                "means": "The line on the timeline; the blue date on the calendar"})
    return out


# ── Rebaseline ───────────────────────────────────────────────────────────────

def rebaseline_request(row, new_date=None, agreed_with=None, reason=None, source=None, today=None, decided_on=None):
    """Check a rebaseline and build the call for it. `row` is the milestone's row. `new_date` (YYYY-MM-DD or DD-MM-YYYY) is
    where the agreed date moves to; when it's left out, it is the date the milestone is now expected, which needs the milestone to
    have slipped. An agreed date typed in is allowed only for a milestone that has slipped too (the draft: "Rebaseline (only
    when slipped)"), and it must be later than the current agreed date and not before today. The writer refuses a rebaseline without who agreed it, the reason
    and the source, so they're asked for here.

    Returns (request, errors). On success request is {"changes", "rebaseline"} and errors is []; use it as
    `step.update("milestones", row["id"], request["changes"], rebaseline=request["rebaseline"])`. On failure request is None
    and errors lists, in plain words, everything to put right. A forecast earlier than the new agreed date moves with it."""
    errors, on = [], today or ms.today()
    base, status = row.get("baseline_date"), row.get("status") or "Planned"
    if status != "Planned":
        errors.append("Only a planned milestone can be rebaselined; this one is %s." % status.lower())
    elif not base:
        errors.append("This milestone has no agreed date yet, so there is nothing to rebaseline. Set its agreed date instead.")
    to, slipped = None, False
    can = status == "Planned" and bool(base)
    if can:
        slipped = (ms.slip_days(row, on) or 0) > 0
    if new_date in (None, ""):
        if can and slipped:
            to = expected_date(row, on)
        elif can:
            errors.append("This milestone hasn't slipped, so give the new agreed date.")
    else:
        to = parse_date(new_date)
        if to is None:
            errors.append("The new agreed date isn't a date I can read. Write it as DD-MM-YYYY, for example 31-01-2027.")
        elif can and not slipped:
            errors.append("This milestone hasn't slipped, so its agreed date can't be moved yet.")
        elif can and to == base:
            errors.append("The new agreed date is the same as the current one (%s)." % shown(base))
        elif can and to < base:
            errors.append("The new agreed date must be later than the current one (%s)." % shown(base))
        elif can and to < on:
            errors.append("The new agreed date can't be before today (%s)." % shown(on))
    who = ", ".join(str(w).strip() for w in agreed_with if str(w).strip()) if isinstance(agreed_with, (list, tuple)) \
        else str(agreed_with or "").strip()
    reason, source = str(reason or "").strip(), str(source or "").strip()
    if not who:
        errors.append("Say who agreed the new date.")
    if not reason:
        errors.append("Give the reason the agreed date is moving.")
    if not source:
        errors.append("Give the source: where it was agreed, for example the meeting or the email.")
    when = None
    if decided_on not in (None, ""):
        when = parse_date(decided_on)
        if when is None:
            errors.append("The date the decision was made isn't a date I can read. Write it as DD-MM-YYYY.")
        elif when > on:
            errors.append("The decision can't be dated in the future (%s)." % shown(when))
    if errors:
        return None, errors
    changes = {"baseline_date": to}
    fc = row.get("forecast_date")
    if fc and fc < to:
        changes["forecast_date"] = to
    rb = {"agreed_with": who, "reason": reason, "source": source}
    if when:
        rb["date"] = when
    return {"changes": changes, "rebaseline": rb}, []
