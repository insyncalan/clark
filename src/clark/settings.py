"""The smallest reading seam for clark's settings (#111): `<data folder>/settings.json`, read with defaults.

There is no settings store in clark yet (FR-1 is still to come). This file holds only what a built item needs today, the number of
backups kept, so that item has one place to read it. A later settings module replaces the reading and writing here and keeps the
names (`backups_kept`, `set_backups_kept`) and the file. Nothing here names a path outside the data folder it is given.

The file is a JSON object. A missing file, a file that isn't a JSON object, a value of the wrong kind or one out of range is not an
error: the default is used, so a bad settings file can never stop a backup or its tidying up. Standard library only, Python 3.9.
"""
import json
from pathlib import Path

from clark import platform

FILE = "settings.json"
LIMIT = 64 * 1024                       # a settings file larger than this is not read
BACKUPS_KEPT = "backups_kept"
BACKUPS_KEPT_DEFAULT = 14               # = backup.KEEP; a test keeps the two equal
BACKUPS_KEPT_RANGE = (1, 365)

# What Settings › Safety says about the number, in plain words (the page shows these, not the key).
BACKUPS_KEPT_LABEL = "How many backups to keep"
BACKUPS_KEPT_HELP = ("This many backups are kept of each kind (daily, before an undo, before an import and so on); the oldest "
                     "are removed after that. 14 is usual. The newest backup is always kept.")


def read(data_dir):
    """The settings object in `data_dir`, or {} when there is none or it can't be read as one."""
    path = Path(data_dir) / FILE
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > LIMIT:
            return {}
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, RecursionError):
        return {}
    return value if isinstance(value, dict) else {}


def _whole_number_in(value, low, high):
    return isinstance(value, int) and not isinstance(value, bool) and low <= value <= high


def backups_kept(data_dir):
    """How many backups of each kind are kept: the file's whole number from 1 to 365, else the default (14)."""
    value = read(data_dir).get(BACKUPS_KEPT)
    return value if _whole_number_in(value, *BACKUPS_KEPT_RANGE) else BACKUPS_KEPT_DEFAULT


def set_backups_kept(data_dir, number):
    """Save the number kept (a whole number from 1 to 365), leaving every other setting as it is. Raises ValueError in plain
    words for anything else. The file is replaced in one step (platform.write_file)."""
    if not _whole_number_in(number, *BACKUPS_KEPT_RANGE):
        raise ValueError(f"Choose a whole number of backups from {BACKUPS_KEPT_RANGE[0]} to {BACKUPS_KEPT_RANGE[1]}.")
    data_dir = Path(data_dir)
    current = read(data_dir)
    path = data_dir / FILE
    if not current and (path.is_symlink() or path.exists()):
        try:
            readable = (not path.is_symlink() and path.is_file() and path.stat().st_size <= LIMIT
                        and isinstance(json.loads(path.read_text(encoding="utf-8")), dict))
        except (OSError, ValueError, RecursionError):
            readable = False
        if not readable:     # never replace a file that can't be read: it may hold other settings
            raise ValueError("Your settings couldn't be read, so the number wasn't changed. Nothing was lost.")
    current[BACKUPS_KEPT] = number
    platform.write_file(data_dir / FILE, json.dumps(current, indent=2, sort_keys=True) + "\n")
    return number
