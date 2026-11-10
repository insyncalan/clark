"""The Source NAME (row 1077, the owner's ruling of 10-11-2026): a work item's or milestone's `source` words as a person may see them,
anywhere the Source line is drawn (the live peek through activity_read, a published file through publish.select).

The stored words are kept as they are in the database. Shown, each comma-separated part that reads as a path (it starts at a root:
/, \\, ~, a drive letter or a scheme; or it has a separator and ends in a file name with an extension) keeps only what follows its last
/ or \\ (the file's name, never the folders above it); a stored YYYY-MM-DD reads DD-MM-YYYY when it is a real day; hidden characters are
dropped and the whole is trimmed. Plain words ("Added by hand in clark", "Duplicated from ABC-A-001", a date written 01/10/2026,
"<b>x</b>" kept as data) are unchanged. Imports nothing from clark, so publish and activity_read can both use it without pulling the other in."""
import re
import unicodedata
from datetime import date

_ISO_DAY = re.compile(r"(?<![\d-])(\d{4})-(\d{2})-(\d{2})(?![\d-])")
_SEP = re.compile(r"[\\/]")
_ROOT = re.compile(r"^\s*(?:[\\/~]|[A-Za-z]:[\\/]|[A-Za-z][A-Za-z0-9+.-]*://)")      # a path from its root, or an address
_FILE = re.compile(r"\.[A-Za-z0-9]{1,8}$")                                             # the last part names a file (an extension)


def _day_as_shown(m):
    try:
        date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return m.group(0)
    return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"


def _plain(text):
    """Hidden characters out (control and format characters, Cc and Cf), the rest as typed."""
    return "".join(ch for ch in text if unicodedata.category(ch) not in ("Cc", "Cf"))


def _last_part(part):
    """A part that reads as a path: what follows its last separator (a trailing separator names what is before it, "folder/" is the
    folder). Any other part, slashes and all, as it is."""
    pieces = [p.strip() for p in _SEP.split(part) if p.strip()]
    if not pieces:
        return ""
    if len(pieces) == 1 and not _ROOT.match(part):
        return part.strip()
    if _ROOT.match(part) or _FILE.search(pieces[-1]):
        return "" if re.fullmatch(r"[A-Za-z]:", pieces[-1]) else pieces[-1]       # a bare drive ("C:\\") names nothing
    return part.strip()


def source_name(words):
    """The words to show for a stored `source`, or "" when there is nothing to show."""
    if not isinstance(words, str):
        return ""
    parts = [_last_part(_plain(p)) for p in words.split(",")]
    kept = [p for p in parts if p]
    if not kept:
        return ""
    return _ISO_DAY.sub(_day_as_shown, ", ".join(kept)).strip()
