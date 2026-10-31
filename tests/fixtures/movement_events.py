"""Planted histories for the Movement tests (#136): milestone rows and the Movement read's reply, all made up.

Not a test file. Load it with `load()` (tests/fixtures is not a package). Events have the shape history.history() gives
(event_id, at, step, by_user, table, ref, field, before, after, op, route, place, origin, actor, undoes, is_undo, undone_by,
in_force), so milestone_rows.movement runs on them unchanged. Project ABC, "today" is TODAY.

  rows()        the project's milestone rows (the table's columns), including a Done, a Cancelled, a Forecast and an archived one
  reply()       the read's reply: {"project", "milestones": {id: {"original", "total", "events"}}, "truncated"}
  MARKERS       strings planted in the internal note, the state reason, the reason, who agreed and the source; none may reach a
                published file, and the internal note's must not reach the Movement view either
"""
import importlib.util
from pathlib import Path

TODAY = "2026-10-28"
CODE = "ABC"
INTERNAL_MARKER = "PLANTED-INTERNAL-NOTE-5521 supplier wants more money"
REASON_MARKER = "PLANTED-REASON-7710 build ran long"
WHO_MARKER = "PLANTED-AGREED-WITH-3302 Pat Placeholder"
SOURCE_MARKER = "PLANTED-SOURCE-9184 steering minutes"
STATE_REASON_MARKER = "PLANTED-STATE-REASON-6043 waiting on the vendor"
MARKERS = (INTERNAL_MARKER, REASON_MARKER, WHO_MARKER, SOURCE_MARKER, STATE_REASON_MARKER)

M_REBASED, M_QUIET, M_FORECAST_BACK, M_UNDONE, M_MANY, M_ARCHIVED, M_DONE, M_CANCELLED, M_NO_AGREED = (
    "ABC-M-00%d" % i for i in range(1, 10))

_next = [0]


