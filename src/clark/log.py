"""The daily log and what it may hold (#110, BRD FR-8b).

One plain-text file a day in the log folder (`platform.log_dir()`), `clark-YYYY-MM-DD.log`, one line per entry:

    2026-10-28 14:32:05 INFO  server       change saved  route=/api/change status=200 ms=12

Never content. A line holds a time, a level, an area, a FIXED message and details that are numbers, yes/no, an item ID or
a route clark itself serves. Any other text passed as a detail (a title, a name, a note, a prompt, a file name, an address,
a token) is not written: it becomes `<text, N characters>`. The message is scrubbed too (the home folder becomes `~`,
addresses, quoted text and long tokens go), and a fault is logged as its class name and where it happened (file name, line,
function), never its text, since a fault's text often quotes what was being read. Standard library only, Python 3.9.
A message is a fixed text written in the code (a constant): a value goes in a detail, never in the message, because a bare
word in a message is written as it is. tests/test_log.py scans src/ and fails on a log call with a message built at run time.

Rules the module keeps:
  - A write never raises. A read-only folder, a full disk or a bad setting leaves clark running.
  - Normal ("info") and Debug; warnings and errors are always written. The level is read with a cache; a bad value keeps Normal.
  - A day's file stops at 5 MB with one line saying so. Its last tenth is kept for warnings and errors (#234): normal and Debug
    lines stop at 4.5 MB with one line saying so, so a burst of ordinary lines can never push out a later fault. Today and the six days before it are kept; the first entry of a new
    day removes older files, and only files this module names (`clark-DATE.log`). A file dated in the future (a clock that was
    ahead) is never removed, and never makes today's cut-off later.
  - Each entry is one append, so two processes never mix a line.
  - Page errors are rate-limited to 20 a minute (the rest are dropped, no line is written for them), with quoted text, addresses, paths and addresses on the web removed.

(creaite v2.6.11 `system/scripts/log.py`, rewritten; see the reuse record.)
"""
import json
import logging
import os
import re
import threading
import time
import traceback
from datetime import date, datetime, timedelta
from pathlib import Path

from clark import platform

LEVELS = {"debug": 10, "info": 20, "warn": 30, "error": 40}
LABELS = {10: "DEBUG", 20: "INFO ", 30: "WARN ", 40: "ERROR"}
NORMAL, DEBUG = "normal", "debug"
MAX_BYTES = 5 * 1024 * 1024
KEEP_DAYS = 7
PAGE_ERRORS_PER_MINUTE = 20
DEBUG_NOTICE_AFTER_DAYS = 7
MESSAGE_LIMIT = 120
RESERVE_PART = 10                  # the last tenth of a day's file is kept for warnings and errors (#234)
FULL_NOTICE = "log full for today, only warnings and errors are kept from now on"
LAST_NOTICE = "log full for today, later entries are not kept"
FILE = re.compile(r"clark-(\d{4}-\d{2}-\d{2})\.log$")
ENTRY = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (DEBUG|INFO|WARN|ERROR)\s+(\S+)\s*(.*)$")
CONTROL = re.compile(r"[\x00-\x1f\x7f-\x9f\u2028\u2029]+")
AREA_OK = re.compile(r"[^A-Za-z0-9_.-]+")
ITEM_ID = re.compile(r"[A-Z][A-Z0-9]{1,6}-[A-Z]{1,2}-\d{1,6}\Z")      # ABC-A-003 (a project code, a kind letter, a number)
KEY_OK = re.compile(r"[a-z][a-z0-9_]{0,24}\Z")
ROUTE_OK = re.compile(r"/(?:api/)?[a-z][a-z0-9_-]{0,30}(?:/[a-z][a-z0-9_-]{0,30}){0,3}\Z")
NAME_OK = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,60}\Z")                    # a Python class or function name
QUOTED = re.compile(r"'[^']*'|\"[^\"]*\"|“[^”]*”|‘[^’]*’|`[^`]*`")
ADDRESS = re.compile(r"\S+@\S+")
WEB = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*://\S+|\bwww\.\S+")
PATH_LIKE = re.compile(r"(?<![\w/])(?:[A-Za-z]:[\\/]|~[\\/]|/|\\\\)[^\s]*")
HOME_LIKE = re.compile(r"(?:/Users|/home|[A-Za-z]:[\\/]Users)[\\/][^\s]*", re.IGNORECASE)
TOKEN = re.compile(r"[A-Za-z0-9_\-+=]{24,}")
GONE = "…"
METHODS = frozenset("GET POST HEAD OPTIONS".split())


