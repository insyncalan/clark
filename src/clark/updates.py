"""Check an update file and work out what installing it would change.

Everything here only READS: it opens the update file and the app folder and writes nothing, so it can be run for a review
at any time. Installing, backing up and undoing are other steps and live elsewhere.

- read_release(path, ...) opens a download (clark-X.Y.Z-mac.zip) without extracting it to disk by name, and checks it, in
  this order, stopping at the first failure with one plain sentence (UpdateError.message). The real reason, and up to five
  member names, are in UpdateError.detail, for the log and never for the screen:
  the name and system; a regular file, not too big; opens as a zip; clark-release.json is there (else it is GitHub's whole
  source code); the shape of every member (no folders, links, encryption, odd compression or duplicate names); every member
  path (nothing absolute, no `..`, no backslash or colon, nothing Windows can't hold, no names that differ only by capitals or
  accents); every member is in release_files' list for this system and nothing from it is missing; the manifest agrees with
  the members, and each file's SHA-256, size and mode match; the version inside agrees with the name; then the version rule
  (newer, or the same or older only when reinstalling), `min_from`, and the data layout number: an update that changes the
  data layout is refused for now.
- check_app_folder(app_dir) refuses a folder that holds `.git`, has no record of what it holds, has a link inside, or can't
  be written to.
- plan(release, app_dir) compares the new files with the installed ones: added, replaced, removed (only a file the last
  install recorded, so a file the person added is never removed), left, and changed by hand.
- review(release, plan, installed_version) is the plain text the page shows: from to, the date, the notes, the three lists and
  "Your projects, settings and published reports are kept."
- newest_in(folder, system) names the newest update file in a folder (Downloads), reading file names only.

Standard library only, Python 3.9. A sentence a person reads never starts with the product name, and holds no file path,
database text or the words zip, manifest or SHA.
"""
import hashlib
import json
import os
import re
import stat
import unicodedata
import zipfile
from pathlib import Path, PurePosixPath

from clark import release_files
from clark.platform import MAX_PATH, RESERVED_NAMES

MANIFEST = release_files.MANIFEST
INSTALLED_RECORD = MANIFEST            # the installed app folder keeps the manifest of its own release, as its record
MAX_ZIP_BYTES = 200 * 1024 * 1024
MAX_TOTAL_BYTES = 500 * 1024 * 1024
MAX_MANIFEST_BYTES = 4 * 1024 * 1024
CHUNK = 1024 * 1024
MAX_PART = 255
MAX_DETAIL_NAMES = 5
COPY_SUFFIX = r"(?: \([0-9]+\))?"                  # a browser's "clark-0.3.1-mac (1).zip", accepted for a chosen file only
NUM = r"(0|[1-9][0-9]*)"
NAME_RE = re.compile(rf"clark-{NUM}\.{NUM}\.{NUM}-(mac|windows|linux)\.zip\Z")
CHOSEN_RE = re.compile(rf"clark-{NUM}\.{NUM}\.{NUM}-(mac|windows|linux){COPY_SUFFIX}\.zip\Z")
SOURCE_RE = re.compile(rf"clark-{NUM}\.{NUM}\.{NUM}{COPY_SUFFIX}\.zip\Z")     # GitHub's "Source code (zip)"
VERSION_RE = re.compile(rf"{NUM}\.{NUM}\.{NUM}\Z")
DEV_RE = re.compile(rf"{NUM}\.{NUM}\.{NUM}\.dev[0-9]*\Z")
TOP_RE = re.compile(rf"clark-{NUM}\.{NUM}\.{NUM}\Z")
BAD_CHARS = set('<>"|?*:\\')
FILE_ATTRIBUTE_REPARSE_POINT = 0x400               # a Windows junction or other reparse point
SYSTEM_NAMES = {"mac": "Mac", "windows": "Windows", "linux": "Linux"}
STAMP_LENGTH = len("20261029T120000Z")

NO_NOTES = "No notes were written for this release."
KEPT = "Your projects, settings and published reports are kept. A copy of your data is made first."

