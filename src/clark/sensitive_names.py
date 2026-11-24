"""Row 1365 S1: names of people or contract material inside a source folder, found from NAMES only.

scan(folder) walks folder and file names with os.scandir. It never opens or reads a file, never calls the network, and
never warns for size or depth (a library root with thousands of files gives nothing unless a name matches).
Matching is whole word, upper or lower case alike, accents folded: "Corporates" does not match "rates", "Résumé" matches "resume".
Links (symlinks, Windows junctions and other reparse points) are not followed, so the walk stays inside the folder. It stops after MAX_ENTRIES names or MAX_DEPTH folders deep; when the names run out the result has truncated=True.
Only top-level files are listed by name (decision); files inside folders are counted under the folder.
"""
import os
import re
import sys
import unicodedata

from clark import ask_exclude, ask_passages

# The one place for the word list: strong words only (a false-alarm check on real folder names: weak words such as rates, proposal, legal, performance, commercial, agreement, pricing, hr, candidate, interview are left out).
WORDS = (
    "cv", "cvs", "resume", "resumes", "salary", "payroll", "passport", "passports", "ssn", "disciplinary", "grievance",
    "redundancy", "contract", "contracts", "sow", "sows", "nda", "ndas", "purchase order", "purchase orders",
)

# One source: the types ask clark reads (ask_passages), so the two lists cannot drift.
READABLE_TYPES = ask_passages.TEXT_TYPES + ask_passages.WORD_TYPES + ask_passages.PDF_TYPES
MAX_ENTRIES = 100000
MAX_DEPTH = 64


def _tokens(name):
    """The lower-case, accent-free words of a name, without a file ending's dot."""
    folded = unicodedata.normalize("NFKD", name)
    folded = "".join(c for c in folded if not unicodedata.combining(c)).lower()
    return re.findall(r"[^\W_]+", folded)


def words_in(name, words=WORDS):
    """The listed words (and two-word phrases) that appear in name as whole words, in list order."""
    toks = _tokens(name)
    joined = " " + " ".join(toks) + " "
    return [w for w in words if f" {w} " in joined]


_REPARSE_POINT = 0x400


def _is_link(entry):
    """True for a symlink or a Windows junction / reparse point: never followed, never counted, never listed."""
    if entry.is_symlink():
        return True
    is_junction = getattr(entry, "is_junction", None)
    if is_junction is not None and is_junction():
        return True
    if sys.platform == "win32":
        attrs = getattr(entry.stat(follow_symlinks=False), "st_file_attributes", 0)
        return bool(attrs & _REPARSE_POINT)
    return False


def _readable(name):
    return os.path.splitext(name)[1].lower() in READABLE_TYPES


class _Budget:
    def __init__(self):
        self.left = MAX_ENTRIES
        self.truncated = False

    def take(self):
        self.left -= 1
        if self.left < 0:
            self.truncated = True
        return self.left >= 0


def _count(path, depth, budget, rel="", left=()):
    """Readable files under path, by name."""
    n = 0
    try:
        with os.scandir(path) as it:
            entries = list(it)
    except OSError:
        return 0
    for e in entries:
        if not budget.take():
            break
        try:
            if _is_link(e):
                continue
            if e.is_dir(follow_symlinks=False):
                if depth < MAX_DEPTH:
                    if not (left and ask_exclude.left_out((rel + "/" + e.name).split("/"), left)):
                        n += _count(e.path, depth + 1, budget, rel + "/" + e.name, left)
            elif _readable(e.name) and not (left and ask_exclude.left_out((rel + "/" + e.name).split("/"), left)):
                n += 1
        except OSError:
            continue
    return n


def _walk(root, rel, depth, budget, out, left=()):
    try:
        with os.scandir(os.path.join(root, rel) if rel else root) as it:
            entries = sorted(it, key=lambda e: e.name)
    except OSError:
        return
    for e in entries:
        if not budget.take():
            return
        try:
            if _is_link(e):
                continue
            is_dir = e.is_dir(follow_symlinks=False)
        except OSError:
            continue
        sub = os.path.join(rel, e.name) if rel else e.name
        if left and ask_exclude.left_out(sub.split(os.sep), left):      # row 1365: left out by the person, no longer named
            continue
        found = words_in(e.name)
        if is_dir:
            if found:
                out.append({"name": e.name, "path_rel": sub, "words": found, "dir": True,
                            "readable_files": _count(e.path, 1, budget, sub.replace(os.sep, "/"), left)})
            elif depth < MAX_DEPTH:
                _walk(root, sub, depth + 1, budget, out, left)
        elif found and not rel:
            out.append({"name": e.name, "path_rel": sub, "words": found, "dir": False,
                        "readable_files": 1 if _readable(e.name) else 0})


class ScanResult(list):
    """The found rows, with .truncated True when MAX_ENTRIES stopped the scan early."""
    truncated = False


def scan(folder, left_out=()):
    """[{name, path_rel, words, readable_files}] for each folder (any depth) and each top-level file named with a listed word.

    A saved folder whose own name holds a listed word comes first in the list (own=True, path_rel "", dir False).
    `left_out` (row 1365) is the folder's list of left-out subfolders (relative paths): they and what is below are not looked at or named.
    The list has a truncated attribute: True when the scan stopped at MAX_ENTRIES names."""
    out = ScanResult()
    budget = _Budget()
    own = os.path.basename(os.path.normpath(str(folder)))      # row 1365: the saved folder's own name counts too, and is named in the warning
    found = words_in(own)
    if found:
        out.append({"name": own, "path_rel": "", "words": found, "dir": False, "own": True,
                    "readable_files": _count(str(folder), 1, budget, "", tuple(left_out))})
    _walk(str(folder), "", 0, budget, out, tuple(left_out))
    out.truncated = budget.truncated
    return out
