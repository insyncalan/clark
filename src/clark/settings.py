"""The smallest reading seam for clark's settings (#111): `<data folder>/settings.json`, read with defaults.

There is no settings store in clark yet (FR-1 is still to come). This file holds only what a built item needs today: the number of
backups kept, and (#180) the person's name and email, so each has one place to read it. A later settings module replaces the reading and writing here and keeps the
names (`backups_kept`, `set_backups_kept`) and the file. Nothing here names a path outside the data folder it is given.

The file is a JSON object. A missing file, a file that isn't a JSON object, a value of the wrong kind or one out of range is not an
error: the default is used, so a bad settings file can never stop a backup or its tidying up. Standard library only, Python 3.9.
"""
import functools
import json
import os
import re
import threading
import unicodedata
from pathlib import Path

from clark import platform

FILE = "settings.json"
LOCK = threading.RLock()                # every setter reads the file and writes it back whole: one at a time, so none is lost
LIMIT = 64 * 1024                       # a settings file larger than this is not read
BACKUPS_KEPT = "backups_kept"
BACKUPS_KEPT_DEFAULT = 14               # = backup.KEEP; a test keeps the two equal
BACKUPS_KEPT_RANGE = (1, 365)

# What Settings › Safety says about the number, in plain words (the page shows these, not the key).
BACKUPS_KEPT_LABEL = "How many backups to keep"
BACKUPS_KEPT_HELP = ("This many backups are kept of each of daily, before an undo and before an import or change (those two share the "
                     "count); before a restore keeps at least 2 and before an update at least 3, whatever the number is; the oldest "
                     "are removed after that. 14 is usual. The newest backup is always kept.")


def _one_at_a_time(setter):
    """Run a setter under LOCK."""
    @functools.wraps(setter)
    def run(*args, **kw):
        with LOCK:
            return setter(*args, **kw)
    return run


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


@_one_at_a_time
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


# ===== Your name and your email (#180, Settings › Profile › About you) =====
# Kept in the same file as the backups number: this person's, on this computer. Both are optional. The name is shown at the top of the
# profile menu and is the name on each change (by_user) instead of the login name; the email is only used to tell which addresses are
# the person's own (the Draft email's own domain). clark never reads either from the computer, the browser or the Claude sign-in, and
# never sends mail. The Alias (item 613) is what colleagues call the person, or their initials: plain text kept beside them, read and
# checked as the name is.
PROFILE_NAME = "profile_name"
PROFILE_EMAIL = "profile_email"
PROFILE_ALIAS = "profile_alias"
NAME_MAX, EMAIL_MAX, ALIAS_MAX = 60, 254, 60
NAME_TOO_LONG = f"Your name is too long. Use {NAME_MAX} characters or fewer. Nothing was saved."
NAME_BAD = "Your name has a character that can't be kept. Remove it and try again. Nothing was saved."
ALIAS_TOO_LONG = f"Your Alias is too long. Use {ALIAS_MAX} characters or fewer. Nothing was saved."
ALIAS_BAD = "Your Alias has a character that can't be kept. Remove it and try again. Nothing was saved."
EMAIL_BAD = "That email address is not complete. Check it, or leave it empty. Nothing was saved."
PROFILE_UNREADABLE = "Your settings couldn't be read, so your name and email were not changed. Nothing was saved."
_UNSEEN = frozenset({"Cc", "Cf", "Cs", "Co", "Cn", "Zl", "Zp"})
_ADDRESS = re.compile(r"[^@\s<>?,;:\"()\[\]\\]+@[^@\s<>?,;:\"()\[\]\\]+\.[^@\s<>?,;:\"()\[\]\\]+")


def _one_line(value):
    """`value` as text on one line (runs of spaces made one, ends trimmed), or None when it holds a control, format, surrogate,
    private-use, unassigned or separator-line character (a bidi override, a zero-width mark, a line break)."""
    text = value if isinstance(value, str) else ""
    if any(unicodedata.category(c) in _UNSEEN or (c.isspace() and c != " ") for c in text):
        return None
    return " ".join(text.split())


def profile(data_dir):
    """{"name", "email", "alias"} as saved ("" for each that is not there, or is not a plain string within its limit): never an error,
    and never anything but what was typed in Settings."""
    got = read(data_dir)
    name, email, alias = _one_line(got.get(PROFILE_NAME)), _one_line(got.get(PROFILE_EMAIL)), _one_line(got.get(PROFILE_ALIAS))
    return {"name": name if name is not None and len(name) <= NAME_MAX else "",
            "email": email if email and len(email) <= EMAIL_MAX and _ADDRESS.fullmatch(email) else "",
            "alias": alias if alias is not None and len(alias) <= ALIAS_MAX else ""}