MESSAGES = {
    "name": "That isn't a clark update. Choose the update file from the clark releases page. Its name looks like clark-1.2.3-{ours}.",
    "source": "That is the whole source code, not an update. On the releases page, download the file under Assets "
              "whose name ends in -{ours}.",
    "system": "This update is for {theirs}. Download the one for {ours} from the clark releases page.",
    "unreadable": "That file can't be read as an update. Choose the downloaded update file.",
    "damaged": "This update file is damaged or has been changed. Download it again.",
    "incomplete": "This update file is incomplete. Download it again.",
    "unsafe": "This update would change things outside clark's own files, so it wasn't installed. "
              "Download it again from the clark releases page.",
    "older": "Version {theirs} is older than the one you have ({ours}). Choose Install again only if you want it anyway.",
    "same": "Version {theirs} is the one you have already. Choose Install again only if you want it anyway.",
    "min_from": "This update can only be installed over version {need} or newer. Install that version first, then this one.",
    "layout": "This update changes how your data is kept, so it can't be installed from Settings yet. Nothing was changed. "
              "Keep using the version you have; a later update will install it for you.",
    "installed": "The version you have can't be told, so it can't update itself. Download the latest release and replace "
                 "the clark folder by hand. Nothing was changed.",
    "git": "This copy of clark runs from its source code, so it can't update itself. Download the latest release instead.",
    "norecord": "This copy of clark has no record of what it holds, so it can't update itself. Nothing was changed. "
                "Download the latest release and replace the clark folder by hand.",
    "link": "The clark folder has a shortcut inside it, so the update can't be installed safely. "
            "Download clark again into a new folder.",
    "readonly": "You can't change the clark folder from this account, so the update can't be installed. "
                "Move the clark folder into your own folders, then try again.",
    "toodeep": "The clark folder is too deep in other folders for this update. Move it nearer the top of the drive, "
               "then try again.",
}


class UpdateError(Exception):
    """A refusal. `key` names the sentence, `message` is the plain line shown, `detail` is for the log only."""

    def __init__(self, key, detail="", **words):
        self.key = key
        self.message = MESSAGES[key].format(**words)
        self.detail = detail
        super().__init__(self.message)


def names_for_log(names):
    names = list(names)
    return ", ".join(names[:MAX_DETAIL_NAMES]) + (f" and {len(names) - MAX_DETAIL_NAMES} more" if len(names) > MAX_DETAIL_NAMES else "")


MAX_DIGITS = 1000               # a number in the release record longer than this is refused (it would be slow to read on 3.9)
MAX_NOTES = 20000               # characters of release notes kept for the page
# Characters that change how text is drawn or read without being seen: the bidirectional controls and the zero-width ones.
HIDDEN = {0x200B, 0x200C, 0x200D, 0x200E, 0x200F, 0x2028, 0x2029, 0x202A, 0x202B, 0x202C, 0x202D, 0x202E, 0x2060,
          0x2066, 0x2067, 0x2068, 0x2069, 0xFEFF}


def parse_int(text):
    """json's reader for whole numbers, refusing a very long one before it is turned into a number."""
    if len(text) > MAX_DIGITS:
        raise ValueError("number too long")
    return int(text)


def clean_notes(text):
    """The release notes as the page may show them: control characters other than line breaks and tabs, and the hidden
    characters above, taken out; at most MAX_NOTES characters."""
    if not isinstance(text, str):
        return ""
    kept = "".join(c for c in text.replace("\r\n", "\n").replace("\r", "\n")
                   if (c in "\n\t" or (ord(c) >= 32 and not 127 <= ord(c) < 160)) and ord(c) not in HIDDEN)
    return kept[:MAX_NOTES]


# --- versions ---------------------------------------------------------------------------------------------------------

def version_key(text):
    """A version as numbers that compare: X.Y.Z, or X.Y.Z.devN for a source copy, which sorts below its own release."""
    text = str(text)
    if VERSION_RE.match(text):
        return tuple(int(n) for n in text.split(".")) + (1,)
    if DEV_RE.match(text):
        return tuple(int(n) for n in text.split(".")[:3]) + (0,)
    raise ValueError(text)


