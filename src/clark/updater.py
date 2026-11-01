"""Settings › Version and updates: the server's seam for its update routes (status, review, install, arm and undo).

The server (server.py, guarded) imports no clark module; __main__ gives it an Updater, as it gives Safety for the backups. Each
method takes the request's JSON (already token-, Host- and size-checked by the dispatcher) and answers (status, body). The page
never sends a path or a file name: the file is the newest one in Downloads, or the one the person picks in the system's own
Open dialog on this computer, and an install or an undo names only the review or the arm this object handed out.

  status()        what is installed, whether this copy can update itself, the newest update in Downloads ("Review X.Y.Z" or
                  "Up to date."), the last update with Undo, and once the line about how the last update or undo ended
  review(req)     {"from": "downloads" | "file", "reinstall": bool}: take the file in once, check it, plan it, and answer the
                  review (from → to, the date, the notes, the files, the checksum). The review is held here for REVIEW_SECONDS
  install(req)    {"review_id"}: the held review only. Backs up, stages, checks, and hands over to the helper; the answer says
                  "restart", and the server then stops so the helper can swap the files. While it runs, every other route of
                  the server answers 503 (installing())
  arm_undo(req)   {}: says whether a full undo is possible or only the app and settings (the data changed since), and arms
                  the undo for ARM_SECONDS
  undo(req)       {"arm_id", "app_only": bool}: the armed undo only, within ARM_SECONDS; refuses the full undo when the data
                  changed since, and offers the app and settings only
  settle()        once the helper has finished (no marker): records what happened (the update went in, or the undo did and the
                  settings are put back), keeps the line for status() to say once, tidies clark's own folders and keeps the last
                  three. A thread started by watch() calls it when the new version starts; status() calls it too.

No request body and no file path is logged; a refusal's detail goes to the log, its plain sentence to the page. A sentence a
person reads never starts with the product name and holds no file path, nor the words zip, manifest or SHA.
"""
import hmac
import json
import logging
import os
import secrets
import threading
import time
from pathlib import Path

import clark
from clark import appfiles, platform, store, update_helper, update_install as ui, updates

LOG = logging.getLogger("clark.updater")
REVIEW_SECONDS = 15 * 60
ARM_SECONDS = 5
PENDING = "pending.json"
NOTICE = "notice.json"
WATCH_SECONDS = 120

MESSAGES = {
    "bad_request": "That could not be read. Reload the page and try again.",
    "busy": "An update is being installed. One moment.",
    "none_found": "There is no update in your Downloads folder. Download it from the clark releases page, or choose the file.",
    "review_again": "Review the update again, then install it.",
    "arm_again": "Choose Undo update again: the second click must come within 5 seconds of the first.",
    "not_here": "Updates can't be installed on this computer yet. Download the latest release and replace the clark folder by hand.",
    "dialog": "The window to choose a file could not be opened. Try again; if it keeps happening, restart clark.",
    "generic": "Something went wrong, and nothing was changed. Try again, or restart clark.",
}
UP_TO_DATE = "Up to date."
INSTALLING = "Installing version {to}. One moment while clark restarts. Don't close this window."
UNDOING = "Putting back version {to}. One moment while clark restarts. Don't close this window."
ARMED_FULL = "Choose Undo update again within 5 seconds to put back version {to}."
ARMED_RESTORE = ("Version {to} cannot open the data the update changed, so Undo update puts your data back as it was before the "
                 "update. Changes made after the update will be lost. Choose Undo update again within 5 seconds to go on.")
ARMED_APP_ONLY = ("Your data has changed since the update, and putting back the old data would lose those changes. "
                  "Choose Put back the app and settings only within 5 seconds to keep your data as it is.")
UPDATE_STOPPED = ("The update to version {to} didn't install, and your data is still in its newer layout. Choose Undo update to put "
                  "your data back as it was before the update.")
INSTALLED = "Version {to} is installed."
UNDO_DONE = "Version {to} has been put back. Your projects are as they were."
CHOOSE_PROMPT = "Choose the clark update file"


def reply(status, code, message=None, **extra):
    return status, {"ok": False, "code": code, "message": message or MESSAGES[code], **extra}


def app_folder():
    """The folder this copy of clark runs from: the parent of src/ (src/clark/__init__.py is two levels below it)."""
    return Path(clark.__file__).resolve().parents[2]