def text_marker(value):
    """What stands for text that must not be written: its length only."""
    n = len(str(value))
    return f"<text, {n} character{'' if n == 1 else 's'}>"


def home_to_tilde(text, home=None):
    """The home folder written as `~` (either slash, and the folder's name in any case); the person's name never shows."""
    try:
        home = str(home if home is not None else Path.home())
    except (RuntimeError, KeyError):
        return text
    if len(home) < 2:
        return text
    for form in {home, home.replace("\\", "/"), home.replace("/", "\\")}:
        text = re.sub(re.escape(form), "~", text, flags=re.IGNORECASE)
    return text


def scrub(text, limit=MESSAGE_LIMIT, home=None, keep=None):
    """One safe line from a message: home folder to `~`, web addresses, email addresses, quoted text, other paths and long
    tokens replaced, control characters (newlines too) spaces, and a long text cut. A path that is exactly one of the routes in
    `keep` (the ones clark itself serves) stays, so a request line still says which route it was."""
    t = str(text)
    t = home_to_tilde(t, home)
    t = WEB.sub(GONE, t)
    t = ADDRESS.sub(GONE, t)
    t = QUOTED.sub(GONE, t)
    t = PATH_LIKE.sub(lambda m: m.group(0) if keep and m.group(0) in keep
                      else "~/" + GONE if m.group(0).startswith(("~/", "~\\")) else GONE, t)
    t = TOKEN.sub(GONE, t)
    t = CONTROL.sub(" ", t).strip()
    return t if len(t) <= limit else t[:limit - 1] + GONE


def scrub_line(line, limit=300, home=None):
    """A log line read back for a report: the home folder to `~`, any other home-folder path, web and email addresses
    removed. Routes and the line's own shape are kept."""
    t = home_to_tilde(str(line), home)
    t = HOME_LIKE.sub(GONE, WEB.sub(GONE, ADDRESS.sub(GONE, t)))
    t = CONTROL.sub(" ", t).rstrip()
    return t if len(t) <= limit else t[:limit - 1] + GONE


# The only words a page error's text may keep: the browsers' own wording for a fault. Any other word (a title, a name, a
# note, anything a person typed) becomes …, so a page error can say what kind of fault it was and never what it was about.
PAGE_WORDS = frozenset("""a an and are as at be but by cannot can could not read write set get of in on to is it its for from
    undefined null properties property reading setting is not function object array string number value values defined
    defined iterator iterable constructor class new this that with without no more than less empty invalid unexpected
    token end input json parse expected missing failed fetch network request load loading error errors type reference
    syntax range maximum call stack size exceeded script resource blocked policy access denied aborted timeout timed out
    out undefined variable assignment constant typeerror referenceerror syntaxerror rangeerror""".split())


# The only names a page error may carry for its kind: the browsers' own fault classes. Any other name is written as Error.
PAGE_KINDS = frozenset("Error TypeError ReferenceError SyntaxError RangeError EvalError URIError".split())


def page_words(message, limit=100):
    """A page error's text cut to the browsers' own fault words; every other word, number or mark becomes …."""
    words = re.findall(r"[A-Za-z]+|[^\sA-Za-z]+", CONTROL.sub(" ", str(message)))
    kept, gap = [], False
    for w in words:
        if w.lower() in PAGE_WORDS:
            kept.append(w)
            gap = False
        elif not gap:
            kept.append(GONE)
            gap = True
    t = " ".join(kept)
    return t if len(t) <= limit else t[:limit - 1] + GONE


def area_of(area):
    """An area name safe for one log column: letters, digits and _.- only, at most 12 characters."""
    return AREA_OK.sub("_", str(area).strip())[:12] or "app"


