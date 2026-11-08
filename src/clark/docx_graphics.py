"""The pictures in the Word report (#1012): the milestone plan as the main screen draws it, the Health bar and the progress bar.

Each function gives (png bytes, width, height in pixels) from png_draw, or None when there is nothing to draw. A picture holds only
shapes and colours: every colour is a design token (`tok`, the Word build's colour table; the status colours the table does not
carry are read from the look, the same tokens.css), and there is no text in a picture, so no font is needed. Every label is real
Word text in the table beside it. The picture of the plan has one lane for each milestone, in the order of the table under it.

The marks and their colours are the page's (milestone_rows.LOOK, MsMark.jsx): Achieved a green ring with a tick, On track a green
dot, At risk an amber triangle, Slipped a red diamond, Overdue (the client's word is Late) a red disc with a cross, Forecast a
blue dashed ring; a slipped milestone also has a dashed red ring on its expected date joined to the agreed date by a dashed red
line (FR-50); the Today line is navy. The axis is the page's (milestone_rows.timeline_span). A date outside 2000 to 2100 is not
drawn (its lane stays empty). At most MAX_LANES milestones are drawn (the table lists them all) and the picture is never bigger than WIDTH x its lanes.
Standard library only, Python 3.9.
"""
from datetime import date, timedelta

from clark import look, milestone_rows as mr, milestones as ms
from clark.png_draw import Canvas

WIDTH, LANE, TOP, PAD = 900, 18, 14, 10            # pixels: the picture's width, a lane's height, the month band, the side space
MAX_LANES = 60
MAX_TICKS = 40
BAR_W, BAR_H = 600, 8
HEALTH_ORDER = ("green", "amber", "red")

# The tokens the pictures use that the Word colour table (excel_colours.TOKENS) does not carry; read from the look when imported.
EXTRA = ("surface", "status-green", "status-amber", "status-red", "status-blue", "status-grey", "grey-200", "brand-blue")
LOOK_TOKENS = {n: look.colour(n) for n in EXTRA}


def tokens(tok):
    """The table the pictures read: the look's extras under the Word build's colours (a local brand's values win)."""
    return {**LOOK_TOKENS, **tok}


def _day(iso):
    try:
        return date.fromisoformat(iso) if isinstance(iso, str) and len(iso) == 10 and mr.in_range(iso) else None
    except ValueError:
        return None


def _number(value):
    try:
        n = float(value)
    except (TypeError, ValueError, OverflowError):      # 10**400 is an int float() cannot hold
        return None
    return None if n != n else max(0.0, min(100.0, n))


def percent(value):
    """A percent complete as a whole number 0 to 100, or None when it is not a number."""
    n = _number(value)
    return None if n is None else int(round(n))


# ===== Progress and Health =====
def progress_bar(pct, tok):
    """The progress bar (the page's .pbar): a grey track, the done part in the brand blue. None when pct is not a number."""
    p = percent(pct)
    if p is None:
        return None
    t = tokens(tok)
    c = Canvas(BAR_W, BAR_H, t["grey-100"])
    c.rect(0, 0, round(BAR_W * p / 100), BAR_H, t["brand-blue"])
    return c.png(), BAR_W, BAR_H


def health_bar(colour, tok):
    """The Health bar: three segments, green amber red; the one that is the project's health in its status colour, the others
    pale. A health with no such colour is one pale bar (nothing is claimed)."""
    t = tokens(tok)
    width, height, gap = 900, 14, 6
    c = Canvas(width, height, t["surface"])
    seg = (width - 2 * gap) // 3
    for i, name in enumerate(HEALTH_ORDER):
        x = i * (seg + gap)
        c.rect(x, 0, x + seg, height, t["status-" + name] if name == colour else t["grey-100"])
    return c.png(), width, height


