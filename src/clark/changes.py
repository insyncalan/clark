"""What the page may change, and how: the logic behind POST /api/change and POST /api/undo (#65; guarded).

New in clark; no creaite source (creaite has no report sections; its /api/undo only takes the latest apply, which is not
copied: clark undoes by step). This is the boundary between the browser and the one writer, so the whole file is read by

What it does, and does not:
- The request names things only from allow-lists here (CHANGE_KINDS). A field is accepted only if it is in the list for
  its kind and op AND is a column of the table. The request's text never names a table, a column or any part of SQL, and
  this file holds no SQL: it writes only through the store's steps (Store.step, Step.create/update/cancel, Store.undo).
- The project, a section's id and type (once made) and its sort_order are never taken from `values` or `changes`: the
  server works the place out (clark.order).
- Every refusal is plain words, 400. An id (or a `before` / `after`) is a section of THIS project: another project's section
  and a missing one get the same words, so a request can't find out what exists elsewhere.
- Each call opens its own store (a SQLite connection belongs to the thread that made it, and the server is threaded) and
  does ALL its work under one lock: for an undo, the check that the step is the report's and the undo itself are one
  does not make an empty database, when clark.db isn't there.
- The reply carries only what the page needs of each section: id, type, title, beside, hidden, sort_order. Never its body.

`change(req)` and `undo(req)` return (status, body); the server sends them. make_change / make_undo build them for one
database file; the launcher passes those to server.serve. Standard library only, Python 3.9.
"""
import re
import threading
import unicodedata
from pathlib import Path

from clark import order, platform
from clark import store as clark_store
from clark.store import Invalid

# The ops, as the request names them. Made from one string, not written one by one: tests/test_store_writer.py reads a lone
# "update" or "delete" string anywhere in src/ as SQL (its check is case-blind until #39's case-sensitive version merges), and
# these are not SQL: no op here is ever put in a statement.
NEW, UPDATE, MOVE, DELETE, ARCHIVE, RESTORE = "new update move delete archive restore".split()

# The allow-list: kind -> op -> the fields a request may give (`values` for new, `changes` for update). A field must also
# be a column of the table (tests/test_changes.py asserts it for each). sort_order, project, id and type (after creation)
# are in no list: they are never taken from a request.
ARCHIVABLE = ("projects", "milestones", "actions", "raid", "decisions", "use_cases", "documents")      # #126: archive and restore, no fields
CHANGE_KINDS = {
    "report_sections": {NEW: ("type", "title"), UPDATE: ("title", "hidden", "beside"), MOVE: ("beside",), DELETE: ()},
    # #68: the work items board changes an item's fields, and nothing else. Only `update`: no new, move or delete for these kinds
    # (an item is closed or cancelled by its status, and archived only by archiving). priority is not in raid's list because the
    # store works it out from impact and likelihood; `archived` is in no list.
    "actions": {UPDATE: ("status", "workstream", "owner", "priority", "due_date", "milestone")},
    "raid": {UPDATE: ("status", "workstream", "owner", "due_date", "milestone")},
    "decisions": {UPDATE: ("status", "made_by", "needed_by", "date")},
    # #45: the At a glance tiles and the project's health. A tile is hidden, given an outline colour or moved (its place is worked
    # out here, never sent); the project's change takes no `id` (it is the request's project) and only its health and the reason.
    "glance_tiles": {UPDATE: ("hidden", "outline"), MOVE: ()},
    "projects": {UPDATE: ("health", "health_reason")},
}
KIND_OP_KEYS = {"projects": {UPDATE: ("changes",)}}   # per kind, the keys an op takes when they are not OP_KEYS' (a project has no id)
TILES = ("health", "overdue", "risks", "decisions")  # glance_tiles.tile (the store's ALLOWED holds the same four; a test says so)
TILE_WORDS = {"health": "Project health", "overdue": "Overdue actions", "risks": "High risks and issues",
              "decisions": "Decisions needed"}      # the tiles as the page says them (glance.TILE_TITLES; a test says they agree)
OUTLINES = ("", "R", "A", "G", "N")                  # automatic, red, amber, green, no colour
OUTLINE_WORDS = {"": "Automatic", "R": "Red", "A": "Amber", "G": "Green", "N": "No colour"}
TILE_SHOWN = ("tile", "hidden", "outline", "sort_order")   # what a reply says of a tile
HEALTHS = ("On track", "At risk", "Off track")
# What an Undo from here may reverse: table -> the fields it may put back, or None for any field (sections, work items). ONE table
# for every kind of step this file makes (#126 adds its own entries); the FIELD is checked, not only the table, so a dashboard step
# that changed another project field (a name, a phase) is never undone from here. `updated_at` and `note` follow any change.
UNDOABLE = {"report_sections": None, "actions": None, "raid": None, "decisions": None,
            "glance_tiles": ("hidden", "outline", "sort_order"),
            "projects": ("health", "health_reason", "archived", "active"),       # #126: a project's own archive or restore step sets the flag and `active`
            "milestones": ("archived",), "use_cases": ("archived",), "documents": ("archived",), "workstreams": ("archived",)}
UNDO_ALSO = ("updated_at", "note")
for _kind in ARCHIVABLE:                              # #126: every record can be archived and restored, with no fields; the items keep their update
    CHANGE_KINDS.setdefault(_kind, {}).update({ARCHIVE: (), RESTORE: ()})
ITEM_KINDS = ("actions", "raid", "decisions")        # the work items; every other kind is a report section
ITEM_NOT_NULL = ("status", "owner", "priority")      # a work item field that has to have a value (the others may be cleared)
ITEM_SHOWN = {k: ("id",) + tuple(CHANGE_KINDS[k][UPDATE]) + (("closed",) if k != "decisions" else ())
              for k in ITEM_KINDS}                   # what a reply says of a changed item
FLAG_FIELDS = ("hidden", "beside")        # 0 or 1 only: a bool, a float, a string or any other number is refused
BASE_KEYS = ("project", "kind", "op", "place")
OP_KEYS = {NEW: ("values", "after"), UPDATE: ("id", "changes"), MOVE: ("id", "before", "flags"), DELETE: ("id",),
           ARCHIVE: ("id",), RESTORE: ("id",)}
