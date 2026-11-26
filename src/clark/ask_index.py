"""ask: a local, rebuildable index of the passages in a project's saved folders (Row 1366, slice 1). Standard library only (sqlite3 FTS5).

ONE FILE PER PROJECT: `<data folder>/ask-index/<project code>.db`, 0600 in a 0700 folder, never clark.db, never inside a source folder.
It is a copy that can always be rebuilt: delete it and `build` makes the same passages again. A question calls `search` and opens no file.

WHAT GETS IN. Files are listed and opened only through `reach` (`readable_files`, `read_bytes`), the same gates as `ask_passages`.
Text, Markdown, CSV, TSV, RST and Word are read like `ask_passages` reads them. PDF goes through `pdf_reader` (its own process, a passage per
page: "<file>, page n"); Excel (.xlsx, .xlsm) through vendored openpyxl, read-only, stored values, a passage run per sheet ("<file>, sheet S"); a PDF with no
readable text (scanned, encrypted, damaged) counts as `type` and is listed as left out, a damaged workbook as `type`, a PDF over INDEX_PDF_PAGES / INDEX_PDF_BYTES / INDEX_PDF_SECONDS (or a workbook over its limits) as `too_long`, listed "too long to read" (never as a password).
PowerPoint (.pptx: slide text and notes, a passage run per slide, "<file>, slide n") and web pages (.html, .htm: the visible text) are read by `ask_extract`;
a file with no text, and a hostile or damaged one (zip bomb, too many parts, an entity declaration, broken XML, too big), count as `type`, never as a password. A file whose name or text looks like a password or
a key is screened by `secret_screen` BEFORE any of it is stored: it leaves a row with no text (label and size only). A picture
(.png, .jpg, .jpeg) goes through `ask_picture` (this Mac's own text recognition, nothing sent out): read it is `indexed` and counted in
`pictures_read`; where no reader is available (not a Mac, or none built) it is counted `picture` and listed as left out. Every
other type is counted as `type`. No per-question file, byte or time limit.

FRESH. `refresh` compares each file's size and modified time with the row kept and reads again only what changed; a file that is gone,
or a folder no longer in the project, loses its passages (and the free pages are wiped, so no copy of the text stays in the file).

LABELS. Each passage is labelled "<folder>/<name> (part n), modified YYYY-MM-DD", so an answer can say which of two versions is newer;
equal matches rank the newer file first.

`status` gives counts that add up to the files of the folders: indexed, type, online_only, too_long, safety, not_yet (and `stopped`).
Not in this slice: OCR, the page budget, online-only reads, lifting `reach`'s 20,000-file listing cap,
running in the background, the Settings text.
"""
import json
import os
import re
import sqlite3
import threading
import time
from pathlib import Path

from clark import ask, ask_data, ask_exclude, ask_extract, ask_passages, ask_picture, ask_vision_mac, docx_read, pdf_reader, platform, reach, secret_screen

MAX_RESULTS = ask.MAX_PASSAGES
MAX_PARTS_PER_FILE = 5000
INDEX_PDF_PAGES = 2000                   # background index runs: a PDF over any of these three is skipped and listed (the question path keeps pdf_reader's own, smaller limits)
INDEX_PDF_BYTES = 100 * 1024 * 1024
INDEX_PDF_SECONDS = 120
EXCEL_TYPES = (".xlsx", ".xlsm")
PPTX_TYPES = (".pptx",)
HTML_TYPES = (".html", ".htm")
PICTURE_TYPES = ask_picture.PICTURE_TYPES
ask_vision_mac.register()          # the Mac's own text recognition for pictures; nothing is registered on another system
INDEXED_TYPES = ask_passages.TEXT_TYPES + ask_passages.WORD_TYPES + ask_passages.PDF_TYPES + EXCEL_TYPES + PPTX_TYPES + HTML_TYPES
TRACKED_TYPES = INDEXED_TYPES + PICTURE_TYPES          # the files that have a row in the index (a picture too, read or left out)
MAX_PPTX_BYTES = 50 * 1024 * 1024
MAX_EXCEL_BYTES = 25 * 1024 * 1024
STALE_POLL_SECONDS = 5
SCREEN_VERSION = 2                       # the version of the secret screen the text was checked with; raise it whenever secret_screen gets tighter, and every index made under an older one is read again (and refused until it is)
MAX_EXCEL_ROWS = 50000                   # per sheet
MAX_EXCEL_CELLS = 1000000                # per file
MAX_EXCEL_MEMBERS = 2000                 # parts in the zip
MAX_EXCEL_TOTAL = 50 * 1024 * 1024       # all parts together, unpacked
MAX_EXCEL_SHARED = 8 * 1024 * 1024       # the shared strings part, unpacked: openpyxl parses it whole before the first row, about 0.65 s per MB
MAX_EXCEL_PART = 30 * 1024 * 1024        # any other part, unpacked
MAX_EXCEL_SECONDS = 20                   # wall clock for one workbook
CLOCK = time.monotonic
NAMES = ("indexed", "type", "online_only", "too_long", "safety", "picture", "not_yet")
_WORD = re.compile(r"\w+", re.UNICODE)
# Row 1624: the common words of a question are not searched for. A passage that shares only "the" or "is" with the question is not about it, so it is not sent.
STOP_WORDS = frozenset("a an and are as at be been but by can could did do does for from had has have how i if in into is it its me my of on or our so than that the their them then "
                       "there these they this to us was we were what when where which who whom why will with would you your".split())
