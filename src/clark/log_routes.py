"""The routes behind Settings > Diagnostics and the page's error reports (#110, BRD FR-8b).

`Logs` is the seam the server hands its /api/page-error, /api/diagnostics, /api/logging and /api/logging/open-folder requests
to (server.logs_route). Each method answers (status, body). The server stays free of any log logic: what may be written is
decided in log.py, and what the report holds in diagnostics.py. Nothing here reads or returns a request body to the log.
Standard library only, Python 3.9.
"""
import re

from clark import __version__, diagnostics, log as clog, platform

NOT_SAVED = "The logging level could not be saved. Check that the folder can be written to, then try again."
NOT_OPENED = "The log folder could not be opened. Try again; if it keeps happening, restart clark."
BAD_LEVEL = "That level isn't one of the choices. Reload the page and try again."

# The Errors list on screen says each error in plain words. The technical line (area, route, class) stays in the log and in Copy
# diagnostics, which is for support. One fixed sentence per kind of error, chosen here from the route and the area of the log
# entry; none of the entry's own text is passed on. The sentences are the ones the owner approved for #295.
SAVE_DID_NOT_WORK = "Saving a change did not work."
TRY_AGAIN = "Try again. If it keeps happening, use Copy diagnostics and send it to the person who is helping you."
READ_DID_NOT_WORK = "Loading part of the page did not work."
PAGE_DID_NOT_WORK = "Part of the page stopped working."
STORE_DID_NOT_WORK = "Reading or saving your project data did not work."
SOMETHING_DID_NOT_WORK = "Something did not work."
A_REQUEST_FAILED = re.compile(r"^(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS) (\S+) failed")
WRITES = ("POST", "PUT", "PATCH", "DELETE")
SAVING_ROUTES = frozenset("""/api/change /api/undo /api/people /api/people/undo /api/profile /api/projects /api/use-cases /api/milestones
    /api/movement /api/section-file /api/section-image""".split())
ROUTE_SENTENCES = {
    "/api/publish": "Publishing did not work.",
    "/api/publication": "Publishing did not work.",
    "/api/client-folder": "Publishing did not work.",
    "/api/export": "Making the Excel workbook did not work.",
    "/api/word-export": "Making the Word file did not work.",
    "/api/word-import": "Reading the Word file did not work.",
    "/api/backups/restore": "Restoring a backup did not work.",
    "/api/draft-email": "Drafting the email did not work.",
    "/api/draft-email/sent": "Marking the email as sent did not work.",
    "/api/logging": "Changing the log setting did not work.",
}


def what_it_was(group):
    """The fixed sentence for one error group: from its area, and for a server error from the request's method and route."""
    if group["area"] == "page":
        return PAGE_DID_NOT_WORK
    if group["area"] == "store":
        return STORE_DID_NOT_WORK
    m = A_REQUEST_FAILED.match(group["message"]) if group["area"] == "server" else None
    if not m:
        return SOMETHING_DID_NOT_WORK
    method, route = m.groups()
    if route == "/api/ask" or route.startswith("/api/ask/"):
        return "Asking clark did not work."
    if method == "POST" and route == "/api/backups":
        return "Making a backup did not work."
    if method in WRITES and route in SAVING_ROUTES:
        return SAVE_DID_NOT_WORK
    if route in ROUTE_SENTENCES:
        return ROUTE_SENTENCES[route]
    return READ_DID_NOT_WORK if method == "GET" else SOMETHING_DID_NOT_WORK


def plain_error(group):
    """One error group from the log, as the plain line the list shows: when it was last and how many times, what it was about (a
    fixed sentence for its kind) and what to do next. None of the group's own text is passed on."""
    return {"count": group["count"], "last": f"{group['last']:%d-%m-%Y %H:%M}", "what": what_it_was(group), "next": TRY_AGAIN}


class Logs:
    """`log` is a clog.Log. `counts` is a function giving {name: whole number} for the report (or None). `opener` shows a folder
    (platform.open_file unless a test gives its own)."""

    def __init__(self, log, counts=None, opener=None, version=None):
        self.log, self.counts, self.version = log, counts, version or __version__
        self.opener = opener or platform.open_file

    def page_error(self, req):
        """The page reported a fault: its kind and message go to log.page_error, which rate-limits and keeps only the browsers' own
        fault words. The answer is the same whether the line was written or dropped."""
        req = req if isinstance(req, dict) else {}
        self.log.page_error(req.get("kind"), req.get("message"))
        return 200, {"ok": True}

    def diagnostics(self):
        """The level, how long Debug has been on, the errors of the last 7 days and the text Copy diagnostics copies."""
        try:
            counts = dict(self.counts()) if self.counts else {}
        except Exception:
            counts = {}
        errors = [plain_error(g) for g in self.log.errors()]
        report = diagnostics.build(self.log, self.version, {"log_level": self.log.level()}, counts)
        return 200, {"ok": True, "level": self.log.level(), "notice": self.log.debug_notice(), "errors": errors, "report": report}

    def set_level(self, req):
        """Save Normal or Debug. A level that is not one of the two is refused; a level that could not be saved is said plainly."""
        want = req.get("level") if isinstance(req, dict) else None
        if want not in (clog.NORMAL, clog.DEBUG):
            return 400, {"ok": False, "code": "bad_level", "message": BAD_LEVEL}
        now = self.log.set_level(want)
        if now != want:
            return 409, {"ok": False, "code": "not_saved", "message": NOT_SAVED, "level": now}
        return 200, {"ok": True, "level": now, "notice": self.log.debug_notice()}

    def open_folder(self, req=None):
        """Show the log folder in Finder (made first, so a day with nothing logged still opens it)."""
        try:
            self.log.folder.mkdir(parents=True, exist_ok=True)
            self.opener(self.log.folder)
        except (OSError, platform.PlatformError):
            return 503, {"ok": False, "code": "not_opened", "message": NOT_OPENED}
        return 200, {"ok": True}