MAX_FLAGS = 4                             # a move may set the `beside` of at most this many sections (the moved one, its old partner, its new one, the one before)
PLACES = tuple(p for p in ("menu", "cell", "report", "board") if p in clark_store.PLACES)   # where the change was made (the step's place); "board" counts once the store knows it
MADE_OP = clark_store.OP_MADE            # the log's word for a row a step made: the store's own constant
VIA = "dashboard"                         # the route of every step made here; an undo is never undone from here
SHOWN = ("id", "type", "title", "beside", "hidden", "sort_order")      # what a reply says of a section: never its body
DEFAULT_TITLE = "New section"             # the title of a section added with none (server side: the page need not send one)
LOCK = threading.Lock()                   # one change or undo at a time in this process; across processes the store's
#                                           BEGIN IMMEDIATE and busy timeout do the same

BAD_PROJECT = "Use a project code of 3 to 7 capital letters or digits."   # as server.MESSAGES["bad_project_code"]
NO_PROJECT = "There is no project with that code. Check the code in the address, or choose a project from the list."   # as server.MESSAGES["project_not_found"]
NOT_JSON_OBJECT = "Send a JSON object."
BAD_KIND = "That kind of change isn't allowed here."
BAD_OP = "That isn't a change clark can make."
BAD_PLACE = "clark doesn't know that place."
NOT_MINE = "That section isn't in this project."
NOT_MINE_RECORD = "That isn't in this project. Reload the page and try again."        # #126: another project's record and a missing one get the same words
NOT_A_TILE = "That tile isn't in this project."          # an unknown tile and another project's: the same words
BAD_OUTLINE = "That outline colour isn't one clark has."
BAD_HEALTH = "Health can be On track, At risk or Off track."
HEALTH_NEEDS_REASON = "Say why in a line or two before the health changes."
PROJECT_NOT_ACTIVE = "That project is archived. Restore it first."
STALE = "Your page is out of date. Reload it, then try again."
INVALID_LAYOUT = "That isn't a valid layout change."
ITEM_NOT_MINE = "That item isn't in this project."     # another project's item, a missing one and an archived one: the same words
ITEM_KEEPS_TYPE = "A work item keeps its type."
NO_ARCHIVE = "An item can't be archived by editing its details. Archiving isn't available from the page yet. Ask the clark team if you need an item hidden now."
NO_RAID_PRIORITY = "A risk or issue's priority comes from its impact and likelihood. Change those in its details."
NO_DECISION_FIELD = {"workstream": "A decision isn't part of a workstream.", "milestone": "A decision isn't tied to a milestone.",
                     "priority": "A decision has no priority."}
ITEM_VALUE_WORDS = "That value isn't one clark can use."
ITEM_TEXT_WORDS = "Use plain text, with no line breaks or hidden characters."
ITEM_BAD_KINDS = frozenset({"Cc", "Cf", "Cs", "Co", "Zl", "Zp"})   # as the store's section titles: control, format, surrogate, private use, separators
NOT_A_DATE = "That isn't a date. Pick a day from the calendar."
NOT_A_STATUS = "That status isn't available for this item."
NO_WORKSTREAM = "That workstream isn't available."
ARCHIVED_MILESTONE = "That milestone is archived. Restore it first."
ARCHIVED_USE_CASE = "That use case is archived. Restore it first."
NO_MILESTONE = "That milestone isn't in this project."          # another project's and a missing one: the same words
DECISION_NEEDS_DATE = "A decision that is made needs the date it was made."
DECISION_NOT_MADE = "A decision that isn't made yet has no date."
MADE_STAYS = "A decision that has been made can't go back to Pending. Record a new decision that replaces it."
MADE_CANT_BE_PUT_BACK = "A decision that has been made can't be put back. Record a new decision that replaces it."
BEFORE_RAISED = clark_store.BEFORE_RAISED               # one sentence, kept in store.py
# The store's sentences (a part of each) -> fixed plain words. Order matters: the first part found wins.
STORE_WORDS = (("must be a date stored as", NOT_A_DATE), ("is not a real date", NOT_A_DATE), ("must be one of", NOT_A_STATUS),
               ("isn't an active workstream", NO_WORKSTREAM), ("milestone", NO_MILESTONE),
               ("that is Made needs its date", DECISION_NEEDS_DATE), ("Pending decision has no date", DECISION_NOT_MADE),
               ("can't go back to Pending", MADE_STAYS), (clark_store.BEFORE_RAISED_KEY, BEFORE_RAISED),
               ("isn't an item of this project", ITEM_NOT_MINE))
ONLY_TEXT = "Only a text section can be added."
KEEPS_TYPE = "A section keeps its type."
FLAG_WORDS = "That must be 0 or 1."
NO_UNDO = "That step can't be undone from here."
UNDONE = "That step has been undone already."
NO_DATA = "clark's data can't be found."
IN_USE = "clark's data is in use by another program. Wait a moment and try again."
CANT_OPEN = "clark can't read its data. Restart clark, or restore a backup."
CANT_SAVE = "clark can't save to its data. Check the folder is writable, then try again."      # the store's "could not be opened for writing"
NOT_OPENED = "clark's data could not be opened"


class Refused(Exception):
    """A request clark won't act on: the status, and the plain words a person reads."""

    def __init__(self, message, status=400, code="refused"):
        super().__init__(message)
        self.message, self.status, self.code = message, status, code


def _shown(name):
    """A request's own word, made safe to say back: short, letters, digits and a few marks only."""
    return re.sub(r"[^\w .-]", "", str(name))[:30]


def _id_or_none(value, words):
    """`value` if it is None or text; else Refused(words)."""
    if value is not None and not isinstance(value, str):
        raise Refused(words)
    return value


def _flag(value):
    """0 or 1 as a whole number, or Refused. True and False are refused here (the store would turn them into 1 and 0):
    a page that means 0 or 1 sends 0 or 1."""
    if type(value) is not int or value not in (0, 1):
        raise Refused(FLAG_WORDS)
    return value