_CODE = re.compile(r"[^A-Za-z0-9._-]")
MAX_LEFT_OUT_SHOWN = 200
LEFT_OUT_BUTTON = "Show the files left out"
ONLINE_LINE = "Online-only files not searched"           # row 1537 AP4: the owner's words of 19-11, NEW-WORDS.md:2225-2226; no count in front
REASON_TYPE = "of a type clark can't read yet"
REASON_SAFETY = "looks like a password or a key"
REASON_TOO_LONG_PDF = "is a PDF that is too long"          # a PDF over its page, size or time limit (the words main already had)
REASON_TOO_LONG = "is too long"                           # any other file over its limits (approved words, 22-11)
REASON_PICTURE = "is a picture and this computer cannot read pictures"
COUNTED = ("indexed", "type", "too_long", "picture")          # the states that have their own count; any other state is a safety one


def path_for(data_dir, code):
    """The index file of one project."""
    safe = _CODE.sub("_", str(code)).lstrip(".") or "project"
    return Path(data_dir) / "ask-index" / f"{safe}.db"


def remove_all(data_dir):
    """Delete every project's index (asking turned Off: no copy of the folders' text is kept while nothing may be asked)."""
    folder = Path(data_dir) / "ask-index"
    try:
        names = [p.name for p in folder.iterdir()]
    except OSError:
        return
    for name in names:
        if name.endswith((".db", ".db-wal", ".db-shm", ".db-journal")):
            (folder / name).unlink(missing_ok=True)


def remove(data_dir, code):
    """Delete the index of one project, with any -wal, -shm or -journal beside it (used when the project goes, or has no folder left)."""
    base = path_for(data_dir, code)
    for suffix in ("", "-wal", "-shm", "-journal"):
        Path(str(base) + suffix).unlink(missing_ok=True)


def _open(data_dir, code, create=True):
    p = path_for(data_dir, code)
    if not p.exists() and not create:
        return None
    made = not p.parent.exists()
    p.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(p.parent, 0o700)                # a folder made earlier (or by another tool) is put right too
    if made:
        platform.exclude_from_backup(p.parent)   # Row 1568 AP1: Time Machine skips the folder, again each time it is made new
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


class TooLong(ValueError):
    """A file over a size, part or time limit: counted `too_long`, the same word as a PDF with too many pages."""


def _check_excel_zip(raw):
    """Refuse a workbook that would unpack to too much BEFORE openpyxl parses anything: the parts declared in the zip, and the bytes
    really unpacked (a forged header says less than the data holds). Raises TooLong, or ValueError("excel") for a damaged zip."""
    import io
    import zipfile
    try:
        zf = zipfile.ZipFile(io.BytesIO(raw))
        infos = zf.infolist()
    except (zipfile.BadZipFile, OSError, EOFError, NotImplementedError) as e:
        raise ValueError("excel") from e
    if len(infos) > MAX_EXCEL_MEMBERS:
        raise TooLong("too many parts")

    def cap(info):
        return MAX_EXCEL_SHARED if "sharedstrings" in info.filename.lower() else MAX_EXCEL_PART
    if sum(i.file_size for i in infos) > MAX_EXCEL_TOTAL or any(i.file_size > cap(i) for i in infos):
        raise TooLong("too big once unpacked")
    total = 0
    try:
        for info in infos:
            got = 0
            with zf.open(info) as f:
                while True:
                    chunk = f.read(1 << 20)
                    if not chunk:
                        break
                    got += len(chunk)
                    total += len(chunk)
                    if got > cap(info) or total > MAX_EXCEL_TOTAL:
                        raise TooLong("too big once unpacked")
    except (zipfile.BadZipFile, OSError, EOFError, NotImplementedError, RuntimeError) as e:
        raise ValueError("excel") from e


def _excel_groups(raw, truncated):
    """[(part name, lines)] one group per sheet: stored values (not formulas), cells joined with ' | '.
    Limits are checked before and while reading: file bytes, parts and unpacked sizes (`_check_excel_zip`), rows, cells and MAX_EXCEL_SECONDS."""
    if truncated or len(raw) > MAX_EXCEL_BYTES:
        raise TooLong("too big")
    _check_excel_zip(raw)
    import io
    import openpyxl
    began = CLOCK()
    try:
        wb = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
    except Exception as e:                     # a damaged or unsafe workbook is left out, never an error
        raise ValueError("excel") from e
    out, cells = [], 0
    try:
        for ws in wb.worksheets:
            if getattr(ws, "sheet_state", "visible") != "visible":
                continue                       # a hidden or very hidden sheet is not read (the ticket: only if the person says so)
            lines, header = [], None
            for n, row in enumerate(ws.iter_rows(values_only=True)):
                if n >= MAX_EXCEL_ROWS or cells >= MAX_EXCEL_CELLS:
                    raise TooLong("too many rows or cells")      # never cut silently: the file is listed "too long to read" and none of it is indexed
                if CLOCK() - began > MAX_EXCEL_SECONDS:
                    raise TooLong("too slow")
                cells += len(row)
                cols = [str(v).replace("\n", " ").strip() if v is not None else "" for v in row]
                if not any(cols):
                    continue
                if header is None:
                    header = cols if all(isinstance(v, str) for v in row if v is not None) else []
                    lines.append(" | ".join(c for c in cols if c))
                    continue
                # every row carries its column headers, so a passage cut from the middle of a sheet still says what each cell is
                lines.append(" | ".join(f"{header[i]}: {c}" if i < len(header) and header[i] else c for i, c in enumerate(cols) if c))
            if lines:
                out.append((f"sheet {ws.title}", lines))
    except TooLong:
        raise
    except Exception as e:
        raise ValueError("excel") from e
    finally:
        wb.close()
    return out


def _drop(db, label):
    db.execute("DELETE FROM p WHERE file=?", (label,))
    db.execute("DELETE FROM files WHERE label=?", (label,))


