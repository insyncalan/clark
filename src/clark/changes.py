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
- A section may be added as text, needs, tracker, a template, gantt or gantttable (NEW_SECTION_TYPES, an allow-list; a gantt or gantttable section has no body, rows 926 and 1068). An update may write `body` only for a
  needs or tracker section, through the checker registry section_bodies.CHECKERS keyed by the STORED type, or for a text section
  through sanitise.clean_html (_text_body); each save replaces the whole body in one step with one Undo. A needs or tracker
  section may be deleted like a text one (Undo-able, kept in
  change_log): "we archive, we never delete" is about work items and is not breached.
- #96 R1, pictures: a section template that holds pictures (its section_kinds module has `with_picture`) never takes one through
  /api/change: a body sent there may not name `pictures`, may be at most the module's TEXT_LIMIT, and keeps the pictures already
  stored (read inside the step). A picture is set or taken out only by POST /api/section-image (`section_image(req)`): one slot,
  read and written in one step with one Undo; the picture is checked by the template's own rules (PNG, JPEG or WebP only, its
  first bytes, its size, no camera details) before the step and again by the store's checker on write.
- #96: make_section_file adds a file that section_files.py copied into the client folder to a Documents and links or One document
  section, as one step with one Undo; its request is made by clark, not by the page (it is no op of /api/change).

