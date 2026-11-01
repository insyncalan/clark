"""What the Milestones Movement page draws (#136; BRD FR-50 to FR-53), without the page, the database or the clock.

Pure functions over the project's milestone rows and the Movement read's reply (design-136, B1). Standard library only, and
Python 3.9-safe. Give `today` as YYYY-MM-DD.

  view(rows, reply, today)         -> {"sentence", "worst", "rows", "milestones"}: what the page draws (internal only)
  confirm_text(row, to, today)     -> the words of the "Move the agreed date" confirm
  refusal_text(row, to, ...)       -> plain-words reasons a move can't go ahead ([] when it can)
  toast_hold(), toast_moved(...)   -> the words after Hold and after a move

Everything here is owner-only. Nothing in this module may be published: no publishing module imports it.

The numbers, the dates and the state come from milestone_rows.py and milestones.py, unchanged. Dates are YYYY-MM-DD in every
value and DD-MM-YYYY in every sentence. Wording is in the constants below, pinned by tests/test_movement_view.py.
"""
from clark import milestone_rows as mr
from clark import milestones as ms

# ── wording (design-136, A2 to A4 and E) ─────────────────────────────────────

TAG_UNDONE = "Undone"
TAG_INTERNAL = "Internal only: never published"
HELP_LINE = "Movement is for you and the team: it is never published."
NO_DATE_YET = "No date yet"
NO_AGREED_DATE = "No agreed date yet"
ON_AGREED = "On the agreed date"
AFTER_AGREED = "%s after the agreed date"
BEFORE_AGREED = "%s before the agreed date"
NEVER_MOVED = "Never moved"
MOVED_ONCE = "Moved 1 time"
MOVED_MANY = "Moved %d times"
AGREED_MOVED = "Agreed date moved"
NOTHING_CHANGED = "Nothing has changed since it was first agreed."
OVER_LIMIT_PLAIN = "These changes are too old to show here. The peek's Activity has them all."
OVER_LIMIT = "Showing the latest %d changes. The peek's Activity has them all."
NO_MILESTONES = "No milestones yet."
ALL_ACHIEVED = "Every milestone is achieved."
ONE_BEHIND = "The open milestone is behind its agreed date."
ONE_ON_DATE = "The open milestone is on its agreed date."
ONE_NO_DATE = "The open milestone has no agreed date yet."
SOME_BEHIND = "%d of %d open milestones are behind their agreed date; %d overdue."
WORST = "%s is %s behind the agreed date"
WORST_ORIGINAL = " and %s behind the original"
HOLD_LABEL = "Hold: keep the forecast, agreed date unchanged"
MOVE_LABEL = "Move the agreed date"
KEEP_LABEL = "Keep the date"
CONFIRM = ("Move the agreed date of %s from %s to %s? The original date (%s) is kept and a decision is recorded. "
           "You can undo this.")
TOAST_HOLD = "Hold recorded in the note. Undo."
TOAST_MOVED = "%s: the agreed date is now %s. Undo."
READ_FAILS = "Movement couldn't be loaded. Check that clark is still running, then try again."
ARCHIVED = "That milestone is archived. Restore it first."
NOT_HERE = "That milestone isn't in this project."

PER_MILESTONE = 50                  # events a milestone's list holds (the read's limit; the notice says so)

# What a Movement entry may carry to the page. Anything else, `detail` above all (the internal note's text), is dropped.
ENTRY_KEYS = ("step", "event_id", "at", "at_text", "by", "kind", "text", "why", "decision", "undone", "tag",
              "from_date", "to_date", "days")
# What the read's reply may hold; a key outside these is ignored.
REPLY_KEYS = ("project", "milestones", "truncated")
MILESTONE_KEYS = ("original", "total", "moves", "events")
# Row keys: the whole set the page gets for one open milestone.
ROW_KEYS = ("id", "name", "state", "colour", "mark", "owner", "percent", "agreed", "forecast", "original", "original_text",
            "slip", "variance", "expected", "moved", "moves", "moves_text", "moved_label", "rebaselined", "can_move",
            "entries", "total", "notice", "state_reason", "movement")
ALLOWED_KEYS = frozenset(ROW_KEYS)
SUMMARY_KEYS = ("sentence", "worst", "rows", "tag", "help", "truncated")


# ── small helpers ────────────────────────────────────────────────────────────

def days_text(n):
    """"1 day" or "N days" (FR-50's grammar)."""
    return "%d day%s" % (n, "" if abs(n) == 1 else "s")


def variance_text(slip, state=None):
    """How far a milestone is from its agreed date: "N days after the agreed date", "On the agreed date", or, with no slip (a
    Forecast has none), "No agreed date yet"."""
    if slip is None:
        return NO_AGREED_DATE
    if slip == 0:
        return ON_AGREED
    return (AFTER_AGREED if slip > 0 else BEFORE_AGREED) % days_text(abs(slip))


def moves_text(n):
    """"Never moved", "Moved 1 time" or "Moved N times"."""
    return NEVER_MOVED if n <= 0 else MOVED_ONCE if n == 1 else MOVED_MANY % n


def original_of(original, agreed, forecast):
    """The Original date, never blank: the first agreed date still in force (`original`, from the read); else the current agreed
    date; else the forecast; else None (the page says "No date yet")."""
    return original or agreed or forecast or None


def clean_entry(entry):
    """One Movement entry cut to ENTRY_KEYS, with its tag. An internal-note entry never comes through (see `entries_for`)."""
    out = {k: entry[k] for k in ENTRY_KEYS if k in entry}
    out["tag"] = TAG_UNDONE if entry.get("undone") else ""
    return out


