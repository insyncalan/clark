"""What POST /api/project does (#444, Settings > Projects: Add project and Edit; guarded: it writes through the one writer).

Like changes.py this is a boundary between the browser and the store, so both reviewers read it. The server (which imports nothing
from clark) hands a request to a seam made here and sends the (status, body) it returns. Nothing new is written by hand: a project and
its workstreams are made with Step.create and changed with Step.update, the store's own rules apply, and the step is checked
and run under the one lock by changes._call, as every other write is.

Two ops:
- "new": {op, code, name, client, workstreams}. The code is 3 to 7 letters or digits, starting with a letter (shown in capitals);
  it is never changed afterwards. The project starts On track with the reason "Just started.", with its report sections
  (the store gives them) and the workstreams named (Delivery when none is named), all in ONE step. A code that is taken, archived
  or not, is refused in words. It is the prototype's project form (system/prototype/views.js C.projectForm).
- "edit": {op, code, name, client, workstreams}. The name and the client are changed; a workstream named that the project does not
  have is added; one the project has and the list leaves out is closed (its items keep its name); an empty list leaves them all as they
  are. One step. An archived project is read only. The code is the one the request names and is never changed.

Neither op can be undone from the page: the store's Undo does not take a project, a project's name or its workstreams back. A new
project is archived (Archive on its row), which is the page's way back. Every message is plain words, "clark" in lower case and never
first. Standard library only, Python 3.9.
"""
import re

from clark import store as clark_store
from clark.changes import Refused, _call, _plain_text, _shown
from clark.store import Invalid

NEW_KEYS = ("op", "code", "name", "client", "workstreams")
OPS = ("new", "edit")
MAX_NAME = 120
MAX_WORKSTREAMS = 12
MAX_WORKSTREAM = 60
SOURCE = "Added by hand in clark"              # a workstream's source, as the page's other hand-made rows say it
START_REASON = "Just started."                 # a new project's reason, the prototype's words
DEFAULT_WORKSTREAMS = ("Delivery",)

NOT_JSON_OBJECT = "That could not be read. Reload the page and try again."
BAD_OP = "That isn't something clark can do with a project."
BAD_CODE = "Use a short code of 3 to 7 letters or digits, starting with a letter."
NO_NAME = "Give the project a name."
LONG_NAME = f"Keep the name to {MAX_NAME} characters or fewer."
BAD_TEXT = "Use plain text, with no line breaks or hidden characters."
LONG_CLIENT = f"Keep the client to {MAX_NAME} characters or fewer."
BAD_WORKSTREAMS = "Name the workstreams in a list of words, separated by commas."
TOO_MANY = f"Name at most {MAX_WORKSTREAMS} workstreams."
LONG_WORKSTREAM = f"Keep each workstream's name to {MAX_WORKSTREAM} characters or fewer."
TAKEN = "That code is already in use. Choose another."
NOT_FOUND = "There is no project with that code. Check the code, or choose a project from the list."
ARCHIVED = "It is archived. Restore it first."


def _text(value, limit, long_words, required=None):
    """A name as it is stored: trimmed, plain, short. Blank is `required`'s words, or "" when it may be blank."""
    if not isinstance(value, str):
        raise Refused(BAD_TEXT)
    text = re.sub(r"\s+", " ", value).strip()
    if not _plain_text(text):
        raise Refused(BAD_TEXT)
    if not text:
        if required:
            raise Refused(required)
        return ""
    if len(text) > limit:
        raise Refused(long_words)
    return text


def _workstreams(value):
    """The workstream names, in the order given, once each (any case), or None when the request names none at all."""
    if value is None:
        return None
    if not isinstance(value, list) or any(not isinstance(v, str) for v in value):
        raise Refused(BAD_WORKSTREAMS)
    names, seen = [], set()
    for v in value:
        name = _text(v, MAX_WORKSTREAM, LONG_WORKSTREAM)
        if name and name.lower() not in seen:
            seen.add(name.lower())
            names.append(name)
    if len(names) > MAX_WORKSTREAMS:
        raise Refused(TOO_MANY)
    return names


def _shape(req):
    if not isinstance(req, dict):
        raise Refused(NOT_JSON_OBJECT)
    for k in req:
        if k not in NEW_KEYS:
            raise Refused(f"That request has something that is not allowed: '{_shown(k)}'.")
    op = req.get("op")
    if not isinstance(op, str) or op not in OPS:
        raise Refused(BAD_OP)
    code = req.get("code")
    code = code.upper() if isinstance(code, str) else code
    if not isinstance(code, str) or not re.fullmatch(clark_store.CODE_RE, code):
        raise Refused(BAD_CODE, code="bad_project_code")
    name = _text(req.get("name"), MAX_NAME, LONG_NAME, NO_NAME)
    client = _text(req.get("client", ""), MAX_NAME, LONG_CLIENT)
    return op, code, name, client, _workstreams(req.get("workstreams"))


def _new(store, who, code, name, client, names):
    if store.read("projects", ref=code) is not None:
        raise Refused(TAKEN, 409, "code_taken")
    names = list(names) if names else list(DEFAULT_WORKSTREAMS)
    with store.step("dashboard", who, place="dashboard") as st:
        st.create("projects", {"code": code, "name": name, "client_name": client or None, "health": "On track", "health_reason": START_REASON})
        for n in names:
            st.create("workstreams", {"project": code, "name": n, "source": SOURCE})
        apply_id = st.peek_apply_id()
    return 200, {"ok": True, "op": "new", "code": code, "name": name, "apply_id": apply_id, "message": f"{name} created."}


def _edit(store, who, code, name, client, names):
    row = store.read("projects", ref=code)
    if row is None:
        raise Refused(NOT_FOUND, 404, "project_not_found")
    if row["archived"]:
        raise Refused(ARCHIVED, 409, "archived")
    have = [w for w in store.read("workstreams", project=code) if not w["archived"] and w["status"] == "Active"]
    kept = {w["name"].lower() for w in have}
    wanted = {n.lower() for n in names or ()}
    with store.step("dashboard", who, place="dashboard") as st:
        changes = {}
        if name != row["name"]:
            changes["name"] = name
        if (client or None) != (row["client_name"] or None):
            changes["client_name"] = client or None
        if changes:
            st.update("projects", code, changes)
        for n in names or ():
            if n.lower() not in kept:
                st.create("workstreams", {"project": code, "name": n, "source": SOURCE})
        if names:
            for w in have:
                if w["name"].lower() not in wanted:
                    st.update("workstreams", w["id"], {"status": "Closed"})
        apply_id = st.peek_apply_id()
    return 200, {"ok": True, "op": "edit", "code": code, "name": name, "apply_id": apply_id, "message": f"{name} saved."}


def _do_project(store, who, req):
    op, code, name, client, names = _shape(req)
    try:
        return (_new if op == "new" else _edit)(store, who, code, name, client, names)
    except Invalid as e:                                       # a rule of the store, in its own plain words
        text = str(e)
        if text.startswith("clark's data is in use"):
            raise
        raise Refused(text) from None


def make_project(path, onedrive_roots=None, by_user=None):
    """The `project_save` seam the server calls for POST /api/project, for the database at `path`. `by_user` is a name or a function
    that gives one (as in changes.make_change)."""
    def project_seam(req):
        return _call(path, onedrive_roots, by_user, _do_project, req)
    return project_seam
