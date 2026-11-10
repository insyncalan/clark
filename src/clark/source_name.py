"""The Source NAME (row 1077, the owner's ruling of 10-11-2026): a work item's or milestone's `source` words as a person may see them,
anywhere the Source line is drawn (the live peek through activity_read, a published file through publish.select).

The stored words are kept as they are in the database. Shown: hidden characters are dropped; every kind of slash (/, \\, the fullwidth
and the division slash) is one separator. The path rule runs on the WHOLE string first (commas inside a folder name must not split it):
from a root (/, \\, ~/, a drive letter, a scheme://) to the end, only what follows the LAST separator is kept, and only when it names a
file (it has an extension); a folder, a trailing separator or a bare web host names nothing. A value with a separator and no root is a path
from its first part that has one. A URL loses its ?query and #fragment. A stored YYYY-MM-DD reads DD-MM-YYYY when it is a real day. The
whole is trimmed and cut at 120 characters with an ellipsis. Plain words ("Added by hand in clark", "Duplicated from ABC-A-001", a date
written 01/10/2026, "<b>x</b>" kept as data) are unchanged. Imports nothing from clark.

Known limit: a comma inside a folder name of a ROOTLESS relative path ("Private Clients, Inc/Q3 plan.xlsx") cannot be told from two words.
"""
import re
import unicodedata
from datetime import date

CAP = 120
_ISO_DAY = re.compile(r"(?<![\d-])(\d{4})-(\d{2})-(\d{2})(?![\d-])")
_SLASHES = str.maketrans({"\uff0f": "/", "\uff3c": "\\", "\u2215": "/", "\u29f8": "/", "\u2044": "/"})
_SEP = re.compile(r"[\\/]")
_ROOT = re.compile(r"(?:^|(?<=[,\s]))(?:[A-Za-z][A-Za-z0-9+.-]*://|[A-Za-z]:[\\/]|~[\\/]|[\\/])")      # a root, at the start or after a comma or a space
_FILE = re.compile(r"\.[A-Za-z0-9]{1,8}(?=\s*(?:,|$))")                                                  # a file name: an extension at the end or before a comma
_PATHISH = re.compile(r"(?<!<)[\\/]")                                                                  # a separator that is not the "</" of a tag (markup is data)
_DATE_ONLY = re.compile(r"[\d\s/\\.-]+")                                                                  # 01/10/2026: a date, not a path


def _day_as_shown(m):
    try:
        date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return m.group(0)
    return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"


def _plain(text):
    """Hidden characters out (control and format characters, Cc and Cf), the other slashes made plain ones."""
    return "".join(ch for ch in text if unicodedata.category(ch) not in ("Cc", "Cf")).translate(_SLASHES)


def _name(span):
    """The file name a path span ends in, or "" (a folder, a bare host, nothing after the last separator)."""
    web = re.match(r"[A-Za-z][A-Za-z0-9+.-]*://", span)
    if web:
        span = re.split(r"[?#]", span, 1)[0]
        rest = span[web.end():]
        if not _SEP.search(rest):
            return ""                                   # a bare host
    name = _SEP.split(span)[-1].strip()
    return name if name and _FILE.search(name) else ""


def source_name(words):
    """The words to show for a stored `source`, or "" when there is nothing to show."""
    if not isinstance(words, str):
        return ""
    text = _plain(words).strip()
    root = _ROOT.search(text)
    if root:
        prefix, kept = text[:root.start()], _name(text[root.start():])
    else:
        parts = text.split(",")
        at = next((i for i, p in enumerate(parts) if _PATHISH.search(p) and not _DATE_ONLY.fullmatch(p)), None)
        if at is None:
            prefix, kept = text, ""
        else:
            prefix, kept = ",".join(parts[:at]), _name(",".join(parts[at:]))
    out = ", ".join(x for x in (prefix.strip(" ,"), kept) if x)
    out = _ISO_DAY.sub(_day_as_shown, out).strip()
    return out if len(out) <= CAP else out[:CAP - 1].rstrip() + "\u2026"
