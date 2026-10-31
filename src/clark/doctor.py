"""python3 -m clark.doctor: check what clark needs on this computer, and say what to do in plain words (#57).

    python3 -m clark.doctor [--data FOLDER] [--port N]

What it prints can include folder names (the data folder given with --data is shown in full when it is outside the home
folder), and --help says so once.

Each check prints one line: Ready, To fix, Worth knowing (advice, never a fault) or Not checked. The checks, in order:
- Python is 3.9 or newer and has SQLite (required)
- the data folder can be made and saved in (required)
- the data folder isn't inside OneDrive, where the system can say (required)
- clark's own folder is in OneDrive (advice: set it to always keep its files on this device)
- the browser: Chrome found, or the default browser is used (advice)
- nothing else is using the connection clark needs, asked as the launcher asks (required)
- Claude Code, for ask clark (advice: clark runs without it)

It ends with "Everything clark needs is ready." or how many things to fix. The exit code is 0 when every required check is
ready, 1 otherwise. A check this computer can't do yet (platform.py's NotBuiltYet, as on Windows for now) says so and counts as
not ready; nothing it finds is ever shown as a traceback. It changes nothing: the data folder isn't made, and only a small
temporary file is written (and removed) to see that the folder can be saved in. The paths it shows use ~ for the home folder.
Every system call is in platform.py; `main`'s seams let the tests run it with fakes. Standard library only, Python 3.9.
"""
import argparse
import os
import sys
import tempfile
from collections import namedtuple
from pathlib import Path

from clark import platform

try:
    import sqlite3
except ImportError:                     # a Python built without it: check_python says so
    sqlite3 = None

READY, FIX, ADVICE, NOT_CHECKED = "ready", "fix", "advice", "not checked"
LABELS = {READY: "Ready:", FIX: "To fix:", ADVICE: "Worth knowing:", NOT_CHECKED: "Not checked:"}
MIN_PYTHON = (3, 9)
APP = Path(__file__).resolve().parents[2]       # clark's own folder (the one holding clark.command)
AGAIN = "python3 -m clark.doctor"               # how to run the checks again, said in the lines that ask for it
UNKNOWN_MARK = "not-this-data"                  # asked when the data folder isn't known: no clark answers "this is yours"

Line = namedtuple("Line", "kind words")
Check = namedtuple("Check", "name required run")


class Seen:
    """What the checks look at, and the system calls they make. Each is a seam the tests replace."""

    def __init__(self, data=None, port=None, environ=None, home=None, on=None, version=None, sqlite_version=None,
                 data_dir=None, onedrive_roots=None, find_chrome=None, find_claude=None, health=None, free=None, app=APP):
        self.data, self.port_text, self.home, self.on, self.app = data, port, home, on or platform.system(), Path(app)
        self.environ = os.environ if environ is None else environ
        self.version = tuple(sys.version_info[:3]) if version is None else tuple(version)
        self.sqlite_version = (sqlite3.sqlite_version if sqlite3 else "") if sqlite_version is None else sqlite_version
        self.data_dir = data_dir or (lambda: platform.data_dir(self.home, on=self.on))
        self.onedrive_roots = onedrive_roots or (lambda: platform.onedrive_roots(self.home, on=self.on))
        self.find_chrome = find_chrome or (lambda: platform.find_chrome(self.environ, self.home, on=self.on))
        self.find_claude = find_claude or platform.find_claude
        self.health, self.free = health, free
        self._folder = self._roots = None

    def tilde(self, path):
        return platform.with_tilde(path, self.home)

    def folder(self):
        """The data folder clark would use: --data, or the system's own place (NotBuiltYet where it isn't written yet)."""
        if self._folder is None:
            self._folder = Path(self.data).expanduser() if self.data else Path(self.data_dir())
        return self._folder

    def roots(self):
        if self._roots is None:
            self._roots = list(self.onedrive_roots())
        return self._roots


