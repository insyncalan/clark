"""ask: a local, rebuildable index of the passages in a project's saved folders (#1366, slice 1). Standard library only (sqlite3 FTS5).

ONE FILE PER PROJECT: `<data folder>/ask-index/<project code>.db`, 0600 in a 0700 folder, never clark.db, never inside a source folder.
It is a copy that can always be rebuilt: delete it and `build` makes the same passages again. A question calls `search` and opens no file.

WHAT GETS IN. Files are listed and opened only through `reach` (`readable_files`, `read_bytes`), the same gates as `ask_passages`.
Text, Markdown, CSV, TSV, RST and Word are read like `ask_passages` reads them. A file whose name or text looks like a password or
a key is screened by `secret_screen` BEFORE any of it is stored: it leaves a row with no text (label and size only). Every
other type (PDF, Excel, PowerPoint, HTML, pictures) is counted as `type` until its own slice. No per-question file, byte or time limit.

FRESH. `refresh` compares each file's size and modified time with the row kept and reads again only what changed; a file that is gone,
or a folder no longer in the project, loses its passages (and the free pages are wiped, so no copy of the text stays in the file).

LABELS. Each passage is labelled "<folder>/<name> (part n), modified YYYY-MM-DD", so an answer can say which of two versions is newer;
equal matches rank the newer file first.

`status` gives counts that add up to the files of the folders: indexed, type, online_only, too_long, safety, not_yet (and `stopped`).
Not in this slice: PDF, Excel, PowerPoint, HTML, OCR, the page budget, online-only reads, lifting `reach`'s 20,000-file listing cap,
running in the background, the Settings text.
"""
import json
import os
import re
import sqlite3
import time
from pathlib import Path

from clark import ask, ask_data, ask_passages, docx_read, reach, secret_screen

MAX_RESULTS = ask.MAX_PASSAGES
MAX_PARTS_PER_FILE = 5000
NAMES = ("indexed", "type", "online_only", "too_long", "safety", "not_yet")
_WORD = re.compile(r"\w+", re.UNICODE)
_CODE = re.compile(r"[^A-Za-z0-9._-]")
MAX_LEFT_OUT_SHOWN = 200
LEFT_OUT_BUTTON = "Show the files left out"
REASON_TYPE = "of a type clark can't read yet"
REASON_SAFETY = "looks like a password or a key"


def path_for(data_dir, code):
    """The index file of one project."""
    safe = _CODE.sub("_", str(code)).lstrip(".") or "project"
    return Path(data_dir) / "ask-index" / f"{safe}.db"


def _open(data_dir, code, create=True):
    p = path_for(data_dir, code)
    if not p.exists() and not create:
        return None
    p.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if not p.exists():
        os.close(os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600))
    os.chmod(p, 0o600)
    db = sqlite3.connect(p)
    db.execute("PRAGMA secure_delete=ON")
    db.executescript(
        "CREATE TABLE IF NOT EXISTS files(label TEXT PRIMARY KEY, size INTEGER, mtime_ns INTEGER, state TEXT);"
        "CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT);"
        "CREATE TABLE IF NOT EXISTS left(label TEXT PRIMARY KEY, reason TEXT);"
        "CREATE VIRTUAL TABLE IF NOT EXISTS p USING fts5(text, file UNINDEXED, part UNINDEXED, mtime UNINDEXED);")
    return db


def _lines(raw, truncated, low, name):
    if low.endswith(ask_passages.WORD_TYPES):
        if truncated:
            raise docx_read.WordRefused("too big")
        return ask_passages._lines_of_word(raw, name)
    return ask_passages._lines_of_text(raw, truncated)


def _drop(db, label):
    db.execute("DELETE FROM p WHERE file=?", (label,))
    db.execute("DELETE FROM files WHERE label=?", (label,))