`change(req)` and `undo(req)` return (status, body); the server sends them. make_change / make_undo build them for one
database file; the launcher passes those to server.serve. Standard library only, Python 3.9.
"""
import json
import re
import threading
from contextlib import contextmanager
import unicodedata
from datetime import date, timedelta
from pathlib import Path

from clark import backup, doclinks, milestone_rows, milestones, order, platform, sanitise, section_bodies, section_kinds
from clark import people as people_rules
from clark import store as clark_store
from clark.limits import ITEM_TITLE_MAX      # a work item's title, at most (_checked_item_changes); one literal, in limits.py
from clark.section_kinds import base as section_base, textimage as pictures
from clark.store import Invalid

# The ops, as the request names them. Made from one string, not written one by one: tests/test_store_writer.py reads a lone
# "update" or "delete" string anywhere in src/ as SQL (its check is case-blind until #39's case-sensitive version merges), and
# these are not SQL: no op here is ever put in a statement.
NEW, UPDATE, MOVE, DELETE, ARCHIVE, RESTORE, PICK, BULK, HAND_OVER, LINK = "new update move delete archive restore pick bulk handover link".split()
MS_ADD, MS_REMOVE = "msadd", "msremove"     # row 1107: link a use case straight to milestones, and take such links off

# The allow-list: kind -> op -> the fields a request may give (`values` for new, `changes` for update). A field must also
# be a column of the table (tests/test_changes.py asserts it for each). sort_order, project, id and type (after creation)
# are in no list: they are never taken from a request.
NEWABLE = ("actions", "raid", "decisions", "milestones")      # #67: the kinds a report row can be added to (use cases: never from here)
ARCHIVABLE = ("projects", "milestones", "actions", "raid", "decisions", "use_cases", "documents")      # #126: archive and restore, no fields
DOC_FIELDS = ("title", "kind", "url", "date")        # #74: a document link's own fields; its id, project, place and archive flag never come from a request
GANTT_PROJECT_FIELDS = ("show_gantt_editor", "show_gantt_client", "gantt_tab_name", "gantt_title", "gantt_hidden_columns", "gantt_default_rows")     # row 926: the project's six Gantt settings, changed like review_after_days
PROJECT_FIELDS = ("health", "health_reason", "week_ending", "review_after_days") + GANTT_PROJECT_FIELDS + ("brand",)
GANTT_FIELDS = ("name", "type", "parent", "start", "end", "pct", "health", "depends", "owner", "workstream", "priority",
                "baseline_start", "baseline_end", "effort", "budget", "deliverable", "show", "note")     # row 926: what a request may give for a Gantt line; never its id, project, place or stamp
CHANGE_KINDS = {
    "report_sections": {NEW: ("type", "title", "body"), UPDATE: ("title", "hidden", "beside", "body"), MOVE: ("beside",), DELETE: ()},   # a body is written only for a needs or tracker section: see _section_body
    # #68: the work items board changes an item's fields, and nothing else. Only `update`: no new, move or delete for these kinds
    # (an item is closed or cancelled by its status, and archived only by archiving). priority is not in raid's list because the
    # store works it out from impact and likelihood (D-12: the status picker's Rating sets those two); `archived` is in no list.
    # #67: a work item's title is the column the page shows as its title: an action's and a RAID item's `description`, a decision's `decision`.
    "actions": {UPDATE: ("status", "workstream", "owner", "priority", "due_date", "milestone", "use_case", "description", "latest_update", "client_message", "client_visible", "client_action"), DELETE: ()},   # the peek's Latest update (an action's only); item 658: DELETE removes the item, with its links and labels
    "raid": {UPDATE: ("status", "impact", "likelihood", "workstream", "owner", "due_date", "milestone", "use_case", "description", "client_message", "client_visible", "client_action"), DELETE: ()},   # row 811: needed from the client (an action or a risk or issue; a decision has no such flag)
    "decisions": {UPDATE: ("status", "made_by", "needed_by", "date", "use_case", "decision", "client_message", "client_visible"), DELETE: ()},   # #45: use_case links an existing use case of this project, or clears the link
    # #45: the At a glance tiles and the project's health. A tile is hidden, given an outline colour or moved (its place is worked
    # out here, never sent); the project's change takes no `id` (it is the request's project) and only its health and the reason.
    "glance_tiles": {UPDATE: ("hidden", "outline"), MOVE: ()},
    "projects": {UPDATE: PROJECT_FIELDS},     # week_ending: the report bar's date (YYYY-MM-DD); #171: review_after_days, a whole number from 1 to 365; row 926: the five Gantt settings
    # #136: Milestones Movement. The dates, Done, the state with its reason, the client wording and the Movement choice. Never the
    # owner, the name, the workstream, the place or the archive flag (archive stays its own op). #458: + the internal note, the one
    # box Movement keeps for the owner (owner only: never in a reply, a Movement entry or a published file).
    "milestones": {UPDATE: ("baseline_date", "forecast_date", "actual_date", "status", "state", "state_set", "state_reason",
                            "client_message", "movement", "internal_note",
                            "name", "owner", "workstream", "percent_complete", "description")},     # row 828: + the peek's own fields (the name, owner, workstream, progress and description)
    # #164: an EXISTING use case's name, headline, status, standing text and eye (client_visible). Only `update` here: the
    # archive and restore ops below are #126's, and there is no new, move or delete for use cases.
    "use_cases": {UPDATE: ("title", "headline", "status", "standing", "client_visible", "commitment", "owner"), NEW: ("ref", "title", "status", "headline", "commitment"), LINK: (), MS_ADD: (), MS_REMOVE: ()},   # #455: and a NEW one (below); #485: link work items to it (no fields: the items' own use_case is set)
    # #67: the eye on a report row. `new` hides the row from the report and `delete` shows it again; both take only the item's id
    # (no values: the row is the pair project + item, and the project is the request's).
    # `pick` is the picker's Add (see _do_pick): it puts several hidden rows back on the page in one step.
    "report_hidden": {NEW: (), DELETE: (), PICK: ()},
    "gantt_lines": {NEW: GANTT_FIELDS, UPDATE: GANTT_FIELDS, MOVE: (), DELETE: ()},      # row 926: the eye is an update of `show`; each op is one step with one Undo
}
KIND_OP_KEYS = {"projects": {UPDATE: ("changes",)}, **{k: {NEW: ("values", "copy_of") if k in ("actions", "raid", "decisions") else ("values",)} for k in NEWABLE},   # per kind, the keys an op takes when they are not OP_KEYS' (a project has no id)
                "report_hidden": {NEW: ("id",), DELETE: ("id",), PICK: ("ids",)},
                "report_sections": {NEW: ("values", "after", "beside")},
                "gantt_lines": {NEW: ("values", "after"), UPDATE: ("id", "changes"), MOVE: ("id", "before"), DELETE: ("id",)}}      # #149: a new section may go beside the one it is added after, in the same step
KIND_OP_KEYS["use_cases"] = {NEW: ("values",), LINK: ("id", "ids"), MS_ADD: ("id", "ids"), MS_REMOVE: ("id", "ids")}    # #455: a new use case is only `values` (its reference, name, status and headline); no id is sent. #485: `link` names the use case and the work items to link to it
KIND_OP_KEYS["milestones"][UPDATE] = ("id", "changes", "rebaseline", "new_person")     # #136: a milestone's agreed date moves with a `rebaseline`; row 986: and an owner may be a new person
for _k in ("actions", "raid", "decisions"):
    KIND_OP_KEYS[_k][UPDATE] = ("id", "changes", "new_person")     # row 986: the owner update alone takes `new_person` (no other op, no other kind)
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
UNDOABLE = {"report_sections": None, "actions": None, "raid": None, "decisions": None, "report_hidden": None,
            "glance_tiles": ("hidden", "outline", "sort_order"),
            "projects": PROJECT_FIELDS + ("archived", "active"),       # #126: a project's own archive or restore step sets the flag and `active`
            "gantt_lines": None,                                                                     # row 926: a Gantt line, any field (a Gantt step holds nothing else: see _eligible)
            "milestones": ("archived", "baseline_date", "forecast_date", "actual_date", "status", "state", "state_set", "state_reason",
                           "client_message", "movement", "internal_note",
                           "name", "owner", "owner_id", "workstream", "percent_complete", "description"),     # row 828: the peek's fields (owner_id: the link that goes with an owner edit, never asked for); #136: a Movement step; its decision is a work item's row (see _movement_step); #458: + the internal note
            "use_cases": ("archived", "title", "headline", "status", "standing", "client_visible", "commitment", "owner", "owner_id"), "documents": ("archived",) + DOC_FIELDS, "workstreams": ("archived",)}
UNDO_ALSO = ("updated_at", "note")
CHANGE_KINDS["actions"][NEW] = ("description", "client_message", "client_visible", "owner", "priority", "due_date", "workstream", "milestone", "latest_update", "use_case")      # #485: a next step added from a use case's row names it; #67: a row added in the report: no id,
CHANGE_KINDS["raid"][NEW] = ("type", "description", "client_message", "owner", "impact", "likelihood", "due_date", "workstream", "milestone", "client_visible")   # raised, status or source
CHANGE_KINDS["decisions"][NEW] = ("decision", "client_message", "made_by", "status", "date", "needed_by", "client_visible", "reasoning")      # (clark gives those), and no priority on a risk (worked out)
CHANGE_KINDS["milestones"][NEW] = ("name", "baseline_date", "owner", "workstream")
# #196: one field change to several work items of one kind, in one step with one Undo (_do_bulk). A risk's impact and likelihood
# are here (its priority is worked out from them); a decision takes only who makes it.
CHANGE_KINDS["actions"][BULK] = ("status", "owner", "due_date", "priority", "workstream", "milestone")
CHANGE_KINDS["raid"][BULK] = ("status", "owner", "due_date", "impact", "likelihood", "workstream", "milestone")
CHANGE_KINDS["decisions"][BULK] = ("made_by",)
HAND_OVER_FIELD = {"actions": "owner", "raid": "owner", "decisions": "made_by"}      # #199: who has a work item; the one field a hand over changes
for _kind, _field in HAND_OVER_FIELD.items():
    CHANGE_KINDS[_kind][HAND_OVER] = (_field,)
CHANGE_KINDS["documents"] = {NEW: DOC_FIELDS, UPDATE: DOC_FIELDS}          # #74 (archive and restore are added below)
KIND_OP_KEYS["documents"] = {NEW: ("values",)}
for _kind in ARCHIVABLE:                              # #126: every record can be archived and restored, with no fields; the items keep their update
    CHANGE_KINDS.setdefault(_kind, {}).update({ARCHIVE: (), RESTORE: ()})
ITEM_KINDS = ("actions", "raid", "decisions")        # the work items; every other kind is a report section
UC_FIELDS = CHANGE_KINDS["use_cases"][UPDATE]        # #164: what a request may change on a use case
UC_REF_LIMIT = 20                                    # #455: a new use case's reference as the project writes it ("3.1"), in characters
UC_NAME_LIMIT = 120                                  # a use case's name, in characters
UC_HEADLINE_LIMIT = 300                              # its one-line headline
ITEM_NOT_NULL = ("status", "owner", "priority", "description", "decision", "impact", "likelihood")   # D-12: a rating is never cleared, as a new row (row 893: the client wording may be cleared, so it is not here)
CLEARED_BY_NEW = ("owner", "priority", "status", "description", "decision", "type", "name", "impact", "likelihood", "client_visible")   # sent as null on a new row: refused      # a work item field that has to have a value (the others may be cleared)
EXPLAIN_FIELDS = ("latest_update", "reasoning")      # #458: the one explanation line a new action or decision may start with (Movement's buttons); never said back, never in ask clark's before and after
TITLE_FIELDS = ("description", "decision", "client_message")           # #67: a work item's title, and the client wording the report rows edit in place; never said back in a reply (the page keeps what it sent); a new milestone's name is held to the same
ITEM_SHOWN = {k: ("id",) + tuple(f for f in CHANGE_KINDS[k][UPDATE] if f not in TITLE_FIELDS) + (("closed",) if k != "decisions" else ())
              + (("priority",) if k == "raid" else ()) for k in ITEM_KINDS}   # what a reply says of a changed item: a risk's priority too,
                                                     # which the store works out from impact and likelihood (said back, never taken)
FLAG_FIELDS = ("hidden", "beside")        # 0 or 1 only: a bool, a float, a string or any other number is refused
BASE_KEYS = ("project", "kind", "op", "place")
OP_KEYS = {NEW: ("values", "after"), UPDATE: ("id", "changes"), MOVE: ("id", "before", "flags"), DELETE: ("id",),
           ARCHIVE: ("id",), RESTORE: ("id",), PICK: ("ids",), BULK: ("ids", "changes", "confirm", "from_status"), HAND_OVER: ("ids", "to", "confirm"),
           LINK: ("id", "ids"), MS_ADD: ("id", "ids"), MS_REMOVE: ("id", "ids")}
MAX_PICK = 100                            # the picker adds at most this many rows in one step
MAX_BULK = 500                            # #196: a bulk change names at most this many items (the body limit allows about this many)
BULK_CONFIRM_ABOVE = 25                   # #196: more items than this need the request's `confirm`, counting every id sent
BULK_PLACE = "bulk"                       # #196: the store's place for a bulk change ("in the table" in the history)
MAX_FLAGS = 4                             # a move may set the `beside` of at most this many sections (the moved one, its old partner, its new one, the one before)
PLACES = tuple(p for p in ("menu", "cell", "report", "board", "peek", "eye", "draft", "email", "text") if p in clark_store.PLACES)   # where the page says the change was made (the step's place); #123: + peek, eye, draft, email, text. Not bulk, dashboard, excel or ask: no screen of the page is those (ask clark and Excel import write through their own routes)
MOVEMENT_PLACE = "movement"               # #136: a Movement change is written as place "dashboard" with the src_ref "Movement" (no schema change)
MADE_OP = clark_store.OP_MADE            # the log's word for a row a step made: the store's own constant
VIA = "dashboard"                         # the route of every step made here; an undo is never undone from here
ASSISTANT = "assistant"                   # #47e: the route of a step ask clark makes (make_ask_change); history says "via ask clark"
ASK_ACTOR = "clark"                       # #47e: and its actor (store.ACTORS)
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
BAD_REVIEW_DAYS = "Choose a whole number of days from 1 to 365. Nothing was changed."        # #171: the one refusal for every value that is not a whole number in that range
BAD_WEEK = "The week ending date must be a real date. The old date was kept. Pick a date and try again."
NOT_FRIDAY = "Week ending is a Friday. Pick Friday {friday}."      # #570: {friday} is DD-MM-YYYY, the Friday on or after the date
BAD_HEALTH = "Health can be On track, At risk or Off track."
HEALTH_NEEDS_REASON = "Say why in a line or two before the health changes."
PROJECT_NOT_ACTIVE = "That project is archived. Restore it first."
STALE = "Your page is out of date. Reload it, then try again."
INVALID_LAYOUT = "That isn't a valid layout change."
ITEM_NOT_MINE = "That item isn't in this project."     # another project's item, a missing one and an archived one: the same words
DOC_NOT_MINE = "That document isn't in this project. Reload the page and try again."     # #74: another project's and a missing one: the same words
DOC_KIND_WORDS = clark_store.DOC_KIND_WORDS
ALREADY_HIDDEN = "That is hidden from the report already."
NOT_HIDDEN = "That isn't hidden from the report."
PICK_NOTHING = "Choose at least one item to add."
LINK_NOTHING = "Choose at least one work item to link."
MS_NOTHING = "Choose at least one milestone."
MS_NOT_MINE = "That milestone isn't in this project."
PICK_TOO_MANY = f"Choose at most {MAX_PICK} items at a time."
PICK_NOT_HIDDEN = "One of those is already on the page. Reload the page and try again."
PICK_SENSITIVE = "A Sensitive item is never published, so it can't be added to the report."
PICK_ARCHIVED = "One of those is archived. Restore it first."
BULK_NOTHING = "Choose at least one item to change."
BULK_TOO_MANY = f"Choose at most {MAX_BULK} items at a time."
BULK_KINDS = "These items are of different kinds."
BULK_PROJECTS = "These items are in different projects."
BULK_CONFIRM = "Send confirm as true or false."
BULK_ARCHIVED = "It is archived. Restore it first."
BULK_NOT_CLOSED = "It isn't closed, so it stays as it is."       # item 1133: Reopen only undoes a close
BULK_CANCELLED = "It is cancelled, so it stays cancelled."         # item 1133: Close does not turn Cancelled into Closed
BULK_NOT_FROM = "Its status isn't one this change applies to, so it stays as it is."
BULK_DECIDED = "It has been made or withdrawn, so who made it stays as recorded. Record a new decision instead."
DECIDED = ("Made", "Withdrawn")              # #196: a decision with one of these keeps its `made_by` in a bulk change
HAND_OVER_DONE = clark_store.CLOSED_STATUSES + DECIDED     # #199: an item with one of these keeps who has it (the page's CLOSED list; a test pins the two)
BULK_CLOSED = "It is closed, so who had it stays as recorded."
HAND_OVER_NOBODY = "Say who to hand them over to: a person, not TBC."
HAND_OVER_UNKNOWN = "That name isn't on the people list. Check the spelling, or add the person to the list first."
HAND_OVER_MANY = "More than one person on the people list has that name, so clark can't tell who you mean. Nothing changed."
HAND_OVER_CHANGED = "Who has it was changed after the hand over, so it can't be undone. Nothing was changed."
HAND_OVER_ARCHIVED = "That person is archived on the people list. Restore them first, then hand over."
BULK_GONE = "It isn't in this project now. Reload the page."
BULK_NONE_CAN = "Nothing changed: none of these items can take that change."
BULK_ALREADY = "Nothing changed: they already have that."
ITEM_KEEPS_TYPE = "A work item keeps its type."
NO_ARCHIVE = "An item can't be archived by editing its details. Archiving isn't available from the page yet. Ask the clark team if you need an item hidden now."
NO_RAID_PRIORITY = "A risk or issue's priority comes from its impact and likelihood. Change those in its details."
NO_DECISION_FIELD = {"workstream": "A decision isn't part of a workstream.", "milestone": "A decision isn't tied to a milestone.",
                     "priority": "A decision has no priority."}
ITEM_VALUE_WORDS = "That value isn't one clark can use."
STORE_LEAK = re.compile(r"\(got |\b[a-z]+_[a-z_]+\b")      # a store text that shows a value it was sent or a field name: never said to a person
LATEST_UPDATE_MAX = 1000                  # the most characters a latest update may have
LATEST_LONG_WORDS = f"A latest update can be at most {LATEST_UPDATE_MAX} characters. Shorten it and try again."
LATEST_HIDDEN_WORDS = "That has a hidden character in it. Take it out and try again."     # a latest update may have line breaks, so ITEM_TEXT_WORDS would be wrong
ITEM_TEXT_WORDS = "Use plain text, with no line breaks or hidden characters."
NOTE_TEXT_WORDS = "Use plain text, with no hidden characters."      # #458: the internal note may hold line breaks
ITEM_BAD_KINDS = frozenset({"Cc", "Cf", "Cs", "Co", "Zl", "Zp"})   # as the store's section titles: control, format, surrogate, private use, separators
NOT_A_DATE = "That isn't a date. Pick a day from the calendar."
DOC_NOT_A_DATE = "That isn't a date. Write it as DD-MM-YYYY (day, month, year), or leave it empty."      # #74: a document's date is typed, there is no calendar
NOT_A_CHOICE = "That choice isn't one clark has."
NEW_NEEDS = {"actions": "Say what the action is.", "raid": "Say what the risk or issue is, and whether it is a risk, assumption, issue or dependency.",
             "decisions": "Say what the decision is.", "milestones": "Give the milestone a name."}
NEW_SOURCE = "Added by hand in clark"       # the row's source, as the prototype words it; never taken from a request
ASK_SOURCE = "Added by ask clark"          # #1009: the source of an item ask clark created (Apply), not "by hand"
COPY_SOURCE = "Duplicated from "             # #442: a copy's source, then the item's id (system/prototype/peek.js, Duplicate)
COPY_MARK = " (copy)"                        # #442: the end of a copy's title
COPIED = {                                   # #442: what Duplicate copies from the stored item (the prototype copies the item whole); never the
    "actions": ("workstream", "owner", "owner_id", "priority", "due_date", "status", "latest_update", "client_message", "milestone", "use_case"),
    "raid": ("type", "workstream", "owner", "owner_id", "response_action", "due_date", "impact", "likelihood", "status", "client_message", "milestone", "use_case"),
    "decisions": ("made_by", "owner_id", "date", "status", "needed_by", "reasoning", "options", "revisit", "use_case", "client_message"),
}                                            # id, raised, closed, archived, history or a decision's `replaces`; a RAID priority is worked out again
NOT_A_STATUS = "That status isn't available for this item."
# D-12: the status picker's Rating sets a risk's or issue's impact and likelihood; these are its own refusals.
RATING_FIELDS = ("impact", "likelihood")
NOT_A_RATING = "Impact and likelihood are each High, Medium or Low, so nothing was changed. Pick a rating from the list."
RATING_KINDS = clark_store.RATING_TYPES     # the store says which RAID types carry a rating
RATING_NOT_THIS_KIND = "Only a risk or an issue has a rating, so nothing was changed. Pick a status instead."
NO_WORKSTREAM = "That workstream isn't available."
ARCHIVED_MILESTONE = "That milestone is archived. Restore it first."
NOT_PLANNED = "A Hold or a Rebaseline is for a Planned milestone. This one is not Planned."
BAD_STATE = "That state isn't one a milestone can have."
BAD_MOVEMENT = "That Movement choice isn't available."
AGREED_STAYS = "An agreed date can't be cleared once it is set. Move it to a new date instead."
NEEDS_NEW_DATE = "Say the new agreed date, later than the current one."
STATE_NEEDS_REASON = "Say why in a line before a state that is better than the dates suggest."
STATE_TOGETHER = "Set the state and its flag together, or clear both."
DONE_STATE = "A Done milestone is Achieved. Reopen it before giving it another state."
ACHIEVED_IS_DONE = "An Achieved milestone is Done. Mark it Done first."
ACHIEVED_DATE = "The achieved date is only for a Done milestone, and it can't be after today."
ARCHIVED_USE_CASE = "That use case is archived. Restore it first."
NO_USE_CASE = "That use case isn't in this project."          # another project's and a missing one: the same words
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
UC_NAME_WORDS = f"A use case needs a name of 1 to {UC_NAME_LIMIT} characters, with no line breaks or hidden characters."
UC_HEADLINE_WORDS = f"A headline can be at most {UC_HEADLINE_LIMIT} characters, with no line breaks or hidden characters."
UC_STATUS_WORDS = "A use case's status can be On track, Flag, High risk or Done."
UC_COMMITMENTS = clark_store.COMMITMENTS                 # #709: the flag's words, defined once in the store (its writers and the page read it too)
UC_OWNER_LIMIT = 200                                     # row 875: a use case's owner, in characters (as a milestone's)
UC_COMMITMENT_WORDS = "A use case's commitment can be " + ", ".join(UC_COMMITMENTS[:-1]) + " or " + UC_COMMITMENTS[-1] + ", or none."
UC_STANDING_WORDS = "That text can't be saved. It may be too long, or not text."
UC_REF_WORDS = f"A use case needs an ID of 1 to {UC_REF_LIMIT} characters, with no line breaks or hidden characters."
UC_REF_USED = "That ID is already used by another use case of this project."
UC_NOT_MINE = NOT_MINE_RECORD                          # another project's use case and a missing one: the same words
BUILT_IN_TYPES = tuple(s["type"] for s in clark_store.DEFAULT_SECTIONS if s["type"] != "text")   # row 906: re-added from Add a section, one of each
NEW_SECTION_TYPES = ("text",) + section_bodies.BODY_TYPES + BUILT_IN_TYPES + ("gantt", "gantttable")         # what a new section may be: an allow-list, never the request's own spelling; gantttable (row 1068) is the Gantt table alone, no body either
NEW_TYPE_WORDS = "That kind of section can't be added."
NO_BODY_HERE = "That kind of section can't take content this way."
BODY_NOT_TEXT = "A section's content must be sent as text."
BIDI_CONTROLS = re.compile("[\u202a-\u202e\u2066-\u2069]")   # the nine bidi override, embedding and isolate marks: they can make text read backwards (zero-width joiners stay: emoji need them)
TEXT_BODY_MAX = 64 * 1024               # bytes of a text section's body as stored; never more than server.SECTION_BODY_MAX, the most the change route carries (a test holds it at or under, so either may be raised alone)
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

    def __init__(self, message, status=400, code="refused", extra=None):
        super().__init__(message)
        self.message, self.status, self.code = message, status, code
        self.extra = dict(extra or {})          # #196: more for the page (a bulk change's left-out items); never replaces the three


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
    known = set(BASE_KEYS) | {k for keys in OP_KEYS.values() for k in keys} | {k for ops in KIND_OP_KEYS.values() for keys in ops.values() for k in keys}
    for k in req:
        if k not in known:
            raise Refused(f"That change doesn't take '{_shown(k)}'.")
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
    if place is not None and (not isinstance(place, str) or place not in PLACES + ((MOVEMENT_PLACE,) if (kind, op) == ("milestones", UPDATE) else ())
                              + ((BULK_PLACE,) if op in (BULK, HAND_OVER) else ())):
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
        if kind in ITEM_KINDS and op != NEW:
            _item_field_words(kind, k)
        elif kind in ITEM_KINDS and (k == "archived" or (kind == "raid" and k == "priority")):
            _item_field_words(kind, k)                                  # a new row too: the same plain words
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


def _rich_field(value, plain_max, long_words, hidden_words):
    """Row 1005: a field on the one rich editor, as it is stored: clean HTML (sanitise.rich_or_plain: the editor's markup is cleaned by
    the server's own cleaner, plain text from an older caller is escaped into paragraphs), or None when it holds no words. The limit counts
    the WORDS (as the plain field did), the markup is held to TEXT_BODY_MAX bytes. Not text, too long, or a hidden character: Refused."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise Refused(ITEM_VALUE_WORDS)
    if len(value) > TEXT_BODY_MAX:
        raise Refused(long_words)
    value = sanitise.nfc_for_markup(value.replace("\r\n", "\n").replace("\r", "\n"))     # BEFORE the cleaner (a mark after a tag would compose into it and lose the words inside: sanitise.nfc_for_markup); a CR is a line break, in HTML as in plain text
    if not _plain_text(value.replace("\t", " ").replace("\n", " ")):     # a NUL, a bidi mark or a zero-width space is refused as it always was, never dropped quietly by the cleaner
        raise Refused(hidden_words)
    try:
        html = sanitise.rich_or_plain(value)
    except sanitise.SanitiseError:
        raise Refused(long_words) from None
    again = unicodedata.normalize("NFC", html)                 # an entity can decode to a mark that composes: take the composed text only if it is still clean
    if sanitise.rich_or_plain(again) == again:
        html = again
    words = sanitise.plain_text(html)                          # every check below is of the FINAL stored value (a count before NFC could end over the limit)
    if not _plain_text(words.replace("\n", " ")):
        raise Refused(hidden_words)
    if not words.strip():
        return None
    if len(words) > plain_max or len(html.encode("utf-8")) > TEXT_BODY_MAX:
        raise Refused(long_words)
    return html


def _checked_item_changes(fields, blank_clears=()):
    """A work item's fields with their values checked: plain text or None (None only where the field may be cleared), and
    short. The store checks the rest (the words a status may take, a real date, an active workstream, this project's
    milestone); its refusals are put into plain words in _do_item_change. `blank_clears` names the text fields an edit may clear by
    sending null or a blank string (row 893: the client wording, so the title is read again). The work item tables keep "no wording"
    as an empty string (the column is NOT NULL DEFAULT ''), so a clear is written as "", the state a new row starts in; a new row refuses a blank one."""
    fields = {k: (None if k == "use_case" and v == "" else v) for k, v in fields.items()}    # an empty use case clears the link
    cleared = {k: "" for k, v in fields.items() if k in blank_clears and (v is None or isinstance(v, str) and not v.strip())}
    fields = {k: v for k, v in fields.items() if k not in cleared}
    sent_latest = "latest_update" in fields                        # a JSON false is a value to refuse, not a field left out
    latest = fields.pop("latest_update", None)                     # the peek's Latest update: plain text, line breaks allowed, up to 1000 characters, blank clears it
    if sent_latest:                                                # row 1005: the rich editor's HTML (or plain text from an older caller), stored as clean HTML
        if isinstance(latest, str) and "\r" in latest:             # as before: a carriage return is a hidden character in a latest update (a milestone's description folds it into a line break)
            raise Refused(LATEST_HIDDEN_WORDS)
        latest = _rich_field(latest, LATEST_UPDATE_MAX, LATEST_LONG_WORDS, LATEST_HIDDEN_WORDS)
    flag = {k: _flag(v) for k, v in fields.items() if k in ("client_visible", "client_action")}         # #97: the eye, 0 or 1 as on a use case; nothing else is a number
    fields = {k: v for k, v in fields.items() if k not in flag}
    for k, v in fields.items():
        if v is None and k in ITEM_NOT_NULL or v is not None and (not isinstance(v, str) or not v.strip() or len(v) > ITEM_TITLE_MAX):
            raise Refused(ITEM_VALUE_WORDS)
        if isinstance(v, str) and not _plain_text(v):
            raise Refused(ITEM_TEXT_WORDS)
    out = {k: (unicodedata.normalize("NFC", v).strip() if isinstance(v, str) else v) for k, v in fields.items()}
    out.update(cleared)
    if sent_latest:
        out["latest_update"] = latest
    return {**out, **flag}


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
    if text.startswith("use case ") and ("isn't here" in text or " belongs to " in text):
        return NO_USE_CASE
    for start, words in STORE_WORDS:
        if start in text:
            return words
    return ITEM_VALUE_WORDS


def _checked_changes(fields):
    """An update's fields with their values checked: the title as the store keeps it, a flag as 0 or 1, a body as text (what
    the body holds is checked by the checker of the stored section's type, inside the step: see _section_body)."""
    out = {}
    for k, v in fields.items():
        if k == "body":
            if not isinstance(v, str):
                raise Refused(BODY_NOT_TEXT)
            out[k] = v
        else:
            out[k] = _flag(v) if k in FLAG_FIELDS else clark_store.section_title(v)
    return out


def _section_body(section, body):
    """The canonical text of `body` for the stored section `section` (a row of this project), through the one checker registry
    (section_bodies.CHECKERS, keyed by the STORED type: the request never says which type it is). Only a needs or tracker section
    takes a body here, and a text section (Summary, This week, Next week) through the cleaner (_text_body). A refusal is plain words and never
    quotes the content. The store checks it again on write (every write, an Undo too). A section that holds pictures (#96 R1)
    takes its words here and keeps its stored pictures (_keep_pictures)."""
    if section["type"] == "text":
        return _text_body(body)
    if section["type"] not in section_bodies.CHECKERS:
        raise Refused(NO_BODY_HERE)
    try:
        if _picture_kind(section["type"]) is not None:
            return _keep_pictures(section, body)
        return clark_store.check_section_body(section["type"], body)
    except Invalid as e:
        raise Refused(str(e)) from None


def _text_body(body):
    """A text section's body as it is stored: the server's own cleaner (sanitise.clean_html) decides what is kept, never the page's
    copy of it. Bidi override marks are dropped first. Over TEXT_BODY_MAX bytes once cleaned, or text the cleaner refuses (too long), is refused in plain words."""
    body = BIDI_CONTROLS.sub("", body)      # dropped BEFORE the cleaner, so it judges the text that is kept (a mark inside a link's address can't hide it)
    try:
        text = sanitise.clean_html(body)
    except sanitise.SanitiseError:
        raise Refused(WORDS_TOO_LONG) from None
    if len(text.encode("utf-8")) > TEXT_BODY_MAX:
        raise Refused(WORDS_TOO_LONG)
    return text


# ── Pictures in a section template (#96 R1) ───────────────────────────────────

PICTURES = "pictures"                     # the one field of a picture template's body that only POST /api/section-image sets
IMAGE_KEYS = ("project", "section", "slot", "image", "place")
NO_PICTURE_HERE = "That section can't hold a picture."
PICTURE_NOT_TEXT = "Send the picture as text, or nothing to take it out."
WORDS_TOO_LONG = "That text is too long to save. Shorten it and try again."


def _picture_kind(kind):
    """The section_kinds module of a template that holds pictures (it has `with_picture`), or None."""
    module = section_kinds.REGISTRY.get(kind)
    return module if module is not None and callable(getattr(module, "with_picture", None)) else None


def _stored_value(section):
    """The stored body of a section as a value (None when it has none, or when it no longer checks: then it starts afresh)."""
    try:
        text = clark_store.check_section_body(section["type"], section.get("body") or "")
    except Invalid:
        return None
    return json.loads(text) if text else None


def _keep_pictures(section, body):
    """A picture template's words from /api/change, with the pictures already stored kept: the sent body is checked on its own
    (it may not name `pictures`, and is at most the template's TEXT_LIMIT), then the stored pictures are put back and the whole
    is checked again. The pictures are read from the row read inside the step, so a picture added meanwhile is never lost."""
    module = _picture_kind(section["type"])
    if len(body) > module.TEXT_LIMIT:
        raise Refused(WORDS_TOO_LONG)
    text = clark_store.check_section_body(section["type"], body)
    value = json.loads(text) if text else {"v": 1}
    if type(value) is not dict:
        raise Refused(section_bodies.NOT_READABLE)
    if PICTURES in value:
        raise Refused(pictures.PICTURES_OWN_WAY)
    stored = _stored_value(section)
    if type(stored) is dict and stored.get(PICTURES):
        value[PICTURES] = stored[PICTURES]
    return clark_store.check_section_body(section["type"], section_bodies.canonical(value))


def _do_section_image(store, by_user, req):
    """POST /api/section-image: {project, section, slot, image, place}. Sets the picture in one slot of a picture template (or
    takes it out when `image` is null), as one step with one Undo. The picture is checked by the template's own rules before the
    step (pictures.picture: a PNG, JPEG or WebP data address, its first bytes, its size, no camera details) and
    the whole body again by the store's checker on write. The reply is the change route's: apply_id, ref and the sections."""
    if not isinstance(req, dict):
        raise Refused(NOT_JSON_OBJECT)
    for k in req:
        if k not in IMAGE_KEYS:
            raise Refused(f"A picture request doesn't take '{_shown(k)}'. Reload the page and try again.")
    project = req.get("project")
    if not isinstance(project, str) or not re.fullmatch(clark_store.CODE_RE, project):
        raise Refused(BAD_PROJECT, code="bad_project_code")
    place = req.get("place", "report")
    if not isinstance(place, str) or place not in PLACES:
        raise Refused(BAD_PLACE)
    ref, slot, image = req.get("section"), req.get("slot"), req.get("image")
    if not isinstance(ref, str):
        raise Refused(NOT_MINE)
    if not isinstance(slot, str):
        raise Refused(pictures.BAD_SLOT)
    if image is not None and not isinstance(image, str):
        raise Refused(PICTURE_NOT_TEXT)
    if store.read("projects", ref=project) is None:
        raise Refused(NO_PROJECT, 404, "project_not_found")
    table = "report_sections"
    with store.step(VIA, by_user, place=place) as st:               # BEGIN IMMEDIATE: the body read next is the body written
        rows = _sections(store, project)
        _mine(ref, [r["id"] for r in rows], NOT_MINE)
        section = next(r for r in rows if r["id"] == ref)
        module = _picture_kind(section["type"])
        if module is None:
            raise Refused(NO_PICTURE_HERE)
        try:
            if image is not None:
                pictures.picture(image, module.PICTURE_MAX)
            value = module.with_picture(_stored_value(section), slot, image)
        except section_base.Bad as e:
            raise Refused(str(e)) from None
        try:
            body = clark_store.check_section_body(section["type"], section_bodies.canonical(value))
        except Invalid as e:
            raise Refused(str(e)) from None
        if body != section.get("body"):
            st.update(table, ref, {"body": body})
        apply_id = st.peek_apply_id()                               # None when nothing changed: the page shows no Undo
    return 200, {"ok": True, "apply_id": apply_id, "ref": ref, "sections": _shown_rows(_sections(store, project))}


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


def _on_its_own(rows, ref):
    """Whether section `ref` is on its own: not half of a pair, read the way the page reads pairs (a 1 on a second half or on
    the last row is ignored)."""
    ids = [r["id"] for r in rows]
    flag = {r["id"]: r["beside"] for r in rows}
    i = 0
    while i < len(ids):
        if flag[ids[i]] == 1 and i + 1 < len(ids):
            if ref in (ids[i], ids[i + 1]):
                return False
            i += 2
        else:
            i += 1
    return True


def _stray_flags(rows):
    """#439 (prototype views.js:251): the sections whose `beside` is 1 though the page reads it as nothing, so a flag left behind by an
    add, a move or an earlier change never starts a new pair later: a 1 on the second half of a pair, and a 1 on the last section."""
    ids = [r["id"] for r in rows]
    flag = {r["id"]: r["beside"] for r in rows}
    out, i = [], 0
    while i < len(ids):
        if flag[ids[i]] == 1 and i + 1 < len(ids):
            if flag[ids[i + 1]] == 1:
                out.append(ids[i + 1])
            i += 2
        else:
            if flag[ids[i]] == 1:
                out.append(ids[i])
            i += 1
    return out


def _do_change(store, by_user, req):
    project, kind, op, place = _shape(req)
    if store.read("projects", ref=project) is None:
        raise Refused(NO_PROJECT, 404, "project_not_found")
    table = next(k for k in CHANGE_KINDS if k == kind)              # the allow-list's own spelling, never the request's
    if (kind == "report_hidden" or op in (BULK, HAND_OVER, DELETE) or (op == NEW and kind in NEWABLE)) and clark_store.is_archived(store.con, project):
        raise Refused(PROJECT_NOT_ACTIVE)                           # #67: an archived project is read only; said alike for show, hide, pick and a new row
    if op in (ARCHIVE, RESTORE):
        return _do_archive(store, by_user, project, table, op, place, req.get("id"))
    columns = clark_store.columns(store.con, table)
    if kind == "gantt_lines":                                        # row 926: a Gantt line's add, edit, eye, move and delete
        return _do_gantt_change(store, by_user, req, project, table, columns, op, place)
    if kind == "documents":                                         # #74: a document link's add or edit
        return _do_document_change(store, by_user, req, project, table, columns, op, place)
    if kind == "use_cases":                                         # #164: first, and before any work item line, so that a use case
        return _do_use_case_change(store, by_user, req, project, table, columns, place, op)       # is never taken by the work item path
    if op == NEW and kind in NEWABLE:
        return _do_new_row(store, by_user, req, project, table, columns, place)
    if op == BULK:
        return _do_bulk(store, by_user, req, project, table, columns, place)
    if op == HAND_OVER:
        return _do_hand_over(store, by_user, req, project, place)
    if kind in ITEM_KINDS and op == DELETE:
        return _do_delete_item(store, by_user, req, project, table, place)
    if kind in ITEM_KINDS:
        return _do_item_change(store, by_user, req, project, table, columns, place)
    if kind == "milestones":
        return _do_milestone_change(store, by_user, req, project, table, columns, place)
    if kind == "glance_tiles":
        return _do_tile_change(store, by_user, req, project, table, columns, op, place)
    if kind == "projects":
        return _do_project_change(store, by_user, req, project, table, columns, place)
    if kind == "report_hidden":
        return _do_hidden_change(store, by_user, req, project, table, op, place)
    ref = req.get("id")
    changes = None
    if op == NEW:
        values = _fields(req.get("values"), kind, op, columns, "the new section's values")
        new_type = next((t for t in NEW_SECTION_TYPES if t == values.get("type", "text")), None)    # the allow-list's own spelling
        if new_type is None:
            raise Refused(NEW_TYPE_WORDS)
        title = clark_store.section_title(values["title"]) if "title" in values else DEFAULT_TITLE
        if new_type in BUILT_IN_TYPES:                              # row 906: a built-in comes back with its own title and settings
            title = next(s["title"] for s in clark_store.DEFAULT_SECTIONS if s["type"] == new_type)
        start_body = None
        if "body" in values:                                        # #929: a text section may start with its words, in the one step (one Undo)
            if not isinstance(values["body"], str):
                raise Refused(BODY_NOT_TEXT)
            if new_type != "text":
                raise Refused(NO_BODY_HERE)
            start_body = _text_body(values["body"])                 # the same cleaner and limits as an update of a text section's body
        after = _id_or_none(req.get("after"), STALE)
        beside = _flag(req["beside"]) if "beside" in req else 0
        if beside and after is None:
            raise Refused(INVALID_LAYOUT)                           # "beside" needs the section it goes beside
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
        if not rows and not store.had_sections(project):            # a project made before #65: the defaults first, in this step (not one whose sections were all deleted, row 906)
            st.seed_sections(project)
            rows = _sections(store, project)
        ids = [r["id"] for r in rows]
        if op == NEW:
            if new_type in BUILT_IN_TYPES and any(r["type"] == new_type for r in rows):
                raise Refused(NEW_TYPE_WORDS)                       # row 906: one of each built-in; said as the allow-list says it
            if beside:
                _mine(after, ids, STALE)
                if not _on_its_own(rows, after):
                    raise Refused(STALE)                            # it has a partner now: nothing is written, the page redraws
            ref = _add(st, project, rows, ids, title, after, new_type, start_body)
            if beside:
                st.update(table, after, {"beside": 1})              # the same step: one Undo removes the section and the pairing
            elif ids and after in (None, ids[-1]) and rows[-1]["beside"] == 1 and _on_its_own(rows, ids[-1]):
                st.update(table, ids[-1], {"beside": 0})            # #244: a stale flag on the lone last section would pair the new one with it; cleared in the same step, so one Undo restores both
        else:
            _mine(ref, ids, NOT_MINE)
            if op == UPDATE:
                if "body" in changes:                               # read from the stored section inside the step, so the body meets its own type's checker
                    changes["body"] = _section_body(next(r for r in rows if r["id"] == ref), changes["body"])
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
                for other in _stray_flags(_sections(store, project)):       # #439: after any move, a lone section's stray flag goes too
                    st.update(table, other, {"beside": 0})
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
    with store.step(VIA, by_user, **_where(place)) as st:
        (st.archive if op == ARCHIVE else st.restore)(table, ref)
        apply_id = st.peek_apply_id()
        counts = dict(st.result.get("counts") or {}) if table == "projects" else None
    reply = {"ok": True, "apply_id": apply_id, "ref": ref, "archived": 1 if op == ARCHIVE else 0}
    if counts is not None:
        reply["counts"] = counts
    return 200, reply


def _do_delete_item(store, by_user, req, project, table, place):
    """Item 658: delete one action, RAID item or decision of THIS project, with its links and labels, in one step with one Undo.
    Refused for an archived project (before this), a missing or archived item, and an item another record points at (the refusal
    names the pointer, in the Undo's own words). The reply gives the apply_id for the toast's Undo."""
    ref = req.get("id")
    with store.step(VIA, by_user, place=place) as st:
        row = store.read(table, ref=ref) if isinstance(ref, str) and _belongs(table, ref, project) else None
        if row is None or row["project"] != project:
            raise Refused(ITEM_NOT_MINE)
        if row["archived"]:
            raise Refused(f"{ref} is archived. Restore it first.")      # the store's own words for an archived item
        pointer = clark_store.item_pointer(st.con, ref)
        if pointer:
            raise Refused(f"{ref} can't be deleted: something refers to it ({clark_store._REF_WORDS.get(pointer[0], pointer[0])} {pointer[1]}).")
        st.delete(table, ref)
        apply_id = st.peek_apply_id()
    return 200, {"ok": True, "apply_id": apply_id, "undoable": apply_id is not None, "ref": ref, "deleted": True}


def _do_new_row(store, by_user, req, project, table, columns, place):
    """#67: add one action, risk or issue, decision or milestone to THIS project, in one step with one Undo. The request gives the row's
    own fields from the allow-list (CHANGE_KINDS[kind]["new"]); clark gives the id (store.next_id: one number sequence per project,
    shared by actions, risks and decisions, and a number once used is never used again), the project, the day it was raised, its
    status and its source. The text fields are held to the same plain-text rule as an edit, a closed set (type, impact, a priority
    ...) must be one of its words, and the store's own rules (a real date, an active workstream, this project's milestone, a made
    decision's date) are put in fixed words. A refusal writes nothing. The reply says the new row, not any other project's."""
    given = _fields(req.get("values"), table, NEW, columns, "the new row's values")
    values = _checked_item_changes({k: v for k, v in given.items() if v is not None})
    for k, v in given.items():
        if v is None and k in CLEARED_BY_NEW:
            raise Refused(ITEM_VALUE_WORDS)
    first = {"actions": "description", "raid": "description", "decisions": "decision", "milestones": "name"}[table]
    if not values.get(first) or (table == "raid" and not values.get("type")):
        raise Refused(NEW_NEEDS[table])
    for k, v in values.items():
        if (table, k) in clark_store.ALLOWED and v not in clark_store.ALLOWED[(table, k)]:
            raise Refused(NOT_A_CHOICE)
    if table in ("actions", "raid"):
        values["raised"] = clark_store.today()
    if table == "decisions":
        values.setdefault("status", "Pending")
    values.update(project=project, source=ASK_SOURCE if isinstance(store, _AskStore) else NEW_SOURCE)
    source = req.get("copy_of")
    if source is not None and (table not in ITEM_KINDS or not isinstance(source, str)):
        raise Refused(ITEM_NOT_MINE)
    with store.step(VIA, by_user, place=place) as st:               # BEGIN IMMEDIATE: the next number is read and used inside it
        link = values.get("use_case")                               # #485: a next step added from a use case's row: an existing, live use case of this project
        if link is not None:
            found = store.read("use_cases", ref=link) if _belongs("use_cases", link, project) else None
            if found is None or found["project"] != project:
                raise Refused(NO_USE_CASE)
            if found["archived"]:
                raise Refused(ARCHIVED_USE_CASE)
        if source is not None:                                      # Duplicate: the copy is the item again, so it carries the item's labels and its hiding from the report (a Sensitive item's copy stays Sensitive and unpublished), read inside the step
            was = store.read(table, ref=source) if _belongs(table, source, project) else None
            if was is None or was["project"] != project or was["archived"]:
                raise Refused(ITEM_NOT_MINE)
            values = {k: was[k] for k in COPIED[table] if was[k] is not None}     # #442: the copy's fields are the STORED item's, never the request's
            values[first] = was[first][:ITEM_TITLE_MAX - len(COPY_MARK)] + COPY_MARK
            values.update(project=project, source=COPY_SOURCE + source, **({"raised": clark_store.today()} if table in ("actions", "raid") else {}))
            values["labels"] = clark_store.labels_of(st.con, source)
            values["client_visible"] = 1 if was["client_visible"] else 0   # #424: the eye is the item's own, whatever the request carried
            hide = store.read("report_hidden", ref=f"{project}|{source}") is not None
        try:
            ref = st.create(table, values)
            if source is not None and hide:
                st.create("report_hidden", {"project": project, "item_id": ref})
        except Invalid as e:                                        # a rule of the store, in fixed words: no field name, no value
            words_ = _store_words(e)
            if words_ is None:
                raise
            raise Refused(words_) from None
        if source is None and any(values.get(f) for f in EXPLAIN_FIELDS):   # #487 (not a copy: its hiding is the item's own, above): a row that starts with Movement's explanation line starts hidden from the client (the eye off), in this same step so one Undo takes both back; the owner shows it when he chooses
            if not st.is_hidden(project, ref):
                st.create("report_hidden", {"project": project, "item_id": ref})     # only if no hiding row is there yet (a Duplicate of a hidden item makes one too; the key is project + item, so a second would fail)
        apply_id = st.peek_apply_id()
    row = store.read(table, ref=ref)
    shown = ("id",) + tuple(f for f in CHANGE_KINDS[table][NEW] if f not in TITLE_FIELDS + EXPLAIN_FIELDS + ("name", "client_visible")) + (("raised",) if table in ("actions", "raid") else ()) + ("status",) \
        + (("priority",) if table == "raid" else ())
    return 200, {"ok": True, "apply_id": apply_id, "ref": ref, "item": {k: row[k] for k in dict.fromkeys(shown)}}


NEW_PERSON_KEYS = ("name", "email")                         # row 986: the only two things a request may say of a new person
NEW_PERSON_BAD = "That isn't a name clark can add as a person. Check it and try again. Nothing was changed."
NEW_PERSON_NOT_A_NAME = "That isn't a name. Type the person's real name, or choose TBC (no one yet) to leave it open. Nothing was changed."
NEW_PERSON_ELSEWHERE = "A new person can only be added when the owner is being set. Nothing was changed."
CLEAR_ENTRY = "TBC (no one yet)"                            # row 986: the picker's label for the stored TBC; never a name to store


def _checked_new_person(req, table, place):
    """Row 986: the request's `new_person` ({name, email?}) checked for shape and text, or None when it is not there. It must go with
    the owner field alone (made_by for a decision) and name the same person (spacing aside). Returns (name, email, changes)."""
    if "new_person" not in req:
        return None
    given, field = req["new_person"], {**HAND_OVER_FIELD, "milestones": "owner"}[table]
    if place == MOVEMENT_PLACE or not isinstance(given, dict) or any(k not in NEW_PERSON_KEYS for k in given) or not isinstance(given.get("name"), str) \
            or not isinstance(given.get("email"), (str, type(None))) \
            or (given.get("email") and not _plain_text(given["email"])):
        raise Refused(NEW_PERSON_BAD)
    sent = req.get("changes")
    if not isinstance(sent, dict) or list(sent) != [field]:
        raise Refused(NEW_PERSON_ELSEWHERE)
    name = _checked_item_changes({field: given["name"]})[field]
    owner = _checked_item_changes({field: sent[field]})[field]
    name, owner = " ".join(name.split()), " ".join(owner.split())
    if people_rules.name_key(name) in people_rules.NO_PERSON or people_rules.name_key(name) == people_rules.name_key(CLEAR_ENTRY):
        raise Refused(NEW_PERSON_NOT_A_NAME, code="not_a_name")
    if name != owner or len(name) > people_rules.NAME_MAX:
        raise Refused(NEW_PERSON_BAD)
    return name, given.get("email"), {field: name}


def _add_new_person(st, store, name, email):
    """Row 986: inside the item's step, the person is added as the people list adds one by hand; a name already on the list (any case,
    accent, alias; live or archived) or a bad or taken email refuses the whole step. Returns the person's id."""
    have = store.people(archived=None)
    found = people_rules.resolve(name, have)
    if found["status"] in ("one", "many", "archived"):
        person = next(p for p in have if p["id"] == found["ids"][0])
        shown = {"id": person["id"], "name": person["name"]}
        if found["status"] == "archived":
            raise Refused(people_rules.archived_prompt(person["name"]), code="person_archived", extra={"person": shown})
        raise Refused(f"{person['name']} is already on the people list. Use this one.", code="person_exists", extra={"person": shown})
    clean, problems = people_rules.check_person({"name": name, "email": email}, have)
    if problems:
        raise Refused(" ".join(problems) + " Nothing was changed.")
    try:
        return st.add_person(source=PEOPLE_SOURCE, name=clean["name"], needs_details=0 if clean["email"] else 1, **({"email": clean["email"]} if clean["email"] else {}))
    except (Invalid, ValueError):                                   # a store rule, or the person ids used up (P-999): plain words, the step rolls back
        raise Refused(NEW_PERSON_BAD) from None


def _do_item_change(store, by_user, req, project, table, columns, place):
    """#68: change fields of one work item of THIS project, in one step (several fields, one Undo). Only `update` gets here
    (CHANGE_KINDS has no other op for these kinds). The store applies its own rules (closing, a Made decision's date, an
    active workstream, this project's milestone); a rule it refuses comes back in its words and nothing is written."""
    ref = req.get("id")
    new = _checked_new_person(req, table, place)
    changes = _checked_item_changes(_fields(req.get("changes"), table, UPDATE, columns, "the changes"), blank_clears=("client_message",))
    if not changes:
        raise Refused("Say what to change.")
    if new:
        changes = dict(new[2])
    with store.step(VIA, by_user, place=place) as st:               # BEGIN IMMEDIATE: what is read next is what is changed
        row = store.read(table, ref=ref) if isinstance(ref, str) else None
        if row is None or row["project"] != project or row["archived"]:
            raise Refused(ITEM_NOT_MINE)
        person = _add_new_person(st, store, new[0], new[1]) if new else None
        if table == "raid" and any(f in changes for f in RATING_FIELDS):   # D-12: a risk or issue only, whatever its status (#448), High, Medium or Low
            if row["type"] not in RATING_KINDS:
                raise Refused(RATING_NOT_THIS_KIND)
            if any(changes[f] not in clark_store.ALLOWED[("raid", f)] for f in RATING_FIELDS if f in changes):
                raise Refused(NOT_A_RATING)
        link = changes.get("use_case")
        if link is not None:                                        # an existing use case of this project, else the same words for every other case
            found = store.read("use_cases", ref=link) if _belongs("use_cases", link, project) else None
            if found is None or found["project"] != project:
                raise Refused(NO_USE_CASE)
        was_pending = table == "decisions" and row["status"] == "Pending"
        who = HAND_OVER_FIELD.get(table)
        if who in changes:                                          # row 866: the owner text and the person it links to change together, else a later rename or merge of the old person puts the old name back
            found = store.resolve_owner(changes[who]) if changes[who] else {"status": "blank"}
            changes["owner_id"] = found["id"] if found["status"] == "one" else None
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
                 "item": {k: now[k] for k in ITEM_SHOWN[table]}, **({"person": {"id": person, "name": new[0]}} if person else {})}