# ── Reading a request (no store yet) ──────────────────────────────────────────

def _shape(req):
    """The request's project, kind, op and place, and its op's own parts, checked for type and for unknown keys. Nothing is
    looked up here, so a list or an object where text is wanted is a refusal, never an error."""
    if not isinstance(req, dict):
        raise Refused(NOT_JSON_OBJECT)
    known = set(BASE_KEYS) | {k for keys in OP_KEYS.values() for k in keys}
    for k in req:
        if k not in known:
            raise Refused(f"clark doesn't know '{_shown(k)}' in that request.")
    project = req.get("project")
    if not isinstance(project, str) or not re.fullmatch(clark_store.CODE_RE, project):
        raise Refused(BAD_PROJECT, code="bad_project_code")
    kind, op = req.get("kind"), req.get("op")
    if not isinstance(kind, str) or kind not in CHANGE_KINDS:
        raise Refused(BAD_KIND)
    if not isinstance(op, str) or op not in CHANGE_KINDS[kind]:
        raise Refused(BAD_OP)
    keys = KIND_OP_KEYS.get(kind, {}).get(op, OP_KEYS[op])
    for k in req:
        if k not in BASE_KEYS and k not in keys:
            if k == "flags":
                raise Refused(INVALID_LAYOUT)
            raise Refused(f"That change doesn't take '{_shown(k)}'.")
    place = req.get("place")
    if place is not None and (not isinstance(place, str) or place not in PLACES):
        raise Refused(BAD_PLACE)
    return project, kind, op, place


def _fields(given, kind, op, columns, what):
    """`given` (an object) as a dict whose every field is in the allow-list for kind and op and is a column; else Refused."""
    if given is None:
        given = {}
    if not isinstance(given, dict):
        raise Refused(f"Send {what} as an object.")
    usable = set(CHANGE_KINDS[kind][op]) & set(columns)
    for k in given:
        if kind in ITEM_KINDS:
            _item_field_words(kind, k)
        if k == "type" and op == UPDATE:
            raise Refused(KEEPS_TYPE)
        if k not in usable:
            raise Refused(f"The field '{_shown(k)}' can't be set here.")
    return dict(given)


def _item_field_words(kind, field):
    """Plain words for a field that a work item can never take here; nothing when it is simply not in the list."""
    if field == "archived":
        raise Refused(NO_ARCHIVE)
    if field == "type":
        raise Refused(ITEM_KEEPS_TYPE)
    if kind == "raid" and field == "priority":
        raise Refused(NO_RAID_PRIORITY)
    if kind == "decisions" and field in NO_DECISION_FIELD:
        raise Refused(NO_DECISION_FIELD[field])


def _plain_text(v):
    """Whether `v` is text a person can read: it can be saved as UTF-8 (a lone surrogate can't) and holds no control or
    invisible character (a line break, NUL, a bidi override, a zero-width space), as a section title may not."""
    try:
        v.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return not any(unicodedata.category(c) in ITEM_BAD_KINDS for c in v)


def _checked_item_changes(fields):
    """A work item's fields with their values checked: plain text or None (None only where the field may be cleared), and
    short. The store checks the rest (the words a status may take, a real date, an active workstream, this project's
    milestone); its refusals are put into plain words in _do_item_change."""
    for k, v in fields.items():
        if v is None and k in ITEM_NOT_NULL or v is not None and (not isinstance(v, str) or not v.strip() or len(v) > 200):
            raise Refused(ITEM_VALUE_WORDS)
        if isinstance(v, str) and not _plain_text(v):
            raise Refused(ITEM_TEXT_WORDS)
    return {k: (unicodedata.normalize("NFC", v).strip() if isinstance(v, str) else v) for k, v in fields.items()}


def _store_words(e):
    """The store's refusal of a work item change as a fixed plain sentence: never its field names or the value that was sent.
    A busy database passes through for _call to word."""
    text = str(e)
    if text.startswith("clark's data is in use") or text.startswith(NOT_OPENED):
        return None
    if text.startswith("Milestone ") and text.endswith("is archived. Restore it first."):
        return ARCHIVED_MILESTONE
    if text.startswith("Use case ") and text.endswith("is archived. Restore it first."):
        return ARCHIVED_USE_CASE
    for start, words in STORE_WORDS:
        if start in text:
            return words
    return ITEM_VALUE_WORDS


def _checked_changes(fields):
    """An update's fields with their values checked: the title as the store keeps it, a flag as 0 or 1."""
    out = {}
    for k, v in fields.items():
        out[k] = _flag(v) if k in FLAG_FIELDS else clark_store.section_title(v)
    return out


# ── The change ────────────────────────────────────────────────────────────────

def _sections(store, code):
    """The project's sections as shown: by sort_order, then id."""
    return order.in_order(store.read("report_sections", code))


def _shown_rows(rows):
    return [{k: r[k] for k in SHOWN} for r in rows]


def _mine(ref, ids, words):
    """`ref` if it is one of this project's section ids, else Refused(words): the same words for another project's section
    and a missing one."""
    if not isinstance(ref, str) or ref not in ids:
        raise Refused(words)
    return ref


def _move_flags(given, allowed, columns):
    """A move's optional `flags`: an object of at most MAX_FLAGS section ids, each 0 or 1, setting `beside` and nothing else.
    Whether each id is a section of this project is checked inside the step, with the same words as `before`."""
    if given is None:
        return {}
    if not isinstance(given, dict):
        raise Refused(INVALID_LAYOUT)
    if len(given) > MAX_FLAGS:
        raise Refused(INVALID_LAYOUT)
    if given and not ("beside" in allowed and "beside" in columns):
        raise Refused(INVALID_LAYOUT)
    return {k: _flag(v) for k, v in given.items()}


