"""The dashboard "as at" a chosen date, rebuilt from the change history (#349, follow-on 8 of the #125 design note).

`AsAt` answers one request for the server (server.as_at_route), as (status, body):
- read(code, day): GET /api/as-at?project=&date=YYYY-MM-DD. The project's data as the page reads it (Store.data_for), as it stood at
  the end of `day` (the computer's own day), rebuilt from change_log.

How it is rebuilt: store.rewound_copy copies clark.db, on a read-only connection, into a new file in a temporary folder of this
read's own, and in that copy undoes every change made after the end of the day (and drops the log after it, so freshness, the
"not reviewed" marks, is read from the history as it was; it is counted on that day here). Store.data_for then reads the copy, so the
answer has exactly the shape and the rules of today's (the eye's hidden rows, the archived rows, the label rules). The copy is
removed before the reply is sent.

It never writes clark.db: every write is to the copy, in store.py (the one writer). Nothing here publishes: no publishing module
imports it, and the page draws the answer read only, behind its banner, with no Edit, Publish or peek tools. What the log does not
hold, it cannot rebuild: a value set by a database update step (a migration), not by a step, reads as it is now. That is why the
page always says "rebuilt from the change history". Standard library only, Python 3.9."""
import re
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from clark import freshness as fresh
from clark import history
from clark.store import FRESH_TABLES, Store, connect, review_days_for, rewound_copy

DAY = re.compile(r"\d{4}-\d{2}-\d{2}")
PROJECT_CODE = re.compile(r"[A-Z][A-Z0-9]{2,6}")

MESSAGES = {
    "bad_project_code": "Give the project's code (3 to 7 capital letters or digits).",
    "bad_date": "Give a real day, as DD-MM-YYYY.",
    "future": "That day has not happened yet. Pick today or a day before it.",
    "project_not_found": "There is no project with that code.",
    "not_yet": "This project did not exist yet on {day}. Pick a later day.",
    "db_unreadable": "The records could not be read. Restart clark and try again.",
}


def shown(iso):
    return f"{iso[8:10]}-{iso[5:7]}-{iso[0:4]}"


def cutoff(day, tz=None):
    """The first moment after `day` (YYYY-MM-DD) ends in the computer's own time zone (or `tz`), in UTC as change_log writes it:
    'YYYY-MM-DD HH:MM:SS'. A change at or after it is undone."""
    start = datetime.strptime(day, "%Y-%m-%d") + timedelta(days=1)
    local = start.replace(tzinfo=tz) if tz is not None else start.astimezone()
    return local.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def refresh(path, data, day):
    """Freshness counted on `day`, not today, from the copy's history (as store.attach_freshness does it). Reads only."""
    days = review_days_for(data["project"])
    opened = [row for t in FRESH_TABLES for row in data.get(t, ()) if fresh.is_open(row)]
    con = connect(path, readonly=True)
    try:
        events = history.review_events(con, [row["id"] for row in opened])
    finally:
        con.close()
    for row in opened:
        f = fresh.freshness(row, events[row["id"]], day, days)
        row["freshness"] = {"raised": f["raised"], "last_reviewed": f["last_reviewed"], "days": days, "not_reviewed": f["not_reviewed"]}


def rebuild(db_path, code, day, tz=None):
    """The project's data (as Store.data_for gives it) at the end of `day`, or None when the project was not there then."""
    with tempfile.TemporaryDirectory(prefix="clark-as-at-") as tmp:
        copy = Path(tmp) / "as-at.db"
        rewound_copy(db_path, copy, cutoff(day, tz))
        data = Store.data_for(SimpleNamespace(path=copy, review_cache=None), code)
        if data is not None:
            refresh(copy, data, day)
        return data


class AsAt:
    def __init__(self, db_path, today=None, tz=None):
        self.db_path = Path(db_path)
        self.today = today or (lambda: date.today().isoformat())
        self.tz = tz                                       # None: the computer's own zone (a test passes one)

    def fail(self, code, **fill):
        return {"ok": False, "code": code, "message": MESSAGES[code].format(**fill)}

    def read(self, code, day):
        if not isinstance(code, str) or not PROJECT_CODE.fullmatch(code):
            return 400, self.fail("bad_project_code")
        if not isinstance(day, str) or not DAY.fullmatch(day):
            return 400, self.fail("bad_date")
        try:
            date.fromisoformat(day)
        except ValueError:
            return 400, self.fail("bad_date")
        if day > self.today():
            return 400, self.fail("future")
        try:
            con = connect(self.db_path, readonly=True)
            try:
                there = con.execute("SELECT 1 FROM projects WHERE code = ?", (code,)).fetchone() is not None
            finally:
                con.close()
            if not there:
                return 404, self.fail("project_not_found")
            data = rebuild(self.db_path, code, day, self.tz)
        except Exception:
            return 500, self.fail("db_unreadable")
        if data is None:
            return 404, self.fail("not_yet", day=shown(day))
        return 200, {"ok": True, "project": code, "as_at": day, "data": data}
