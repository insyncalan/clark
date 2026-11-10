"""The brand library (#944 T2): brands live in system/branding/<id>/, come in from a checked zip, and go out again.

review(path, root) checks a brand zip and writes nothing; install(review_id, root, data) puts the reviewed brand in place
(stage, check again, two renames); remove(id, root, data) and undo(root, data) take it out or put the last change back, each
with a backup under <data>/brand-backups/. installed(root) lists the brands; folder(root, id) is where one lives, or GENERIC.

A zip is read once into memory and judged by its end record and headers before any member is read; every structure failure is
the update zip's own "damaged" refusal. Nothing here joins text from a request onto a path: an id must match ID_RE first.
"""
import functools
import hashlib
import importlib.util
import json
import os
import re
import secrets
import shutil
import stat
import struct
import sys
import threading
import time
import unicodedata
import zipfile
import zlib
from contextlib import contextmanager
from pathlib import Path

from clark import excel_picture, publish, updates

ZIP_CAP = 16 * 1024 * 1024          # the zip file
TOTAL_CAP = 24 * 1024 * 1024        # all members unpacked (declared sum, and counted while reading)
MEMBER_CAP = 5 * 1024 * 1024        # one member unpacked
FILE_CAP = 50                       # entries in the zip, all of them, from the end record
COMMENT_CAP = 1024
TOKENS_CAP = 256 * 1024             # excel_palette.MAX_BRAND_BYTES: nothing accepted here may be ignored later at export
MANIFEST_CAP = 64 * 1024
RATIO_FLOOR = 64 * 1024             # a member over this at more than MEMBER_RATIO times its compressed size is a bomb
MEMBER_RATIO = 100
TOTAL_RATIO = 20                    # applied once the whole is over RATIO_FLOOR (a few KB of zeros is no bomb)
HOLD_SECONDS = 15 * 60              # a review is held this long
KEEP_BACKUPS = 5
CHUNK = 64 * 1024
MAX_NAME = 60
MAX_INT_DIGITS = 30

LOCAL = "local-brand"
GENERIC = object()                  # what folder() answers for the committed look: not None, not a path
RESERVED = ("assets", "design-system", "generic", LOCAL)
ID_RE = re.compile(r"[a-z0-9-]{1,40}")
VERSION_RE = re.compile(r"[0-9]{1,6}\.[0-9]{1,6}\.[0-9]{1,6}")
LOOK_AT = 5                         # the newest this many zips in Downloads are looked at for a brand manifest
MANIFEST = "clark-brand.json"
TOKENS = "tokens.css"
HIDDEN_NEW = ".clark-brand-new-"
HIDDEN_OLD = ".clark-brand-old-"
JOURNAL = "brand-last.json"             # beside brand-backups/, not in it
ALLOWED = re.compile(r"tokens\.css|clark-brand\.json|logo\.png|design-system/logo\.png"
                     r"|assets/(?:cover\.(?:png|jpg|jpeg|webp)|logo\.png|(?:logo|cover)-[a-z0-9-]{1,40}\.png)")

# Words a brand's name, file names and tokens.css may not hold (decision 17). A plain list; the refusal never names one.
DENY_WORDS = ("forbiddenexample",)      # extra plain words refused here (a seam the tests build files from); the real list is LISTED_WORD_CHECK


def _load_listed_word_check():
    """The repo's own listed-word guard (names_listed_word in dev/tools/publish_public.py, the one that refuses these words in
    published material), found by path in a source checkout, so no word is copied into this file. A download holds no dev/
    folder: there it is a check that finds nothing."""
    path = Path(__file__).resolve().parents[2] / "dev" / "tools" / "publish_public.py"
    try:
        spec = importlib.util.spec_from_file_location("_clark_publish_public", str(path))
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module          # its own dataclasses and regexes look themselves up by module name
        spec.loader.exec_module(module)
        return module.names_listed_word
    except Exception:
        sys.modules.pop("_clark_publish_public", None)
        return lambda line: False


LISTED_WORD_CHECK = None            # a test sets a function (line -> bool); None means "load the repo's guard on first use"