def refresh(data_dir, code, folders, home=None):
    """Bring the index up to date with `folders`; reads again only the files whose size or modified time changed."""
    usable, unusable = [], 0
    for f in folders or ():
        try:
            why = reach.never_inside(f, data_dir, home)
        except (OSError, ValueError, RuntimeError):
            why = "unusable"
        if why:
            unusable += 1
        else:
            usable.append(f)
    if not usable:
        p = path_for(data_dir, code)
        if p.exists():
            p.unlink()                       # no folder left: no copy of its text stays
        if unusable:
            db = _open(data_dir, code)
            db.execute("INSERT OR REPLACE INTO meta VALUES('counts', ?)", (json.dumps({**dict.fromkeys(NAMES, 0), "safety": unusable}),))
            db.commit()
            db.close()
        return
    reasons = {}
    listing = reach.readable_files(usable, data_dir, reasons, home)
    roots = reach.roots(usable, home)
    db = _open(data_dir, code)
    kept = {r[0]: (r[1], r[2], r[3]) for r in db.execute("SELECT label, size, mtime_ns, state FROM files")}
    left = {}
    seen, type_n, safety = set(), 0, unusable + listing.skipped - reasons.get(reach.ONLINE, 0)
    for path in listing.files:
        low = str(path).lower()
        if not low.endswith(ask_passages.TEXT_TYPES + ask_passages.WORD_TYPES):
            type_n += 1
            root = next((r for r in roots if reach.inside(path, r)), None)
            name = ask_passages._label(root, path) if root is not None else None
            if name is not None:
                left[name] = REASON_TYPE
            continue
        root = next((r for r in roots if reach.inside(path, r)), None)
        label = ask_passages._label(root, path) if root is not None else None
        if label is None:
            safety += 1
            continue
        try:
            st = os.stat(path)
        except OSError:
            safety += 1
            continue
        seen.add(label)
        if kept.get(label, (None,))[:2] == (st.st_size, st.st_mtime_ns):
            continue
        _drop(db, label)
        state = "indexed"
        try:
            raw, truncated = reach.read_bytes(path, usable, data_dir, docx_read.MAX_FILE_BYTES if low.endswith(ask_passages.WORD_TYPES) else ask_passages.MAX_TEXT_BYTES, home)
            lines = _lines(raw, truncated, low, os.path.basename(str(path)))
        except (reach.Never, docx_read.WordRefused, ValueError, UnicodeError):
            state = "safety"
            lines = ()
        if state == "indexed" and (secret_screen.name_looks_like_secret(label) or secret_screen.looks_like_secret("\n".join(lines))):
            state = "safety"
        if state == "indexed":
            parts = ask_data._cut(label, list(ask_passages._chunks(lines)))[:MAX_PARTS_PER_FILE]
            for i, part in enumerate(parts, 1):
                db.execute("INSERT INTO p(text, file, part, mtime) VALUES(?,?,?,?)", (part.text, label, i if len(parts) > 1 else 0, int(st.st_mtime)))
        db.execute("INSERT INTO files VALUES(?,?,?,?)", (label, st.st_size, st.st_mtime_ns, state))
    for gone in set(kept) - seen:
        _drop(db, gone)
    states = [r[0] for r in db.execute("SELECT state FROM files")]
    for (name,) in db.execute("SELECT label FROM files WHERE state='safety'"):
        left[name] = REASON_SAFETY
    db.execute("DELETE FROM left")
    db.executemany("INSERT INTO left VALUES(?,?)", sorted(left.items()))
    counts = dict.fromkeys(NAMES, 0)
    counts.update(indexed=states.count("indexed"), type=type_n, online_only=reasons.get(reach.ONLINE, 0),
                  safety=safety + states.count("safety"))
    counts["stopped"] = bool(listing.stopped)
    db.execute("INSERT OR REPLACE INTO meta VALUES('counts', ?)", (json.dumps(counts),))
    db.commit()
    db.execute("INSERT INTO p(p) VALUES('optimize')")     # merges the segments so deleted rows are really gone
    db.commit()
    db.execute("VACUUM")                         # wipes freed pages: text of a removed file is not left behind
    db.close()


def build(data_dir, code, folders, home=None):
    """Make the index again from nothing."""
    p = path_for(data_dir, code)
    if p.exists():
        p.unlink()
    refresh(data_dir, code, folders, home)


def search(data_dir, code, question, limit=MAX_RESULTS):
    """Passages for `question`, best first (newer file first when equal). Opens no source file."""
    words = _WORD.findall(question or "")
    if not words:
        return []
    db = _open(data_dir, code, create=False)
    if db is None:
        return []
    try:
        match = " OR ".join('"' + w.replace('"', "") + '"' for w in words[:40])
        rows = db.execute("SELECT text, file, part, mtime FROM p WHERE p MATCH ? ORDER BY round(rank, 6), mtime DESC LIMIT ?", (match, limit)).fetchall()
    except sqlite3.Error:
        return []
    finally:
        db.close()
    out = []
    for text, file, part, mtime in rows:
        label = f"{file} (part {part})" if part else file
        out.append(ask.Passage(f"{label}, modified {time.strftime('%Y-%m-%d', time.gmtime(mtime))}", text, file=file))
    return out


def status(data_dir, code, folders=None):
    """The counts kept by the last refresh (all 0 when there is no index yet)."""
    counts = dict.fromkeys(NAMES, 0)
    db = _open(data_dir, code, create=False)
    if db is not None:
        try:
            row = db.execute("SELECT v FROM meta WHERE k='counts'").fetchone()
            if row:
                counts.update(json.loads(row[0]))
        except sqlite3.Error:
            pass
        finally:
            db.close()
    return counts


def files_left_out(data_dir, code, limit=MAX_LEFT_OUT_SHOWN):
    """{"files": [(name, plain reason)] (at most `limit`, by name), "more": how many are not in that list}. Names only, never any text."""
    db = _open(data_dir, code, create=False)
    if db is None:
        return {"files": [], "more": 0}
    try:
        total = db.execute("SELECT count(*) FROM left").fetchone()[0]
        rows = db.execute("SELECT label, reason FROM left ORDER BY label LIMIT ?", (max(int(limit), 0),)).fetchall()
    except sqlite3.Error:
        return {"files": [], "more": 0}
    finally:
        db.close()
    return {"files": [tuple(r) for r in rows], "more": total - len(rows)}


def more_line(n):
    return f"and {n} more"


def left_out_line(reason, n):
    """The approved sentence for `n` files left out for one reason (only "safety" so far)."""
    if reason == "safety":
        return f"{n} look like a password or a key and were left out." if n != 1 else "1 looks like a password or a key and was left out."
    raise ValueError(reason)


def answer_note(counts):
    """The note under an answer while files are still being read; "" once the index is complete."""
    n = int((counts or {}).get("not_yet") or 0)
    if n <= 0:
        return ""
    return f"Still reading {n} file{'' if n == 1 else 's'}, so this answer may miss some."