def entries_for(events, milestone_id):
    """The "What changed" lines for one milestone, newest first. The internal note's changes, a line that stands on a note alone
    (it can only come from the internal note) and every `detail` are left out, so no note text can reach the page."""
    out = []
    for en in mr.movement(events or [], milestone_id):
        if en.get("internal") or en.get("kind") in ("internal_note", "note"):
            continue
        out.append(clean_entry(en))
    return out


def _reply_for(reply, milestone_id):
    block = ((reply or {}).get("milestones") or {}).get(milestone_id) or {}
    return {k: block.get(k) for k in MILESTONE_KEYS if k in block}


def _worst_key(r):
    # Worst first: the longest slip, then Overdue before the rest, then the earliest agreed date, then the id.
    return (-(r["slip"] or 0), r["state"] != "Overdue", r["agreed"] is None, r["agreed"] or "", r["id"])


def _row(d, block, today):
    events = block.get("events") or []
    entries = entries_for(events, d["id"])
    n = block["moves"] if isinstance(block.get("moves"), int) else mr.moves(entries)     # the read counts over the whole history, before its cut
    original = original_of(block.get("original"), d["baseline"], d["forecast"])
    total = block.get("total") or len(events)
    slip = d["slip"]
    expected = d["expected"]
    return {
        "id": d["id"], "name": d["name"], "state": d["state"], "colour": d["colour"], "mark": d["mark"], "owner": d["owner"],
        "percent": d["percent"], "agreed": d["baseline"], "forecast": d["forecast"],
        "original": original, "original_text": mr.shown(original) if original else NO_DATE_YET,
        "slip": slip, "variance": variance_text(slip), "expected": expected,
        "moved": n > 0, "moves": n, "moves_text": moves_text(n),
        "moved_label": AGREED_MOVED if (original and d["baseline"] and original != d["baseline"]) else moves_text(n),
        "rebaselined": bool(original and d["baseline"] and original != d["baseline"]),
        "can_move": bool(slip and slip > 0 and d["state"] != ms.FORECAST),
        "entries": entries, "total": total,
        "notice": (OVER_LIMIT % len(entries) if entries else OVER_LIMIT_PLAIN) if total > len(events) else "",
        "state_reason": d["state_reason"], "movement": d["movement"],
    }


def sentence(open_rows):
    """The one sentence about the open milestones, from `view`'s rows (A3)."""
    n = len(open_rows)
    if n == 1:
        r = open_rows[0]
        return ONE_NO_DATE if r["slip"] is None else ONE_BEHIND if r["slip"] > 0 else ONE_ON_DATE
    behind = sum(1 for r in open_rows if r["slip"] and r["slip"] > 0)
    return SOME_BEHIND % (behind, n, sum(1 for r in open_rows if r["state"] == "Overdue"))


def worst_sentence(open_rows):
    """"{Name} is {N days} behind the agreed date and {M days} behind the original." for the worst row, or "" when nothing is
    behind. The second clause only when the original date differs from the agreed one and the milestone is behind it too."""
    if not open_rows or not (open_rows[0]["slip"] or 0) > 0:
        return ""
    r = open_rows[0]
    text = WORST % (r["name"], days_text(r["slip"]))
    if r["rebaselined"] and r["expected"] and r["original"]:
        behind = (mr._d(r["expected"]) - mr._d(r["original"])).days
        if behind > 0:
            text += WORST_ORIGINAL % days_text(behind)
    return text + "."


def view(rows, reply, today):
    """What the Movement page draws. `rows` are the project's milestone rows (the table's columns); `reply` is the Movement read's
    reply (design-136, B1) or None; `today` is YYYY-MM-DD.

    One row per open milestone: Planned and not archived. Done, Cancelled and archived ones are not rows (FR-43c), and an
    archived one is not counted. Worst first. Returns {"sentence", "worst", "rows", "tag", "help", "truncated"}; `rows` carry
    exactly ROW_KEYS. Internal only: it holds names, reasons and who agreed, so it must never feed anything published."""
    live = [r for r in rows or [] if not r.get("archived")]
    reply = reply or {}
    displays = mr.milestone_rows(live, today)
    open_displays = [d for d in displays if d["status"] == "Planned"]
    out = sorted((_row(d, _reply_for(reply, d["id"]), today) for d in open_displays), key=_worst_key)
    if not displays:
        text = NO_MILESTONES
    elif not out:
        text = ALL_ACHIEVED
    else:
        text = sentence(out)
    return {"sentence": text, "worst": worst_sentence(out), "rows": out, "tag": TAG_INTERNAL, "help": HELP_LINE,
            "truncated": bool(reply.get("truncated"))}


# ── Move the agreed date (A4) ────────────────────────────────────────────────

def confirm_text(row, to, today=None, original=None):
    """The words of the confirm for moving a milestone's agreed date to `to` (YYYY-MM-DD or DD-MM-YYYY). `original` is the
    Original date (default: the current agreed date, when it has never moved)."""
    base = row.get("baseline_date")
    new = mr.parse_date(to) or str(to or "")
    orig = original or base
    return CONFIRM % (row.get("name") or "this milestone", mr.shown(base), mr.shown(new), mr.shown(orig))


def refusal_text(row, to=None, agreed_with=None, reason=None, source=None, today=None):
    """Why a move of the agreed date can't go ahead, as plain-words lines (the words of milestone_rows.rebaseline_request,
    reused, not re-worded); [] when it can. An archived milestone reads ARCHIVED."""
    if row.get("archived"):
        return [ARCHIVED]
    _, errors = mr.rebaseline_request(row, to, agreed_with, reason, source, today)
    return errors


def toast_hold():
    return TOAST_HOLD


def toast_moved(name, to):
    """The words after a move: "{name}: the agreed date is now DD-MM-YYYY. Undo."."""
    return TOAST_MOVED % (name, mr.shown(mr.parse_date(to) or to))