MESSAGES = {
    "damaged": updates.MESSAGES["damaged"],
    "failed": "That didn't work, and nothing was changed. Try again, or restart clark.",
    "too_big": "This brand file holds a file that is too big. The most for one file is 5 MB. Nothing was installed.",
    "too_many": "This brand file holds too many files. The most is 50. Nothing was installed.",
    "unsafe_name": "This brand file has a file name clark can't use safely. Nothing was installed.",
    "link": "This brand file holds a shortcut, which clark doesn't accept. Nothing was installed.",
    "mode": "This brand file wasn't made the way clark expects. Ask for a new copy. Nothing was installed.",
    "folder": "This brand file isn't laid out the way clark expects: it should hold one folder named after the brand. "
              "Nothing was installed.",
    "id": "The brand's short name can only use lowercase letters, numbers and hyphens, up to 40 characters. "
          "Nothing was installed.",
    "reserved": "That short name is kept for clark itself, so the brand needs a different one. Nothing was installed.",
    "denied": "This brand can't be installed: its name, a file name or its colours file holds a word clark doesn't allow.",
    "manifest": "This brand's list of files is missing or doesn't make sense. Ask for a new copy. Nothing was installed.",
    "hash": "A file in this brand doesn't match what the brand file says it holds. Download it again. "
            "Nothing was installed.",
    "tokens": "This brand's colours and fonts file can't be used: it must be plain text, at most 256 KB, and not "
              "refer to anything outside itself. Nothing was installed.",
    "picture": "A picture in this brand can't be used: it must be a PNG, JPEG or WebP picture that isn't damaged, "
               "and a PNG at most 1 MB and 2000 pixels each way. Nothing was installed.",
    "file_name": "This brand holds a file clark doesn't use. Only the colours file and the logo and cover pictures "
                 "are allowed. Nothing was installed.",
    "expired": "That brand was checked too long ago, or has been used already. Choose the brand file again.",
    "busy": "That brand is being used to make a report right now. Wait for it to finish, then try again.",
}


class BrandError(Exception):
    """A refusal. `key` names the sentence, `message` is the one plain sentence shown, `detail` is for the log only."""

    def __init__(self, key, detail=""):
        self.key = key
        self.message = MESSAGES[key]
        self.detail = detail
        super().__init__(self.message)


clock = time.time               # tests replace these two
after_write = None              # called with the staged folder once the files are written, before they are checked again

_mutex = threading.RLock()
_reviews = {}                   # review_id -> (created, id, {rel: bytes})
_state = threading.Lock()       # guards _users and _writing
_users = {}                     # brand id -> number of in_use holders
_writing = set()                # brand ids being installed, removed or put back


# --- the brand lock -----------------------------------------------------------------------------------------------------

@contextmanager
def in_use(brand_id):
    """Held by a publish or export of this brand: an install, remove or undo of it is refused meanwhile."""
    with _state:
        if brand_id in _writing:
            raise BrandError("busy", brand_id)
        _users[brand_id] = _users.get(brand_id, 0) + 1
    try:
        yield
    finally:
        with _state:
            _users[brand_id] -= 1
            if not _users[brand_id]:
                del _users[brand_id]


@contextmanager
def _write(brand_id):
    with _state:
        if _users.get(brand_id) or brand_id in _writing:
            raise BrandError("busy", brand_id)
        _writing.add(brand_id)
    try:
        yield
    finally:
        with _state:
            _writing.discard(brand_id)


# --- the library --------------------------------------------------------------------------------------------------------

def _branding(root):
    return Path(root) / "system" / "branding"


def _read_small(path, cap):
    """The bytes of a regular file of at most `cap` bytes, opened without following a link, or None."""
    try:
        before = os.lstat(path)
        if not stat.S_ISREG(before.st_mode) or before.st_size > cap:
            return None
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
        with os.fdopen(fd, "rb") as f:
            if not stat.S_ISREG(os.fstat(f.fileno()).st_mode):
                return None
            data = f.read(cap + 1)
        return data if len(data) <= cap else None
    except OSError:
        return None


def _int(text):
    if len(text.lstrip("-")) > MAX_INT_DIGITS:
        raise ValueError("number too long")
    return int(text)


def _parse_manifest(data):
    """The manifest as a dict, or None when it isn't JSON of an object."""
    try:
        doc = json.loads(data.decode("utf-8"), parse_int=_int)
    except (ValueError, RecursionError):
        return None
    return doc if isinstance(doc, dict) else None


def _clean_text(text, limit):
    return (isinstance(text, str) and 0 < len(text) <= limit and text == text.strip()
            and not any(unicodedata.category(c) in updates.HIDDEN_CATEGORIES for c in text))


def _listed(folder, brand_id):
    """{"id", "name", "version"} when `folder` is an installed brand folder whose manifest names `brand_id`, else None."""
    data = _read_small(folder / MANIFEST, MANIFEST_CAP)
    doc = _parse_manifest(data) if data is not None else None
    if not doc or doc.get("id") != brand_id or not _clean_text(doc.get("name"), MAX_NAME) \
            or not isinstance(doc.get("version"), str) or not VERSION_RE.fullmatch(doc["version"]):
        return None
    return {"id": brand_id, "name": doc["name"], "version": doc["version"]}


def _has_top_tokens(base):
    try:
        return stat.S_ISREG(os.lstat(base / TOKENS).st_mode)
    except OSError:
        return False