def _prefixes(roots):
    """{root: the name its files carry in a label}. The folder's own name, unless another saved folder has the same name (a/docs, b/docs):
    then the fewest trailing parts of the path that tell them apart (a/docs, b/docs), so two files of the same name never share a label."""
    roots = list(dict.fromkeys(roots))
    by_name = {}
    for r in roots:
        by_name.setdefault(os.path.basename(str(r)), []).append(r)
    out = {}
    for name, group in by_name.items():
        if len(group) == 1:
            out[group[0]] = name
            continue
        parts = {r: [x for x in Path(r).parts if x not in ("/", "\\")] for r in group}
        depth = 2
        while depth < max(len(v) for v in parts.values()) and len({tuple(v[-depth:]) for v in parts.values()}) < len(group):
            depth += 1
        for r in group:
            out[r] = "/".join(parts[r][-depth:])
    return out


def _all_roots(usable, home):
    return [r for f in usable for r in reach.roots([f], home)]


def _unusable(folders, data_dir, home):
    usable, bad = [], []
    for f in folders or ():
        try:
            why = reach.never_inside(f, data_dir, home)
        except (OSError, ValueError, RuntimeError):
            why = "unusable"
        (bad if why else usable).append(f)
    return usable, bad


def _cuts(folders, leave_out):
    """Row 1542: (usable folders, the folders whose left-out list cannot be read, {folder: the test the walk is given}). A folder whose list cannot be read is not indexed at all
    (the same fail-closed rule as the question's reader): a broken list never means "index everything"."""
    use, broken, cuts = [], [], {}
    for f in folders:
        try:
            rels = ask_exclude.parse((leave_out or {}).get(f))
        except ValueError:
            broken.append(f)
            continue
        use.append(f)
        if rels:
            cuts[f] = ask_passages._gone(rels)
    return use, broken, cuts


def _open_read(data_dir, code):
    """The index for a reader (a question, the Settings poll): None when there is none or it cannot be opened now (a refresh holds it locked)."""
    try:
        return _open(data_dir, code, create=False)
    except (sqlite3.Error, OSError):
        return None


def _screen_ok(db):
    """True when the text in this index was screened by the current version of the secret screen (an index made before the version was kept has none: not ok)."""
    try:
        row = db.execute("SELECT v FROM meta WHERE k='screen'").fetchone()
    except sqlite3.Error:
        return False
    return row is not None and row[0] == str(SCREEN_VERSION)


def _set(db, k, v):
    db.execute("INSERT OR REPLACE INTO meta VALUES(?, ?)", (k, v if isinstance(v, str) else json.dumps(v)))


def refresh(data_dir, code, folders, home=None, stop=None, progress=None, leave_out=None):
    """Bring the index up to date with `folders`; reads again only the files whose size or modified time changed.
    `stop` (a threading.Event) ends it early (False is returned, the index is not marked complete); `progress(folder, done, total)` is
    called after each file. Returns True when it ran to the end.
    `leave_out` (row 1542) is {saved folder: the stored list of subfolders the person left out}: nothing under them is read, and what an earlier run kept from them is dropped."""
    listed = sorted(str(f) for f in folders or ())
    usable, bad = _unusable(folders, data_dir, home)
    usable, broken, cuts = _cuts(usable, leave_out)
    bad = [*bad, *broken]
    per = {str(f): {**dict.fromkeys(NAMES, 0), "safety": 1} for f in bad}
    if not usable:
        remove(data_dir, code)               # no folder left: no copy of its text stays
        if bad:
            db = _open(data_dir, code)
            _set(db, "counts", {**dict.fromkeys(NAMES, 0), "safety": len(bad)})
            _set(db, "folders", per)
            _set(db, "listed", listed)
            _set(db, "screen", str(SCREEN_VERSION))
            _set(db, "complete", "1")
            db.commit()
            db.close()
        return True
    db = _open(data_dir, code)
    try:
        return _refresh_open(db, data_dir, code, usable, bad, per, listed, home, stop, progress, cuts)
    finally:
        db.close()                               # also when a read fails half way: no connection is left open by the worker


