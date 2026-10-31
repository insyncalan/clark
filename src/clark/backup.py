"""Backups of clark.db (#86). Guarded with store.py: a cut-down copy of creaite's `backup_db` (tracker.py v2.6.9, db5adb2) and

This module never imports sqlite3 and holds no SQL: the copy, its checks and the "is another program using it?" probe are
`store.snapshot`, `store.check_copy`, `store.identity` and `store.in_use`. What is here is names, the folder, when a copy is due,
retention, and the files moved for a restore.

A copy is taken by `Store.step` itself (`before`), so no route can forget it: before every undo and every import, and on the first
step of a UTC day. If the copy for an undo or an import can't be made, nothing is written (`Invalid`, in plain words), and an
import is refused whenever its copy fails. If only the daily copy can't be made (a full disk, say), the change is still saved and
a plain warning is kept (`store.backup_warning`) and logged. There is no setting that turns any of this off.
Nothing is remembered between steps: "is a daily copy due?" is decided by listing the backups folder, so a new Store for every
request (#65) decides the same way. The one piece of module state is the lock below.

The copies sit beside the database, on the same disk. They protect against a clark bug, a bad import or a wrong undo, not against
losing the disk or the computer (the off-computer copy is #86b). Standard library only, Python 3.9.
"""
import contextlib
import json
import errno
import logging
import os
import re
import secrets
import shutil
import threading
import time
from datetime import timedelta
from pathlib import Path

try:
    import fcntl                       # macOS and Linux; not on Windows, where only the in-process flag guards a restore
except ImportError:
    fcntl = None

from clark import platform, settings, store as clark_store, timefmt
from clark.store import Invalid

# The default number of each kind of copy kept (whole number, 1 to 365). The number used is the data folder's settings.json
# `backups_kept` (settings.backups_kept, #111), which falls back to this when there is none or it isn't a whole number from 1 to 365.
KEEP = 14
TAGS = ("daily", "undo", "import", "changes", "restore", "migrate")
FAMILY = {"daily": "daily", "undo": "undo", "import": "import", "changes": "import", "restore": "restore", "migrate": "migrate"}     # each family is counted on its own
KIND_WORDS = {"daily": "daily", "undo": "before an undo", "import": "before an import", "changes": "before a change",
              "restore": "restored copy", "migrate": "before an update"}     # what the restore list shows a person for each tag
ROUTE_TAG = {"undo": "undo", "excel": "import", "team": "changes"}          # the routes that always take a copy; none takes "migrate" (#126's migration calls make(..., family="migrate") itself)
IMPORT_TAGS = ("import", "changes")
NAME = re.compile(r"clark-([0-9]{8}T[0-9]{6}Z)-(" + "|".join(TAGS) + r")(?:-([0-9]+))?\.db")        # a whole name (digits are 0-9 only; \d would take other scripts' digits); the only files retention or a restore touch
PART_AGE = 24 * 60 * 60         # seconds; an unfinished copy this old is removed
ASIDE = re.compile(r"replaced-[0-9]{8}T[0-9]{6}Z(?:-[0-9]+)?")      # [0-9], never \d: \d also takes digits of other scripts
RESTORING = ".restoring"
MARKER = ".restoring.json"

LOG = logging.getLogger("clark.backup")
backup_warning = None           # #111: the plain words of the last failed daily copy, or None after a good one. A store is closed after each request, so the page reads this, not a store; a restart clears it
_HOLD = object()                # what `once` leaves on a store (store._backup_hold) to say its copy is already taken; nothing else counts
_lock = threading.Lock()        # held while a copy is given its final name and when old copies are removed (threads; see move_unless_exists)


# ── Words ─────────────────────────────────────────────────────────────────────

def shown(path):
    """A folder as a person reads it: under the home folder it is written from "~" (so no user name is in a message)."""
    return platform.shown(path)


def _cause(error):
    if isinstance(error, OSError) and not isinstance(error, platform.PlatformError):
        cause = error.strerror or str(error)
    else:
        cause = str(error)
    return cause.strip().rstrip(".")


def plain_reason(error):
    """The system's reason for a file problem, in words a person reads: the few that are jargon are put plainly."""
    if isinstance(error, NotADirectoryError):
        return "it is a file, not a folder"
    if isinstance(error, IsADirectoryError):
        return "it is a folder, not a file"
    if isinstance(error, FileNotFoundError):
        return "it isn't there"
    if isinstance(error, PermissionError):
        return "this account isn't allowed to use it"
    if isinstance(error, OSError) and not isinstance(error, platform.PlatformError):
        if error.errno == errno.ENOSPC:
            return "the disk is full"
        if error.errno == errno.EROFS:
            return "the disk is read-only"
        return "a file problem"
    return _cause(error)