def _top_pack(base):
    """{"id", "name", "version", "own_folder": False, "alias": local-brand} for a pack unzipped straight into system/branding
    (tokens.css and a valid clark-brand.json at the top), else None. Its id is the manifest's when that is a plain unreserved id,
    else local-brand; its name is the manifest's. local-brand keeps resolving to the top folder too (the alias)."""
    if not _has_top_tokens(base):
        return None
    data = _read_small(base / MANIFEST, MANIFEST_CAP)
    doc = _parse_manifest(data) if data is not None else None
    if not doc or not _clean_text(doc.get("name"), MAX_NAME) or not isinstance(doc.get("version"), str) \
            or not VERSION_RE.fullmatch(doc["version"]):
        return None
    given = doc.get("id")
    plain = isinstance(given, str) and ID_RE.fullmatch(given) and given not in RESERVED
    return {"id": given if plain else LOCAL, "name": doc["name"], "version": doc["version"], "own_folder": False,
            "alias": LOCAL}


def has_manifest(path):
    """True when `path` is a zip of at most ZIP_CAP bytes and FILE_CAP entries with a clark-brand.json one folder down that is
    at most MANIFEST_CAP bytes, parses as a JSON object and names a plain id. Reads only that one member."""
    try:
        if os.path.getsize(path) > ZIP_CAP:
            return False
        with zipfile.ZipFile(path) as zf:
            infos = zf.infolist()
            if len(infos) > FILE_CAP:
                return False
            for info in infos:
                if info.filename.count("/") == 1 and info.filename.endswith("/" + MANIFEST):
                    if info.file_size > MANIFEST_CAP:
                        return False
                    with zf.open(info) as f:
                        body = f.read(MANIFEST_CAP + 1)
                    doc = _parse_manifest(body) if len(body) <= MANIFEST_CAP else None
                    given = doc.get("id") if doc else None
                    return isinstance(given, str) and bool(ID_RE.fullmatch(given)) and given not in RESERVED
            return False
    except (OSError, zipfile.BadZipFile, ValueError, NotImplementedError, RuntimeError, EOFError, zlib.error):
        return False


def newest_brand_zip(folder):
    """The newest of the newest LOOK_AT zips in `folder` that holds a brand manifest, or None. Links are not followed."""
    found = []
    for p in (sorted(Path(folder).glob("*.zip")) if folder else []):
        try:
            if p.is_file() and not p.is_symlink():
                found.append((p.stat().st_mtime, p))
        except OSError:
            continue
    for _mtime, p in sorted(found, key=lambda t: t[0], reverse=True)[:LOOK_AT]:
        if has_manifest(p):
            return p
    return None


def installed(root):
    """[{"id", "name", "version"}]: the folders of system/branding with a valid manifest naming themselves, plus local-brand
    when a tokens.css sits at the top. Hidden folders and the legacy sub-folders are ignored. Read per Settings call."""
    base = _branding(root)
    out = []
    try:
        entries = sorted(os.scandir(base), key=lambda e: e.name)
    except OSError:
        return []
    for entry in entries:
        name = entry.name
        if name in RESERVED or not ID_RE.fullmatch(name):
            continue
        try:
            if entry.is_symlink() or not entry.is_dir(follow_symlinks=False):
                continue
        except OSError:
            continue
        found = _listed(base / name, name)
        if found:
            out.append(found)
    top = _top_pack(base)
    if top and not any(b["id"] == top["id"] for b in out):
        out.append(top)
    elif _has_top_tokens(base) and not top:
        out.append({"id": LOCAL, "name": LOCAL, "version": ""})
    return sorted(out, key=lambda b: b["id"])


def _own_folder(root, brand_id):
    """True when system/branding/<brand_id> is a real (not linked) folder whose manifest names that id. Never the top pack."""
    path = _branding(root) / brand_id
    try:
        return stat.S_ISDIR(os.lstat(path).st_mode) and _listed(path, brand_id) is not None
    except OSError:
        return False


def folder(root, brand_id):
    """Where a brand lives: GENERIC for generic, an unknown or removed brand and any id that isn't plain; the top folder for
    local-brand; else system/branding/<id>. An id is matched against ID_RE and looked up as an installed brand, never joined
    from request text."""
    if not isinstance(brand_id, str) or not ID_RE.fullmatch(brand_id) or brand_id in ("generic", "assets", "design-system"):
        return GENERIC
    base = _branding(root)
    if brand_id == LOCAL:
        return base if _has_top_tokens(base) else GENERIC
    path = base / brand_id
    try:
        if stat.S_ISDIR(os.lstat(path).st_mode) and _listed(path, brand_id):
            return path
    except OSError:
        pass
    top = _top_pack(base)
    return base if top and top["id"] == brand_id else GENERIC


# --- crash recovery -----------------------------------------------------------------------------------------------------

def _rmtree(path):
    """Remove a folder or a file or a link at `path`, never following a link."""
    try:
        mode = os.lstat(path).st_mode
    except OSError:
        return
    if stat.S_ISDIR(mode):
        shutil.rmtree(path, ignore_errors=True)
    else:
        try:
            os.unlink(path)
        except OSError:
            pass


