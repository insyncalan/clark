"""Row 1046: read the notices for the bell from the file or folder set in Settings. Read only: nothing here writes, moves or deletes
anything at that place, and nothing is sent over a network.

The place may be one JSON file or a folder of `.json` files. A file holds a list of notices, or an object {"notices": [...]}. A notice
is passed on as plain data (strings, numbers, lists and objects); what is shown, and what is dropped (an action that leaves clark, a
too-long title, a notice past its date), is decided by the page (logic/notices.js), which never reads any of it as HTML.

A place that is away (an unreachable share, a missing file, a file that is not JSON) is never an error for the person: the answer is
an empty list and a short reason word. The read runs in a helper thread and gives up after TIMEOUT seconds, so a share that does not
answer can never slow the server or the start of clark. Standard library only.
"""
import json
import threading
from pathlib import Path

from clark import settings

TIMEOUT = 3.0                 # seconds to wait for the place before giving up
FILE_LIMIT = 64 * 1024        # a file larger than this is not read
MAX_FILES = 30                # in a folder: the first 30 `.json` files by name
MAX_NOTICES = 200             # passed to the page; the page keeps at most 30 shown
WHY = ("off", "away", "none", "ok")      # off: no path set; away: not reachable in time; none: nothing readable there; ok


def _items(path):
    """The raw notice objects in one file, or [] when it can't be read as notices."""
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > FILE_LIMIT:
            return []
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, RecursionError):
        return []
    if isinstance(value, dict):
        value = value.get("notices")
    return [n for n in value if isinstance(n, dict)] if isinstance(value, list) else []


def read_place(place):
    """Every raw notice at `place` (a file, or a folder of `.json` files)."""
    place = Path(place)
    if place.is_dir():
        found = []
        for child in sorted(place.glob("*.json"))[:MAX_FILES]:
            found.extend(_items(child))
        return found[:MAX_NOTICES]
    return _items(place)[:MAX_NOTICES]


def read_within(place, timeout=None):
    """(notices, why): `read_place` run in a helper thread that is given up on after `timeout` seconds (why "away")."""
    box = []
    worker = threading.Thread(target=lambda: box.append(read_place(place)), daemon=True)
    worker.start()
    worker.join(TIMEOUT if timeout is None else timeout)
    if worker.is_alive() or not box:
        return [], "away"
    return box[0], "ok" if box[0] else "none"


class Notices:
    """The seam behind GET /api/notices: reads the saved place each time it is asked (the page asks on start and every few minutes)."""

    def __init__(self, data_dir, timeout=None):
        self.data_dir = Path(data_dir)
        self.timeout = timeout

    def read(self):
        """(status, body): {"ok": True, "why": "off"|"away"|"none"|"ok", "notices": [...]}. Never an error status for a bad place."""
        place = settings.notices_path(self.data_dir)
        if place is None:
            return 200, {"ok": True, "why": "off", "notices": []}
        found, why = read_within(place, self.timeout)
        return 200, {"ok": True, "why": why, "notices": found}
