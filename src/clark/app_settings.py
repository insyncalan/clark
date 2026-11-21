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
Row 1294 adds GET and POST /api/ask-files in the same way (the Files switch: see the section at the end).
Row 1306 adds GET and POST /api/ask-connectors in the same way (the connector switches: see the section at the end).
Every change is one store step, so it is one entry in the history and one Undo. A body with any other field is refused, and so is
anything that is not JSON of the right shape; a refused request changes nothing. Every answer is (status, {ok, ...}) with a plain
`message`; a refusal also has a stable `code`.
"""
import re
import threading
from pathlib import Path

from clark import ask_connectors, ask_index, ask_words, platform
from clark.store import CODE_RE, CONNECTORS, HIDDEN_CONNECTORS, THEMES, Invalid, columns, open_store

SETTINGS_FIELDS = ("ask_enabled", "updated_at", "theme")
ASK_FIELDS = ("ask_enabled", "updated_at")
THEME_FIELDS = ("theme", "updated_at")
CODE_FULL = re.compile(CODE_RE)
CONNECTOR_FIELDS = ("is_on", "off", "updated_at")
FILES_FIELDS = ("ask_files", "ask_files_off", "updated_at")

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
    "bad_connector": "That is not a connector clark knows. Nothing was changed.",
    "bad_project": "That project is not here. Nothing was changed.",
    "connector_on": "That connector is on for this computer.",
    "connector_off": "That connector is off.",
    "project_off": "That connector is off in this project.",
    "project_allowed": "That connector is no longer kept off in this project.",
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
        if platform.container_mode():             # Row 1293: Settings says asking is not available in Docker
            body["docker"], body["docker_line"] = True, ask_words.DOCKER
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
                if not enabled:
                    ask_index.remove_all(self.db_path.parent)      # Row 1366: asking Off keeps no copy of the folders' text
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
            if type(theme) is not str or theme not in THEMES or theme == "cards":     # row 1363: Cards cannot be chosen any more
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

    # ----- the connector switches (row 1306) -----
    # GET /api/ask-connectors[?project=CODE] answers {ok, saved, connectors: [{id, label, on, off_here}]}: ONLY the connectors found on this computer
    # (ask_connectors discovery), `on` this computer's choice (Off until turned on), `off_here` the project's own turn-off (false without a project).
    # POST takes exactly one of {"id", "on": bool} (this computer's choice for every project), {"project", "id", "off_here": bool} (that project's
    # own turn-off) or {"undo": apply_id}; every POST answers the same list. Only switch state is kept: no token, key, address or connector content is
    # stored or returned. Nothing here reads a connector. Discovery can take a while, so it runs before the lock is taken.
    def found_connectors(self):
        """[(id, label)] of the connectors found here, each id once, only ids the store knows. Never raises."""
        try:
            rows = ask_connectors.list_found()
        except Exception:
            rows = []
        out, seen = [], set()
        for r in rows if isinstance(rows, list) else []:
            cid = r.get("connector") if isinstance(r, dict) else None
            label = r.get("label") if isinstance(r, dict) else None
            if type(cid) is str and cid in CONNECTORS and cid not in HIDDEN_CONNECTORS and cid not in seen and type(label) is str:
                seen.add(cid)
                out.append((cid, label))
        return out

    def answer_connectors(self, store, project=None, message=None, apply_id=None, found=None):
        on = store.connector_switches()
        off_here = set(store.project_connectors_off(project)) if project else set()
        out = [{"id": c, "label": label, "on": bool(on[c]), "off_here": c in off_here}
               for c, label in (self.found_connectors() if found is None else found)]
        body = {"ok": True, "saved": store.connectors_ready(), "connectors": out}
        if message:
            body["message"] = message
        if apply_id:
            body["apply_id"] = apply_id
        return 200, body

    def project_known(self, store, project):
        return type(project) is str and bool(store.con.execute("SELECT 1 FROM projects WHERE code = ?", (project,)).fetchone())

    def read_connectors(self, project=None):
        if project is not None and (type(project) is not str or not CODE_FULL.fullmatch(project)):
            return 400, self.fail("bad_project")
        found = self.found_connectors()
        with self.lock:
            try:
                store = self.store()
            except Invalid:
                return 409, self.fail("busy", MESSAGES["busy"])
            try:
                if project is not None and not self.project_known(store, project):
                    return 404, self.fail("bad_project")
                return self.answer_connectors(store, project, found=found)
            finally:
                store.close()

    def change_connectors(self, body):
        if not isinstance(body, dict):
            return 400, self.fail("bad_request")
        keys = set(body)
        if keys == {"undo"}:
            if not self.valid_step(body["undo"]):
                return 400, self.fail("no_undo")
            kind, asked = "undo", body["undo"]
        elif keys == {"id", "on"}:
            kind, asked = "global", None
            if type(body["on"]) is not bool:
                return 400, self.fail("bad_value")
        elif keys == {"id", "project", "off_here"}:
            kind, asked = "project", None
            if type(body["off_here"]) is not bool:
                return 400, self.fail("bad_value")
            if type(body["project"]) is not str or not CODE_FULL.fullmatch(body["project"]):
                return 400, self.fail("bad_project")
        else:
            return 400, self.fail("bad_request")
        if kind != "undo" and (type(body["id"]) is not str or body["id"] not in CONNECTORS or body["id"] in HIDDEN_CONNECTORS):
            return 400, self.fail("bad_connector")
        found = self.found_connectors()
        turning_off = (kind == "global" and body["on"] is False) or (kind == "project" and body["off_here"] is True)
        if kind != "undo" and not turning_off and body["id"] not in [c for c, _l in found]:
            return 400, self.fail("bad_connector")      # a connector that is not set up on this computer cannot be turned On; an Off always works (also when discovery fails)
        with self.lock:
            try:
                store = self.store()
            except Invalid:
                return 409, self.fail("busy", MESSAGES["busy"])
            try:
                if not store.connectors_ready():
                    return 409, self.fail("not_ready")
                if kind == "undo":
                    undone = self.undo_connector(store, asked)
                    if not undone:
                        return 409, self.fail("no_undo")
                    return self.answer_connectors(store, undone[1], MESSAGES["undone"], found=found)
                name = body["id"]
                if kind == "global":
                    if store.connector_switches()[name] == body["on"]:
                        return self.answer_connectors(store, None, MESSAGES["same"], found=found)
                    step = self.save(store, lambda st: st.update("connector_switches", name, {"is_on": body["on"]}))
                    if step is False:
                        return 409, self.fail("cant_save")
                    return self.answer_connectors(store, None, MESSAGES["connector_on" if body["on"] else "connector_off"], step, found=found)
                project = body["project"]
                if not self.project_known(store, project):
                    return 404, self.fail("bad_project")
                now_off = name in store.project_connectors_off(project)
                if now_off == body["off_here"]:
                    return self.answer_connectors(store, project, MESSAGES["same"], found=found)
                have = store.con.execute("SELECT 1 FROM project_connectors WHERE project_id = ? AND connector = ?", (project, name)).fetchone()
                if have:
                    make = lambda st: st.update("project_connectors", f"{project}|{name}", {"off": body["off_here"]})
                else:
                    make = lambda st: st.create("project_connectors", {"project_id": project, "connector": name, "off": body["off_here"]})
                step = self.save(store, make)
                if step is False:
                    return 409, self.fail("cant_save")
                return self.answer_connectors(store, project, MESSAGES["project_off" if body["off_here"] else "project_allowed"], step, found=found)
            finally:
                store.close()

    def undo_connector(self, store, step):
        """(True, project or None) when `step` was one of this route's own changes and is now undone, else None."""
        rows = store.step_rows(step)
        if not rows or not all(r["table"] in ("connector_switches", "project_connectors") and r["via"] == "dashboard"
                               and (r["field"] in CONNECTOR_FIELDS or r["field"] in ("project_id", "connector")) for r in rows):
            return None
        project = next((str(r["key"]).split("|")[0] for r in rows if r["table"] == "project_connectors"), None)
        try:
            done = store.undo(step, self.by_user(), place="menu")
        except Invalid:
            return None
        return (True, project) if done.get("reversed") else None


    # ----- the Files switch (row 1294) -----
    # GET /api/ask-files[?project=CODE] answers {ok, saved, on, off_here, allowed}: `on` is this computer's switch (On until turned off), `off_here` the project's own
    # turn-off (false without a project), `allowed` is on and not off_here (false without a project). POST takes exactly one of {"on": bool} (every project),
    # {"project", "off_here": bool} (that project alone) or {"undo": apply_id}; every POST answers the same body. Only the two flags are kept. The ask route reads
    # the same two flags again for every question that carries files (ask_service.py), so a stale page cannot send one.
    def answer_files(self, store, project=None, message=None, apply_id=None):
        on = store.ask_files_on()
        off_here = bool(project) and store.ask_files_off_here(project)
        body = {"ok": True, "saved": "ask_files" in columns(store.con, "app_settings") and store.settings_ready(), "on": on, "off_here": off_here,
                "allowed": bool(project) and on and not off_here}
        if message:
            body["message"] = message
        if apply_id:
            body["apply_id"] = apply_id
        return 200, body

    def read_files(self, project=None):
        if project is not None and (type(project) is not str or not CODE_FULL.fullmatch(project)):
            return 400, self.fail("bad_project")
        with self.lock:
            try:
                store = self.store()
            except Invalid:
                return 409, self.fail("busy", MESSAGES["busy"])
            try:
                if project is not None and not self.project_known(store, project):
                    return 404, self.fail("bad_project")
                return self.answer_files(store, project)
            finally:
                store.close()

    def change_files(self, body):
        if not isinstance(body, dict):
            return 400, self.fail("bad_request")
        keys = set(body)
        if keys == {"undo"}:
            if not self.valid_step(body["undo"]):
                return 400, self.fail("no_undo")
            kind = "undo"
        elif keys == {"on"}:
            kind = "global"
            if type(body["on"]) is not bool:
                return 400, self.fail("bad_value")
        elif keys == {"project", "off_here"}:
            kind = "project"
            if type(body["off_here"]) is not bool:
                return 400, self.fail("bad_value")
            if type(body["project"]) is not str or not CODE_FULL.fullmatch(body["project"]):
                return 400, self.fail("bad_project")
        else:
            return 400, self.fail("bad_request")
        with self.lock:
            try:
                store = self.store()
            except Invalid:
                return 409, self.fail("busy", MESSAGES["busy"])
            try:
                if not store.settings_ready() or "ask_files" not in columns(store.con, "app_settings"):
                    return 409, self.fail("not_ready")
                if kind == "undo":
                    rows = store.step_rows(body["undo"])
                    project = next((str(r["key"]) for r in rows if r["table"] == "projects"), None)
                    if not rows or not all((r["table"], str(r["key"])) in (("app_settings", "1"), ("projects", project)) and r["field"] in FILES_FIELDS
                                           and r["via"] == "dashboard" for r in rows):
                        return 409, self.fail("no_undo")
                    try:
                        done = store.undo(body["undo"], self.by_user(), place="menu")
                    except Invalid:
                        return 409, self.fail("no_undo")
                    if not done.get("reversed"):
                        return 409, self.fail("no_undo")
                    return self.answer_files(store, project, MESSAGES["undone"])
                if kind == "global":
                    if store.ask_files_on() == body["on"]:
                        return self.answer_files(store, None, MESSAGES["same"])
                    step = self.save(store, lambda st: st.update("app_settings", "1", {"ask_files": 1 if body["on"] else 0}))
                    if step is False:
                        return 409, self.fail("cant_save")
                    return self.answer_files(store, None, None, step)
                project = body["project"]
                if not self.project_known(store, project):
                    return 404, self.fail("bad_project")
                if store.ask_files_off_here(project) == body["off_here"]:
                    return self.answer_files(store, project, MESSAGES["same"])
                step = self.save(store, lambda st: st.update("projects", project, {"ask_files_off": 1 if body["off_here"] else 0}))
                if step is False:
                    return 409, self.fail("cant_save")
                return self.answer_files(store, project, None, step)
            finally:
                store.close()