class Updater:
    """One per server. `choose`, `downloads`, `clock`, `python`, `start` and `server_pid` are seams for the tests."""

    def __init__(self, data_dir, db_path, port, app_dir=None, system=None, version=None, schema=None, choose=None,
                 downloads=None, clock=time.monotonic, python=None, start=None, server_pid=None, home=None, migration_backup=None, open_db=None):
        self.data = Path(data_dir)
        self.db = Path(db_path)
        self.port = port
        self.app = Path(app_dir) if app_dir else app_folder()
        self.system = system or ("mac" if platform.system() == platform.MAC else platform.system())
        self.version = version or clark.__version__
        self.schema = store.SCHEMA_VERSION if schema is None else schema
        self.choose = choose or platform.choose_file
        self.downloads = downloads
        self.home = home
        self.clock = clock
        self.python, self.start = python, start
        self.store = open_db                               # the server's open database: an undo that restores the data closes it
        self.server_pid = server_pid or os.getpid()
        self.migration_backup = migration_backup           # the copy this start's migration took (store.bring_up_to_date), else None
        self.lock = threading.Lock()
        self._installing = False
        self.reviewed = None
        self.armed = None

    # --- the maintenance flag ---

    def installing(self):
        return self._installing

    # --- helpers ---

    def _downloads(self):
        if self.downloads is not None:
            return Path(self.downloads)
        try:
            return platform.downloads_dir(self.home)
        except platform.PlatformError:
            return None

    def _blocked(self):
        """The plain sentence why this copy can't update itself, or None."""
        try:
            updates.check_app_folder(self.app)
        except updates.UpdateError as e:
            return e.message
        if self.system not in updates.SYSTEM_NAMES:
            return MESSAGES["not_here"]
        return None

    def _newer_in_downloads(self):
        folder = self._downloads()
        found = updates.newest_in(folder, self.system) if folder else None
        if found is None:
            return None
        version = updates.check_name(found.name, self.system)
        try:
            newer = updates.version_key(version) > updates.version_key(self.version)
        except ValueError:
            return None
        return version if newer else None

    def _write(self, name, doc):
        folder = platform.private_folder(self.data / ui.UPDATES)
        update_helper.write_json(folder / name, doc)

    def _read(self, name):
        try:
            doc = json.loads((self.data / ui.UPDATES / name).read_text(encoding="utf-8"), parse_int=ui.parse_int)
        except (OSError, ValueError):
            return None
        return doc if isinstance(doc, dict) else None

    def _drop(self, name):
        (self.data / ui.UPDATES / name).unlink(missing_ok=True)

    # --- GET /api/update ---

    def status(self, *req):
        self.settle()
        record = updates.installed_record(self.app) or {}
        released = record.get("released")
        installed = f"Version {self.version}" + (f", released {updates.date_text(released)}." if isinstance(released, str)
                                                    and len(released) == 10 and released[4] == "-" else ".")
        blocked = self._blocked()
        newer = None if blocked else self._newer_in_downloads()
        last = ui.last_update(self.data)
        notice = self._read(NOTICE)
        if notice is not None:
            self._drop(NOTICE)                        # said once
        body = {"ok": True, "version": self.version, "installed": installed, "blocked": blocked,
                "available": {"version": newer, "label": f"Review {newer}"} if newer else None,
                "line": None if blocked or newer else UP_TO_DATE,
                "last": None, "notice": notice.get("message") if notice and isinstance(notice.get("message"), str) else None,
                "installing": self._installing}
        if last is not None and not last[1].get("undone"):
            folder, rec = last
            day = updates.date_text("-".join((folder.name[0:4], folder.name[4:6], folder.name[6:8])))
            body["last"] = {"from": rec.get("from"), "to": rec.get("to"),
                            "line": f"Last update: {rec.get('from')} → {rec.get('to')} on {day}."}
            if isinstance(rec.get("data_restore_pending"), dict) and rec.get("installed") is not True:     # #280: the update stopped, the data is still in the newer layout
                body["last"]["line"] = UPDATE_STOPPED.format(to=rec.get("to"))
        return 200, body

    # --- POST /api/update/review ---

    def review(self, req):
        if not isinstance(req, dict) or set(req) - {"from", "reinstall"} or req.get("from") not in ("downloads", "file") \
                or not isinstance(req.get("reinstall", False), bool):
            return reply(400, "bad_request")
        if self._installing:
            return reply(409, "busy")
        blocked = self._blocked()
        if blocked:
            return reply(409, "blocked", blocked)
        if req["from"] == "downloads":
            folder = self._downloads()
            path = updates.newest_in(folder, self.system) if folder else None
            if path is None:
                return reply(404, "none_found")
        else:
            try:
                path = self.choose(CHOOSE_PROMPT, start=self._downloads())
            except platform.PlatformError:
                return reply(500, "dialog")
            if path is None:
                return 200, {"ok": True, "cancelled": True}
        reinstall = bool(req.get("reinstall", False))
        kept = None
        try:
            kept, digest = ui.take_in(path, self.data, self.system, chosen=req["from"] == "file")
            release = ui.read_taken(kept, digest, self.system, self.version, self.schema, reinstall=reinstall)
            plan = updates.plan(release, self.app)
        except updates.UpdateError as e:
            if kept is not None and e.key in ("unsigned", "badsig", "nokey"):       # an untrusted file is not kept
                kept.unlink(missing_ok=True)
                Path(str(kept) + updates.SIGNATURE_SUFFIX).unlink(missing_ok=True)
            LOG.info("an update was refused: %s", e.key)
            LOG.debug("an update was refused: %s", e.detail)
            return reply(409, e.key, e.message, again=e.key == "same")
        rid = secrets.token_urlsafe(18)
        self.reviewed = {"id": rid, "path": kept, "digest": digest, "reinstall": reinstall, "at": self.clock(), "to": release.version}
        return 200, {"ok": True, "review_id": rid, "review": updates.review(release, plan, self.version)}

    # --- POST /api/update/install ---

    def _held(self, slot, given, seconds):
        held = getattr(self, slot)
        return held if (held and isinstance(given, str) and hmac.compare_digest(given.encode("utf-8", "surrogatepass"),
                                                                              held["id"].encode())
                        and self.clock() - held["at"] <= seconds) else None

    def install(self, req):
        if not isinstance(req, dict) or set(req) != {"review_id"}:
            return reply(400, "bad_request")
        if not self.lock.acquire(blocking=False):
            return reply(409, "busy")
        try:
            if self._installing:
                return reply(409, "busy")
            held = self._held("reviewed", req["review_id"], REVIEW_SECONDS)
            self.reviewed = None                      # a review is used once
            if held is None:
                return reply(409, "review_again")
            self._installing = True
            stamp = ui.stamp_now()
            try:
                release = ui.read_taken(held["path"], held["digest"], self.system, self.version, self.schema, held["reinstall"])
                plan = updates.plan(release, self.app)
                backup_dir = ui.back_up(self.app, self.data, self.db, stamp, self.version, release.version, plan)
                self._write(PENDING, {"kind": "install", "stamp": stamp, "set": backup_dir.name, "to": release.version})
                staging = ui.stage(release, self.app, stamp)
                ui.first_check(staging, self.python)
                self._hand_over(staging, stamp, self.version, release.version, backup_dir)
            except (updates.UpdateError, ui.InstallError) as e:
                return self._stopped(stamp, e)
            return 200, {"ok": True, "restart": True, "message": INSTALLING.format(to=release.version)}
        finally:
            self.lock.release()

    def _hand_over(self, staging, stamp, from_version, to_version, backup_dir):
        kw = {"python": self.python} if self.python else {}
        if self.start:
            kw["start"] = self.start
        ui.hand_over(self.data, self.app, staging, stamp, from_version, to_version, self.schema, self.server_pid, self.port,
                     appfiles.MARK_HEADER, appfiles.data_mark(self.data), backup_dir, **kw)

    def _stopped(self, stamp, error):
        """A step before the hand-over failed: nothing in the app folder changed. Put the flag down and say so."""
        ui.remove_staging(self.app, stamp)
        self._drop(PENDING)
        self._installing = False
        LOG.info("an update stopped before it began: %s", error.key)
        LOG.debug("an update stopped before it began: %s", error.detail)
        return reply(409, error.key, error.message)

    # --- POST /api/update/arm-undo and /api/update/undo ---

    def arm_undo(self, req):
        if req not in ({}, None):
            return reply(400, "bad_request")
        if self._installing:
            return reply(409, "busy")
        try:
            choice = ui.undo_choice(self.data, self.db)
        except ui.InstallError as e:
            return reply(409, e.key, e.message)
        to = ui.last_update(self.data)[1].get("from")
        aid = secrets.token_urlsafe(18)
        self.armed = {"id": aid, "at": self.clock(), "choice": choice}
        return 200, {"ok": True, "arm_id": aid, "choice": choice, "seconds": ARM_SECONDS,
                     "line": (ARMED_RESTORE if ui.migration_of(ui.last_update(self.data)[1]) else ARMED_FULL).format(to=to)
                     if choice == "full" else ARMED_APP_ONLY}

    def undo(self, req):
        if not isinstance(req, dict) or set(req) - {"arm_id", "app_only"} or "arm_id" not in req \
                or not isinstance(req.get("app_only", False), bool):
            return reply(400, "bad_request")
        if not self.lock.acquire(blocking=False):
            return reply(409, "busy")
        try:
            if self._installing:
                return reply(409, "busy")
            held = self._held("armed", req["arm_id"], ARM_SECONDS)
            self.armed = None
            if held is None:
                return reply(409, "arm_again")
            try:
                choice = ui.undo_choice(self.data, self.db)
            except ui.InstallError as e:
                return reply(409, e.key, e.message)
            if choice == "app_only" and not req.get("app_only", False):
                return reply(409, "data_changed", ui.MESSAGES["data_changed"], choice="app_only")
            folder, record = ui.last_update(self.data)
            to = record.get("from")
            self._installing = True
            stamp = ui.stamp_now()
            restored, began = False, time.time()
            try:
                ui.check_restore(self.db, record)                 # a migrated update: the copy must be there and whole before anything starts
                undo_set = ui.back_up(self.app, self.data, self.db, stamp, self.version, to, kind="undo")
                staging = ui.stage_undo(folder, self.app, stamp)
                self._write(PENDING, {"kind": "undo", "stamp": stamp, "set": folder.name, "undo_set": undo_set.name, "to": to})
                ui.restore_data(self.db, record, self.store)      # last step before the hand-over, so a failure hands nothing over
                restored = ui.migration_of(record) is not None
                self._hand_over(staging, stamp, self.version, to, undo_set)
            except (updates.UpdateError, ui.InstallError) as e:
                if restored:                                      # #280: the data was put back but nothing took over: put the newer data back too
                    ui.put_back_newer_data(self.db, began)
                return self._stopped(stamp, e)
            return 200, {"ok": True, "restart": True, "message": UNDOING.format(to=to)}
        finally:
            self.lock.release()

    # --- after the helper ---

    def settle(self):
        """What the helper ended with, recorded once it has finished. Safe to call any number of times."""
        if self._installing or update_helper.marker_path(self.data).exists():
            return False
        pending = self._read(PENDING)
        if pending is not None:
            result = update_helper.read_result(self.data) or {}
            sets = self.data / ui.UPDATES
            if result.get("stamp") == pending.get("stamp") and result.get("status") == "installed":
                try:
                    if pending.get("kind") == "install" and ui.SET_RE.match(str(pending.get("set"))):
                        ui.note_installed(sets / pending["set"], self.db, self.migration_backup)
                        message = INSTALLED.format(to=pending.get("to"))
                    elif pending.get("kind") == "undo" and ui.SET_RE.match(str(pending.get("set"))):
                        ui.put_back_settings(sets / pending["set"], self.data)
                        ui.mark_undone(sets / pending["set"])
                        message = UNDO_DONE.format(to=pending.get("to"))
                    else:
                        message = None
                except (OSError, store.Invalid) as e:
                    LOG.warning("the end of an update could not be recorded: %s", type(e).__name__)
                    message = None
            else:
                message = result.get("message")
            self._drop(PENDING)
            if isinstance(message, str):
                self._write(NOTICE, {"message": message})
            try:
                update_helper.cleanup_old(self.app)
            except OSError:
                pass
        try:
            ui.prune(self.data, self.version, self.system)
        except OSError:
            pass
        return True

    def watch(self, sleep=time.sleep):
        """At start: settle() as soon as the helper that started this server has finished (the marker is gone)."""
        def run():
            end = self.clock() + WATCH_SECONDS
            while self.clock() < end:
                if self.settle():
                    return
                sleep(0.5)
        threading.Thread(target=run, daemon=True).start()
