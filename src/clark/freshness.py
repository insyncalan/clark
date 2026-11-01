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
MAX_DAYS = 3650                      # ten years; a larger number is a slip of the finger, not a review period
CLOSED = ("Closed", "Cancelled", "Made", "Withdrawn")          # the Work items list's "not open" (workItems.js isOpen)
PERSON_ROUTES = ("dashboard",)


DAYS_WORDS = "Use a whole number of days from 1 to %d. The setting stays as it was." % MAX_DAYS
_WHOLE = re.compile(r"[0-9]{1,5}")


def check_days(value):
    """The "Not reviewed after (days)" setting, checked. Takes what was typed or sent and gives back
    {"ok": True, "days": n} or {"ok": False, "message": plain words}. A whole number from 1 to MAX_DAYS is accepted (a number or its
    digits, spaces round it allowed); 0, a negative, a fraction, a true or false, an empty value and anything else is refused, and
    the caller keeps the old number. The page (reviewSetting.js parseReviewDays) says the same words."""
    if isinstance(value, bool):
        return {"ok": False, "message": DAYS_WORDS}
    text = str(value).strip() if isinstance(value, (int, str)) else ""
    if _WHOLE.fullmatch(text):
        n = int(text)
        if 1 <= n <= MAX_DAYS:
            return {"ok": True, "days": n}
    return {"ok": False, "message": DAYS_WORDS}


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


def _has_day(stamp):
    """True when calendar_day(stamp) would give a day. Reading the stamp is enough away from the ends of the calendar, where a
    zone change cannot overflow (the conversion to the local zone is the slow part, and a history has thousands of stamps)."""
    try:
        return 1 < parse(stamp).year < 9999 or calendar_day(stamp) is not None
    except (ValueError, TypeError, OverflowError):
        return False


def _ordered(events):
    return sorted((e for e in events or [] if _has_day(e.get("at"))), key=lambda e: (str(e["at"]), e.get("event_id") or 0))


def _raised(ev, tz=None):
    return calendar_day(ev[0]["at"], tz).isoformat() if ev else None


def _last_reviewed(ev, tz=None):
    people = [e for e in ev if by_person(e)]
    return calendar_day(people[-1]["at"], tz).isoformat() if people else None


def raised(events, tz=None):
    """The day of the first history row, as YYYY-MM-DD, or None when there is no history."""
    return _raised(_ordered(events), tz)


def last_reviewed(events, tz=None):
    """The day of the latest change made by a person, as YYYY-MM-DD, or None when no person has changed the item."""
    return _last_reviewed(_ordered(events), tz)


def days_between(earlier, later):
    """Plain calendar days from `earlier` to `later` (YYYY-MM-DD each), or None if either is not a real day."""
    a, b = _day(earlier), _day(later)
    return None if a is None or b is None else b.toordinal() - a.toordinal()


def not_reviewed(row, events, today, days=DEFAULT_DAYS, tz=None):
    """True when the open item has gone more than `days` calendar days since it was last reviewed (or, never reviewed by a
    person, since it was raised). Closed, archived and history-less items are never flagged."""
    return freshness(row, events, today, days, tz)["not_reviewed"]


def freshness(row, events, today, days=DEFAULT_DAYS, tz=None):
    """What the peek shows: {raised, last_reviewed, days_since, not_reviewed}, dates as YYYY-MM-DD (shown DD-MM-YYYY by the page).
    `days_since` is counted from last reviewed, else raised, else None. The history is put in order once (#158: a page of
    thousands of items asks for this for each of them)."""
    ev = _ordered(events)
    r, l = _raised(ev, tz), _last_reviewed(ev, tz)
    n = days_between(l or r, today)
    return {"raised": r, "last_reviewed": l, "days_since": n, "not_reviewed": bool(is_open(row) and n is not None and n > days)}