def detail(value, routes=None):
    """One detail value as it may be written: a number or yes/no as is; an item ID, a known route or a short class name as
    is; anything else (any other text) as its length marker."""
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return f"{value:.1f}"
    if value is None:
        return "none"
    s = str(value)
    if ITEM_ID.match(s) or s in METHODS:
        return s
    if routes is not None and s in routes:
        return s
    return text_marker(s)


def details(pairs, routes=None):
    """`key=value` for each detail, in the order given. A key that is not a short lower-case word is dropped (a key is code,
    never data); each value goes through `detail`."""
    out = []
    for key, value in (pairs or {}).items():
        if KEY_OK.match(str(key)):
            out.append(f"{key}={detail(value, routes)}")
    return " ".join(out)


def fault_of(exc):
    """A fault as (class name, [where it happened]): never its text, never the source line. Where is `file.py:12 function`."""
    kind = type(exc).__name__ if exc is not None else ""
    kind = kind if NAME_OK.match(kind) else "Exception"
    where = []
    try:
        for fr in traceback.extract_tb(exc.__traceback__)[-8:]:
            name = Path(fr.filename.replace("\\", "/")).name
            func = fr.name if NAME_OK.match(fr.name) or fr.name == "<module>" else "?"
            where.append(f"{scrub(name, 40)}:{fr.lineno} {func}")
    except Exception:
        pass
    return kind, where


