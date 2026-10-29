"""What the Word routes do: the logic behind POST /api/word-import and POST /api/word-export (#48; guarded; BRD FR-72, FR-82,
FR-43a; design-48-word.md sections 4 and 9; the Head's rulings on Q2, Q4 and Q6).

Like changes.py this is the boundary between the browser and the one writer, so it is read by both reviewers. The server (which
imports nothing from clark) hands a request to a seam made here and sends the (status, body) it returns.

Import, in three ops of one route:
- "check": a Word file (its bytes, as text the page sends) is read by docx_read and staged by word_import. Nothing is written.
  The plan waits in memory (a few at once, for 30 minutes) and the reply lists the new items by number.
- "apply": the person accepts "all" or some numbers. The accepted items go in ONE step by the "word" route through
  excel_import._try (the import path's refuse-and-rollback: if any row breaks a rule every broken one is named and nothing
  at all is written), so one Undo reverses the lot. Each item's history says "Added from Word (<file name>)" (the step's
  src_ref) under the person's name. Only new items are made, each with client_visible off; there is no path that changes,
  closes or removes an item. The fingerprints of what was made go to word-import-state.json beside clark.db (ids and
  fingerprints only, never any text) so the same content is not added twice.
- "undo": reverses one Word import step, and only a Word import step.

Export (POST /api/word-export): the report's published rows (publish.select, so only what is published) become a Word file
(docx_build) named {CODE}-report-{date}.docx. It is written to the project's report folder (the one last published to, else one
the person chooses in the system's own dialog; the request never names a folder or a file) with platform.write_file, read back
and compared. A name that is taken asks first (nothing is written until the person says Add a number, Replace it or Cancel).
Only "to_client": true also copies it into the client folder saved in Settings (checked first, with to_client.preflight, before
anything is written; a name taken there is always given a number, never replaced); a copy that does not match is taken back.
One publications row (word 1, the file's SHA-256) records it, with the client copy's path when there is a verified one.

Every message is plain words (no file-format terms), "clark" in lower case and never first. Standard library only, Python 3.9.
"""
import base64
import binascii
import hashlib
import json
import os
import re
import secrets
import time
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from clark import docx_build, docx_read, milestones, platform, publish, to_client, word_import
from clark import store as clark_store
from clark.changes import Refused, _call, _shown
from clark.store import Invalid

ROUTE = "word"                       # the step's route (store.ROUTES)
STATE_FILE = "word-import-state.json"
MAX_REMEMBERED = 50_000              # fingerprints kept in the state file
MAX_PLANS = 4                        # imports waiting for a decision, at once
PLAN_MINUTES = 30                    # how long one waits
MAX_NAME = 255
IMPORT_KEYS = ("op", "project", "name", "data", "plan", "accept", "apply_id")
OPS = ("check", "apply", "undo")
TABLE_OF_KEY = {"A": "actions", "R": "raid", "D": "decisions"}

NOT_JSON_OBJECT = "That could not be read. Reload the page and try again."
BAD_OP = "That isn't something clark can do with a Word file."
NO_FILE = "Choose a Word file to import."
BAD_NAME = "The file's name could not be read. Choose the Word file again."
BAD_FILE = "That file could not be read. Choose the Word file again."
EXPIRED = "That import is no longer waiting. Choose the Word file again."
BAD_ACCEPT = "Accept all, or give the numbers of the items to accept."
NOTHING_ACCEPTED = "Nothing was accepted, so nothing was added."
NO_UNDO = "That step can't be undone from here."
UNDONE = "That step has been undone already."
NOT_RECORDED = ("{file} was added, but clark could not note that in its list of imports, so importing the same file again may add "
                "the same items twice.")
ALL_SEEN = "Everything in {file} has been added already, so nothing was added."
SOME_SEEN = " {n} item(s) were added from this content a moment ago, so they were not added again."

PLANS = {}                           # plan id → {"project", "plan", "file", "at"}; used only under changes.LOCK


# ── The record of what was made ───────────────────────────────────────────────

def state_path(store):
    return Path(store.path).parent / STATE_FILE


def _load_state(store):
    """[{"fp", "id", "table"}, ...] from word-import-state.json; [] when there is none or it can't be read."""
    try:
        got = json.loads(state_path(store).read_text(encoding="utf-8"))
        rows = got.get("created") if isinstance(got, dict) else None
        return [r for r in rows or [] if isinstance(r, dict) and isinstance(r.get("fp"), str) and isinstance(r.get("id"), str)
                and r.get("table") in TABLE_OF_KEY.values()]
    except (OSError, ValueError):
        return []


