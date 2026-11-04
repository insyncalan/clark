"""clark's own kept copies of what was published (#443, from #342; guarded: store and server).

Every publication of a project's web page keeps a copy of the file in clark's own folder, `published-copies`, beside clark.db: one
file for each publication, named from the project's code and the publication's number and nothing else (`ABC-3.html`). It is the
very file that was saved and sent, so what a client was given can be shown again exactly. A copy is written once and never
changed: it is made with O_EXCL (an existing file is never opened for writing), read-only, and nothing in clark rewrites or
removes one. Nothing is ever pruned: the list in Settings shows the newest 10, and the older copies are still here.

A name is made only from a code of the stored shape and a whole number, so no path from a request, a row or a file name ever
reaches the folder. A copy is read through a link-refusing open and its SHA-256 is compared with the one the publication's row
holds before a single byte is used; a copy that no longer matches is reported, never shown.

#342: beside each page, a copy of its data, `ABC-3.json`: the very JSON of the page's own clark-data block, cut from the bytes that
were published, so it holds nothing the published file did not. It is written once, like the page, and only after the page is. A
later view (#344's week picker, #346's compare with the publication before) reads it with `read_data`, which checks it against the
page whose SHA-256 the row holds. An old publication can be archived (`archive`): a marker, `ABC-3.archived`, hides it from the
list and nothing is removed. Every file here is written once: to a temporary file, then linked into place under its name, which
refuses a name already there, so a reader never meets half a file and nothing is ever replaced.

No module of clark is imported here (the store calls `keep` and `archive`, and the past-reports seam calls `read`), so there is no
cycle. Standard library only, Python 3.9."""
import hashlib
import json
import os
import re
import secrets
import stat
from pathlib import Path

FOLDER = "published-copies"                       # beside clark.db; the pages, their data copies and archive marks, nothing else
PROJECT_CODE = re.compile(r"[A-Z][A-Z0-9]{2,6}")
MAX_BYTES = 6 * 1024 * 1024                       # a little over the 5 MB a report may be (publish.MAX_BYTES): a bigger file is not ours
NUMBER_MAX = 999999
SHA = re.compile(r"[0-9a-f]{64}")
DATA, ARCHIVED = ".json", ".archived"             # #342: the data copy and the archive mark, beside ABC-3.html
# publish.DATA_BLOCK, as bytes (a test pins the two equal): the clark-data block, only where render() puts it, before the last </body>
DATA_BLOCK = re.compile(rb'<script type="application/json" id="clark-data">([^<]*)</script>\n\Z')

OK, MISSING, CHANGED = "ok", "missing", "changed"


def file_name(code, number):
    """`ABC-3.html`, or None when `code` is not a project code or `number` is not a whole number from 1 to 999999. The one place a
    kept copy's name is made."""
    if not isinstance(code, str) or not PROJECT_CODE.fullmatch(code):
        return None
    if type(number) is not int or not 1 <= number <= NUMBER_MAX:
        return None
    return f"{code}-{number}.html"


def _name(code, number, suffix):
    """`ABC-3.json` or `ABC-3.archived`: made from file_name, so only from a code and a number; None as file_name is."""
    name = file_name(code, number)
    return None if name is None else name[:-len(".html")] + suffix


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


def _folder(data_dir):
    """The kept folder, made if need be; None when it can't be used (it is a link or a file, or can't be made)."""
    folder = folder_of(data_dir)
    try:
        os.mkdir(folder, 0o700)
    except FileExistsError:
        pass
    except OSError:
        return None
    try:
        return folder if stat.S_ISDIR(os.lstat(folder).st_mode) else None   # a link or a file where the folder should be: not used
    except OSError:
        return None