def is_release_version(text):
    return isinstance(text, str) and bool(VERSION_RE.match(text))


# --- the name ---------------------------------------------------------------------------------------------------------

def check_name(name, system, chosen=False):
    """Refuse a name that isn't an update for this system. Returns the version text in the name."""
    found = (CHOSEN_RE if chosen else NAME_RE).match(name)
    if not found:
        if SOURCE_RE.match(name):
            raise UpdateError("source", f"the name {name} is GitHub's source download", ours=system)
        raise UpdateError("name", f"the name {name} does not fit", ours=system)
    if found.group(4) != system:
        raise UpdateError("system", f"the update is for {found.group(4)}", theirs=SYSTEM_NAMES[found.group(4)],
                          ours=SYSTEM_NAMES.get(system, system))
    return ".".join(found.group(1, 2, 3))


# --- member paths -----------------------------------------------------------------------------------------------------

def path_problem(rel):
    """Why `rel` (a member name without the top folder, "/" between parts) can't be a safe app file, or None.

    The rules are the strictest of Mac, Windows and Linux, so a file that passes here is safe on all three."""
    if not rel:
        return "empty name"
    if "\\" in rel:
        return "backslash"
    if rel.startswith("/"):
        return "absolute path"
    if re.match(r"^[A-Za-z]:", rel):
        return "drive letter"
    if unicodedata.normalize("NFC", rel) != rel:
        return "name is not in Unicode normal form"
    for part in rel.split("/"):
        if part in ("", ".", ".."):
            return "empty, dot or dot-dot part"
        if len(part) > MAX_PART:
            return "part longer than 255 characters"
        if any(ord(c) < 32 or ord(c) == 127 for c in part):
            return "control character"
        if BAD_CHARS & set(part):
            return "character Windows can't hold"
        if part != part.rstrip(". "):
            return "trailing dot or space"
        if part.split(".")[0].rstrip(" ").upper() in RESERVED_NAMES:
            return "Windows device name"
    return None


def collisions(rels):
    """Names that differ only by capitals or accents (one file would overwrite the other on a Mac or Windows disk), and a
    file with the same folded name as a folder. Returns the offending names."""
    seen, folders, bad = {}, set(), []
    for rel in rels:
        folded = unicodedata.normalize("NFC", rel).casefold()
        if folded in seen:
            bad += [rel, seen[folded]]
        seen[folded] = rel
        parts = folded.split("/")
        folders.update("/".join(parts[:i]) for i in range(1, len(parts)))
    bad += [seen[f] for f in seen if f in folders]
    return sorted(set(bad))


def too_deep(app_dir, rels, data_dir=None, limit=MAX_PATH, from_version="0.0.0", to_version="0.0.0"):
    """The relative names whose longest place (in the app folder, in the staging folder beside it, or in the backup under
    the data folder) would reach `limit` characters, counting the ending NUL as Windows does. The caller passes the limit
    only where it applies (Windows)."""
    app = str(app_dir)
    staging = os.path.join(app, ".clark-update-" + "0" * STAMP_LENGTH)
    backup = os.path.join(str(data_dir), "updates", "0" * STAMP_LENGTH + f"-{from_version}-to-{to_version}", "app") if data_dir else None
    long = []
    for rel in rels:
        longest = max(len(os.path.join(base, *rel.split("/"))) for base in (app, staging) + ((backup,) if backup else ()))
        if longest + 1 >= limit:
            long.append(rel)
    return long


# --- reading a release ------------------------------------------------------------------------------------------------

class Release:
    """What a checked update file holds. `files` maps each name (without the top folder) to {sha256, size, mode}."""

    def __init__(self, path, manifest, top):
        self.path = Path(path)
        self.top = top
        self.version = manifest["version"]
        self.system = manifest["system"]
        self.released = manifest["released"]
        self.notes = clean_notes(manifest.get("notes", ""))
        self.schema_version = manifest["schema_version"]
        self.min_from = manifest["min_from"]
        self.files = manifest["files"]
        self.reinstall = False
        self.zip_sha256 = ""            # the whole download's digest, for the person to compare with the releases page