def seen_fingerprints(store):
    """The fingerprints of rows an earlier import made that are still in clark: an Undo that took a row back lets the same
    content be added again."""
    out = set()
    for r in _load_state(store):
        try:
            if store.read(r["table"], ref=r["id"]) is not None:
                out.add(r["fp"])
        except Invalid:
            continue
    return out


def _remember(store, made):
    """Add [{"fp", "id", "table"}] to the state file, with platform.write_file. Raises OSError or PlatformError."""
    rows = (_load_state(store) + made)[-MAX_REMEMBERED:]
    platform.write_file(state_path(store), json.dumps({"created": rows}, ensure_ascii=False, indent=0) + "\n")


# ── Reading a request ─────────────────────────────────────────────────────────

def _shape(req):
    if not isinstance(req, dict):
        raise Refused(NOT_JSON_OBJECT)
    for k in req:
        if k not in IMPORT_KEYS:
            raise Refused(f"That request has something that is not allowed: '{_shown(k)}'.")
    op = req.get("op")
    if not isinstance(op, str) or op not in OPS:
        raise Refused(BAD_OP)
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


def _expire(now):
    for key in [k for k, v in PLANS.items() if now - v["at"] > PLAN_MINUTES * 60]:
        del PLANS[key]


def _described(plan):
    return {"file": plan.file, "items": [{"n": i.n, "table": i.table, "where": i.where, "text": i.describe()} for i in plan.items],
            "problems": [p.message for p in plan.problems], "notes": list(plan.notes), "already_added": plan.already_created,
            "report": plan.report()}


# ── The three ops ─────────────────────────────────────────────────────────────

def _check(store, req, project, today, clock):
    name = req.get("name")
    if not isinstance(name, str) or not name.strip() or len(name) > MAX_NAME:
        raise Refused(BAD_NAME)
    data = req.get("data")
    if not isinstance(data, str) or not data:
        raise Refused(NO_FILE)
    shown = word_import.file_label(name)
    if len(data) > docx_read.MAX_FILE_BYTES * 4 // 3 + 16:                # said before anything is decoded
        raise Refused(f"{shown} is more than {docx_read.MAX_FILE_BYTES // 1048576} MB, more than clark will open.")
    try:
        raw = base64.b64decode(data, validate=True)
    except (binascii.Error, ValueError):
        raise Refused(BAD_FILE) from None
    try:
        read = docx_read.read(raw, shown)
    except docx_read.WordRefused as e:
        raise Refused(str(e)) from None
    plan = word_import.stage(read, shown, today, seen_fingerprints(store))
    now = clock()                                        # the caller (changes._call) holds the one lock, so PLANS is ours here
    _expire(now)
    while len(PLANS) >= MAX_PLANS:
        del PLANS[min(PLANS, key=lambda k: PLANS[k]["at"])]
    key = secrets.token_urlsafe(12)
    PLANS[key] = {"project": project, "plan": plan, "file": shown, "at": now}
    return 200, {"ok": True, "plan": key, **_described(plan)}


@lru_cache(maxsize=None)
def _excel_import():
    """clark.excel_import, imported when the first Word import is applied: it reads Excel files, so it needs the bundled
    openpyxl that whoever starts clark puts on the path (__main__ does), and a page that only exports to Word, or a test of the
    server, never needs it."""
    from clark import excel_import
    return excel_import


@lru_cache(maxsize=None)
def _row_class():
    """_Row: a staged Word item as the import path's writer takes it (a new row), with the words that name it if it breaks a rule."""
    @dataclass
    class _Row(_excel_import().StagedChange):
        text: str = ""

        @property
        def label(self):
            return self.text
    return _Row


def _rows(plan, project, accepted):
    row = _row_class()
    return [row(n=i.n, kind="new", table=i.table, sheet=i.where, row=0, after={**i.values, "project": project}, fp=i.fp,
                text=i.label) for i in accepted]