def _refresh_open(db, data_dir, code, usable, bad, per, listed, home, stop, progress, cuts=None):
    _set(db, "complete", "0")
    db.commit()
    kept = {r[0]: (r[1], r[2], r[3]) for r in db.execute("SELECT label, size, mtime_ns, state FROM files")}
    reuse = kept if _screen_ok(db) else {}        # text kept under an older screen is read and screened again, not trusted
    names = _prefixes(_all_roots(usable, home))
    seen, now_state = set(), {}
    type_labels = set()                          # `left` is kept as it was until the run ends, so a stopped run leaves the whole list, not part of it
    type_n, online, safety = 0, 0, len(bad)
    stopped_listing = False
    for folder in usable:
        reasons = {}
        listing = reach.readable_files([folder], data_dir, reasons, home, {folder: cuts[folder]} if cuts and folder in cuts else None)
        stopped_listing = stopped_listing or bool(listing.stopped)
        roots = reach.roots([folder], home)
        c = dict.fromkeys(NAMES, 0)
        c["pictures_read"] = 0
        c["online_only"] = reasons.get(reach.ONLINE, 0)
        c["safety"] = listing.skipped - c["online_only"]
        online += c["online_only"]
        safety += c["safety"]
        per[str(folder)] = c
        done = c["online_only"] + c["safety"]
        total = done + len(listing.files)
        if progress:
            progress(str(folder), done, total)
        for path in listing.files:
            if stop is not None and stop.is_set():
                db.commit()
                return False
            done += 1
            low = str(path).lower()
            if not low.endswith(TRACKED_TYPES):
                type_n += 1
                c["type"] += 1
                root = next((r for r in roots if reach.inside(path, r)), None)
                if root is not None:
                    type_labels.add(ask_passages._label(root, path, names.get(root)))
            else:
                root = next((r for r in roots if reach.inside(path, r)), None)
                label = ask_passages._label(root, path, names.get(root)) if root is not None else None
                state = None
                try:
                    st = os.stat(path) if label is not None else None
                except OSError:
                    st = None
                if label is None or st is None:
                    safety += 1
                    c["safety"] += 1
                elif label in now_state:
                    c[now_state[label] if now_state[label] in COUNTED else "safety"] += 1
                    c["pictures_read"] += _is_read_picture(label, now_state[label])
                else:
                    seen.add(label)
                    if reuse.get(label, (None,))[:2] == (st.st_size, st.st_mtime_ns) and not _picture_reader_changed(low, reuse[label][2]):
                        state = reuse[label][2]
                    else:
                        state = _read_one(db, path, label, low, st, usable, data_dir, home)
                    now_state[label] = state
                    c[state if state in COUNTED else "safety"] += 1
                    c["pictures_read"] += _is_read_picture(label, state)
            if progress:
                progress(str(folder), done, total)
    for gone in set(kept) - seen:
        _drop(db, gone)
    db.execute("DELETE FROM left")
    db.executemany("INSERT OR REPLACE INTO left VALUES(?,?)", [(x, REASON_TYPE) for x in type_labels])
    db.execute("INSERT OR REPLACE INTO left SELECT label, ? FROM files WHERE state='safety'", (REASON_SAFETY,))
    db.execute("INSERT OR REPLACE INTO left SELECT label, ? FROM files WHERE state='type'", (REASON_TYPE,))
    db.execute("INSERT OR REPLACE INTO left SELECT label, CASE WHEN lower(label) LIKE '%.pdf' THEN ? ELSE ? END FROM files WHERE state='too_long'", (REASON_TOO_LONG_PDF, REASON_TOO_LONG))
    db.execute("INSERT OR REPLACE INTO left SELECT label, ? FROM files WHERE state='picture'", (REASON_PICTURE,))
    states = [r[0] for r in db.execute("SELECT state FROM files")]
    read_pictures = sum(_is_read_picture(r[0], r[1]) for r in db.execute("SELECT label, state FROM files"))
    counts = dict.fromkeys(NAMES, 0)
    counts.update(indexed=states.count("indexed"), type=type_n + states.count("type"), too_long=states.count("too_long"), picture=states.count("picture"), pictures_read=read_pictures, online_only=online, safety=safety + states.count("safety"))
    counts["stopped"] = stopped_listing
    _set(db, "counts", counts)
    _set(db, "folders", per)
    _set(db, "screen", str(SCREEN_VERSION))
    _set(db, "listed", listed)
    _set(db, "complete", "1")
    db.commit()
    db.execute("INSERT INTO p(p) VALUES('optimize')")     # merges the segments so deleted rows are really gone
    db.commit()
    db.execute("VACUUM")                         # wipes freed pages: text of a removed file is not left behind
    return True


def _is_read_picture(label, state):
    """1 when the file is a picture that was read (so it is counted `indexed` and also in `pictures_read`), else 0."""
    return int(state == "indexed" and str(label).lower().endswith(PICTURE_TYPES))


def _picture_reader_changed(low, state):
    """A picture kept as left out is read again once a reader exists, and one kept as read is left out again when the reader is gone."""
    return low.endswith(PICTURE_TYPES) and ((state == "picture") == (ask_picture.reader() is not None))


def _read_one(db, path, label, low, st, usable, data_dir, home):
    """Read one changed file into the index; returns its state ("indexed", "safety", or "type" for a PDF with no text to read)."""
    _drop(db, label)
    state = "indexed"
    groups = []                                  # [(part name or None, lines)]
    is_pdf, is_excel, is_word = low.endswith(ask_passages.PDF_TYPES), low.endswith(EXCEL_TYPES), low.endswith(ask_passages.WORD_TYPES)
    is_pptx, is_html = low.endswith(PPTX_TYPES), low.endswith(HTML_TYPES)
    is_picture = low.endswith(PICTURE_TYPES)
    pic = ask_picture.reader() if is_picture else None
    if is_picture and pic is not None and secret_screen.name_looks_like_secret(label):
        db.execute("INSERT INTO files VALUES(?,?,?,?)", (label, st.st_size, st.st_mtime_ns, "safety"))      # a secret-named picture is never read: no copy, no reader
        return "safety"
    if is_picture and pic is None:
        db.execute("INSERT INTO files VALUES(?,?,?,?)", (label, st.st_size, st.st_mtime_ns, "picture"))      # nothing is opened: this computer cannot read it
        return "picture"
    limit = ask_picture.MAX_PICTURE_BYTES if is_picture else INDEX_PDF_BYTES if is_pdf else MAX_EXCEL_BYTES if is_excel else MAX_PPTX_BYTES if is_pptx else ask_extract.MAX_HTML_BYTES if is_html else docx_read.MAX_FILE_BYTES if is_word else ask_passages.MAX_TEXT_BYTES
    try:
        raw, truncated = reach.read_bytes(path, usable, data_dir, limit, home)
        if is_picture:
            groups = [(None, pic(raw).splitlines())] if not truncated else None
            if groups is None:
                state = "too_long"           # over the size limit: counted like any file that is too big
        elif is_pdf:
            got = pdf_reader.read(raw, truncated=truncated, max_bytes=INDEX_PDF_BYTES, max_pages=INDEX_PDF_PAGES, seconds=INDEX_PDF_SECONDS)
            if got.status != "ok":
                state = "too_long" if got.reason in ("too_big", "too_many_pages", "timeout") else "type"
            elif got.left_out:
                state = "too_long"               # only its leading pages fit the output budget: never shown as indexed in full
            else:
                groups = [(f"page {n}", t.splitlines()) for n, t in got.pages]
        elif is_excel:
            groups = _excel_groups(raw, truncated)
        elif is_pptx or is_html:
            groups = (ask_extract.pptx_groups if is_pptx else ask_extract.html_groups)(raw, truncated)
            if not groups:
                state = "type"                   # no text to read, like a scanned PDF
        else:
            groups = [(None, _lines(raw, truncated, low, os.path.basename(str(path))))]
    except reach.Never:
        state = "safety"
    except TooLong:
        state = "too_long"
    except (docx_read.WordRefused, ask_picture.PictureUnreadable, ValueError, UnicodeError, OSError):
        # a read error on this one file (OSError) leaves only this file out, so the pass goes on and the files already read stay; damaged, too big or hostile Word/Excel/PowerPoint/web page: left out as `type`, never said to look like a password (a real secret inside still screens as `safety` below)
        state = "type"
    if state == "indexed":
        every = "\n".join("\n".join(lines) for _n, lines in groups)
        if secret_screen.name_looks_like_secret(label) or secret_screen.looks_like_secret(every):
            state = "safety"
    if state == "indexed":
        left = MAX_PARTS_PER_FILE
        for name, lines in groups:
            parts = ask_data._cut(label, list(ask_passages._chunks(lines)))[:left]
            left -= len(parts)
            for i, part in enumerate(parts, 1):
                mark = i if len(parts) > 1 else 0
                if name is not None:
                    mark = name if mark == 0 else f"{name}, part {mark}"
                db.execute("INSERT INTO p(text, file, part, mtime) VALUES(?,?,?,?)", (part.text, label, mark, int(st.st_mtime)))
    db.execute("INSERT INTO files VALUES(?,?,?,?)", (label, st.st_size, st.st_mtime_ns, state))
    return state