def recover(root):
    """Put right what a crash between the two renames left: a hidden old folder is moved back when the brand's own folder is
    missing, else removed; a hidden new folder is removed. Called first by every brand action."""
    base = _branding(root)
    try:
        names = sorted(os.listdir(base))
    except OSError:
        return
    with _mutex:
        for name in names:
            if name.startswith(HIDDEN_OLD):
                brand_id = name[len(HIDDEN_OLD):]
                target = base / brand_id
                if ID_RE.fullmatch(brand_id) and not os.path.lexists(target) and stat.S_ISDIR(os.lstat(base / name).st_mode):
                    os.rename(base / name, target)
                else:
                    _rmtree(base / name)
        for name in names:
            if name.startswith(HIDDEN_NEW):
                _rmtree(base / name)


# --- reading a zip ------------------------------------------------------------------------------------------------------

_ZIP_FAILS = (zipfile.BadZipFile, zipfile.LargeZipFile, zlib.error, EOFError, RuntimeError, OSError, ValueError,
              NotImplementedError, OverflowError, struct.error)


def _refusing(fn):
    """A brand action's OSError (disk full, no permission, a folder pruned from under it) is the "failed" refusal, never a bare
    error. What may be left behind is a hidden folder, put right by the next recover()."""
    @functools.wraps(fn)
    def run(*a, **k):
        try:
            return fn(*a, **k)
        except OSError as e:
            raise BrandError("failed", "%s: %s" % (type(e).__name__, e))
    return run


def _damaged(detail):
    return BrandError("damaged", detail)


def _end_record(data):
    """(position, directory start) of the zip's end record, checked: no zip64, one disk, a comment of at most 1 KB that runs to
    the end of the file, and at most FILE_CAP entries. Nothing else of the zip has been parsed yet."""
    pos = data.rfind(b"PK\x05\x06")
    if pos < 0 or pos + 22 > len(data):                 # none, or cut short: fewer than 22 bytes from the signature on
        raise _damaged("no end record")
    _sig, disk, cd_disk, here, total, cd_size, cd_off, clen = struct.unpack("<4sHHHHIIH", data[pos:pos + 22])
    if clen > COMMENT_CAP or pos + 22 + clen != len(data):
        raise _damaged("the zip comment is too long or does not end the file")
    if data[max(0, pos - 20):pos - 16] == b"PK\x06\x07" or 0xFFFF in (here, total) or 0xFFFFFFFF in (cd_size, cd_off):
        raise _damaged("zip64")
    if disk or cd_disk or here != total or not total:
        raise _damaged("more than one disk, or no entries")
    if total > FILE_CAP:
        raise BrandError("too_many", "%d entries" % total)
    if cd_size > pos or cd_off + cd_size > pos:
        raise _damaged("the directory is outside the file")
    return pos, pos - cd_size, total


def _zip64_extra(extra):
    at = 0
    while at + 4 <= len(extra):
        ident, size = struct.unpack("<HH", extra[at:at + 4])
        if ident == 1:
            return True
        at += 4 + size
    return False


def _check_headers(infos, data, cd_start):
    """Everything the headers can say, before one member is read."""
    total = packed = 0
    for i in infos:
        name = i.filename
        if name.endswith("/"):
            raise BrandError("mode", "folder entry")
        if updates.path_problem(name):
            raise BrandError("unsafe_name", updates.path_problem(name))
        if i.flag_bits & 0x2041 or i.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
            raise _damaged("encrypted or an odd compression method")
        if i.create_system != 3:
            raise BrandError("mode", "not made on Unix")
        mode = i.external_attr >> 16
        if stat.S_ISLNK(mode):
            raise BrandError("link", "link member")
        if not stat.S_ISREG(mode) or stat.S_IMODE(mode) not in (0o644, 0o755):
            raise BrandError("mode", oct(mode))
        if i.file_size > MEMBER_CAP:
            raise BrandError("too_big", "%d bytes" % i.file_size)
        if 0xFFFFFFFF in (i.file_size, i.compress_size, i.header_offset) or _zip64_extra(i.extra):
            raise _damaged("zip64")
        if i.file_size > RATIO_FLOOR and i.file_size > MEMBER_RATIO * i.compress_size:
            raise _damaged("a member far bigger than its packed size")
        total += i.file_size
        packed += i.compress_size
    if total > TOTAL_CAP:
        raise _damaged("declared total over the cap")
    if total > RATIO_FLOOR and total > TOTAL_RATIO * packed:
        raise _damaged("total ratio over the cap")
    if updates.collisions([i.filename for i in infos]):
        raise BrandError("unsafe_name", "duplicate or clashing names")
    spans = []
    for i in infos:                                     # no two members may share or cross bytes
        at = i.header_offset
        if data[at:at + 4] != b"PK\x03\x04" or at + 30 > len(data):
            raise _damaged("no local header")
        nlen, elen = struct.unpack("<HH", data[at + 26:at + 30])
        end = at + 30 + nlen + elen + i.compress_size
        if i.flag_bits & 0x8:                           # a data descriptor follows: 16 bytes with its signature, else 12
            end += 16 if data[end:end + 4] == b"PK\x07\x08" else 12
        spans.append((at, end))
    spans.sort()
    last = 0
    for at, end in spans:
        if at < last:
            raise _damaged("members overlap")
        last = end
    if last > cd_start:
        raise _damaged("a member runs into the directory")


