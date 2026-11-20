"""The standing instructions of asking (row 1294, A8): the logic of GET and POST /api/ask-instructions. Unguarded; server.py only routes to it.

There are two texts, each up to INSTRUCTIONS_MAX (4,000) characters: the one for all projects (app_settings.ask_instructions, this computer's) and a
project's own (projects.ask_instructions). Both are sent with every question, the one for all projects first (ask.build_request).
GET /api/ask-instructions?project=CODE answers (200, {ok, all, project, saved, max}); `project` is "" in the answer when none was asked for.
POST takes {scope: "all", text} or {scope: "project", project: CODE, text}, or {undo: apply_id, scope[, project]}. A text that is blank is the same as
none. A text that looks like a password or a key is refused (the one screen of ask.py), so it is never kept to be sent. Every change is one store
step: one entry in History and one Undo. A refused request changes nothing. Every answer is (status, {ok, ...}) with a plain `message`; a refusal
also has a stable `code`.
"""
import re
import threading
import unicodedata
from pathlib import Path

from clark import ask, platform
from clark.store import INSTRUCTIONS_MAX, Invalid, open_store

PROJECT_CODE = re.compile(r"[A-Z][A-Z0-9]{2,6}")
FIELDS = ("ask_instructions", "updated_at")
SCOPES = ("all", "project")

MESSAGES = {
    "bad_request": "That request could not be read. Nothing was changed.",
    "bad_project_code": "That isn't a project clark knows. Nothing was changed.",
    "project_not_found": "That project isn't here. Nothing was changed.",
    "project_archived": "That project is archived. Restore it before changing its standing instructions. Nothing was changed.",
    "too_long": f"Standing instructions can be {INSTRUCTIONS_MAX:,} characters at most. Make them shorter. Nothing was changed.",
    "odd_character": "Standing instructions can hold text, line breaks and tabs only. Nothing was changed.",
    "secret": f"That {ask.LOOKS_LIKE}, so it was not saved. Take it out and try again. Nothing was changed.",
    "no_undo": "There is nothing to undo there. Nothing was changed.",
    "not_ready": "This computer's saved data can't keep that yet. Nothing was changed.",
    "cant_save": "That could not be saved. Wait a moment and try again; if it keeps happening, close clark and start it again. Nothing was changed.",
    "busy": "The saved data could not be opened just now. Wait a moment and try again.",
    "saved": "Saved.",
    "cleared": "Cleared.",
    "same": "That is what is saved already.",
    "undone": "Undone.",
}


def odd_character(c):
    return c not in "\n\t" and (unicodedata.category(c).startswith("C") or unicodedata.category(c) in ("Zl", "Zp"))


class StandingInstructions:
    """`db_path` is the database; `onedrive_roots` as the launcher's; `by_user` is a seam for tests."""

    def __init__(self, db_path, onedrive_roots=None, *, by_user=None):
        self.db_path = Path(db_path)
        self.onedrive_roots = list(platform.onedrive_roots() if onedrive_roots is None else onedrive_roots)
        self.by_user = by_user or platform.login_name
        self.lock = threading.Lock()

    def fail(self, code):
        return {"ok": False, "code": code, "message": MESSAGES[code]}

    def store(self):
        return open_store(self.db_path, onedrive_roots=self.onedrive_roots)

    def answer(self, store, project, message=None, apply_id=None):
        body = {"ok": True, "all": store.ask_instructions(), "project": store.ask_instructions(project) if project else "",
                "saved": store.settings_ready(), "max": INSTRUCTIONS_MAX}
        if message:
            body["message"] = message
        if apply_id:
            body["apply_id"] = apply_id
        return 200, body

    def problem(self, store, project):
        """The refusal (status, body) when `project` can't be changed or read, or None."""
        if project == "":
            return None
        if not isinstance(project, str) or not PROJECT_CODE.fullmatch(project):
            return 400, self.fail("bad_project_code")
        row = store.read("projects", ref=project)
        if row is None:
            return 404, self.fail("project_not_found")
        return None

    def read(self, project=""):
        with self.lock:
            try:
                store = self.store()
            except Invalid:
                return 409, self.fail("busy")
            try:
                refused = self.problem(store, project)
                return refused or self.answer(store, project)
            finally:
                store.close()

    def valid_text(self, text):
        """None when `text` can be kept, else the refusal's code."""
        if not isinstance(text, str):
            return "bad_request"
        if len(text) > INSTRUCTIONS_MAX:
            return "too_long"
        if any(odd_character(c) for c in text):
            return "odd_character"
        if text.strip() and ask.looks_secret(text):
            return "secret"
        return None

    def undo_ok(self, store, step, table, key):
        rows = store.step_rows(step)
        return bool(rows) and all(r["table"] == table and str(r["key"]) == key and r["field"] in FIELDS and r["via"] == "dashboard" for r in rows)

    def change(self, body):
        if not isinstance(body, dict):
            return 400, self.fail("bad_request")
        scope = body.get("scope")
        if scope not in SCOPES:
            return 400, self.fail("bad_request")
        if set(body) == {"scope", "undo"} or set(body) == {"scope", "project", "undo"}:
            asked, text = body["undo"], None
            if type(asked) is not int or not 1 <= asked < 2 ** 63:
                return 400, self.fail("no_undo")
        elif set(body) == {"scope", "text"} or set(body) == {"scope", "project", "text"}:
            asked, text = None, body["text"]
        else:
            return 400, self.fail("bad_request")
        project = body.get("project", "")
        if (scope == "project") != ("project" in body) or (scope == "project" and not project):
            return 400, self.fail("bad_request")
        if text is not None:
            bad = self.valid_text(text)
            if bad:
                return 400, self.fail(bad)
            text = text if text.strip() else ""
        with self.lock:
            try:
                store = self.store()
            except Invalid:
                return 409, self.fail("busy")
            try:
                refused = self.problem(store, project)
                if refused:
                    return refused
                table, key = ("app_settings", "1") if scope == "all" else ("projects", project)
                if not store.settings_ready():
                    return 409, self.fail("not_ready")
                if asked is not None:
                    done = None
                    if self.undo_ok(store, asked, table, key):
                        try:
                            done = store.undo(asked, self.by_user(), place="menu")
                        except Invalid:
                            done = None
                    if not done or not done.get("reversed"):
                        return 409, self.fail("no_undo")
                    return self.answer(store, project, MESSAGES["undone"])
                if scope == "project" and store.read("projects", ref=project).get("archived"):
                    return 409, self.fail("project_archived")
                if store.ask_instructions(project if scope == "project" else None) == text:
                    return self.answer(store, project, MESSAGES["same"])
                try:
                    with store.step("dashboard", self.by_user(), place="menu") as st:
                        st.update(table, key, {"ask_instructions": text})
                        step = st.peek_apply_id()
                except Invalid:
                    return 409, self.fail("cant_save")
                return self.answer(store, project, MESSAGES["saved" if text else "cleared"], step)
            finally:
                store.close()