def _check_flags(rows, ref, before, flags):
    """The `flags` of a move must fit the page that sent them (#95): only the moved section, its old neighbours, `before` and
    the section just before the landing place may be named, and a flag of 1 on any section but the moved one means "the moved
    section goes in its other half", so that section must still be the one directly before the landing place and on its own
    (not the second half of a pair). Else the report has changed since the page drew it: refused, nothing written."""
    if not flags:
        return
    ids = [r["id"] for r in rows]
    at = ids.index(ref)
    rest = [r for r in rows if r["id"] != ref]
    rest_ids = [r["id"] for r in rest]
    land = len(rest) if before is None else rest_ids.index(before)
    above = rest_ids[land - 1] if land else None
    allowed = {ref, before, above, ids[at - 1] if at else None, ids[at + 1] if at + 1 < len(ids) else None}
    if any(other not in allowed for other in flags):
        raise Refused(STALE)
    now = {r["id"]: r["beside"] for r in rest}                      # how the rows stand now, with the page's own clearing of the old partners
    for other, value in flags.items():
        if other != ref and not (value == 1 and other == above):
            now[other] = value
    roles, i = {}, 0
    while i < len(rest_ids):                                        # walk the pairs the way the page does: a 1 on a second half or a last row is ignored
        if now[rest_ids[i]] == 1 and i + 1 < len(rest_ids):
            roles[rest_ids[i]], roles[rest_ids[i + 1]] = "first", "second"
            i += 2
        else:
            roles[rest_ids[i]] = "lone"
            i += 1
    for other, value in flags.items():
        if value == 1 and other != ref:
            if other != above or roles.get(above) != "lone":
                raise Refused(STALE)
    if flags.get(ref) == 1 and before is not None and roles.get(before) != "lone":
        raise Refused(STALE)                                        # it would sit beside a section that is no longer on its own


def _flags_to_clear(rows, ref):
    """The sections whose `beside` must go to 0 when `ref` is deleted, so no stray flag is left: the first half above it (read the
    way the page reads pairs: a 1 on a second half or on the last row is ignored), and a flag the second half below it carries
    (else it would start a new pair with a stranger). Nothing for a section on its own."""
    ids = [r["id"] for r in rows]
    flag = {r["id"]: r["beside"] for r in rows}
    i = 0
    while i < len(ids):
        if flag[ids[i]] == 1 and i + 1 < len(ids):
            first, second = ids[i], ids[i + 1]
            if ref == second:
                return [first]
            if ref == first:
                return [second] if flag[second] == 1 else []
            i += 2
        else:
            i += 1
    return []


def _do_change(store, by_user, req):
    project, kind, op, place = _shape(req)
    if store.read("projects", ref=project) is None:
        raise Refused(NO_PROJECT, 404, "project_not_found")
    table = next(k for k in CHANGE_KINDS if k == kind)              # the allow-list's own spelling, never the request's
    if op in (ARCHIVE, RESTORE):
        return _do_archive(store, by_user, project, table, op, place, req.get("id"))
    columns = clark_store.columns(store.con, table)
    if kind in ITEM_KINDS:
        return _do_item_change(store, by_user, req, project, table, columns, place)
    if kind == "glance_tiles":
        return _do_tile_change(store, by_user, req, project, table, columns, op, place)
    if kind == "projects":
        return _do_project_change(store, by_user, req, project, table, columns, place)
    ref = req.get("id")
    changes = None
    if op == NEW:
        values = _fields(req.get("values"), kind, op, columns, "the new section's values")
        if values.get("type", "text") != "text":
            raise Refused(ONLY_TEXT)
        title = clark_store.section_title(values["title"]) if "title" in values else DEFAULT_TITLE
        after = _id_or_none(req.get("after"), STALE)
    elif op == UPDATE:
        changes = _checked_changes(_fields(req.get("changes"), kind, op, columns, "the changes"))
        if not changes:
            raise Refused("Say what to change.")
    elif op == MOVE:
        if "before" not in req:
            raise Refused("Say where to move it.")
        before = _id_or_none(req.get("before"), STALE)
        flags = _move_flags(req.get("flags"), CHANGE_KINDS[kind][op], columns)
    with store.step(VIA, by_user, place=place) as st:               # BEGIN IMMEDIATE: what is read next is what is changed
        rows = _sections(store, project)
        if not rows:                                                # a project made before #65: the defaults first, in this step
            st.seed_sections(project)
            rows = _sections(store, project)
        ids = [r["id"] for r in rows]
        if op == NEW:
            ref = _add(st, project, rows, ids, title, after)
        else:
            _mine(ref, ids, NOT_MINE)
            if op == UPDATE:
                st.update(table, ref, changes)
            elif op == MOVE:
                if before is not None:
                    _mine(before, ids, STALE)
                if before == ref:
                    raise Refused("A section can't be moved before itself.")
                for other in flags:
                    _mine(other, ids, STALE)                        # before anything is written
                _check_flags(rows, ref, before, flags)
                for other, place_ in order.section_slot(rows, ref, before).items():
                    st.update(table, other, {"sort_order": place_})
                for other, value in flags.items():                  # the same step: one Undo for the place and every flag
                    st.update(table, other, {"beside": value})
            else:
                for other in _flags_to_clear(rows, ref):            # the same step: one Undo puts the section and the flag back
                    st.update(table, other, {"beside": 0})
                st.cancel(table, ref)
        apply_id = st.peek_apply_id()                               # None when nothing changed: the page shows no Undo
    if apply_id is not None and all(r["via"] == clark_store.SEED_VIA for r in store.step_rows(apply_id)):
        apply_id = None                                             # an old project's first change changed nothing: only the starting sections went in, so no Undo
    return 200, {"ok": True, "apply_id": apply_id, "ref": ref, "sections": _shown_rows(_sections(store, project))}


def _belongs(table, ref, project):
    """Whether record key `ref` is a record of `project`: its own code for a project, `CODE-` for an item, `CODE|` for a
    document. The separator is part of the test, so project ABC never matches ABCD-A-001 (#126)."""
    if not isinstance(ref, str):
        return False
    try:
        ref.encode("utf-8")                    # a lone surrogate can't be saved or looked up: it is nobody's record
    except UnicodeEncodeError:
        return False
    if table == "projects":
        return ref == project
    return ref.startswith(project + ("|" if table == "documents" else "-"))