class Log:
    """The log for one folder. `folder` is where the files go; `data` is where the level is kept (diagnostics.json)."""

    def __init__(self, folder, data=None, clock=None, home=None, routes=None):
        self.folder = Path(folder)
        self.data = Path(data) if data is not None else None
        self.clock = clock or datetime.now
        self.home = home
        self.routes = set(routes) if routes is not None else None
        self._level_cache = (None, NORMAL)
        self._page = []
        self._lock = threading.Lock()

    # The level

    @property
    def level_file(self):
        return self.data / "diagnostics.json" if self.data is not None else None

    def _read_state(self):
        try:
            state = json.loads(self.level_file.read_text(encoding="utf-8"))
            return state if isinstance(state, dict) else {}
        except Exception:
            return {}

    def level(self):
        """"normal" or "debug". Cached until the file changes; a missing file or a bad value keeps Normal."""
        try:
            stamp = self.level_file.stat().st_mtime_ns
        except Exception:
            self._level_cache = (None, NORMAL)
            return NORMAL
        if self._level_cache[0] != stamp:
            value = self._read_state().get("level")
            self._level_cache = (stamp, DEBUG if value == DEBUG else NORMAL)
        return self._level_cache[1]

    def set_level(self, level):
        """Save the level. Debug records the day it was switched on; Normal clears it. Returns the level now in force (the old one when the file cannot be written; never raises)."""
        level = DEBUG if str(level).lower() == DEBUG else NORMAL
        state = self._read_state()
        if level == DEBUG:
            if state.get("level") != DEBUG or not state.get("debug_since"):
                state["debug_since"] = self.clock().date().isoformat()
        else:
            state.pop("debug_since", None)
        state["level"] = level
        try:
            platform.write_file(self.level_file, json.dumps(state, sort_keys=True) + "\n")
        except Exception:
            pass                                   # a folder that cannot be written keeps the old level; never raises
        self._level_cache = (None, NORMAL)
        return self.level()

    def debug_days(self):
        """How many days Debug has been on, or 0 when it is off or the day is unknown."""
        try:
            if self.level() != DEBUG:
                return 0
            since = date.fromisoformat(self._read_state().get("debug_since", ""))
            return max(0, (self.clock().date() - since).days)
        except Exception:
            return 0

    def debug_notice(self):
        """The line Settings shows once Debug has been on for more than 7 days, or ""."""
        days = self.debug_days()
        if days <= DEBUG_NOTICE_AFTER_DAYS:
            return ""
        return f"Debug has been on for {days} days. It keeps more detail, so switch it back to Normal when you have finished."

    # Writing

    def path_for(self, day):
        return self.folder / f"clark-{day.isoformat()}.log"

    def _emit(self, level, area, message, pairs=None, extra=()):
        try:
            if level < 30 and level < LEVELS[DEBUG if self.level() == DEBUG else "info"]:
                return
            now = self.clock()
            path = self.path_for(now.date())
            self.folder.mkdir(parents=True, exist_ok=True)
            with self._lock:
                if not path.exists():
                    self.prune_on_new_day(now.date())
                size = path.stat().st_size if path.exists() else 0
                normal_cap = MAX_BYTES - MAX_BYTES // RESERVE_PART
                if size >= MAX_BYTES:
                    if LAST_NOTICE not in self._last_bytes(path):
                        self._append(path, f"{now:%Y-%m-%d %H:%M:%S} {LABELS[30]} {'log':<12} {LAST_NOTICE}\n")
                    return
                if level < 30 and size >= normal_cap:
                    return                             # the rest of the day's file is kept for warnings and errors
                head = f"{now:%Y-%m-%d %H:%M:%S} {LABELS[level]} {area_of(area):<12} {scrub(message, home=self.home, keep=self.routes)}"
                tail = details(pairs, self.routes)
                lines = [head + ("  " + tail if tail else "")] + ["    " + x for x in extra]
                text = "\n".join(lines) + "\n"
                self._append(path, text)
                if size < normal_cap <= size + len(text.encode("utf-8")):
                    self._append(path, f"{now:%Y-%m-%d %H:%M:%S} {LABELS[30]} {'log':<12} {FULL_NOTICE}\n")
        except Exception:
            pass                                       # a log write never raises

    @staticmethod
    def _append(path, text):
        fd = os.open(str(path), os.O_WRONLY | os.O_APPEND | os.O_CREAT | getattr(os, "O_BINARY", 0), 0o600)
        try:
            os.write(fd, text.encode("utf-8"))         # one write per entry, so two writers never mix a line
        finally:
            os.close(fd)

    @staticmethod
    def _last_bytes(path, n=300):
        try:
            with open(str(path), "rb") as f:
                f.seek(max(0, path.stat().st_size - n))
                return f.read().decode("utf-8", "replace")
        except OSError:
            return ""

    def debug(self, area, message, **pairs):
        self._emit(10, area, message, pairs)

    def info(self, area, message, **pairs):
        self._emit(20, area, message, pairs)

    def warn(self, area, message, **pairs):
        self._emit(30, area, message, pairs)

    def error(self, area, message, **pairs):
        self._emit(40, area, message, pairs)

    def exception(self, area, message, exc=None, **pairs):
        """An error entry for a fault (the one given, or the one being handled): its class and where it happened."""
        try:
            if exc is None:
                import sys
                exc = sys.exc_info()[1]
            kind, where = fault_of(exc)
            self._emit(40, area, f"{message} ({kind})", pairs, extra=where)
        except Exception:
            pass

    def page_error(self, kind, message, now=None):
        """A fault the page reported through the local server. At most 20 a minute (a burst past that is dropped without a line:
        a flood must not fill the log). The text has quoted text, addresses, web addresses and paths removed. Returns
        True when it was written."""
        try:
            t = time.monotonic() if now is None else now
            with self._lock:
                self._page = [x for x in self._page if t - x < 60]
                if len(self._page) >= PAGE_ERRORS_PER_MINUTE:
                    return False
                self._page.append(t)
            name = str(kind) if str(kind) in PAGE_KINDS else "Error"
            self._emit(40, "page", f"{name}: {page_words(message)}")
            return True
        except Exception:
            return False

    # Keeping only the last days

    def files(self):
        """The log files, oldest first."""
        try:
            return sorted(p for p in self.folder.iterdir() if p.is_file() and FILE.match(p.name))
        except OSError:
            return []

    def prune(self, today=None):
        """Remove files dated before the last 7 days (today and the six before). Only `clark-DATE.log` files; a file dated
        after today (a clock that was ahead) stays and changes nothing. Returns the names removed."""
        removed = []
        try:
            today = today or self.clock().date()
            cutoff = today - timedelta(days=KEEP_DAYS - 1)
            for p in self.files():
                try:
                    when = date.fromisoformat(FILE.match(p.name).group(1))
                except ValueError:
                    continue
                if when < cutoff:
                    try:
                        p.unlink()
                        removed.append(p.name)
                    except OSError:
                        pass
        except Exception:
            pass
        return removed

    def prune_on_new_day(self, today):
        """Prune, unless no log is dated in the last 6 days before today: a first entry after a long break, or from a
        clock that jumped far ahead, then keeps what is there (the next day's first entry prunes once yesterday's file
        is in the window). A clock set ahead is not told apart from the real time any other way."""
        recent = [p for p in self.files()
                  if today - timedelta(days=KEEP_DAYS - 1) <= date.fromisoformat(FILE.match(p.name).group(1)) < today]
        return self.prune(today) if recent else []

    # Reading

    @staticmethod
    def _lines(p):
        """A file's lines, split on newlines only (a stray separator such as U+0085 never splits an entry)."""
        text = p.read_text(encoding="utf-8", errors="replace")
        return (text[:-1] if text.endswith("\n") else text).split("\n") if text else []

    def tail(self, n=200):
        """The last n lines across the files up to today (a file dated after today is left out), oldest first."""
        out = []
        try:
            today = self.clock().date()
            for p in reversed(self.files()):
                if date.fromisoformat(FILE.match(p.name).group(1)) > today:
                    continue
                out = self._lines(p) + out
                if len(out) >= n:
                    break
        except Exception:
            pass
        return out[-n:]

    def _since(self, first):
        """Every line of the files dated `first` to today, oldest first (nothing older is read)."""
        out = []
        try:
            today = self.clock().date()
            for p in self.files():
                if first <= date.fromisoformat(FILE.match(p.name).group(1)) <= today:
                    out += self._lines(p)
        except Exception:
            pass
        return out

    def errors(self, days=KEEP_DAYS):
        """[{count, area, message, last}] for the errors in the last `days` days, grouped by area and message (numbers
        ignored), most recent first."""
        since = self.clock() - timedelta(days=days)
        seen = {}
        for line in self._since(since.date()):
            m = ENTRY.match(line)
            if not m or m.group(2) != "ERROR":
                continue
            at = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
            if at < since or at > self.clock():
                continue
            msg = re.sub(r"\d+", "#", m.group(4).split("  ")[0])
            g = seen.setdefault((m.group(3), msg), {"count": 0, "area": m.group(3), "message": msg, "last": at})
            g["count"] += 1
            g["last"] = max(g["last"], at)
        return sorted(seen.values(), key=lambda g: g["last"], reverse=True)