def _manifest_of(zf, infos, system):
    """The parsed clark-release.json and the top folder, or the source-zip refusal when there is none."""
    first = infos[0].filename.split("/")[0] if infos else ""
    entry = f"{first}/{MANIFEST}"
    found = [i for i in infos if i.filename == entry]
    if not found:
        raise UpdateError("source", "no clark-release.json", ours=system)
    info = found[0]
    if info.file_size > MAX_MANIFEST_BYTES:
        raise UpdateError("damaged", "clark-release.json is too big")
    try:
        data = zf.read(info)
        doc = json.loads(data.decode("utf-8"), parse_int=parse_int)
    except (ValueError, zipfile.BadZipFile, OSError, RuntimeError):
        raise UpdateError("damaged", "clark-release.json can't be read")
    return doc, first


def _check_manifest_shape(doc, system):
    if not isinstance(doc, dict) or doc.get("product") != "clark":
        raise UpdateError("name", "the manifest is not clark's", ours=system)
    for key, kind in (("version", str), ("system", str), ("released", str), ("notes", str), ("schema_version", int),
                      ("min_from", str), ("files", dict)):
        if not isinstance(doc.get(key), kind) or (kind is int and isinstance(doc.get(key), bool)):
            raise UpdateError("damaged", f"manifest field {key} is missing or the wrong kind")
    if not is_release_version(doc["version"]) or not is_release_version(doc["min_from"]):
        raise UpdateError("damaged", "manifest version is not X.Y.Z")
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", doc["released"]):
        raise UpdateError("damaged", "manifest date is not YYYY-MM-DD")
    for rel, row in doc["files"].items():
        if not isinstance(row, dict) or not isinstance(rel, str) or not isinstance(row.get("sha256"), str) \
                or not re.fullmatch(r"[0-9a-f]{64}", row["sha256"]) or not isinstance(row.get("size"), int) \
                or isinstance(row.get("size"), bool) or row["size"] < 0 or row.get("mode") not in ("644", "755"):
            raise UpdateError("damaged", f"manifest row for {rel!r} is malformed")


def _check_structure(infos, max_total):
    names = [i.filename for i in infos]
    if len(set(names)) != len(names):
        raise UpdateError("damaged", "duplicate member names: " + names_for_log(sorted({n for n in names if names.count(n) > 1})))
    total = 0
    for i in infos:
        if i.filename.endswith("/"):
            raise UpdateError("damaged", f"folder entry {i.filename}")
        if i.flag_bits & 0x1:
            raise UpdateError("damaged", f"encrypted member {i.filename}")
        if i.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
            raise UpdateError("damaged", f"odd compression for {i.filename}")
        if i.create_system != 3:
            raise UpdateError("damaged", f"not made on Unix: {i.filename}")
        mode = i.external_attr >> 16
        if stat.S_ISLNK(mode):
            raise UpdateError("unsafe", f"link member {i.filename}")
        if not stat.S_ISREG(mode) or stat.S_IMODE(mode) not in (0o644, 0o755):
            raise UpdateError("damaged", f"mode {oct(mode)} for {i.filename}")
        total += i.file_size
    if total > max_total:
        raise UpdateError("damaged", f"declared size {total} is over the cap")


def file_digest(path, size):
    """The SHA-256 of the whole file at `path`, read in chunks and counted against `size` (a file that grows while it is
    read is refused)."""
    h, got = hashlib.sha256(), 0
    try:
        with open(path, "rb") as f:
            while True:
                chunk = f.read(CHUNK)
                if not chunk:
                    break
                got += len(chunk)
                if got > size:
                    raise UpdateError("damaged", "the file grew while it was being read")
                h.update(chunk)
    except OSError:
        raise UpdateError("unreadable", "the file can't be read")
    return h.hexdigest()


