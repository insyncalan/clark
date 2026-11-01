"""The server's side of an update, before the helper takes over: take the file in, back up, stage, check, hand over, undo.

updates.py only reads; update_helper.py swaps the files once the server has stopped. This module holds what comes between, in
the order the server runs it, and every step here leaves the app folder as it was if it fails (it writes only into clark's own
folders: the data folder's `releases/` and `updates/`, and one hidden staging folder inside the app folder, removed again on a
failure):

  take_in(source, data_dir)        copies the chosen or downloaded file ONCE into `<data>/releases/`, hashing it as it is read,
                                   from a file opened without following a link. Every later look (the checks, the checksum the
                                   page shows, the staging) is at that copy, which only clark writes, so the bytes that were
                                   checked are the bytes that are installed.
  back_up(...)                     the backup set, `<data>/updates/<stamp>-<from>-to-<to>/`: the whole app folder as it is
                                   (`app/`), settings.json, the database through store.snapshot (one moment, checked) and
                                   update.json, the record of what was backed up. Written under a `.part` name and renamed when
                                   whole, so a half-made set is never taken for a backup.
  stage(release, app_dir, stamp)   writes the new files into `<app>/.clark-update-<stamp>/`, checking each one's hash as it is
                                   written, with the record (clark-release.json) last.
  first_check(staging)             every module of the staged copy imports, in a fresh interpreter (platform.run_python_check).
  hand_over(...)                   writes the helper's marker (update_helper.begin) and starts the helper; the server then
                                   closes and exits, and the helper does the swap, checks again, starts the new version, and
                                   puts the old one back by itself on any failure.
  last_update / undo_choice        the newest update that is not undone, and whether a full undo is still safe: only if the
                                   data has not changed since (db_id, last step and row counts against the record). Otherwise
                                   only the app and settings may be put back.
  stage_undo(...)                  stages the backed-up app folder, checked against its own record, for the same helper.
  prune(data_dir)                  keeps the last KEEP update sets and release files (never the installed one), by exact name.

Standard library only, Python 3.9. A sentence a person reads never starts with the product name and holds no file path, nor
the words zip, manifest or SHA.
"""
import hashlib
import io
import json
import os
import re
import shutil
import stat
import sys
import time
import zipfile
from pathlib import Path

from clark import backup, platform, settings, store, update_helper, updates

RELEASES = "releases"
UPDATES = update_helper.UPDATES
RECORD = "update.json"
APP = "app"
DB_COPY = "clark.db"
KEEP = 3
SET_RE = re.compile(r"([0-9]{8}T[0-9]{6}Z)-([0-9]+\.[0-9]+\.[0-9]+)-to-([0-9]+\.[0-9]+\.[0-9]+)\Z")
RELEASE_RE = re.compile(r"clark-([0-9]+)\.([0-9]+)\.([0-9]+)-(mac|windows|linux)\.zip\Z")
SPACE_MARGIN = 50 * 1024 * 1024
STAMP_RE = re.compile(r"[0-9]{8}T[0-9]{6}Z\Z")
READY_SECONDS = 10

MESSAGES = {
    "space": "There isn't enough room on this disk to update safely. Free up some space, then try again. Nothing was changed.",
    "backup": "A copy of your data couldn't be made, so the update wasn't installed. Nothing was changed. "
              "Check the disk has space, then try again.",
    "staging": "The new version couldn't be put in place for checking, so the update wasn't installed. Nothing was changed. "
               "Download it again, then try again.",
    "first_check": "The new version didn't pass its check, so the update wasn't installed. Nothing was changed. "
                   "Download it again, then try again.",
    "helper": "The update couldn't start, so nothing was changed. Close every clark window, open clark again and try again.",
    "no_update": "There is no update to undo.",
    "undone": "That update has been undone already.",
    "data_changed": "Your data has changed since the update, and putting back the old data would lose those changes. "
                    "Choose Put back the app and settings only to keep your data as it is.",
    "data_gone": backup.UPDATE_GONE,
    "data_restore": "Your data could not be put back, so it was left as it is. Close every clark window, open clark again and "
                    "try again.",
    "backup_damaged": "The copy kept from before the update doesn't match its record, so it can't be put back. Nothing was "
                      "changed. Download the version you want and replace the clark folder by hand.",
}


