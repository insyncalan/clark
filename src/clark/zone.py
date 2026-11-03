"""The time zone clark's clock is read in, inside the shipped container (#631; the logic only, server.py and __main__.py wire it in).

A container runs in UTC, so in Dubai from midnight to 04:00 (and in New York in the evening) 'today' would be a day out: a new
item's created date, a report's 'as at' date, the future-date check, the Excel and Word dates, the log lines, and History's
times and offset. Every one of those reads the process zone (store.today, milestones.today, sneak.today,
movement_read.today_text, store.local_offset, excel.day and excel.exported_text, timefmt, the log), so this module sets that
one zone and they all follow. There is no second copy of it anywhere.

Where the zone comes from, in this order:
- TZ given to the container at its start (the compose file's optional pin): when it is a real zone name it wins and the page
  is not asked;
- else the page's own zone, sent as X-Clark-Tz on its requests and on the "still here" every 10 seconds, so a laptop that
  travels follows within a few seconds;
- else nothing changes: the process zone stays as it started (UTC in a container).
A name is taken only when it is an IANA name this machine knows (Asia/Dubai, America/New_York, UTC). Anything else (a Windows
zone id such as "Arabian Standard Time", a path, an empty value) is ignored and never logged.

Only inside the shipped container: on a Mac the process already has the person's zone, and time.tzset does not exist on
Windows. The container test mirrors #427's container_mode (CLARK_CONTAINER=1 and a container marker file); once #427 is on main
this can use platform.container_mode instead. Standard library only, Python 3.9.
"""
import os
import re
import threading
import time

try:
    from zoneinfo import ZoneInfo
except ImportError:              # pragma: no cover  (Python 3.9 has it; a build without it takes no zone)
    ZoneInfo = None

HEADER = "X-Clark-Tz"
NAME = re.compile(r"[A-Za-z][A-Za-z0-9_+-]{0,30}(?:/[A-Za-z0-9_+-]{1,30}){0,2}")      # Area/Location[/More], or UTC
CONTAINER_MARKERS = ("/.dockerenv", "/run/.containerenv")


def container_mode(environ=None, exists=os.path.exists):
    """True only when CLARK_CONTAINER=1 is set (by the shipped Dockerfile) and this really is a container (#427's test)."""
    environ = os.environ if environ is None else environ
    return environ.get("CLARK_CONTAINER") == "1" and any(exists(p) for p in CONTAINER_MARKERS)


def valid(name):
    """`name` when it is an IANA zone name this machine has, else None. Never raises, whatever it is given."""
    if not isinstance(name, str) or ZoneInfo is None or not NAME.fullmatch(name) or ".." in name:
        return None
    try:
        ZoneInfo(name)
    except Exception:  # noqa: BLE001  an unknown, odd or unreadable name is simply not taken
        return None
    return name


class Zone:
    """The process zone, set from one place. `environ` and `tzset` are seams for tests (the real ones by default)."""

    def __init__(self, environ=None, tzset=None):
        self.environ = os.environ if environ is None else environ
        self.tzset = tzset or getattr(time, "tzset", None)
        self.pin = valid(self.environ.get("TZ"))       # the compose file's TZ, when it is a real name
        self.current = self.pin
        self.lock = threading.Lock()

    def apply(self, name):
        """Use zone `name` from now on; True when it changed. Nothing changes for a pinned zone, a name that is not a real one,
        the zone already in use, or a system with no tzset."""
        if self.pin or self.tzset is None:
            return False
        name = valid(name)
        if name is None or name == self.current:
            return False
        with self.lock:
            self.environ["TZ"] = name
            self.tzset()
            self.current = name
        return True


def make(environ=None, tzset=None, container=None):
    """The server's apply_zone(name) inside the shipped container, else None (nothing to set: the Mac route is unchanged)."""
    environ = os.environ if environ is None else environ
    inside = container_mode(environ) if container is None else container
    return Zone(environ, tzset).apply if inside else None