def build(data_dir, code, folders, home=None):
    """Make the index again from nothing."""
    remove(data_dir, code)
    refresh(data_dir, code, folders, home)


def search(data_dir, code, question, limit=MAX_RESULTS, extra=()):
    """Passages for `question`, best first (newer file first when equal). Opens no source file. `extra` (row 1537 AP2) are item IDs of earlier turns:
    each is one quoted phrase ("RISK-12"), outside the first 40 question words."""
    typed = ask.ID_PATTERN.findall(question or "")       # an item ID typed in this question is matched whole, like one of an earlier turn: its pieces are not words
    words = [w for w in _WORD.findall(ask.ID_PATTERN.sub(" ", question or "")) if w.casefold() not in STOP_WORDS]       # row 1624: no common words
    phrases = ['"' + str(x).replace('"', "") + '"' for x in (*typed, *(extra or ())) if str(x).replace('"', "").strip()]
    if not words and not phrases:
        return []
    db = _open_read(data_dir, code)
    if db is None:
        return []
    try:
        if not _screen_ok(db):
            return []                                # text screened by an older screen is never given out; the next read screens it again
        match = " OR ".join(phrases + ['"' + w.replace('"', "") + '"' for w in words[:40]])
        rows = db.execute("SELECT text, file, part, mtime FROM p WHERE p MATCH ? ORDER BY round(rank, 6), mtime DESC LIMIT ?", (match, limit)).fetchall()
    except sqlite3.Error:
        return []
    finally:
        db.close()
    out = []
    for text, file, part, mtime in rows:
        label = (f"{file} (part {part})" if isinstance(part, int) else f"{file}, {part}") if part else file
        out.append(ask.Passage(f"{label}, modified {time.strftime('%Y-%m-%d', time.gmtime(mtime))}", text, file=file))
    return out


def status(data_dir, code, folders=None):
    """The counts kept by the last refresh (all 0 when there is no index yet)."""
    counts = dict.fromkeys(NAMES, 0)
    db = _open_read(data_dir, code)
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
    db = _open_read(data_dir, code)
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
    """The approved sentence for `n` files left out for one reason (picture, online, safety)."""
    if reason == "picture":
        return f"{n} {_plural(n, 'is a picture', 'are pictures')} and this computer cannot read {_plural(n, 'pictures', 'them')}."
    if reason == "online":
        return ONLINE_LINE
    if reason == "safety":
        return f"{n} look like a password or a key and were left out." if n != 1 else "1 looks like a password or a key and was left out."
    raise ValueError(reason)


def answer_note(counts):
    """The note under an answer while files are still being read; "" once the index is complete."""
    n = int((counts or {}).get("not_yet") or 0)
    if n <= 0:
        return ""
    return f"Still reading {n} file{'' if n == 1 else 's'}, so this answer may miss some."


# ----- the per-folder status line (Row 1366 slice a; the words are the approved ones) -----

def _plural(n, one, many):
    return one if n == 1 else many


def line_for(counts, reading=None):
    """The status line of one folder. `reading` is (done, total) while it is being read; `counts` the counts of its last full read."""
    if reading is not None:
        done, total = reading
        return f"Indexing\u2026 {min(99, done * 100 // total) if total > 0 else 0}%"
    total = sum(counts.get(n, 0) for n in NAMES)
    out = [f"Indexed {counts.get('indexed', 0)} of {total} {_plural(total, 'file', 'files')}."]
    t, o, long_, s, pic = (counts.get(k, 0) for k in ("type", "online_only", "too_long", "safety", "picture"))
    if counts.get("pictures_read"):
        out.append(f"{counts['pictures_read']} {_plural(counts['pictures_read'], 'picture', 'pictures')} read on this Mac.")
    if t:
        out.append(f"{t} {_plural(t, 'is', 'are')} of a type clark can't read yet.")
    if pic:
        out.append(left_out_line("picture", pic))
    if o:
        out.append(left_out_line("online", o))
    if long_:
        out.append(f"{long_} {_plural(long_, 'file is', 'files are')} too long.")
    if s:
        out.append(f"{s} {_plural(s, 'looks', 'look')} like a password or a key and {_plural(s, 'was', 'were')} left out.")
    return " ".join(out)


