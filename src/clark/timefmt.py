"""How clark shows a time (#75; "All times need to be local time").

The store keeps every time as UTC to the millisecond ("2026-10-28 14:05:09.123", as datetime('now') in schema.sql and
store.now()), so times compare and sort the same on every machine. They are converted only here, at the point of showing, to
the time on the user's own clock, written DD-MM-YYYY HH:MM. Dates alone (due, agreed, week ending) are calendar dates and
are never passed through this module: a zone must not move them.

Standard library only, Python 3.9.
"""
import re
from datetime import datetime, timedelta, timezone

STAMP = re.compile(r"(\d{4})-(\d\d)-(\d\d)[T ](\d\d):(\d\d)(?::(\d\d)(?:\.(\d+))?)?\s*(Z|[+-]\d\d:?\d\d)?\Z")
COMPACT = re.compile(r"(\d{4})(\d\d)(\d\d)T(\d\d)(\d\d)(\d\d)Z")      # a backup's file name (#86): 20261028T143005Z, UTC; T and Z required


def parse(stamp):
    """A stored time as an aware datetime. A time with no zone is UTC (that is how the store writes them); one with Z or an
    offset keeps it. A backup's compact name time (20261028T143005Z) is UTC. Anything else raises ValueError."""
    text = str(stamp).strip()
    c = COMPACT.fullmatch(text)
    if c:
        try:
            return datetime(*(int(x) for x in c.groups()), tzinfo=timezone.utc)
        except ValueError as e:            # month 13, day 32: not a time
            raise ValueError(f"{stamp!r} is not a time clark stores") from e
    m = STAMP.fullmatch(text)
    if not m:
        raise ValueError(f"{stamp!r} is not a time clark stores")
    y, mo, d, h, mi, s, frac, zone = m.groups()
    micro = int((frac or "0")[:6].ljust(6, "0"))
    dt = datetime(int(y), int(mo), int(d), int(h), int(mi), int(s or 0), micro, tzinfo=timezone.utc)
    if zone and zone != "Z":
        sign = 1 if zone[0] == "+" else -1
        digits = zone[1:].replace(":", "")
        dt = dt.replace(tzinfo=timezone(sign * timedelta(hours=int(digits[:2]), minutes=int(digits[2:]))))
    return dt


def local_text(stamp):
    """`stamp` (a stored time) as the user's local time, DD-MM-YYYY HH:MM. An empty value is returned as it is, and text that
    is not a time is returned unchanged, so a screen never fails to draw over one odd value."""
    if stamp is None or stamp == "":
        return stamp
    try:
        return parse(stamp).astimezone().strftime("%d-%m-%Y %H:%M")
    except (ValueError, OverflowError, OSError):        # a year-9999 time east of UTC overflows; an odd one never stops a screen
        return stamp


_DAY = re.compile(r"(\d{4})-(\d\d)-(\d\d)")


def day_text(value, prefix=False):
    """A stored calendar day (YYYY-MM-DD) as DD-MM-YYYY. Only a real day is rewritten (29 Feb in a leap year, never 30 Feb or month
    13); anything else, empty included, comes back as it is, as text. With `prefix`, a day followed by a space or T and a time
    ("2026-10-25 14:00:00") is read as its day. A day is never moved by a zone."""
    text = "" if value is None else str(value)
    m = _DAY.match(text)
    if not m or (len(text) > 10 and not (prefix and text[10] in " T")) :
        return text
    try:
        datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return text
    return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
