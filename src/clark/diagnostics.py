"""Copy diagnostics: a plain-text report a person can paste into a message to get help (#110, BRD FR-8b).

It holds the version, Python and the system, the log level, an allow-list of safe settings, counts, the errors of the last
7 days (area and a fixed message, with how many and when) and the last 200 log lines scrubbed once more. It never holds a
profile name, an email address, a project name, a title, a note or a path to the home folder: settings come only from the
allow-list below and only as numbers, yes/no or one of the listed words; counts are numbers. Standard library only.
"""
import platform as stdlib_platform
import re
import sys
from datetime import datetime

from clark import log as clog

LAST_LINES = 200
# The settings that may appear, and the words each may have (None: a number or yes/no only). Add a name here to show it.
SAFE_SETTINGS = {"log_level": {"normal", "debug"}, "appearance": {"system", "light", "dark"}, "update_check": None,
                 "report_sections_shown": None, "backup_on": None}
# The counts that may appear (names fixed here, values whole numbers only). Add a name here to show it.
COUNT_NAMES = frozenset("projects actions risks issues decisions milestones promises reports items errors warnings".split())
SYSTEM_NAMES = {"darwin": "macOS", "win32": "Windows", "linux": "Linux"}
INDENT = re.compile(r"^ {4}")


def safe_settings(settings):
    """The allow-listed settings with a safe value, in the allow-list's order: numbers and yes/no, or one of the listed words.
    Anything else (an unknown name, other text) is left out."""
    out = []
    for name, words in SAFE_SETTINGS.items():
        if not isinstance(settings, dict) or name not in settings:
            continue
        v = settings[name]
        if isinstance(v, bool):
            shown = "yes" if v else "no"
        elif isinstance(v, int):
            shown = str(v)
        elif isinstance(v, str) and words and v in words:
            shown = v
        else:
            continue
        out.append((name, shown))
    return out


def system_line(system=None, release=None):
    name = SYSTEM_NAMES.get(system or sys.platform, "Other system")
    return f"{name} {clog.scrub(release if release is not None else stdlib_platform.release(), 40)}".strip()


def build(log, version, settings=None, counts=None, home=None, now=None, python=None, system=None, release=None):
    """The report as text. `counts` is {name: number}; a name that is not in COUNT_NAMES or a value that is not a
    whole number is left out."""
    now = now or log.clock()
    home = home if home is not None else log.home
    lines = ["Diagnostics report", f"Made on {now:%d-%m-%Y %H:%M}", "",
             f"Version: {clog.scrub(version, 40)}",
             f"Python: {python or '.'.join(str(x) for x in sys.version_info[:3])}",
             f"System: {system_line(system, release)}",
             f"Logging: {log.level()}"]
    notice = log.debug_notice()
    if notice:
        lines.append(notice)
    shown = safe_settings(settings)
    if shown:
        lines += ["", "Settings"] + [f"  {k}: {v}" for k, v in shown]
    pairs = [(k, v) for k, v in (counts or {}).items()
             if k in COUNT_NAMES and isinstance(v, int) and not isinstance(v, bool)]
    if pairs:
        lines += ["", "Counts"] + [f"  {k}: {v}" for k, v in pairs]
    errors = log.errors()
    lines += ["", "Errors in the last 7 days"]
    lines += ([f"  {g['count']} x {g['area']}: {g['message']} (last {g['last']:%d-%m-%Y %H:%M})" for g in errors]
              if errors else ["  None"])
    lines += ["", f"Last {LAST_LINES} log lines"]
    lines += ["  " + clog.scrub_line(x, 300, home) for x in log.tail(LAST_LINES)] or ["  None"]
    return "\n".join(lines) + "\n"