def done_line(counts):
    """The status line of a folder whose read is finished (row 1371): the share read, and how many files could not be read; the page's "(why)" lists them."""
    total = sum(counts.get(n, 0) for n in NAMES)
    if total <= 0 or counts.get("indexed", 0) <= 0:
        return "No files to index"          # nothing was readable: never "100% indexed"
    unread = max(total - counts.get("indexed", 0), 0)
    return "100% indexed" + (f". {unread} {_plural(unread, 'file', 'files')} could not be read" if unread else "")


def _left_by_folder(data_dir, code, folders, limit=MAX_LEFT_OUT_SHOWN):
    """{folder: {"files": [[name inside the folder, plain reason]] (at most `limit`), "more": n}} for the folders with a file left out.
    A left-out label is "<folder name>/<name>", so it goes to the folder with that name (the whole "name/" with its separator). Two folders
    with the same name (a/docs, b/docs) share that prefix, so there a file is given to the folder that really holds it."""
    whole = files_left_out(data_dir, code, 10 ** 9)["files"]
    out = {}
    roots = {}
    for f in folders or ():
        got = reach.roots([f])
        if got:
            roots[str(f)] = got[0]
    names = _prefixes(roots.values())
    for f in folders or ():
        f = str(f)
        name = names.get(roots.get(f)) or os.path.basename(f.rstrip("/\\"))
        prefix = name + "/"
        mine = [[label[len(prefix):], reason] for label, reason in whole if label.startswith(prefix)]
        if sum(1 for n in names.values() if os.path.basename(n) == os.path.basename(name)) > 1 or name != os.path.basename(name):
            mine = [m for m in mine if os.path.lexists(os.path.join(f, *m[0].split("/")))]
        if mine:
            out[f] = {"files": mine[:limit], "more": max(len(mine) - limit, 0)}
    return out


def _with_online(left, saved):
    """The files-left-out list of a folder that has online-only files starts with the line "Online-only files not searched" (row 1537 AP4; no name: they are never opened)."""
    out = dict(left)
    for f, c in saved.items():
        if isinstance(c, dict) and c.get("online_only"):
            got = out.get(f) or {"files": [], "more": 0}
            out[f] = {"files": [[ONLINE_LINE, ""]] + list(got["files"]), "more": got["more"]}
    return out


def folder_status(data_dir, code, folders, live=None, busy=False, failed=False, cleared=False, changed=None):
    """{folder: {"state": ..., "line": text}} for the folders that have something to say. The states: "reading" (the folder is being read now:
    `live` is the worker's {folder: (done, total)} for the run in progress), "done", "waiting" (a run is queued or running and has not reached a folder
    that has no index yet), "updating" (the same for a folder that has one: `changed` is {folder: n files that differ}, the count is in "changed"),
    "paused" (the index of the folder was not finished and no run is going), "failed" (the last run failed) and "cleared" (the index was deleted).
    `busy`, `failed` and `cleared` are the worker's word for the project. A folder with no index yet and no run says nothing."""
    saved = {}
    db = _open_read(data_dir, code)
    has_index = db is not None
    if db is not None:
        try:
            row = db.execute("SELECT v FROM meta WHERE k='folders'").fetchone()
            saved = json.loads(row[0]) if row else {}
        except (sqlite3.Error, ValueError):
            saved = {}
        finally:
            db.close()
    left = _with_online(_left_by_folder(data_dir, code, folders) if saved else {}, saved)
    out = {}
    for f in folders or ():
        f = str(f)
        if live and f in live:
            out[f] = {"state": "reading", "line": line_for(None, live[f])}
        elif failed:
            out[f] = {"state": "failed", "line": "Could not index this folder."}
        elif cleared:
            out[f] = {"state": "cleared", "line": "Not indexed."}
        elif busy and f not in saved:
            out[f] = {"state": "waiting", "line": "Waiting to index"}
        elif busy and (changed or {}).get(f):
            n = changed[f]
            out[f] = {"state": "updating", "line": f"Updating\u2026 {n} {_plural(n, 'file', 'files')} changed", "changed": n}
        elif f in saved:
            out[f] = {"state": "done", "line": done_line(saved[f])}
            if left.get(f):
                out[f]["left"] = left[f]
        elif has_index:
            out[f] = {"state": "paused", "line": "Indexing paused. It carries on when clark is open"}
    return out


def current(data_dir, code, folders):
    """True when the index was finished for exactly these folders (a question may then use it and read no file)."""
    db = _open_read(data_dir, code)
    if db is None:
        return False
    try:
        meta = dict(db.execute("SELECT k, v FROM meta WHERE k IN ('complete', 'listed')").fetchall())
        return _screen_ok(db) and meta.get("complete") == "1" and json.loads(meta.get("listed", "null")) == sorted(str(f) for f in folders or ())
    except (sqlite3.Error, ValueError):
        return False
    finally:
        db.close()


def stale(data_dir, code, folders, home=None, leave_out=None):
    """True when the files now in `folders` differ from the ones the index holds: a file new, gone (or no longer readable), or with another
    size or modified time. Lists the folders the way `refresh` does and reads no file. A file changed to the same size AND the same modified
    time cannot be seen this way (no content hash: that would mean reading every file on every question)."""
    db = _open_read(data_dir, code)
    if db is None:
        return True
    try:
        if not _screen_ok(db):
            return True                              # read again so the text is screened again
        kept = {r[0]: (r[1], r[2]) for r in db.execute("SELECT label, size, mtime_ns FROM files")}
    except sqlite3.Error:
        return True
    finally:
        db.close()
    usable, _bad = _unusable(folders, data_dir, home)
    usable, _broken, cuts = _cuts(usable, leave_out)
    names = _prefixes(_all_roots(usable, home))
    seen = set()
    try:
        for folder in usable:
            listing = reach.readable_files([folder], data_dir, None, home, {folder: cuts[folder]} if folder in cuts else None)
            roots = reach.roots([folder], home)
            for path in listing.files:
                if not str(path).lower().endswith(TRACKED_TYPES):
                    continue
                root = next((r for r in roots if reach.inside(path, r)), None)
                if root is None:
                    continue
                label = ask_passages._label(root, path, names.get(root))
                if label is None:
                    continue
                st = os.stat(path)
                if kept.get(label) != (st.st_size, st.st_mtime_ns):
                    return True
                seen.add(label)
    except OSError:
        return True
    return bool(set(kept) - seen)