def _read_counted(zf, info):
    """The bytes of one member, read in chunks and counted against its declared size (a bomb can't grow past it)."""
    out, got = [], 0
    try:
        member = zf.open                        # an archive member, read as bytes
        with member(info) as f:
            while True:
                chunk = f.read(CHUNK)
                if not chunk:
                    break
                got += len(chunk)
                if got > info.file_size:
                    raise UpdateError("damaged", f"{info.filename} is bigger than it says")
                out.append(chunk)
    except (zipfile.BadZipFile, OSError, RuntimeError, EOFError, ValueError):
        raise UpdateError("damaged", f"{info.filename} can't be read")
    return b"".join(out)


def check_coverage(system, rels):
    """Unsafe: anything outside release_files' list. Incomplete: anything the list needs that is missing."""
    extra = sorted(r for r in rels if not release_files.covers(system, r))
    if extra:
        raise UpdateError("unsafe", "outside the app's own list: " + names_for_log(extra))
    present = set(rels)
    missing = []
    for item in release_files.listed(system) + (release_files.START_HERE,):
        if item.endswith("/"):
            if not any(r.startswith(item) for r in present):
                missing.append(item)
        elif item not in present:
            missing.append(item)
    if missing:
        raise UpdateError("incomplete", "missing: " + names_for_log(missing))


def read_release(path, system, installed_version, installed_schema, reinstall=False, chosen=False,
                 max_zip=MAX_ZIP_BYTES, max_total=MAX_TOTAL_BYTES):
    """Check the update file at `path` and return a Release, or raise UpdateError. Writes nothing."""
    path = Path(path)
    version_in_name = check_name(path.name, system, chosen)
    try:
        st = os.lstat(path)
    except OSError:
        raise UpdateError("unreadable", "the file can't be found")
    if not stat.S_ISREG(st.st_mode):
        raise UpdateError("unreadable", "not a regular file (a link or folder)")
    if st.st_size > max_zip:
        raise UpdateError("damaged", f"file is {st.st_size} bytes, over the cap")
    digest = file_digest(path, st.st_size)
    try:
        zf = zipfile.ZipFile(path)
    except (zipfile.BadZipFile, OSError):
        raise UpdateError("damaged", "not a zip file")
    with zf:
        infos = zf.infolist()
        doc, top = _manifest_of(zf, infos, system)
        _check_manifest_shape(doc, system)
        if doc["system"] != system:
            raise UpdateError("system", f"the manifest says {doc['system']}", theirs=SYSTEM_NAMES.get(doc["system"], doc["system"]),
                              ours=SYSTEM_NAMES.get(system, system))
        _check_structure(infos, max_total)
        if not TOP_RE.match(top) or top != f"clark-{doc['version']}" or doc["version"] != version_in_name:
            raise UpdateError("damaged", f"top folder {top!r}, manifest {doc['version']}, name {version_in_name}")
        members = {}
        for i in infos:
            head, _, rel = i.filename.partition("/")
            if head != top:
                raise UpdateError("unsafe", f"member outside the one top folder: {i.filename}")
            problem = path_problem(rel)
            if problem:
                raise UpdateError("unsafe", f"{problem}: {i.filename}")
            members[rel] = i
        clash = collisions(list(members))
        if clash:
            raise UpdateError("unsafe", "names that clash on a Mac or Windows disk: " + names_for_log(clash))
        rels = [r for r in members if r != MANIFEST]
        check_coverage(system, rels)
        listed = set(doc["files"])
        if listed != set(rels):
            odd = sorted(listed ^ set(rels))
            raise UpdateError("incomplete", "manifest and members differ: " + names_for_log(odd))
        bad_names = [r for r in doc["files"] if path_problem(r)]
        if bad_names:
            raise UpdateError("unsafe", "manifest names: " + names_for_log(bad_names))
        init_text = None
        for rel in sorted(rels):
            row, info = doc["files"][rel], members[rel]
            if info.file_size != row["size"]:
                raise UpdateError("damaged", f"size of {rel} differs from the manifest")
            if format(stat.S_IMODE(info.external_attr >> 16), "o") != row["mode"]:
                raise UpdateError("damaged", f"mode of {rel} differs from the manifest")
            data = _read_counted(zf, info)
            if len(data) != row["size"] or hashlib.sha256(data).hexdigest() != row["sha256"]:
                raise UpdateError("damaged", f"hash of {rel} differs from the manifest")
            if rel == "src/clark/__init__.py":
                init_text = data.decode("utf-8", "replace")
    found = re.search(r'^__version__ = "([^"]+)"', init_text or "", re.M)
    if not found or found.group(1) != doc["version"]:
        raise UpdateError("damaged", "the version inside the files differs from the manifest")
    release = Release(path, doc, top)
    release.zip_sha256 = digest
    check_version(release, installed_version, installed_schema, reinstall)
    release.reinstall = reinstall
    return release


