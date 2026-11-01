"""The folders asking may read (#47): the logic of GET and POST /api/ask-folders. Unguarded; server.py only routes to it.

The page sends {project, action: "choose" | "remove", path} ("choose" opens the system's folder window; "add" with a path is for other callers) and shows the answer in its own words: (200, {ok, folders, message}) or
(status, {ok: False, code, message}). One more action, "undo" with the apply_id an earlier answer gave, takes a change back.
Every change is one store step, so it is one entry in the history and one Undo. The folder list is the store's `source_folders`
table; the store's own rule (reach.never_inside) is the last check, this module's checks come first and say why in plain words.
"""
import os
import re
import threading
import unicodedata
from pathlib import Path

from clark import platform, reach
from clark.store import Invalid, open_store

PROJECT_CODE = re.compile(r"[A-Z][A-Z0-9]{2,6}")
PATH_LIMIT = 1000
MAX_FOLDERS = 20
ACTIONS = ("add", "remove", "undo", "choose")
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


def odd_character(c):
    return unicodedata.category(c).startswith("C") or unicodedata.category(c) in ("Zl", "Zp")


class AskFolders:
    """`db_path` is the database; `onedrive_roots` as the launcher's; `data_dir` is clark's own folder; `home` and `by_user` are
    seams for tests."""

    def __init__(self, db_path, onedrive_roots=None, *, data_dir=None, home=None, by_user=None, choose_folder=None):
        self.db_path = Path(db_path)
        self.onedrive_roots = list(platform.onedrive_roots() if onedrive_roots is None else onedrive_roots)
        self.data_dir = Path(data_dir) if data_dir else self.db_path.parent
        self.home = home
        self.by_user = by_user or platform.login_name
        self.choose_folder = choose_folder or platform.choose_folder      # the system's folder window (a seam for tests)
        self.lock = threading.Lock()

    def fail(self, code, message=None):
        return {"ok": False, "code": code, "message": message or MESSAGES[code]}

    def store(self):
        return open_store(self.db_path, onedrive_roots=self.onedrive_roots)

    def listed(self, store, code):
        rows = store.read("source_folders", code)
        return [r["path"] for r in sorted(rows, key=lambda r: (r.get("sort_order") or 0, r["path"]))]

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
                return 200, {"ok": True, "folders": self.listed(store, code)}
            finally:
                store.close()

    # ----- POST -----
    def change(self, body):
        if not isinstance(body, dict):
            return 400, self.fail("bad_request")
        code, action = body.get("project"), body.get("action")
        if not isinstance(code, str) or not PROJECT_CODE.fullmatch(code):
            return 400, self.fail("bad_project_code")
        if action not in ACTIONS:
            return 400, self.fail("bad_action")
        allowed = {"project", "action", "apply_id"} if action == "undo" else {"project", "action"} if action == "choose" else {"project", "action", "path"}
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
                if action == "choose":
                    return self.choose(store, code)
                return self.add(store, code, asked)
            finally:
                store.close()

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
        if len(now) >= MAX_FOLDERS:
            return 409, self.fail("too_many")
        order = len(now)
        step = self.save(store, lambda st: st.create("source_folders", {"project": code, "path": real, "sort_order": order}))
        if step is False:
            return 409, self.fail("cant_save")
        return 200, {"ok": True, "folders": self.listed(store, code), "message": MESSAGES["added"], "apply_id": step}

    def choose(self, store, code):
        """The system's folder window, then the same checks and the same one step as an added folder. Cancelled: nothing changes."""
        now = self.listed(store, code)
        start = now[-1] if now else next(iter(self.onedrive_roots), None)
        try:
            picked = self.choose_folder(PICK_PROMPT, start=start)
        except platform.PlatformError:
            return 409, self.fail("dialog_failed")
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
