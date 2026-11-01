"""What POST /api/demo does (#444, Settings > Data: Reset the demo data; guarded: it replaces the database file).

The server (which imports nothing from clark) hands a request to a seam made here and sends the (status, body) it returns.

Two ops, neither taking anything else from the request:
- "state": {"ok": true, "demo": true or false}. Whether the data clark has open is the demo data (clark was started with --demo, so
  its data is in the temporary demo folder the launcher made). The page offers Reset the demo data only when this is true.
- "reset": puts the demo data back as it started. Refused in plain words, with nothing touched, unless the open data is the demo
  data: clark was started with --demo AND the database file is the one in that demo folder, so a real data folder can never be
  reset from here, whatever the request says. Taken under the one lock (changes.LOCK) without waiting, so a change or an
  undo that is running is never overlapped; the demo database is built again by the demo builder the launcher hands in (the same
  one --demo uses) and swapped in whole, so a failure leaves the data as it was.

Every message is plain words, "clark" in lower case and never first. Standard library only, Python 3.9.
"""
import logging
from pathlib import Path

from clark import changes

LOG = logging.getLogger("clark.demo")

NOT_JSON_OBJECT = "That could not be read. Reload the page and try again."
BAD_OP = "That isn't something clark can do with the demo data."
NOT_DEMO = "These are not demo data, so they can't be reset. Nothing was changed."
BUSY = "Something is being saved. Wait a moment and try again."
FAILED = "The demo data could not be put back. Nothing was changed."
DONE = "The demo data is back as it started."
OPS = ("state", "reset")


def make_demo(path, demo_folder=None, rebuild=None):
    """The `demo` seam the server calls for POST /api/demo, for the database at `path`. `demo_folder` is the temporary folder the
    launcher made for --demo (None when clark is running on real data) and `rebuild(path)` builds the demo database there again
    (None: it is not available, as in a copy with no demo builder)."""
    def is_demo():
        if demo_folder is None or rebuild is None:
            return False
        try:
            return Path(path).resolve().parent == Path(demo_folder).resolve()
        except OSError:
            return False

    def demo(req):
        if not isinstance(req, dict) or set(req) != {"op"} or req["op"] not in OPS:
            return 400, {"ok": False, "code": "bad_request", "message": BAD_OP if isinstance(req, dict) and "op" in req else NOT_JSON_OBJECT}
        if req["op"] == "state":
            return 200, {"ok": True, "demo": is_demo()}
        if not is_demo():
            return 409, {"ok": False, "code": "not_demo", "message": NOT_DEMO}
        if not changes.LOCK.acquire(blocking=False):
            return 409, {"ok": False, "code": "busy", "message": BUSY}
        try:
            rebuild(Path(path))
        except Exception as e:                               # noqa: BLE001  the builder's own words are never shown; the data is as it was
            LOG.error("demo reset failed (%s)", type(e).__name__)    # the kind of fault only: no path, no content
            return 500, {"ok": False, "code": "reset_failed", "message": FAILED}
        finally:
            changes.LOCK.release()
        return 200, {"ok": True, "code": "reset", "message": DONE, "reload": True}
    return demo