def ev(ref, step, field, before, after, minute=0, **more):
    """One history event. `minute` places it in time (2026-10-01 plus that many minutes, UTC); event_id counts up."""
    _next[0] += 1
    n = _next[0]
    base = {"event_id": n, "at": "2026-10-%02dT%02d:%02d:00.000Z" % (1 + minute // 1440, minute // 60 % 24, minute % 60),
            "step": step, "by_user": "Test Owner", "table": "milestones", "ref": ref, "field": field, "before": before,
            "after": after, "op": "update", "route": "dashboard", "place": "dashboard", "origin": "user", "actor": "Test Owner",
            "undoes": None, "is_undo": False, "undone_by": None, "in_force": True}
    base.update(more)
    return base


def row(mid, name, **more):
    base = {"id": mid, "project": CODE, "name": name, "status": "Planned", "baseline_date": None, "forecast_date": None,
            "state": None, "state_set": 0, "state_reason": None, "sort_order": 0, "archived": 0, "client_visible": 1,
            "workstream": None, "owner": "Test Owner", "percent_complete": None, "actual_date": None, "internal_note": None,
            "client_message": None, "movement": None, "description": None}
    base.update(more)
    return base


def rows():
    return [
        row(M_REBASED, "Pilot live", baseline_date="2026-11-24", forecast_date="2026-12-08", state="At risk", state_set=1,
            state_reason=STATE_REASON_MARKER, internal_note=INTERNAL_MARKER, percent_complete=40),
        row(M_QUIET, "Training done", baseline_date="2026-10-20"),
        row(M_FORECAST_BACK, "Data moved across", baseline_date="2026-11-10", forecast_date="2026-11-10"),
        row(M_UNDONE, "Go-live review", baseline_date="2026-11-30"),
        row(M_MANY, "Handover", baseline_date="2026-12-01", forecast_date="2026-12-01"),
        row(M_ARCHIVED, "Old workshop", baseline_date="2026-09-01", archived=1),
        row(M_DONE, "Kick-off", status="Done", baseline_date="2026-10-01", actual_date="2026-10-02"),
        row(M_CANCELLED, "Spin-off", status="Cancelled", baseline_date="2026-11-01"),
        row(M_NO_AGREED, "Phase two start", forecast_date="2027-02-01", state="Forecast", state_set=1),
    ]


def events():
    """{milestone id: [event, ...]} oldest first."""
    _next[0] = 0
    out = {}
    # M-001: created, rebaselined (two decisions named; the last is the one the store wrote), forecast moved, state set,
    # internal note changed.
    out[M_REBASED] = [
        ev(M_REBASED, 1, "id", None, M_REBASED, 0),
        ev(M_REBASED, 1, "baseline_date", None, "2026-11-03", 0),
        ev(M_REBASED, 1, "forecast_date", None, "2026-11-10", 0),
        ev(M_REBASED, 2, "baseline_date", "2026-11-03", "2026-11-24", 100),
        ev(M_REBASED, 2, "forecast_date", "2026-11-10", "2026-11-24", 100),
        ev(M_REBASED, 2, "note", None, "%s Agreed with %s. Source: %s. See ABC-D-004. Decision ABC-D-011"
           % (REASON_MARKER, WHO_MARKER, SOURCE_MARKER), 100),
        ev(M_REBASED, 3, "forecast_date", "2026-11-24", "2026-12-08", 200),
        ev(M_REBASED, 4, "state", None, "At risk", 300),
        ev(M_REBASED, 4, "state_reason", None, STATE_REASON_MARKER, 300),
        ev(M_REBASED, 5, "internal_note", None, INTERNAL_MARKER, 400),
    ]
    out[M_QUIET] = []
    # M-003: forecast moved out and put back (two steps, both in force).
    out[M_FORECAST_BACK] = [
        ev(M_FORECAST_BACK, 10, "forecast_date", "2026-11-10", "2026-11-17", 500),
        ev(M_FORECAST_BACK, 11, "forecast_date", "2026-11-17", "2026-11-10", 600),
    ]
    # M-004: a rebaseline that was undone (rows marked not in force; the undo's own rows are is_undo).
    out[M_UNDONE] = [
        ev(M_UNDONE, 20, "baseline_date", "2026-11-30", "2026-12-14", 700, in_force=False, undone_by=9001),
        ev(M_UNDONE, 20, "note", None, "Vendor slipped. Decision ABC-D-020", 700, in_force=False, undone_by=9001),
        ev(M_UNDONE, 21, "baseline_date", "2026-12-14", "2026-11-30", 710, is_undo=True, op="undo", undoes=9001),
    ]
    # M-005: 120 forecast moves, each a step (the read keeps the latest 50 of them).
    many, d = [], 1
    for i in range(120):
        nxt = "2026-12-%02d" % (2 + (i + 1) % 20)
        many.append(ev(M_MANY, 100 + i, "forecast_date", "2026-12-%02d" % (1 + d % 20) if i else "2026-12-01", nxt, 800 + i))
        d = (i + 1) % 20 + 1
    out[M_MANY] = many
    # An archived milestone is never in the reply; its history is planted here to prove it.
    out[M_ARCHIVED] = [ev(M_ARCHIVED, 200, "baseline_date", "2026-08-01", "2026-09-01", 900)]
    return out


def reply():
    evs = events()
    block = {}
    for mid, items in evs.items():
        if mid == M_ARCHIVED:
            continue
        newest = list(reversed(items))
        block[mid] = {"original": next((e["after"] for e in items if e["field"] == "baseline_date" and e["after"]
                                        and not e["is_undo"] and e["in_force"]), None),
                      "total": len(items), "events": newest[:50]}
    return {"project": CODE, "milestones": block, "truncated": False}


def load():
    """This module, loaded from its path (for a test, since tests/fixtures is not a package)."""
    spec = importlib.util.spec_from_file_location("movement_events", Path(__file__))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