class InstallError(Exception):
    """A step before the hand-over failed. `key` picks the sentence; `detail` is for the log only."""

    def __init__(self, key, detail=""):
        self.key = key
        self.message = MESSAGES[key]
        self.detail = detail
        super().__init__(self.message)


def parse_int(text):
    """json's reader for whole numbers in clark's own records, refusing a very long one (as updates.py does for a release's)."""
    if len(text.lstrip("-")) > updates.MAX_INT_DIGITS:
        raise ValueError("number too long")
    return int(text)


def stamp_now(now=None):
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime(now))


# --- taking the file in -----------------------------------------------------------------------------------------------

def take_in(source, data_dir, system, chosen=False, max_bytes=updates.MAX_ZIP_BYTES):
    """Copy the update file at `source` once into `<data>/releases/<its proper name>` and return (that path, its SHA-256).
    The signature file beside it (`source` + .sig) is copied too, so everything after works from the private copy; a missing
    one is not an error here (updates.read_release refuses an unsigned copy).

    The name is checked first (updates.check_name). The file is opened without following a link, must be a regular file no
    bigger than `max_bytes`, and is read once, in chunks, into a new private file in the releases folder; nothing else of the
    original is looked at again. A copy already there under the same name is replaced only when the new one is whole."""
    source = Path(source)
    version = updates.check_name(source.name, system, chosen)
    folder = platform.private_folder(Path(data_dir) / RELEASES)
    name = f"clark-{version}-{system}.zip"
    part = folder / f".{name}.{os.getpid()}.part"
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
    try:
        fd = os.open(str(source), flags)
    except OSError:
        raise updates.UpdateError("unreadable", "the file can't be opened (missing, or a link)")
    h, got = hashlib.sha256(), 0
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            raise updates.UpdateError("unreadable", "not a regular file")
        if st.st_size > max_bytes:
            raise updates.UpdateError("damaged", f"file is {st.st_size} bytes, over the cap")
        part.unlink(missing_ok=True)
        platform.private_file(part)
        with os.fdopen(fd, "rb", closefd=True) as src, open(part, "wb") as out:
            fd = None
            while True:
                chunk = src.read(updates.CHUNK)
                if not chunk:
                    break
                got += len(chunk)
                if got > max_bytes:
                    raise updates.UpdateError("damaged", "the file grew past the cap while it was read")
                h.update(chunk)
                out.write(chunk)
            out.flush()
            os.fsync(out.fileno())
        (folder / (name + updates.SIGNATURE_SUFFIX)).unlink(missing_ok=True)       # never a signature left from another file
        os.replace(part, folder / name)
        signature = updates.read_signature(source)
        if signature is not None:
            sig_part = folder / f".{name}{updates.SIGNATURE_SUFFIX}.{os.getpid()}.part"
            platform.private_file(sig_part)
            sig_part.write_bytes(signature)
            os.replace(sig_part, folder / (name + updates.SIGNATURE_SUFFIX))
    except OSError:
        raise updates.UpdateError("unreadable", "the file can't be read")
    finally:
        if fd is not None:
            os.close(fd)
        part.unlink(missing_ok=True)
    return folder / name, h.hexdigest()


def read_taken(path, digest, system, installed_version, installed_schema, reinstall=False, public_key=None):
    """updates.read_release on the copy take_in made (signature first), refusing it if the copy is not the bytes take_in hashed."""
    release = updates.read_release(path, system, installed_version, installed_schema, reinstall=reinstall,
                                   public_key=public_key)
    if release.zip_sha256 != digest:
        raise updates.UpdateError("damaged", "the kept copy changed after it was taken in")
    return release


# --- the backup set ---------------------------------------------------------------------------------------------------

def set_name(stamp, from_version, to_version):
    return f"{stamp}-{from_version}-to-{to_version}"


