"""What POST /api/excel-import does (#444, Settings > Data: Import workbook; guarded: it writes through the one writer).

Like word_route.py (#48) this is the boundary between the browser and the one writer, so both reviewers read it. The server (which
imports nothing from clark) hands a request to a seam made here and sends the (status, body) it returns. It holds NO import logic of
its own: reading a workbook, staging the differences, the clash rules, the export's record and the apply with its one step are
excel_import.py's (#38), the code the command line and the tests of the import already use.

Three ops of one route:
- "check": a workbook (its bytes, as text the page sends) is put in a private temporary folder and read by excel_import.read_workbook
  against the named project. Nothing is written to the database. The reply lists every difference by number, in words (new,
  changed, no longer in the workbook), with the ones that would be refused and the ones that clash with a later change in clark.
  The plan waits in memory (a few at once, for 30 minutes) with its temporary file, which is removed when the plan is applied or
  goes.
- "apply": the person accepts "all" or some numbers. "all" takes the new and changed rows with no problem and no clash (as the
  import always has: a row that is only missing from the workbook, a clash and a problem are accepted by number); the accepted ones
  go in ONE step by the "excel" route through excel_import.apply_import (if any breaks a rule every broken one is named and nothing
  at all is written). A workbook clark did not export is applied only when the request says `confirm` is true, as the import
  requires. The temporary file is read once more by the import (its hash must be what was read) and removed.
- "undo": reverses one workbook import step of the named project, and only an "excel" step, with Store.undo.

The request never names a path: the file's own name is shown in words and used for nothing else. Every message is plain words,
"clark" in lower case and never first. Standard library only, Python 3.9 (the spreadsheet library is the bundled one, imported on
the first check).
"""
import base64
import binascii
import re
import secrets
import shutil
import tempfile
import time
from pathlib import Path

from clark import store as clark_store
from clark import word_import, word_route
from clark.changes import Refused, _call, _shown
from clark.store import Invalid

ROUTE = "excel"                      # the step's route (store.ROUTES); excel_import writes it
MAX_PLANS = 4                        # checks waiting for a decision, at once
PLAN_MINUTES = 30                    # how long one waits
MAX_NAME = 255
OPS = ("check", "apply", "undo")
ALLOWED = {"check": ("op", "project", "name", "data"), "apply": ("op", "project", "plan", "accept", "confirm"),
           "undo": ("op", "project", "apply_id")}
MAX_FILE_BYTES = 25 * 1024 * 1024     # excel.MAX_FILE_BYTES; a test says they agree

NOT_JSON_OBJECT = "That could not be read. Reload the page and try again."
BAD_OP = "That isn't something clark can do with a workbook."
NO_FILE = "Choose a workbook to import."
BAD_NAME = "The file's name could not be read. Choose the workbook again."
BAD_FILE = "That file could not be read. Choose the workbook again."
EXPIRED = "That import is no longer waiting. Choose the workbook again."
BAD_ACCEPT = "Accept all, or give the numbers of the changes to accept."
NEEDS_CONFIRM = ("clark has no record of exporting this workbook, so it is not applied until you confirm it. Check it is the right "
                 "file, then choose Import anyway.")
NO_UNDO = "That step can't be undone from here."
UNDONE = "That step has been undone already."
NOT_APPLIED = "Nothing was changed."

PLANS = {}                           # plan id -> {"project", "plan", "dir", "at"}; used only under changes.LOCK


def _drop(held):
    shutil.rmtree(held["dir"], ignore_errors=True)


def _expire(now):
    for key in [k for k, v in PLANS.items() if now - v["at"] > PLAN_MINUTES * 60]:
        _drop(PLANS.pop(key))


def _shape(req):
    if not isinstance(req, dict):
        raise Refused(NOT_JSON_OBJECT)
    op = req.get("op")
    if not isinstance(op, str) or op not in OPS:
        raise Refused(BAD_OP)
    for k in req:
        if k not in ALLOWED[op]:
            raise Refused(f"That request has something that is not allowed: '{_shown(k)}'.")
    project = req.get("project")
    if not isinstance(project, str) or not re.fullmatch(clark_store.CODE_RE, project):
        raise Refused("Use a project code of 3 to 7 capital letters or digits.", code="bad_project_code")
    return op, project


def _accepted_numbers(value):
    """"all", or a list of positive whole numbers (at most 5,000): the person's choice."""
    if value == "all":
        return "all"
    if not isinstance(value, list) or not value or len(value) > 5000 or any(type(n) is not int or n < 1 for n in value):
        raise Refused(BAD_ACCEPT)
    return sorted(set(value))


def _item(c):
    """One staged change as the page shows it: its number, its words, and whether it is taken by Accept all."""
    return {"n": c.n, "kind": c.kind, "table": c.table, "text": c.describe(), "detail": c.detail() if c.kind == "new" else "",
            "problem": c.problem, "clash": bool(c.clash), "default": not c.problem and not c.clash and c.kind != "removed"}


def _described(plan, key):
    return {"ok": True, "plan": key, "file": plan.file, "counts": plan.counts(), "unchanged": plan.unchanged,
            "items": [_item(c) for c in plan.changes], "problems": [p.message for p in plan.problems], "notes": list(plan.notes),
            "unrecorded": bool(plan.unrecorded), "already_imported": bool(plan.already_imported), "report": plan.report()}


