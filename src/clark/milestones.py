"""Milestone state, slip and the original date (#32; BRD FR-50).

Copied from creaite v2.6.9 (db5adb2): MS_STATES, MS_RANK, MS_CLIENT_WORD, suggested_state and milestone_state from
system/scripts/tracker.py; slip_days from the cockpit's slip in system/scripts/build_dashboard.py (milestones); and
original_date from tracker.py's milestone_original, made a pure function over change_log rows so the store (#31) reads
them and this module needs no database. clark adds one state, Forecast (the owner, 27-10-2026: "add a 'forecast' state to
milestones"): set by the user while the date isn't agreed yet. Rules: docs/handoff/data-model.md, "Milestone states".

A row is a dict with the milestones table's columns. Dates are YYYY-MM-DD text, which sorts as dates do.
"""
from datetime import date

MS_STATES = ("Achieved", "On track", "At risk", "Slipped", "Overdue")
MS_RANK = {s: i for i, s in enumerate(MS_STATES)}
MS_CLIENT_WORD = {"Achieved": "Achieved", "On track": "On track", "At risk": "At risk", "Slipped": "Expected later",
                  "Overdue": "Late"}     # the owner, 11-10-2026: a late milestone reads "Late"; BL-299: On track is "On track"

# clark: + Forecast (the owner, 27-10-2026). It is only ever set by the user, has no rank (a date not yet agreed is never
# "better than the dates suggest", so it needs no reason), and reads "Forecast" to a client, as in the prototype.
FORECAST = "Forecast"
STATES = MS_STATES + (FORECAST,)
CLIENT_WORD = {**MS_CLIENT_WORD, FORECAST: "Forecast"}


def today():
    """Today's date as YYYY-MM-DD."""
    return date.today().isoformat()


def suggested_state(row, on=None):
    """What the dates say: Achieved when Done; Overdue when the agreed date has passed; Slipped when the forecast is later than
    the agreed date; On track otherwise. At risk is only ever the user's call."""
    on = on or today()
    if row.get("status") == "Done":
        return "Achieved"
    base = row.get("baseline_date")
    fc = row.get("forecast_date") or base
    if base and base < on:
        return "Overdue"
    if base and fc and fc > base:
        return "Slipped"
    return "On track"


def milestone_state(row, on=None):
    """The state shown: Achieved when Done, the user's when they set one (At risk, or clark's Forecast), else the dates' suggestion."""
    if row.get("status") == "Done":
        return "Achieved"
    if row.get("state_set") and row.get("state"):
        return row["state"]
    return suggested_state(row, on)


def needs_reason(row, on=None):
    """True when the user's state is better than the dates suggest, which needs a one-line reason (creaite's check_milestone
    rule, for #31's checks). Forecast never does."""
    state = row.get("state")
    if not (row.get("state_set") and state) or state in ("Achieved", FORECAST):
        return False
    return MS_RANK[state] < MS_RANK[suggested_state(row, on)]


def client_word(state):
    """What a client reads for `state`: creaite's words, so Slipped is "Expected later" and Overdue is "Late"."""
    return CLIENT_WORD[state]


def slip_days(row, on=None):
    """Days a Planned milestone runs past its agreed date, as creaite's cockpit counts it: the expected date is the forecast
    (or the agreed date when there is none), or today if the agreed date has already passed, whichever is later. 0 when on
    time; None when the milestone isn't Planned or has no agreed date."""
    if row.get("status", "Planned") != "Planned" or not row.get("baseline_date"):
        return None
    on = date.fromisoformat(on or today())
    agreed = date.fromisoformat(row["baseline_date"])
    expected = max(date.fromisoformat(row.get("forecast_date") or row["baseline_date"]), on if agreed < on else agreed)
    return (expected - agreed).days


def original_date(changes, item_id, current=None, undone=()):
    """The Original date: the first agreed date in change_log (skipping undone applies and undo rows), else the current one.
    `changes` are change_log rows (dicts) in the order written; `undone` holds the apply_ids whose applies were undone."""
    undone = set(undone)
    for c in changes:
        if (c.get("tbl") == "milestones" and c.get("item_id") == item_id and c.get("field") == "baseline_date"
                and c.get("op") != "undo" and c.get("new_value") is not None and c.get("apply_id") not in undone):
            return c["new_value"]
    return current