DOC_SHOWN = ("id",) + DOC_FIELDS + ("sort_order",)                  # #74: what a reply says of a document
DOC_PLAIN = frozenset({DOC_KIND_WORDS, doclinks.TITLE_ELSEWHERE, doclinks.NOT_USABLE, doclinks.EMPTY, doclinks.TOO_LONG, doclinks.HIDDEN,
                       doclinks.CREDENTIALS, doclinks.NO_SITE, doclinks.BAD_SITE, doclinks.BAD_PORT, doclinks.INTERNAL, doclinks.ONE_EMAIL, doclinks.BAD_EMAIL})


def _real_day(text):
    """Whether YYYY-MM-DD text is a day of the calendar."""
    from datetime import date
    try:
        date.fromisoformat(text)
    except ValueError:
        return False
    return True


def _checked_document(fields):
    """#74: a document's fields with their values checked before the step, in the store's own words where it has them: the title
    as a section title, the kind from doclinks.KINDS, the link through doclinks.check_link (kept as that rule gives it), the date
    empty (no date) or a real YYYY-MM-DD. Whether a title names another site needs the link too: the store checks it on write."""
    out = {}
    for k, v in fields.items():
        if k == "title":
            try:
                out[k] = clark_store.section_title(v)
            except Invalid as e:
                raise Refused(str(e)) from None
        elif k == "kind":
            if not isinstance(v, str) or v not in doclinks.KINDS:
                raise Refused(DOC_KIND_WORDS)
            out[k] = next(x for x in doclinks.KINDS if x == v)             # the list's own spelling
        elif k == "url":
            try:
                out[k] = doclinks.check_link(v)
            except doclinks.LinkError as e:
                raise Refused(str(e)) from None
        else:                                                           # the date
            if v is not None and not isinstance(v, str):
                raise Refused(DOC_NOT_A_DATE)
            v = (v or "").strip()
            if v and not (re.fullmatch(r"\d{4}-\d{2}-\d{2}", v) and _real_day(v)):
                raise Refused(DOC_NOT_A_DATE)
            out[k] = v or None
    return out


def _document_words(e):
    """The store's refusal of a document as plain words: its document, title and link sentences pass as they are (none quotes the
    value); a busy database passes through for _call to word; anything else is a fixed sentence."""
    text = str(e)
    if text.startswith("clark's data is in use") or text.startswith(NOT_OPENED):
        return None
    if text.startswith("Project ") and text.endswith("is archived. Restore it first."):
        return PROJECT_NOT_ACTIVE
    if text in DOC_PLAIN or text.startswith(("A title ", "A project can have at most ")):
        return text
    return ITEM_VALUE_WORDS


def _do_document_change(store, by_user, req, project, table, columns, op, place):
    """#74: add one document link to THIS project, or change the fields of one of its documents, in one step with one Undo. The
    request gives only the fields of DOC_FIELDS; clark gives the id (CODE-L-001, store.next_id: a number once used is never used
    again), the project and the place at the end of the list. The store checks every rule again on write. A refusal writes nothing
    and never quotes the value. An archived project takes no change; an archived document takes no edit (restore it first)."""
    if clark_store.is_archived(store.con, project):
        raise Refused(PROJECT_NOT_ACTIVE)
    ref = req.get("id")
    if op == NEW:
        values = _checked_document(_fields(req.get("values"), table, NEW, columns, "the new document's values"))
        for field, words_ in (("url", doclinks.EMPTY), ("title", "A title can't be blank."), ("kind", DOC_KIND_WORDS)):
            if field not in values:
                raise Refused(words_)
    else:
        changes = _checked_document(_fields(req.get("changes"), table, UPDATE, columns, "the changes"))
        if not changes:
            raise Refused("Say what to change.")
        if not isinstance(ref, str) or not clark_store.DOC_ID.fullmatch(ref):
            raise Refused(DOC_NOT_MINE)
    with store.step(VIA, by_user, place=place) as st:               # BEGIN IMMEDIATE: what is read next is what is changed
        try:
            if op == NEW:
                key = st.create(table, {**values, "project": project, "sort_order": order.end_slot(store.read(table, project))})
                ref = key.split("|", 1)[1]
            else:
                row = store.read(table, ref=f"{project}|{ref}")
                if row is None or row["project"] != project:
                    raise Refused(DOC_NOT_MINE)
                if row["archived"]:
                    raise Refused(BULK_ARCHIVED)
                st.update(table, f"{project}|{ref}", changes)
        except Invalid as e:                                        # a rule of the store, in plain words: no field name, no value
            words_ = _document_words(e)
            if words_ is None:
                raise
            raise Refused(words_) from None
        apply_id = st.peek_apply_id()                               # None when nothing changed: the page shows no Undo
    now = store.read(table, ref=f"{project}|{ref}")
    return 200, {"ok": True, "apply_id": apply_id, "undoable": apply_id is not None, "ref": ref,
                 "item": {k: now[k] for k in DOC_SHOWN}}


def _where(place):
    """The place and src_ref a step is written with: a Movement change is the dashboard's place with the src_ref "Movement", so the
    history can say "in Movement" without a place of its own (#136); any other place is as it was sent."""
    if place == MOVEMENT_PLACE:
        return {"place": "dashboard", "src_ref": clark_store.MOVE_PLACE_NAME}
    return {"place": place}


PEEK_PLACE = "peek"
MILESTONE_PEEK_FIELDS = ("name", "owner", "workstream", "percent_complete", "description")   # row 828: only the peek sets these
MILESTONE_DATES = ("baseline_date", "forecast_date", "actual_date")
MILESTONE_STATUSES = ("Planned", "Done")                 # Cancelled is its own matter, never set from a request
MILESTONE_MOVEMENTS = ("hold", "rebaseline")             # recover and escalate come with their own item
MILESTONE_TEXT = {"state_reason": 300, "client_message": 500, "owner": 200, "workstream": 200}
MILESTONE_DESCRIPTION_LONG_WORDS = ITEM_VALUE_WORDS      # row 1005: the refusal it always had when too long (no new word)
MILESTONE_DESCRIPTION_MAX = 2000                        # row 828: the description, in characters; it may run over several lines
INTERNAL_NOTE_MAX = 2000                                 # #458: the internal note, in characters; it may run over several lines
MILESTONE_SHOWN = ("id", "status", "baseline_date", "forecast_date", "actual_date", "state", "state_set", "state_reason",
                   "client_message", "movement")          # what a reply says of a milestone: never its internal note
REBASELINE_KEYS = ("agreed_with", "reason", "source", "date")
REBASELINE_TEXT_MAX = 500


def _checked_milestone_changes(fields):
    """A milestone's fields with their values checked: a date as text or cleared, a status and a Movement choice from a short closed
    list, a state from the milestone states, a flag as 0 or 1, text as plain short text. The store checks the rest (a real
    date, a state that agrees with the status and the dates); its refusals are put into plain words in _milestone_words."""
    out = {}
    for k, v in fields.items():
        if k in MILESTONE_DATES:
            if v is not None and (not isinstance(v, str) or len(v.strip()) > 10 or not _plain_text(v)):
                raise Refused(NOT_A_DATE)
            out[k] = (v or "").strip() or None
        elif k == "status":
            if not isinstance(v, str) or v not in MILESTONE_STATUSES:
                raise Refused(NOT_A_STATUS)
            out[k] = v
        elif k == "state":
            if v not in (None, "") and (not isinstance(v, str) or v not in milestones.STATES):
                raise Refused(BAD_STATE)
            out[k] = v or None
        elif k == "state_set":
            out[k] = _flag(v)
        elif k == "movement":
            if v not in (None, "") and (not isinstance(v, str) or v not in MILESTONE_MOVEMENTS):
                raise Refused(BAD_MOVEMENT)
            out[k] = v or None
        elif k == "internal_note":                                  # #458, row 1005: the owner's note, on the one rich editor: clean HTML, or plain text from an older caller made into paragraphs; the limit counts the words
            if isinstance(v, str) and not _plain_text(v.replace("\r", "\n").replace("\n", " ") if not sanitise.HTML_START.match(v) else v.replace("\r", "").replace("\n", "").replace("\t", "")):
                raise Refused(NOTE_TEXT_WORDS)                      # as before: a NUL, tab or bidi mark is refused, not quietly dropped by the cleaner
            out[k] = _rich_field(v.strip() if isinstance(v, str) and not sanitise.HTML_START.match(v) else v, INTERNAL_NOTE_MAX, ITEM_VALUE_WORDS, NOTE_TEXT_WORDS)
        elif k == "name":                                           # row 828: a milestone is never nameless; the same limit as a work item's title
            text = unicodedata.normalize("NFC", v).strip() if isinstance(v, str) else ""
            if not text or len(text) > ITEM_TITLE_MAX or not _plain_text(text):
                raise Refused(NEW_NEEDS["milestones"])
            out[k] = text
        elif k == "percent_complete":                               # row 828: a whole number from 0 to 100, or none
            if v is not None and (type(v) is not int or not 0 <= v <= 100):
                raise Refused(ITEM_VALUE_WORDS)
            out[k] = v
        elif k == "description":                                    # row 828: several lines; row 1005: the rich editor's HTML, stored cleaned (plain text from an older caller is escaped into paragraphs)
            out[k] = _rich_field(v, MILESTONE_DESCRIPTION_MAX, MILESTONE_DESCRIPTION_LONG_WORDS, NOTE_TEXT_WORDS)
        elif k == "client_message" and isinstance(v, str) and sanitise.HTML_START.match(v):     # row 1078 (ruled): the editor's rich wording, stored cleaned as the description is, its words held to the limit the field always had; plain text from any other caller is checked below as it always was
            out[k] = _rich_field(v, MILESTONE_TEXT[k], ITEM_VALUE_WORDS, ITEM_TEXT_WORDS)
        else:                                                       # state_reason, client_message, owner, workstream
            if v is not None and (not isinstance(v, str) or len(v) > MILESTONE_TEXT[k]):
                raise Refused(ITEM_VALUE_WORDS)
            if isinstance(v, str) and not _plain_text(v):
                raise Refused(ITEM_TEXT_WORDS)
            out[k] = unicodedata.normalize("NFC", v).strip() or None if isinstance(v, str) else None
    return out


def _checked_rebaseline(given):
    """The `rebaseline` of a request: who agreed it, the reason, the source and optionally the decision's date, all plain text.
    Whether they are given and the date is a good one is rebaseline_request's to say, in its words."""
    if given is None:
        return {}
    if not isinstance(given, dict):
        raise Refused(ITEM_VALUE_WORDS)
    for k, v in given.items():
        if k not in REBASELINE_KEYS:
            raise Refused(f"That change doesn't take '{_shown(k)}'.")
        if v is not None and (not isinstance(v, str) or len(v) > REBASELINE_TEXT_MAX):
            raise Refused(ITEM_VALUE_WORDS)
        if isinstance(v, str) and not _plain_text(v):
            raise Refused(ITEM_TEXT_WORDS)
    return dict(given)


def _milestone_words(e):
    """The store's refusal of a milestone change as a fixed plain sentence: never a field name or the value that was sent. None for
    a busy database (_call words that)."""
    text = str(e)
    if text.startswith("clark's data is in use") or text.startswith(NOT_OPENED):
        return None
    for part, words in (("is archived. Restore it first", ARCHIVED_MILESTONE), ("can't be cleared once agreed", AGREED_STAYS),
                        ("better than the dates suggest", STATE_NEEDS_REASON), ("state_set is 1 exactly", STATE_TOGETHER),
                        ("a Done milestone is Achieved", DONE_STATE), ("an Achieved milestone is Done", ACHIEVED_IS_DONE),
                        ("achieved date", ACHIEVED_DATE), ("isn't an active workstream", NO_WORKSTREAM), ("must be a date stored as", NOT_A_DATE), ("is not a real date", NOT_A_DATE)):
        if part in text:
            return words
    return ITEM_VALUE_WORDS


_TAG = re.compile(r"<(/?)([A-Za-z][A-Za-z0-9]*)[^>]*>")
_VOID = {"br", "hr", "img"}


def _first_block_end(html):
    """Where the first top-level block of clean markup ends: nesting is counted, so a list inside a list goes whole; text before the
    first tag is a block of its own; markup that never closes is one block to the end."""
    if not html.startswith("<"):
        cut = html.find("<")
        return len(html) if cut < 0 else cut
    depth = 0
    for m in _TAG.finditer(html):
        name = m.group(2).lower()
        if name in _VOID:
            if depth == 0:
                return m.end()
        elif m.group(1):
            depth -= 1
            if depth <= 0:
                return m.end()
        else:
            depth += 1
    return len(html)