class Bridge(logging.Handler):
    """Sends clark's standard `logging` records (the server's `LOG.info("%s %s", ...)`) through the same scrub: the record's
    fixed template is the message, and each argument goes through `detail` (numbers and routes as they are, other text as
    its length), so a path or a body in an argument never reaches a file."""

    def __init__(self, log):
        super().__init__(level=logging.DEBUG)
        self.log = log

    def emit(self, record):
        try:
            args = record.args if isinstance(record.args, tuple) else ((record.args,) if record.args else ())
            shown = tuple(a if isinstance(a, (int, float)) and not isinstance(a, bool) else detail(a, self.log.routes) for a in args)
            try:
                message = str(record.msg) % shown
            except Exception:
                message = str(record.msg)
            area = record.name.split(".")[-1]
            if record.exc_info and record.exc_info[1] is not None:
                self.log.exception(area, message, record.exc_info[1])
            else:
                level = {logging.DEBUG: 10, logging.INFO: 20, logging.WARNING: 30}.get(record.levelno, 40)
                self.log._emit(level, area, message)
        except Exception:
            pass


def install(log, logger_name="clark"):
    """Route the `clark` loggers into `log` (once); returns the handler."""
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)
    for h in list(logger.handlers):
        if isinstance(h, Bridge):
            logger.removeHandler(h)
    handler = Bridge(log)
    logger.addHandler(handler)
    return handler


def default(data=None, routes=None):
    """The log for this computer: the platform's log folder, the level kept in the data folder."""
    return Log(platform.log_dir(), data=data, routes=routes)
