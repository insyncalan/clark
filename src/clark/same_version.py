"""Refuse to start from a folder whose files are not all from one version (row 760).

Unzipping a newer download over an older clark folder (unzip -o, ditto) can leave some files old and some new. A download
carries clark-release.json, the size and SHA-256 of each file it holds. On start, each program file it lists (everything in
the hidden .app folder, and clark.command) must be on disk with that size and hash. A listed file that is missing or
different means the folder is mixed, and clark does not start. A file on disk that the list does not mention is ignored.

Only a download is checked. A source checkout has no .app folder, and a download folder with no clark-release.json is not
checked either (nothing to compare with). A clark-release.json that cannot be read, or that does not hold the expected list, is
refused with the same message: a download always carries a good one, so a broken one means the folder is damaged, and the
way out (unzip the download again) is the same. Standard library only, Python 3.9.
"""
import hashlib
import json
import sys
from pathlib import Path, PurePosixPath

MESSAGE = ("These clark files are not all from the same version, so clark will not start. "
           "Delete the clark folder and unzip the download again.")
MANIFEST = "clark-release.json"
HIDDEN = ".app"
CHECKED = ("clark.command",)            # the one program file that sits outside .app
MAX_MANIFEST = 4 * 1024 * 1024


def _code_root():
    """The folder that holds src/ and vendor/: .app in a download, the checkout's top folder otherwise."""
    return Path(__file__).resolve().parents[2]


def _wanted(name):
    return name in CHECKED or name.startswith(HIDDEN + "/")


def _safe(name):
    parts = PurePosixPath(name).parts
    return bool(parts) and not PurePosixPath(name).is_absolute() and ".." not in parts and "\\" not in name


def _same(path, entry):
    """Whether the file at `path` has the size and SHA-256 `entry` records."""
    size, digest = entry.get("size"), entry.get("sha256")
    if not (isinstance(size, int) and not isinstance(size, bool) and isinstance(digest, str)):
        raise ValueError("entry")
    if not path.is_file() or path.stat().st_size != size:         # the size first: most changes stop here without reading
        return False
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest() == digest


_ANSWERS = {}


def mixed(code_root=None):
    """Whether the folder is mixed (see _mixed); asked once per folder in a run, so the stand-in and the launcher share one check."""
    key = str(code_root)
    if key not in _ANSWERS:
        _ANSWERS[key] = _mixed(code_root)
    return _ANSWERS[key]


def _mixed(code_root=None):
    """True when the folder is a download whose files do not all match its clark-release.json; False when it matches or
    is not a download or has no record."""
    root = Path(code_root) if code_root is not None else _code_root()
    if root.name != HIDDEN:
        return False                                              # a source checkout
    top = root.parent
    record = top / MANIFEST
    if not record.exists():
        return False
    try:
        if record.stat().st_size > MAX_MANIFEST:
            return True
        files = json.loads(record.read_text(encoding="utf-8"))["files"]
        if not isinstance(files, dict):
            return True
        for name, entry in files.items():
            if not isinstance(name, str) or not _safe(name) or not isinstance(entry, dict):
                return True
            if _wanted(name) and not _same(top / name, entry):
                return True
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return True
    return False


def refuse(err=None, code_root=None):
    """Print the message to the terminal and return True when the folder is mixed; False otherwise."""
    if not mixed(code_root):
        return False
    print(MESSAGE, file=err or sys.stderr, flush=True)
    return True