def _note_with_line_trimmed(was, line):
    """(the internal note with a dated line added at the end, whether anything was dropped): the oldest go first when it would pass the limit.
    Row 1005: a stored note that is the editor's HTML (or none yet) gets the line as an escaped paragraph and loses whole blocks, counted on
    the words; an older plain note keeps its own form: newline-joined lines, trimmed by line."""
    if was and not sanitise.HTML_START.match(was):
        text = (was.strip() + "\n" + line).strip()
        kept = text
        while len(kept) > INTERNAL_NOTE_MAX and "\n" in kept:
            kept = kept.split("\n", 1)[1]
        return kept, kept != text
    html = (was or "") + "<p>%s</p>" % sanitise.text_escape(line)
    whole = html
    while len(sanitise.plain_text(html)) > INTERNAL_NOTE_MAX:
        end = _first_block_end(html)
        if end <= 0 or end >= len(html):                           # the last block (the new line) is never the one dropped
            break
        html = html[end:]
    if html != whole:
        html = sanitise.clean_html(html)                           # the Hold stores without the route's cleaner: the cut is cleaned here
    return html, html != whole


def _note_with_line(was, line):
    """The internal note with a dated line added at the end; the oldest go first when it would pass the limit."""
    return _note_with_line_trimmed(was, line)[0]


def _hold_line(today, forecast):
    """The dated line a Hold is recorded with (dates only, nothing a person typed)."""
    return "%s: holding; agreed date unchanged%s." % (milestone_rows.shown(today), ", forecast " + milestone_rows.shown(forecast) if forecast else "")


def _do_milestone_change(store, by_user, req, project, table, columns, place):
    """#136: change fields of one milestone of THIS project, in one step (several fields, one Undo). Moving the agreed date is a
    rebaseline: who agreed it, the reason and the source are asked for (milestone_rows.rebaseline_request's own rules and words),
    and the date, the new decision and the note are one step. A Hold writes its dated line as the step's note and adds it to the internal note (#458). The internal note
    (#458) may be set or cleared; row 828: so may the name, owner, workstream, progress and description. An owner edit also sets
    or clears the link to the person (owner_id), so a later rename or merge of a person leaves a typed owner alone. The archive flag is not changeable here. A refusal
    writes nothing."""
    ref = req.get("id")
    sent = _fields(req.get("changes"), table, UPDATE, columns, "the changes")
    new = _checked_new_person(req, table, place)
    if place != PEEK_PLACE and not new:                             # row 828: the peek's own fields come from the peek only; Movement (and any other place) keeps its narrow list (row 986: a new person's owner is set from the picker, in any place but Movement)
        for k in sent:
            if k in MILESTONE_PEEK_FIELDS:
                raise Refused(f"The field '{_shown(k)}' can't be set here.")
    changes = _checked_milestone_changes(sent)
    if new:
        changes = dict(new[2])
    given = _checked_rebaseline(req.get("rebaseline"))
    if not changes:
        raise Refused("Say what to change.")
    with store.step(VIA, by_user, **_where(place)) as st:          # BEGIN IMMEDIATE: what is read next is what is changed
        row = store.read(table, ref=ref) if _belongs(table, ref, project) else None
        if row is None or row["project"] != project:
            raise Refused(NO_MILESTONE)
        if row["archived"]:
            raise Refused(ARCHIVED_MILESTONE)
        person = _add_new_person(st, store, new[0], new[1]) if new else None
        if changes.get("movement") and (changes.get("status") or row.get("status") or "Planned") != "Planned":
            raise Refused(NOT_PLANNED)                              # a Hold on a Done or Cancelled milestone means nothing
        today = clark_store.today()
        agreed, rebase = row.get("baseline_date"), None
        if "baseline_date" in changes and agreed and changes["baseline_date"] != agreed:
            if changes["baseline_date"] is None:
                raise Refused(AGREED_STAYS)
            asked, errors = milestone_rows.rebaseline_request(
                row, new_date=changes["baseline_date"], agreed_with=given.get("agreed_with"), reason=given.get("reason"),
                source=given.get("source"), today=today, decided_on=given.get("date"))
            if errors:
                raise Refused(" ".join(errors))
            for k, v in asked["changes"].items():
                if k == "baseline_date" or k not in changes:        # the forecast moves with the date unless the request says where
                    changes[k] = v
            rebase = asked["rebaseline"]
            if "movement" not in changes and row.get("movement"):
                changes["movement"] = None                          # a Hold was for the old agreed date; the new one starts clear (an Undo puts it back)
        elif given and agreed:
            raise Refused(NEEDS_NEW_DATE)
        note, trimmed = None, False
        if changes.get("movement") == "hold" and rebase is None:
            note = _hold_line(today, changes.get("forecast_date", row.get("forecast_date")))
            last = sanitise.rich_plain_text(row.get("internal_note")).split("\n")[-1]
            if "internal_note" not in changes and last != note:     # #458: the Hold's dated line goes into the internal note too (the prototype's), in this same step and Undo; not twice when the last line is this same Hold today
                changes["internal_note"], trimmed = _note_with_line_trimmed(row.get("internal_note"), note)   # #603: trimmed says so in the reply
        if "owner" in changes:                                      # row 828: the link follows the owner text, as a hand over writes it: the one live person it names, else none
            found = store.resolve_owner(changes["owner"] or "")
            changes["owner_id"] = found["id"] if found["status"] == "one" else None
        try:
            st.update(table, ref, changes, rebaseline=rebase, note=note)
        except Invalid as e:                                        # a rule of the store, in fixed words: no field name, no value
            words = _milestone_words(e)
            if words is None:
                raise
            raise Refused(words) from None
        apply_id = st.peek_apply_id()                               # None when nothing changed: the page shows no Undo
        decision = next((r["key"] for r in store.step_rows(apply_id) if r["table"] == "decisions" and r["op"] == MADE_OP), None) \
            if apply_id is not None and rebase else None
        if decision:                                                # the decision names who agreed the date: owner only, so it is
            st.update("decisions", decision, {"client_visible": 0})  # made not client-visible, in this same step (an Undo removes it)
    now = store.read(table, ref=ref)
    reply = {"ok": True, "apply_id": apply_id, "undoable": apply_id is not None, "ref": ref,
             "milestone": {k: now[k] for k in MILESTONE_SHOWN}, "decision": decision, **({"person": {"id": person, "name": new[0]}} if person else {})}
    if trimmed and apply_id is not None:
        reply["note_trimmed"] = True                                # #603: the Hold's line pushed the oldest note lines out; the page says so (an Undo restores them)
    return 200, reply




def _checked_use_case_changes(fields):
    """A use case's fields with their values checked: the name and headline plain one-line text, the status one of the closed
    set, the standing text through the rich-text allow-list (the same cleaner the published file uses), the eye 0 or 1. The
    words never quote the value that was sent."""
    out = {}
    for k, v in fields.items():
        if k == "title":
            text = unicodedata.normalize("NFC", v).strip() if isinstance(v, str) else ""
            if not text or len(text) > UC_NAME_LIMIT or not _plain_text(text):
                raise Refused(UC_NAME_WORDS)
            out[k] = text
        elif k == "headline":
            text = unicodedata.normalize("NFC", v).strip() if isinstance(v, str) else None
            if text is None or len(text) > UC_HEADLINE_LIMIT or not _plain_text(text):
                raise Refused(UC_HEADLINE_WORDS)
            out[k] = text
        elif k == "status":
            if not isinstance(v, str) or v not in clark_store.ALLOWED[("use_cases", "status")]:
                raise Refused(UC_STATUS_WORDS)
            out[k] = v
        elif k == "commitment":                                     # #709: one of the three words, case exact; "" or None is no flag (NULL)
            if v is None or v == "":
                out[k] = None
            elif not isinstance(v, str) or v not in UC_COMMITMENTS:
                raise Refused(UC_COMMITMENT_WORDS)
            else:
                out[k] = v
        elif k == "owner":                                          # row 875: plain one-line text, 200 characters; blank or None clears it
            if v is not None and not isinstance(v, str):
                raise Refused(ITEM_VALUE_WORDS)
            stored = unicodedata.normalize("NFC", v).strip() if isinstance(v, str) else ""      # the limit counts what is kept, not the spaces round it
            if len(stored) > UC_OWNER_LIMIT:
                raise Refused(ITEM_VALUE_WORDS)
            if isinstance(v, str) and not _plain_text(v):
                raise Refused(ITEM_TEXT_WORDS)
            out[k] = stored or None
        elif k == "standing":
            try:
                out[k] = sanitise.clean_html(v)
            except sanitise.SanitiseError:
                raise Refused(UC_STANDING_WORDS) from None
        else:
            out[k] = _flag(v)                                       # client_visible: the eye
    return out


def _use_case_shown(row):
    """What a reply says of a use case: its own editable fields (the standing text is already clean)."""
    return {"id": row["id"], "title": row["title"], "headline": row["headline"], "status": row["status"],
            "standing": row["standing"], "client_visible": row["client_visible"], "commitment": row["commitment"], "owner": row["owner"]}


def _do_new_use_case(store, by_user, req, project, table, columns, place):
    """#455: add one use case to THIS project, in one step (it is in the change log under its own apply id and shows in History). The
    request gives its reference (as the project writes it, "3.1"), name, status and headline; clark gives the id (the next -U-
    number), the project, the place at the end of the list and the source. #455 (the owner, 03-11-2026): a new use case is hidden from the
    client by default, so client_visible is set here to 0 (eye off), not left to the table's default of 1, which existing and imported
    use cases keep; it is off the dashboard and out of the published file until the eye is turned on (the Use cases page's eye, or the
    dashboard's "Add a use case from your project record"). The name and headline are held to the same plain-text rule as an edit.
    A reference that any use case of the project already has, archived or not, is refused: an archived use case's reference is still
    taken, and a Restore must never bring back a second live one with it. The reply has no Undo (see below). Nothing is written when
    anything is refused."""
    if clark_store.is_archived(store.con, project):
        raise Refused(PROJECT_NOT_ACTIVE)
    given = _fields(req.get("values"), table, NEW, columns, "the new use case's values")
    ref_text = unicodedata.normalize("NFC", given["ref"]).strip() if isinstance(given.get("ref"), str) else ""
    if not ref_text or len(ref_text) > UC_REF_LIMIT or not _plain_text(ref_text):
        raise Refused(UC_REF_WORDS)
    values = _checked_use_case_changes({k: v for k, v in given.items() if k != "ref"})
    if "title" not in values:
        raise Refused(UC_NAME_WORDS)
    values.setdefault("status", "On track")
    values.setdefault("headline", "")
    values.update(ref=ref_text, project=project, source=NEW_SOURCE, client_visible=0)   # #455: hidden from the client until the eye is on
    with store.step(VIA, by_user, place=place) as st:               # BEGIN IMMEDIATE: the next number is read and used inside it
        mine = store.read(table, project=project)                   # live AND archived: an archived use case's reference is still taken
        if any(str(r["ref"]).strip().casefold() == ref_text.casefold() for r in mine):
            raise Refused(UC_REF_USED)
        values["sort_order"] = max([r["sort_order"] for r in mine] + [0]) + 1
        try:
            new_ref = st.create(table, values)
        except Invalid as e:                                        # a rule of the store, in fixed words
            words_ = _store_words(e)
            if words_ is None:
                raise
            raise Refused(words_) from None
    # The step is logged under its own apply id (st.create opens it), but the reply gives none: no Undo. Taking back a creation would
    # DELETE the row, and use cases are archived, never deleted, so _eligible refuses an undo of this step (NO_UNDO); Archive is the way back.
    return 200, {"ok": True, "apply_id": None, "undoable": False, "ref": new_ref,
                 "use_case": {**_use_case_shown(store.read(table, ref=new_ref)), "ref": ref_text}}


def _do_use_case_change(store, by_user, req, project, table, columns, place, op):
    """#164: change fields of one EXISTING use case of THIS project, in one step (several fields, one Undo, one history line
    each). `update` changes fields; `new` (#455) adds one, see _do_new_use_case. There is no move or delete for use cases. Another project's use case and a missing one get the same words; an archived one is not edited; nothing is
    written when anything is refused."""
    if op == NEW:
        return _do_new_use_case(store, by_user, req, project, table, columns, place)
    if op == LINK:
        return _do_link_use_case(store, by_user, req, project, table, place)
    if op in (MS_ADD, MS_REMOVE):
        return _do_use_case_milestones(store, by_user, req, project, table, place, op)
    ref = req.get("id")
    changes = _checked_use_case_changes(_fields(req.get("changes"), table, UPDATE, columns, "the changes"))
    if not changes:
        raise Refused("Say what to change.")
    with store.step(VIA, by_user, place=place) as st:               # BEGIN IMMEDIATE: what is read next is what is changed
        row = store.read(table, ref=ref) if isinstance(ref, str) else None
        if row is None or row["project"] != project:
            raise Refused(UC_NOT_MINE)
        if row["archived"]:
            raise Refused(ARCHIVED_USE_CASE)
        if "owner" in changes:                                      # row 875: the link follows the owner text (the one live person it names, else none), in this one step
            found = store.resolve_owner(changes["owner"] or "")
            changes["owner_id"] = found["id"] if found["status"] == "one" else None
        try:
            st.update(table, ref, changes)
        except Invalid as e:                                        # a rule of the store, in fixed words
            words_ = _store_words(e)
            if words_ is None:
                raise
            raise Refused(words_) from None
        apply_id = st.peek_apply_id()                               # None when nothing changed: the page shows no Undo
    return 200, {"ok": True, "apply_id": apply_id, "undoable": apply_id is not None, "ref": ref,
                 "use_case": _use_case_shown(store.read(table, ref=ref))}


def _do_link_use_case(store, by_user, req, project, table, place):
    """#485: link existing work items (actions, risks and issues, decisions, of any mix) to ONE use case of THIS project, in one step with
    one Undo: each item's `use_case` is set to the use case; an item already linked to it is left as it is, and one linked to another use
    case moves. The whole request is checked before anything is written: the use case must be this project's and live, every item
    must be a live work item of this project (an id that is not, another project's item, an archived one and a use case's own id get the
    same words and are never said back). The reply gives the Undo only when something changed."""
    if clark_store.is_archived(store.con, project):
        raise Refused(PROJECT_NOT_ACTIVE)
    given = req.get("ids")
    if not isinstance(given, list) or not given:
        raise Refused(LINK_NOTHING)
    if len(given) > MAX_PICK:
        raise Refused(PICK_TOO_MANY)
    ids = []
    for item in given:
        if not (isinstance(item, str) and clark_store.ITEM_ID.fullmatch(item) and clark_store.item_table(item) in ITEM_KINDS):
            raise Refused(ITEM_NOT_MINE)
        if item not in ids:
            ids.append(item)
    ref = req.get("id")
    with store.step(VIA, by_user, place=place) as st:               # BEGIN IMMEDIATE: what is read next is what is changed
        found = store.read(table, ref=ref) if isinstance(ref, str) else None
        if found is None or found["project"] != project:
            raise Refused(UC_NOT_MINE)
        if found["archived"]:
            raise Refused(ARCHIVED_USE_CASE)
        plan = []
        for item in ids:
            item_table = clark_store.item_table(item)
            row = store.read(item_table, ref=item)
            if row is None or row["project"] != project or row["archived"]:
                raise Refused(ITEM_NOT_MINE)
            if row["use_case"] != ref:
                plan.append((item_table, item))
        for item_table, item in plan:
            st.update(item_table, item, {"use_case": ref})
        apply_id = st.peek_apply_id()                               # None when nothing changed: the page shows no Undo
    return 200, {"ok": True, "apply_id": apply_id, "undoable": apply_id is not None, "ref": ref, "linked": [item for _, item in plan]}


def _do_use_case_milestones(store, by_user, req, project, table, place, op):
    """Row 1107: link ONE use case of THIS project straight to several of its milestones (msadd), or take such links off (msremove), in one
    step with one Undo. The whole request is checked before anything is written: the use case must be this project's and live, every
    milestone a live milestone of this project (a missing one, another project's and an archived one get the same words, never said back).
    A milestone already linked (msadd) or not linked (msremove) is left as it is. The reply gives the Undo only when something changed."""
    if clark_store.is_archived(store.con, project):
        raise Refused(PROJECT_NOT_ACTIVE)
    given = req.get("ids")
    if not isinstance(given, list) or not given:
        raise Refused(MS_NOTHING)
    if len(given) > MAX_PICK:
        raise Refused(PICK_TOO_MANY)
    ids = []
    for m in given:
        if not (isinstance(m, str) and clark_store.ITEM_ID.fullmatch(m) and clark_store.item_table(m) == "milestones"):
            raise Refused(MS_NOT_MINE)
        if m not in ids:
            ids.append(m)
    ref = req.get("id")
    changed = []
    with store.step(VIA, by_user, place=place) as st:               # BEGIN IMMEDIATE: what is read next is what is changed
        found = store.read(table, ref=ref) if isinstance(ref, str) else None
        if found is None or found["project"] != project:
            raise Refused(UC_NOT_MINE)
        if found["archived"]:
            raise Refused(ARCHIVED_USE_CASE)
        for m in ids:
            row = store.read("milestones", ref=m)
            if row is None or row["project"] != project or (row["archived"] and op == MS_ADD):
                raise Refused(MS_NOT_MINE)
        for m in ids:
            try:
                done = (clark_store.link_use_case_milestone if op == MS_ADD else clark_store.unlink_use_case_milestone)(st, ref, m)
            except Invalid as e:                                    # a rule of the store, in fixed words
                words_ = _store_words(e)
                if words_ is None:
                    raise
                raise Refused(words_) from None
            if done:
                changed.append(m)
        apply_id = st.peek_apply_id()                               # None when nothing changed: the page shows no Undo
    return 200, {"ok": True, "apply_id": apply_id, "undoable": apply_id is not None, "ref": ref, "milestones": changed,
                 "linked": clark_store.use_case_milestone_ids(store.con, ref)}


HIDABLE = ("milestones", "actions", "raid", "decisions", "use_cases")      # what the eye can hide: the store's own list of items a report shows


def _hidable(ref):
    """Whether `ref` is the id of a kind of item the report shows (milestone, action, RAID item, decision, use case)."""
    return isinstance(ref, str) and (bool(clark_store.ITEM_ID.fullmatch(ref)) and clark_store.item_table(ref) in HIDABLE
                                     or bool(clark_store.DOC_ID.fullmatch(ref)))       # #74: + a document, by its own id


def _report_row(store, project, ref):
    """The row a hidable id names (an item by its id; #74: a document by this project's key for it), or None."""
    if clark_store.DOC_ID.fullmatch(ref):
        return store.read("documents", ref=f"{project}|{ref}")
    return store.read(clark_store.item_table(ref), ref=ref)


def _blocked_labels(store):
    """The label names (lower case) that keep a row out of every published file: Sensitive, and any label whose behaviour or default
    choice is exclude. The same rule as publish._excluded_labels, so the picker's Add never offers what a publish would drop."""
    return clark_store.excluded_label_names(dict(r) for r in store.read("labels"))


def _hidden_ids(store, code):
    """The ids the project's report hides, in order."""
    return sorted(r["item_id"] for r in store.read("report_hidden", code))


def _do_hidden_change(store, by_user, req, project, table, op, place):
    """#67: the eye. `new` hides one item of THIS project from the report, `delete` shows it again; one step, one Undo. The item is
    named by its id and checked before anything is written: an id that is not a real item of this project (another project's, a
    missing one, anything that is not an id) is refused in the same words and never said back. An archived item may still be hidden
    or shown: the flag is about the report, not the item."""
    if op == PICK:
        return _do_pick(store, by_user, req, project, table, place)
    ref = req.get("id")
    if not _hidable(ref):
        raise Refused(ITEM_NOT_MINE)
    key = f"{project}|{ref}"
    with store.step(VIA, by_user, place=place) as st:               # BEGIN IMMEDIATE: what is read next is what is changed
        row = _report_row(store, project, ref)
        if row is None or row["project"] != project:
            raise Refused(ITEM_NOT_MINE)
        there = store.read("report_hidden", ref=key) is not None
        if op == NEW:
            if there:
                raise Refused(ALREADY_HIDDEN)
            st.create(table, {"project": project, "item_id": ref})
        else:
            if not there:
                raise Refused(NOT_HIDDEN)
            st.cancel(table, key)
        apply_id = st.peek_apply_id()
    return 200, {"ok": True, "apply_id": apply_id, "ref": ref, "hidden": _hidden_ids(store, project)}


PICK_NOTE = "Added to the report"                                  # #67: history only, on a row that was off but not hidden: the step has no report_hidden row to mark it as the picker's, and a step that only turned a flag on must not be mistaken for it


def _do_pick(store, by_user, req, project, table, place):
    """#67 (a reviewer's MEDIUM on the pure part): the picker's Add, in ONE step with ONE Undo. For each chosen item: take its report_hidden
    row away if it has one, and turn `client_visible` on where it is off, because #39's publish drops a row for either, and an Add
    that did only the first would show the row in the editor and still leave it out of the file. Only a row that is hidden in one of
    those two ways can be chosen (else the page is out of date); a Sensitive item (a label that excludes) is refused whole, so a row
    the picker lists can always be published; an archived or another project's item is refused. The whole request is checked before
    anything is written, so one bad id adds nothing. The reply says which rows were also shown to the client."""
    given = req.get("ids")
    if not isinstance(given, list) or not given:
        raise Refused(PICK_NOTHING)
    if len(given) > MAX_PICK:
        raise Refused(PICK_TOO_MANY)
    ids = []
    for ref in given:
        if not _hidable(ref):
            raise Refused(ITEM_NOT_MINE)
        if ref not in ids:
            ids.append(ref)
    shown = []
    with store.step(VIA, by_user, place=place) as st:               # BEGIN IMMEDIATE: what is read next is what is changed
        blocked = _blocked_labels(store)
        plan = []
        for ref in ids:
            item_table = clark_store.item_table(ref)
            row = _report_row(store, project, ref)
            if row is None or row["project"] != project:
                raise Refused(ITEM_NOT_MINE)
            if row["archived"]:
                raise Refused(PICK_ARCHIVED)
            if any(str(n).casefold() in blocked for n in clark_store.labels_of(store.con, ref)):
                raise Refused(PICK_SENSITIVE)
            there = store.read("report_hidden", ref=f"{project}|{ref}") is not None
            off = row.get("client_visible") == 0                    # #74: a document has no client flag
            if not there and not off:
                raise Refused(PICK_NOT_HIDDEN)
            plan.append((ref, item_table, there, off))
        for ref, item_table, there, off in plan:
            if there:
                st.cancel(table, f"{project}|{ref}")
            if off:
                st.update(item_table, ref, {"client_visible": 1}, note=None if there else PICK_NOTE)
                shown.append(ref)
        apply_id = st.peek_apply_id()
    return 200, {"ok": True, "apply_id": apply_id, "added": ids, "shown_to_client": shown, "hidden": _hidden_ids(store, project)}


