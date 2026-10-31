"""The backup list, Preview and Restore, as the server runs them (#111; the unguarded feed beside the guarded backup.py, store.py and
server.py). The routes in server.py call this and nothing else; it holds no SQL (every look at a database is clark.store's
`snapshot` and `check_copy`) and moves no file itself (the swap is `backup.restore_path`, #88).

One class, Safety, with three public methods, each returning (status, body) for the server to send:
- listing(): GET /api/backups: the copies newest first with their size and kind in words, a status line, the last daily copy's
  warning, a check of the newest copy, and how many are kept.
- preview(req): POST /api/backups/preview {name}: counts of projects, work items and milestones in the copy and now. It reads a
  private working copy of the backup (in the backups folder, removed after) and a temporary snapshot of the live data, never the live file itself, and removes both.
- restore(req): POST /api/backups/restore {name, last_step}: under changes.LOCK, taken without waiting, so a change, an undo or
  another restore in this process is never overlapped. In order: the name is checked, the live data is checked to be as it was at
  Preview (`last_step`), an older copy is tried on a temporary copy (open_store's migration) so a failure changes nothing, backup.restore_path swaps the files, and the new file is opened once (and closed).

Every reply has `ok`, a stable `code` and `message` in plain words (MESSAGES, or the plain refusal text of backup.py and store.py,
which their own tests pin). A fault that is none of these is raised and the server answers it with its own 500.
Standard library only, Python 3.9.
"""
import os
import shutil
import stat
import tempfile
import threading
from pathlib import Path

from clark import backup, changes, platform, settings, store as clark_store, timefmt
from clark.store import Invalid

KIND_LABELS = {"daily": "Daily", "undo": "Before an undo", "import": "Before an import", "changes": "Before a change",
               "restore": "Before a restore", "migrate": "Before an update"}      # = backup.KIND_WORDS, capitalised; "restore" is the copy taken before a restore
WORK_ITEM_TABLES = ("actions", "raid", "decisions")     # what the page calls work items
COPY_LIMIT = 4 * 1024 ** 3                               # a backup larger than this is not copied for a Preview

MESSAGES = {
    "no_backup": "No backup called {name} is in the backups folder.",
    "folder": "The backups folder can't be read. Check that it is a folder and that you can open it, then try again.",
    "other_database": "{name} is a backup of a different database, so it wasn't put back.",
    "busy": "Something is being saved. Wait a moment and try again.",
    "in_use": "Another window or program has clark's data open. Close it there and try again.",
    "changed": "Your data changed after you looked. Look at the backup again.",
    "bad_request": "Choose a backup from the list and try again.",
    "reopen": "The backup was put back, but clark could not open it again. Close clark and start it again.",
    "restored": "Restored the backup from {date}. Your data from before is kept in case you need it.",
    "restored_empty": "Restored the backup from {date}.",
    "damaged_latest": "The latest backup, from {date}, is damaged and can't be used.",
    "latest": "Latest backup: {when}. A daily backup is always made.",
    "none_yet": "There are no backups yet. One is made when you save your first change of the day.",
    "older": "Made by an older version of clark; it is brought up to date when restored.",
    "busy_preview": "Another backup is being looked at. Wait a moment and try again.",
    "unfinished": "An earlier restore did not finish. Close clark and start it again: it finishes putting your data back, or tells you where your data is. Nothing was changed.",
    "generic": "That backup couldn't be put back. Nothing was changed.",
    "file_problem": "A file clark needs couldn't be read or written ({reason}). Nothing was changed.",
}
COMMAND_WORDS = ("the file clark", "run restore", "restore again", "python3", "--data", ".restoring", "clark.db", "-m clark")     # text holding any of these is command-line talk, never shown
WORK_PREFIXES = ("clark-preview-", "clark-restore-")     # the private working folders, made inside the backups folder
JARGON = ("zip", "sqlite", "wal", "python", "manifest", "traceback", "errno", "db_id", "schema")     # no message a person reads holds these


def reply(status, code, text, **extra):
    return status, {"ok": False, "code": code, "message": text, **extra}


def size_text(n):
    """A file size as a person reads it: "212 KB", "1.4 MB" (1024 to the unit, at least 1 KB)."""
    if n >= 1024 ** 2:
        return f"{n / 1024 ** 2:.1f} MB"
    return f"{max(1, round(n / 1024))} KB"


def _counts(rows):
    return {"projects": rows.get("projects", 0), "work_items": sum(rows.get(t, 0) for t in WORK_ITEM_TABLES),
            "milestones": rows.get("milestones", 0)}


def _date(when):
    return when[:10]                                     # DD-MM-YYYY of "DD-MM-YYYY HH:MM"