def check_version(release, installed_version, installed_schema, reinstall=False):
    """The version rule, `min_from`, and the data layout rule. Raises UpdateError."""
    try:
        have = version_key(installed_version)
    except ValueError:
        raise UpdateError("installed", f"installed version {installed_version!r} is not a version")
    new = version_key(release.version)
    if new <= have and not reinstall:
        raise UpdateError("same" if new == have else "older", f"{release.version} against {installed_version}",
                          theirs=release.version, ours=installed_version)
    if have < version_key(release.min_from):
        raise UpdateError("min_from", f"min_from {release.min_from}, installed {installed_version}", need=release.min_from)
    if release.schema_version != installed_schema:
        raise UpdateError("layout", f"data layout {release.schema_version}, installed {installed_schema}")


# --- the installed folder ---------------------------------------------------------------------------------------------

def _is_link(path):
    try:
        st = os.lstat(path)
    except OSError:
        return False
    return stat.S_ISLNK(st.st_mode) or bool(getattr(st, "st_file_attributes", 0) & FILE_ATTRIBUTE_REPARSE_POINT)


def walk_app(app_dir):
    """Every file under the app folder as a "/" name, never following a link; links are returned apart."""
    files, links = [], []
    base = Path(app_dir)
    stack = [base]
    while stack:
        folder = stack.pop()
        with os.scandir(folder) as it:
            for e in it:
                rel = PurePosixPath(Path(e.path).relative_to(base)).as_posix()
                if _is_link(e.path):
                    links.append(rel)
                elif e.is_dir(follow_symlinks=False):
                    if e.name == "__pycache__" or e.name.startswith((".clark-update-", ".clark-old-")):
                        continue
                    stack.append(Path(e.path))
                elif e.name != ".DS_Store" and not e.name.endswith(".pyc"):
                    files.append(rel)
    return sorted(files), sorted(links)


def check_app_folder(app_dir):
    """Refuse a folder that can't be updated in place, before anything else is looked at."""
    app = Path(app_dir)
    if os.path.lexists(app / ".git"):
        raise UpdateError("git", ".git is in the app folder")
    if not (app / INSTALLED_RECORD).is_file():
        raise UpdateError("norecord", "no clark-release.json in the app folder")
    check_record_names(readable_record(app))
    _, links = walk_app(app)
    if links:
        raise UpdateError("link", "links in the app folder: " + names_for_log(links))
    probe = app / f".clark-write-test-{os.getpid()}"
    try:
        probe.write_bytes(b"")
        probe.unlink()
    except OSError:
        raise UpdateError("readonly", "the app folder can't be written to")


def installed_record(app_dir):
    """The manifest of the installed release (its `files` are what the last install put there), or None."""
    try:
        doc = json.loads((Path(app_dir) / INSTALLED_RECORD).read_text(encoding="utf-8"), parse_int=parse_int)
    except (OSError, ValueError):
        return None
    return doc if isinstance(doc, dict) and isinstance(doc.get("files"), dict) else None