def _bulk_ids(given, project, table):
    """A bulk change's `ids`: a list of 1 to MAX_BULK work item ids, each of THIS project and of `table`'s kind (#199: of any
    work item kind when `table` is None), duplicates dropped (first kept). Worked out from the id alone, before anything is read, so a refusal tells nothing of what exists."""
    if not isinstance(given, list) or not given:
        raise Refused(BULK_NOTHING)
    if len(given) > MAX_BULK:
        raise Refused(BULK_TOO_MANY)
    ids = []
    for ref in given:
        m = clark_store.ITEM_ID.fullmatch(ref) if isinstance(ref, str) and ref.isascii() else None      # no other script's digits
        if m is None:
            raise Refused(ITEM_NOT_MINE)
        if m.group(1) != project:
            raise Refused(BULK_PROJECTS)
        if table is None and clark_store.item_table(ref) not in ITEM_KINDS:
            raise Refused(ITEM_NOT_MINE)
        if table is not None and clark_store.item_table(ref) != table:
            raise Refused(BULK_KINDS)
        if ref not in ids:
            ids.append(ref)
    return ids


def _bulk_words(changed, unchanged, left_out):
    """What a bulk change did, for the page's toast: how many changed (or that nothing did), how many had it already, and each
    item left out and why (at most three named, then a count)."""
    n = len(changed)
    lines = [f"Changed {n} item{'' if n == 1 else 's'}."] if n else [BULK_ALREADY]
    if unchanged and n:
        lines.append(f"{len(unchanged)} already had that.")
    for e in left_out[:3]:
        lines.append(f"Left out {e['id']}: {e['why']}")
    if len(left_out) > 3:
        lines.append(f"{len(left_out) - 3} more were left out.")
    return " ".join(lines)


def _bulk_from_status(given, table, changes):
    """Item 1133: the optional `from_status` of a bulk status change: a list of the statuses an item may be in to take it (the page
    sends Closed and Open for Reopen, so a Delayed or Cancelled item is left out). None when not sent."""
    if given is None:
        return None
    allowed = clark_store.ALLOWED.get((table, "status"), ())
    if (not isinstance(given, list) or not given or "status" not in changes
            or any(not isinstance(v, str) or v not in allowed for v in given)):
        raise Refused(NOT_A_STATUS)
    return tuple(given)


def _do_bulk(store, by_user, req, project, table, columns, place):
    """#196: the same field change to several work items of one kind in THIS project, in ONE step: one safety copy, one Undo,
    and each item's fields logged as a single edit logs them (one history line per item and field). Each item is tried first in a
    step that is always rolled back (dry): an item that can't take the change (archived, gone, or refused by the store's own
    rules) is left out and named with fixed words, and one that has the change already is counted. Then the rest are written in
    one step; if any of them is refused there (the data changed in between), that whole step rolls back and nothing is written.
    Nothing is written when none can take it. More than BULK_CONFIRM_ABOVE ids (every id sent, before any is left out) need
    `confirm: true`; else the reply asks. Archiving is not a field here: an item is never archived or deleted from a bulk change."""
    ids = _bulk_ids(req.get("ids"), project, table)
    changes = _checked_item_changes(_fields(req.get("changes"), table, BULK, columns, "the changes"))
    if not changes:
        raise Refused("Say what to change.")
    for k, v in changes.items():
        if v is not None and (table, k) in clark_store.ALLOWED and v not in clark_store.ALLOWED[(table, k)]:
            raise Refused(NOT_A_STATUS if k == "status" else NOT_A_CHOICE)
    _bulk_confirm(req, ids)
    decided = table == "decisions" and "made_by" in changes      # the record of who decided is not rewritten
    from_status = _bulk_from_status(req.get("from_status"), table, changes)

    def kept(table_, row):
        if decided and row["status"] in DECIDED:
            return BULK_DECIDED
        if from_status is not None and row["status"] not in from_status:     # item 1133: only items in these statuses take the change
            return BULK_CANCELLED if row["status"] == "Cancelled" and changes.get("status") == "Closed" else \
                BULK_NOT_CLOSED if changes.get("status") == "Open" and "Closed" in from_status else BULK_NOT_FROM
        return None
    return _bulk_write(store, by_user, project, place, {ref: (table, changes) for ref in ids}, kept)


def _bulk_confirm(req, ids):
    """More than BULK_CONFIRM_ABOVE ids (every id sent, after duplicates are dropped) need the request's `confirm: true`."""
    confirm = req.get("confirm", False)
    if type(confirm) is not bool:
        raise Refused(BULK_CONFIRM)
    if len(ids) > BULK_CONFIRM_ABOVE and not confirm:
        raise Refused(f"Change {len(ids)} items?", 409, "confirm", {"count": len(ids)})


def _bulk_write(store, by_user, project, place, plan, kept):
    """#196, #199: write `plan` ({id: (table, changes)}) as _do_bulk says, in ONE step. `kept(table, row)` gives the fixed words
    for an item that keeps what it has (left out in the trial), or None; an item it names in the real step was changed since the
    trial, and the whole step rolls back."""
    where = {"place": place or BULK_PLACE}
    left_out, unchanged, ready = [], [], []
    with store.step(VIA, by_user, dry=True, **where) as st:         # always rolled back: only a trial of each item
        for ref, (table, changes) in plan.items():
            row = store.read(table, ref=ref)
            if row is None or row["project"] != project:
                left_out.append({"id": ref, "why": BULK_GONE})
                continue
            if row["archived"]:
                left_out.append({"id": ref, "why": BULK_ARCHIVED})
                continue
            why = kept(table, row)
            if why:
                left_out.append({"id": ref, "why": why})
                continue
            try:
                st.update(table, ref, changes)
            except Invalid as e:                                    # a rule of the store, in fixed words: no field name, no value
                words_ = _store_words(e)
                if words_ is None:
                    raise
                left_out.append({"id": ref, "why": words_})
                continue
            (unchanged if store.read(table, ref=ref) == row else ready).append(ref)
    if not ready:
        if left_out and not unchanged:
            why = {e["why"] for e in left_out}
            raise Refused(next(iter(why)) if len(why) == 1 else BULK_NONE_CAN, 400, "none_can", {"left_out": left_out})
        return 200, {"ok": True, "apply_id": None, "undoable": False, "changed": [], "unchanged": unchanged, "left_out": left_out,
                     "words": _bulk_words([], unchanged, left_out), "items": []}
    with store.step(VIA, by_user, **where) as st:                   # BEGIN IMMEDIATE: one step for every item that can take it
        changed = []
        for ref in ready:
            table, changes = plan[ref]
            before = store.read(table, ref=ref)
            if kept(table, before):
                raise Refused(STALE)                                # closed, made or withdrawn since the trial: the whole step rolls back
            try:
                st.update(table, ref, changes)
            except Invalid as e:                                    # changed since the trial: the whole step rolls back
                if _store_words(e) is None:
                    raise
                raise Refused(STALE) from None
            (changed if store.read(table, ref=ref) != before else unchanged).append(ref)    # what was written, not what the trial said
        apply_id = st.peek_apply_id()
    items = []
    for ref in changed:
        table = plan[ref][0]
        shown = tuple(dict.fromkeys(ITEM_SHOWN[table] + CHANGE_KINDS[table][BULK] + (("priority",) if table == "raid" else ())))
        row = store.read(table, ref=ref)
        items.append({k: row[k] for k in shown})
    return 200, {"ok": True, "apply_id": apply_id, "undoable": apply_id is not None, "changed": changed, "unchanged": unchanged,
                 "left_out": left_out, "words": _bulk_words(changed, unchanged, left_out), "items": items}


def _hand_over_to(store, given):
    """#199: who the items go to, as it will be written. Cleaned as a single owner change is. Then the people list's one resolver
    (#115): once anyone is on the list, the name (or an alias) must be exactly one live person, and is written as the list has it;
    with no one on the list yet, any name is taken, as a single owner change takes it. TBC or blank is no one: refused.
    Returns (name, person id): the id of the one live person it names, or None for a name taken as free text (#199: the design
    note's contract says a hand over writes the person's id beside the name)."""
    to = _checked_item_changes({"owner": given})["owner"]
    found = store.resolve_owner(to)
    if found["status"] == "blank":
        raise Refused(HAND_OVER_NOBODY)
    if found["status"] == "many":
        raise Refused(HAND_OVER_MANY)
    if found["status"] == "archived":
        raise Refused(HAND_OVER_ARCHIVED)
    if found["status"] == "one":
        return _checked_item_changes({"owner": next(p["name"] for p in store.people() if p["id"] == found["id"])})["owner"], found["id"]
    if store.people():
        raise Refused(HAND_OVER_UNKNOWN)
    return to, None


def _do_hand_over(store, by_user, req, project, place):
    """#199: give several work items to someone else: the same person (`to`) on items of any of the three kinds in THIS project,
    in ONE step with one Undo, one history line per item: an action's or risk's owner, a decision's made_by. The bulk change's
    checks and writer (_bulk_ids, _bulk_confirm, _bulk_write), across kinds. A closed item and a decision made or withdrawn keep
    who has them (left out and named). Only that field changes, and the owner's id beside it (the person's, or NULL for free text,
    in the same step so one Undo restores both): never a status, an archive or a delete."""
    ids = _bulk_ids(req.get("ids"), project, None)
    to, person = _hand_over_to(store, req.get("to"))
    _bulk_confirm(req, ids)
    plan = {ref: (t, {HAND_OVER_FIELD[t]: to, "owner_id": person}) for ref, t in ((ref, clark_store.item_table(ref)) for ref in ids)}

    def kept(table, row):
        if row["status"] not in HAND_OVER_DONE:
            return None
        return BULK_DECIDED if table == "decisions" else BULK_CLOSED
    return _bulk_write(store, by_user, project, place, plan, kept)


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


def brand_ids():
    """#944: the brand ids a project may take: generic and the installed ones. T1 knows only generic; the brand library fills this in."""
    return {"generic"}


def _checked_project_changes(fields):
    """The project's health and reason, checked for type and the closed set. The store's rule that a changed health has a
    reason in the same change stays the only such rule."""
    out = dict(fields)
    for k, v in fields.items():
        if k == "health" and (not isinstance(v, str) or v not in HEALTHS):
            raise Refused(BAD_HEALTH)
        if k == "week_ending":
            try:
                if not isinstance(v, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", v):
                    raise ValueError(v)
                day = date.fromisoformat(v)
            except ValueError:
                raise Refused(BAD_WEEK) from None
            if day.weekday() != 4:       # #570: Friday is the week end everywhere; the Friday offered is the one on or after that day (a weekend rolls forward)
                friday = day + timedelta(days=(4 - day.weekday()) % 7)
                raise Refused(NOT_FRIDAY.format(friday=friday.strftime("%d-%m-%Y")))
        if k == "review_after_days" and (type(v) is not int or not clark_store.REVIEW_DAYS_RANGE[0] <= v <= clark_store.REVIEW_DAYS_RANGE[1]):
            raise Refused(BAD_REVIEW_DAYS)      # #171: a real int only (not True, 14.5, "14", None or a list), checked before the step opens
        if k == "brand" and (type(v) is not str or v not in brand_ids()):
            raise Refused(BAD_OP)       # #944: an id that is not generic or installed (a real string only), refused before the step opens
        if k in ("show_gantt_editor", "show_gantt_client"):
            out[k] = _flag(v)                                   # row 926: 0 or 1 as a whole number; True, 1.0 or "1" are refused
        if k == "gantt_default_rows" and v is not None and (type(v) is not int or not clark_store.GANTT_ROWS_RANGE[0] <= v <= clark_store.GANTT_ROWS_RANGE[1]):
            raise Refused(clark_store.GANTT_BAD_ROWS)       # row 926: a real whole number from 1 to 500, or None (every row)
        if k in ("gantt_tab_name", "gantt_title", "gantt_hidden_columns"):
            try:                                                # row 926: the store's own check, called here so the first refusal is the route's
                out[k] = (clark_store.gantt_hidden_columns(v) if k == "gantt_hidden_columns" else
                          clark_store.gantt_plain(v, clark_store.GANTT_TAB_LIMIT if k == "gantt_tab_name" else clark_store.GANTT_TITLE_LIMIT,
                                                  clark_store.GANTT_BAD_TAB if k == "gantt_tab_name" else clark_store.GANTT_BAD_TITLE, blank_ok=k == "gantt_title"))
            except Invalid as e:
                raise Refused(str(e)) from None
        if k == "health_reason":
            try:
                out[k] = clark_store.health_reason_html(v)      # the store's own check, called here so the first refusal is the route's; row 1005: stored as the editor's HTML (plain text from an older caller is made into paragraphs)
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
    return text if text in clark_store.REASON_REFUSALS or text in clark_store.GANTT_REFUSALS else ITEM_VALUE_WORDS


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
                 "project": {"health": now["health"], "health_reason": now["health_reason"], "week_ending": now["week_ending"],
                             "review_after_days": now["review_after_days"], "brand": now["brand"],
                             **{f: now[f] for f in GANTT_PROJECT_FIELDS}}}



# ── Gantt lines (row 926) ─────────────────────────────────────────────────────

GANTT_NOT_MINE = NOT_MINE_RECORD                                    # another project's line and a missing one: the same words
GANTT_WORKED_OUT = "{} is worked out; it cannot be typed over."     # Days and Status are never stored: {} is the column's name
GANTT_WORKED_OUT_NAMES = {"days": "Days", "status": "Status", "outline": "The outline number", "outline_number": "The outline number"}
GANTT_NEW_NAMES = {"phase": "New phase", "task": "New task", "milestone": "New milestone"}     # a line added with no name starts with one
GANTT_TEXT_FIELDS = ("name", "owner", "workstream", "deliverable", "note")
GANTT_DATE_FIELDS = ("start", "end", "baseline_start", "baseline_end")
GANTT_ENUM_FIELDS = ("type", "health", "priority")
GANTT_CLEARED_TO = {"parent": None, "baseline_start": None, "baseline_end": None, "effort": None, "budget": None}     # a blank clears these to no value; the other text columns hold ''
GANTT_SHOWN = ("id", "type", "name", "parent", "start", "end", "pct", "health", "depends", "owner", "workstream",
               "priority", "baseline_start", "baseline_end", "effort", "budget", "deliverable", "show", "note", "sort_order")   # what a reply says of a line: all of it (the editor's own page)


def _gantt_words(e):
    """The store's refusal of a Gantt change as a fixed plain sentence; None for a busy database (_call words that). The store's
    own sentences for a line are already plain; its generic ones (a date, a number, a choice) are put in the Gantt words."""
    text = str(e)
    if text.startswith("clark's data is in use") or text.startswith(NOT_OPENED):
        return None
    if text in clark_store.GANTT_REFUSALS or (text.startswith('There is no line "') and text.endswith('" to depend on.')) \
            or (text.startswith('There is no line "') and text.endswith('" to be the parent.')):
        return text
    if "pct" in text:
        return clark_store.GANTT_BAD_PCT
    if "must be a date" in text or "is not a real date" in text:
        return clark_store.GANTT_BAD_DATE
    if "must be one of" in text:
        return clark_store.GANTT_BAD_CHOICE
    if text.startswith("Project ") and text.endswith("is archived. Restore it first."):
        return PROJECT_NOT_ACTIVE
    return ITEM_VALUE_WORDS