def _open_regular(path):
    """A read-only handle on `path` that is a regular file and not a link (a link swapped in after the name was checked is refused)."""
    fd = os.open(str(path), os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink > 1 or info.st_size > COPY_LIMIT:
            raise Invalid("not a backup")
        return os.fdopen(fd, "rb")
    except BaseException:
        os.close(fd)
        raise


class Safety:
    """The server's `safety`. `path` is clark.db; `lock` is the one writer lock (changes.LOCK; a test may pass another). Nothing
    else holds the database open while clark runs (the launcher closes its own store before serving, and every request opens its
    own), so a restore can take the file; another program that has it open is caught by backup.restore_path's in-use look."""

    def __init__(self, path, onedrive_roots=None, lock=None):
        self.path = Path(path)
        self.folder = self.path.parent / "backups"
        self.roots = onedrive_roots
        self.lock = lock if lock is not None else changes.LOCK
        self._preview_lock = threading.Lock()                # one Preview at a time (each copies a whole backup)
        self.clean_work()

    def clean_work(self):
        """Remove working folders a stopped earlier run left in the backups folder (each holds a copy of the data). Never raises."""
        try:
            for p in self.folder.iterdir():
                if p.name.startswith(WORK_PREFIXES) and p.is_dir() and not p.is_symlink():
                    shutil.rmtree(p, ignore_errors=True)
        except OSError:
            pass

    def _work(self, prefix):
        """A new private working folder inside the backups folder (not the system temp folder, so a full copy never lands there)."""
        return Path(tempfile.mkdtemp(prefix=prefix, dir=str(self.folder)))

    # ── the words for a refusal ──────────────────────────────────────────────

    def refusal(self, error, name=None):
        """(status, body) for an Invalid or a file problem, in plain words. Text from backup.py and store.py is already plain and is
        kept; the few that point at the command line are put in this page's terms."""
        text = str(error)
        if isinstance(error, platform.PlatformError) or isinstance(error, OSError):
            return reply(400, "file_problem", MESSAGES["file_problem"].format(reason=backup.plain_reason(error)))
        if text.startswith("The backups folder") and "can't be read" in text:
            return reply(400, "folder", MESSAGES["folder"])
        if text.startswith("No backup called"):
            return reply(400, "no_backup", MESSAGES["no_backup"].format(name=name_for_words(name)))
        if "a backup of a different database" in text:
            return reply(400, "other_database", MESSAGES["other_database"].format(name=name_for_words(name)))
        if text.startswith("Another window or program has clark's data open") or "can't be opened right now" in text:
            return reply(409, "in_use", MESSAGES["in_use"])
        low = text.lower()
        if not isinstance(error, OSError) and any(w in low for w in COMMAND_WORDS):
            if "stopped part-way" in low or "earlier restore" in low:      # the words point at a file or the command line: say it plainly
                return reply(500, "unfinished", MESSAGES["unfinished"])
            return reply(400, "refused", MESSAGES["generic"])
        if "is damaged" in text:
            return reply(400, "damaged", text)
        if "newer clark" in text:
            return reply(400, "newer", text)
        if text.startswith(clark_store.MIGRATE_REFUSAL_STARTS):
            return reply(400, "migrate_failed", text)
        if "stopped part-way" in text:
            return reply(500, "unfinished", text)
        return reply(400, "refused", text)

    def _name(self, req):
        """The backup's path from the request, or a (status, body) refusal. Only a whole backup name in the backups folder passes."""
        name = req.get("name") if isinstance(req, dict) else None
        if not isinstance(name, str) or not name or len(name) > 200:
            return None, reply(400, "bad_request", MESSAGES["bad_request"])
        try:
            return backup.valid_name(self.folder, name), None
        except Invalid as e:
            return None, self.refusal(e, name)
        except OSError as e:
            return None, self.refusal(e, name)

    # ── the list ─────────────────────────────────────────────────────────────

    def listing(self):
        try:
            found = backup.entries(self.folder)
        except OSError:
            return reply(503, "folder", MESSAGES["folder"])
        rows = []
        for e in reversed(found):
            try:
                size = e.path.stat().st_size
            except OSError:
                continue
            rows.append({"name": e.name, "tag": e.tag, "kind": backup.KIND_WORDS[e.tag], "kind_label": KIND_LABELS[e.tag],
                         "when": timefmt.local_text(e.stamp), "size": size, "size_text": size_text(size)})
        status, check = self._status(rows)
        return 200, {"ok": True, "backups": rows, "status": status, "newest_ok": check, "warning": backup.backup_warning,
                     "keep": settings.backups_kept(self.path.parent), "keep_label": settings.BACKUPS_KEPT_LABEL,
                     "keep_help": settings.BACKUPS_KEPT_HELP}

    def _status(self, rows):
        if not rows:
            return MESSAGES["none_yet"], True
        newest = rows[0]
        try:
            clark_store.check_copy(self.folder / newest["name"])
        except (Invalid, OSError):
            return MESSAGES["damaged_latest"].format(date=_date(newest["when"])), False
        return MESSAGES["latest"].format(when=newest["when"]), True

    # ── Preview ──────────────────────────────────────────────────────────────

    def _live_summary(self, work):
        """The live data's summary from a temporary snapshot (a read-only look; the live file is never opened for writing), or None
        when there is no live data or it can't be read."""
        if not self.path.is_file():
            return None
        dest = work / "now.db"
        try:
            platform.private_file(dest)
            return clark_store.snapshot(self.path, dest)
        except (Invalid, OSError):
            return None

    def _copy_of(self, chosen, work):
        """The chosen backup copied into the private folder `work`; the copy's path."""
        copy = work / "copy.db"
        with _open_regular(chosen) as src, open(platform.private_file(copy), "wb") as dst:
            shutil.copyfileobj(src, dst)
        return copy

    def preview(self, req):
        chosen, refused = self._name(req)
        if refused:
            return refused
        if not self._preview_lock.acquire(blocking=False):      # never two at once; never wait
            return reply(409, "busy_preview", MESSAGES["busy_preview"])
        try:
            work = self._work("clark-preview-")
        except OSError as e:
            self._preview_lock.release()
            return self.refusal(e, chosen.name)
        try:
            try:
                copy = self._copy_of(chosen, work)
                info = clark_store.check_copy(copy)
            except Invalid as e:
                return self.refusal(Invalid(str(e).replace("copy.db", chosen.name)), chosen.name)
            except OSError as e:
                return self.refusal(e, chosen.name)
            now = self._live_summary(work)
            entry = next((e for e in backup.entries(self.folder) if e.name == chosen.name), None)
            when = timefmt.local_text(entry.stamp) if entry else ""
            older = info["schema_version"] < clark_store.SCHEMA_VERSION
            same = now is None or clark_store.identity(work / "now.db") == info["db_id"]
            return 200, {"ok": True, "name": chosen.name, "when": when, "kind_label": KIND_LABELS.get(entry.tag, "") if entry else "",
                         "copy": _counts(info["rows"]), "now": _counts(now["rows"]) if now else None,
                         "last_step": now["last_step"] if now else None, "same_database": same, "older": older,
                         "older_note": MESSAGES["older"] if older else None}
        finally:
            shutil.rmtree(work, ignore_errors=True)
            self._preview_lock.release()

    # ── Restore ──────────────────────────────────────────────────────────────

    def _trial(self, copy, work):
        """An older copy is opened (so migrated) once on a temporary copy before anything real is touched. Invalid when it fails."""
        trial = work / "trial"
        trial.mkdir(mode=0o700)
        shutil.copyfile(copy, trial / "clark.db")
        clark_store.open_store(trial / "clark.db", onedrive_roots=[]).close()

    def restore(self, req):
        chosen, refused = self._name(req)
        if refused:
            return refused
        step = req.get("last_step")
        if step is not None and (not isinstance(step, int) or isinstance(step, bool)):
            return reply(400, "bad_request", MESSAGES["bad_request"])
        if not self.lock.acquire(blocking=False):            # a change, an undo or an import is running: never wait for it
            return reply(409, "busy", MESSAGES["busy"])
        try:
            work = self._work("clark-restore-")
        except OSError as e:
            self.lock.release()
            return self.refusal(e, chosen.name)
        try:
            live = self._live_summary(work)         # None when the file is missing or can't be read: then only a request with no step passes (Preview showed no step either)
            if (live["last_step"] if live else None) != step:
                return reply(409, "changed", MESSAGES["changed"])
            try:
                copy = self._copy_of(chosen, work)
                info = clark_store.check_copy(copy)
            except Invalid as e:
                return self.refusal(Invalid(str(e).replace("copy.db", chosen.name)), chosen.name)
            except OSError as e:
                return self.refusal(e, chosen.name)
            if info["schema_version"] < clark_store.SCHEMA_VERSION:
                try:
                    self._trial(copy, work)
                except Invalid as e:
                    return self.refusal(e, chosen.name)
            try:
                done = backup.restore_path(self.path, chosen.name, self.folder, self.roots, None)
            except Invalid as e:
                return self.refusal(e, chosen.name)
            except (OSError, platform.PlatformError) as e:
                return self.refusal(e, chosen.name)
            entry = next((e for e in backup.entries(self.folder) if e.name == chosen.name), None)
            date = _date(timefmt.local_text(entry.stamp)) if entry else ""
            try:
                clark_store.open_store(self.path, onedrive_roots=self.roots).close()       # opened once: an older copy is brought up to date
            except (Invalid, OSError, platform.PlatformError):
                return reply(500, "reopen", MESSAGES["reopen"])
            text = MESSAGES["restored" if done["replaced"] else "restored_empty"].format(date=date)
            return 200, {"ok": True, "code": "restored", "message": text, "reload": True}
        finally:
            self.lock.release()
            shutil.rmtree(work, ignore_errors=True)


def name_for_words(name):
    """A name typed by someone, as it may be put in a sentence: printable characters only and not too long."""
    return "".join(c if c.isprintable() else "?" for c in str(name)[:80])