def _apply(store, who, req, project, clock):
    key = req.get("plan")
    accept = _accepted_numbers(req.get("accept"))
    now = clock()
    _expire(now)
    held = PLANS.get(key) if isinstance(key, str) else None
    if held is None or held["project"] != project:
        raise Refused(EXPIRED, 410, "expired")
    plan, file = held["plan"], held["file"]
    for item in plan.items:
        item.state = "waiting"
    if accept == "all":
        plan.accept_all()
    else:
        missing = [n for n in accept if n > len(plan.items)]
        if missing:
            raise Refused(f"There is no staged item {missing[0]}.")
        plan.accept(*accept)
    taken = seen_fingerprints(store)                                     # another import may have made the same rows since
    chosen = [i for i in plan.accepted() if i.fp not in taken]
    skipped = len(plan.accepted()) - len(chosen)
    if not chosen:
        raise Refused(ALL_SEEN.format(file=file) if skipped else NOTHING_ACCEPTED, 409, "nothing_to_add")
    src = re.sub(r"\s+", " ", f"Added from Word ({file})")[:300]
    made = {}
    problems, step_id, refused = _excel_import()._try(store, _rows(plan, project, chosen), who, commit=True, src_ref=src,
                                                      made=made, route=ROUTE, place=None)
    if refused:
        raise Refused(f"Nothing was added, because clark could not start the import: {refused}", 503, "busy")
    if problems:
        names = "; ".join(p.message for p in problems)
        raise Refused(f"Nothing was added, because {len(problems)} item(s) break a rule: {names} Choose fewer items, or fix them in "
                      "the Word file and import it again.", 400, "rolled_back")
    note = ""
    try:
        _remember(store, [{"fp": i.fp, "id": made[i.n], "table": i.table} for i in chosen if i.n in made])
    except (OSError, platform.PlatformError, ValueError):
        note = " " + NOT_RECORDED.format(file=file)
    PLANS.pop(key, None)                                                 # an import is applied once
    count = len(chosen)
    words = f"Added {count} new item(s) from {file} as one step you can undo. They are not shown to the client until you turn " \
            "them on." + (SOME_SEEN.format(n=skipped) if skipped else "") + note
    return 200, {"ok": True, "apply_id": step_id, "added": [made[i.n] for i in chosen if i.n in made], "message": words}


def _eligible(rows, project):
    """Whether step rows are a Word import of THIS project: at least one, every one written by the word route, in a table a Word
    import makes, and an item of this project."""
    mine = project + "-"
    return bool(rows) and all(r["via"] == ROUTE and r["table"] in TABLE_OF_KEY.values() and str(r["key"]).startswith(mine)
                              for r in rows)


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
    removed = len({e["ref"] for e in done["reversed"] if e["change"] == "removed"})
    left = len(done["skipped"])
    words = f"Put back: {removed} item(s) from the Word import were removed." + \
            (f" {left} change(s) were left as they are because they were changed later." if left else "")
    return 200, {"ok": True, "apply_id": done["step_id"], "message": words}


def _do_import(store, who, req, today, clock):
    op, project = _shape(req)
    if store.read("projects", ref=project) is None:
        raise Refused("There is no project with that code. Check the code in the address, or choose a project from the list.",
                      404, "project_not_found")
    allowed = {"check": ("op", "project", "name", "data"), "apply": ("op", "project", "plan", "accept"),
               "undo": ("op", "project", "apply_id")}[op]
    for k in req:
        if k not in allowed:
            raise Refused(f"That request has something that is not allowed here: '{_shown(k)}'.")
    if op == "check":
        return _check(store, req, project, today(), clock)
    if op == "apply":
        return _apply(store, who, req, project, clock)
    return _undo(store, who, req, project)


def make_word_import(path, onedrive_roots=None, by_user=None, today=None, clock=None):
    """The `word_import` seam the server calls for POST /api/word-import, for the database at `path`. `by_user` is a name or a
    function that gives one (as in changes.make_change). `today` and `clock` are seams for tests."""
    today = today or milestones.today
    clock = clock or time.time

    def word_import_seam(req):
        return _call(path, onedrive_roots, by_user, lambda store, who, r: _do_import(store, who, r, today, clock), req)
    return word_import_seam


# ── The export ────────────────────────────────────────────────────────────────

EXPORT_KEYS = ("project", "to_client", "on_clash", "confirmed")
CLASHES = ("number", "overwrite", "cancel")
CHOOSE_FOLDER = "Choose the folder for the Word report"

BAD_FLAG = "That must be true or false."
BAD_CLASH = "That isn't a choice clark offers. Choose Add a number, Replace it or Cancel."
NO_CLIENT_FOLDER = "No client folder yet. Set it in Settings."
OVERWRITE_UNCONFIRMED = "Replacing a file needs your confirmation, and the request didn't carry it. Nothing was saved."
NAME_TAKEN = "A file called “{name}” is already in {where}. Nothing was saved yet."
APPEARED = "A file called “{name}” appeared in {where} while clark was working. Nothing was saved; try again to choose what to do."
FOLDER_GONE = "The folder “{name}” isn't there, or clark can't write to it. Check it, or choose another folder."
FOLDER_DATA = "That folder is inside clark's own data folder. Choose a folder for reports."
NOT_SAVED = "{name} could not be saved ({reason}). If it is open in Word, close it and try again. Nothing was written."
NOT_AS_MADE = "{name} was not saved as it was made (the folder may be syncing), so it was taken back. Try again."
NOT_AS_MADE_REPLACED = "{name} was replaced, but what was saved did not match what clark made (the folder may be syncing). Save it again."
SAVED = "Saved “{name}” in {folder}."
SAVED_CLIENT = " It was also copied to the client folder as “{name}”. OneDrive uploads it from there; clark can't see when that finishes."
CLIENT_FAILED = " It was not copied to the client folder: {reason} Nothing was added to the client folder."
NOT_RECORDED_FILE = " The file is fine, but clark could not record it ({reason}); save it again to record it."
CANCELLED = "Cancelled. Nothing was saved."