def _write_once(folder, name, data):
    """Write `data` as `folder/name`, read-only, once: True only when this call put it there. The bytes go to a temporary file of
    this call's own (an exclusive create), are flushed, and the file is then linked in under `name`; a link refuses a name that is
    there already (a file, a link or anything else), so nothing is replaced or written through, and a reader sees the whole file or
    none. A file system that can't link is written with an exclusive create instead. The temporary file is always removed."""
    tmp = folder / f".{name}.{secrets.token_hex(8)}.tmp"
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | nofollow, 0o444)
    except OSError:
        return False
    try:
        try:
            view = memoryview(data)
            while view:
                view = view[os.write(fd, view):]
            os.fsync(fd)
        finally:
            os.close(fd)
        try:
            os.link(tmp, folder / name)
            return True
        except FileExistsError:                              # written once: the one there stands
            return False
        except OSError:
            pass
        fd = os.open(folder / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | nofollow, 0o444)
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
        finally:
            if not done:
                try:
                    os.unlink(folder / name)
                except OSError:
                    pass
        return done
    except OSError:
        return False
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def data_of(page):
    """The JSON text of a published page's own clark-data block (bytes), or None when the page has no such block where render()
    puts it, or its text is not a JSON object."""
    end = page.rfind(b"</body>") if isinstance(page, (bytes, bytearray)) else -1
    m = DATA_BLOCK.search(page, 0, end) if end >= 0 else None
    if m is None:
        return None
    try:
        return m.group(1) if isinstance(json.loads(m.group(1)), dict) else None
    except ValueError:
        return None


def keep(data_dir, code, number, source, sha256):
    """Keep a copy of the file at `source`, the file the publication `code` `number` recorded with `sha256`, and (#342) a copy of
    its data. True only when a new copy of the page was written. False, and nothing written, when: the name is not one clark makes,
    the copy is there already (it is never opened for writing), `source` is not an ordinary file that still holds exactly the bytes
    whose SHA-256 is `sha256`, or the folder cannot be used (it is a link or a file). A fault while writing leaves no copy and says
    False; the publication itself is not undone by this: its row says it was made, and the list says "Not kept" for it. The data
    copy is written only after the page, from the page's own bytes, and only once; one that can't be written leaves the page kept
    (read_data reads the page's block then)."""
    name = file_name(code, number)
    if name is None or not isinstance(sha256, str) or not SHA.fullmatch(sha256):
        return False
    data = _plain_file(source, MAX_BYTES)
    if data is None or hashlib.sha256(data).hexdigest() != sha256:
        return False
    folder = _folder(data_dir)
    if folder is None or not _write_once(folder, name, data):
        return False
    block = data_of(data)
    if block is not None:
        _write_once(folder, _name(code, number, DATA), block)
    return True


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


def read_data(data_dir, code, number, sha256):
    """#342: (OK, the data as a dict), (MISSING, None) or (CHANGED, None), for a later view (#344, #346). The page's kept copy is
    read first, as `read` does (its SHA-256 must be `sha256`, the row's); the data copy must then be exactly the page's own
    clark-data block, or it is CHANGED. A page kept before data copies were (or whose data copy could not be written) is read
    from its own block. Read-only."""
    state, page = read(data_dir, code, number, sha256)
    if state != OK:
        return state, None
    block = data_of(page)
    if block is None:
        return CHANGED, None
    path = folder_of(data_dir) / _name(code, number, DATA)
    try:
        os.lstat(path)
    except OSError:
        return OK, json.loads(block)
    kept = _plain_file(path, MAX_BYTES)
    if kept != block:
        return CHANGED, None
    return OK, json.loads(kept)


def archive(data_dir, code, number):
    """#342: archive the publication `code` `number`: its mark, `ABC-3.archived`, is written once (empty), and the list leaves it
    out. Nothing is removed or changed: the page and its data stay as they are. True when this call archived it; False when it was
    archived already, the name is not one clark makes, or the folder can't be used. The store checks the publication is there."""
    name = _name(code, number, ARCHIVED)
    if name is None:
        return False
    folder = _folder(data_dir)
    return folder is not None and _write_once(folder, name, b"")


def unarchive(data_dir, code, number):
    """Restore a publication that was archived: its mark, `ABC-3.archived`, is removed and the list shows the publication again. Only
    the mark is removed (the page and its data copy are never touched). True when this call removed it; False when there was no mark,
    the name is not one clark makes, or the mark could not be removed. A link under that name is removed as a link, never followed."""
    name = _name(code, number, ARCHIVED)
    if name is None:
        return False
    try:
        os.unlink(folder_of(data_dir) / name)
        return True
    except OSError:
        return False


def is_archived(data_dir, code, number):
    """Whether the publication has its archive mark (anything under that name counts: it is never followed or read)."""
    name = _name(code, number, ARCHIVED)
    if name is None:
        return False
    try:
        os.lstat(folder_of(data_dir) / name)
        return True
    except OSError:
        return False
