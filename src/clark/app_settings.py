"""The setting that lives in the database for asking (#47): the logic of /api/ask-enabled. Unguarded; server.py only routes to it,
and the store (store.py) is the only writer.

Row 1269 adds the install's Theme to the same row: GET /api/theme answers {ok, theme, saved} and POST /api/theme takes {"theme": "classic" | "cards"}
or {"undo": apply_id}, with the same refusals and the same one-step-one-Undo as the ask switch. An Undo is accepted only for a step
that changed the Theme, and the ask switch's only for one that changed the switch.
GET /api/ask-enabled answers {ok, ask_enabled, saved}. POST /api/ask-enabled takes {"enabled": true | false} or {"undo": apply_id}.
The switch belongs to this computer, not to a project: nothing is sent to Claude while it is off, wherever clark is opened, because
the ask route itself reads store.ask_enabled() before anything is sent (ask_service.py). `saved` is false for a data file that
cannot keep the switch yet; the switch then reads as off (store.ASK_WHEN_MISSING), and a change is refused in plain words rather
than looking saved.
Every change is one store step, so it is one entry in the history and one Undo. A body with any other field is refused, and so is
anything that is not JSON of the right shape; a refused request changes nothing. Every answer is (status, {ok, ...}) with a plain
`message`; a refusal also has a stable `code`.
"""
import threading
from pathlib import Path

from clark import platform
from clark.store import THEMES, Invalid, open_store

SETTINGS_FIELDS = ("ask_enabled", "updated_at", "theme")
ASK_FIELDS = ("ask_enabled", "updated_at")
THEME_FIELDS = ("theme", "updated_at")

MESSAGES = {
    "bad_request": "That request could not be read. Nothing was changed.",
    "bad_value": "Asking can only be on or off. Nothing was changed.",
    "no_undo": "There is nothing to undo there. Nothing was changed.",
    "not_ready": "This computer's saved data can't keep that setting yet. Nothing was changed.",
    "cant_save": "That could not be saved. Wait a moment and try again; if it keeps happening, close clark and start it again. Nothing was changed.",
    "busy": "The saved data could not be opened just now. Wait a moment and try again.",
    "asking_on": "Asking is on.",
    "asking_off": "Asking is off. Nothing is sent.",
    "bad_theme": "That Theme is not one clark has. Nothing was changed.",
    "same": "That is the setting already in use.",
    "undone": "Undone.",
}


class AppSettings:
    """`db_path` is the database; `onedrive_roots` as the launcher's; `by_user` is a seam for tests."""

    def __init__(self, db_path, onedrive_roots=None, *, by_user=None):
        self.db_path = Path(db_path)
        self.onedrive_roots = list(platform.onedrive_roots() if onedrive_roots is None else onedrive_roots)
        self.by_user = by_user or platform.login_name
        self.lock = threading.Lock()

    def fail(self, code, message=None):
        return {"ok": False, "code": code, "message": message or MESSAGES[code]}

    def store(self):
        return open_store(self.db_path, onedrive_roots=self.onedrive_roots)

    def save(self, store, make):
        """The step's id, or False when the store refused it (nothing is written then)."""
        try:
            with store.step("dashboard", self.by_user(), place="menu") as st:
                make(st)
                return st.peek_apply_id()
        except Invalid:
            return False

    def undo_ok(self, store, step, table, key, fields):
        """True when `step` is one of this module's own changes: every row of it is this table, this key, one of these fields, and
        was written from the dashboard. A missing step, another setting's and another route's all look the same: no undo."""
        rows = store.step_rows(step)
        return bool(rows) and all(r["table"] == table and str(r["key"]) == key and r["field"] in fields and r["via"] == "dashboard"
                                  for r in rows)

    def undo(self, store, step, table, key, fields):
        if not self.undo_ok(store, step, table, key, fields):
            return None
        try:
            done = store.undo(step, self.by_user(), place="menu")
        except Invalid:
            return None
        return done if done.get("reversed") else None

    def valid_step(self, asked):
        return type(asked) is int and 1 <= asked < 2 ** 63

    # ----- the ask switch -----
    def answer_ask(self, store, message=None, apply_id=None):
        body = {"ok": True, "ask_enabled": store.ask_enabled(), "saved": store.settings_ready()}
        if message:
            body["message"] = message
        if apply_id:
            body["apply_id"] = apply_id
        return 200, body

    def read_ask(self, _project=""):
        with self.lock:
            try:
                store = self.store()
            except Invalid:
                return 409, self.fail("busy", MESSAGES["busy"])
            try:
                return self.answer_ask(store)
            finally:
                store.close()

    def change_ask(self, body):
        if not isinstance(body, dict):
            return 400, self.fail("bad_request")
        if set(body) == {"undo"}:
            asked, enabled = body["undo"], None
            if not self.valid_step(asked):
                return 400, self.fail("no_undo")
        elif set(body) == {"enabled"}:
            asked, enabled = None, body["enabled"]
            if type(enabled) is not bool:
                return 400, self.fail("bad_value")
        else:
            return 400, self.fail("bad_request")
        with self.lock:
            try:
                store = self.store()
            except Invalid:
                return 409, self.fail("busy", MESSAGES["busy"])
            try:
                if not store.settings_ready():
                    return 409, self.fail("not_ready")
                if asked is not None:
                    if self.undo(store, asked, "app_settings", "1", ASK_FIELDS) is None:
                        return 409, self.fail("no_undo")
                    return self.answer_ask(store, MESSAGES["undone"])
                if store.ask_enabled() == enabled:
                    return self.answer_ask(store, MESSAGES["same"])
                step = self.save(store, lambda st: st.update("app_settings", "1", {"ask_enabled": enabled}))
                if step is False:
                    return 409, self.fail("cant_save")
                return self.answer_ask(store, MESSAGES["asking_on" if enabled else "asking_off"], step)
            finally:
                store.close()

    # ----- the Theme (row 1269) -----
    def answer_theme(self, store, message=None, apply_id=None):
        body = {"ok": True, "theme": store.theme(), "saved": store.settings_ready()}
        if message:
            body["message"] = message
        if apply_id:
            body["apply_id"] = apply_id
        return 200, body

    def read_theme(self, _project=""):
        with self.lock:
            try:
                store = self.store()
            except Invalid:
                return 409, self.fail("busy", MESSAGES["busy"])
            try:
                return self.answer_theme(store)
            finally:
                store.close()

    def change_theme(self, body):
        if not isinstance(body, dict):
            return 400, self.fail("bad_request")
        if set(body) == {"undo"}:
            asked, theme = body["undo"], None
            if not self.valid_step(asked):
                return 400, self.fail("no_undo")
        elif set(body) == {"theme"}:
            asked, theme = None, body["theme"]
            if type(theme) is not str or theme not in THEMES:
                return 400, self.fail("bad_theme")
        else:
            return 400, self.fail("bad_request")
        with self.lock:
            try:
                store = self.store()
            except Invalid:
                return 409, self.fail("busy", MESSAGES["busy"])
            try:
                if not store.settings_ready():
                    return 409, self.fail("not_ready")
                if asked is not None:
                    if self.undo(store, asked, "app_settings", "1", THEME_FIELDS) is None:
                        return 409, self.fail("no_undo")
                    return self.answer_theme(store, MESSAGES["undone"])
                if store.theme() == theme:
                    return self.answer_theme(store, MESSAGES["same"])
                step = self.save(store, lambda st: st.update("app_settings", "1", {"theme": theme}))
                if step is False:
                    return 409, self.fail("cant_save")
                return self.answer_theme(store, None, step)
            finally:
                store.close()