def _checked_gantt(given, columns):
    """A Gantt line's fields from a request with their JSON types checked and blanks turned into what the column holds; the values'
    own rules (a real date, the order of two dates, a parent that is a phase, depends) are the store's, inside the step. A field that
    is worked out is refused with its own words; a field that is not in the allow-list is refused as everywhere else."""
    if given is None:
        given = {}
    if not isinstance(given, dict):
        raise Refused("Send the line's values as an object.")
    out = {}
    for k, v in given.items():
        if k in GANTT_WORKED_OUT_NAMES:
            raise Refused(GANTT_WORKED_OUT.format(GANTT_WORKED_OUT_NAMES[k]))
        if k not in GANTT_FIELDS or k not in columns:
            raise Refused(f"The field '{_shown(k)}' can't be set here.")
        if k == "show":
            out[k] = _flag(v)
        elif k == "pct":
            if type(v) is not int or not 0 <= v <= 100:
                raise Refused(clark_store.GANTT_BAD_PCT)
            out[k] = v
        elif k in ("effort", "budget"):
            if v is None or (isinstance(v, str) and not v.strip()):
                out[k] = None
            elif isinstance(v, bool) or not isinstance(v, (int, float)) or v != v or not 0 <= v <= clark_store.gantt_number_limit(k):
                raise Refused(clark_store.GANTT_BAD_NUMBER)
            else:
                out[k] = v
        elif k == "depends":
            if v is None:
                v = ""
            if isinstance(v, list) and all(isinstance(x, str) for x in v):
                v = ",".join(v)
            if not isinstance(v, str):
                raise Refused(clark_store.GANTT_BAD_TEXT)
            out[k] = v
        elif k == "parent":
            if v is not None and not isinstance(v, str):
                raise Refused(clark_store.GANTT_NO_PARENT.format(""))
            out[k] = (v or "").strip() or None
        elif k in GANTT_DATE_FIELDS:
            if v is None or (isinstance(v, str) and not v.strip()):
                if k in ("start", "end"):
                    raise Refused(clark_store.GANTT_BAD_DATE)
                out[k] = None
            elif not isinstance(v, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", v) or not _real_day(v):
                raise Refused(clark_store.GANTT_BAD_DATE)
            else:
                out[k] = v
        elif k in GANTT_ENUM_FIELDS:
            if k == "type" and v not in clark_store.ALLOWED[("gantt_lines", "type")]:
                raise Refused(clark_store.GANTT_BAD_TYPE)
            if k != "type" and not (v is None or v == "" or (isinstance(v, str) and v in clark_store.ALLOWED[("gantt_lines", k)])):
                raise Refused(clark_store.GANTT_BAD_CHOICE)
            out[k] = v or ""
        else:                                                       # a text field: the store tidies it and holds it to its limit
            if k == "name" and (not isinstance(v, str) or not v.strip()):
                raise Refused(clark_store.GANTT_NO_NAME)
            if v is not None and not isinstance(v, str):
                raise Refused(clark_store.GANTT_BAD_TEXT)
            out[k] = v if v is not None else ""
    return out


def _gantt_lines(store, project):
    return order.in_order(store.read("gantt_lines", project=project))


def _gantt_reply(store, project, ref, apply_id, **more):
    lines = _gantt_lines(store, project)
    return 200, {"ok": True, "apply_id": apply_id, "undoable": apply_id is not None, "ref": ref,
                 "lines": [{k: r[k] for k in GANTT_SHOWN} for r in lines], **more}


def _gantt_new_values(values, lines, after_row, project):
    """The values of a new line: what the request gave and, for what it left out, a name by type, the dates of the line it follows
    (else today; a milestone is on one day) and the parent that line has (after a phase, under it). Nothing is taken from the request
    but its allow-listed fields; the project and the place are clark's."""
    out = dict(values)
    out.setdefault("type", "task")
    out.setdefault("name", GANTT_NEW_NAMES[out["type"]] if out["type"] in GANTT_NEW_NAMES else GANTT_NEW_NAMES["task"])
    day = after_row["end"] if after_row else clark_store.today()
    out.setdefault("start", day)
    out.setdefault("end", out["start"])
    if out.get("type") == "milestone":
        out["end"] = out["start"]
    if "parent" not in out and after_row and out["type"] != "phase":
        out["parent"] = after_row["id"] if after_row["type"] == "phase" else after_row["parent"]
    if out.get("parent") is None:
        out.pop("parent", None)
    out["project"] = project
    return out


def _gantt_milestone_dates(changes, now):
    """`changes` for a line `now`, with a milestone's one date kept: changing its Start moves its End too, and an End alone is refused."""
    if changes.get("type", now["type"]) == "milestone":
        if "end" in changes and changes["end"] != changes.get("start", now["start"]):
            raise Refused(clark_store.GANTT_MILESTONE_ONE_DATE)
        changes["end"] = changes.get("start", now["start"])
    return changes


def gantt_import_write(store, st, project, ref, given):
    """Row 926, the workbook import: one Gantt line of `project` added (`ref` None; at the end of the list, with the next free id) or
    changed, inside the caller's step, through the page's own checks (_checked_gantt, _gantt_new_values, _gantt_milestone_dates) and the
    store's rules. Returns the line's id. A refusal is an Invalid in the Gantt words; nothing the request says is taken for the id,
    the project, the place or the stamp."""
    try:
        if clark_store.is_archived(store.con, project):
            raise Refused(PROJECT_NOT_ACTIVE)
        if isinstance(given, dict) and "show" in given and type(given["show"]) is not int:
            raise Refused(clark_store.GANTT_BAD_CHOICE)             # the sheet's Yes or No that could not be read
        values = _checked_gantt(given, clark_store.columns(store.con, "gantt_lines"))
        if ref is None:
            lines = _gantt_lines(store, project)
            return st.create("gantt_lines", {**_gantt_new_values(values, lines, None, project), "sort_order": order.end_slot(lines)})
        now = store.read("gantt_lines", ref=ref)
        if now is None or now["project"] != project:
            raise Refused(GANTT_NOT_MINE)
        st.update("gantt_lines", ref, _gantt_milestone_dates(values, now))
        return ref
    except Refused as e:
        raise Invalid(e.message) from None
    except Invalid as e:
        words_ = _gantt_words(e)
        if words_ is None:
            raise
        raise Invalid(words_) from None


def _do_gantt_change(store, by_user, req, project, table, columns, op, place):
    """Row 926: add a Gantt line, change its fields (the eye is `show`), move it or delete it, in THIS project; each is one step with
    one Undo. A new line goes just after the line named by `after` (None: at the end) and gets the next free id; renumbering is
    display only, so nothing is renumbered here and ids never change. Deleting a line takes its id out of the lines that depend on it
    and the parent from the lines under it, in the same step. The store checks every rule again on write, and a refusal writes
    nothing. A milestone has one date: changing its Start moves its End too, and changing its End alone is refused."""
    if clark_store.is_archived(store.con, project):
        raise Refused(PROJECT_NOT_ACTIVE)
    ref = req.get("id")
    values = changes = None
    if op == NEW:
        values = _checked_gantt(req.get("values"), columns)
        after = _id_or_none(req.get("after"), STALE)
    elif op == UPDATE:
        changes = _checked_gantt(req.get("changes"), columns)
        if not changes:
            raise Refused("Say what to change.")
    elif op == MOVE:
        if "before" not in req:
            raise Refused("Say where to move it.")
        before = _id_or_none(req.get("before"), STALE)
    if op != NEW and not (isinstance(ref, str) and clark_store.GANTT_ID.fullmatch(ref) and _belongs(table, ref, project)):
        raise Refused(GANTT_NOT_MINE)
    with store.step(VIA, by_user, place=place) as st:               # BEGIN IMMEDIATE: what is read next is what is changed
        lines = _gantt_lines(store, project)
        by_id = {r["id"]: r for r in lines}
        try:
            if op == NEW:
                if after is not None and after not in by_id:
                    raise Refused(STALE)
                made = _gantt_new_values(values, lines, by_id.get(after), project)
                end = order.end_slot(lines)
                new_place, renumber = end, {}
                if after is not None and lines.index(by_id[after]) + 1 < len(lines):
                    nxt = lines[lines.index(by_id[after]) + 1]["id"]
                    renumber = order.section_slot(lines + [{"id": "", "sort_order": end}], "", nxt)
                    new_place = renumber.pop("", end)
                ref = st.create(table, {**made, "sort_order": new_place})
                for other, slot in renumber.items():
                    st.update(table, other, {"sort_order": slot})
            elif ref not in by_id:
                raise Refused(GANTT_NOT_MINE)
            elif op == UPDATE:
                st.update(table, ref, _gantt_milestone_dates(changes, by_id[ref]))
            elif op == MOVE:
                if before is not None and before not in by_id:
                    raise Refused(STALE)
                if before == ref:
                    raise Refused("A line can't be moved before itself.")
                for other, slot in order.section_slot(lines, ref, before).items():
                    st.update(table, other, {"sort_order": slot})
            else:
                st.cancel(table, ref)
        except Invalid as e:                                        # a rule of the store, in fixed words: no field name, no value
            words_ = _gantt_words(e)
            if words_ is None:
                raise
            raise Refused(words_) from None
        apply_id = st.peek_apply_id()                               # None when nothing changed: the page shows no Undo
    return _gantt_reply(store, project, ref, apply_id)


def _add(st, project, rows, ids, title, after, kind="text", body=None):
    """Make a section of type `kind` (text, needs or tracker) just after section `after` (None: at the end); its id. A needs or
    tracker section starts with the body the registry gives it (section_bodies.EMPTY), never one from the request. When no whole number fits between its
    neighbours, the rows are renumbered in the same step (clark.order)."""
    if after is not None:
        _mine(after, ids, STALE)
    end = order.end_slot(rows)
    new_place, renumber = end, {}
    if after is not None and ids.index(after) + 1 < len(ids):
        probe = rows + [{"id": "", "sort_order": end}]              # the new row, at the end, then moved up to its place
        renumber = order.section_slot(probe, "", ids[ids.index(after) + 1])
        new_place = renumber.pop("", end)
    start = {"body": section_bodies.EMPTY[kind]} if section_bodies.EMPTY.get(kind) else {}
    if body:
        start = {"body": body}                                      # #929: only a text section is given one (checked by the caller)
    ref = st.create("report_sections", {"project": project, "type": kind, "title": title, "sort_order": new_place, **start})
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
    if table == "gantt_lines":                                      # row 926
        return bool(clark_store.GANTT_ID.fullmatch(key)) and key.startswith(project + "-GNT-")
    if table == "report_hidden":                                    # #67: the key is "CODE|item id"; the separator keeps ABC from matching ABCD
        return key.startswith(f"{project}|{project}-") and field in (None, "project", "item_id", clark_store.REMOVED)
    if table == "glance_tiles":                                     # #45
        return key in {f"{project}|{t}" for t in TILES} and (row["via"] == clark_store.SEED_VIA or field in allowed + UNDO_ALSO)
    if table == "workstreams":                                      # archived only along with its project: it has no single archive
        return project_step and field in ("archived", "updated_at") and (table, key) in flagged and key.startswith(project + "-W-")
    if table not in ARCHIVABLE:
        return False
    if field == "archived":
        return _belongs(table, key, project)
    if table == "projects" and key == project and field in PROJECT_FIELDS + ("note",):      # #45: the health change; #171: and the review days
        return True
    if field == "updated_at":                                       # the stamp goes only with its own record's flag or change
        return ((table, key) in flagged and _belongs(table, key, project)) or (table == "projects" and key == project)
    return table == "projects" and project_step and field == "active" and key == project


def _ours(store, step, rows, project):
    """_eligible, and #47e: an assistant-route step is ours only when ask clark made it. The one test for a single undo and a batch."""
    if rows and any(r["table"] == "use_case_milestones" for r in rows):      # row 1107: a step of direct milestone links is one family, all of this project's use cases
        mine = clark_store.use_case_link_ids(store.con, project)
        return all(r["table"] == "use_case_milestones" and r["via"] == VIA and str(r["key"]).split("|")[-1] in mine for r in rows)
    return (_eligible(rows, project, _is_hand_over(store, step, rows)) and
            not (any(r["via"] == ASSISTANT for r in rows) and store.step_actors(step) != {ASK_ACTOR}))


def _is_hand_over(store, step, rows):
    """#199: whether step `step` (its Store.step_rows `rows`) is a hand over: written in the bulk place, only the owner (or made_by)
    and its owner_id link of work items, with at least one link row. Nothing else writes a link from here, so the link is the
    mark. Read only; a step with no link row is never asked about its history."""
    if not any(r.get("field") == "owner_id" for r in rows):
        return False
    if any(r["table"] not in HAND_OVER_FIELD or r.get("field") not in ("owner_id", HAND_OVER_FIELD[r["table"]], "updated_at")
           or r.get("op") == MADE_OP for r in rows):
        return False
    key = next(r["key"] for r in rows if r.get("field") == "owner_id")
    return any(e["step"] == step and e["place"] == BULK_PLACE for e in store.history(key))


def _hand_over_changed(store, step, rows, all_gone=True):
    """#199, #620: the id of an item that stops this hand over being undone from here, or None. The owner and its link go back
    together or not at all. When an item's owner (or made_by) text was changed after the hand over, the store leaves that item alone,
    link and all, and undoes the others (Store.undo's per-item skip, #620), so such an item blocks nothing, unless every item of the
    step changed (`all_gone`: nothing would go back, so a single Undo says so and is refused). A link-only item (no owner text row in
    the step, so the store has no name to judge by) whose name was edited since is judged here by the name the new link has: it
    blocks the whole step, as the store would put its link back beside the new name. Read only."""
    if not _is_hand_over(store, step, rows):
        return None
    items, changed = [], []
    for key in dict.fromkeys(r["key"] for r in rows if r.get("field") == "owner_id"):
        table = clark_store.item_table(str(key))
        field = HAND_OVER_FIELD[table]
        mine = [e for e in store.history(key) if e["step"] == step]
        text = [e for e in mine if e["field"] == field]
        if text:
            expected = text[0]["after"]                             # history is newest first: this step's last word on the field
        else:
            link = next(e for e in mine if e["field"] == "owner_id")["after"]
            named = [p["name"] for p in store.people(archived=None) if p["id"] == link]
            if not named:
                continue                                            # a link cleared with the name as it was: nothing to compare
            expected = named[0]
        items.append(key)
        row = store.read(table, ref=key)
        if row is not None and str(row[field] if row[field] is not None else "") != str(expected if expected is not None else ""):
            if not text:
                return key                                          # a link alone can't be skipped by the store: the step is left whole
            changed.append(key)
    if all_gone and changed and len(changed) == len(items):
        return changed[0]
    return None


def _eligible(rows, project, hand_over=False):
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
    beside = {(r["table"], str(r["key"])) for r in rows if r.get("field") in ("archived", "active") + PROJECT_FIELDS + ("note",)}
    project_step = ("projects", project) in flagged
    if any(r["table"] == "gantt_lines" for r in rows):              # row 926: a Gantt step is one family: lines of this project and nothing else
        return all(r["table"] == "gantt_lines" and r["via"] == VIA and _row_is_ours(r, project, False, flagged) for r in rows)
    items = {"actions": re.compile(re.escape(project) + r"-A-\d{3}"), "raid": re.compile(re.escape(project) + r"-\d{3}"),
             "decisions": re.compile(re.escape(project) + r"-D-\d{3}"),
             "milestones": re.compile(re.escape(project) + r"-M-\d{3}"),     # #68: an item of this project, in its own table (#67: + a milestone, for a row added in the report)
             "use_cases": re.compile(re.escape(project) + r"-U-\d{3}"),     # #164: a use case of this project, edited as one family
             "documents": re.compile(re.escape(project) + r"\|" + re.escape(project) + r"-L-\d{3}")}     # #74: a document of this project, by its key
    shown_kinds = {**items, "use_cases": re.compile(re.escape(project) + r"-U-\d{3}")}    # #67: the picker's step also reaches these two

    milestone = re.compile(re.escape(project) + r"-M-\d{3}")

    gone = clark_store.REMOVED

    def deleted_row(r):                                             # item 658: a deleted item, and the links, labels and hiding that went with it, all of this project
        key = str(r["key"])
        if r.get("field") != gone or r["via"] != VIA:
            return False
        if r["table"] in ITEM_KINDS:
            return bool(items[r["table"]].fullmatch(key))
        if r["table"] == "links":
            return all(re.fullmatch(re.escape(project) + r"-(?:[AD]-)?\d{3}", end) for end in key.split("|")[:2])
        if r["table"] == "item_labels":
            return bool(re.match(re.escape(project) + r"-(?:[AD]-)?\d{3}\|", key))
        return r["table"] == "report_hidden" and key.startswith(project + "|" + project + "-")
    if any(r.get("field") == gone and r["table"] in ITEM_KINDS for r in rows):
        return all(deleted_row(r) for r in rows)                    # a delete is one family: nothing else in its step

    def movement_row(r):                                            # #136: a Movement step's own rows: the milestone's fields, and the decision a rebaseline made
        if r["table"] == "milestones":
            return bool(milestone.fullmatch(str(r["key"]))) and r.get("field") in UNDOABLE["milestones"] + UNDO_ALSO
        return (r["table"] == "decisions" and bool(items["decisions"].fullmatch(str(r["key"])))
                and (r.get("op") == MADE_OP or r.get("field") in ("client_visible", "updated_at")))
    if any(r["table"] == "milestones" and r.get("op") != MADE_OP and r.get("field") in CHANGE_KINDS["milestones"][UPDATE] for r in rows):
        return all(r["via"] in (VIA, ASSISTANT) and movement_row(r) for r in rows)      # nothing else in it (#47e: ask clark's step too)

    def of_item(r):
        return r["table"] in items and bool(items[r["table"]].fullmatch(str(r["key"]))) and (r["table"], str(r["key"])) not in flagged

    def item_field_row(r):
        if not of_item(r):
            return False
        fields = tuple(CHANGE_KINDS[r["table"]].get(UPDATE, ())) + tuple(CHANGE_KINDS[r["table"]].get(BULK, ())) + ("closed", "priority")   # #196: + a bulk change's
        if r.get("field") == "owner_id":                            # #199: a hand over's link to the person, in a hand over's step only (_is_hand_over), with or without the owner text beside it
            if r["table"] == "use_cases":                           # row 875: the link beside a use case's owner text, in the same step (never a hand over)
                return any(o["table"] == "use_cases" and str(o["key"]) == str(r["key"]) and o.get("field") == "owner" for o in rows)
            return r["table"] in HAND_OVER_FIELD and (hand_over or any(      # row 866: or the link a single owner edit (or an ask clark change) writes beside the owner text of the same item in the same step
                o["table"] == r["table"] and str(o["key"]) == str(r["key"]) and o.get("field") == HAND_OVER_FIELD[r["table"]] for o in rows))
        return (r.get("op") == MADE_OP and r["table"] != "use_cases") or r.get("field") in fields

    def item_stamp_row(r):
        return of_item(r) and r.get("field") == "updated_at"
    def pick_row(r):                                                # #67: the picker's one step: a hidden row put back, a client flag turned on
        if r["table"] == "report_hidden":
            return _row_is_ours(r, project, False, flagged)
        return (r["table"] in shown_kinds and bool(shown_kinds[r["table"]].fullmatch(str(r["key"])))
                and r.get("field") in ("client_visible", "updated_at", "note"))
    def copy_row(r):                                                # #488: Duplicate's one step: the new item, the labels it carries and its hiding from the report (all made here)
        if r["table"] == "item_labels":
            return r.get("op") == MADE_OP and any(items[k].fullmatch(str(r["key"]).split("|", 1)[0]) for k in ITEM_KINDS)
        if r["table"] == "report_hidden":
            return r.get("op") == MADE_OP and _row_is_ours(r, project, False, flagged)
        return item_field_row(r) or item_stamp_row(r)
    if (any(r["table"] in ITEM_KINDS and of_item(r) and r.get("op") == MADE_OP for r in rows)
            and any(r["table"] in ("item_labels", "report_hidden") for r in rows)):
        return all(r["via"] == VIA and copy_row(r) for r in rows)
    picked = any(r.get("field") == "note" and r["table"] in shown_kinds and bool(shown_kinds[r["table"]].fullmatch(str(r["key"]))) for r in rows)
    made_item = any(r.get("op") == MADE_OP and r["table"] in ("actions", "decisions") and of_item(r) for r in rows)      # #487: a new row that started hidden is a work-item step with its hiding in it
    if not made_item and (picked or any(r["table"] == "report_hidden" for r in rows)) and any(r.get("field") == "client_visible" for r in rows):
        return all(r["via"] in (VIA, clark_store.SEED_VIA) and not r["via"].startswith(clark_store.REVERT_VIA) and pick_row(r) for r in rows)
    made_people = {str(r["key"]) for r in rows if r["table"] == "people" and r.get("op") == MADE_OP}      # row 986: the person an owner edit added, in the same step

    def person_row(r):
        return r["table"] == "people" and str(r["key"]) in made_people and r["via"] == VIA
    if any(item_field_row(r) for r in rows):                        # a step of work-item fields: nothing else in it (#47e: ask clark's too)
        return all(person_row(r) or (r["via"] in (VIA, clark_store.SEED_VIA) or (r["via"] == ASSISTANT and r["table"] in ASK_KINDS))      # ask clark's: its own kinds only, never a use case
                   and not r["via"].startswith(clark_store.REVERT_VIA) and (item_field_row(r) or item_stamp_row(r) or (made_item and r["table"] == "report_hidden" and _row_is_ours(r, project, False, flagged))) for r in rows)
    archive_family = any(r.get("field") in ("archived", "active") for r in rows)
    page_family = any(r["table"] in ("report_sections", "glance_tiles", "report_hidden") or (r["table"] == "projects" and r.get("field") in PROJECT_FIELDS + ("note",))
                      for r in rows)
    if archive_family and page_family:                              # a mix of families is not undone from here
        return False
    stamp_ok = lambda r: r.get("field") != "updated_at" or (r["table"], str(r["key"])) in beside        # noqa: E731
    return bool(rows) and all(r["via"] in (VIA, clark_store.SEED_VIA) and not r["via"].startswith(clark_store.REVERT_VIA)
                              and stamp_ok(r) and _row_is_ours(r, project, project_step, flagged) for r in rows)


UC_FIELD_NAMES = {"title": "name", "headline": "headline", "standing": "standing text", "commitment": "commitment", "owner": "owner"}
ITEM_FIELD_NAMES = {"description": "title", "decision": "title", "status": "status", "workstream": "workstream", "owner": "owner", "priority": "priority",
                    "due_date": "due date", "milestone": "milestone", "made_by": "decider", "needed_by": "needed-by date",
                    "date": "decision date", "closed": "closing date", "use_case": "use case", "impact": "impact", "likelihood": "likelihood",
                    "latest_update": "latest update"}
UC_REF = re.compile(r"[A-Z][A-Z0-9]{2,6}-U-\d{3}")                  # #164: a use case's id; the words call it by its name
TILE_REF = re.compile(r"[A-Z][A-Z0-9]{2,6}\|(" + "|".join(TILES) + ")")      # #45: a tile's key
ITEM_REF = re.compile(r"[A-Z][A-Z0-9]{2,6}-(?:[ADMU]-)?\d{3}")        # a work item's id is what a person calls it
HIDDEN_REF = re.compile(r"[A-Z][A-Z0-9]{2,6}\|([A-Z][A-Z0-9]{2,6}-(?:[ADMUL]-)?\d{3})")      # #67: a hidden row's key; the item is what a person calls it
DOC_REF = re.compile(r"[A-Z][A-Z0-9]{2,6}\|[A-Z][A-Z0-9]{2,6}-L-\d{3}")     # #74: a document's key; the words call it by its title
DOC_FIELD_NAMES = {"title": "title", "kind": "kind", "url": "link", "date": "date"}
MILESTONE_REF = re.compile(r"[A-Z][A-Z0-9]{2,6}-M-\d{3}")           # #136: a milestone is called by its id in an Undo's words
MILESTONE_FIELD_NAMES = {"baseline_date": "agreed date", "forecast_date": "forecast date", "actual_date": "achieved date",
                         "status": "status"}
MILESTONE_KEPT_AS_WAS = {"state": "state", "state_set": "state", "state_reason": "state", "client_message": "client wording",
                         "movement": "Movement choice", "internal_note": "internal note"}        # said without the value: a reason or wording is never repeated


GANTT_REF = re.compile(r"[A-Z][A-Z0-9]{2,6}-(GNT-\d{3})")             # row 926: a Gantt line is known by the id the page shows (GNT-001), never by its name
GANTT_FIELD_NAMES = {"name": "name", "type": "type", "parent": "parent", "start": "start", "end": "end", "pct": "done %",
                     "health": "health", "depends": "dependency list", "owner": "owner", "workstream": "workstream", "priority": "priority",
                     "baseline_start": "baseline start", "baseline_end": "baseline end", "effort": "effort", "budget": "budget",
                     "deliverable": "deliverable", "note": "notes", "sort_order": "place"}


def _name(names, ref):
    """A section as a person knows it: by its title; a section with no title to hand is "a section", never its id. A work
    item (#68) is known by its id."""
    if GANTT_REF.fullmatch(str(ref)):
        return "line " + GANTT_REF.fullmatch(ref).group(1)         # row 926
    if isinstance(ref, str) and ref not in names and (ITEM_REF.fullmatch(ref) or MILESTONE_REF.fullmatch(ref)):
        return ref
    hidden = HIDDEN_REF.fullmatch(str(ref))
    if hidden and ref not in names:
        return "a document" if "-L-" in hidden.group(1) else hidden.group(1)     # #67: the item, never the pair; #74: a document, never its id
    tile = TILE_REF.fullmatch(str(ref))
    if tile and ref not in names:
        return "the tile " + TILE_WORDS[tile.group(1)]             # #45: a tile is known by the page's own name for it
    if ref in names:
        return "\u201c" + names[ref] + "\u201d"
    return "a section" if "-S-" in str(ref) else "a document" if DOC_REF.fullmatch(str(ref)) else "a record"          # #126: a record that was archived or restored is not a section


def _kind_word(ref):
    """What a removed row is called in the words: a work item by its kind, anything else a section."""
    ref = str(ref)
    if GANTT_REF.fullmatch(ref):
        return "line"                                               # row 926
    if DOC_REF.fullmatch(ref):
        return "document"                                           # #74
    if not ITEM_REF.fullmatch(ref):
        return "section"
    return "action" if "-A-" in ref else "decision" if "-D-" in ref else "milestone" if "-M-" in ref else "use case" if "-U-" in ref else "risk or issue"


def _use_case_words(f, to, name):
    """#164: what an Undo put back on a use case, without quoting its text (a headline or the standing text can be long)."""
    if f == "client_visible":
        return f"{name} is shown to the client again" if to == "1" else f"{name} is hidden from the client again"
    if f == "status":
        return f"the status of {name} is back to {to}" if to in clark_store.ALLOWED[("use_cases", "status")] else f"the status of {name}"
    if f == "commitment":                                           # #709: the word it was, or that it had none
        return f"the commitment of {name} is back to {to}" if to in UC_COMMITMENTS else f"the commitment of {name} is cleared again"
    if f == "owner":                                                # row 875: the name it was, or that it had none
        return f"the owner of {name} is back to {to}" if to else f"the owner of {name} is cleared again"
    return f"the {UC_FIELD_NAMES.get(f, 'details')} of {name}"


def _field_words(entry, name):
    f, to = entry["field"], entry.get("to")
    if GANTT_REF.fullmatch(str(entry.get("ref"))):                  # row 926: the field's name, never the text or the value
        if f == "show":
            return f"{name} is hidden from the client again" if to == "0" else f"{name} is shown to the client again"
        return f"the {GANTT_FIELD_NAMES.get(f, 'details')} of {name} is back as it was"
    if MILESTONE_REF.fullmatch(str(entry.get("ref"))):                  # #136
        if f in MILESTONE_FIELD_NAMES:
            what = MILESTONE_FIELD_NAMES[f]
            back = milestone_rows.shown(to) if f.endswith("_date") else to
            return f"the {what} of {name} is back to {back}" if to else f"the {what} of {name} is cleared again"
        if f in MILESTONE_KEPT_AS_WAS:
            return f"the {MILESTONE_KEPT_AS_WAS[f]} of {name} is back as it was"
    if UC_REF.fullmatch(str(entry.get("ref"))):
        return _use_case_words(f, to, name)
    if f == "latest_update" and ITEM_REF.fullmatch(str(entry.get("ref"))):
        return f"the latest update of {name} is back as it was"      # never the text itself
    if DOC_REF.fullmatch(str(entry.get("ref"))) and f in DOC_FIELD_NAMES:
        return f"the {DOC_FIELD_NAMES[f]} of {name}"                # #74: never the old text or link itself
    if f in ("description", "decision") and ITEM_REF.fullmatch(str(entry.get("ref"))):
        return f"the title of {name} is back as it was"          # #67: never the old text itself
    if f == "client_action" and ITEM_REF.fullmatch(str(entry.get("ref"))):
        return f"the Needed from the client of {name} is back as it was"     # row 811: the switch's own label; no value said
    if f == "client_message" and ITEM_REF.fullmatch(str(entry.get("ref"))):
        return f"the client wording of {name} is back as it was"      # the report rows edit it in place; never the old text itself
    if f in ITEM_FIELD_NAMES and ITEM_REF.fullmatch(str(entry.get("ref"))):
        return f"the {ITEM_FIELD_NAMES[f]} of {name} is back to {to}" if to else f"the {ITEM_FIELD_NAMES[f]} of {name} is cleared again"
    if f == "client_visible":                                       # #67: the picker's Add also showed the row to the client
        return f"{name} is hidden from the client again" if to == "0" else f"{name} is shown to the client again"
    if f == "title":
        return f"the title of {name}"
    if f == "body":
        return f"the content of {name}"                             # never the content itself
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
    if UC_REF.fullmatch(str(ref)):                                  # #164: the usual reason is that the use case was archived since
        return f"{name} couldn't be put back, so it was left as it is. If the use case is archived, restore it first."
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
        if e["field"] == "week_ending":
            if "the week ending date" not in seen:
                seen.add("the week ending date")
                put.append("the week ending date")
            continue
        if e["field"] == "review_after_days":                       # #171: the days before an item counts as not reviewed
            if "the days before an item counts as not reviewed" not in seen:
                seen.add("the days before an item counts as not reviewed")
                put.append("the days before an item counts as not reviewed")
            continue
        if e["field"] == "brand":                                   # #944: the project's brand
            if "the brand" not in seen:
                seen.add("the brand")
                put.append("the brand")
            continue
        if e["field"] in GANTT_PROJECT_FIELDS:                      # row 926: the project's Gantt settings, one line, never the title or the tab's name
            if "the Gantt settings" not in seen:
                seen.add("the Gantt settings")
                put.append("the Gantt settings")
            continue
        if e["field"] == "closed" and ITEM_REF.fullmatch(str(e["ref"])):
            continue                                                # a closing date follows the status: one line says both
        if HIDDEN_REF.fullmatch(str(e["ref"])) and "-L-" in str(e["ref"]) and not e.get("doc"):     # #74: the eye of a document, undone either way
            phrase = (f"{_name(names, e['ref'])} is back on the published page" if e["ref"] in removed
                      else f"{_name(names, e['ref'])} is left out of the published page again")
        elif HIDDEN_REF.fullmatch(str(e["ref"])) and not e.get("doc"):      # #67: the eye, undone either way
            phrase = (f"{_name(names, e['ref'])} is back in the report" if e["ref"] in removed
                      else f"{_name(names, e['ref'])} is hidden from the report again")
        elif e["ref"] in removed:
            phrase = f"the new {_name(names, e['ref'])} was removed" if GANTT_REF.fullmatch(str(e["ref"])) else f"the new {_kind_word(e['ref'])} {_name(names, e['ref'])} was removed"
        elif e["ref"] in restored and "|" in str(e["ref"]) and any(ITEM_REF.fullmatch(str(r)) for r in restored):
            continue                                                # item 658: its links and labels come back with it; "<ID> is back" says it
        elif e["ref"] in restored and ITEM_REF.fullmatch(str(e["ref"])):
            phrase = f"{_name(names, e['ref'])} is back"                # item 658: a deleted work item is back (an item, never a section)
        elif e["ref"] in restored:
            phrase = f"the {_name(names, e['ref'])} is back" if GANTT_REF.fullmatch(str(e["ref"])) else f"the section {_name(names, e['ref'])} is back"
        else:
            phrase = _field_words(e, _name(names, e["ref"]))
        if phrase not in seen:
            seen.add(phrase)
            put.append(phrase)
    if len(put) > 3:
        only_items = all(ITEM_REF.fullmatch(str(e["ref"])) or HIDDEN_REF.fullmatch(str(e["ref"])) for e in reversed_)
        only_tiles = all(TILE_REF.fullmatch(str(e["ref"])) for e in reversed_)
        only_uc = all(UC_REF.fullmatch(str(e["ref"])) for e in reversed_)
        put = [f"{len(put)} changes to the use case" if only_uc
               else f"{len(put)} changes to the work items" if only_items else f"{len(put)} changes to the tiles" if only_tiles
               else f"{len(put)} changes to the sections"]
    lines = [("Undone: " if only_flags else "Put back: ") + "; ".join(put) + "." if put else "Nothing was put back."]
    left = []
    for s in skipped:
        line = _why_words(s, names)
        if line not in left:
            left.append(line)
    return " ".join(lines + left[:3] + ([f"{len(left) - 3} more were left as they are."] if len(left) > 3 else []))


CHANGED_LATER, BACK_ALREADY, GONE = "It was changed later.", "It is back already.", "It is no longer there."
LINKED_NOW = "Something is linked to it now."
SKIP_WORDS = (("something refers to it now", LINKED_NOW), ("other data depends on it", LINKED_NOW), ("has changed since", CHANGED_LATER), ("is back already", BACK_ALREADY), ("no longer exists", GONE))


def _skipped_why(why):
    """The store's reason for leaving a row as it is, as a fixed sentence (no field name, no value)."""
    why = str(why or "")
    if "can't go back to Pending" in why:
        return MADE_CANT_BE_PUT_BACK
    for start, words in SKIP_WORDS:
        if why.startswith(start):
            return words
    return "It couldn't be put back."


def _name_use_cases(store, step_rows, names):
    """Put the name of each use case the step touched into `names`, so the words call it by its name and never its id. #74: and
    the title of each document it touched (by its key, or the hidden row's key that names it), never its id."""
    for r in step_rows:
        if r["table"] == "use_cases" and UC_REF.fullmatch(str(r["key"])):
            found = store.read("use_cases", ref=str(r["key"]))
            if found is not None:
                names[str(r["key"])] = found["title"]
        hidden = HIDDEN_REF.fullmatch(str(r["key"])) if r["table"] == "report_hidden" else None
        doc = str(r["key"]) if r["table"] == "documents" and DOC_REF.fullmatch(str(r["key"])) else None
        if hidden and "-L-" in hidden.group(1):
            doc = str(r["key"]).split("|", 1)[0] + "|" + hidden.group(1)
        found = store.read("documents", ref=doc) if doc else None
        if found is not None:
            names[str(r["key"])] = found["title"]


def _do_undo(store, by_user, req):
    if not isinstance(req, dict):
        raise Refused(NOT_JSON_OBJECT)
    if "steps" in req and "apply_id" not in req:                    # #197: several steps at once
        return _do_undo_many(store, by_user, req)
    for k in req:
        if k not in ("project", "apply_id", "place"):
            raise Refused(f"That change doesn't take '{_shown(k)}'.")
    project = req.get("project")
    if not isinstance(project, str) or not re.fullmatch(clark_store.CODE_RE, project):
        raise Refused(BAD_PROJECT, code="bad_project_code")
    place = req.get("place")                                        # #123: where the Undo was pressed; the step's route is "undo" whatever it is
    if place is not None and (not isinstance(place, str) or place not in PLACES):
        raise Refused(BAD_PLACE)
    step = req.get("apply_id")
    if type(step) is not int or not 1 <= step < 2 ** 63:
        raise Refused(NO_UNDO)                                      # the same words as every other step that isn't ours
    if store.read("projects", ref=project) is None:
        raise Refused(NO_PROJECT, 404, "project_not_found")
    step_rows = store.step_rows(step)
    if not _ours(store, step, step_rows, project) and not _batch_is_ours(store, step, project):   # a missing step, another project's and
        raise Refused(NO_UNDO)                                      # another route's all say the same: nothing tells which exist
    if _hand_over_changed(store, step, step_rows):
        raise Refused(HAND_OVER_CHANGED, 409, "changed_since")      # #199: nothing of it can go back; #620: when some can, the store skips only the changed owner
    names = {r["id"]: r["title"] for r in _sections(store, project)}
    _name_use_cases(store, step_rows, names)                        # #164
    try:                                                            # still inside the caller's one lock
        done = store.undo(step, by_user, place=place)
    except Invalid as e:
        text = str(e)
        if "undone already" in text or "undid an undo" in text:
            raise Refused(UNDONE, 409, "undone") from None
        if text.startswith("clark's data is in use"):
            raise Refused(IN_USE, 503, "busy") from None
        raise Refused(NO_UNDO) from None
    rows = _sections(store, project)
    names.update({r["id"]: r["title"] for r in rows})
    _name_use_cases(store, step_rows, names)
    reversed_ = []
    doc_keys = {r["key"] for r in step_rows if r["table"] == "documents"} - {r["key"] for r in step_rows if r["table"] == "report_hidden"}
    owner_text = {e["ref"] for e in done["reversed"] if e["field"] in HAND_OVER_FIELD.values()}
    for e in done["reversed"]:
        if e["field"] == "owner_id" and e["ref"] in owner_text:
            continue                                                # #199: the link goes back with its owner text; the words count the owner once
        entry = {"ref": e["ref"], "field": e["field"], "change": e["change"], "to": e.get("to")}
        if e["ref"] in doc_keys:
            entry["doc"] = True                                     # #74: a document's own step (its key looks like the eye's, but it is not a hide or a show)
        if e["change"] in ("removed", "put back"):
            if any(x["ref"] == e["ref"] and x["change"] == e["change"] for x in reversed_):
                continue                                            # one line for a whole section, not one for each field
            entry["field"] = None
        reversed_.append(entry)
    owner_skipped = {s["ref"] for s in done["skipped"] if s["field"] in HAND_OVER_FIELD.values()}
    skipped = [{"ref": s["ref"], "field": s["field"], "why": _skipped_why(s["why"]), "by_step": s["by_step"]} for s in done["skipped"]
               if not (s["field"] == "owner_id" and s["ref"] in owner_skipped)]      # #620: a link left with its owner text is one line, not two
    if not reversed_ and any(s["why"] == MADE_CANT_BE_PUT_BACK for s in skipped):       # a decision that is made is not put back
        raise Refused(MADE_CANT_BE_PUT_BACK, 409, "not_undoable")
    out = {"ok": True, "apply_id": done["step_id"],
           "reversed": [{k: e[k] for k in ("ref", "field", "change")} for e in reversed_], "skipped": skipped,
           "words": words(reversed_, skipped, names), "sections": _shown_rows(rows)}
    if any(r["table"] == "glance_tiles" for r in step_rows):
        out["tiles"] = _tiles(store, project)                       # #45: the tiles as they are now
    for r in step_rows:
        if r["table"] == "use_cases" and UC_REF.fullmatch(str(r["key"])) and r.get("field") != "archived":
            out["use_case"] = _use_case_shown(store.read("use_cases", ref=str(r["key"])))
            break
    if any(r["table"] == "report_hidden" for r in step_rows):
        out["hidden"] = _hidden_ids(store, project)                 # #67: what the report hides now
    if any(r["table"] == "gantt_lines" for r in step_rows):
        out["lines"] = [{k: r[k] for k in GANTT_SHOWN} for r in _gantt_lines(store, project)]      # row 926: the lines as they are now
    if any(r["table"] == "projects" for r in step_rows):
        now = store.read("projects", ref=project)
        out["project"] = {"health": now["health"], "health_reason": now["health_reason"], "week_ending": now["week_ending"],
                          "review_after_days": now["review_after_days"], "brand": now["brand"],
                             **{f: now[f] for f in GANTT_PROJECT_FIELDS}}
    return 200, out


# ── Calls the server makes ────────────────────────────────────────────────────

# ── #197: Undo several ────────────────────────────────────────────────────────

CONFIRM_ABOVE = 25                        # more steps than this need `confirm: true` (the page asks a second time first)
MANY_NONE = "Choose at least one change to undo."
MANY_TOO_MANY = f"Choose at most {clark_store.MAX_UNDO_MANY} changes to undo at a time."
MANY_NOT_MINE = "One of those changes isn't in this project. Reload the page and try again."   # a missing step and another project's: the same words
MANY_CONFIRM = "Confirm that you want to undo these {n} changes."
MANY_NOTHING = "None of those changes can be undone."
MANY_BAD_FLAG = "That must be true or false."
IS_AN_UNDO = "This is an undo. Undo it on its own."
UNDONE_ALREADY = "This has been undone already."
NOT_FROM_HERE = "This change can't be undone from here."
ARCHIVED_NOW = "It is archived. Restore it first."
CHANGED_SINCE = "It was changed later, so it is left as it is."


def _of_project(key, project):
    """Whether a change_log key is one of this project's: its code, or an id or a pair that starts with it."""
    key = str(key)
    return key == project or key.startswith(project + "-") or key.startswith(project + "|")


def _batch_is_ours(store, step, project):
    """#197: whether `step` is a batch undo (Store.undo_many) of this project's own steps, so the toast's Undo may undo it."""
    steps = store.batch_undo_steps(step)
    return bool(steps) and all(_ours(store, s, store.step_rows(s), project) for s in steps)


def _many_why(why, by_step):
    """The store's reason for leaving a change as it is, as a fixed sentence for the preview (no value, no field's text)."""
    why = str(why or "")
    if why == NOT_FROM_HERE:
        return why
    if why == "is an undo":
        return IS_AN_UNDO
    if why == "already undone":
        return UNDONE_ALREADY
    if why.endswith("is archived. Restore it first."):
        return ARCHIVED_NOW
    if by_step or why.startswith("has changed since"):
        return CHANGED_SINCE
    return _skipped_why(why)


def _many_field(field):
    """A field as a person reads it in the preview."""
    if field is None:
        return ""
    return (ITEM_FIELD_NAMES.get(field) or MILESTONE_FIELD_NAMES.get(field) or MILESTONE_KEPT_AS_WAS.get(field)
            or UC_FIELD_NAMES.get(field) or str(field).replace("_", " "))


def _many_entries(entries, skipped):
    """The preview's lines, newest step first: one per field changed, one per item made or put back whole (never one per column)."""
    out, seen = [], set()
    texts = {(e["step"], e["ref"]) for e in entries if e["field"] in HAND_OVER_FIELD.values()}
    for e in entries:
        if e["field"] == "owner_id" and (e["step"], e["ref"]) in texts:
            continue                                                # #199: a hand over's link goes with its owner text: one line
        whole = e.get("change") in ("removed", "put back")
        key = (e["step"], e["ref"], e.get("change") if whole else e["field"])
        if key in seen:
            continue
        seen.add(key)
        line = {"step": e["step"], "ref": str(e["ref"]), "field": "" if whole else _many_field(e["field"])}
        if skipped:
            line["why"] = _many_why(e.get("why"), e.get("by_step"))
        else:
            line["change"] = e.get("change") or "set"
        out.append(line)
    return out


def _many_flag(req, key):
    value = req.get(key, False)
    if type(value) is not bool:
        raise Refused(MANY_BAD_FLAG)
    return value


def _do_undo_many(store, by_user, req):
    """#197: POST /api/undo with `steps` (the steps of the history rows chosen), `preview` and `confirm`. A preview is the same
    run rolled back: it lists each change that will be undone and each that will be left, with its reason. Without `preview` one
    new step undoes them all (newest first), and its Undo puts them all back. A step not of this project refuses the whole request;
    a step of this project that can't be undone from here is left out and named. The data can change between the preview and the
    run, so the run's reply is complete on its own: what was undone and what was left, with the reasons, as the preview gives them;
    the page shows that reply, not the preview it showed before."""
    for k in req:
        if k not in ("project", "steps", "preview", "confirm"):
            raise Refused(f"That change doesn't take '{_shown(k)}'.")
    project = req.get("project")
    if not isinstance(project, str) or not re.fullmatch(clark_store.CODE_RE, project):
        raise Refused(BAD_PROJECT, code="bad_project_code")
    preview, confirm = _many_flag(req, "preview"), _many_flag(req, "confirm")
    steps = req.get("steps")
    if not isinstance(steps, list) or not steps:
        raise Refused(MANY_NONE)
    if len(steps) > clark_store.MAX_UNDO_MANY * 2:                  # refused before any is looked at, duplicates or not
        raise Refused(MANY_TOO_MANY)
    if any(type(s) is not int or not 1 <= s < 2 ** 63 for s in steps):
        raise Refused(MANY_NOT_MINE)
    steps = sorted(set(steps), reverse=True)
    if len(steps) > clark_store.MAX_UNDO_MANY:
        raise Refused(MANY_TOO_MANY)
    if store.read("projects", ref=project) is None:
        raise Refused(NO_PROJECT, 404, "project_not_found")
    if len(steps) > CONFIRM_ABOVE and not preview and not confirm:
        raise Refused(MANY_CONFIRM.format(n=len(steps)), 409, "confirm")
    left, ours = [], []
    for s in steps:
        rows = store.step_rows(s)
        if not rows or not any(_of_project(r["key"], project) for r in rows):
            raise Refused(MANY_NOT_MINE)                            # nothing tells a missing step from another project's
        if all(str(r["via"]).startswith(clark_store.REVERT_VIA) for r in rows):
            why = "is an undo"
        elif not _ours(store, s, rows, project):
            why = NOT_FROM_HERE
        elif _hand_over_changed(store, s, rows, all_gone=False):
            why = "has changed since: left as it is"                # #199: a link-only item whose name changed leaves the step whole; #620: other changed owners are skipped one by one
        else:
            ours.append(s)
            continue
        mine = [r for r in rows if _of_project(r["key"], project) and r["field"] not in UNDO_ALSO]
        left += [{"step": s, "ref": r["key"], "field": None, "why": why, "by_step": None} for r in mine[:1]]
        # one line for the step, left whole: named by a row of THIS project (never another's), with no field
    done = {"step_id": None, "reversed": [], "skipped": []}
    if ours:
        try:
            done = store.undo_many(ours, by_user, dry=preview)
        except Invalid as e:
            if str(e).startswith("clark's data is in use"):
                raise Refused(IN_USE, 503, "busy") from None
            if str(e).startswith("There's no step"):              # gone since it was checked: the same words as a missing one
                raise Refused(MANY_NOT_MINE) from None
            raise                                                   # a safety copy that can't be made, in the store's plain words
    undo = _many_entries(done["reversed"], False)
    skipped = _many_entries(sorted(left + done["skipped"], key=lambda e: -e["step"]), True)
    out = {"ok": True, "preview": preview, "apply_id": done["step_id"], "count": len(steps),
           "needs_confirm": len(steps) > CONFIRM_ABOVE, "undo": undo, "skipped": skipped}
    if preview:
        out["words"] = (f"{len(undo)} change{'' if len(undo) == 1 else 's'} will be undone."
                        + (f" {len(skipped)} will be left as {'it is' if len(skipped) == 1 else 'they are'}." if skipped else ""))
        return 200, out
    if done["step_id"] is None:
        raise Refused(MANY_NOTHING, 409, "not_undoable")
    out["words"] = (f"Undone: {len(undo)} change{'' if len(undo) == 1 else 's'}."
                    + (f" {len(skipped)} left as {'it is' if len(skipped) == 1 else 'they are'}." if skipped else ""))
    out["sections"] = _shown_rows(_sections(store, project))
    return 200, out


def undo_refusals(store, project, steps):
    """The steps among `steps` that Undo several would leave out whole, each with its plain reason: {step: words}. It asks the same
    questions _do_undo_many asks, in the same order (an undo, a step that is not ours, a step undone already), so the Activity tab can
    withhold the tick before it is chosen. A step that can be chosen is not in the answer. Read only."""
    out = {}
    reverted = None                                        # #377: the reverted set is read once per call, not once per step
    for s in set(steps):
        rows = store.step_rows(s)
        if not rows:
            continue
        if all(str(r["via"]).startswith(clark_store.REVERT_VIA) for r in rows):
            out[s] = IS_AN_UNDO
        elif not _ours(store, s, rows, project):
            out[s] = NOT_FROM_HERE
        elif _hand_over_changed(store, s, rows):
            out[s] = CHANGED_SINCE
        else:
            if reverted is None:
                reverted = clark_store.reverted_rowids(store.con)
            if store.step_undone(s, reverted):
                out[s] = UNDONE_ALREADY
    return out


def _call(path, onedrive_roots, by_user, work, req):
    """Run `work(store, by_user, req)` on a store of its own, under the one lock; (status, body). A refusal and the
    store's own rule messages are 400 in plain words; a missing database, a busy one and an unusable folder are 503; any
    other fault is raised, and the server answers it with its own 500 (no class, no text)."""
    try:
        with LOCK:
            if not Path(path).is_file():
                if backup.restoring(path):                          # clark.db is moved aside for a moment: say so, not "can't be found"
                    raise Refused(backup.RESTORE_BUSY, 503, "no_data")
                raise Refused(NO_DATA, 503, "no_data")              # open_store would make an empty one: never from here
            try:
                store = clark_store.open_store(path, onedrive_roots=onedrive_roots)
            except platform.PlatformError as e:
                raise Refused(str(e), 503, "no_data") from None
            except Invalid as e:
                raise Refused(IN_USE if str(e).startswith("clark's data is in use") else
                              CANT_SAVE if str(e).startswith(NOT_OPENED) else
                              str(e) if str(e).startswith(clark_store.MIGRATE_REFUSAL_STARTS) or str(e) == backup.RESTORE_BUSY else CANT_OPEN, 503, "no_data") from None
            try:
                who = by_user() if callable(by_user) else (by_user or platform.login_name())
                return work(store, who, req)
            finally:
                store.close()
    except Refused as r:
        return r.status, {**r.extra, "ok": False, "message": r.message, "code": r.code}
    except Invalid as e:                                            # a store rule, in its plain words
        if str(e).startswith("clark's data is in use"):
            return 503, {"ok": False, "message": IN_USE, "code": "busy"}
        if str(e).startswith(NOT_OPENED):                           # a folder or file that can't be written to
            return 503, {"ok": False, "message": CANT_SAVE, "code": "no_data"}
        return 400, {"ok": False, "message": ITEM_VALUE_WORDS if STORE_LEAK.search(str(e)) else str(e), "code": "refused"}


def make_change(path, onedrive_roots=None, by_user=None):
    """The `change` the server calls for POST /api/change, for the database at `path`. `by_user` is a name or a function
    that gives one (the server passes the profile name, falling back to the login name, platform.login_name, which is also the default here)."""
    def change(req):
        return _call(path, onedrive_roots, by_user, _do_change, req)
    return change


def _section_body_shape(req):
    """Refused unless `req` is the one request POST /api/section-body takes (#273): report_sections, update, `changes` holding a body
    and nothing else. The words are the change path's own for the same fault; everything after this is the change path itself."""
    if not isinstance(req, dict):
        raise Refused(NOT_JSON_OBJECT)
    if req.get("kind") != "report_sections":
        raise Refused(BAD_KIND)
    if req.get("op") != UPDATE:
        raise Refused(BAD_OP)
    changes = req.get("changes")
    if not isinstance(changes, dict) or "body" not in changes:
        raise Refused(NOT_JSON_OBJECT)
    for k in changes:
        if k != "body":
            raise Refused(f"That change doesn't take '{_shown(k)}'.")


def make_section_body(path, onedrive_roots=None, by_user=None):
    """The `section_body` the server calls for POST /api/section-body (#273), for the database at `path` (see make_change): a
    section's content only, saved by the same code as a change, so the checks, the step, the Undo and the history are the same."""
    def section_body(req):
        try:
            _section_body_shape(req)
        except Refused as r:
            return r.status, {**r.extra, "ok": False, "message": r.message, "code": r.code}
        return _call(path, onedrive_roots, by_user, _do_change, req)
    return section_body


def make_section_image(path, onedrive_roots=None, by_user=None):
    """The `section_image` the server calls for POST /api/section-image (#96 R1), for the database at `path` (see make_change)."""
    def section_image(req):
        return _call(path, onedrive_roots, by_user, _do_section_image, req)
    return section_image


# ── A file for a section template (#96, POST /api/section-file) ────────────────

FILE_TYPES = tuple(t for t, m in section_bodies.TEMPLATES.items() if callable(getattr(m, "add_file", None)))   # the templates that hold a file
NO_FILE_HERE = "That section can't hold a file. Add a Documents and links or One document section, then add the file there."


def _do_section_file(store, by_user, req):
    """Add a file that is already in the client folder to a section, as one step with one Undo (place "report"). `req` is made by
    clark itself (section_files.py, after it copied the file), never by the page: {project, id, entry: {name, rel, bytes}}. The
    stored body is read inside the step and the section's own template says where the file goes (its add_file); the result meets
    the type's checker like any other body write, so the store's rules are the same as a save from the page."""
    project, ref, entry = req.get("project"), req.get("id"), req.get("entry")
    if not isinstance(project, str) or store.read("projects", ref=project) is None:
        raise Refused(NO_PROJECT, 404, "project_not_found")
    if clark_store.is_archived(store.con, project):
        raise Refused(PROJECT_NOT_ACTIVE)
    with store.step(VIA, by_user, place="report") as st:
        rows = _sections(store, project)
        _mine(ref, [r["id"] for r in rows], NOT_MINE)
        row = next(r for r in rows if r["id"] == ref)
        kind = next((t for t in FILE_TYPES if t == row["type"]), None)
        if kind is None:
            raise Refused(NO_FILE_HERE)
        text = _section_body(row, row.get("body") or "")
        try:
            value = section_bodies.TEMPLATES[kind].add_file(json.loads(text) if text else None, entry)
        except section_bodies.Bad as e:
            raise Refused(str(e)) from None
        st.update("report_sections", ref, {"body": _section_body(row, section_bodies.canonical(value))})
        apply_id = st.peek_apply_id()
    return 200, {"ok": True, "apply_id": apply_id, "ref": ref, "sections": _shown_rows(_sections(store, project))}


def make_section_file(path, onedrive_roots=None, by_user=None):
    """The step that adds a copied file to a section (see _do_section_file), for the database at `path`. Called by section_files.py
    only; it is not a route of its own."""
    def section_file(req):
        return _call(path, onedrive_roots, by_user, _do_section_file, req)
    return section_file


def make_undo(path, onedrive_roots=None, by_user=None):
    """The `undo` the server calls for POST /api/undo, for the database at `path` (see make_change)."""
    def undo(req):
        return _call(path, onedrive_roots, by_user, _do_undo, req)
    return undo


# ── The people list (#115) ────────────────────────────────────────────────────
# Portfolio level: no project in the request. One route for the six person writers, one for their Undo, one read. A person's
# fields are checked by the store (people rules); this checks only the shape of the request, then one step, one Undo.
PERSON_FIELDS = ("name", "email", "organisation", "role", "label", "aliases", "kind", "needs_details")
PEOPLE_SHAPES = {"add": PERSON_FIELDS, "edit": ("id", "changes"), "rename": ("id", "name"), "merge": ("from", "into"),
                 "archive": ("id",), "restore": ("id",), "paste": ("rows",)}
PEOPLE_SOURCE = "People list"
BAD_PERSON = "That isn't a person clark knows. Reload the page and try again."
NO_PEOPLE_UNDO = "That step can't be undone from here."
PERSON_ID = re.compile(r"P-\d{3}")


def _person_value(key, value, capped=True):
    if key == "needs_details":
        return value if isinstance(value, bool) or value in (0, 1) and type(value) is int else _refuse_person()
    if value is None:
        return value
    if not isinstance(value, str) or len(value) > 2000:
        _refuse_person()
    if capped and key in ("organisation", "role") and len(" ".join(value.split())) > people_rules.CELL_MAX:
        raise Refused(f"the {key} is too long (at most {people_rules.CELL_MAX} characters). Shorten it and try again. Nothing was changed.")
    return value


def _refuse_person():
    raise Refused("One of the person's details isn't text clark can use. Check it and try again.")


def _person_ref(value):
    if not isinstance(value, str) or not PERSON_ID.fullmatch(value):
        raise Refused(BAD_PERSON, 400, "bad_person")
    return value


PASTE_FIELDS = ("name", "email", "organisation", "role")     # #454: the four columns the People card's Paste from Excel takes
PASTE_NONE = "There is nothing to add. Paste rows copied from Excel: name, email, organisation, role."
PASTE_MANY = f"That is more than {people_rules.ROW_LIMIT} rows. Paste fewer rows at a time. Nothing was changed."
PASTE_BAD_ROW = "One of the rows isn't details clark can use. Check the rows and try again. Nothing was changed."


def _paste_people(st, rows):
    """#454: rows of name, email, organisation and role (the People card's Paste from Excel), applied in the caller's ONE step, so one
    Undo takes the whole paste back. A name already on the live list (the people rules' exact match on a name or alias, never fuzzy)
    gets the details that were pasted: a blank cell leaves what is there alone. Any other name is added, Needs details when it has no
    email. Every field goes through the same writer and checks as an add or an edit (the email rule, one email per person, the
    limits). One row that can't be used refuses the whole paste, in words that name the person, and nothing is written. Returns
    (added, updated)."""
    if not isinstance(rows, list) or not rows:
        raise Refused(PASTE_NONE)
    if len(rows) > people_rules.ROW_LIMIT:
        raise Refused(PASTE_MANY)
    added = updated = 0
    by_id, live, gone = {}, {}, {}                                  # the name and alias index, built ONCE: key -> ids (live, archived)
    for p in st.store.people(archived=None):
        by_id[p["id"]] = p
        for key in people_rules.keys_of(p):
            (gone if p.get("archived") else live).setdefault(key, []).append(p["id"])
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("name"), str) or any(k not in PASTE_FIELDS for k in row):
            raise Refused(PASTE_BAD_ROW)
        given = {k: _person_value(k, v, capped=False) for k, v in row.items()}      # the paste says the cap with the person's name, just below
        name = " ".join(given["name"].split())
        if not name:
            raise Refused("A row has no name. Give each person a name. Nothing was changed.")
        shown = name if len(name) <= 40 else name[:40] + "…"
        try:
            key = people_rules.name_key(name)
            if key in people_rules.NO_PERSON:                        # the placeholder rule the owner fields use: TBC is no one
                raise Refused(f"{shown} isn't a name. Give the person's real name, or leave the row out. Nothing was changed.")
            ids = live.get(key, [])                                  # exactly people.resolve's order: live first, then archived
            if len(ids) > 1:
                raise Refused(f"More than one person is called {shown}. Change the name to say which one, then paste again. Nothing was changed.")
            if not ids and key in gone:
                raise Refused(f"{shown} is on the list but has been archived. Restore them from the People card instead of pasting them again. Nothing was changed.")
            email, bad = people_rules.clean_email(given.get("email"))
            if bad:
                raise Refused(f"{shown}: {bad} Nothing was changed.")
            details = {"email": email or None, "organisation": " ".join((given.get("organisation") or "").split()) or None,
                       "role": " ".join((given.get("role") or "").split()) or None}
            for field in ("organisation", "role"):
                if details[field] and len(details[field]) > people_rules.CELL_MAX:
                    raise Refused(f"{shown}: the {field} is too long (at most {people_rules.CELL_MAX} characters). Shorten it and try again. Nothing was changed.")
            if ids:
                now = by_id[ids[0]]
                changes = {k: v for k, v in details.items() if v and v != now.get(k)}
                if changes:
                    st.edit_person(ids[0], changes)
                    now.update(changes)
                    updated += 1
            else:
                new = st.add_person(source=PEOPLE_SOURCE, name=name, needs_details=0 if email else 1, **{k: v for k, v in details.items() if v})
                person = {"id": new, "name": name, "aliases": None, "archived": 0, **details}
                by_id[new] = person
                for k in people_rules.keys_of(person):
                    live.setdefault(k, []).append(new)
                added += 1
        except Invalid as e:                                    # a store rule (one email per person ...), said with the person's name
            raise Refused(f"{shown} couldn't be saved. Check the row and try again. Nothing was changed.") from None
    return added, updated