def check_python(seen):
    version = ".".join(str(n) for n in seen.version)
    if seen.version < MIN_PYTHON:
        if seen.on == platform.MAC:
            return Line(FIX, f"This Mac's Python ({version}) is too old for clark. Type xcode-select --install in Terminal, "
                             "then start clark again.")
        if seen.on == platform.WINDOWS:
            return Line(FIX, "The Python inside clark's folder is missing or too old. Download clark again.")
        return Line(FIX, f"This computer's Python ({version}) is too old for clark, which needs 3.9 or newer. Install a newer "
                         "Python, then start clark again.")
    if not seen.sqlite_version:
        if seen.on == platform.WINDOWS:
            return Line(FIX, "The Python inside clark's folder can't keep clark's data. Download clark again.")
        return Line(FIX, "This Python can't keep clark's data. Install a full copy of Python from python.org, then start clark again.")
    return Line(READY, f"Python {version} is ready.")


def _can_save_in(folder):
    """True if a file can be saved in `folder`, or `folder` can be made where it is meant to go. Nothing is made."""
    folder = Path(folder)
    if folder.exists():
        if not folder.is_dir():
            return False
        try:
            with tempfile.TemporaryFile(dir=str(folder)):
                return True
        except OSError:
            return False
    parent = folder.parent
    while not parent.exists() and parent != parent.parent:
        parent = parent.parent
    return parent.is_dir() and os.access(str(parent), os.W_OK | os.X_OK)


def check_data_folder(seen):
    folder = seen.folder()
    if _can_save_in(folder):
        return Line(READY, f"Your clark data can be saved in {seen.tilde(folder)}.")
    return Line(FIX, f"Your clark data can't be saved in {seen.tilde(folder)}. Check you can save files there, then start "
                     "clark again.")


def check_data_not_in_onedrive(seen):
    folder = seen.folder()
    if platform.inside_onedrive(folder, seen.roots()) is None:
        return Line(READY, "Your clark data isn't inside OneDrive.")
    # The OneDrive folder's own name is not said: on a work computer it holds the organisation's name (PR #80 review).
    return Line(FIX, f"Your clark data is set to go in {seen.tilde(folder)}, which is inside OneDrive. OneDrive copies files "
                     "while they are being written, which damages the data. Choose a folder on this computer that OneDrive "
                     "doesn't sync. Then, in the Terminal window that START-HERE.txt describes, type python3 -m clark --data and "
                     "that folder's name, and press Return. Backups can still go to OneDrive.")


def check_app_folder(seen):
    if platform.inside_onedrive(seen.app, seen.roots()) is None:
        return Line(READY, "Your clark folder isn't in OneDrive.")
    where = "In Finder" if seen.on == platform.MAC else "In File Explorer"
    return Line(ADVICE, f"Your clark folder is in OneDrive. {where}, set it to 'Always keep on this device' so its files are "
                        "always there.")


def check_browser(seen):
    if seen.find_chrome():
        return Line(READY, "Chrome is there, so clark opens in its own window.")
    return Line(ADVICE, "Chrome wasn't found, so clark will open in your usual browser. Install Chrome to give clark its own "
                        "window.")


def check_port(seen):
    from clark import appfiles, launch, server       # here, so the Python check still runs on a Python too old for these
    from clark.__main__ import Usage, port_number, port_free
    given = seen.port_text is not None
    where = "--port" if given else "CLARK_PORT"
    try:
        port = port_number(seen.port_text if given else (seen.environ.get("CLARK_PORT") or server.DEFAULT_PORT), where)
    except Usage:                               # the doctor's own words, not __main__'s (PR #65 has that file)
        return Line(FIX, f"The start-up number (set with {where}) must be a whole number from 1 to 65535. Change it, then "
                         f"run {AGAIN} again.")
    try:
        folder = seen.folder()
    except platform.PlatformError:
        folder = None
    mark = appfiles.data_mark(folder) if folder is not None else UNKNOWN_MARK
    kind = (seen.health or launch.ask_health)(port, mark)
    if kind == launch.NOTHING:
        return Line(READY, "Nothing else on this computer is in the way of clark starting.")
    if kind == launch.OURS:
        return Line(READY, "Your clark is already running with this data.")
    if kind == launch.OTHER_DATA and folder is None:
        return Line(READY, "A copy of clark is already running on this computer.")
    return Line(FIX, launch.report(kind, port, folder, seen.free or port_free).replace("\n", " "))


