"""Windows route (v1.1, #625): folders on the Windows side that the container can reach, and how a path is said back.

Pure: it reads text, never a disk, and never writes. The compose file for Windows shares up to three folders in and names each one's
Windows path in an environment variable; the container sees each at a fixed place under /shares. A person types a Windows path in
Settings; this module says whether it is inside a shared folder, gives the container path it maps to, and writes a container path
back in Windows form. Only to_container is called from a route so far (the pasted client folder in publish_flow.py); see docs/v1.1-container-host-side.md.
Standard library only.
"""
import re
from pathlib import PureWindowsPath

from clark import platform

HOST_SETTING = "CLARK_HOST"
WINDOWS = "windows"

# slot: (the variable that names the shared folder's Windows path, where the container sees it)
SLOTS = {
    "client": ("CLARK_SHARE_CLIENT", "/shares/client"),
    "backup": ("CLARK_SHARE_BACKUP", "/shares/backup"),
    "files": ("CLARK_SHARE_FILES", "/shares/files"),
}

NOT_SHARED = ("Only a folder that was shared when this was started can be used here, and “{folder}” was not. "
              "Nothing was changed.")
NOT_A_PATH = "Type the full path of the folder, starting with the drive, for example C:\\Users\\Name\\Documents. Nothing was changed."
NOT_SHARED_AT_ALL = "No folder has been shared for this yet. Nothing was changed."
SAVED = "Saved as {path}."

_SEP = re.compile(r"[\\/]+")
_BAD = re.compile(r'[<>"|?*\x00-\x1f\x7f]')


def windows_host(environ):
    """True when the compose file says the host is Windows and this really is a container (the setting alone is not enough)."""
    return environ.get(HOST_SETTING) == WINDOWS and platform.container_mode()


def _parse(text):
    """(drive letter in capitals, [parts]) for a full Windows path with a drive letter, else None. A network share, a \\\\?\\ form,
    a character Windows won't take, an empty or dot part all give None, so a typed path can never climb out of a shared folder."""
    if not isinstance(text, str):
        return None
    text = text.strip()
    if len(text) < 3 or text[1] != ":" or not (text[0].isascii() and text[0].isalpha()) or text[2] not in "\\/":
        return None
    if _BAD.search(text) or ":" in text[2:]:
        return None
    parts = [p for p in _SEP.split(text[3:]) if p != ""]
    if any(not p.strip(".") or p[-1] in ". " for p in parts):
        return None
    return text[0].upper(), parts


def is_drive_path(text):
    """True when `text` starts like a Windows drive path (a letter, a colon, a slash), so a caller can send it to to_container."""
    text = text.strip() if isinstance(text, str) else ""
    return len(text) >= 3 and text[0].isascii() and text[0].isalpha() and text[1] == ":" and text[2] in "\\/"


def shares(environ):
    """{slot: (drive, parts)} for the shared folders the compose file named, ignoring one that is missing or not a full path. Empty
    unless the host is Windows."""
    if not windows_host(environ):
        return {}
    found = {}
    for slot, (name, _target) in SLOTS.items():
        parsed = _parse(environ.get(name, ""))
        if parsed:
            found[slot] = parsed
    return found


def _within(root, parsed):
    """The parts of `parsed` below `root` (both from _parse), or None when it is not inside it. Letter case is ignored, as Windows does."""
    if root[0] != parsed[0] or len(parsed[1]) < len(root[1]):
        return None
    if [p.casefold() for p in parsed[1][:len(root[1])]] != [p.casefold() for p in root[1]]:
        return None
    return parsed[1][len(root[1]):]


def to_container(slot, typed, environ):
    """(container path, Windows form) for a typed Windows path inside the shared folder of `slot`. Raises ValueError in plain words,
    ending "Nothing was changed.", for text that is not a full path, for a slot nothing was shared for, and for a path outside the
    shared folder. The Windows form is the path as typed with a capital drive letter and backslashes."""
    parsed = _parse(typed)
    if parsed is None:
        raise ValueError(NOT_A_PATH)
    root = shares(environ).get(slot)
    if root is None:
        raise ValueError(NOT_SHARED_AT_ALL)
    below = _within(root, parsed)
    if below is None:
        raise ValueError(NOT_SHARED.format(folder=platform.host_shown("\\".join([parsed[0] + ":"] + parsed[1]))))
    target = SLOTS[slot][1]
    return "/".join([target] + below), "\\".join([parsed[0] + ":"] + parsed[1])


def windows_form(container_path, environ):
    """A path inside a shared folder in the container (such as /shares/files/a/b.html) as the Windows path it is, or None when it is not
    inside one. The path is cleaned first, so a dot-dot cannot make it land in another folder's name."""
    if not isinstance(container_path, str) or ".." in container_path.split("/"):
        return None
    for slot, root in shares(environ).items():
        target = SLOTS[slot][1]
        if container_path == target or container_path.startswith(target + "/"):
            rest = [p for p in container_path[len(target):].split("/") if p]
            return str(PureWindowsPath(root[0] + ":\\", *root[1], *rest))
    return None


def saved_words(container_path, environ):
    """The sentence that says where a saved file is, in Windows form with the user's name hidden (platform.host_shown), or None when the
    host is not Windows or the file is not in a shared folder (the caller then says what it said before)."""
    path = windows_form(container_path, environ)
    return None if path is None else SAVED.format(path=platform.host_shown(path))