def _do_archive(store, by_user, project, table, op, place, ref):
    """Archive or restore one record of this project, or a whole project with its children: one step, one Undo (#126). The
    reply says what happened and how many of each kind went with a project; never a body."""
    if not _belongs(table, ref, project) or store.read(table, ref=ref) is None:
        raise Refused(NOT_MINE_RECORD)
    with store.step(VIA, by_user, place=place) as st:
        (st.archive if op == ARCHIVE else st.restore)(table, ref)
        apply_id = st.peek_apply_id()
        counts = dict(st.result.get("counts") or {}) if table == "projects" else None
    reply = {"ok": True, "apply_id": apply_id, "ref": ref, "archived": 1 if op == ARCHIVE else 0}
    if counts is not None:
        reply["counts"] = counts
    return 200, reply


def _do_item_change(store, by_user, req, project, table, columns, place):
    """#68: change fields of one work item of THIS project, in one step (several fields, one Undo). Only `update` gets here
    (CHANGE_KINDS has no other op for these kinds). The store applies its own rules (closing, a Made decision's date, an
    active workstream, this project's milestone); a rule it refuses comes back in its words and nothing is written."""
    ref = req.get("id")
    changes = _checked_item_changes(_fields(req.get("changes"), table, UPDATE, columns, "the changes"))
    if not changes:
        raise Refused("Say what to change.")
    with store.step(VIA, by_user, place=place) as st:               # BEGIN IMMEDIATE: what is read next is what is changed
        row = store.read(table, ref=ref) if isinstance(ref, str) else None
        if row is None or row["project"] != project or row["archived"]:
            raise Refused(ITEM_NOT_MINE)
        was_pending = table == "decisions" and row["status"] == "Pending"
        try:
            st.update(table, ref, changes)
        except Invalid as e:                                        # a rule of the store, in fixed words: no field name, no value
            words = _store_words(e)
            if words is None:
                raise
            raise Refused(words) from None
        apply_id = st.peek_apply_id()                               # None when nothing changed: the page shows no Undo
    now = store.read(table, ref=ref)
    made = was_pending and now["status"] == "Made"                  # a decision that is made is replaced by a new one, never put back
    return 200, {"ok": True, "apply_id": None if made else apply_id, "undoable": apply_id is not None and not made, "ref": ref,
                 "item": {k: now[k] for k in ITEM_SHOWN[table]}}


def _tiles(store, code):
    """The project's tile rows as shown: by place, then tile."""
    rows = sorted(store.read("glance_tiles", code), key=lambda r: (r["sort_order"], r["tile"]))
    return [{k: r[k] for k in TILE_SHOWN} for r in rows]


def _a_tile(ref, words):
    """`ref` if it is one of the four tile names, else Refused(words): no other text reaches a key."""
    if not isinstance(ref, str) or ref not in TILES:
        raise Refused(words)
    return ref


def _checked_tile_changes(fields):
    """A tile's fields with their values checked: hidden as 0 or 1, the outline one of the closed set."""
    out = {}
    for k, v in fields.items():
        if k == "hidden":
            out[k] = _flag(v)
        else:
            if not isinstance(v, str) or v not in OUTLINES:
                raise Refused(BAD_OUTLINE)
            out[k] = v
    return out


def _do_tile_change(store, by_user, req, project, table, columns, op, place):
    """#45: hide a tile, set its outline colour, or move it, in one step with one Undo. The tiles are started first (as history
    only) when the project has none. A tile is named by its closed name; its key is made here from the request's project."""
    ref = _a_tile(req.get("id"), NOT_A_TILE)
    changes, before = None, None
    if op == UPDATE:
        changes = _checked_tile_changes(_fields(req.get("changes"), table, op, columns, "the changes"))
        if not changes:
            raise Refused("Say what to change.")
    else:
        if "before" not in req:
            raise Refused("Say where to move it.")
        before = req.get("before")
        if before is not None:
            _a_tile(before, STALE)
        if before == ref:
            raise Refused("A tile can't be moved before itself.")
    with store.step(VIA, by_user, place=place) as st:               # BEGIN IMMEDIATE: what is read next is what is changed
        if not store.read("glance_tiles", project):                 # a project made before #45: the starting tiles first, in this step
            st.seed_tiles(project)
        key = f"{project}|{ref}"
        if op == UPDATE:
            st.update(table, key, changes)
        else:
            rows = [{"id": r["tile"], "sort_order": r["sort_order"]} for r in store.read("glance_tiles", project)]
            for other, place_ in order.section_slot(rows, ref, before).items():
                st.update(table, f"{project}|{other}", {"sort_order": place_})
        apply_id = st.peek_apply_id()                               # None when nothing changed: the page shows no Undo
    if apply_id is not None and all(r["via"] == clark_store.SEED_VIA for r in store.step_rows(apply_id)):
        apply_id = None                                             # only the starting tiles went in: no Undo
    return 200, {"ok": True, "apply_id": apply_id, "ref": ref, "tiles": _tiles(store, project)}


def _checked_project_changes(fields):
    """The project's health and reason, checked for type and the closed set. The store's rule that a changed health has a
    reason in the same change stays the only such rule."""
    out = dict(fields)
    for k, v in fields.items():
        if k == "health" and (not isinstance(v, str) or v not in HEALTHS):
            raise Refused(BAD_HEALTH)
        if k == "health_reason":
            try:
                out[k] = clark_store.health_reason_text(v)      # the store's own check, called here so the first refusal is the route's
            except Invalid as e:
                raise Refused(str(e)) from None
    return out


def _project_words(e):
    """The store's refusal of a project change as a fixed plain sentence; None for a busy database (_call words that)."""
    text = str(e)
    if text.startswith("clark's data is in use") or text.startswith(NOT_OPENED):
        return None
    if "needs a reason" in text:
        return HEALTH_NEEDS_REASON
    return text if text in clark_store.REASON_REFUSALS else ITEM_VALUE_WORDS