def check_claude(seen):
    try:
        found = seen.find_claude()
    except platform.NotBuiltYet:
        raise                                   # said as "can't run on this computer yet" by run_check
    except platform.PlatformError as e:
        return Line(ADVICE, str(e))
    if found:
        return Line(READY, "Claude Code is installed, so you can ask clark for help.")
    return Line(ADVICE, "Claude Code wasn't found, so ask clark can't run. The rest of clark works without it. To use ask "
                        "clark, install Claude Code, then start clark again.")


CHECKS = (
    Check("The Python check", True, check_python),
    Check("The data folder check", True, check_data_folder),
    Check("The OneDrive check for your data", True, check_data_not_in_onedrive),
    Check("The OneDrive check for the clark folder", False, check_app_folder),
    Check("The browser check", False, check_browser),
    Check("The check that nothing is in the way", True, check_port),
    Check("The Claude Code check", False, check_claude),
)


def run_check(check, seen):
    """One check's line. Never raises: a check this system can't do yet, or one that stops, says so plainly."""
    try:
        return check.run(seen)
    except platform.NotBuiltYet:
        return Line(NOT_CHECKED, f"{check.name} can't run on this computer yet.")
    except Exception:                           # noqa: BLE001 - never a traceback, nor the computer's own error text
        return Line(NOT_CHECKED, f"{check.name} couldn't finish. Run python3 -m clark.doctor again.")


def summary(results):
    """The last line, and the exit code."""
    to_fix = sum(1 for check, line in results if line.kind == FIX)
    unknown = sum(1 for check, line in results if check.required and line.kind == NOT_CHECKED)
    if to_fix:
        return (f"{to_fix} {'thing' if to_fix == 1 else 'things'} to fix before clark can start. Fix "
                f"{'it' if to_fix == 1 else 'each one'}, then run {AGAIN} again."), 1
    if unknown:
        return ("Some checks can't run on this computer yet, so we can't say whether clark will start. Try starting it; if "
                "it won't, tell the clark team."), 1
    return "Everything clark needs is ready.", 0


def doctor(seen, say=print, checks=CHECKS):
    """Run every check and say its line, then the summary. The exit code: 0 all required checks ready, 1 not."""
    say("Checking what clark needs on this computer...")
    results = []
    for check in checks:
        line = run_check(check, seen)
        results.append((check, line))
        say(f"{LABELS[line.kind]} {line.words}")
    last, code = summary(results)
    say(last)
    return code


def parser():
    p = argparse.ArgumentParser(prog="python3 -m clark.doctor",
                                description="Check what clark needs on this computer, and say what to do.",
                                epilog="What it prints can include the names of folders on this computer, so look it over "
                                       "before you share it.")
    p.add_argument("--data", metavar="FOLDER", help="the folder for clark's data (default: clark's own folder on this "
                                                    "computer)")
    p.add_argument("--port", metavar="N", help="the number clark starts with (advanced; default: the CLARK_PORT setting, or "
                                               "the usual one)")
    return p


def main(argv=None, say=print, **seams):
    """The command. `seams` are Seen's fakes (environ, home, on, health, find_chrome, ...)."""
    args = parser().parse_args(argv)
    try:
        return doctor(Seen(data=args.data, port=args.port, **seams), say)
    except KeyboardInterrupt:
        return 1
    except Exception:                           # noqa: BLE001 - never a traceback, nor the computer's own error text
        say("The checks stopped before the end. Run python3 -m clark.doctor again; if it keeps happening, tell the clark team.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