def _do_people(store, by_user, req):
    """POST /api/people: {"op": add | edit | rename | merge | archive | restore | paste, ...}. One step; answers the new apply_id (the
    Undo's handle; None when a paste changed nothing), the person's id where there is one, how many work items a rename or merge
    carried, how many people a paste added and updated, and the list as it now is."""
    if not isinstance(req, dict):
        raise Refused(NOT_JSON_OBJECT)
    op = req.get("op")
    if not isinstance(op, str) or op not in PEOPLE_SHAPES:
        raise Refused(BAD_OP)
    allowed = ("op",) + PEOPLE_SHAPES[op]
    for k in req:
        if k not in allowed:
            raise Refused(f"That change doesn't take '{_shown(k)}'.")
    ref, count, pasted = None, 0, {}
    with store.step("dashboard", by_user) as st:
        if op == "paste":
            added, updated = _paste_people(st, req.get("rows"))
            pasted = {"added": added, "updated": updated}
        elif op == "add":
            fields = {k: _person_value(k, v) for k, v in req.items() if k != "op"}
            ref = st.add_person(source=PEOPLE_SOURCE, **fields)
        elif op == "edit":
            ref = _person_ref(req.get("id"))
            ch = req.get("changes")
            if not isinstance(ch, dict) or not ch or any(k not in PERSON_FIELDS for k in ch):
                raise Refused(BAD_PERSON, 400, "bad_person")
            st.edit_person(ref, {k: _person_value(k, v) for k, v in ch.items()})
        elif op == "rename":
            ref = _person_ref(req.get("id"))
            count = st.rename_person(ref, _person_value("name", req.get("name")))
        elif op == "merge":
            ref = _person_ref(req.get("into"))
            count = st.merge_people(_person_ref(req.get("from")), ref)
        elif op == "archive":
            ref = _person_ref(req.get("id"))
            st.archive_person(ref)
        else:
            ref = _person_ref(req.get("id"))
            st.restore_person(ref)
        apply_id = st.peek_apply_id()
    return 200, {"ok": True, "apply_id": apply_id, "id": ref, "items": count, **pasted, "people": store.people(archived=None)}