def _copy_file(source, dest):
    """Copy one file, hashing what was read; its SHA-256."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    h = hashlib.sha256()
    with open(source, "rb") as src, open(dest, "wb") as out:
        for chunk in iter(lambda: src.read(updates.CHUNK), b""):
            h.update(chunk)
            out.write(chunk)
    shutil.copymode(source, dest)
    return h.hexdigest()


def space_needed(app_dir, db_path, release=None):
    """Bytes an update needs free: the old app (backup), the new app (staging) and the database copy, twice, plus a margin."""
    files, _ = updates.walk_app(app_dir)
    old = sum(os.path.getsize(Path(app_dir) / r) for r in files)
    new = sum(row["size"] for row in release.files.values()) if release else old
    db = os.path.getsize(db_path) if Path(db_path).is_file() else 0
    return 2 * (old + new + db) + SPACE_MARGIN


def back_up(app_dir, data_dir, db_path, stamp, from_version, to_version, plan_=None, kind="install", free=None, fault=None):
    """Make the backup set and return its folder. Raises InstallError ("space" or "backup") and leaves nothing behind."""
    app, data = Path(app_dir), Path(data_dir)
    root = platform.private_folder(data / UPDATES)
    need = space_needed(app, db_path)
    have = (free or (lambda p: shutil.disk_usage(str(p)).free))(root)
    if have < need:
        raise InstallError("space", f"{need} bytes needed, {have} free")
    final = root / set_name(stamp, from_version, to_version)
    part = root / (final.name + ".part")
    if os.path.lexists(final) or os.path.lexists(part):
        raise InstallError("backup", "a backup set of that name is there already")
    try:
        part.mkdir()
        platform.private_folder(part)
        files, links = updates.walk_app(app)
        if links:
            raise InstallError("backup", "links in the app folder")
        if fault:
            fault("back_up:app")
        hashes = {rel: _copy_file(app / rel, part / APP / rel) for rel in files}
        if fault:
            fault("back_up:settings")
        settings_file = data / settings.FILE
        had_settings = settings_file.is_file() and not settings_file.is_symlink()
        if had_settings:
            _copy_file(settings_file, part / settings.FILE)
        if fault:
            fault("back_up:database")
        db_before = None
        if Path(db_path).is_file():
            platform.private_file(part / DB_COPY)
            store.snapshot(db_path, part / DB_COPY)
            db_before = store.check_copy(part / DB_COPY)
        record = {"kind": kind, "from": from_version, "to": to_version, "stamp": stamp, "system": platform.system(),
                  "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "app_dir": platform.with_tilde(app),
                  "app_files": hashes, "settings": had_settings, "db_before": db_before, "db_after": None,
                  "planned": ({"added": plan_.added, "replaced": plan_.replaced, "removed": plan_.removed,
                               "by_hand": plan_.by_hand} if plan_ else None),
                  "installed": False, "undone": False}
        if fault:
            fault("back_up:record")
        update_helper.write_json(part / RECORD, record)
        os.rename(part, final)
    except InstallError:
        shutil.rmtree(part, ignore_errors=True)
        raise
    except Exception as e:                       # the system's own words go to the log, never the screen
        shutil.rmtree(part, ignore_errors=True)
        raise InstallError("backup", f"{type(e).__name__}: {e}")
    return final


def read_set(folder):
    try:
        doc = json.loads((Path(folder) / RECORD).read_text(encoding="utf-8"), parse_int=parse_int)
    except (OSError, ValueError):
        return None
    return doc if isinstance(doc, dict) else None


def sets(data_dir):
    """The finished backup sets, oldest first: [(folder, record)]. Only exact names; a `.part` is never one."""
    root = Path(data_dir) / UPDATES
    out = []
    try:
        entries = sorted(os.scandir(root), key=lambda e: e.name)
    except OSError:
        return out
    for e in entries:
        if SET_RE.match(e.name) and e.is_dir(follow_symlinks=False):
            record = read_set(e.path)
            if record is not None:
                out.append((Path(e.path), record))
    return out


def note_installed(backup_dir, db_path, migration_backup=None):
    """After the new version answers: the update went in, and the data as it stands (db_after), which Undo compares with later.
    When the update brought the data up to a newer layout (the set's own copy of the database was at an older one), the safety
    copy that migration took is recorded too, as record["migration"]: the old version cannot open the newer data, so the undo
    puts that copy back. `migration_backup` is the copy this start took, else the newest `migrate` copy in the backups folder."""
    record = read_set(backup_dir)
    if record is None:
        return
    before = (record.get("db_before") or {}).get("schema_version")
    if isinstance(before, int) and before < store.SCHEMA_VERSION:
        name = Path(migration_backup).name if migration_backup else None
        if name is None:
            found = [e for e in backup.entries(Path(db_path).parent / "backups") if e.tag == "migrate"]
            name = Path(found[-1].path).name if found else None
        record["migration"] = {"backup": name, "from": before, "to": store.SCHEMA_VERSION}
    record["db_after"] = summary_of(db_path)
    record["installed"] = True
    update_helper.write_json(Path(backup_dir) / RECORD, record)


def summary_of(db_path):
    """db_id, last step and row counts of the live database, as store.check_copy gives them (None if there is none)."""
    if not Path(db_path).is_file():
        return None
    found = store.check_copy(db_path)
    return {k: found[k] for k in ("db_id", "last_step", "rows")}


# --- staging and the first check --------------------------------------------------------------------------------------

def staging_dir(app_dir, stamp):
    return Path(app_dir) / (update_helper.STAGING_PREFIX + stamp)


def stage(release, app_dir, stamp, fault=None):
    """Write the release's files into the staging folder from the kept copy, checking each hash, and the record last. The
    staging folder's path. Raises InstallError("staging") and removes the folder on any failure."""
    if not STAMP_RE.match(stamp):
        raise InstallError("staging", "bad stamp")
    folder = staging_dir(app_dir, stamp)
    try:
        if not release.data:
            raise InstallError("staging", "no checked bytes to stage from")          # never the file on disk again
        folder.mkdir()
        with zipfile.ZipFile(io.BytesIO(release.data)) as zf:      # the bytes that were signed and checked
            infos = {i.filename: i for i in zf.infolist()}
            for rel in sorted(release.files):
                row = release.files[rel]
                if updates.path_problem(rel):
                    raise InstallError("staging", f"unsafe name {rel!r}")
                dest = folder.joinpath(*rel.split("/"))
                if folder.resolve() not in dest.resolve().parents:
                    raise InstallError("staging", f"{rel!r} is outside the staging folder")
                if fault:
                    fault("stage:" + rel)
                data = updates._read_counted(zf, infos[f"{release.top}/{rel}"])
                if hashlib.sha256(data).hexdigest() != row["sha256"] or len(data) != row["size"]:
                    raise InstallError("staging", f"hash of {rel} differs while staging")
                dest.parent.mkdir(parents=True, exist_ok=True)
                with open(dest, "xb") as out:
                    out.write(data)
                os.chmod(dest, int(row["mode"], 8))
            record = updates._read_counted(zf, infos[f"{release.top}/{updates.MANIFEST}"])
        with open(folder / updates.MANIFEST, "xb") as out:
            out.write(record)
        os.chmod(folder / updates.MANIFEST, 0o644)
    except InstallError:
        shutil.rmtree(folder, ignore_errors=True)
        raise
    except Exception as e:
        shutil.rmtree(folder, ignore_errors=True)
        raise InstallError("staging", f"{type(e).__name__}: {e}")
    return folder


IMPORT_ALL = ("import importlib, pkgutil, sys\n"
              "src, vendor = sys.argv[1], sys.argv[2]\n"
              "sys.path[:0] = [src, vendor]\n"
              "import clark\n"
              "for m in pkgutil.iter_modules(clark.__path__):\n"
              "    importlib.import_module('clark.' + m.name)\n")


def first_check(staging, python=None, run=None):
    """Every module of the staged copy imports in a fresh interpreter. Raises InstallError("first_check")."""
    staging = Path(staging)
    try:
        status, errors = platform.run_python_check(python or sys.executable, IMPORT_ALL, [staging / "src", staging / "vendor"],
                                                   run=run)
    except Exception as e:
        raise InstallError("first_check", f"{type(e).__name__}: {e}")
    if status != 0:
        raise InstallError("first_check", "a module does not import: " + errors[-300:])


def remove_staging(app_dir, stamp):
    """Take a staging folder away after a step before the hand-over failed (clark's own hidden folder, nothing else)."""
    folder = staging_dir(app_dir, stamp)
    if folder.is_dir() and not folder.is_symlink():
        shutil.rmtree(folder, ignore_errors=True)


# --- the hand-over ----------------------------------------------------------------------------------------------------

def hand_over(data_dir, app_dir, staging, stamp, from_version, to_version, installed_schema, server_pid, port, mark_header,
              mark, backup_dir, python=None, start=None, sleep=time.sleep, clock=time.monotonic, wait=READY_SECONDS):
    """Write the marker and start the helper; return once it says it is ready, so the server may close and exit.

    If the helper does not say so in `wait` seconds, the marker and the staging folder are taken away (nothing in the app
    folder has changed) and InstallError("helper") is raised; a helper that starts after that finds no marker and stops."""
    marker = update_helper.begin(data_dir, app_dir, staging, stamp, from_version, to_version, installed_schema, server_pid,
                                 port, mark_header, mark, backup_dir=str(backup_dir))
    helper_dir = Path(json.loads(marker.read_text(encoding="utf-8"))["helper_dir"])
    argv = [str(python or sys.executable), "-I", "-B", str(helper_dir / "update_helper.py"), "--marker", str(marker)]
    try:
        (start or platform.start_detached)(argv, dict(os.environ), Path(data_dir) / UPDATES / update_helper.LOG_NAME,
                                           cwd=str(helper_dir))
        end = clock() + wait
        while clock() < end:
            try:
                if json.loads(marker.read_text(encoding="utf-8")).get("phase") != "staged":
                    return marker
            except (OSError, ValueError):
                pass
            sleep(0.1)
        raise InstallError("helper", "the helper did not say it was ready")
    except Exception as e:
        marker.unlink(missing_ok=True)
        remove_staging(app_dir, stamp)
        if isinstance(e, InstallError):
            raise
        raise InstallError("helper", f"{type(e).__name__}: {e}")


# --- undo -------------------------------------------------------------------------------------------------------------

def last_update(data_dir):
    """The newest backup set of an update (not an undo) that went in: (folder, record), or None. A set whose update stopped
    before it was installed (the old version was kept) is not one, unless the helper left the data in the newer layout and
    recorded that putting it back is waiting (#280, record["data_restore_pending"]): the Undo update that puts it back is offered."""
    found = [(f, r) for f, r in sets(data_dir)
             if r.get("kind") == "install" and (r.get("installed") is True or isinstance(r.get("data_restore_pending"), dict))]
    return found[-1] if found else None


def undo_choice(data_dir, db_path):
    """"full" when the data is as the update left it, "app_only" when it changed since. Raises InstallError otherwise."""
    found = last_update(data_dir)
    if found is None:
        raise InstallError("no_update", "no backup set")
    folder, record = found
    if record.get("undone"):
        raise InstallError("undone", folder.name)
    if migration_of(record):
        return "full"            # put back whole from the copy taken before the migration: the old version cannot open the newer data
    now = summary_of(db_path)
    after = record.get("db_after")
    return "full" if after is not None and now == after else "app_only"


def migration_of(record):
    """The migration an update's set recorded, {"backup", "from", "to"}, or None when it kept the data layout."""
    found = record.get("migration")
    return found if isinstance(found, dict) else None


def check_restore(db_path, record):
    """Before an undo starts: if the update migrated the data, its copy must be there and be a copy taken before an update
    (backup.restore_before_update, not yet confirmed, changes nothing). InstallError("data_gone") otherwise; no migration: nothing."""
    found = migration_of(record)
    if found is None:
        return
    try:
        backup.restore_before_update(db_path, found.get("backup"))
    except store.Invalid as e:
        if str(e) != backup.UPDATE_ASK:        # asked to confirm: the copy is there; anything else is a refusal
            raise InstallError("data_gone", str(e))


def put_back_newer_data(db_path, since):
    """After restore_data, if the hand-over then failed: put the newer database back, from the `restore` copy restore_data took of
    it (one made since `since`, a time.time() value taken before restore_data; never an older one), so the person's latest
    changes are where they were and the next start finds the data the running version expects. Best effort; True if it was put back. The running version's own store stays closed, which the hand-over's message already tells the
    person to deal with: close clark and open it again."""
    folder = Path(db_path).parent / "backups"
    try:
        found = [e for e in backup.entries(folder) if e.tag == "restore" and e.mtime_ns / 1e9 >= since - 2]
        if not found:
            return False
        backup.restore_path(db_path, Path(found[-1].path).name, folder)
        return True
    except (store.Invalid, OSError):
        return False


def restore_data(db_path, record, open_db=None):
    """The undo of a migrated update: put the copy taken before the migration back over the database, replacing it (the newer
    file is kept whole in the backups folder). Nothing when the update kept the data layout. InstallError("data_restore")
    when it could not be done, and the database is then as it was."""
    found = migration_of(record)
    if found is None:
        return
    try:
        backup.restore_before_update(db_path, found.get("backup"), confirmed=True, store=open_db)
    except store.Invalid as e:
        raise InstallError("data_restore", str(e))


def stage_undo(backup_dir, app_dir, stamp):
    """Copy the backed-up app folder's shipped files into a staging folder, each checked against the backup's own record and
    against the old release record kept in it. The staging folder's path. InstallError("backup_damaged") on any mismatch."""
    backup_dir = Path(backup_dir)
    record = read_set(backup_dir)
    old_release = updates.installed_record(backup_dir / APP)
    if record is None or old_release is None:
        raise InstallError("backup_damaged", "no record in the backup set")
    try:
        updates.check_record_names(old_release)
    except updates.UpdateError:
        raise InstallError("backup_damaged", "unsafe names in the kept record")
    folder = staging_dir(app_dir, stamp)
    try:
        folder.mkdir()
        for rel, row in sorted(old_release["files"].items()):
            source = backup_dir / APP / rel
            if record["app_files"].get(rel) != row.get("sha256") or not source.is_file() or source.is_symlink():
                raise InstallError("backup_damaged", f"{rel} is not as recorded")
            digest = _copy_file(source, folder / rel)
            if digest != row["sha256"]:
                raise InstallError("backup_damaged", f"{rel} changed while it was copied")
            os.chmod(folder / rel, int(row.get("mode", "644"), 8))
        _copy_file(backup_dir / APP / updates.MANIFEST, folder / updates.MANIFEST)
    except InstallError:
        shutil.rmtree(folder, ignore_errors=True)
        raise
    except Exception as e:
        shutil.rmtree(folder, ignore_errors=True)
        raise InstallError("backup_damaged", f"{type(e).__name__}: {e}")
    return folder


def put_back_settings(backup_dir, data_dir):
    """settings.json as it was before the update (written whole, through platform.write_file)."""
    kept = Path(backup_dir) / settings.FILE
    if kept.is_file() and not kept.is_symlink():
        platform.write_file(Path(data_dir) / settings.FILE, kept.read_bytes())


def mark_undone(backup_dir):
    record = read_set(backup_dir)
    if record is not None:
        record["undone"] = True
        update_helper.write_json(Path(backup_dir) / RECORD, record)


# --- keeping the last few ---------------------------------------------------------------------------------------------

def prune(data_dir, installed_version, system, keep=KEEP):
    """Keep the newest `keep` backup sets and release files; never the installed release, never while an update is
    unfinished (a marker is there). Only names this module makes are looked at. The names taken away."""
    data = Path(data_dir)
    if update_helper.marker_path(data).exists():
        return []
    gone = []
    for folder, _ in sets(data)[:-keep] if keep > 0 else []:
        shutil.rmtree(folder, ignore_errors=True)
        gone.append(folder.name)
    releases = []
    try:
        entries = list(os.scandir(data / RELEASES))
    except OSError:
        entries = []
    for e in entries:
        found = RELEASE_RE.match(e.name)
        if found and found.group(4) == system and e.is_file(follow_symlinks=False):
            releases.append((tuple(int(n) for n in found.group(1, 2, 3)), e))
    releases.sort(key=lambda pair: pair[0])
    installed = f"clark-{installed_version}-{system}.zip"
    for _, e in releases[:-keep] if keep > 0 else []:
        if e.name != installed:
            os.unlink(e.path)
            gone.append(e.name)
    return gone
