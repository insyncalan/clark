"""The routes behind Settings > Diagnostics and the page's error reports (#110, BRD FR-8b).

`Logs` is the seam the server hands its /api/page-error, /api/diagnostics, /api/logging and /api/logging/open-folder requests
to (server.logs_route). Each method answers (status, body). The server stays free of any log logic: what may be written is
decided in log.py, and what the report holds in diagnostics.py. Nothing here reads or returns a request body to the log.
Standard library only, Python 3.9.
"""
from clark import __version__, diagnostics, log as clog, platform

NOT_SAVED = "The logging level could not be saved. Check that the folder can be written to, then try again."
NOT_OPENED = "The log folder could not be opened. Try again; if it keeps happening, restart clark."
BAD_LEVEL = "That level isn't one of the choices. Reload the page and try again."


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
        errors = [{"count": g["count"], "area": g["area"], "message": g["message"], "last": f"{g['last']:%d-%m-%Y %H:%M}"}
                  for g in self.log.errors()]
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