def readable_record(app_dir):
    """The installed record, or the no-record refusal when it is there but isn't a record (not JSON, or no list of files)."""
    record = installed_record(app_dir)
    if record is None:
        raise UpdateError("norecord", "the app folder's clark-release.json can't be read as a record")
    return record


def check_record_names(record):
    """Every name in the installed record must be a safe relative name: it comes from a file on disk that anyone could have
    changed, and plan() joins it to the app folder."""
    bad = [str(r) for r in record["files"] if not isinstance(r, str) or path_problem(r)]
    if bad:
        raise UpdateError("unsafe", "unsafe names in the installed record: " + names_for_log(bad))


def _sha256_of(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


class Plan:
    def __init__(self):
        self.added, self.replaced, self.removed, self.left, self.by_hand = [], [], [], [], []


def plan(release, app_dir):
    """What installing `release` over `app_dir` would do. Reads only.

    added: in the update, not on disk. replaced: on disk with different bytes. removed: on disk, recorded by the last install
    as shipped, and not in the update (before the first recorded install nothing is removed). left: on disk, not in the
    update and not recorded, so the person's own and never touched. by_hand: recorded files whose bytes differ from the
    record (they are replaced anyway and kept in the backup)."""
    app = Path(app_dir)
    record = readable_record(app)
    check_record_names(record)
    recorded = record["files"]
    on_disk, _ = walk_app(app)
    present = set(on_disk)
    result = Plan()
    for rel, row in sorted(release.files.items()):
        if rel not in present:
            result.added.append(rel)
        elif _sha256_of(app / rel) != row["sha256"]:
            result.replaced.append(rel)
    result.removed = sorted(r for r in recorded if r not in release.files and r in present)
    result.left = sorted(r for r in present if r not in release.files and r not in recorded and r != INSTALLED_RECORD)
    result.by_hand = sorted(r for r, row in recorded.items() if r in present and _sha256_of(app / r) != row.get("sha256"))
    return result


# --- the review the page shows ----------------------------------------------------------------------------------------

def date_text(iso):
    year, month, day = iso.split("-")
    return f"{day}-{month}-{year}"


def count_text(label, items):
    return f"{label} ({len(items)} file{'' if len(items) == 1 else 's'})"


def review(release, plan_, installed_version):
    """The review as plain text for the page. Install is a second click, so nothing here changes anything."""
    return {
        "from": installed_version,
        "to": release.version,
        "heading": f"Version {installed_version} → {release.version}. Released {date_text(release.released)}.",
        "notes": release.notes,
        "notes_text": release.notes if release.notes.strip() else NO_NOTES,
        "replaced": {"label": count_text("Replaced", plan_.replaced), "names": list(plan_.replaced)},
        "added": {"label": count_text("Added", plan_.added), "names": list(plan_.added)},
        "removed": {"label": count_text("Removed", plan_.removed), "names": list(plan_.removed)},
        "by_hand": (f"{len(plan_.by_hand)} file{' in the clark folder was' if len(plan_.by_hand) == 1 else 's in the clark folder were'}"
                    " changed by hand and will be replaced. A copy is kept in the backup.") if plan_.by_hand else None,
        "checksum": release.zip_sha256,
        "checksum_text": f"Checksum of this file: {release.zip_sha256}. Compare it with the one on the releases page.",
        "kept": KEPT,
        "reinstall": release.reinstall,
    }


# --- finding the file -------------------------------------------------------------------------------------------------

def newest_in(folder, system):
    """The newest update file for `system` in `folder`, by version, from file names only; None if there is none.

    Only exact names (clark-X.Y.Z-mac.zip) that are regular files are looked at, and no file is opened."""
    best = None
    try:
        entries = list(os.scandir(folder))
    except OSError:
        return None
    for e in entries:
        found = NAME_RE.match(e.name)
        if not found or found.group(4) != system:
            continue
        try:
            if not e.is_file(follow_symlinks=False):
                continue
        except OSError:
            continue
        key = tuple(int(n) for n in found.group(1, 2, 3))
        if best is None or key > best[0]:
            best = (key, Path(e.path))
    return best[1] if best else None