_open_member = zipfile.ZipFile.open        # a zip member's stream (bytes), not a text-mode open()


def _read_members(zf, infos):
    """{member name: bytes}, each read in bounded chunks and counted against its declared size and the total cap."""
    out, got_total = {}, 0
    for i in infos:
        parts, got = [], 0
        with _open_member(zf, i) as f:
            while True:
                chunk = f.read(max(1, min(CHUNK, i.file_size + 1 - got)))
                if not chunk:
                    break
                got += len(chunk)
                got_total += len(chunk)
                if got > i.file_size:
                    raise _damaged("a member longer than it says")
                if got_total > TOTAL_CAP:
                    raise _damaged("unpacked total over the cap")
                parts.append(chunk)
        if got != i.file_size:
            raise _damaged("a member shorter than it says")
        out[i.filename] = b"".join(parts)
    return out


def _open_zip(path):
    """(members {name: bytes}, modes {name: permission bits}, whole-file sha256) for a brand zip, or a BrandError."""
    try:
        data = updates.read_once(path, ZIP_CAP)
    except updates.UpdateError as e:
        raise _damaged(e.detail)
    try:
        import io
        _pos, cd_start, total = _end_record(data)
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            infos = zf.infolist()
            if len(infos) != total:
                raise _damaged("the end record's count is not the directory's")
            _check_headers(infos, data, cd_start)
            members = _read_members(zf, infos)
            modes = {i.filename: stat.S_IMODE(i.external_attr >> 16) for i in infos}
    except BrandError:
        raise
    except _ZIP_FAILS as e:
        raise _damaged("%s: %s" % (type(e).__name__, e))
    return members, modes, hashlib.sha256(data).hexdigest()


# --- checking what is inside --------------------------------------------------------------------------------------------

def check_id(brand_id):
    if not isinstance(brand_id, str) or not ID_RE.fullmatch(brand_id):
        raise BrandError("id", "not a plain id")
    if brand_id in RESERVED:
        raise BrandError("reserved", brand_id)


def _has_word(text):
    global LISTED_WORD_CHECK
    low = text.lower()
    if any(w in low for w in DENY_WORDS):
        return True
    if LISTED_WORD_CHECK is None:
        LISTED_WORD_CHECK = _load_listed_word_check()
    return any(LISTED_WORD_CHECK(line) for line in text.splitlines())


def _check_jpeg(data):
    if data[:2] != b"\xff\xd8":
        return False
    at, size, sof, sos = 2, len(data), False, False
    while True:
        while at < size and data[at] == 0xFF and at + 1 < size and data[at + 1] == 0xFF:
            at += 1
        if at + 2 > size or data[at] != 0xFF:
            return False
        kind = data[at + 1]
        if kind == 0xD9:
            return sof and sos and at + 2 == size
        if kind == 0x01 or 0xD0 <= kind <= 0xD8 or kind == 0x00:
            at += 2
            continue
        if at + 4 > size:
            return False
        length = struct.unpack(">H", data[at + 2:at + 4])[0]
        if length < 2 or at + 2 + length > size:
            return False
        if kind in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
            if length < 8:
                return False
            height, width = struct.unpack(">HH", data[at + 5:at + 9])
            if not (1 <= width <= 10000 and 1 <= height <= 10000):
                return False
            sof = True
        at += 2 + length
        if kind == 0xDA:
            sos = True
            while True:                                 # the scan runs to the next marker that is not a stuffed byte or a restart
                at = data.find(b"\xff", at)
                if at < 0 or at + 1 >= size:
                    return False
                if data[at + 1] == 0x00 or 0xD0 <= data[at + 1] <= 0xD7:
                    at += 2
                    continue
                break


def _check_webp(data):
    if len(data) < 20 or data[:4] != b"RIFF" or data[8:12] != b"WEBP" or struct.unpack("<I", data[4:8])[0] + 8 != len(data):
        return False
    at, first = 12, True
    while at < len(data):
        if at + 8 > len(data):
            return False
        kind, size = struct.unpack("<4sI", data[at:at + 8])
        if first and kind not in (b"VP8 ", b"VP8L", b"VP8X"):
            return False
        if first and kind == b"VP8L" and data[at + 8:at + 9] != b"\x2f":
            return False
        first = False
        at += 8 + size + (size & 1)
    return at == len(data)


