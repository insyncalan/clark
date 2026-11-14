"""item 631: the time zone in the Docker route. A container runs in UTC, so 'today' (store.today, milestones.today, sneak.today,
movement_read.today_text) and the offset on History times would be the container's, not the person's. Those functions read the
process zone, so this one place sets it: apply_zone(name) validates an IANA name, sets TZ and calls time.tzset. It is used only in
container mode (the Mac route runs in the person's own zone, and tzset does not exist on Windows; the container is Linux).

The page sends its own zone in X-Clark-Tz; follow_header applies it. A name that is not an IANA name is ignored and never logged.
A zone pinned by TZ in the container's settings (docker/compose.yaml) is kept: the page's zone is then not applied."""
import os
import re
import threading
import time
from zoneinfo import ZoneInfo

HEADER = "X-Clark-Tz"
_SHAPE = re.compile(r"[A-Za-z][A-Za-z0-9_+\-]{0,31}(/[A-Za-z0-9_+\-]{1,32}){0,2}")      # Area/Place, Area/Region/Place, or UTC, EST5EDT
_lock = threading.Lock()


def valid(name):
    """The name when it is an IANA zone this machine knows, else None."""
    if not isinstance(name, str) or len(name) > 70 or not _SHAPE.fullmatch(name):
        return None
    try:
        ZoneInfo(name)
    except Exception:                       # unknown name, no zone data, an unreadable file: all the same, ignored
        return None
    return name


PINNED = valid(os.environ.get("TZ") or "")      # read once, before apply_zone changes TZ


def apply_zone(name):
    """Set the process zone to `name`; True when it was applied, False when it is not an IANA name (nothing changes).
    Where time.tzset does not exist (Windows) nothing is applied."""
    name = valid(name)
    if name is None or not hasattr(time, "tzset"):
        return False
    with _lock:
        if os.environ.get("TZ") != name:
            os.environ["TZ"] = name
            time.tzset()
    return True


def follow_header(value, in_container):
    """The server's step before routing: apply the page's zone, in the container only and only when no zone is pinned."""
    if in_container and PINNED is None and isinstance(value, str):
        return apply_zone(value.strip())
    return False