@_one_at_a_time
def set_profile(data_dir, name, email, alias=None):
    """Save the name, the email and the Alias (each may be empty; an Alias of None keeps the one saved), leaving every other setting as
    it is; returns what was saved. Raises ValueError in plain words, ending "Nothing was saved.", for a name or an Alias over 60
    characters or with an unkeepable character, or an email that is not shaped like an address, and then writes nothing. The file is
    replaced in one step (platform.write_file), and a file that can't be read is never replaced."""
    if name is not None and not isinstance(name, str) or email is not None and not isinstance(email, str):
        raise ValueError(NAME_BAD)
    if alias is not None and not isinstance(alias, str):
        raise ValueError(ALIAS_BAD)
    clean_name, clean_email = _one_line(name or ""), _one_line(email or "")
    if clean_name is None:
        raise ValueError(NAME_BAD)
    if len(clean_name) > NAME_MAX:
        raise ValueError(NAME_TOO_LONG)
    clean_alias = None if alias is None else _one_line(alias)
    if alias is not None and clean_alias is None:
        raise ValueError(ALIAS_BAD)
    if clean_alias is not None and len(clean_alias) > ALIAS_MAX:
        raise ValueError(ALIAS_TOO_LONG)
    if clean_email is None or clean_email and (len(clean_email) > EMAIL_MAX or not _ADDRESS.fullmatch(clean_email)):
        raise ValueError(EMAIL_BAD)
    data_dir = Path(data_dir)
    current = read(data_dir)
    path = data_dir / FILE
    if not current and (path.is_symlink() or path.exists()):
        try:
            readable = (not path.is_symlink() and path.is_file() and path.stat().st_size <= LIMIT
                        and isinstance(json.loads(path.read_text(encoding="utf-8")), dict))
        except (OSError, ValueError, RecursionError):
            readable = False
        if not readable:
            raise ValueError(PROFILE_UNREADABLE)
    if clean_alias is None:                          # no Alias sent: the one saved stays as it is
        clean_alias = profile(data_dir)["alias"]
    else:
        current[PROFILE_ALIAS] = clean_alias
    current[PROFILE_NAME], current[PROFILE_EMAIL] = clean_name, clean_email
    platform.write_file(path, json.dumps(current, indent=2, sort_keys=True) + "\n")
    return {"name": clean_name, "email": clean_email, "alias": clean_alias}


# ===== Copy my backups to (#622, Settings › Backups) =====
# One optional folder, on this computer's settings only (never in the database, so a backup or a restore never carries it). Each finished
# backup is also put there (backup.copy_out). OneDrive is allowed here: a finished single file is safe to sync, which a live database is not.
BACKUP_COPY_FOLDER = "backup_copy_folder"
COPY_PATH_MAX = 1000
COPY_BAD = "Choose a full folder path, such as one in your OneDrive folder. Nothing was changed."
COPY_IN_DATA = ("That folder is clark's own data or backups folder. Choose a different folder for the copies, such as one in "
                "OneDrive. Nothing was changed.")
COPY_NOT_FOLDER = "That is a file, not a folder. Choose a folder. Nothing was changed."
COPY_CANT_MAKE = "That folder isn't there and clark couldn't make it. Check the path, or choose a folder that exists. Nothing was changed."
COPY_NOT_WRITABLE = "This account isn't allowed to save files in that folder. Choose another folder. Nothing was changed."
COPY_UNREADABLE = "Your settings couldn't be read, so the backup copy folder was not changed. Nothing was changed."


def _copy_path(text):
    """`text` as an absolute path (a leading ~ written out), or None when it is not one clark may use."""
    if not isinstance(text, str) or not text.strip() or len(text) > COPY_PATH_MAX:
        return None
    if any(unicodedata.category(c) in _UNSEEN for c in text):
        return None
    path = Path(text.strip()).expanduser()
    return path if path.is_absolute() else None


def backup_copy_problem(data_dir, folder):
    """Why `folder` can't be the copy folder for the data in `data_dir`, in plain words (ending "Nothing was changed."), or None when it can.
    Looks only: it makes nothing. The folder must not be the data folder, the backups folder beside it, or inside either, once links are
    followed (a shortcut can't get round it). Used when the folder is saved and again at every copy."""
    path = _copy_path(str(folder))
    if path is None:
        return COPY_BAD
    live = Path(data_dir).resolve()
    try:
        here = path.resolve()
    except (OSError, RuntimeError):
        return COPY_BAD
    for avoid in (live, live / "backups"):
        if here == avoid or avoid in here.parents:
            return COPY_IN_DATA
    if path.exists() and not path.is_dir():
        return COPY_NOT_FOLDER
    return None