def _said(folder, error, step):
    """The reason in one sentence, then what to do: `step`, unless the reason brings its own. A platform error's own words
    already name the folder and say what to do, so nothing is added; the store's refusals (Invalid) are whole sentences, and
    the copy may have been written before its check failed, so they are never put after "can't be written to"."""
    if isinstance(error, platform.PlatformError):
        return f"{_cause(error)}."
    if isinstance(error, Invalid):
        return f"{_cause(error)}. {step}"
    if os.path.lexists(folder) and not os.path.isdir(folder):          # a file where the folder should be (F4)
        return f"{shown(folder)} is a file, not a folder. Rename or move it, then try again."
    return f"The backups folder {shown(folder)} can't be written to ({plain_reason(error)}). {step}"


SAVED = "The backup could not be saved."      # what a person reads for a copy that failed in a way only clark knows about
STEP = "Check that the backups folder exists and has space, then try again."
IMPORT_STEP = "Check that the backups folder exists and you can save files there, then import again."


def refusal(tag, folder, error):
    """The plain refusal when a copy can't be made. For an import it is the gate: there is no import until a copy is kept."""
    if isinstance(error, Invalid) and str(error) == clark_store.CHECK_FAILED:      # a copy was made but did not check out
        again = "Try again; if it happens again, check the disk has space."
        if tag in IMPORT_TAGS:
            return f"The import was stopped, because a backup of your data must be made first. {error} Nothing was imported. {again}"
        if tag == "migrate":
            return f"The database could not be updated because a backup of your data must be made first. {error} Nothing was changed. {again}"
        return f"A backup of your data must be made first. {error} Nothing was changed. {again}"
    if tag in IMPORT_TAGS:
        return ("The import was stopped, because a backup of your data must be made first and it couldn't be. Nothing was "
                f"imported. {_said(folder, error, IMPORT_STEP)}")
    if tag == "migrate":
        return ("The database could not be updated because a backup of your data must be made first, and it couldn't be. "
                f"Nothing was changed. {_said(folder, error, STEP)}")
    return f"A backup of your data must be made first, and it couldn't be. Nothing was changed. {_said(folder, error, STEP)}"


def daily_warning(folder, error):
    """The plain warning when only the daily copy can't be made. It is not a refusal: the change goes ahead (see `before`)."""
    return ("Your change was saved, but today's backup of your data couldn't be made. A new try is made with your next "
            f"change. {_said(folder, error, 'To keep your backups up to date, check that the backups folder exists and has space.')}")


CLOSE = "Check the disk has space and no other program is using the file, then try again."
GATE_STARTS = ("The import was stopped, because a backup", "A backup of your data must be made first",
               "The database could not be updated because a backup")


def is_refusal(text):
    """Whether `text` is one of the refusals above (the Excel import shows it as it is)."""
    return str(text).startswith(GATE_STARTS)


RESTORE_HELP = "\n".join((                     # no line starts with the product name
    "To put a backup back, close clark, then run this, with NAME the file name from the list above:",
    "    python3 -m clark restore NAME",
    "A file name with \"migrate\" in it is a backup taken just before clark updated the database.",
    "A backup of what you have now is made first. Then the database being replaced is moved into a folder called",
    "replaced-DATE inside the backups folder. Those folders hold whole old databases and are never removed",
    "by clark: remove them yourself when you are sure you don't need them.",
    "The backups are on this computer's disk, so they don't protect against losing the disk or the computer.",
    "If that command isn't to hand: 1 Quit clark. 2 Open the backups folder, beside clark.db. 3 Choose the backup by its",
    "date. The list above shows your local time, but a file's name carries UTC time (the Z at its end). 4 Move every",
    "file whose name starts with clark.db out of the way, copy the chosen file in, rename it clark.db, and start clark."))


# ── Names, the folder, and what is in it ──────────────────────────────────────

def _latest_believed():
    """The latest time a copy's name or file time may carry and be believed: a day after now, as the store's clock says (UTC
    text)."""
    return (clark_store.clock() + timedelta(days=1)).strftime("%Y%m%dT%H%M%SZ")


