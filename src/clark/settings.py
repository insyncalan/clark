"""The smallest reading seam for clark's settings (#111): `<data folder>/settings.json`, read with defaults.

There is no settings store in clark yet (FR-1 is still to come). This file holds only what a built item needs today: the number of
backups kept, and (#180) the person's name and email, so each has one place to read it. A later settings module replaces the reading and writing here and keeps the
names (`backups_kept`, `set_backups_kept`) and the file. Nothing here names a path outside the data folder it is given.

The file is a JSON object. A missing file, a file that isn't a JSON object, a value of the wrong kind or one out of range is not an
error: the default is used, so a bad settings file can never stop a backup or its tidying up. Standard library only, Python 3.9.
"""
import json
import re
import unicodedata
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


# ===== Your profile (#180, #440: Settings › Profile) =====
# Kept in the same file as the backups number: this person's, on this computer. All five are optional. The name is shown at the top of the
# profile menu and is the name on each change (by_user) instead of the login name; the email is only used to tell which addresses are
# the person's own (the Draft email's own domain). clark never reads either from the computer, the browser or the Claude sign-in, and
# never sends mail. The alias, the phone number and the organisation are only kept and shown back in Settings: nothing else reads them,
# and none of the five is written into a published file, the client report, Word, Excel or an email.
PROFILE_NAME = "profile_name"
PROFILE_EMAIL = "profile_email"
PROFILE_ALIAS = "profile_alias"
PROFILE_PHONE = "profile_phone"
PROFILE_ORG = "profile_org"
NAME_MAX, EMAIL_MAX, ALIAS_MAX, PHONE_MAX, ORG_MAX = 60, 254, 40, 30, 80
NAME_TOO_LONG = f"Your name is too long. Use {NAME_MAX} characters or fewer. Nothing was saved."
NAME_BAD = "Your name has a character that can't be kept. Remove it and try again. Nothing was saved."
EMAIL_BAD = "That email address is not complete. Check it, or leave it empty. Nothing was saved."
ALIAS_TOO_LONG = f"Your alias is too long. Use {ALIAS_MAX} characters or fewer. Nothing was saved."
ALIAS_BAD = "Your alias has a character that can't be kept. Remove it and try again. Nothing was saved."
PHONE_TOO_LONG = f"That phone number is too long. Use {PHONE_MAX} characters or fewer. Nothing was saved."
PHONE_BAD = "A phone number can have digits, spaces and the signs + - ( ) . only. Check it, or leave it empty. Nothing was saved."
ORG_TOO_LONG = f"Your organisation is too long. Use {ORG_MAX} characters or fewer. Nothing was saved."
ORG_BAD = "Your organisation has a character that can't be kept. Remove it and try again. Nothing was saved."
PROFILE_UNREADABLE = "Your settings couldn't be read, so your details were not changed. Nothing was saved."
_UNSEEN = frozenset({"Cc", "Cf", "Cs", "Co", "Cn", "Zl", "Zp"})
_ADDRESS = re.compile(r"[^@\s<>?,;:\"()\[\]\\]+@[^@\s<>?,;:\"()\[\]\\]+\.[^@\s<>?,;:\"()\[\]\\]+")
_PHONE = re.compile(r"[0-9 +\-().]+")
# the details, in the order Settings shows them: (field, settings key, longest allowed, words for too long, words for not kept)
PROFILE_FIELDS = (("name", PROFILE_NAME, NAME_MAX, NAME_TOO_LONG, NAME_BAD), ("alias", PROFILE_ALIAS, ALIAS_MAX, ALIAS_TOO_LONG, ALIAS_BAD),
                  ("email", PROFILE_EMAIL, EMAIL_MAX, EMAIL_BAD, EMAIL_BAD), ("phone", PROFILE_PHONE, PHONE_MAX, PHONE_TOO_LONG, PHONE_BAD),
                  ("org", PROFILE_ORG, ORG_MAX, ORG_TOO_LONG, ORG_BAD))


def _one_line(value):
    """`value` as text on one line (runs of spaces made one, ends trimmed), or None when it holds a control, format, surrogate,
    private-use, unassigned or separator-line character (a bidi override, a zero-width mark, a line break)."""
    text = value if isinstance(value, str) else ""
    if any(unicodedata.category(c) in _UNSEEN or (c.isspace() and c != " ") for c in text):
        return None
    return " ".join(text.split())


def _shaped(field, text):
    """True when `text` (one line) has the right shape for `field`: empty, or an address for the email, digits and the usual signs for
    the phone number, anything at all for the rest."""
    if not text or field not in ("email", "phone"):
        return True
    return bool((_ADDRESS if field == "email" else _PHONE).fullmatch(text))


def profile(data_dir):
    """{"name", "alias", "email", "phone", "org"} as saved ("" for each that is not there, or is not a plain string within its limit and
    shape): never an error, and never anything but what was typed in Settings."""
    got, out = read(data_dir), {}
    for field, key, most, _, _ in PROFILE_FIELDS:
        text = _one_line(got.get(key))
        out[field] = text if text is not None and len(text) <= most and _shaped(field, text) else ""
    return out


def set_profile(data_dir, name, email, alias=None, phone=None, org=None):
    """Save the details (each may be empty), leaving every other setting as it is; returns what was saved. The name and the email are
    always given (None is empty); the alias, the phone number and the organisation stay as they were when None. Raises ValueError in
    plain words, ending "Nothing was saved.", for a detail that is too long or has an unkeepable character, a phone number with
    anything but digits, spaces and + - ( ) ., or an email not shaped like an address, and then writes nothing. The file is replaced in
    one step (platform.write_file), and a file that can't be read is never replaced."""
    given = {"name": name or "", "email": email or "", "alias": alias, "phone": phone, "org": org}
    if any(v is not None and not isinstance(v, str) for v in given.values()):
        raise ValueError(NAME_BAD)
    kept, clean = profile(data_dir), {}
    for field, _, most, too_long, bad in PROFILE_FIELDS:
        if given[field] is None:                          # not given: what is saved stays
            clean[field] = kept[field]
            continue
        text = _one_line(given[field])
        if text is None:
            raise ValueError(bad)
        if len(text) > most:
            raise ValueError(too_long)
        if not _shaped(field, text):
            raise ValueError(bad)
        clean[field] = text
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
    for field, key, _, _, _ in PROFILE_FIELDS:
        current[key] = clean[field]
    platform.write_file(path, json.dumps(current, indent=2, sort_keys=True) + "\n")
    return clean
