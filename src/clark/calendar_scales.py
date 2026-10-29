"""The milestone Calendar's Week, Month and Quarter, without the page (#76; "default view is month but we
should have switches for week, month, quarter"; "in Quarter if I click on the month name it presents that month view to me").

Pure functions, in the style of milestone_rows.py: no database, no clock (give `today`), no page. Standard library only.

A pane is keyed as milestone_rows.buckets keys it: a week by its Monday ("2026-10-05"), a month by "2026-10", a quarter by
"2026-Q4". Weeks run Monday to Sunday. Dates are YYYY-MM-DD in every value and DD-MM-YYYY in every sentence. The chips on each
day come from milestone_rows.calendar_chips, which this module does not repeat. The published page uses the same functions over
milestone_rows.for_client's rows.

  normalise_scale / pick_scale / remember_key   the scale, its default and where a place remembers it
  today_key / step / title / panes              which pane, the next and the last, its heading, and all the panes to draw
  week_days / month_grid / quarter_months       what a pane holds
  open_month_from_quarter                       a month's name in Quarter opens that month
"""
from datetime import date, timedelta

from clark import milestone_rows as mr

SCALES = ("week", "month", "quarter")
DEFAULT_SCALE = "month"
WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
_RANGE = "The calendar can't go that far."


def normalise_scale(value):
    """`value` if it is week, month or quarter; otherwise month (the default)."""
    return value if value in SCALES else DEFAULT_SCALE


def remember_key(place):
    """Where a place remembers its scale (the prototype's "msv.calv.<place>"), for the page's own store."""
    place = str(place or "").strip()
    if not place:
        raise ValueError("Say which place the calendar is in.")
    return "msv.calv." + place


def pick_scale(stored):
    """The scale to show from what was remembered (nothing, or something odd, gives month)."""
    return normalise_scale(stored)


def _scale(scale):
    if scale not in SCALES:
        raise ValueError("The calendar scale must be week, month or quarter.")
    return scale


def _bad(scale, key):
    return ValueError("%r is not a %s the calendar knows." % (key, scale))


def _parse(scale, key):
    """A pane key as numbers: a date (week), (year, month) or (year, quarter). ValueError in plain words when it isn't one."""
    _scale(scale)
    try:
        text = str(key)
        if scale == "week":
            d = date.fromisoformat(text)
            if len(text) != 10 or d.weekday() != 0:
                raise ValueError
            return d
        if scale == "month":
            if len(text) != 7 or text[4] != "-":
                raise ValueError
            y, m = int(text[:4]), int(text[5:])
            date(y, m, 1)
            return y, m
        if len(text) != 7 or text[4:6] != "-Q" or text[6] not in "1234":
            raise ValueError
        y = int(text[:4])
        date(y, 1, 1)
        return y, int(text[6])
    except (ValueError, TypeError):
        raise _bad(scale, key) from None


def today_key(scale, today):
    """The key of the pane that holds `today` (YYYY-MM-DD)."""
    _scale(scale)
    try:
        return mr.bucket_key(scale, today)
    except (ValueError, TypeError):
        raise ValueError("%r is not a date." % (today,)) from None


def step(scale, key, direction):
    """The pane before (direction -1) or after (+1) `key`: a week is 7 days, a month a month, a quarter three months. It works
    for any key, with or without milestones in it, and across year ends."""
    if direction not in (-1, 1):
        raise ValueError("Step by -1 (earlier) or 1 (later).")
    p = _parse(scale, key)
    try:
        if scale == "week":
            return (p + timedelta(days=7 * direction)).isoformat()
        y, n = p
        n += direction
        if scale == "month":
            y, n = y + (n - 1) // 12, (n - 1) % 12 + 1
            date(y, n, 1)
            return "%04d-%02d" % (y, n)
        y, n = y + (n - 1) // 4, (n - 1) % 4 + 1
        date(y, 1, 1)
        return "%04d-Q%d" % (y, n)
    except (OverflowError, ValueError):
        raise ValueError(_RANGE) from None


def title(scale, key):
    """The heading in plain words: "Week of 05-10-2026", "October 2026", "Q4 2026"."""
    p = _parse(scale, key)
    if scale == "week":
        return "Week of " + mr.shown(key)
    if scale == "month":
        return "%s %d" % (mr.MONTHS[p[1] - 1], p[0])
    return "Q%d %d" % (p[1], p[0])


def panes(rows, today, scale):
    """The keys of every pane to draw, in order: from the earliest to the latest of the marks (solid and expected) and today,
    so the pane that holds today is always there, even with no milestones. `rows` are milestone_rows' or for_client's output."""
    _scale(scale)
    dates = sorted(mr.mark_dates(rows or ()) + [today])
    return [b["key"] for b in mr.buckets(scale, dates[0], dates[-1])]


def _day(d, today, outside=False):
    return {"date": d.isoformat(), "day": d.day, "weekday": WEEKDAYS[d.weekday()], "weekend": d.weekday() >= 5,
            "today": d.isoformat() == today, "outside": outside}


def week_days(key, today=None):
    """The seven days of the week `key`, Monday to Sunday: date, day (the number), weekday (Mon...), weekend, today, outside
    (always False)."""
    start = _parse("week", key)
    return [_day(start + timedelta(days=i), today) for i in range(7)]


def month_grid(key, today=None):
    """The month as weeks of seven days, Monday first: a list of weeks, each a list of the same day dicts as week_days. The
    days before the 1st and after the last belong to the neighbouring months and are marked outside."""
    y, m = _parse("month", key)
    first = date(y, m, 1)
    last = mr._month_end(y, m)
    d = first - timedelta(days=first.weekday())
    weeks = []
    while d <= last:
        weeks.append([_day(d + timedelta(days=i), today, outside=not (first <= d + timedelta(days=i) <= last))
                      for i in range(7)])
        d += timedelta(days=7)
    return weeks


def quarter_months(key):
    """The three month keys of the quarter `key`, in order."""
    y, q = _parse("quarter", key)
    return ["%04d-%02d" % (y, (q - 1) * 3 + i) for i in (1, 2, 3)]


def open_month_from_quarter(month_key):
    """What to show when a month's name is clicked in Quarter: that month, in the Month scale."""
    _parse("month", month_key)
    return {"scale": "month", "key": month_key}