# ===== The plan =====
def _rows(milestones):
    """The milestone rows that can be drawn, in table order, as milestone_rows' display shape: {name, state, word, marks}."""
    out = []
    for m in milestones:
        state = m.get("state") if m.get("state") in mr.LOOK else ms.FORECAST
        base, fc, done = (_day(m.get(k)) for k in ("baseline_date", "forecast_date", "actual_date"))
        if m.get("status") == "Done" and (done or base):
            solid = (done or base, "achieved" if done else "agreed")
        elif base:
            solid = (base, "agreed")
        elif fc:
            solid = (fc, "forecast")
        else:
            solid = (None, "")                                 # no date that can be drawn: an empty lane keeps the table's order
        try:
            slip = int(m.get("slip_days") or 0)
        except (TypeError, ValueError, OverflowError):
            slip = 0
        ghost = None
        if 0 < slip <= 36500 and state != ms.FORECAST and solid[1] == "agreed" and m.get("status") != "Done":
            end = solid[0] + timedelta(days=slip)
            ghost = end if mr.in_range(end.isoformat()) else None
        out.append({"row": m, "state": state, "shape": mr.LOOK[state][1], "colour": mr.LOOK[state][0],
                    "solid": solid[0], "ghost": ghost, "marks": {"solid": {"date": solid[0].isoformat()} if solid[0] else None,
                    "ghost": {"date": ghost.isoformat()} if ghost else None}})
    return out[:MAX_LANES]


def _mark(c, shape, x, y, colour, t):
    col, white = t["status-" + colour], t["surface"]
    if shape == "tick-circle":
        c.circle(x, y, 7, col)
        c.circle(x, y, 5, white)
        c.line(x - 3, y, x - 1, y + 3, col, 2)
        c.line(x - 1, y + 3, x + 4, y - 3, col, 2)
    elif shape == "dot":
        c.circle(x, y, 6, col)
    elif shape == "triangle":
        c.polygon([(x, y - 7), (x + 8, y + 6), (x - 8, y + 6)], col)
        c.polygon([(x, y - 3), (x + 4, y + 4), (x - 4, y + 4)], white)
    elif shape == "diamond":
        c.polygon([(x, y - 8), (x + 8, y), (x, y + 8), (x - 8, y)], col)
        c.polygon([(x, y - 4), (x + 4, y), (x, y + 4), (x - 4, y)], white)
    elif shape == "cross-circle":
        c.circle(x, y, 7, col)
        c.line(x - 3, y - 3, x + 3, y + 3, white, 2)
        c.line(x - 3, y + 3, x + 3, y - 3, white, 2)
    elif shape == "dashed-circle":
        c.circle(x, y, 7, col, inner=4, dashed=True)
    else:
        c.hline(x - 5, x + 5, y, t["status-grey"], 2)


def plan(milestones, today, tok):
    """The milestone plan: a month band, a lane for each milestone with its mark on its date (and, if it has slipped, the ghost
    on the expected date joined by a dashed line), and the Today line. A milestone with no date that can be drawn has an empty
    lane. Returns ((png, width, height), rows) or None when no milestone has a date that can be drawn."""
    rows = _rows(milestones)
    now = _day(today)
    if not any(r["solid"] for r in rows):
        return None
    t = tokens(tok)
    first = min(r["solid"] for r in rows if r["solid"])
    start_iso, end_iso = mr.timeline_span(rows, now.isoformat() if now else first.isoformat())
    start, end = date.fromisoformat(start_iso), date.fromisoformat(end_iso)
    days = max(1, (end - start).days)
    height = TOP + LANE * len(rows) + 2

    def x(d):
        return PAD + round((d - start).days * (WIDTH - 2 * PAD) / days)

    c = Canvas(WIDTH, height, t["surface"])
    for i in range(len(rows)):
        if i % 2 == 0:
            c.rect(0, TOP + i * LANE, WIDTH, TOP + (i + 1) * LANE, t["grey-100"])
    months = []
    y, m = start.year, start.month
    while date(y, m, 1) < end and len(months) < 2000:
        months.append(date(y, m, 1))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    for d in months[::-(-len(months) // MAX_TICKS)]:
        c.vline(x(d), 0, height, t["grey-200"])
    c.hline(0, WIDTH, TOP, t["grey-300"], 2)
    if now and start <= now < end:
        c.vline(x(now), 0, height, t["brand-navy"], 2)
    for i, r in enumerate(rows):
        cy = TOP + i * LANE + LANE // 2
        if not r["solid"]:
            continue
        if r["ghost"]:
            c.hline(x(r["solid"]), x(r["ghost"]), cy, t["status-red"], 2, dash=(5, 3))
            c.circle(x(r["ghost"]), cy, 7, t["status-red"], inner=4, dashed=True)
        _mark(c, r["shape"], x(r["solid"]), cy, r["colour"], t)
    c.hline(0, WIDTH, height - 1, t["grey-300"])
    return (c.png(), WIDTH, height), rows