class _ReadFs:
    """The facts about a folder that to_client.preflight asks for. It reads and never writes."""

    def exists(self, path):
        return os.path.exists(path)

    def is_dir(self, path):
        return os.path.isdir(path)

    def writable(self, path):
        return os.access(path, os.W_OK | os.X_OK)

    def realpath(self, path):
        return os.path.realpath(path)


def _names_in(folder):
    """{name in lower case: is a folder} for what is in `folder`."""
    with os.scandir(folder) as it:
        return {e.name.lower(): e.is_dir() for e in it}


def _export_shape(req):
    if not isinstance(req, dict):
        raise Refused(NOT_JSON_OBJECT)
    for k in req:
        if k not in EXPORT_KEYS:
            raise Refused(f"That request has something that is not allowed: '{_shown(k)}'. clark chooses the folders itself.")
    project = req.get("project")
    if not isinstance(project, str) or not re.fullmatch(clark_store.CODE_RE, project):
        raise Refused("Use a project code of 3 to 7 capital letters or digits.", code="bad_project_code")
    for flag in ("to_client", "confirmed"):
        if flag in req and not isinstance(req[flag], bool):
            raise Refused(BAD_FLAG)
    clash = req.get("on_clash")
    if clash is not None and (not isinstance(clash, str) or clash not in CLASHES):
        raise Refused(BAD_CLASH)
    if clash == "overwrite" and req.get("confirmed") is not True:
        raise Refused(OVERWRITE_UNCONFIRMED)
    return project, req.get("to_client", False), clash


def _usable_local(folder):
    """The folder as a Path if clark may save a report there, else None."""
    try:
        path = Path(folder)
        ok = path.is_absolute() and path.is_dir() and os.access(path, os.W_OK | os.X_OK)
    except (OSError, ValueError):
        return None
    return path if ok else None


def _outside_data(path, data):
    """Whether `path` is neither clark's data folder `data` nor inside it nor holding it."""
    data = Path(data).resolve()
    here = Path(path).resolve()
    return not (here == data or data in here.parents or here in data.parents)


def _verified(dest, digest):
    try:
        return hashlib.sha256(dest.read_bytes()).hexdigest() == digest
    except OSError:
        return False


def _write_new(dest, data):
    """True if written as a new file; False if the name was taken at the last moment (nothing is replaced)."""
    return platform.write_file_unless_exists(dest, data)


def _take_back(dest):
    try:
        dest.unlink()
    except OSError:
        pass


