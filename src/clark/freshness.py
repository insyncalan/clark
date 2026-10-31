"""Data-freshness flags: the pure rules (#119; BRD FR-35a, FR-43a).

No page, no server, no database and no clock: every function takes the rows it works on and "today" (YYYY-MM-DD, the user's own
calendar day) and gives back plain values, so a test can fix the date. Nothing here is stored: no new columns, everything is
worked out from an item's history (the events `history.history` returns, oldest or newest first; this module sorts them).
Standard library only, Python 3.9.

The rules
- Raised is the date of the item's first history row. Last reviewed is the date of the latest change made by a person: an event
  whose actor is "you" and whose route is the dashboard. A change by ask clark (actor "clark" or route "assistant"), an import
  (route excel, team, client or migrate) or an undo (route undo, or is_undo) is not a review. An item with no such change has
  no Last reviewed, and is then judged from Raised.
- Times are stored in UTC. They are turned into the user's calendar day (`tz`, default the machine's own zone) and only then
  counted, so a late evening change lands on the day the user saw it.
- "Not reviewed in N days" counts plain calendar days between two dates (date ordinals), never 24-hour spans, so midnight and a
  clock change cannot move it. An item is flagged when the days since it was last reviewed (or raised) are more than N: exactly N
  days is not yet flagged. N defaults to 14 and is passed in.
- Closed, cancelled, made and withdrawn items and archived items are never flagged. A row with no history is never flagged
  (nothing is known), and a date that is not a real day gives no flag.
"""
import re
from datetime import date

from clark.timefmt import parse

DEFAULT_DAYS = 14
CLOSED = ("Closed", "Cancelled", "Made", "Withdrawn")          # the Work items list's "not open" (workItems.js isOpen)
PERSON_ROUTES = ("dashboard",)


def is_open(row):
    """Open means not closed, cancelled, made or withdrawn and not archived."""
    return row.get("status") not in CLOSED and not row.get("archived")


def by_person(event):
    """True when the change was made by a person: not ask clark, not an import, not an undo."""
    return (event.get("actor") == "you" and event.get("route") in PERSON_ROUTES and not event.get("is_undo")
            and event.get("undoes") is None)


def calendar_day(stamp, tz=None):
    """A stored time as the user's calendar day (a `date`), or None when it is not a time."""
    try:
        return parse(stamp).astimezone(tz).date()
    except (ValueError, TypeError, OverflowError):
        return None


# Only YYYY-MM-DD, nothing else: no time part, no ISO week date (2026-W44-3), no ordinal or compact form (20261029). Python 3.11 and
# later read those forms in fromisoformat, the page (workItems.js dayNumber) does not, and publish.build uses the same shape.
DAY = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")

# Trap: the page falls back to a row's `raised` (filters.js notReviewed). If work-item rows ever get a typed `raised` of their own,
# rename this key (for example first_seen) so the two cannot be confused.


def _day(iso):
    try:
        return date.fromisoformat(iso) if isinstance(iso, str) and DAY.fullmatch(iso) else None
    except ValueError:
        return None


def _ordered(events):
    return sorted((e for e in events or [] if calendar_day(e.get("at")) is not None), key=lambda e: (str(e["at"]), e.get("event_id") or 0))


def raised(events, tz=None):
    """The day of the first history row, as YYYY-MM-DD, or None when there is no history."""
    ev = _ordered(events)
    return calendar_day(ev[0]["at"], tz).isoformat() if ev else None


def last_reviewed(events, tz=None):
    """The day of the latest change made by a person, as YYYY-MM-DD, or None when no person has changed the item."""
    ev = [e for e in _ordered(events) if by_person(e)]
    return calendar_day(ev[-1]["at"], tz).isoformat() if ev else None


def days_between(earlier, later):
    """Plain calendar days from `earlier` to `later` (YYYY-MM-DD each), or None if either is not a real day."""
    a, b = _day(earlier), _day(later)
    return None if a is None or b is None else b.toordinal() - a.toordinal()


def not_reviewed(row, events, today, days=DEFAULT_DAYS, tz=None):
    """True when the open item has gone more than `days` calendar days since it was last reviewed (or, never reviewed by a
    person, since it was raised). Closed, archived and history-less items are never flagged."""
    if not is_open(row):
        return False
    since = last_reviewed(events, tz) or raised(events, tz)
    n = days_between(since, today)
    return n is not None and n > days


def freshness(row, events, today, days=DEFAULT_DAYS, tz=None):
    """What the peek shows: {raised, last_reviewed, days_since, not_reviewed}, dates as YYYY-MM-DD (shown DD-MM-YYYY by the page).
    `days_since` is counted from last reviewed, else raised, else None."""
    r, l = raised(events, tz), last_reviewed(events, tz)
    return {"raised": r, "last_reviewed": l, "days_since": days_between(l or r, today),
            "not_reviewed": not_reviewed(row, events, today, days, tz)}