def _check(store, req, project, clock):
    name = req.get("name")
    if not isinstance(name, str) or not name.strip() or len(name) > MAX_NAME:
        raise Refused(BAD_NAME)
    data = req.get("data")
    if not isinstance(data, str) or not data:
        raise Refused(NO_FILE)
    shown = word_import.file_label(name).replace("a Word file", "a workbook")
    if len(data) > MAX_FILE_BYTES * 4 // 3 + 16:                          # said before anything is decoded
        raise Refused(f"{shown} is more than {MAX_FILE_BYTES // 1048576} MB, more than clark will open. A clark export is far smaller. "
                      "Check it is the right file, then choose it again.")
    try:
        raw = base64.b64decode(data, validate=True)
    except (binascii.Error, ValueError):
        raise Refused(BAD_FILE) from None
    now = clock()                                          # the caller (changes._call) holds the one lock, so PLANS is ours here
    _expire(now)
    while len(PLANS) >= MAX_PLANS:
        _drop(PLANS.pop(min(PLANS, key=lambda k: PLANS[k]["at"])))
    folder = Path(tempfile.mkdtemp(prefix="clark-import-"))
    try:
        file = folder / (re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", shown)[:120].rstrip(". ") or "workbook")
        if file.suffix.lower() != ".xlsx":
            file = file.with_name(file.name + ".xlsx")
        file.write_bytes(raw)
        plan = word_route._excel_import().read_workbook(store, file, project)
    except BaseException:
        shutil.rmtree(folder, ignore_errors=True)
        raise
    key = secrets.token_urlsafe(12)
    if plan.already_imported:                              # nothing is staged: nothing to wait for
        shutil.rmtree(folder, ignore_errors=True)
        return 200, _described(plan, None)
    PLANS[key] = {"project": project, "plan": plan, "dir": folder, "at": now}
    return 200, _described(plan, key)


def _apply(store, who, req, project, clock):
    key = req.get("plan")
    accept = _accepted_numbers(req.get("accept"))
    confirm = req.get("confirm", False)
    if confirm is not True and confirm is not False:
        raise Refused(BAD_ACCEPT)
    now = clock()
    _expire(now)
    held = PLANS.get(key) if isinstance(key, str) else None
    if held is None or held["project"] != project:
        raise Refused(EXPIRED, 410, "expired")
    plan = held["plan"]
    if plan.unrecorded and not confirm:
        raise Refused(NEEDS_CONFIRM, 409, "needs_confirm")
    if plan.unrecorded:
        plan.confirm_unrecorded()
    plan.reject_all()                                      # whatever was staged before: only what is accepted now is applied
    if accept == "all":
        plan.accept_all()
    else:
        missing = [n for n in accept if n > len(plan.changes)]
        if missing:
            raise Refused(f"There is no staged change {missing[0]}.")
        plan.accept(*accept)
    done = word_route._excel_import().apply_import(store, plan, who)
    if not done.applied:
        raise Refused(done.message or NOT_APPLIED, 400 if done.problems else 409, "rolled_back" if done.problems else "not_applied")
    PLANS.pop(key, None)                                   # an import is applied once
    _drop(held)
    return 200, {"ok": True, "apply_id": done.step_id, "counts": done.counts, "message": done.message}


def _eligible(rows, project):
    """Whether step rows are a workbook import of THIS project: at least one, every one written by the excel route, and a record of this project."""
    mine = project + "-"
    return bool(rows) and all(r["via"] == ROUTE and str(r["key"]).startswith(mine) for r in rows)


def _undo(store, who, req, project):
    step = req.get("apply_id")
    if type(step) is not int or not 1 <= step < 2 ** 63 or not _eligible(store.step_rows(step), project):
        raise Refused(NO_UNDO)
    try:
        done = store.undo(step, who)
    except Invalid as e:
        text = str(e)
        if "undone already" in text or "undid an undo" in text:
            raise Refused(UNDONE, 409, "undone") from None
        if text.startswith("clark's data is in use"):
            raise Refused(text, 503, "busy") from None
        raise Refused(NO_UNDO) from None
    left = len(done["skipped"])
    words = "Put back as it was before the import." + (f" {left} change(s) were left as they are because they were changed later." if left else "")
    return 200, {"ok": True, "apply_id": done["step_id"], "message": words}


def _do_import(store, who, req, clock):
    op, project = _shape(req)
    if store.read("projects", ref=project) is None:
        raise Refused("There is no project with that code. Check the code, or choose a project from the list.", 404, "project_not_found")
    if op == "check":
        return _check(store, req, project, clock)
    if op == "apply":
        return _apply(store, who, req, project, clock)
    return _undo(store, who, req, project)


def make_excel_import(path, onedrive_roots=None, by_user=None, clock=None):
    """The `excel_import` seam the server calls for POST /api/excel-import, for the database at `path`. `by_user` is a name or a
    function that gives one (as in changes.make_change). `clock` is a seam for tests."""
    clock = clock or time.time

    def excel_import_seam(req):
        return _call(path, onedrive_roots, by_user, lambda store, who, r: _do_import(store, who, r, clock), req)
    return excel_import_seam
