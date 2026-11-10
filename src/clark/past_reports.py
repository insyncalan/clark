"""The seam behind the Published reports list and Open (#443, from #343 and #345; guarded: server and store).

`PastReports` answers three requests for the server (server.past_route, server.past_page_route), each as (status, body):
- listing(code): GET /api/publications?project=. The newest 10 publications of the project, each as {number, when, where, who,
  word, kept, week, day, at, pdf}, how many there are in all and how many are archived (#342: an archived one is left out of the list and the total,
  and is still kept and still opens). `week` is the week ending it was published for (YYYY-MM-DD, or None) and `day` the computer's
  own day it was published on (YYYY-MM-DD): the Dashboard's week picker (#344) lists and opens them. Nothing is read but the number, the time, who, whether a copy went to the client
  and whether it was a Word copy: no path and no SHA-256 leaves. Every publication is kept (#348); only the list is cut to 10.
- visit(code, number): GET /api/past-report?project=&number=. The publication's kept copy (published_copies.read) is checked
  against the SHA-256 its row holds, and kept in memory for one visit to the address in `url` (a new tab cannot send the token, so
  the address is the one-visit secret, as the Preview's is). #343: what the address gives is the very bytes that were published with
  one block added after <body> for that visit (past_banner.py): the banner 'Publication N · DD-MM-YYYY · read only', a tinted frame
  and 'Back to now'; the copy on disk is not touched. The request names a code and a number and nothing else: the copy's
  file name is made from those two by published_copies.file_name, so no path from a request reaches the disk.
- take(id): GET /past?id=. The page for an address from visit(), once; None when it is unknown, used or too old. It is the page the
  client was given with the banner block added (past_banner.unframe gives the published bytes back), with nothing from Edit.

Reads clark.db on a read-only connection and writes nothing but the one-visit entry in memory. Standard library only, Python 3.9."""
import re
import threading
import secrets
import time
from datetime import timezone
from pathlib import Path

from clark import history, past_banner, published_copies, timefmt
from clark.store import connect

SHOWN = 10                       # the list shows the newest ten; every publication is kept
DAY = re.compile(r"\d{4}-\d{2}-\d{2}")
VISIT_KEEP = 4                   # past reports waiting to be opened; the oldest goes first
VISIT_SECONDS = 120              # an address not visited in this time is dropped
NONCE = re.compile(r"[A-Za-z0-9_-]{16,64}")
NOT_RECORDED = "Not recorded"
WHERE_LOCAL, WHERE_CLIENT, WORD = "Local", "Local and to client", " · Word"

MESSAGES = {
    "bad_project_code": "Give the project's code (3 to 7 capital letters or digits).",
    "bad_number": "Give the publication's number, a whole number from 1.",
    "project_not_found": "There is no project with that code.",
    "no_publication": "There is no Publication {number} for this project.",
    "not_kept": "The page for Publication {number} was not kept, so it can't be opened. Only pages published after clark began keeping every one have a copy.",
    "copy_changed": "The kept copy of Publication {number} no longer matches what was published, so clark will not open it. Restore your data from a backup, or ask the clark team for help.",
    "past_ready": "Opening Publication {number} as it was published.",
    "db_unreadable": "The records could not be read. Restart clark and try again.",
}


def local_day(at):
    """The computer's own day (YYYY-MM-DD) of a logged UTC time, as the Dashboard as at a day reads a day (as_at.cutoff); None when
    it is not a time."""
    try:
        return timefmt.parse(at).astimezone().date().isoformat()
    except (ValueError, OverflowError, OSError):
        return None


def utc_stamp(at):
    """A logged time as UTC with a Z (YYYY-MM-DDTHH:MM:SSZ), for the page to show in the person's own zone and name it (row 1087);
    None when it is not a time. The seconds are cut, never rounded."""
    try:
        return timefmt.parse(at).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except (ValueError, OverflowError, OSError):
        return None


