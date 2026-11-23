"""The folders asking may read (#47): the logic of GET and POST /api/ask-folders. Unguarded; server.py only routes to it.

The page sends {project, action: "choose" | "remove", path} ("choose" opens the system's folder window; "add" with a path is for other callers) and shows the answer in its own words: (200, {ok, folders, message}) or
(status, {ok: False, code, message}). One more action, "undo" with the apply_id an earlier answer gave, takes a change back.
Every change is one store step, so it is one entry in the history and one Undo. The folder list is the store's `source_folders`
table; the store's own rule (reach.never_inside) is the last check, this module's checks come first and say why in plain words.
"""
import json
import os
import re
import threading
import unicodedata
from pathlib import Path

from clark import ask_exclude, platform, reach, sensitive_names
from clark.store import Invalid, open_store

PROJECT_CODE = re.compile(r"[A-Z][A-Z0-9]{2,6}")
PATH_LIMIT = 1000
MAX_FOLDERS = 20
SHARED_FILE = "ask_folders_all.json"      # row 1294: the folders for all projects, kept beside the data (a list of full paths, in the order they were added)
ACTIONS = ("add", "remove", "undo", "choose", "exclude")
PICK_PROMPT = "Choose a folder asking may read"
WIDE_PLACES = ("/Volumes", "/private/var", "/var", "/private/var/folders", "/private/tmp", "/tmp")   # other disks, and the system's working files (a teammate: LOW)

MESSAGES = {
    "bad_project_code": "That isn't a project clark knows. Nothing was changed.",
    "project_not_found": "That project isn't here. Nothing was changed.",
    "project_archived": "That project is archived. Restore it before changing its folders. Nothing was changed.",
    "bad_request": "That request could not be read. Nothing was changed.",
    "bad_action": "Asking can only add a folder, remove one, or undo the last change. Nothing was changed.",
    "not_a_path": "That isn't a folder on this computer. Use Choose folder to pick one. Nothing was changed.",
    "not_full_path": "That isn't a folder on this computer. Use Choose folder to pick one. Nothing was changed.",
    "dots": "That isn't a folder on this computer. Use Choose folder to pick one. Nothing was changed.",
    "dialog_failed": "The folder window could not be opened. Try Choose folder again. Nothing was changed.",
    "no_window": "The folder window can't open on this computer. Type the folder's location in the box above and press Add folder. Nothing was changed.",
    "no_window_docker": "The folder window needs the Mac, so it can't open when clark runs in Docker. Type the folder's location, as Docker sees it, in the box above and press Add folder. Nothing was changed.",
    "not_a_folder": "That isn't a folder on this computer. Nothing was changed.",
    "home_folder": "Your whole home folder is too wide for asking. Choose a folder inside it. Nothing was changed.",
    "onedrive_root": "The whole of OneDrive is too wide for asking. Choose a folder inside it. Nothing was changed.",
    "top_of_disk": "The top of the disk is too wide for asking. Choose a folder inside it. Nothing was changed.",
    "wide_place": "That folder holds other disks or the computer's own working files, so it is too wide for asking. Choose a folder of your own. Nothing was changed.",
    "pipe_in_name": "That folder's name has a | in it, which asking can't use. Rename it or choose another folder. Nothing was changed.",
    "closed_place": "Asking can't read that folder, because it is, or holds, a place clark keeps closed. Nothing was changed.",
    "too_many": "That is as many folders as asking can have. Remove one first. Nothing was changed.",
    "not_in_list": "That folder isn't in the list. Nothing was changed.",
    "no_undo": "There is nothing to undo there. Nothing was changed.",
    "cant_save": "That folder could not be saved. Try Choose folder again; if it keeps happening, close clark and start it again. Nothing was changed.",
    "added": "Added. Asking may now read the files in that folder.",
    "already": "That folder is already in the list.",
    "all_too_many": "That is as many folders for all projects as asking can have. Remove one first. Nothing was changed.",
    "removed": "Removed. Asking no longer reads that folder.",
    "undone": "Undone.",
}