def _do_export(store, who, req, today, chosen, roots):
    code, want_client, clash = _export_shape(req)
    row = store.read("projects", ref=code)
    if row is None:
        raise Refused("There is no project with that code. Check the code in the address, or choose a project from the list.",
                      404, "project_not_found")
    as_at = today()
    try:
        published = publish.select(publish.read_inputs(store, code, as_at))
        data = docx_build.build(published)
    except (publish.PublishError, docx_build.WordError) as e:
        raise Refused(str(e)) from None
    digest = hashlib.sha256(data).hexdigest()
    week = published["data"]["project"]["week_ending"]
    local = _usable_local(chosen) if chosen else _usable_local(store.last_publish_folder(code) or "")
    if local is None:
        if chosen:
            raise Refused(FOLDER_GONE.format(name=Path(chosen).name or str(chosen)), 400, "folder_gone")
        raise Refused(CHOOSE_FOLDER + ".", 409, "needs_folder")
    if not _outside_data(local, Path(store.path).parent):
        raise Refused(FOLDER_DATA, 400, "folder_data")
    client = None
    if want_client:
        saved = row.get("publish_client")
        if not saved:
            raise Refused(NO_CLIENT_FOLDER, 400, "no_client_folder")
        checked = to_client.preflight(_ReadFs(), saved, data_dir=str(Path(store.path).parent), onedrive_roots=roots,
                                     local_folder=str(local))
        if not checked["ok"]:
            raise Refused(checked["message"] + " Nothing was saved.", 400, "client_folder")
        client = Path(checked["folder"])
    try:
        listing = {"here": _names_in(local), **({"client": _names_in(client)} if client else {})}
    except OSError as e:
        raise Refused(NOT_SAVED.format(name="The report", reason=e.strerror or "the folder can't be read"), 400, "not_saved") from None
    wanted = {"here": docx_build.file_name(code, week, as_at, local), **({"client": docx_build.file_name(code, week, as_at, client)}
                                                                          if client else {})}
    where = {"here": f"“{local.name or local}”", "client": "the client folder"}
    taken = {k: n for k, n in wanted.items() if n.lower() in listing[k]}
    if clash == "cancel":
        return 200, {"ok": True, "cancelled": True, "message": CANCELLED}
    if taken and clash is None:
        names = " ".join(NAME_TAKEN.format(name=n, where=where[k]) for k, n in taken.items())
        return 409, {"ok": False, "code": "name_taken", "message": names + " Add a number, replace it, or cancel.",
                     "taken": taken, "choices": ["number", "overwrite", "cancel"] if "here" in taken else ["number", "cancel"],
                     "can_replace": "here" in taken and not listing["here"][taken["here"].lower()]}
    names, replace = dict(wanted), False
    for k, n in taken.items():
        if clash == "overwrite" and k == "here":
            if listing["here"][n.lower()]:
                raise Refused(f"“{n}” is a folder, so it can't be replaced. Add a number instead.", 400, "folder_has_name")
            replace = True
        else:
            names[k] = to_client.numbered_name(n, list(listing[k]), local if k == "here" else client)
    dest = local / names["here"]
    try:
        if replace:
            platform.write_file(dest, data)
        elif not _write_new(dest, data):
            raise Refused(APPEARED.format(name=dest.name, where=where["here"]), 409, "name_appeared")
    except (OSError, platform.PlatformError) as e:
        raise Refused(NOT_SAVED.format(name=dest.name, reason=getattr(e, "strerror", None) or str(e)), 503, "not_saved") from None
    if not _verified(dest, digest):
        if replace:
            raise Refused(NOT_AS_MADE_REPLACED.format(name=dest.name), 500, "not_as_made")
        _take_back(dest)
        raise Refused(NOT_AS_MADE.format(name=dest.name), 500, "not_as_made")
    words, copy, failed = SAVED.format(name=dest.name, folder=where["here"]), None, ""
    if client:
        target = client / names["client"]
        try:
            if not _write_new(target, data):
                failed = APPEARED.format(name=target.name, where=where["client"])
            elif not _verified(target, digest):
                _take_back(target)
                failed = "what was copied did not match the report, so it was taken back."
            else:
                copy = target
        except (OSError, platform.PlatformError) as e:
            failed = f"{getattr(e, 'strerror', None) or e}."
        words += SAVED_CLIENT.format(name=names["client"]) if copy else CLIENT_FAILED.format(reason=failed)
    seq = None
    try:
        seq = store.log_publication(code, dest, week, digest, who, word=1, client_path=copy)
    except Invalid as e:
        words += NOT_RECORDED_FILE.format(reason=str(e))
    return 200, {"ok": True, "path": str(dest), "name": dest.name, "sha256": digest, "bytes": len(data), "seq": seq,
                 "client_name": copy.name if copy else None, "client_failed": bool(failed), "message": words}


def make_word_export(path, onedrive_roots=None, by_user=None, today=None, choose_folder=None):
    """The `word_export` seam the server calls for POST /api/word-export, for the database at `path`. When the project has no
    folder to save in yet, the seam asks `choose_folder(prompt)` (default: the system's folder dialog) with no lock held; it
    returns a folder or None for Cancel. `today` and `choose_folder` are seams for tests."""
    today = today or milestones.today
    ask = choose_folder or (lambda prompt: platform.choose_folder(prompt))

    def run(req, chosen):
        roots = onedrive_roots if onedrive_roots is not None else _safe_roots()
        return _call(path, onedrive_roots, by_user, lambda store, who, r: _do_export(store, who, r, today, chosen, roots), req)

    def word_export_seam(req):
        status, body = run(req, None)
        if body.get("code") != "needs_folder":
            return status, body
        try:
            folder = ask(CHOOSE_FOLDER)
        except platform.PlatformError as e:
            return 503, {"ok": False, "message": str(e), "code": "no_dialog"}
        if not folder:
            return 200, {"ok": True, "cancelled": True, "message": CANCELLED}
        return run(req, folder)
    return word_export_seam


def _safe_roots():
    try:
        return platform.onedrive_roots()
    except platform.PlatformError:
        return []