def _do_project_change(store, by_user, req, project, table, columns, place):
    """#45: change the project's health and/or its reason, in one step: one Undo puts both back together. The request has no id."""
    changes = _checked_project_changes(_fields(req.get("changes"), table, UPDATE, columns, "the changes"))
    if not changes:
        raise Refused("Say what to change.")
    with store.step(VIA, by_user, place=place) as st:
        if clark_store.is_archived(store.con, project):             # a project's own row has no `project` column, so the store's
            raise Refused(PROJECT_NOT_ACTIVE)                       # row rule doesn't see it: said here, with nothing written
        try:
            st.update(table, project, changes)
        except Invalid as e:
            words = _project_words(e)
            if words is None:
                raise
            raise Refused(words) from None
        apply_id = st.peek_apply_id()                               # None when nothing changed: the page shows no Undo
    now = store.read(table, ref=project)
    return 200, {"ok": True, "apply_id": apply_id, "ref": project,
                 "project": {"health": now["health"], "health_reason": now["health_reason"]}}


def _add(st, project, rows, ids, title, after):
    """Make a text section just after section `after` (None: at the end); its id. When no whole number fits between its
    neighbours, the rows are renumbered in the same step (clark.order)."""
    if after is not None:
        _mine(after, ids, STALE)
    end = order.end_slot(rows)
    new_place, renumber = end, {}
    if after is not None and ids.index(after) + 1 < len(ids):
        probe = rows + [{"id": "", "sort_order": end}]              # the new row, at the end, then moved up to its place
        renumber = order.section_slot(probe, "", ids[ids.index(after) + 1])
        new_place = renumber.pop("", end)
    ref = st.create("report_sections", {"project": project, "type": "text", "title": title, "sort_order": new_place})
    for other, place in renumber.items():
        st.update("report_sections", other, {"sort_order": place})
    return ref


# ── The undo ──────────────────────────────────────────────────────────────────

def _row_is_ours(row, project, project_step, flagged):
    """Whether one step row is the dashboard's to undo for `project`: in a table of UNDOABLE, a row of this project, and a field
    that table may put back (the FIELD is checked, not only the table). A section of this project as before; a tile of this
    project (a starting tile, written via seed, is history and passes); the project's health and reason (#45); since #126 the
    `archived` flag of a record of this project (and the `updated_at` stamp that goes with it, on a record whose flag is in the
    same step; the project's own stamp also goes with its health change, see _eligible), or (in a project's own archive or restore step) the project's `active`. Anything else, a title included, is not."""
    table, key, field = row["table"], str(row["key"]), row.get("field")
    if table not in UNDOABLE:
        return False
    allowed = UNDOABLE[table]
    if table == "report_sections":
        return key.startswith(project + "-S-")
    if table == "glance_tiles":                                     # #45
        return key in {f"{project}|{t}" for t in TILES} and (row["via"] == clark_store.SEED_VIA or field in allowed + UNDO_ALSO)
    if table == "workstreams":                                      # archived only along with its project: it has no single archive
        return project_step and field in ("archived", "updated_at") and (table, key) in flagged and key.startswith(project + "-W-")
    if table not in ARCHIVABLE:
        return False
    if field == "archived":
        return _belongs(table, key, project)
    if table == "projects" and key == project and field in ("health", "health_reason", "note"):      # #45: the health change
        return True
    if field == "updated_at":                                       # the stamp goes only with its own record's flag or change
        return ((table, key) in flagged and _belongs(table, key, project)) or (table == "projects" and key == project)
    return table == "projects" and project_step and field == "active" and key == project


def _eligible(rows, project):
    """Whether step rows (Store.step_rows) are the dashboard's own to undo from here: at least one, every one written via the
    dashboard (the starting sections an old project's first change makes carry their own via), none by an undo, and every one
    either a section of this project, since #126 the `archived` flag of a record of this project (the FIELD is checked, not
    just the table, so a step that edited a title is not undone from here), or, #68, a field of a work item of this project.
    A step is one family, never a mix: work-item fields; archive flags (a project's own archive or restore step touches several
    tables but is one family); or the page's own data (sections, tiles and the project's health, which may share a step). A step
    whose rows span more than one family is refused here. A record's `updated_at` stamp passes only beside a row of the same
    record in the same step that is its archive flag, its `active`, or its health change. The project's own row has the bare code
    as its key."""
    flagged = {(r["table"], str(r["key"])) for r in rows if r.get("field") == "archived"}
    beside = {(r["table"], str(r["key"])) for r in rows if r.get("field") in ("archived", "active", "health", "health_reason", "note")}
    project_step = ("projects", project) in flagged
    items = {"actions": re.compile(re.escape(project) + r"-A-\d{3}"), "raid": re.compile(re.escape(project) + r"-\d{3}"),
             "decisions": re.compile(re.escape(project) + r"-D-\d{3}")}      # #68: an item of this project, in its own table

    def of_item(r):
        return r["table"] in items and bool(items[r["table"]].fullmatch(str(r["key"]))) and (r["table"], str(r["key"])) not in flagged

    def item_field_row(r):
        return of_item(r) and (r.get("op") == MADE_OP or r.get("field") in tuple(CHANGE_KINDS[r["table"]][UPDATE]) + ("closed", "priority"))

    def item_stamp_row(r):
        return of_item(r) and r.get("field") == "updated_at"
    if any(item_field_row(r) for r in rows):                        # a step of work-item fields: nothing else in it
        return all(r["via"] in (VIA, clark_store.SEED_VIA) and not r["via"].startswith(clark_store.REVERT_VIA)
                   and (item_field_row(r) or item_stamp_row(r)) for r in rows)
    archive_family = any(r.get("field") in ("archived", "active") for r in rows)
    page_family = any(r["table"] in ("report_sections", "glance_tiles") or (r["table"] == "projects" and r.get("field") in ("health", "health_reason", "note"))
                      for r in rows)
    if archive_family and page_family:                              # a mix of families is not undone from here
        return False
    stamp_ok = lambda r: r.get("field") != "updated_at" or (r["table"], str(r["key"])) in beside        # noqa: E731
    return bool(rows) and all(r["via"] in (VIA, clark_store.SEED_VIA) and not r["via"].startswith(clark_store.REVERT_VIA)
                              and stamp_ok(r) and _row_is_ours(r, project, project_step, flagged) for r in rows)


