"""The pictures in the Word report (#1012): the milestone plan as the main screen draws it, the Health bar and the progress bar.

Each function gives (png bytes, width, height in pixels) from png_draw, or None when there is nothing to draw. A picture holds shapes, colours and
two kinds of short words, drawn as pixels with the small font below (no font file is needed): a lane's name at the left and the
months along the top (#1036). Every colour is a design token (`tok`, the Word build's colour table; the status colours the table does
not carry are read from the look, the same tokens.css). The full words are still real Word text in the table beside it. The picture
of the plan has one lane for each milestone, in the order of the table under it.

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

WIDTH, LANE, TOP, PAD = 900, 18, 20, 10            # pixels: the picture's width, a lane's height, the month band, the side space
MAX_LANES = 60
MAX_TICKS = 40
BAR_W, BAR_H = 600, 8
HEALTH_ORDER = ("green", "amber", "red")

# The tokens the pictures use that the Word colour table (excel_colours.TOKENS) does not carry; read from the look when imported.
EXTRA = ("surface", "status-green", "status-amber", "status-red", "status-blue", "status-grey", "grey-200", "brand-blue",
         "brand-blue-strong", "text", "grey-500")
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


# ===== Words in a picture =====
# A small 5 x 7 pixel font, drawn at TEXT_SCALE, for the lane names and the axis dates (the table beside the picture still carries the
# words as Word text). It holds the letters (a small letter is drawn as its capital), the digits and the usual marks; any other
# character (another script, a control or direction mark) is one "?" box, so nothing in a name can bring anything but pixels.
TEXT_SCALE, LABEL_W, LABEL_MAX = 2, 240, 19        # pixels per font dot; the lane name column's width; the most characters in a lane name
_FONT = {
    "A": "01110 10001 10001 11111 10001 10001 10001", "B": "11110 10001 10001 11110 10001 10001 11110",
    "C": "01110 10001 10000 10000 10000 10001 01110", "D": "11110 10001 10001 10001 10001 10001 11110",
    "E": "11111 10000 10000 11110 10000 10000 11111", "F": "11111 10000 10000 11110 10000 10000 10000",
    "G": "01110 10001 10000 10111 10001 10001 01111", "H": "10001 10001 10001 11111 10001 10001 10001",
    "I": "01110 00100 00100 00100 00100 00100 01110", "J": "00111 00010 00010 00010 00010 10010 01100",
    "K": "10001 10010 10100 11000 10100 10010 10001", "L": "10000 10000 10000 10000 10000 10000 11111",
    "M": "10001 11011 10101 10101 10001 10001 10001", "N": "10001 11001 10101 10011 10001 10001 10001",
    "O": "01110 10001 10001 10001 10001 10001 01110", "P": "11110 10001 10001 11110 10000 10000 10000",
    "Q": "01110 10001 10001 10001 10101 10010 01101", "R": "11110 10001 10001 11110 10100 10010 10001",
    "S": "01111 10000 10000 01110 00001 00001 11110", "T": "11111 00100 00100 00100 00100 00100 00100",
    "U": "10001 10001 10001 10001 10001 10001 01110", "V": "10001 10001 10001 10001 10001 01010 00100",
    "W": "10001 10001 10001 10101 10101 11011 10001", "X": "10001 10001 01010 00100 01010 10001 10001",
    "Y": "10001 10001 01010 00100 00100 00100 00100", "Z": "11111 00001 00010 00100 01000 10000 11111",
    "0": "01110 10001 10011 10101 11001 10001 01110", "1": "00100 01100 00100 00100 00100 00100 01110",
    "2": "01110 10001 00001 00010 00100 01000 11111", "3": "11110 00001 00001 01110 00001 00001 11110",
    "4": "00010 00110 01010 10010 11111 00010 00010", "5": "11111 10000 11110 00001 00001 10001 01110",
    "6": "00110 01000 10000 11110 10001 10001 01110", "7": "11111 00001 00010 00100 01000 01000 01000",
    "8": "01110 10001 10001 01110 10001 10001 01110", "9": "01110 10001 10001 01111 00001 00010 01100",
    " ": "00000 00000 00000 00000 00000 00000 00000", ".": "00000 00000 00000 00000 00000 01100 01100",
    ",": "00000 00000 00000 00000 01100 00100 01000", "-": "00000 00000 00000 11111 00000 00000 00000",
    ":": "00000 01100 01100 00000 01100 01100 00000", "/": "00001 00001 00010 00100 01000 10000 10000",
    "(": "00010 00100 01000 01000 01000 00100 00010", ")": "01000 00100 00010 00010 00010 00100 01000",
    "'": "00100 00100 01000 00000 00000 00000 00000", "&": "01100 10010 10100 01000 10101 10010 01101",
    "+": "00000 00100 00100 11111 00100 00100 00000", "%": "11001 11010 00010 00100 01000 01011 10011",
    "_": "00000 00000 00000 00000 00000 00000 11111", "?": "11111 10001 10001 10001 10001 10001 11111",
}
_GLYPHS = {k: [[c == "1" for c in row] for row in v.split()] for k, v in _FONT.items()}
X0, X1 = LABEL_W + PAD, WIDTH - PAD                # the time line's first and last pixel, right of the lane names


def label(text, limit=LABEL_MAX):
    """What a picture shows of a name: whitespace made single spaces, a small letter a capital, a character the font lacks a "?",
    and, past `limit` characters, the first limit - 2 and two dots."""
    text = " ".join(str(text if text is not None else "").split()).upper()
    text = "".join(ch if ch in _GLYPHS else "?" for ch in text)
    return text if len(text) <= limit else text[:limit - 2] + ".."


def text_width(text):
    return len(text) * 6 * TEXT_SCALE


def draw_text(c, x, y, text, colour):
    """Draw `text` (already through label()) with its top left at x, y."""
    k = TEXT_SCALE
    for i, ch in enumerate(text):
        for gy, row in enumerate(_GLYPHS[ch]):
            for gx, on in enumerate(row):
                if on:
                    px, py = x + (i * 6 + gx) * k, y + gy * k
                    c.rect(px, py, px + k, py + k, colour)


def month_labels(c, months, x, colour):
    """The axis dates: each month's first day as "NOV 26" in the band at the top, a month skipped if it would touch the one before."""
    edge = -1
    for d in months:
        word = f"{d:%b} {d:%y}".upper()
        at = x(d) + 3
        if at > edge and at + text_width(word) <= c.w:
            draw_text(c, at, 3, word, colour)
            edge = at + text_width(word) + 6


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
        return X0 + round((d - start).days * (X1 - X0) / days)

    c = Canvas(WIDTH, height, t["surface"])
    for i in range(len(rows)):
        if i % 2 == 0:
            c.rect(0, TOP + i * LANE, WIDTH, TOP + (i + 1) * LANE, t["grey-100"])
    months = []
    y, m = start.year, start.month
    while date(y, m, 1) < end and len(months) < 2000:
        months.append(date(y, m, 1))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    ticks = months[::-(-len(months) // MAX_TICKS)]
    for d in ticks:
        c.vline(x(d), 0, height, t["grey-200"])
    month_labels(c, ticks, x, t["text"])
    c.hline(0, WIDTH, TOP, t["grey-300"], 2)
    if now and start <= now < end:
        c.vline(x(now), 0, height, t["brand-navy"], 2)
    for i, r in enumerate(rows):
        draw_text(c, PAD, TOP + i * LANE + (LANE - 7 * TEXT_SCALE) // 2, label(r["row"].get("name")), t["text"])
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


# ===== The Gantt tab =====
# The page's Gantt chart (gantt/logic/gantt.js, GanttChart.jsx, shell.css .gt-*) as one picture for each run of at most GANTT_CHUNK
# lines, on one shared time line: a phase a navy bar, a task a bar in --gt-task with the done part lighter, a milestone a diamond
# (amber, green when done), and the Today line in the status red. The lines are the published Gantt's (publish.gantt_for_client
# has already left out every eye-off line); a line the page would not draw is left out here too and counted, never repaired.
GANTT_CHUNK, G_LANE, G_TOP = 30, 22, 20
G_TYPES = ("phase", "task", "milestone")


def mix(a, b, share):
    """`share` (0 to 1) of colour a over colour b, as six hex digits (CSS color-mix in srgb)."""
    ra, rb = (tuple(int(x[i:i + 2], 16) for i in (0, 2, 4)) for x in (a.lstrip("#"), b.lstrip("#")))
    return "".join(f"{round(p * share + q * (1 - share)):02X}" for p, q in zip(ra, rb))


def gantt_lines(lines):
    """(drawable lines, how many were left out). A drawable line is the page's tidy(): its start is a real day in 2000 to 2100 (else it
    has no place on the time line and is left out and counted), a type that is not one of the three reads as a task, a milestone ends
    the day it starts, an end that is no day or before the start is the start, done is a whole number 0 to 100, and a line whose eye
    is off (show 0 or false, when the line carries it) is not drawn at all and not counted."""
    out, left = [], 0
    for r in lines if isinstance(lines, (list, tuple)) else ():
        if not isinstance(r, dict) or r.get("show") is False or (type(r.get("show")) is int and r["show"] == 0):
            continue
        start = _day(r.get("start"))
        if start is None:
            left += 1
            continue
        kind = r.get("type") if r.get("type") in G_TYPES else "task"
        end = _day(r.get("end")) or start
        if kind == "milestone" or end < start:
            end = start
        out.append({"line": r, "type": kind, "start": start, "end": end, "pct": percent(r.get("pct")) or 0})
    return out, left


def gantt_range(drawn, today):
    """The page's chartRange: the first of the earliest month to the end of the latest month, at least 180 days, today counted."""
    days = [d for r in drawn for d in (r["start"], r["end"])] + ([today] if today else [])
    first = min(days).replace(day=1)
    top = max(days)
    stop = date(top.year + (top.month == 12), top.month % 12 + 1, 1)
    while (stop - first).days < 180:
        stop = date(stop.year + (stop.month == 12), stop.month % 12 + 1, 1)
    return first, stop - timedelta(days=1)


def gantt(lines, today, tok):
    """The Gantt tab's pictures: {"pictures": [((png, width, height), the drawable lines in it)], "start", "end" (the time line's first
    and last day), "left_out": n, "drawn": all the drawable lines}, one picture for each run of GANTT_CHUNK lines, in the order given.
    None when the Gantt holds no line at all."""
    drawn, left = gantt_lines(lines)
    if not drawn:
        return {"pictures": [], "start": None, "end": None, "left_out": left, "drawn": []} if left else None
    now = _day(today)
    first, last = gantt_range(drawn, now)
    t = tokens(tok)
    ppd = (X1 - X0) / ((last - first).days + 1)
    task = mix(t["brand-blue-strong"], t["text"], 0.6)
    lighter = mix(t["white"], task, 0.3)

    def x(d):
        return X0 + round((d - first).days * ppd)
    months = []
    y, m = first.year, first.month
    while date(y, m, 1) <= last and len(months) < 2000:
        months.append(date(y, m, 1))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    ticks = months[::-(-len(months) // MAX_TICKS)]
    pictures = []
    for at in range(0, len(drawn), GANTT_CHUNK):
        run = drawn[at:at + GANTT_CHUNK]
        height = G_TOP + G_LANE * len(run) + 2
        c = Canvas(WIDTH, height, t["surface"])
        for i, r in enumerate(run):
            if r["type"] == "phase":
                c.rect(0, G_TOP + i * G_LANE, WIDTH, G_TOP + (i + 1) * G_LANE, t["grey-50"])
            c.hline(0, WIDTH, G_TOP + (i + 1) * G_LANE - 1, t["grey-100"])
        for d in ticks:
            c.vline(x(d), 0, height, t["grey-100"])
        month_labels(c, ticks, x, t["text"])
        for i, r in enumerate(run):
            draw_text(c, PAD, G_TOP + i * G_LANE + (G_LANE - 7 * TEXT_SCALE) // 2, label(r["line"].get("name")), t["text"])
        c.hline(0, WIDTH, G_TOP, t["grey-300"], 2)
        if now and first <= now <= last:
            c.vline(x(now), 0, height, t["status-red"], 2)
        for i, r in enumerate(run):
            cy = G_TOP + i * G_LANE + G_LANE // 2
            x1 = x(r["start"])
            if r["type"] == "milestone":
                border, fill = (t["status-green-text"], t["status-green"]) if r["pct"] >= 100 else (t["status-amber-text"], t["status-amber"])
                c.polygon([(x1, cy - 8), (x1 + 8, cy), (x1, cy + 8), (x1 - 8, cy)], border)
                c.polygon([(x1, cy - 5), (x1 + 5, cy), (x1, cy + 5), (x1 - 5, cy)], fill)
                continue
            x2 = max(x(r["end"] + timedelta(days=1)), x1 + 14)
            if r["type"] == "phase":
                c.rect(x1, cy - 6, x2, cy + 6, t["grey-500"])
                c.rect(x1 + 1, cy - 5, x2 - 1, cy + 5, t["brand-navy"])
            else:
                c.rect(x1, cy - 6, x2, cy + 6, task)
                c.rect(x1, cy - 6, x1 + round((x2 - x1) * r["pct"] / 100), cy + 6, lighter)
        c.hline(0, WIDTH, height - 1, t["grey-300"])
        pictures.append(((c.png(), WIDTH, height), run))
    return {"pictures": pictures, "start": first, "end": last, "left_out": left, "drawn": drawn}