def _check_picture(rel, body):
    ext = rel.rsplit(".", 1)[-1]
    if ext == "png":
        try:
            excel_picture.read_size(body, rel)
        except excel_picture.PictureRefused as e:
            raise BrandError("picture", "%s: %s" % (rel, e))
    elif not (_check_jpeg(body) if ext in ("jpg", "jpeg") else _check_webp(body)):
        raise BrandError("picture", "%s is not a sound picture" % rel)


def _check_tokens(body):
    if len(body) > TOKENS_CAP:
        raise BrandError("tokens", "tokens.css is %d bytes" % len(body))
    try:
        css = body.decode("utf-8")
    except UnicodeDecodeError:
        raise BrandError("tokens", "tokens.css is not UTF-8")
    if _has_word(css):
        raise BrandError("denied", "tokens.css")
    if "<" in css:                  # the text goes into a <style> of the page: nothing in it may open or close a tag
        raise BrandError("tokens", "tokens.css holds a <")
    wrapped = "<style>" + css + "</style>"
    try:
        publish.check_brand(wrapped)
    except publish.PublishError as e:
        raise BrandError("tokens", str(e))
    if publish.outside_addresses(wrapped):
        raise BrandError("tokens", "reaches outside the file")


def check_content(name, files):
    """The checks both the review and tools/make_brand_zip.py run on a brand's name and its files ({rel: bytes}, without the
    manifest): allowed names, the deny-list, tokens.css, the pictures."""
    for rel in sorted(files):
        if not ALLOWED.fullmatch(rel):
            raise BrandError("file_name", rel)
    if _has_word(name) or any(_has_word(rel) for rel in files):
        raise BrandError("denied", "name or file name")
    if TOKENS not in files:
        raise BrandError("tokens", "no tokens.css")
    _check_tokens(files[TOKENS])
    for rel in sorted(files):
        if rel != TOKENS:
            _check_picture(rel, files[rel])


def _check_manifest(doc):
    """The manifest's shape; returns {path: (size, sha256, mode)}."""
    if not _clean_text(doc.get("name"), MAX_NAME) or not isinstance(doc.get("id"), str):
        raise BrandError("manifest", "name or id")
    if not isinstance(doc.get("version"), str) or not VERSION_RE.fullmatch(doc["version"]):
        raise BrandError("manifest", "version")
    rows = doc.get("files")
    if not isinstance(rows, list) or len(rows) > FILE_CAP:
        raise BrandError("manifest", "files")
    out = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("path"), str) or not isinstance(row.get("sha256"), str) \
                or not re.fullmatch(r"[0-9a-f]{64}", row["sha256"]) or not isinstance(row.get("size"), int) \
                or isinstance(row["size"], bool) or row["size"] < 0 or not isinstance(row.get("mode"), str) \
                or not re.fullmatch(r"[0-7]{3,6}", row["mode"]) or row["path"] in out or row["path"] == MANIFEST:
            raise BrandError("manifest", "a row")
        out[row["path"]] = (row["size"], row["sha256"], int(row["mode"], 8) & 0o7777)
    return out


def _old_files(root, brand_id):
    base = _branding(root) / brand_id
    out = []
    for dirpath, _dirs, files in os.walk(base):
        out += [(Path(dirpath) / n).relative_to(base).as_posix() for n in files]
    return sorted(out)


def _purge(now):
    for key in [k for k, v in _reviews.items() if now - v[0] > HOLD_SECONDS]:
        del _reviews[key]


@_refusing
def review(path, root):
    """Check a brand zip and hold it for 15 minutes. Returns {"review_id", "id", "name", "version", "zip_sha256", "added",
    "replaced", "removed"}. Writes nothing (it only puts right what a crash left, first)."""
    recover(root)
    members, modes, zip_sha = _open_zip(path)
    names = list(members)
    tops = {n.split("/")[0] for n in names if "/" in n}
    if len(tops) != 1 or any("/" not in n for n in names):
        raise BrandError("folder", "not one top folder")
    top = tops.pop()
    files = {n[len(top) + 1:]: b for n, b in members.items()}
    if len(files) != len(names):
        raise BrandError("unsafe_name", "duplicate names")
    if MANIFEST not in files:
        raise BrandError("manifest", "no manifest")
    if len(files[MANIFEST]) > MANIFEST_CAP:
        raise BrandError("manifest", "too big")
    manifest_bytes = files.pop(MANIFEST)
    doc = _parse_manifest(manifest_bytes)
    if doc is None:
        raise BrandError("manifest", "not a JSON object")
    rows = _check_manifest(doc)
    brand_id = doc["id"]
    check_id(brand_id)
    if brand_id != top:
        raise BrandError("folder", "the manifest's id is not the folder's")
    if set(rows) != set(files):
        raise BrandError("manifest", "the rows and the files differ")
    for rel, body in files.items():
        size, sha, mode = rows[rel]
        if mode != modes[top + "/" + rel]:
            raise BrandError("manifest", "mode")
        if len(body) != size or hashlib.sha256(body).hexdigest() != sha:
            raise BrandError("hash", rel)
    check_content(doc["name"], files)
    new = sorted(list(files) + [MANIFEST])
    old = _old_files(root, brand_id)
    now = clock()
    with _mutex:
        _purge(now)
        review_id = secrets.token_hex(16)
        _reviews[review_id] = (now, brand_id, dict(files, **{MANIFEST: manifest_bytes}))
    return {"review_id": review_id, "id": brand_id, "name": doc["name"], "version": doc["version"], "zip_sha256": zip_sha,
            "added": [n for n in new if n not in old], "replaced": [n for n in new if n in old],
            "removed": [n for n in old if n not in new]}