ITEM_FIELD_NAMES = {"status": "status", "workstream": "workstream", "owner": "owner", "priority": "priority",
                    "due_date": "due date", "milestone": "milestone", "made_by": "decider", "needed_by": "needed-by date",
                    "date": "decision date", "closed": "closing date"}
TILE_REF = re.compile(r"[A-Z][A-Z0-9]{2,6}\|(" + "|".join(TILES) + ")")      # #45: a tile's key
ITEM_REF = re.compile(r"[A-Z][A-Z0-9]{2,6}-(?:[AD]-)?\d{3}")        # a work item's id is what a person calls it


def _name(names, ref):
    """A section as a person knows it: by its title; a section with no title to hand is "a section", never its id. A work
    item (#68) is known by its id."""
    if isinstance(ref, str) and ref not in names and ITEM_REF.fullmatch(ref):
        return ref
    tile = TILE_REF.fullmatch(str(ref))
    if tile and ref not in names:
        return "the tile " + TILE_WORDS[tile.group(1)]             # #45: a tile is known by the page's own name for it
    if ref in names:
        return "\u201c" + names[ref] + "\u201d"
    return "a section" if "-S-" in str(ref) else "a record"          # #126: a record that was archived or restored is not a section


def _kind_word(ref):
    """What a removed row is called in the words: a work item by its kind, anything else a section."""
    ref = str(ref)
    if not ITEM_REF.fullmatch(ref):
        return "section"
    return "action" if "-A-" in ref else "decision" if "-D-" in ref else "risk or issue"


def _field_words(entry, name):
    f, to = entry["field"], entry.get("to")
    if f in ITEM_FIELD_NAMES and ITEM_REF.fullmatch(str(entry.get("ref"))):
        return f"the {ITEM_FIELD_NAMES[f]} of {name} is back to {to}" if to else f"the {ITEM_FIELD_NAMES[f]} of {name} is cleared again"
    if f == "title":
        return f"the title of {name}"
    if f == "sort_order":
        return f"the place of {name}"
    if f == "hidden":
        return f"{name} is hidden again" if to == "1" else f"{name} is shown again"
    if f == "outline":
        return f"the outline of {name} is {OUTLINE_WORDS.get(to or '', 'Automatic')} again"
    if f == "beside":
        return f"{name} is beside the next section again" if to == "1" else f"{name} is full width again"
    return f"{name}"


def _why_words(skipped, names):
    ref = skipped.get("ref")
    name = "the project's health" if skipped.get("field") in ("health", "health_reason") else _name(names, ref)
    name = name[:1].upper() + name[1:]                              # it starts the sentence
    if skipped.get("by_step"):
        return f"{name} was changed later (step {skipped['by_step']}), so it was left as it is."
    why = str(skipped.get("why") or "")
    if why == MADE_CANT_BE_PUT_BACK:
        return f"{name} has been made, so it was left as it is. Record a new decision that replaces it."
    if why == CHANGED_LATER:
        return f"{name} was changed later, so it was left as it is."
    if why == BACK_ALREADY:
        return f"{name} is back already, so it was left as it is."
    if why == GONE:
        return f"{name} is no longer in the report, so it was left as it is."
    return f"{name} couldn't be put back, so it was left as it is."


def words(reversed_, skipped, names):
    """What an undo did, in plain words, for the page's toast: "Put back: ..." and one line for each section left as it is."""
    put, seen = [], set()
    flags = [e for e in reversed_ if e["field"] == "archived"]       # #126: archive and restore, said in counts, never by id
    reversed_ = [e for e in reversed_ if e["field"] not in ("archived", "active")]      # a project's `active` goes with its archive
    for to, phrase in (("0", "restored"), ("1", "archived again")):
        refs = {e["ref"] for e in flags if e.get("to") == to}
        if len(refs) == 1 and (ITEM_REF.fullmatch(str(next(iter(refs)))) or re.fullmatch(clark_store.CODE_RE, str(next(iter(refs))))):
            put.append(f"{next(iter(refs))} {phrase}")          # one record is named (its id or code), never counted
        elif refs:
            put.append(f"{len(refs)} record{'' if len(refs) == 1 else 's'} {phrase}")
    only_flags = bool(put) and not reversed_                        # nothing but archive flags went back
    removed = {e["ref"] for e in reversed_ if e["change"] == "removed"}
    restored = {e["ref"] for e in reversed_ if e["change"] == "put back"}
    health = {e["ref"]: e for e in reversed_ if e["field"] == "health"}
    for e in reversed_:
        if e["field"] in ("health", "health_reason"):               # #45: the project's health and its reason: one line, never the reason's text
            if e["field"] == "health_reason" and e["ref"] in health:
                continue
            if e["field"] == "health":
                to = e.get("to")
                has_reason = any(x["field"] == "health_reason" and x["ref"] == e["ref"] for x in reversed_)
                phrase = "the health of the project" + (f" ({to})" if to in HEALTHS else "") + (" and its reason" if has_reason else "")
            else:
                phrase = "the reason for the project's health"
            if phrase not in seen:
                seen.add(phrase)
                put.append(phrase)
            continue
        if e["field"] == "closed" and ITEM_REF.fullmatch(str(e["ref"])):
            continue                                                # a closing date follows the status: one line says both
        if e["ref"] in removed:
            phrase = f"the new {_kind_word(e['ref'])} {_name(names, e['ref'])} was removed"
        elif e["ref"] in restored:
            phrase = f"the section {_name(names, e['ref'])} is back"
        else:
            phrase = _field_words(e, _name(names, e["ref"]))
        if phrase not in seen:
            seen.add(phrase)
            put.append(phrase)
    if len(put) > 3:
        only_items = all(ITEM_REF.fullmatch(str(e["ref"])) for e in reversed_)
        only_tiles = all(TILE_REF.fullmatch(str(e["ref"])) for e in reversed_)
        put = [f"{len(put)} changes to the work items" if only_items else f"{len(put)} changes to the tiles" if only_tiles
               else f"{len(put)} changes to the sections"]
    lines = [("Undone: " if only_flags else "Put back: ") + "; ".join(put) + "." if put else "Nothing was put back."]
    left = []
    for s in skipped:
        line = _why_words(s, names)
        if line not in left:
            left.append(line)
    return " ".join(lines + left[:3] + ([f"{len(left) - 3} more were left as they are."] if len(left) > 3 else []))


