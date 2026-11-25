"""The slash commands of ask clark (row 1295): the logic of GET and POST /api/ask-commands. Unguarded; server.py only routes to it.

Rules and files are ask_commands.py's. There are two folders: the commands for all projects (`ask-commands` in clark's data folder) and a project's
own (`ask-commands/<CODE>`); a project's command with the same name wins in that project (the page does that). GET /api/ask-commands?project=CODE
answers (200, {ok, all, project, damaged, max, builtins}). POST takes {scope: "all" | "project", project?, action: "save" | "remove" | "reset", ...}:
save {record, was?}, remove {name}, reset {name}, fix {name: a file name from `damaged`} (row 1435: a local repair, the old file kept as `<name>.old`; the
answer has `fixed: {kept, left_out}`), unfix {name} (Undo of the fix). A text that looks like a password or a key is refused before anything is written (the one screen of
ask.py), so it is never kept to be sent. Every answer is (status, {ok, ...}) with a plain `message`; a refusal also has a stable `code`.
Nothing here asks a model or changes a report: a slash command is text, and what it asks is screened as any typed question is.
"""
import re
import threading
from pathlib import Path

from clark import ask, ask_commands as ac

PROJECT_CODE = re.compile(r"[A-Z][A-Z0-9]{2,6}")
# The built-in names (page/src/edit/askSlash.js COMMANDS; a test pins that the two lists are the same).
BUILTIN_NAMES = ("check", "summary", "overdue", "risks", "milestones", "usecases", "history", "new")
ACTIONS = ("save", "remove", "reset", "fix", "unfix")

MESSAGES = {
    "bad_request": "That request could not be read. Nothing was changed.",
    "bad_project_code": "That isn't a project clark knows. Nothing was changed.",
    "secret": "That %s, so it was not saved. Take it out and try again. Nothing was changed." % ask.LOOKS_LIKE,
    "saved": "Saved.",
    "removed": "Removed.",
    "reset": "Back to the built-in.",
    "fixed": "Fixed: %d lines kept, %d left out. The old file is kept.",       # approved, row 1435 (words log of 24-11 21:1x)
    "cant_fix": "Could not fix the file. The old file is kept.",
    "cant_save": "That could not be saved. Wait a moment and try again; if it keeps happening, close clark and start it again. Nothing was changed.",
}


class AskCommandsService:
    """`data_dir` is clark's data folder (the one that holds the saved data)."""

    def __init__(self, data_dir):
        self.data_dir = Path(data_dir)
        self.lock = threading.Lock()

    def fail(self, code, message=None, status=400):
        return status, {"ok": False, "code": code, "message": message or MESSAGES[code]}

    def files(self, scope, project):
        return ac.AskCommands(self.data_dir, BUILTIN_NAMES, "" if scope == "all" else project)

    def answer(self, project, message=None):
        mine, bad = self.files("all", "").read()
        own, own_bad = ([], []) if not project else self.files("project", project).read()
        body = {"ok": True, "all": mine, "project": own, "damaged": {"all": bad, "project": own_bad}, "max": ac.MAX_SHORTCUTS,
                "builtins": list(BUILTIN_NAMES)}
        if message:
            body["message"] = message
        return 200, body

    def read(self, project=""):
        if project != "" and not (isinstance(project, str) and PROJECT_CODE.fullmatch(project)):
            return self.fail("bad_project_code")
        with self.lock:
            return self.answer(project)

    def change(self, body):
        if not isinstance(body, dict) or body.get("scope") not in ("all", "project") or body.get("action") not in ACTIONS:
            return self.fail("bad_request")
        scope, action, project = body["scope"], body["action"], body.get("project", "")
        if (scope == "project") != ("project" in body):
            return self.fail("bad_request")
        if scope == "project" and not (isinstance(project, str) and PROJECT_CODE.fullmatch(project)):
            return self.fail("bad_project_code")
        rec = body.get("record")
        keys = {"scope", "project", "action", "record", "was", "name"}
        if set(body) - keys:
            return self.fail("bad_request")
        if action == "save":
            if not isinstance(rec, dict) or not isinstance(body.get("was", ""), str):
                return self.fail("bad_request")
            for k in ("name", "menu", "text"):
                if k in rec and not isinstance(rec[k], str):
                    return self.fail("bad_request")
            if any(ask.looks_secret(rec.get(k, "")) for k in ("menu", "text") if rec.get(k, "").strip()):
                return self.fail("secret")
        elif not isinstance(body.get("name"), str):
            return self.fail("bad_request")
        with self.lock:
            files = self.files(scope, project)
            try:
                if action == "fix":
                    kept, left = files.fix(body["name"])
                    status, out = self.answer(project, MESSAGES["fixed"] % (kept, left))
                    out["fixed"] = {"kept": kept, "left_out": left}
                    return status, out
                if action == "unfix":
                    files.unfix(body["name"])
                    return self.answer(project, "")
                if action == "save":
                    files.write(rec, body.get("was") or None)
                elif action == "remove":
                    files.remove(body["name"])
                else:
                    files.reset(body["name"])
            except ac.Refused as e:
                if action in ("fix", "unfix"):
                    return self.fail("cant_fix", status=409)
                return self.fail("refused", str(e), 400)
            except OSError:
                return self.fail("cant_save", status=409)
            return self.answer(project, {"save": MESSAGES["saved"], "remove": MESSAGES["removed"], "reset": MESSAGES["reset"]}[action])