class Entry:
    """One backup in the folder: its path, name, UTC time text, tag and counter, and the key that orders them."""

    def __init__(self, path, match, mtime_ns):
        self.path, self.name = Path(path), Path(path).name
        self.stamp, self.tag = match.group(1), match.group(2)
        self.counter = int(match.group(3) or 1)
        self.mtime_ns = mtime_ns
        # Oldest first, by when the file was WRITTEN (its file time), then the counter, then the name, so the order is always the
        # clock to decide what goes: a copy dated in the future ages like any other. Never the name as text before the counter
        # ("-10" sorts before "-2" as text).
        # Known limit (a later item, not built): the file time comes from the same clock, so while the clock is wrong a family keeps
        # one recent copy plus the wrong-dated ones. A clock-free order is possible: a counter in the name that is 1 + the largest
        # counter in the folder, ordered by counter then name, with no file time.
        # `ahead` below only says a time can't be believed (more than a day after the store's clock, or one that can't be turned
        # into a date). It is used by the due-today test and by nothing that orders or removes a copy.
        latest = _latest_believed()
        try:
            self.filed = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime(mtime_ns // 1_000_000_000))      # the file time as UTC text
        except (OverflowError, OSError, ValueError):
            self.filed = None                   # a file time that can't be turned into a date is not believed, and is no crash
        self.ahead = self.stamp > latest or self.filed is None or self.filed > latest
        self.key = (mtime_ns, self.counter, self.name)

    @property
    def family(self):
        return FAMILY[self.tag]


def entries(folder):
    """Every backup in `folder`, oldest first: a regular file (never a link, a hard-linked file or a folder) whose whole name is a backup's. A folder
    that isn't there has none."""
    out = []
    try:
        scan = os.scandir(folder)
    except FileNotFoundError:
        return out
    with scan:
        for e in scan:
            m = NAME.fullmatch(e.name)
            if m and e.is_file(follow_symlinks=False):
                try:
                    st = e.stat(follow_symlinks=False)
                    if st.st_nlink > 1:
                        continue            # another name for the same file (a hard link): not a copy clark made, and never removed
                    out.append(Entry(e.path, m, st.st_mtime_ns))
                except FileNotFoundError:
                    pass                    # removed while we looked
    return sorted(out, key=lambda x: x.key)


def _unreadable(folder, error):
    return (f"The backups folder {shown(folder)} can't be read ({plain_reason(error)}). Check that it is a folder and that you can "
            "open it, then try again.")


def valid_name(backups_dir, name):
    """The path of the backup called `name` in `backups_dir`, or Invalid. One function for retention and both restores: the
    whole name must be a backup's name (so `..`, a path, `replaced-*` and `notes.txt` are refused), a regular file and not a
    link, and directly in the folder."""
    text = str(name)
    folder = Path(backups_dir)
    try:
        with os.scandir(folder):
            pass
    except FileNotFoundError:
        pass                            # no folder yet: the name is simply not a copy
    except OSError as e:                # the folder is a file, or can't be read: say that, as the list does (F3)
        raise Invalid(_unreadable(folder, e)) from e
    path = folder / text
    if not NAME.fullmatch(text) or path.is_symlink() or not path.is_file() or path.stat().st_nlink > 1 or path.resolve().parent != folder.resolve():
        said = "".join(c if c.isprintable() else "?" for c in text[:80])      # a name typed with a control character can't change the screen
        raise Invalid(f"No backup called {said} is in {shown(folder)}. To see the backups, run:\n    python3 -m clark restore")
    return path


def listing(folder):
    """The copies in `folder`, newest first, each as {"name", "tag", "kind", "when"}; `kind` is the tag in plain words (KIND_WORDS); `when` is in the person's local time (#75)."""
    try:
        found = entries(folder)
    except OSError as e:                # the folder is a file, or can't be read: say so in words, with no user name in them
        raise Invalid(_unreadable(folder, e)) from e
    return [{"name": x.name, "tag": x.tag, "kind": KIND_WORDS[x.tag], "when": timefmt.local_text(x.stamp)} for x in reversed(found)]


def _today():
    return clark_store.clock().strftime("%Y%m%d")


def due_today(folder):
    """True when no backup of any kind, named for today's UTC day, is in `folder`. Decided by listing it; nothing is remembered."""
    try:
        today = _today()
        # A copy counts as today's only if its file time is not ahead too: a future-dated copy (a clock that ran ahead, then was put
        # right) that carries today's date in its name must not make today's copy be skipped (#113).
        return not any(e.stamp[:8] == today and not e.ahead for e in entries(folder))
    except OSError:
        return True                     # can't be read: a copy is due, and writing it will say why not


# ── Taking a copy ─────────────────────────────────────────────────────────────

def before(store, route):
    """The hook `Store.step` calls before it opens a step (not for a dry one): an undo, an Excel import or a teammate's changes
    take their copy; any other step takes the daily one if none is there for today. If the copy for an undo or an import can't
    be made this raises Invalid, having written nothing. If only the daily copy can't be made (a full disk, say) the step goes
    ahead: the person's change matters more than today's copy, so it is not lost, `store.backup_warning` holds a plain warning
    (and it is logged), and the next step tries again, because a daily copy is still due. (Decided for #86.)"""
    if store._backup_hold is _HOLD:
        return None
    tag = ROUTE_TAG.get(route)
    if tag is not None:
        return take_pending(store, tag)
    if not due_today(store.backups_dir):
        return None
    try:
        take(store, "daily")
    except Exception as e:             # whatever goes wrong, today's copy is only a warning: the person's change is not lost
        # (a RuntimeError from the copy must not escape Store.step either)
        known = isinstance(e, (Invalid, OSError, platform.PlatformError))      # only these carry words a person can read
        warning = daily_warning(store.backups_dir, (e.__cause__ or e) if known else Invalid(SAVED))
        LOG.warning("%s", warning)
    else:
        warning = None
    store.backup_warning = warning
    _set_warning(warning)
    return None


def _set_warning(text):
    global backup_warning
    backup_warning = text


class Pending:
    """A copy taken for an undo or an import, whose step has not finished: retention waits (so a step that fails does not push an
    older copy out), and a step that fails or writes nothing removes it."""

    def __init__(self, path, folder, has_rows):
        self.path, self.folder, self.has_rows = Path(path), Path(folder), has_rows


def take_pending(store, tag):
    """Like `take`, but retention is left to `finish`. A Pending."""
    folder = Path(store.backups_dir)
    try:
        final, summary = _write(store.path, folder, store.onedrive_roots, tag)
    except (OSError, platform.PlatformError, Invalid) as e:
        raise Invalid(refusal(tag, folder, e)) from e
    return Pending(final, folder, summary["rows"]["projects"] > 0)


def finish(pending, kept):
    """The step is over. If it wrote something (`kept`) retention runs, as it would have; if not, the copy is removed again, since
    the database is as it was and the copy is only one more of the 14 kept. Never raises."""
    if pending is None:
        return
    if kept:
        prune(pending.folder, newest_has_rows=pending.has_rows, protect=(pending.path,))
    else:
        with contextlib.suppress(OSError):
            pending.path.unlink()


def take(store, tag):
    """Take a copy of the store's data now, tagged `tag`; its path. Invalid, in plain words, if it can't be made."""
    return make(store.path, store.backups_dir, store.onedrive_roots, tag)


def make(path, folder, onedrive_roots, tag=None, protect=(), family=None):
    """Take a copy tagged `tag`; its path. `family` is the same thing by another name: make(..., family="migrate") and
    make(..., "migrate") are one call (the tag decides the family, FAMILY). Retention never removes the new copy, nor anything in
    `protect`. Invalid, in plain words, if the copy can't be made."""
    if tag is None:
        tag = family
    if tag not in TAGS or family not in (None, tag):
        raise ValueError(f"unknown kind of backup {tag!r}")
    folder = Path(folder)
    try:
        final, summary = _write(path, folder, onedrive_roots, tag)
    except (OSError, platform.PlatformError, Invalid) as e:
        raise Invalid(refusal(tag, folder, e)) from e
    prune(folder, newest_has_rows=summary["rows"]["projects"] > 0, protect=(final, *protect))     # after a good copy only, and never an error
    if not os.path.lexists(final):
        raise Invalid(refusal(tag, folder, Invalid(SAVED)))         # removed straight after it was made
    return final


def _write(path, folder, onedrive_roots, tag):
    platform.check_data_dir(folder, onedrive_roots, what="backups")        # resolves links, so a shortcut into OneDrive is refused
    platform.private_folder(folder)
    stamp = clark_store.clock().strftime("%Y%m%dT%H%M%SZ")
    base = f"clark-{stamp}-{tag}"
    for _ in range(5):
        part = folder / f".{base}.{os.getpid()}.{secrets.token_hex(4)}.part"
        try:
            platform.private_file(part)                 # 0600 before sqlite writes a byte; O_EXCL, so never someone else's
            break
        except FileExistsError:
            continue
    else:
        raise Invalid(SAVED)                    # no private working file could be made
    try:
        summary = clark_store.snapshot(path, part)
        with _lock:
            # A name that is taken gets -2, -3: creaite's free_path (paths.py:92), made safe against a late arrival. The number is one
            # more than the highest in the folder for this second and kind, never a lower one that retention has freed: a freed
            # number reused would put the new copy among the oldest and it would be removed at once.
            taken = [e.counter for e in entries(folder) if e.stamp == stamp and e.tag == tag]
            n = max(taken) + 1 if taken else 1
            while True:
                final = folder / (f"{base}.db" if n == 1 else f"{base}-{n}.db")
                os.utime(part)          # its file time is now, so the file time follows the order the names are given
                if platform.move_unless_exists(part, final):
                    return final, summary
                n += 1
                if n > 10000:
                    raise Invalid(SAVED)        # too many copies with one name
    finally:
        _clear(part)


def _clear(part):
    for name in ("", "-wal", "-shm", "-journal"):
        Path(str(part) + name).unlink(missing_ok=True)


@contextlib.contextmanager
def once(store, tag):
    """One copy for every step inside the `with` (an import of several files): taken now, and no step inside takes another."""
    if tag not in TAGS:
        raise ValueError(f"unknown kind of backup {tag!r}")
    held = store._backup_hold is _HOLD
    if not held:
        take(store, tag)
    store._backup_hold = _HOLD
    try:
        yield
    finally:
        store._backup_hold = _HOLD if held else None


# ── Retention ─────────────────────────────────────────────────────────────────

def prune(folder, keep=None, newest_has_rows=True, protect=()):
    """Remove the oldest copies, keeping the newest `keep` (default: the data folder's setting, 14 unless changed) of each kind (daily, undo, restore, and import-changes) and never the
    newest of all: so a kind can hold 14, plus the newest of all, which may be one more. "Oldest" and "newest" are by when the
    file was written, never by a comparison with the clock; the name and the file time come from the same clock, so a copy dated
    in the future can't be told from a real one and ages like any other. If the newest copy has no projects (`newest_has_rows` False) the newest one that does is kept too, whatever
    its age. Nothing in `protect` (paths) is removed. Only a regular file directly in `folder` with a backup's whole name is ever removed, one file at a time; a
    working file of an earlier run, a day old, is removed too. Never raises: a failure here stops nothing. The names removed."""
    removed = []
    try:
        if keep is None:
            keep = settings.backups_kept(Path(folder).parent)
        with _lock:
            found = entries(folder)
            keepers = set()
            for family in set(FAMILY.values()):
                keepers.update(e.path for e in [x for x in found if x.family == family][-max(2 if family == "restore" else 1, int(keep)):])
            keepers.update(e.path for e in found if e.name in {Path(p).name for p in protect})      # by name: the folder is this one
            if found:
                keepers.add(found[-1].path)
            if found and not newest_has_rows:
                for e in reversed(found):
                    try:
                        if clark_store.check_copy(e.path)["rows"]["projects"] > 0:
                            keepers.add(e.path)
                            break
                    except Invalid:
                        continue
            here = Path(folder).resolve()
            for e in found:
                if e.path not in keepers and e.path.resolve().parent == here and not e.path.is_symlink():
                    try:
                        e.path.unlink()
                        removed.append(e.name)
                    except OSError:
                        pass
            _clear_old_parts(here)
    except Exception:                  # a retention problem must never stop a save, an undo or an import
        pass
    return removed


PART = re.compile(r"\.clark-[0-9]{8}T[0-9]{6}Z-[a-z]+(?:-[0-9]+)?\.[0-9]+\.[0-9a-f]+\.part")


def _clear_old_parts(folder):
    with os.scandir(folder) as scan:
        for e in scan:
            if not PART.fullmatch(e.name):
                continue
            try:
                old = e.is_file(follow_symlinks=False) and time.time() - e.stat(follow_symlinks=False).st_mtime > PART_AGE
            except OSError:
                continue                    # gone (or unreadable) while we looked: leave it
            if old:
                Path(e.path).unlink(missing_ok=True)


# ── Restore ───────────────────────────────────────────────────────────────────

def restore_over(store, name):
    """Put the backup `name` back over this store's database. The store is closed (open it again afterwards). See `restore_path`."""
    return restore_path(store.path, name, store.backups_dir, store.onedrive_roots, store)


_UNDER_WAY = set()                      # the databases a restore is working on in this process (a read must not finish it half-way)
_UNDER_WAY_LOCK = threading.Lock()
RESTORE_BUSY = "A restore is under way. Wait a moment and reload."
LOCK_SUFFIX = ".restore.lock"           # clark.db.restore.lock: held exclusively by a restore; made by the restorer, never removed, never made by a reader
LOCK_BUSY = ("This data is in use by another restore or another running copy of the program, so the restore did not start. "
             "Close the other one and try again. Nothing was changed.")


def _lock_file(path):
    return Path(path).with_name(Path(path).name + LOCK_SUFFIX)


def _take_restore_lock(path):
    """Take the restore lock exclusively without waiting (a reader's brief shared test is waited out for up to one second).
    Returns the open file (keep it open: closing it, or the program ending, releases the lock), or None where there is no
    fcntl or the lock file can't be made. Raises Invalid if another restore or reader holds it. flock, not lockf: a flock is
    held per open file, so a second try in this same process is refused too."""
    if fcntl is None:
        return None
    try:
        held = open(_lock_file(path), "ab")
    except OSError:
        return None
    end = time.monotonic() + 1.0
    while True:
        try:
            fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return held
        except OSError:
            if time.monotonic() >= end:
                held.close()
                raise Invalid(LOCK_BUSY)
            time.sleep(0.05)


def restore_path(path, name, folder=None, onedrive_roots=None, store=None):
    """Put the backup `name` (in `folder`, default the backups folder beside `path`) back over the database at `path`. In order:
    check the name and the copy (a damaged or newer-schema copy, or one of another database, is refused; an older-schema copy is
    put back, and open_store brings it up to date; a database here
    that holds no projects and no steps is not "another database", it is only empty); close `store`;
    make sure no other program has the file open (looked at before anything is written, so a refused restore leaves the backups
    folder as it was); take a `restore` backup of what is there now (not when it is too damaged to copy: it is moved aside whole
    anyway); look again and keep the file held; copy the chosen backup to clark.db.restoring and check it again; only then
    move clark.db and its -wal, -shm and -journal into backups/replaced-<UTC>/ and, as the very last step, move the
    restored copy into place. Nothing is removed. If the last step stops, the next start finishes it (`finish_restore`).
    Tested on macOS only: on Windows the open probe may stop the move of clark.db, and that is reported as "nothing was
    changed", which is true (the database is still where it was).
    Returns {"database": its path, "replaced": the folder the old database was moved into, or None if there was none,
    "backed_up": True only if a copy of the old database was really taken first (not when it was empty, unreadable or too damaged)}."""
    key = os.path.abspath(path)
    with _UNDER_WAY_LOCK:
        _UNDER_WAY.add(key)
    held = None
    try:
        held = _take_restore_lock(path)     # before the .restoring copy or the note is written
        return _restore_path(path, name, folder, onedrive_roots, store)
    finally:
        if held is not None:
            held.close()                    # releases the lock; the file stays
        with _UNDER_WAY_LOCK:
            _UNDER_WAY.discard(key)


def _restore_path(path, name, folder, onedrive_roots, store):
    path = Path(path)
    folder = Path(folder) if folder is not None else path.parent / "backups"
    chosen = valid_name(folder, name)
    if path.with_name(path.name + MARKER).exists() and not path.exists():
        # An earlier restore stopped part-way and the database it was replacing is waiting in a replaced- folder. Starting a new
        # restore would delete the note and the waiting copy and, if it then failed too, clark would make a new empty database.
        _, problem = _unfinished(path)
        if problem is not None:         # starting clark can't finish it: say where the database is and how to go on (F1)
            raise Invalid(f"{problem} Nothing was changed. To put {chosen.name} back instead, first delete the file "
                          f"{path.name + MARKER} in {shown(path.parent)}, then run restore again.")
        raise Invalid(f"An earlier restore stopped part-way, and {path.name} is missing. Nothing was changed. Start clark first: "
                      f"it will finish that restore, or tell you where your database is. Then run restore again if you still "
                      f"want {chosen.name}.")
    info = clark_store.check_copy(chosen)
    live = clark_store.identity(path) if path.exists() else None
    if live is not None and live != info["db_id"] and not _holds_nothing(path):
        raise Invalid(f"{chosen.name} is a backup of a different database, not this one, so it wasn't put back. To open it anyway, "
                      "copy it into a new, empty folder, rename it clark.db, then start clark where FOLDER is the new folder:"
                      "\n    python3 -m clark --data FOLDER")
    if store is not None:
        store.close()
    backed_up = False                         # whether a copy of what was here was really taken (the words the person reads depend on it)
    if live is not None:
        first = clark_store.in_use(path)          # a first look: a database in use is refused before anything is written to the backups folder
        if first is not None:
            first.close()                         # closed again, or the copy below could not read the database
        try:
            make(path, folder, onedrive_roots, "restore", protect=(chosen,))      # the copy asked for is never the one retention removes
            backed_up = True
        except Invalid:
            try:
                clark_store.check_copy(path)
            except Invalid:
                pass                      # the database here is damaged and can't be copied: it is moved aside whole below, so it is not lost
            else:
                raise                     # a good database that couldn't be copied (disk full, say): stop, as for any other copy
    probe = clark_store.in_use(path)                  # second look, kept open until the move is done: nothing can open it between
    aside = None
    restoring = path.with_name(path.name + RESTORING)
    marker = path.with_name(path.name + MARKER)
    try:
        try:
            _clear_marker_parts(marker, 0)       # nothing else can be writing one: the database is held above
            for stale in (restoring, marker):
                stale.unlink(missing_ok=True)
            platform.private_file(restoring)
            with open(chosen, "rb") as src, open(restoring, "wb") as dst:
                shutil.copyfileobj(src, dst)
            try:
                clark_store.check_copy(restoring)
            except Invalid as e:           # the chosen backup passed its own check, so the working copy is what went wrong (N4)
                raise Invalid(f"{chosen.name} could not be copied correctly. Try again, or choose another backup.") from e
            aside = _new_aside(folder, onedrive_roots)
        except BaseException as e:
            restoring.unlink(missing_ok=True)
            if isinstance(e, (OSError, platform.PlatformError)):
                raise Invalid(f"{chosen.name} couldn't be made ready to put back ({plain_reason(e)}). Nothing was changed. "
                              f"{CLOSE}") from e
            raise
        try:
            platform.write_file(marker, json.dumps({"aside": aside.name}))
            for side in ("", "-wal", "-shm", "-journal"):
                if Path(str(path) + side).exists() or Path(str(path) + side).is_symlink():
                    _move_aside(Path(str(path) + side), aside)
            platform.replace_file(restoring, path)
            marker.unlink(missing_ok=True)
        except (OSError, platform.PlatformError) as e:
            if path.exists() and not restoring.exists() and any(aside.iterdir()):
                marker.unlink(missing_ok=True)        # the restored copy is already in place and the old one is aside: finished
            elif path.exists():                 # the old database was never moved: nothing to finish, so nothing is left waiting
                restoring.unlink(missing_ok=True)
                marker.unlink(missing_ok=True)
                with contextlib.suppress(OSError):
                    aside.rmdir()             # empty, unless something was moved before the stop
                raise Invalid(f"{path.name} couldn't be moved out of the way ({plain_reason(e)}), so {chosen.name} wasn't put back. "
                              f"Nothing was changed. {CLOSE}") from e
            else:
                raise Invalid(f"The restore stopped part-way ({plain_reason(e)}). Your database is safe in "
                              f"{shown(aside)}. Start clark again and it will finish putting {chosen.name} back.") from e
    finally:
        if probe is not None:
            probe.close()
    moved = any(aside.iterdir())
    if not moved:
        aside.rmdir()                     # there was no database to move aside
    return {"database": path, "replaced": aside if moved else None, "backed_up": backed_up and moved}


def _clear_marker_parts(marker, older_than):
    """Remove the unfinished working files of the restore note (.clark.db.restoring.json.<n>.<hex>.part) that a stopped earlier
    restore left behind, those older than `older_than` seconds. Never raises."""
    pattern = re.compile(re.escape("." + marker.name) + r"\.[0-9]+\.[0-9a-f]+\.part")
    with contextlib.suppress(OSError):
        with os.scandir(marker.parent) as scan:
            for e in scan:
                if pattern.fullmatch(e.name) and e.is_file(follow_symlinks=False) \
                        and time.time() - e.stat(follow_symlinks=False).st_mtime >= older_than:
                    with contextlib.suppress(OSError):
                        Path(e.path).unlink()


def _holds_nothing(path):
    """True for a database with no projects and no steps: one clark made new (the data folder was emptied or clark.db was
    recreated). It has nothing to lose and a different identity from the backups, so a restore may replace it."""
    try:
        have = clark_store.check_copy(path)
    except Invalid:
        return False
    return have["rows"]["projects"] == 0 and have["rows"]["applies"] == 0


def _new_aside(folder, onedrive_roots):
    platform.check_data_dir(folder, onedrive_roots, what="backups")
    platform.private_folder(folder)
    base = "replaced-" + clark_store.clock().strftime("%Y%m%dT%H%M%SZ")
    n = 1
    while True:
        aside = folder / (base if n == 1 else f"{base}-{n}")
        try:
            os.mkdir(aside, 0o700)
            platform.private_folder(aside)
            return aside
        except FileExistsError:
            n += 1


def _move_aside(source, aside):
    if not platform.move_unless_exists(source, aside / source.name):
        raise OSError(f"{source.name} is already in {aside.name}")


def _unfinished(path):
    """For a restore that stopped part-way (the note is there, clark.db is not): the folder holding the database you had (or
    None) and the reason it can't be finished by the next start (a plain sentence), or None when it can. Changes nothing."""
    path = Path(path)
    marker = path.with_name(path.name + MARKER)
    restoring = path.with_name(path.name + RESTORING)
    try:
        aside = path.parent / "backups" / json.loads(marker.read_text(encoding="utf-8"))["aside"]
        if not ASIDE.fullmatch(aside.name):
            raise ValueError("odd folder name")
    except (OSError, ValueError, KeyError, TypeError):
        aside = None
    if aside is not None and not aside.is_dir():          # the folder the note names has been moved or removed
        return aside, (f"{path.name} is missing from {shown(path.parent)}, and the folder that held your database "
                       f"({shown(aside)}) isn't there any more. Look in {shown(aside.parent)} for a folder whose name starts "
                       f"with replaced-, and move the {path.name} in it back into {shown(path.parent)}, then start clark.")
    try:
        if aside is None or not restoring.is_file():
            raise Invalid("not there")
        clark_store.check_copy(restoring)
    except Invalid:
        if aside is None:
            where = f"a folder whose name starts with replaced- in {shown(path.parent / 'backups')}"
        else:
            where = shown(aside)
        return aside, (f"{path.name} is missing from {shown(path.parent)}. Your database is in {where}. Move {path.name} from "
                       f"there back into {shown(path.parent)}, then start clark.")
    return aside, None


def restoring(path):
    """True while this process is restoring the database at `path`, or while another process (or another restore in this one)
    holds the restore lock. A missing lock file counts as not locked; this never makes it."""
    with _UNDER_WAY_LOCK:
        if os.path.abspath(path) in _UNDER_WAY:
            return True
    if fcntl is None:
        return False
    try:
        probe = open(_lock_file(path), "rb")
    except OSError:
        return False
    with probe:
        try:
            fcntl.flock(probe, fcntl.LOCK_SH | fcntl.LOCK_NB)
        except OSError:
            return True
        return False                        # the shared lock is released when the file closes


def finish_restore(path):
    """Called by `open_store` before it could make a new database. A restore leaves a small note (clark.db.restoring.json) when it
    starts moving the old database aside, and removes it when it has finished. If the note is there and clark.db is not, the
    restore stopped part-way: when the copy waiting beside it (clark.db.restoring) is still good it is moved into place, and
    otherwise Invalid names the folder holding the database you had. With no note, nothing is done, so a leftover
    clark.db.restoring can never bring old data back."""
    if restoring(path):                     # this process is restoring right now: it finishes its own restore (checked first: the note is written late)
        raise Invalid(RESTORE_BUSY)
    path = Path(path)
    marker = path.with_name(path.name + MARKER)
    partial = path.with_name(path.name + RESTORING)
    _clear_marker_parts(marker, 60)         # left by a restore that was stopped hard; a minute old at least, so none being written is touched
    if not marker.exists():
        return
    if path.exists():                       # finished, or never started moving: tidy up
        marker.unlink(missing_ok=True)
        partial.unlink(missing_ok=True)
        return
    aside, problem = _unfinished(path)
    if problem is not None:
        raise clark_store.Unfinished(problem)
    for side in ("-wal", "-shm", "-journal"):      # a left-over one beside the restored copy would be replayed into it
        stray = Path(str(path) + side)
        if stray.exists():
            _move_aside(stray, aside)
    platform.replace_file(partial, path)
    marker.unlink(missing_ok=True)


def restore_into(folder, name, backups_dir, onedrive_roots=None):
    """Put the backup `name` from `backups_dir` into a fresh folder as clark.db (which must not exist or be empty); the path.
    This is also the way to open a backup of a different database, and how a test reads a backup."""
    chosen = valid_name(backups_dir, name)
    clark_store.check_copy(chosen)
    folder = Path(platform.check_data_dir(folder, onedrive_roots))
    if folder.exists() and (not folder.is_dir() or any(folder.iterdir())):
        raise Invalid(f"{shown(folder)} isn't an empty folder, so {chosen.name} wasn't put there. Choose a new, empty folder.")
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / "clark.db"
    platform.private_file(dest)
    try:
        with open(chosen, "rb") as src, open(dest, "wb") as dst:
            shutil.copyfileobj(src, dst)
    except BaseException:
        dest.unlink(missing_ok=True)
        raise
    return dest
