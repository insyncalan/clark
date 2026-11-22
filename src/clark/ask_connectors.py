"""Row 1306 C2: which connectors are set up on this computer (discovery only; nothing here uses a connector).

`list_found` runs the Claude command's own `mcp list` (it health-checks each server, so it can take a while), reads ONLY the name
and the status of each line, keeps the lines whose status says Connected, and maps the name through an EXACT fixed table. A name
that is not in the table is ignored; a name is never guessed from a pattern. The address on a line, tokens and config files are
never read, kept or returned. Any failure of the command gives an empty list.

The command runs with the same scrubbed environment as ask clark's provider (`ask_claude.child_env`), through the one place that
starts programs (`platform.run_stoppable`). The runner is injected, so the parsing and the table are testable without a sign-in.
"""
import re
import threading
import time

from clark import ask_claude, platform

LIST_ARGS = ("mcp", "list")
TIME_LIMIT = 30          # seconds: the command health-checks every server
MAX_OUT = 64 * 1024      # bytes read back
MAX_LINES = 200          # lines looked at
CACHE_SECONDS = 60
CONNECTED = "connected"

# EXACT server name -> ((connector, label), ...). Nothing else is ever listed.
TABLE = {
    "claude.ai Microsoft 365": (("mail", "Mail"), ("calendar", "Calendar"), ("teams", "Teams"),
                                ("sharepoint", "SharePoint and OneDrive")),
    "claude.ai Todoist": (("todoist", "Todoist"),),
}

# '<name>: <url> - <status>': the name has no colon followed by a space; the status is what follows the LAST ' - '.
_LINE = re.compile(r"^(?P<name>[^:\n]{1,100}): (?P<rest>.+) - (?P<status>[^\n]{1,100})$")
_STATUS_MARK = re.compile(r"^[^\w]*")


def parse(text):
    """The names whose status says Connected, in order, each once. Only name and status are read from a line."""
    if not isinstance(text, str):
        return []
    found = []
    for line in text[:MAX_OUT].splitlines()[:MAX_LINES]:
        m = _LINE.match(line.strip())
        if not m:
            continue
        status = _STATUS_MARK.sub("", m.group("status")).strip().lower()
        if status == CONNECTED and m.group("name") not in found:
            found.append(m.group("name"))
    return found


def map_found(names):
    """[{connector, label, server}] for the names in the fixed table; every other name is ignored."""
    out = []
    for name in names:
        for connector, label in TABLE.get(name, ()):
            out.append({"connector": connector, "label": label, "server": name})
    return out


def default_runner():
    """Run `<claude> mcp list` and return its standard output text, or None. Never raises."""
    try:
        path, _why = ask_claude.find_command()
        if path is None:
            return None
        status, out, _code = platform.run_stoppable([str(path), *LIST_ARGS], b"", ask_claude.child_env(), TIME_LIMIT, MAX_OUT,
                                                    stop=threading.Event(), prefix="clark-mcp-")
        if status != "ok":
            return None
        return out.decode("utf-8", "replace")
    except Exception:
        return None


NO_SERVERS = re.compile(r"no mcp servers", re.I)


def parse_all(text):
    """(ok, names): EVERY server name on a list line, whatever its status, each once. ok is False when the output cannot be
    trusted: not text, blank, or no line has the 'name: address - status' shape and it does not say there are no servers."""
    if not isinstance(text, str) or not text.strip():
        return False, []
    names, shaped = [], False
    for line in text[:MAX_OUT].splitlines()[:MAX_LINES]:
        m = _LINE.match(line.strip())
        if m:
            shaped = True
            if m.group("name") not in names:
                names.append(m.group("name"))
    if not shaped and not NO_SERVERS.search(text[:MAX_OUT]):
        return False, []
    return True, names


def list_fresh(run=None):
    """(ok, entries) from a NEW run of the list command, every time: the cache is neither read nor written. entries are
    [{connector, label, server}] for every listed server of any status; a server outside the fixed table gets connector
    "other" (its name only is kept). ok is False when the command failed or its output is unreadable: an empty list with ok
    True means there really are none. Never raises."""
    try:
        text = (run or default_runner)()
    except Exception:
        return False, []
    ok, names = parse_all(text)
    if not ok:
        return False, []
    out = []
    for name in names:
        rows = TABLE.get(name)
        if rows:
            out.extend({"connector": c, "label": l, "server": name} for c, l in rows)
        else:
            out.append({"connector": "other", "label": "", "server": name})
    return True, out


_cache = {"at": None, "value": []}
_lock = threading.Lock()


def clear_cache():
    with _lock:
        _cache["at"] = None
        _cache["value"] = []


def list_found(run=None, now=time.monotonic):
    """The connectors set up and connected on this computer. `run()` returns the command's output text (or None); it is the seam
    for tests. Cached for CACHE_SECONDS (a failure is not cached). Never raises."""
    with _lock:
        t = now()
        if _cache["at"] is not None and 0 <= t - _cache["at"] < CACHE_SECONDS:
            return [dict(x) for x in _cache["value"]]
    try:
        text = (run or default_runner)()
    except Exception:
        text = None
    if not isinstance(text, str):
        return []
    value = map_found(parse(text))
    with _lock:
        _cache["at"] = now()
        _cache["value"] = value
    return [dict(x) for x in value]