def same_folder(a, b):
    """Whether two paths name the same folder on disk (os.path.samefile: an identity test, right on a case-sensitive volume too).
    A path that can't be looked at is not the same as anything."""
    try:
        return os.path.samefile(str(a), str(b))
    except (OSError, ValueError, TypeError):
        return False


def shared_folders(data_dir):
    """The folders for all projects (row 1294): read in every project and counted towards each project's MAX_FOLDERS. [] when none are set or the
    file can't be read (it never fails open: a folder not listed is not read)."""
    try:
        got = json.loads((Path(data_dir) / SHARED_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError, RecursionError):
        return []
    return [p for p in got if isinstance(p, str) and p.startswith("/")] if isinstance(got, list) else []


def odd_character(c):
    return unicodedata.category(c).startswith("C") or unicodedata.category(c) in ("Zl", "Zp")


class AskFolders:
    """`db_path` is the database; `onedrive_roots` as the launcher's; `data_dir` is clark's own folder; `home` and `by_user` are
    seams for tests."""

    def __init__(self, db_path, onedrive_roots=None, *, data_dir=None, home=None, by_user=None, choose_folder=None, indexer=None):
        self.db_path = Path(db_path)
        self.onedrive_roots = list(platform.onedrive_roots() if onedrive_roots is None else onedrive_roots)
        self.data_dir = Path(data_dir) if data_dir else self.db_path.parent
        self.home = home
        self.by_user = by_user or platform.login_name
        self.choose_folder = choose_folder or platform.choose_folder      # the system's folder window (a seam for tests)
        self.lock = threading.Lock()
        self.indexer = indexer                                # ask_index.Indexer or None: the background reader of the saved folders (Row 1366)

    def fail(self, code, message=None):
        return {"ok": False, "code": code, "message": message or MESSAGES[code]}

    def store(self):
        return open_store(self.db_path, onedrive_roots=self.onedrive_roots)

    def warned(self, folders, left=None):
        """Row 1365 S2: [{folder, items: [{name, readable_files, dir}]}] for each folder whose names hold a people or contract word (S1 scan, names only).
        `left` is {folder: stored list of left-out subfolders}: those are not named. A list that cannot be read leaves the folder unscanned."""
        out = []
        for f in folders:
            try:
                gone = ask_exclude.parse((left or {}).get(f))
            except ValueError:
                continue
            items = [{"name": h["name"], "readable_files": h["readable_files"], "dir": h["dir"]} for h in sensitive_names.scan(f, gone)]
            if items:
                out.append({"folder": f, "items": items})
        return out

    def listed(self, store, code):
        rows = store.read("source_folders", code)
        return [r["path"] for r in sorted(rows, key=lambda r: (r.get("sort_order") or 0, r["path"]))]

    def left_out(self, store, code):
        """{saved folder: stored list of left-out subfolders} (row 1365)."""
        return {r["path"]: r.get("excluded") for r in store.read("source_folders", code)}

    # ----- GET -----
    def read(self, code):
        if not isinstance(code, str) or not PROJECT_CODE.fullmatch(code):
            return 400, self.fail("bad_project_code")
        with self.lock:
            try:
                store = self.store()
            except Invalid:
                return 409, self.fail("cant_save", "The saved data could not be opened just now. Wait a moment and try again.")
            try:
                if store.read("projects", ref=code) is None:
                    return 404, self.fail("project_not_found")
                out = {"ok": True, "folders": self.listed(store, code), "shared": shared_folders(self.data_dir),
                       "warnings": self.warned(self.listed(store, code), self.left_out(store, code))}
                if self.indexer is not None:
                    out["index"] = self.indexer.status_for(code, [*out["shared"], *out["folders"]])
                return 200, out
            finally:
                store.close()

    # ----- POST -----
    def change(self, body):
        status, out = self._change(body)
        if status == 200 and isinstance(out, dict) and out.get("ok") and isinstance(body, dict) and body.get("action") in ("add", "choose", "remove", "undo"):
            self.reindex([body["project"]])
        return status, out

    def _change(self, body):
        if not isinstance(body, dict):
            return 400, self.fail("bad_request")
        code, action = body.get("project"), body.get("action")
        if not isinstance(code, str) or not PROJECT_CODE.fullmatch(code):
            return 400, self.fail("bad_project_code")
        if action not in ACTIONS:
            return 400, self.fail("bad_action")
        allowed = {"project", "action", "apply_id"} if action == "undo" else {"project", "action"} if action == "choose" else {"project", "action", "path"}   # exclude takes the saved folder's path, like remove
        if set(body) - allowed or (allowed - {"project", "action"}) - set(body):
            return 400, self.fail("bad_request")
        if action == "undo":
            asked = body["apply_id"]
            if type(asked) is not int or not 1 <= asked < 2 ** 63:
                return 400, self.fail("no_undo")
        elif action == "choose":
            asked = None
        else:
            asked = body["path"]
            if not isinstance(asked, str) or not asked or len(asked) > PATH_LIMIT or any(odd_character(c) for c in asked):
                return 400, self.fail("not_a_path")
        with self.lock:
            try:
                store = self.store()
            except Invalid:
                return 409, self.fail("cant_save", "The saved data could not be opened just now. Wait a moment and try again.")
            try:
                row = store.read("projects", ref=code)
                if row is None:
                    return 404, self.fail("project_not_found")
                if row.get("archived"):
                    return 409, self.fail("project_archived")
                if action == "undo":
                    return self.undo(store, code, asked)
                if action == "remove":
                    return self.remove(store, code, asked)
                if action == "exclude":
                    return self.exclude(store, code, asked)
                if action == "choose":
                    return self.choose(store, code)
                return self.add(store, code, asked)
            finally:
                store.close()

    # ----- the folders for all projects (row 1294) -----
    def read_all(self, code=None):
        out = {"ok": True, "folders": shared_folders(self.data_dir)}
        if self.indexer is not None and isinstance(code, str) and PROJECT_CODE.fullmatch(code):
            out["index"] = self.indexer.status_for(code, self.all_folders(code))
        return 200, out

    def all_folders(self, code):
        """What asking reads in project `code`: the folders for all projects, then the project's own (as ask_service.folders_for)."""
        out = []
        try:
            store = self.store()
        except Invalid:
            return list(shared_folders(self.data_dir))
        try:
            own = self.listed(store, code)
        finally:
            store.close()
        for p in [*shared_folders(self.data_dir), *own]:
            if p not in out:
                out.append(p)
        return out[:MAX_FOLDERS]

    def reindex(self, codes):
        """Start the background read for these projects (None: every project that is not archived). Never raises, never waits."""
        if self.indexer is None:
            return
        try:
            if codes is None:
                store = self.store()
                try:
                    codes = [r["code"] for r in store.read("projects") if not r.get("archived")]
                finally:
                    store.close()
            for c in codes:
                self.indexer.start(c, self.all_folders(c))
        except Exception:                                   # noqa: BLE001 the folder change is saved; the read is only a copy
            pass

    def save_shared(self, folders):
        """One atomic write of the list; False when it can't be written. No folder on disk is touched."""
        target = self.data_dir / SHARED_FILE
        part = self.data_dir / (SHARED_FILE + ".part")
        try:
            part.write_text(json.dumps(folders), encoding="utf-8")
            os.replace(part, target)
        except OSError:
            return False
        return True

    def change_all(self, body):
        status, out = self._change_all(body)
        if status == 200 and isinstance(out, dict) and out.get("ok") and isinstance(body, dict) and body.get("action") in ("add", "choose", "remove"):
            self.reindex(None)
        return status, out

    def _change_all(self, body):
        """{scope: "all", action: "add" | "remove" | "choose", path}: the same checks as a project's folder, then the list for all projects."""
        if not isinstance(body, dict) or body.get("scope") != "all":
            return 400, self.fail("bad_request")
        action = body.get("action")
        if action not in ("add", "remove", "choose"):
            return 400, self.fail("bad_action")
        need = {"scope", "action"} if action == "choose" else {"scope", "action", "path"}
        if set(body) != need:
            return 400, self.fail("bad_request")
        asked = None if action == "choose" else body["path"]
        if action != "choose" and (not isinstance(asked, str) or not asked or len(asked) > PATH_LIMIT or any(odd_character(c) for c in asked)):
            return 400, self.fail("not_a_path")
        with self.lock:
            now = shared_folders(self.data_dir)
            if action == "choose":
                start = now[-1] if now else next(iter(self.onedrive_roots), None)
                try:
                    picked = self.choose_folder(PICK_PROMPT, start=start)
                except platform.NotBuiltYet:
                    return 409, self.fail("no_window", MESSAGES["no_window_docker" if platform.container_mode() else "no_window"])
                except platform.PlatformError as e:
                    return 409, self.fail("dialog_failed", platform.refusal_words(e, MESSAGES["dialog_failed"]))
                if picked is None:
                    return 200, {"ok": True, "folders": now}
                asked = str(picked)
                if not asked or len(asked) > PATH_LIMIT or any(odd_character(c) for c in asked):
                    return 400, self.fail("not_a_path")
                action = "add"
            if action == "remove":
                target = asked if asked in now else os.path.realpath(asked) if asked.startswith("/") else None
                if target not in now:
                    return 409, self.fail("not_in_list")
                if not self.save_shared([p for p in now if p != target]):
                    return 409, self.fail("cant_save")
                return 200, {"ok": True, "folders": shared_folders(self.data_dir), "message": MESSAGES["removed"]}
            real, why = self.checked(asked)
            if why:
                return (409 if why in ("not_a_folder", "closed_place") else 400), self.fail(why)
            if any(same_folder(real, p) for p in now):
                return 200, {"ok": True, "folders": now, "message": MESSAGES["already"]}
            if len(now) >= MAX_FOLDERS:
                return 409, self.fail("all_too_many")
            if not self.save_shared([*now, real]):
                return 409, self.fail("cant_save")
            return 200, {"ok": True, "folders": shared_folders(self.data_dir), "message": MESSAGES["added"]}

    def checked(self, typed):
        """(real path, None) for a folder asking may read, else (None, the refusal's code)."""
        if not typed.startswith("/"):
            return None, "not_full_path"
        if ".." in typed.split("/"):
            return None, "dots"
        real = os.path.realpath(typed)                       # links and dots are resolved before anything is judged
        if real == "/":
            return None, "top_of_disk"
        if not os.path.isdir(real):
            return None, "not_a_folder"
        if "|" in real:                                      # the store keys a folder as project|path (a teammate's MEDIUM on #162)
            return None, "pipe_in_name"
        if same_folder(real, reach.home(self.home)):         # by identity, not spelling: APFS ignores case (a teammate's LOW 1)
            return None, "home_folder"
        if any(same_folder(real, r) for r in self.onedrive_roots):
            return None, "onedrive_root"
        if any(same_folder(real, w) for w in WIDE_PLACES):
            return None, "wide_place"
        if reach.never_inside(real, self.data_dir, self.home):
            return None, "closed_place"
        return real, None

    def save(self, store, make):
        try:
            with store.step("dashboard", self.by_user(), place="menu") as st:
                make(st)
                return st.peek_apply_id()
        except Invalid:
            return False

    def add(self, store, code, typed):
        real, why = self.checked(typed)
        if why:
            return (409 if why in ("not_a_folder", "closed_place") else 400), self.fail(why)
        now = self.listed(store, code)
        if any(same_folder(real, p) for p in now):           # the same folder however it is spelt (case, composed accents)
            return 200, {"ok": True, "folders": now, "message": MESSAGES["already"]}
        shared = shared_folders(self.data_dir)
        if any(same_folder(real, p) for p in shared):        # already read in every project
            return 200, {"ok": True, "folders": now, "message": MESSAGES["already"]}
        if len(now) + len(shared) >= MAX_FOLDERS:            # the folders for all projects count towards the project's 20
            return 409, self.fail("too_many")
        order = len(now)
        step = self.save(store, lambda st: st.create("source_folders", {"project": code, "path": real, "sort_order": order}))
        if step is False:
            return 409, self.fail("cant_save")
        return 200, {"ok": True, "folders": self.listed(store, code), "message": MESSAGES["added"], "apply_id": step,
                     "warnings": self.warned([real])}

    def choose(self, store, code):
        """The system's folder window, then the same checks and the same one step as an added folder. Cancelled: nothing changes."""
        now = self.listed(store, code)
        start = now[-1] if now else next(iter(self.onedrive_roots), None)
        try:
            picked = self.choose_folder(PICK_PROMPT, start=start)
        except platform.NotBuiltYet:                         # no window will ever open here: say why, and that a typed location works
            return 409, self.fail("no_window", MESSAGES["no_window_docker" if platform.container_mode() else "no_window"])
        except platform.PlatformError as e:
            return 409, self.fail("dialog_failed", platform.refusal_words(e, MESSAGES["dialog_failed"]))
        if picked is None:
            return 200, {"ok": True, "folders": now}
        typed = str(picked)
        if not typed or len(typed) > PATH_LIMIT or any(odd_character(c) for c in typed):
            return 400, self.fail("not_a_path")
        return self.add(store, code, typed)

    def remove(self, store, code, typed):
        now = self.listed(store, code)
        target = typed if typed in now else os.path.realpath(typed) if typed.startswith("/") else None
        if target not in now:
            return 409, self.fail("not_in_list")
        step = self.save(store, lambda st: st.cancel("source_folders", f"{code}|{target}"))
        if step is False:
            return 409, self.fail("cant_save")
        return 200, {"ok": True, "folders": self.listed(store, code), "message": MESSAGES["removed"], "apply_id": step}

    def exclude(self, store, code, typed):
        """Row 1365: leave out the subfolders the name scan flagged in one saved folder (the server finds them: the page sends only the folder).
        Each is added to the folder's list (at most ask_exclude.MAX_LEFT_OUT); a folder not in the list, or a list that cannot be read, changes nothing.
        One store step, so one Undo. Nothing on disk is touched."""
        now = self.listed(store, code)
        target = typed if typed in now else os.path.realpath(typed) if typed.startswith("/") else None
        if target not in now:
            return 409, self.fail("not_in_list")
        try:
            have = ask_exclude.parse(self.left_out(store, code).get(target))
        except ValueError:
            return 409, self.fail("cant_save")
        found = [h["path_rel"].replace(os.sep, "/") for h in sensitive_names.scan(target, have) if h["dir"]]
        new = sorted(set(have) | {r for r in map(ask_exclude.clean, found) if r})
        if new == sorted(have):
            return 200, {"ok": True, "folders": now, "warnings": self.warned(now, self.left_out(store, code))}
        if len(new) > ask_exclude.MAX_LEFT_OUT:
            return 409, self.fail("cant_save")
        step = self.save(store, lambda st: st.update("source_folders", f"{code}|{target}", {"excluded": ask_exclude.dump(new)}))
        if step is False:
            return 409, self.fail("cant_save")
        return 200, {"ok": True, "folders": now, "apply_id": step, "warnings": self.warned(now, self.left_out(store, code))}

    def undo(self, store, code, step):
        rows = store.step_rows(step)
        mine = rows and all(r["table"] == "source_folders" and str(r["key"]).startswith(code + "|") and r["via"] == "dashboard"
                            for r in rows)
        if not mine:                                         # a missing step, another project's and another route's: one answer
            return 409, self.fail("no_undo")
        try:
            done = store.undo(step, self.by_user(), place="menu")
        except Invalid:
            return 409, self.fail("no_undo")
        if not done.get("reversed"):
            return 409, self.fail("cant_save")
        return 200, {"ok": True, "folders": self.listed(store, code), "message": MESSAGES["undone"]}
