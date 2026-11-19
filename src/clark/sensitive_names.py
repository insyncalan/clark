"""Row 1365 S1: names of people or contract material inside a source folder, found from NAMES only.

scan(folder) walks folder and file names with os.scandir. It never opens or reads a file, never calls the network, and
never warns for size or depth (a library root with thousands of files gives nothing unless a name matches).
Matching is whole word, upper or lower case alike, accents folded: "Corporates" does not match "rates", "Résumé" matches "resume".
Links are not followed. It stops after MAX_ENTRIES names or MAX_DEPTH folders deep.
"""
import os
import re
import unicodedata

# WORDING FOR APPROVAL: the one place for the word list (proposed from the ticket; not decided by clark).
WORDS = (
    "candidate", "cv", "resume", "interview", "salary", "payroll", "hr", "performance", "disciplinary",
    "grievance", "contract", "sow", "nda", "agreement", "proposal", "pricing", "rates", "commercial",
    "invoice", "purchase order", "legal",
)

READABLE_TYPES = (".txt", ".md", ".markdown", ".csv", ".tsv", ".rst", ".docx", ".pdf")
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


def _readable(name):
    return os.path.splitext(name)[1].lower() in READABLE_TYPES


class _Budget:
    def __init__(self):
        self.left = MAX_ENTRIES

    def take(self):
        self.left -= 1
        return self.left >= 0


def _count(path, depth, budget):
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
            if e.is_symlink():
                continue
            if e.is_dir(follow_symlinks=False):
                if depth < MAX_DEPTH:
                    n += _count(e.path, depth + 1, budget)
            elif _readable(e.name):
                n += 1
        except OSError:
            continue
    return n


def _walk(root, rel, depth, budget, out):
    try:
        with os.scandir(os.path.join(root, rel) if rel else root) as it:
            entries = sorted(it, key=lambda e: e.name)
    except OSError:
        return
    for e in entries:
        if not budget.take():
            return
        try:
            if e.is_symlink():
                continue
            is_dir = e.is_dir(follow_symlinks=False)
        except OSError:
            continue
        found = words_in(e.name)
        sub = os.path.join(rel, e.name) if rel else e.name
        if is_dir:
            if found:
                out.append({"name": e.name, "path_rel": sub, "words": found,
                            "readable_files": _count(e.path, 1, budget)})
            elif depth < MAX_DEPTH:
                _walk(root, sub, depth + 1, budget, out)
        elif found and not rel:
            out.append({"name": e.name, "path_rel": sub, "words": found,
                        "readable_files": 1 if _readable(e.name) else 0})


def scan(folder):
    """[{name, path_rel, words, readable_files}] for each folder (any depth) and each top-level file named with a listed word."""
    out = []
    _walk(str(folder), "", 0, _Budget(), out)
    return out