# --- writing ------------------------------------------------------------------------------------------------------------

def _walk_files(base):
    """{rel: path} of every file under `base`; a link, a device or anything not a plain file or folder is a BrandError."""
    out = {}
    stack = [""]
    while stack:
        rel = stack.pop()
        here = Path(base, rel) if rel else Path(base)
        for name in sorted(os.listdir(here)):
            sub = (rel + "/" + name) if rel else name
            mode = os.lstat(here / name).st_mode
            if stat.S_ISDIR(mode):
                stack.append(sub)
            elif stat.S_ISREG(mode):
                out[sub] = here / name
            else:
                raise BrandError("link", "not a plain file")
    return out


def _copy_tree(src, dst):
    """Copy a brand folder to a new `dst` (mode 0700), files opened exclusive; no link is followed or copied."""
    files = _walk_files(src)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    os.mkdir(dst, 0o700)
    for rel, path in files.items():
        target = os.path.join(dst, *rel.split("/"))
        os.makedirs(os.path.dirname(target), exist_ok=True)
        body = _read_small(path, MEMBER_CAP * 2)
        if body is None:
            raise BrandError("failed", "can't read " + rel)
        _put(target, body)


def _put(target, body):
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o644)
    with os.fdopen(fd, "wb") as f:
        f.write(body)


def _stage(base, brand_id, files):
    """Write `files` ({rel: bytes}) into base/.clark-brand-new-<id> (0700), then check what is on disk against them."""
    stage = base / (HIDDEN_NEW + brand_id)
    _rmtree(stage)
    os.mkdir(stage, 0o700)
    try:
        for rel, body in files.items():
            target = os.path.join(stage, *rel.split("/"))
            os.makedirs(os.path.dirname(target), exist_ok=True)
            _put(target, body)
        if after_write:
            after_write(str(stage))
        _verify(stage, files)
        os.chmod(stage, 0o755)
    except BaseException:
        _rmtree(stage)
        raise
    return stage


def _verify(stage, files):
    """The staged tree holds exactly `files`, as plain files, with the same bytes."""
    found = _walk_files(stage)
    if set(found) != set(files):
        raise BrandError("hash", "the staged files differ")
    for rel, path in found.items():
        body = _read_small(path, MEMBER_CAP * 2)
        if body is None or hashlib.sha256(body).digest() != hashlib.sha256(files[rel]).digest():
            raise BrandError("hash", rel)


def _swap(base, brand_id, stage):
    """Rename the old folder aside, the new one into place, then delete the old. If the second rename fails the old folder is renamed back
    at once (#944); a crash between the renames, or a failed way back, is put right by recover() at the next brand action."""
    target, aside = base / brand_id, base / (HIDDEN_OLD + brand_id)
    _rmtree(aside)
    moved = os.path.lexists(target)
    if moved:
        os.rename(target, aside)
    try:
        os.rename(stage, target)
    except BaseException:
        if moved:
            try:
                os.rename(aside, target)
            except OSError:
                pass
        raise
    _rmtree(aside)


def _stamp(backups, brand_id):
    t = int(clock())
    while True:
        name = "%s-%s" % (time.strftime("%Y%m%dT%H%M%S", time.gmtime(t)), brand_id)
        if not (backups / name).exists():
            return name
        t += 1


def _backup(data, root, brand_id):
    """Copy the brand's folder to <data>/brand-backups/<stamp>-<id>; returns the name."""
    backups = Path(data) / "brand-backups"
    name = _stamp(backups, brand_id)
    _copy_tree(_branding(root) / brand_id, str(backups / name))
    return name


def _journal(data, kind, brand_id, backup):
    backups = Path(data) / "brand-backups"
    os.makedirs(backups, exist_ok=True)
    tmp = Path(data) / (JOURNAL + ".tmp")
    tmp.write_text(json.dumps({"kind": kind, "id": brand_id, "backup": backup}), encoding="utf-8")
    os.replace(tmp, Path(data) / JOURNAL)
    keep = sorted(p.name for p in backups.iterdir() if p.is_dir() and not p.is_symlink())
    for old in keep[:-KEEP_BACKUPS]:
        _rmtree(backups / old)


