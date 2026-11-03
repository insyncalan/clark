"""clark's own kept copies of what was published (#443, from #342; guarded: store and server).

Every publication of a project's web page keeps a copy of the file in clark's own folder, `published-copies`, beside clark.db: one
file for each publication, named from the project's code and the publication's number and nothing else (`ABC-3.html`). It is the
very file that was saved and sent, so what a client was given can be shown again exactly. A copy is written once and never
changed: it is made with O_EXCL (an existing file is never opened for writing), read-only, and nothing in clark rewrites or
removes one. Nothing is ever pruned: the list in Settings shows the newest 10, and the older copies are still here.

A name is made only from a code of the stored shape and a whole number, so no path from a request, a row or a file name ever
reaches the folder. A copy is read through a link-refusing open and its SHA-256 is compared with the one the publication's row
holds before a single byte is used; a copy that no longer matches is reported, never shown.

No module of clark is imported here (the store calls `keep`, and the past-reports seam calls `read`), so there is no cycle.
Standard library only, Python 3.9."""
import hashlib
import os
import re
import stat
from pathlib import Path

FOLDER = "published-copies"                       # beside clark.db; nothing else is kept in it
PROJECT_CODE = re.compile(r"[A-Z][A-Z0-9]{2,6}")
MAX_BYTES = 6 * 1024 * 1024                       # a little over the 5 MB a report may be (publish.MAX_BYTES): a bigger file is not ours
NUMBER_MAX = 999999
SHA = re.compile(r"[0-9a-f]{64}")

OK, MISSING, CHANGED = "ok", "missing", "changed"


def file_name(code, number):
    """`ABC-3.html`, or None when `code` is not a project code or `number` is not a whole number from 1 to 999999. The one place a
    kept copy's name is made."""
    if not isinstance(code, str) or not PROJECT_CODE.fullmatch(code):
        return None
    if type(number) is not int or not 1 <= number <= NUMBER_MAX:
        return None
    return f"{code}-{number}.html"


def folder_of(data_dir):
    return Path(data_dir) / FOLDER


def _plain_file(path, limit):
    """The bytes of an ordinary file of at most `limit` bytes, read without following a link; None for a link, a folder, a pipe,
    a file that is too big, or anything that can't be read."""
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    try:
        fd = os.open(path, flags)
    except OSError:
        return None
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
            return None
        chunks, left = [], limit + 1
        while left > 0:
            chunk = os.read(fd, min(1 << 20, left))
            if not chunk:
                break
            chunks.append(chunk)
            left -= len(chunk)
        data = b"".join(chunks)
        return data if len(data) <= limit else None
    except OSError:
        return None
    finally:
        os.close(fd)


def keep(data_dir, code, number, source, sha256):
    """Keep a copy of the file at `source`, the file the publication `code` `number` recorded with `sha256`. True only when a new
    copy was written. False, and nothing written, when: the name is not one clark makes, the copy is there already (it is never
    opened for writing), `source` is not an ordinary file that still holds exactly the bytes whose SHA-256 is `sha256`, or the
    folder cannot be used (it is a link or a file). A fault while writing removes the half-written copy and says False; the
    publication itself is not undone by this: its row says it was made, and the list says "Not kept" for it."""
    name = file_name(code, number)
    if name is None or not isinstance(sha256, str) or not SHA.fullmatch(sha256):
        return False
    data = _plain_file(source, MAX_BYTES)
    if data is None or hashlib.sha256(data).hexdigest() != sha256:
        return False
    folder = folder_of(data_dir)
    try:
        os.mkdir(folder, 0o700)
    except FileExistsError:
        pass
    except OSError:
        return False
    try:
        if not stat.S_ISDIR(os.lstat(folder).st_mode):        # a link or a file where the folder should be: not used
            return False
        fd = os.open(folder / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o444)
    except OSError:                                          # FileExistsError too: a copy is written once
        return False
    done = False
    try:
        try:
            view = memoryview(data)
            while view:
                view = view[os.write(fd, view):]
            os.fsync(fd)
            done = True
        finally:
            os.close(fd)
    except OSError:
        pass
    if not done:
        try:
            os.unlink(folder / name)
        except OSError:
            pass
    return done


def is_kept(data_dir, code, number):
    """Whether a kept copy of the publication is there as an ordinary file (it is not read or checked)."""
    name = file_name(code, number)
    if name is None:
        return False
    try:
        return stat.S_ISREG(os.lstat(folder_of(data_dir) / name).st_mode)
    except OSError:
        return False


def read(data_dir, code, number, sha256):
    """(OK, bytes), (MISSING, None) or (CHANGED, None). The copy is read only when it is an ordinary file under its own name and its
    SHA-256 is `sha256`, the one the publication's row holds; a file that is there but is not that, is CHANGED."""
    name = file_name(code, number)
    if name is None or not isinstance(sha256, str) or not SHA.fullmatch(sha256):
        return MISSING, None
    path = folder_of(data_dir) / name
    try:
        os.lstat(path)
    except OSError:
        return MISSING, None
    data = _plain_file(path, MAX_BYTES)
    if data is None or hashlib.sha256(data).hexdigest() != sha256:
        return CHANGED, None
    return OK, data