def backup_copy_folder(data_dir):
    """The saved copy folder as a Path, or None when there is none (the default: off) or what is saved is not a usable absolute path."""
    value = read(data_dir).get(BACKUP_COPY_FOLDER)
    return _copy_path(value) if isinstance(value, str) else None


@_one_at_a_time
def set_backup_copy_folder(data_dir, text):
    """Save the copy folder (an existing folder, or one that can be made), or turn it off with an empty text. Every other setting is left
    as it is. Returns the saved Path, or None when turned off. Raises ValueError in plain words, ending "Nothing was changed.", and writes
    nothing, for a path that is not absolute, is clark's own data or backups folder (or inside one), is a file or can't be written to. A
    missing last folder is made; a settings file that can't be read is never replaced."""
    data_dir = Path(data_dir)
    off = text is None or (isinstance(text, str) and not text.strip())
    path = None
    if not off:
        problem = backup_copy_problem(data_dir, text)
        if problem is not None:
            raise ValueError(problem)
        path = _copy_path(text)
        if not path.exists():
            try:
                path.mkdir(parents=True)
            except OSError:
                raise ValueError(COPY_CANT_MAKE) from None
        if not os.access(path, os.W_OK | os.X_OK):
            raise ValueError(COPY_NOT_WRITABLE)
    current = read(data_dir)
    file = data_dir / FILE
    if not current and (file.is_symlink() or file.exists()):
        try:
            readable = (not file.is_symlink() and file.is_file() and file.stat().st_size <= LIMIT
                        and isinstance(json.loads(file.read_text(encoding="utf-8")), dict))
        except (OSError, ValueError, RecursionError):
            readable = False
        if not readable:
            raise ValueError(COPY_UNREADABLE)
    if path is None:
        current.pop(BACKUP_COPY_FOLDER, None)
    else:
        current[BACKUP_COPY_FOLDER] = str(path)
    platform.write_file(file, json.dumps(current, indent=2, sort_keys=True) + "\n")
    return path


# ===== AI (#54, Settings › AI) =====
# Ordinary words only: there is no key or password in clark (the provider is the person's own signed-in command). A value of the wrong
# type reads as not set, so a bad file never turns anything on or chooses anything. ai_connect.py checks the words themselves.
AI_MODEL = "ai_model"
AI_CLAUDE_OFF = "ai_claude_off"
AI_ACCEPTED = "ai_accepted"
AI_CHATGPT_ON = "ai_chatgpt_on"
AI_UNREADABLE = "Your settings couldn't be read, so the AI choice was not changed."


def ai_read(data_dir):
    """{"model": str or "", "claude_off": bool, "chatgpt_on": bool, "accepted": [str]}: the AI choices saved for this data folder."""
    saved = read(data_dir)
    model, off, accepted = saved.get(AI_MODEL), saved.get(AI_CLAUDE_OFF), saved.get(AI_ACCEPTED)
    return {"model": model if isinstance(model, str) else "", "claude_off": off is True, "chatgpt_on": saved.get(AI_CHATGPT_ON) is True,
            "accepted": [m for m in accepted if isinstance(m, str)] if isinstance(accepted, list) else []}


@_one_at_a_time
def ai_write(data_dir, changes):
    """Save any of model, claude_off, chatgpt_on and accepted, leaving every other setting as it is. Raises ValueError, and writes nothing, for a
    settings file that can't be read: it is never replaced."""
    data_dir = Path(data_dir)
    current = read(data_dir)
    file = data_dir / FILE
    if not current and (file.is_symlink() or file.exists()):
        try:
            readable = (not file.is_symlink() and file.is_file() and file.stat().st_size <= LIMIT
                        and isinstance(json.loads(file.read_text(encoding="utf-8")), dict))
        except (OSError, ValueError, RecursionError):
            readable = False
        if not readable:
            raise ValueError(AI_UNREADABLE)
    keys = {"model": AI_MODEL, "claude_off": AI_CLAUDE_OFF, "accepted": AI_ACCEPTED, "chatgpt_on": AI_CHATGPT_ON}
    current.update({keys[k]: v for k, v in changes.items()})
    platform.write_file(file, json.dumps(current, indent=2, sort_keys=True) + "\n")
