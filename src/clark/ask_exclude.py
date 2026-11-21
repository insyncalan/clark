"""Row 1365: the subfolders a person leaves out of a saved source folder. One place for the rules, used by the store (what may be saved),
the folder walk in reach.py (what is never looked at) and the name scan (what is no longer warned about). Standard library only; nothing
here opens a file or the database.

A left-out subfolder is a path RELATIVE to its saved folder: plain names joined by "/", no leading or trailing slash, no "." or "..", no
control character, no "|" or "\\". It is stored as a JSON list of such paths in source_folders.excluded ('[]' = nothing left out).
It leaves out that folder and everything under it. Matching is by name, per level, ignoring case and Unicode spelling (NFC, casefold), so a
volume that ignores case cannot read what the list names: when in doubt more is left out, never less. A folder added later under the same
name is left out too; one with another name is not. A list that cannot be read is never taken as "nothing": see `parse`.
"""
import json
import unicodedata

MAX_LEFT_OUT = 50           # subfolders left out of one saved folder
MAX_REL = 500               # characters in one relative path
MAX_RAW = 20000             # characters in the stored list


def clean(rel):
    """The relative path as it is kept (NFC, one trailing slash allowed and dropped), or None when it is not a plain relative path."""
    if not isinstance(rel, str):
        return None
    rel = unicodedata.normalize("NFC", rel)
    if rel.endswith("/"):
        rel = rel[:-1]
    if len(rel) > MAX_REL:
        return None
    for part in rel.split("/"):
        if part in ("", ".", "..") or part != part.strip():
            return None
        if any(c in "|\\" or unicodedata.category(c).startswith("C") or unicodedata.category(c) in ("Zl", "Zp") for c in part):
            return None
    return rel


def parts_key(rel):
    """The comparison form of a relative path: a tuple of folded names."""
    return tuple(unicodedata.normalize("NFC", p).casefold() for p in rel.split("/"))


def parse(raw):
    """The list kept in the column, as a list of clean paths. None is a row read before the column was there: nothing left out. Anything else that is not a JSON list of at most MAX_LEFT_OUT clean paths raises ValueError (callers refuse to read the folder, never
    read it whole)."""
    if raw is None:
        return []
    if isinstance(raw, list):
        got = raw
    else:
        if not isinstance(raw, str) or len(raw) > MAX_RAW:
            raise ValueError("left-out list is not text of a usable size")
        got = json.loads(raw)
    if not isinstance(got, list) or len(got) > MAX_LEFT_OUT:
        raise ValueError("left-out list is not a short list")
    out = []
    for item in got:
        rel = clean(item)
        if rel != item:
            raise ValueError("left-out list holds a path that is not plain")
        if rel not in out:
            out.append(rel)
    return out


def dump(rels):
    """The text stored for a list of clean paths (sorted, each once)."""
    return json.dumps(sorted(set(rels)), ensure_ascii=False)


def left_out(rel, rels):
    """Whether the path `rel` (relative, "/"-joined or a tuple of names) is one of the left-out folders or below one."""
    names = parts_key("/".join(rel)) if isinstance(rel, (tuple, list)) else parts_key(rel)
    for r in rels:
        k = parts_key(r)
        if names[:len(k)] == k:
            return True
    return False