CHANGED_LATER, BACK_ALREADY, GONE = "It was changed later.", "It is back already.", "It is no longer there."
SKIP_WORDS = (("has changed since", CHANGED_LATER), ("is back already", BACK_ALREADY), ("no longer exists", GONE))


def _skipped_why(why):
    """The store's reason for leaving a row as it is, as a fixed sentence (no field name, no value)."""
    why = str(why or "")
    if "can't go back to Pending" in why:
        return MADE_CANT_BE_PUT_BACK
    for start, words in SKIP_WORDS:
        if why.startswith(start):
            return words
    return "It couldn't be put back."


def _do_undo(store, by_user, req):
    if not isinstance(req, dict):
        raise Refused(NOT_JSON_OBJECT)
    for k in req:
        if k not in ("project", "apply_id"):
            raise Refused(f"clark doesn't know '{_shown(k)}' in that request.")
    project = req.get("project")
    if not isinstance(project, str) or not re.fullmatch(clark_store.CODE_RE, project):
        raise Refused(BAD_PROJECT, code="bad_project_code")
    step = req.get("apply_id")
    if type(step) is not int or not 1 <= step < 2 ** 63:
        raise Refused(NO_UNDO)                                      # the same words as every other step that isn't ours
    if store.read("projects", ref=project) is None:
        raise Refused(NO_PROJECT, 404, "project_not_found")
    step_rows = store.step_rows(step)
    if not _eligible(step_rows, project):                           # a missing step, another project's and another route's
        raise Refused(NO_UNDO)                                      # all say the same: nothing tells which exist
    names = {r["id"]: r["title"] for r in _sections(store, project)}
    try:                                                            # still inside the caller's one lock
        done = store.undo(step, by_user)
    except Invalid as e:
        text = str(e)
        if "undone already" in text or "undid an undo" in text:
            raise Refused(UNDONE, 409, "undone") from None
        if text.startswith("clark's data is in use"):
            raise Refused(IN_USE, 503, "busy") from None
        raise Refused(NO_UNDO) from None
    rows = _sections(store, project)
    names.update({r["id"]: r["title"] for r in rows})
    reversed_ = []
    for e in done["reversed"]:
        entry = {"ref": e["ref"], "field": e["field"], "change": e["change"], "to": e.get("to")}
        if e["change"] in ("removed", "put back"):
            if any(x["ref"] == e["ref"] and x["change"] == e["change"] for x in reversed_):
                continue                                            # one line for a whole section, not one for each field
            entry["field"] = None
        reversed_.append(entry)
    skipped = [{"ref": s["ref"], "field": s["field"], "why": _skipped_why(s["why"]), "by_step": s["by_step"]} for s in done["skipped"]]
    if not reversed_ and any(s["why"] == MADE_CANT_BE_PUT_BACK for s in skipped):       # a decision that is made is not put back
        raise Refused(MADE_CANT_BE_PUT_BACK, 409, "not_undoable")
    out = {"ok": True, "apply_id": done["step_id"],
           "reversed": [{k: e[k] for k in ("ref", "field", "change")} for e in reversed_], "skipped": skipped,
           "words": words(reversed_, skipped, names), "sections": _shown_rows(rows)}
    if any(r["table"] == "glance_tiles" for r in step_rows):
        out["tiles"] = _tiles(store, project)                       # #45: the tiles as they are now
    if any(r["table"] == "projects" for r in step_rows):
        now = store.read("projects", ref=project)
        out["project"] = {"health": now["health"], "health_reason": now["health_reason"]}
    return 200, out


# ── Calls the server makes ────────────────────────────────────────────────────

def _call(path, onedrive_roots, by_user, work, req):
    """Run `work(store, by_user, req)` on a store of its own, under the one lock; (status, body). A refusal and the
    store's own rule messages are 400 in plain words; a missing database, a busy one and an unusable folder are 503; any
    other fault is raised, and the server answers it with its own 500 (no class, no text)."""
    try:
        with LOCK:
            if not Path(path).is_file():
                raise Refused(NO_DATA, 503, "no_data")              # open_store would make an empty one: never from here
            try:
                store = clark_store.open_store(path, onedrive_roots=onedrive_roots)
            except platform.PlatformError as e:
                raise Refused(str(e), 503, "no_data") from None
            except Invalid as e:
                raise Refused(IN_USE if str(e).startswith("clark's data is in use") else
                              CANT_SAVE if str(e).startswith(NOT_OPENED) else
                              str(e) if str(e).startswith(clark_store.MIGRATE_REFUSAL_STARTS) else CANT_OPEN, 503, "no_data") from None
            try:
                who = by_user() if callable(by_user) else (by_user or platform.login_name())
                return work(store, who, req)
            finally:
                store.close()
    except Refused as r:
        return r.status, {"ok": False, "message": r.message, "code": r.code}
    except Invalid as e:                                            # a store rule, in its plain words
        if str(e).startswith("clark's data is in use"):
            return 503, {"ok": False, "message": IN_USE, "code": "busy"}
        if str(e).startswith(NOT_OPENED):                           # a folder or file that can't be written to
            return 503, {"ok": False, "message": CANT_SAVE, "code": "no_data"}
        return 400, {"ok": False, "message": str(e), "code": "refused"}


def make_change(path, onedrive_roots=None, by_user=None):
    """The `change` the server calls for POST /api/change, for the database at `path`. `by_user` is a name or a function
    that gives one (default: the login name, platform.login_name; Settings can override it later)."""
    def change(req):
        return _call(path, onedrive_roots, by_user, _do_change, req)
    return change


def make_undo(path, onedrive_roots=None, by_user=None):
    """The `undo` the server calls for POST /api/undo, for the database at `path` (see make_change)."""
    def undo(req):
        return _call(path, onedrive_roots, by_user, _do_undo, req)
    return undo