class PastReports:
    def __init__(self, db_path, clock=time.monotonic):
        self.db_path = Path(db_path)
        self.data_dir = self.db_path.parent          # the kept copies are in `published-copies` beside clark.db
        self.clock = clock
        self.visits, self.lock = {}, threading.Lock()      # {nonce: (bytes, time made)}: in memory only

    def fail(self, code, **fill):
        return {"ok": False, "code": code, "message": MESSAGES[code].format(**fill)}

    def _con(self):
        return connect(self.db_path, readonly=True)

    def listing(self, code, archived=False):
        """`archived` (#345, Show archived): the archived ones are listed with the rest, each marked `archived`, and counted in the
        total; otherwise they are left out as before."""
        if not isinstance(code, str) or not published_copies.PROJECT_CODE.fullmatch(code):
            return 400, self.fail("bad_project_code")
        try:
            con = self._con()
            try:
                if con.execute("SELECT 1 FROM projects WHERE code = ?", (code,)).fetchone() is None:
                    return 404, self.fail("project_not_found")
                rows = con.execute("SELECT at, number, word, week_ending, client_path IS NOT NULL AS to_client, pdf_name IS NOT NULL AS has_pdf, by_user FROM publications "
                                   "WHERE project = ? ORDER BY number DESC, word", (code,)).fetchall()
            finally:
                con.close()
        except Exception:
            return 500, self.fail("db_unreadable")
        gone = {r["number"] for r in rows if published_copies.is_archived(self.data_dir, code, r["number"])}
        listed = rows if archived else [r for r in rows if r["number"] not in gone]       # #342: archived ones are hidden; #345: unless asked for
        total, out = len(listed), []
        for r in listed[:SHOWN]:
            word = bool(r["word"])
            where = (WHERE_CLIENT if r["to_client"] else WHERE_LOCAL) + (WORD if word else "")
            out.append({"number": r["number"], "when": history.when_text(r["at"], None)[0], "where": where,
                        "who": (r["by_user"] or "").strip() or NOT_RECORDED, "word": word,
                        "kept": not word and published_copies.is_kept(self.data_dir, code, r["number"]),
                        "week": r["week_ending"] if isinstance(r["week_ending"], str) and DAY.fullmatch(r["week_ending"]) else None,
                        "day": local_day(r["at"]), "archived": r["number"] in gone,
                        "at": utc_stamp(r["at"]), "pdf": bool(r["has_pdf"]) and not word})
        return 200, {"ok": True, "project": code, "total": total, "shown": len(out), "limit": SHOWN, "archived": sum(1 for r in rows if r["number"] in gone),
                     "publications": out}

    def visit(self, code, number):
        if not isinstance(code, str) or not published_copies.PROJECT_CODE.fullmatch(code):
            return 400, self.fail("bad_project_code")
        if published_copies.file_name(code, number) is None:
            return 400, self.fail("bad_number")
        try:
            con = self._con()
            try:
                if con.execute("SELECT 1 FROM projects WHERE code = ?", (code,)).fetchone() is None:
                    return 404, self.fail("project_not_found")
                row = con.execute("SELECT file_sha256, word, at FROM publications WHERE project = ? AND number = ? ORDER BY word LIMIT 1",
                                  (code, number)).fetchone()
            finally:
                con.close()
        except Exception:
            return 500, self.fail("db_unreadable")
        if row is None:
            return 404, self.fail("no_publication", number=number)
        if row["word"]:
            return 404, self.fail("not_kept", number=number)
        state, data = published_copies.read(self.data_dir, code, number, row["file_sha256"])
        if state == published_copies.MISSING:
            return 404, self.fail("not_kept", number=number)
        if state != published_copies.OK:
            return 409, self.fail("copy_changed", number=number)
        shown = past_banner.frame(data, number, history.when_text(row["at"], None)[0][:10])      # #343: the banner, the tint, Back to now
        if shown is None:                                      # the checksum matched, but this is not a page clark makes
            return 409, self.fail("copy_changed", number=number)
        nonce, now = secrets.token_urlsafe(24), self.clock()
        with self.lock:
            for k in [k for k, v in self.visits.items() if now - v[1] > VISIT_SECONDS]:
                del self.visits[k]
            while len(self.visits) >= VISIT_KEEP:
                del self.visits[next(iter(self.visits))]
            self.visits[nonce] = (shown, now)
        return 200, {"ok": True, "code": "past_ready", "message": MESSAGES["past_ready"].format(number=number),
                     "number": number, "url": "/past?id=" + nonce}

    def take(self, nonce):
        if not isinstance(nonce, str) or not NONCE.fullmatch(nonce):
            return None
        with self.lock:
            got = self.visits.pop(nonce, None)
        return got[0] if got and self.clock() - got[1] <= VISIT_SECONDS else None