def changed_by_folder(data_dir, code, folders, home=None, leave_out=None):
    """{folder: n} for the saved folders whose files differ from the ones the index holds (a file new, gone, or with another size or modified time).
    The same listing as `stale`, which only says whether there is a change; this counts them, for the "Updating… N files changed" line. Reads no file."""
    db = _open_read(data_dir, code)
    if db is None:
        return {}
    try:
        kept = {r[0]: (r[1], r[2]) for r in db.execute("SELECT label, size, mtime_ns FROM files")}
    except sqlite3.Error:
        return {}
    finally:
        db.close()
    usable, _bad = _unusable(folders, data_dir, home)
    usable, _broken, cuts = _cuts(usable, leave_out)           # row 1542: what the person left out is not counted as changed
    names = _prefixes(_all_roots(usable, home))
    out, seen = {}, set()
    try:
        for folder in usable:
            listing = reach.readable_files([folder], data_dir, None, home, {folder: cuts[folder]} if folder in cuts else None)
            roots = reach.roots([folder], home)
            for path in listing.files:
                if not str(path).lower().endswith(TRACKED_TYPES):
                    continue
                root = next((r for r in roots if reach.inside(path, r)), None)
                label = ask_passages._label(root, path, names.get(root)) if root is not None else None
                if label is None:
                    continue
                st = os.stat(path)
                if kept.get(label) != (st.st_size, st.st_mtime_ns):
                    out[str(folder)] = out.get(str(folder), 0) + 1
                seen.add(label)
            for label in set(kept) - seen:
                if any(label.startswith(names.get(r, "") + "/") for r in roots):
                    out[str(folder)] = out.get(str(folder), 0) + 1
                    seen.add(label)
    except OSError:
        return out
    return out


def folder_data(data_dir, code, question, budget=ask.BUDGET, max_passages=ask.MAX_PASSAGES, extra=()):
    """The passages of the index for a question, in the shape `ask_passages.folder_data` gives. Opens no source file and has no
    per-question file, byte or time limit."""
    found = search(data_dir, code, question, max_passages * 4, extra)
    chosen, left = ask_data.choose(found, " ".join([question, *extra]), budget)
    if len(chosen) > max_passages:
        left += len(chosen) - max_passages
        chosen = chosen[:max_passages]
    counts = status(data_dir, code)
    return ask_passages.FolderData(tuple(chosen), left, counts.get("safety", 0), 0, counts.get("type", 0) + counts.get("picture", 0), bool(counts.get("stopped")))