def _do_people_undo(store, by_user, req):
    """POST /api/people/undo: {"apply_id": n}. Only a step that changed the people list; a work item's own step is the board's Undo."""
    if not isinstance(req, dict) or set(req) != {"apply_id"}:
        raise Refused(NO_PEOPLE_UNDO)
    step = req["apply_id"]
    if type(step) is not int or not 1 <= step < 2 ** 63:
        raise Refused(NO_PEOPLE_UNDO)
    rows = store.step_rows(step)
    if not rows or not any(r["table"] == "people" for r in rows) or any(r["via"] != "dashboard" for r in rows):
        raise Refused(NO_PEOPLE_UNDO)
    try:
        plan = store.undo_many([step], by_user, dry=True)       # the very same run, always rolled back: nothing is written yet
        if any(x["why"] in ("already undone", "is an undo") for x in plan["skipped"]):
            raise Refused(UNDONE, 409, "undone")
        if plan["skipped"]:                                    # all or nothing: one row that can't go back refuses the whole undo
            raise Refused(_people_undo_reason(store, rows, plan["skipped"]))
        done = store.undo(step, by_user)
        if done["skipped"]:                                    # not reachable under the lock; never leave a half-undo if it were
            raise Refused(_people_undo_reason(store, rows, done["skipped"]))
    except Invalid as e:
        text = str(e)
        if "undone already" in text or "undid an undo" in text:
            raise Refused(UNDONE, 409, "undone") from None
        if text.startswith("clark's data is in use"):
            raise Refused(IN_USE, 503, "busy") from None
        raise Refused(NO_PEOPLE_UNDO) from None
    restored = _people_undo_counts(rows)
    return 200, {"ok": True, "people": store.people(archived=None), "restored": restored, "message": _people_undo_words(restored)}


def _people_undo_reason(store, rows, skipped):
    """Plain words for an Undo that would leave something behind: what to do first. Names the person who now holds an email the
    step freed, when that is the cause; otherwise says how many changes can't go back."""
    other = store.live_holder_of_freed_email([r["key"] for r in rows if r["table"] == "people" and r["field"] == "email"])
    if other:
        return (f"This can't be undone: an email address it would put back is now used by {other}. "
                f"Change or archive {other} first, then undo again. Nothing has been changed.")
    n = len(skipped)
    return (f"This can't be undone: {n} change{'s' if n != 1 else ''} can no longer be put back, because the data has changed since. "
            "Undo the later change first, then undo again. Nothing has been changed.")


def _people_undo_counts(rows):
    people = {r["key"] for r in rows if r["table"] == "people"}
    emails = {r["key"] for r in rows if r["table"] == "people" and r["field"] == "email"}
    items = {(r["table"], r["key"]) for r in rows if r["table"] != "people"}
    return {"people": len(people), "emails": len(emails), "items": len(items)}


def _people_undo_words(c):
    p = f"{c['people']} {'person' if c['people'] == 1 else 'people'}"
    e = f", {c['emails']} email address{'' if c['emails'] == 1 else 'es'}" if c["emails"] else ""
    i = f" and {c['items']} item{'' if c['items'] == 1 else 's'}" if c["items"] else ""
    return f"Undone: put back {p}{e}{i}."


def _do_people_list(store, by_user, req):
    return 200, {"ok": True, "people": store.people(archived=None)}


def make_people(path, onedrive_roots=None, by_user=None):
    """The `people` seam for POST /api/people, for the database at `path` (see make_change)."""
    def people(req):
        return _call(path, onedrive_roots, by_user, _do_people, req)
    return people


def make_people_undo(path, onedrive_roots=None, by_user=None):
    """The `people_undo` seam for POST /api/people/undo."""
    def people_undo(req):
        return _call(path, onedrive_roots, by_user, _do_people_undo, req)
    return people_undo


def make_people_list(path, onedrive_roots=None, by_user=None):
    """The `people_list` seam for GET /api/people: everyone on the list, archived too, as the store has them."""
    def people_list():
        return _call(path, onedrive_roots, by_user, _do_people_list, {})
    return people_list


# ── Archive and Restore of one publication (#345, POST /api/publications/archive and /restore) ──
# The server has checked the body is exactly a project code and a publication number. The store writes the one history line and the
# archive mark (store.archive_publication, unarchive_publication); the reply carries no step, so the page offers no Undo. A publication
# already in the state asked for is the 409; any other refusal is the store's own plain words as a 400.
def _do_publication_mark(store, by_user, req, on):
    code, number = req["project"], req["number"]
    try:
        (store.archive_publication if on else store.unarchive_publication)(code, number, by_user)
    except Invalid as e:
        if "already archived" in str(e) or "is not archived" in str(e):
            raise Refused(str(e), 409, "already") from None
        raise
    return 200, {"ok": True, "code": "archived" if on else "restored", "project": code, "number": number}


def make_publication_mark(path, onedrive_roots=None, by_user=None):
    """The `publication_mark(action, req)` seam for POST /api/publications/archive and /restore, for the database at `path`."""
    def publication_mark(action, req):
        return _call(path, onedrive_roots, by_user, lambda store, who, r: _do_publication_mark(store, who, r, action == "archive"), req)
    return publication_mark


# ── ask clark's changes (#47e part 1) ─────────────────────────────────────────
# ask clark's own modules never open the database for writing (tests/test_ask_route.py). A change they have checked comes here, to
# make_ask_change, and goes through the SAME path as a hand edit (_do_change: the allow-list, the plain-text rule, the store's own
# rules), with these differences, all made here and nowhere else:
# - only a new or changed work item or milestone (ASK_KINDS, ASK_OPS): no archive, restore, delete, place or rebaseline;
# - every step is written with route "assistant" and actor "clark", and no place;
# - the switch is read again INSIDE the step, after BEGIN IMMEDIATE (store.ask_enabled: off when it can't say), so off writes nothing;
# - the row before and after are read from the data inside that step, never from the request;
# - `dry=True` (the default) runs it all in a step that is always rolled back (Store.step(dry=True)): what would be saved, saving nothing;
# - an Apply may carry `expect`, the `before` its dry run showed: if the row is not that now, nothing is written.
ASK_KINDS = ("actions", "raid", "decisions", "milestones", "use_cases")
ASK_OPS = (NEW, UPDATE)
# The fields ask clark may give, per kind and op: narrower than CHANGE_KINDS (no use case link, no client wording, no state, no
# Movement, no agreed date moved: that is a rebaseline). Checked here, the one guarded chokepoint; ask_apply reads it from here.
# A RAID item's `type` is set from the suggestion's kind (risk, issue and so on), never named by it.
ASK_FIELDS = {
    "actions": {NEW: ("description", "owner", "priority", "due_date", "workstream", "milestone"),
                UPDATE: ("description", "owner", "priority", "due_date", "status", "workstream", "milestone")},
    "raid": {NEW: ("type", "description", "owner", "impact", "likelihood", "due_date", "workstream", "milestone"),
             UPDATE: ("description", "owner", "due_date", "status", "workstream", "milestone")},
    "decisions": {NEW: ("decision", "made_by", "status", "date", "needed_by"),
                  UPDATE: ("decision", "made_by", "status", "date", "needed_by")},
    "milestones": {NEW: ("name", "owner", "baseline_date", "workstream"),
                   UPDATE: ("forecast_date", "actual_date", "status")},
    "use_cases": {NEW: (),                                                 # issue 729: a change only (no new use case, no name, no eye, no link); the same checks as the editor
                  UPDATE: ("headline", "status", "standing")},
}
ASK_KEYS = {NEW: ("project", "kind", "op", "values"), UPDATE: ("project", "kind", "op", "id", "changes")}
ASK_PART = {NEW: "values", UPDATE: "changes"}
ASK_OFF = "Asking is off, so nothing was changed. Turn it on in Settings first."
ASK_NOT_YET = "That change can't be made by asking yet. Nothing was changed. Make it yourself on the board."
ASK_CHANGED = "That item has changed since the change was shown. Nothing was changed. Look at the change again."
ASK_SHOWN = {t: ("id",) + tuple(f for f in dict.fromkeys(CHANGE_KINDS[t][NEW] + CHANGE_KINDS[t][UPDATE] + ("type", "status", "closed", "priority", "raised"))
                                if f not in clark_store.NEVER_PUBLISH and f not in EXPLAIN_FIELDS and not (t == "use_cases" and f in ("owner", "owner_id")))
             for t in ASK_KINDS}               # what a before or after says of a row (a field the table lacks is left out); #458: never an owner-only column (the internal note, the Movement choice); row 875: nor a use case's owner (internal, as no report carries it)


class _Dry(Exception):
    """Ends a dry run's step, which the store then rolls back."""


class _AskStore:
    """The store as _do_change sees it for ask clark: every read is the store's own; a step is ask clark's (see above)."""

    def __init__(self, store, dry, expect, table, ref):
        self._store, self.dry, self.expect, self.table, self.ref = store, dry, expect, table, ref
        self.before = self.after = None

    def __getattr__(self, name):
        return getattr(self._store, name)

    def shown(self, ref):
        row = self._store.read(self.table, ref=ref) if isinstance(ref, str) else None
        return None if row is None else {k: row[k] for k in ASK_SHOWN[self.table] if k in row}

    @contextmanager
    def step(self, via, by_user, place=None, src_ref=None):
        if via != VIA:
            raise Invalid("not a step of a change")
        with self._store.step(ASSISTANT, by_user, actor=ASK_ACTOR, dry=self.dry) as st:      # BEGIN IMMEDIATE
            if self._store.ask_enabled() is not True:
                raise Refused(ASK_OFF, 409, "asking_off")
            self.before = self.shown(self.ref) if self.ref is not None else None
            if self.expect is not None and self.before != self.expect:
                raise Refused(ASK_CHANGED, 409, "changed")
            yield st
            made = self.ref
            if made is None and st.peek_apply_id() is not None:
                made = next((r["key"] for r in self._store.step_rows(st.peek_apply_id())
                             if r["table"] == self.table and r["op"] == MADE_OP), None)
            self.ref, self.after = made, self.shown(made)
            if self.dry:
                raise _Dry()


def _do_ask(store, by_user, req, dry, expect):
    project, kind, op, place = _shape(req)
    if kind not in ASK_KINDS or op not in ASK_OPS or any(k not in ASK_KEYS[op] for k in req):
        raise Refused(ASK_NOT_YET, code="not_yet")
    part = req.get(ASK_PART[op])
    if not ASK_FIELDS[kind][op] or not isinstance(part, dict) or any(f not in ASK_FIELDS[kind][op] for f in part):
        raise Refused(ASK_NOT_YET, code="not_yet")
    if store.ask_enabled() is not True:
        raise Refused(ASK_OFF, 409, "asking_off")
    ref = req.get("id") if op == UPDATE else None
    if op == UPDATE and not _belongs(kind, ref, project):
        raise Refused(NO_MILESTONE if kind == "milestones" else NO_USE_CASE if kind == "use_cases" else ITEM_NOT_MINE)
    if expect is not None and not isinstance(expect, dict):
        raise Refused(STALE)
    ask = _AskStore(store, dry, expect, kind, ref)
    try:
        _status, body = _do_change(ask, by_user, req)
    except _Dry:
        return 200, {"ok": True, "dry": True, "kind": kind, "ref": ask.ref, "before": ask.before, "after": ask.after}
    apply_id = body.get("apply_id")
    return 200, {"ok": True, "dry": False, "kind": kind, "ref": ask.ref, "apply_id": apply_id,
                 "undoable": bool(body.get("undoable", apply_id is not None)), "before": ask.before, "after": ask.after}


def make_ask_change(path, onedrive_roots=None, by_user=None):
    """The one way ask clark saves (#47e): `ask_change(req, dry=True, expect=None)` takes a request in /api/change's form, for a
    work item or milestone only. A dry run (the default) says {ok, dry, kind, ref, before, after} and saves nothing; `dry=False`
    saves it as one step (route "assistant", actor "clark") and adds apply_id and undoable, for /api/undo."""
    def ask_change(req, dry=True, expect=None):
        return _call(path, onedrive_roots, by_user, lambda store, who, r: _do_ask(store, who, r, dry is not False, expect), req)
    return ask_change
