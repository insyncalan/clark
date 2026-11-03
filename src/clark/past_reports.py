"""The seam behind the Published reports list and Open (#443, from #343 and #345; guarded: server and store).

`PastReports` answers three requests for the server (server.past_route, server.past_page_route), each as (status, body):
- listing(code): GET /api/publications?project=. The newest 10 publications of the project, each as {number, when, where, who,
  word, kept}, and how many there are in all. Nothing is read but the number, the time, who, whether a copy went to the client
  and whether it was a Word copy: no path and no SHA-256 leaves. Every publication is kept (#348); only the list is cut to 10.
- visit(code, number): GET /api/past-report?project=&number=. The publication's kept copy (published_copies.read) is checked
  against the SHA-256 its row holds, and kept in memory for one visit to the address in `url` (a new tab cannot send the token, so
  the address is the one-visit secret, as the Preview's is). The request names a code and a number and nothing else: the copy's
  file name is made from those two by published_copies.file_name, so no path from a request reaches the disk.
- take(id): GET /past?id=. The kept bytes for an address from visit(), once; None when it is unknown, used or too old. They are
  the very bytes that were published, so the page the client was given is shown, with nothing from Edit.

Reads clark.db on a read-only connection and writes nothing but the one-visit entry in memory. Standard library only, Python 3.9."""
import re
import threading
import secrets
import time
from pathlib import Path

from clark import history, published_copies
from clark.store import connect

SHOWN = 10                       # the list shows the newest ten; every publication is kept
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

    def listing(self, code):
        if not isinstance(code, str) or not published_copies.PROJECT_CODE.fullmatch(code):
            return 400, self.fail("bad_project_code")
        try:
            con = self._con()
            try:
                if con.execute("SELECT 1 FROM projects WHERE code = ?", (code,)).fetchone() is None:
                    return 404, self.fail("project_not_found")
                total = con.execute("SELECT count(*) FROM publications WHERE project = ?", (code,)).fetchone()[0]
                rows = con.execute("SELECT at, number, word, client_path IS NOT NULL AS to_client, by_user FROM publications "
                                   "WHERE project = ? ORDER BY number DESC LIMIT ?", (code, SHOWN)).fetchall()
            finally:
                con.close()
        except Exception:
            return 500, self.fail("db_unreadable")
        out = []
        for r in rows:
            word = bool(r["word"])
            where = (WHERE_CLIENT if r["to_client"] else WHERE_LOCAL) + (WORD if word else "")
            out.append({"number": r["number"], "when": history.when_text(r["at"], None)[0], "where": where,
                        "who": (r["by_user"] or "").strip() or NOT_RECORDED, "word": word,
                        "kept": not word and published_copies.is_kept(self.data_dir, code, r["number"])})
        return 200, {"ok": True, "project": code, "total": total, "shown": len(out), "limit": SHOWN, "publications": out}

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
                row = con.execute("SELECT file_sha256, word FROM publications WHERE project = ? AND number = ?",
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
        nonce, now = secrets.token_urlsafe(24), self.clock()
        with self.lock:
            for k in [k for k, v in self.visits.items() if now - v[1] > VISIT_SECONDS]:
                del self.visits[k]
            while len(self.visits) >= VISIT_KEEP:
                del self.visits[next(iter(self.visits))]
            self.visits[nonce] = (data, now)
        return 200, {"ok": True, "code": "past_ready", "message": MESSAGES["past_ready"].format(number=number),
                     "number": number, "url": "/past?id=" + nonce}

    def take(self, nonce):
        if not isinstance(nonce, str) or not NONCE.fullmatch(nonce):
            return None
        with self.lock:
            got = self.visits.pop(nonce, None)
        return got[0] if got and self.clock() - got[1] <= VISIT_SECONDS else None