class Indexer:
    """One background thread that keeps the indexes up to date. `start(code, folders)` queues a run (the newest request for a project
    replaces an older one still waiting); `busy` counts runs queued or running; `shutdown()` stops the run at the next file and ends the thread."""

    def __init__(self, data_dir, home=None, refresh_fn=None, allowed=None, leave_out=None):
        self.data_dir = Path(data_dir)
        self.allowed = allowed               # None, or a function that says whether asking is On: while it is Off no index is built and none is kept
        self.home = home
        self.leave_out = leave_out           # None, or a function code -> {saved folder: stored left-out list} (row 1542); set by the owner of the saved folders
        self.refresh = refresh_fn or refresh
        self.wake = threading.Condition()
        self.queue = {}                      # code -> folders, in the order asked
        self.live = {}                       # code -> {folder: (done, total)} for the run in progress
        self.busy = 0
        self.checked = {}                    # code -> when the Settings poll last looked for changed files
        self.resumed = {}                    # code -> when an unfinished index was last started again
        self.failed = set()                  # projects whose last run failed: the line says so until a read is started again (row 1371)
        self.seen = set()                    # projects whose index the Settings line has shown as done: if the file is gone later, it was cleared
        self.cleared = set()                 # projects whose index was cleared: the line says so and the read starts only when asked
        self.stop = threading.Event()
        self.thread = None

    def _on(self):
        """False while asking is Off (or cannot be read): the index of the project is deleted and nothing is built. Never fails open."""
        if self.allowed is None:
            return True
        try:
            return self.allowed() is True
        except Exception:                    # noqa: BLE001 a switch that can't be read is off
            return False

    def start(self, code, folders):
        if not self._on():
            remove(self.data_dir, code)
            return False
        with self.wake:
            if self.stop.is_set():
                return False
            if code not in self.queue:
                self.busy += 1
            self.queue[code] = list(folders)
            self.failed.discard(code)
            self.cleared.discard(code)
            if self.thread is None or not self.thread.is_alive():
                self.thread = threading.Thread(target=self._work, name="ask-index", daemon=True)
                self.thread.start()
            self.wake.notify_all()
        return True

    def _work(self):
        while True:
            with self.wake:
                while not self.queue and not self.stop.is_set():
                    if not self.wake.wait(timeout=5):
                        self.thread = None
                        return
                if self.stop.is_set():
                    self.thread = None
                    return
                code = next(iter(self.queue))
                folders = self.queue.pop(code)
                self.live[code] = {}
            try:
                if not self._on():
                    remove(self.data_dir, code)
                    continue
                try:
                    os.nice(10)
                except (OSError, AttributeError):
                    pass
                cut = self._cut(code)
                self.refresh(self.data_dir, code, folders, self.home, stop=self.stop, progress=lambda f, d, t, c=code: self._note(c, f, d, t), **({"leave_out": cut} if cut else {}))
                if not self._on():
                    remove(self.data_dir, code)      # asking was turned Off while it ran
            except Exception:              # noqa: BLE001 a run that fails leaves the index not current; the next start tries again
                self.failed.add(code)
            finally:
                with self.wake:
                    self.live.pop(code, None)
                    self.busy -= 1
                    self.wake.notify_all()

    def _cut(self, code):
        """{saved folder: stored left-out list} for the project, only the folders that have something left out; {} when none or no source. A source that fails stops the run (it never reads everything)."""
        if self.leave_out is None:
            return {}
        return {f: raw for f, raw in self.leave_out(code).items() if raw not in (None, "", "[]", [])}

    def _changed(self, code, folders):
        try:
            cut = self._cut(code)
        except Exception:                    # noqa: BLE001 a list that cannot be read: no count is shown
            return None
        return changed_by_folder(self.data_dir, code, folders, self.home, **({"leave_out": cut} if cut else {}))

    def _stale(self, code, folders):
        """`stale` with the left-out lists given only when there are any (a plain call otherwise); a list that cannot be read counts as changed, so the run starts and stops there."""
        try:
            cut = self._cut(code)
        except Exception:                    # noqa: BLE001 a left-out list that cannot be read
            return True
        return stale(self.data_dir, code, folders, self.home, **({"leave_out": cut} if cut else {}))

    def _note(self, code, folder, done, total):
        with self.wake:
            if code in self.live:
                self.live[code][folder] = (done, total)

    def status_for(self, code, folders):
        if not self._on():
            remove(self.data_dir, code)
            self.seen.discard(code)
            return {}
        with self.wake:
            live = dict(self.live[code]) if code in self.live else None
            idle = code not in self.queue and code not in self.live
            due = idle and time.monotonic() - self.checked.get(code, -STALE_POLL_SECONDS) >= STALE_POLL_SECONDS
            if due:
                self.checked[code] = time.monotonic()
            failed = idle and code in self.failed
            gone = idle and code in self.seen and folders and not path_for(self.data_dir, code).exists()
            if gone:
                self.cleared.add(code)
        if failed or gone or code in self.cleared:
            due = False                              # a failed or cleared index is read again when asked (the line's link), not by the poll
        if due and folders and not path_for(self.data_dir, code).exists():
            self.start(code, folders)               # the index file is gone: build it again, so the line and the next question have it
            with self.wake:
                live = dict(self.live[code]) if code in self.live else None
        elif due and folders and not current(self.data_dir, code, folders):
            self.resume(code, folders)              # a first pass that was stopped or failed: carry on, so the index does not stay half made
            with self.wake:
                live = dict(self.live[code]) if code in self.live else None
        elif due and current(self.data_dir, code, folders) and self._stale(code, folders):
            self.start(code, folders)               # a file changed since the last read: read again, so the line stays right
            with self.wake:
                live = dict(self.live[code]) if code in self.live else None
        with self.wake:
            busy = code in self.queue or code in self.live
            failed = not busy and code in self.failed
            cleared = not busy and code in self.cleared
        changed = self._changed(code, folders) if busy and folders else None
        out = folder_status(self.data_dir, code, folders, live, busy=busy, failed=failed, cleared=cleared, changed=changed)
        if any(v["state"] == "done" for v in out.values()):
            self.seen.add(code)
        return out

    def peek(self, code, folders):
        """The same lines as `status_for`, without starting or changing anything: for counting how many projects are indexed."""
        with self.wake:
            live = dict(self.live[code]) if code in self.live else None
            busy = code in self.queue or code in self.live
        return folder_status(self.data_dir, code, folders, live, busy=busy)

    def resume(self, code, folders):
        """Start the read again for an index that is not finished (its first pass was stopped or failed). At most once every
        STALE_POLL_SECONDS for a project, however often it is asked, so a read that keeps failing is a retry now and then, never a loop.
        Nothing starts when a read is queued or running, or once clark is closing (`start` refuses then)."""
        with self.wake:
            if code in self.queue or code in self.live:
                return False
            now = time.monotonic()
            if now - self.resumed.get(code, -STALE_POLL_SECONDS) < STALE_POLL_SECONDS:
                return False
            self.resumed[code] = now
        return self.start(code, folders)

    def not_yet(self, code):
        """How many files of the run in progress for `code` are not read yet (0 when no run is going)."""
        with self.wake:
            return sum(max(t - d, 0) for d, t in self.live.get(code, {}).values())

    def current(self, code, folders):
        if not self._on():
            remove(self.data_dir, code)
            return False
        with self.wake:
            if code in self.queue or code in self.live:
                return False
        if folders and not path_for(self.data_dir, code).exists():
            self.start(code, folders)               # no index file: build it in the background, this question reads the folders
            return False
        if not current(self.data_dir, code, folders):
            if folders:
                self.resume(code, folders)          # the first pass was stopped or failed: carry on in the background; this question reads the folders
            return False
        if self._stale(code, folders):
            self.start(code, folders)               # never answer from text that may be old: this question reads the folders, the index is read again
            return False
        return True

    def wait_idle(self, timeout=10):
        end = time.monotonic() + timeout
        with self.wake:
            while self.busy and time.monotonic() < end:
                self.wake.wait(timeout=0.05)
            return not self.busy

    def shutdown(self, timeout=5):
        with self.wake:
            self.stop.set()
            self.busy -= len(self.queue)
            self.queue.clear()
            self.wake.notify_all()
            t = self.thread
        if t is not None:
            t.join(timeout)