def _journalled(data, kind, brand_id, backup, act):
    """Write the undo journal, then do `act` (#944). If the journal cannot be written nothing has been changed; if `act` fails the journal
    is put back as it was, so Undo never offers a change that was not made."""
    path = Path(data) / JOURNAL
    before = _read_small(path, 4096)
    _journal(data, kind, brand_id, backup)
    try:
        act()
    except BaseException:
        try:
            if before is None:
                _rmtree(path)
            else:
                tmp = Path(data) / (JOURNAL + ".tmp")
                tmp.write_bytes(before)
                os.replace(tmp, path)
        except OSError:
            pass
        raise


@_refusing
def install(review_id, root, data):
    """Put a reviewed brand in place, replacing the same id; one go per review."""
    with _mutex:
        now = clock()
        _purge(now)
        held = _reviews.get(review_id) if isinstance(review_id, str) else None
        if held is None:
            raise BrandError("expired", "unknown or old review")
        _created, brand_id, files = held
        with _write(brand_id):
            del _reviews[review_id]
            recover(root)
            base = _branding(root)
            os.makedirs(base, exist_ok=True)
            target = base / brand_id
            had = os.path.lexists(target)
            if had and not stat.S_ISDIR(os.lstat(target).st_mode):
                raise BrandError("link", "the brand's place is not a folder")
            backup = _backup(data, root, brand_id) if had else None
            stage = _stage(base, brand_id, files)
            try:
                _journalled(data, "replace" if had else "install", brand_id, backup, lambda: _swap(base, brand_id, stage))
            except BaseException:
                _rmtree(stage)            # not swapped in (the journal or a rename failed): the staged copy does not stay behind
                raise


@_refusing
def remove(brand_id, root, data):
    """Back the brand up, then take it out. generic, local-brand and anything not installed are refused."""
    with _mutex:
        if not isinstance(brand_id, str) or not ID_RE.fullmatch(brand_id) or brand_id in RESERVED:
            raise BrandError("failed", "not a removable brand")
        with _write(brand_id):
            recover(root)
            if not _own_folder(root, brand_id):
                raise BrandError("failed", "not installed")
            backup = _backup(data, root, brand_id)
            base = _branding(root)
            aside = base / (HIDDEN_OLD + brand_id)
            _rmtree(aside)

            def take_out():
                os.rename(base / brand_id, aside)
                _rmtree(aside)
            _journalled(data, "remove", brand_id, backup, take_out)


@_refusing
def _last_change(data):
    """The undo journal's contents ({"kind", "id", "backup"}) when <data>/brand-last.json is there and valid, else None."""
    raw = _read_small(Path(data) / JOURNAL, 4096)
    doc = _parse_manifest(raw) if raw else None
    if not doc or doc.get("kind") not in ("install", "replace", "remove") or not isinstance(doc.get("id"), str) \
            or not ID_RE.fullmatch(doc["id"]) or doc["id"] in RESERVED:
        return None
    return doc


def can_undo(root, data):
    """True when undo() has something to put back: the journal is there and valid and, for a replace or a remove, so is its
    backup folder. Reads only; never raises."""
    try:
        doc = _last_change(data)
        if doc is None:
            return False
        if doc["kind"] == "install":
            return True
        name = doc.get("backup")
        if not isinstance(name, str) or "/" in name or not name.endswith("-" + doc["id"]):
            return False
        return stat.S_ISDIR(os.lstat(Path(data) / "brand-backups" / name).st_mode)
    except (OSError, ValueError):
        return False


@_refusing
def undo(root, data):
    """Put the last install, replace or remove back. One level: a second undo has nothing to undo."""
    with _mutex:
        recover(root)
        backups = Path(data) / "brand-backups"
        doc = _last_change(data)
        if doc is None:
            raise BrandError("failed", "nothing to undo")
        brand_id, base = doc["id"], _branding(root)
        with _write(brand_id):
            if os.path.lexists(base / brand_id) and not _own_folder(root, brand_id):
                raise BrandError("failed", "not an installed brand")
            if doc["kind"] == "install":
                aside = base / (HIDDEN_OLD + brand_id)
                _rmtree(aside)
                if os.path.lexists(base / brand_id):
                    os.rename(base / brand_id, aside)
                    _rmtree(aside)
            else:
                name = doc.get("backup")
                if not isinstance(name, str) or "/" in name or not name.endswith("-" + brand_id):
                    raise BrandError("failed", "no backup recorded")
                files = {rel: _read_small(path, MEMBER_CAP * 2) for rel, path in _walk_files(backups / name).items()}
                if None in files.values():
                    raise BrandError("failed", "can't read the backup")
                os.makedirs(base, exist_ok=True)
                _swap(base, brand_id, _stage(base, brand_id, files))
            _rmtree(Path(data) / JOURNAL)
