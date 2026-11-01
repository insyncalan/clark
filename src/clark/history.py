"""One row's history, newest first, with undo links (#31). Cut down from creaite's item_history.py at v2.6.9 (db5adb2): only
change_log joined to item_events; no proposals, chases or mentions. Reads only."""
import difflib
import json
import re
import threading
from datetime import datetime, timedelta, timezone

from clark import freshness as fresh, timefmt
from clark.publish import RICH
from clark.sanitise import SanitiseError, plain_text
from clark.store import BATCH_UNDO, FLAG_COLUMNS, OP_MADE, REMOVED, REVERT_VIA, SEED_VIA, reverted_rowids

JOINED = ("links", "item_labels")      # rows keyed by an item's ID with another: "from|to|kind", "item|label"


def touches(r, item_id):
    """True when a change_log row is about the item: its own row, or a link or label row with the item at one end."""
    if r["tbl"] not in JOINED:
        return True
    parts = str(r["item_id"]).split("|")
    return item_id in (parts[:2] if r["tbl"] == "links" else parts[:1])


ROW_SQL = ("SELECT c.rowid AS rowid, c.tbl, c.item_id, c.field, c.old_value, c.new_value, c.op, c.via, c.apply_id, "
           "a.by_user, a.undone_at, e.event_id, e.at, e.route, e.place, e.origin, e.actor, e.src_ref, e.undoes "
           "FROM change_log c JOIN item_events e ON e.change = c.rowid LEFT JOIN applies a ON a.apply_id = c.apply_id "
           "WHERE c.field != 'updated_at'")


def keyed_by(key, item_id):
    """True when a change_log key names the item the way the history query asks: the key is the ID, starts with 'ID|' or has
    '|ID|' inside it (the same three tests as the query's SQL)."""
    return key == item_id or key.startswith(item_id + "|") or ("|" + item_id + "|") in key


def build_events(rows, reverted):
    """The events for one item from its change_log rows (already in event order, already limited to the ones about it). The
    one place an event is built, for one item or many."""
    # a row's columns are unpacked once, in ROW_SQL's order: reading them by name 21 times a row is slow over a long log
    undone_by = {row[18]: row[11] for row in rows if row[18] is not None}
    events = []
    for (rowid, tbl, item_id, field, old_value, new_value, op, via, apply_id, by_user, undone_at, event_id, at, route, place,
         origin, actor, src_ref, undoes) in rows:
        events.append({
            "event_id": event_id, "at": at, "step": apply_id, "by_user": by_user, "table": tbl,
            "ref": item_id, "field": field, "before": old_value, "after": new_value, "op": op,
            "route": route, "place": place, "origin": origin, "actor": actor, "src_ref": src_ref,
            "undoes": undoes,
            "is_undo": str(via).startswith(REVERT_VIA), "undone_by": undone_by.get(event_id),
            "in_force": not undone_at and rowid not in reverted,
        })
    events.reverse()
    return events


def history(con, item_id):
    """[event, ...] for `item_id`, newest first. Each event: event_id, at, step, by_user, table, field, before, after, op,
    route, place, origin, actor, src_ref (how it came in, such as "by Word import (plan.docx)", else None), undoes (the event it
    reverses), undone_by (the event that reversed it) and in_force (False once an undo still in force has reversed it, or its own
    step was undone)."""
    rows = con.execute(ROW_SQL + " AND (c.item_id = ? OR c.item_id LIKE ? OR c.item_id LIKE ?) ORDER BY e.event_id",
                       (item_id, item_id + "|%", "%|" + item_id + "|%")).fetchall()
    rows = [r for r in rows if touches(r, item_id)]
    return build_events(rows, reverted_rowids(con))


BARE_CHUNK = 100                       # IDs with no hyphen per query: 300 parameters and OR terms, well under SQLite's limits


def history_many(con, ids):
    """{id: history(con, id)} for every ID in `ids`, read in ONE pass: the undone steps are found once and the log is read once
    (the single-item query's leading wildcard cannot use the index, so asking per item scans the whole log each time). Each
    item's events come from the same build_events code, so the answers are the same as history()'s."""
    ids = list(dict.fromkeys(ids))
    if not ids:
        return {}
    wanted = set(ids)
    codes = sorted({i.split("-", 1)[0] for i in ids if "-" in i})
    bare = [i for i in ids if "-" not in i]               # an ID with no hyphen has no code to cut: ask for it as history() does
    mine = {i: [] for i in ids}
    # SQLite caps an expression's depth (1000) and its parameters: each bare ID adds three OR terms, so they go in chunks, the
    # codes with the first. A row two chunks both match is read once; the rows are put back in event order.
    chunks = [bare[n:n + BARE_CHUNK] for n in range(0, len(bare), BARE_CHUNK)] or [[]]
    seen, rows = set(), []
    for n, chunk in enumerate(chunks):
        use = codes if n == 0 else []
        where = " AND (" + " OR ".join(["c.item_id LIKE ? OR c.item_id LIKE ?"] * len(use)
                                       + ["c.item_id = ? OR c.item_id LIKE ? OR c.item_id LIKE ?"] * len(chunk)) + ")"
        args = [x for c in use for x in (c + "-%", "%|" + c + "-%")] + [x for i in chunk for x in (i, i + "|%", "%|" + i + "|%")]
        for r in con.execute(ROW_SQL + where + " ORDER BY e.event_id", args):
            if len(chunks) == 1 or r["rowid"] not in seen:
                seen.add(r["rowid"])
                rows.append(r)
    if len(chunks) > 1:
        rows.sort(key=lambda r: r["event_id"])
    for r in rows:
        key = str(r["item_id"])
        if "|" not in key:                                  # the usual row: keyed by its own item alone
            if key in wanted:
                mine[key].append(r)
            continue
        parts = key.split("|")
        for cand in {key, parts[0], *parts[1:-1]}:          # every ID the three tests of history()'s query could match
            if cand in wanted and keyed_by(key, cand) and touches(r, cand):
                mine[cand].append(r)
    reverted = reverted_rowids(con)
    return {i: build_events(mine[i], reverted) for i in ids}


# #251: freshness needs only an item's first event and its latest one made by a person. So the page's read keeps just those two per
# item (ReviewCache) and, on each call, reads only the log rows added since the last one. A change_log row is never changed once its
# step is committed (an undo writes new rows), so what was kept stays true; a log that has shrunk or lost a row starts again.
# The first read of an item is made by the database in one grouped pass over the project's own keys (other projects' rows are not read).
# `at` and the event number are joined into one text that sorts the way (at, event_id) does: char(31) is below every character of a stamp.
SORT_KEY = "e.at || char(31) || printf('%012d', e.event_id)"
FIRST_SQL = ("SELECT c.tbl, c.item_id, min(" + SORT_KEY + ") AS found FROM change_log c JOIN item_events e ON e.change = c.rowid "
             "WHERE c.field != 'updated_at' AND c.item_id >= ? AND c.item_id < ?@PERSON@ GROUP BY c.tbl, c.item_id")
LAST_SQL = FIRST_SQL.replace("min(", "max(")
PERSON_SQL = (" AND e.actor = 'you' AND e.route = 'dashboard' AND e.undoes IS NULL AND substr(c.via, 1, %d) != '%s'"
              % (len(REVERT_VIA), REVERT_VIA))
ENDS_SQL = ("SELECT c.rowid AS rowid, c.tbl, c.item_id, c.via, e.at, e.event_id, e.route, e.actor, e.undoes FROM change_log c "
            "JOIN item_events e ON e.change = c.rowid WHERE c.field != 'updated_at' AND c.rowid IN "
            "(SELECT rowid FROM change_log WHERE %s)")
NEW_SQL = ("SELECT c.rowid AS rowid, c.tbl, c.item_id, c.via, e.at, e.event_id, e.route, e.actor, e.undoes FROM change_log c "
           "JOIN item_events e ON e.change = c.rowid WHERE c.field != 'updated_at' AND c.rowid > ? AND c.rowid <= ?")


class ReviewCache:
    """What review_events keeps between calls (a Store holds one): {id: [first event, latest person's event]} and the log's
    newest rowid and row count when they were read."""

    def __init__(self):
        self.lock = threading.Lock()
        self.reset()

    def reset(self):
        self.mark = None                                   # None: nothing read yet
        self.count = 0
        self.events = {}


def _event(r, bare=False):
    """The keys freshness.freshness reads. `bare` is an event known only by its time: it has no author, so it never counts as a review."""
    if bare:
        return {"at": r["at"], "event_id": r["event_id"], "actor": None, "route": None, "is_undo": False, "undoes": None}
    return {"at": r["at"], "event_id": r["event_id"], "actor": r["actor"], "route": r["route"],
            "is_undo": str(r["via"]).startswith(REVERT_VIA), "undoes": r["undoes"]}


def _reduce(events):
    """Only what can still matter: the earliest event freshness can read and the latest by a person."""
    ordered = fresh._ordered(events)
    people = [e for e in ordered if fresh.by_person(e)]
    return ordered[:1] + people[-1:] if ordered else []


def _candidates(r):
    """The ids a log row is about, as history_many reads it: a plain key is its own item; a link or label key names its items."""
    key = str(r["item_id"])
    if "|" not in key:
        return [key]
    parts = key.split("|")
    return [c for c in {key, parts[0], *parts[1:-1]} if keyed_by(key, c) and touches(r, c)]


def _first_reads(con, wanted, codes, mine, odd):
    """Fill `mine` {id: events} for ids not seen before, from the database's grouped reads."""
    for sql, person in ((FIRST_SQL, False), (LAST_SQL, True)):
        for code in codes:
            for table, key, found in con.execute(sql.replace("@PERSON@", PERSON_SQL if person else ""), (code + "-", code + ".")):
                at, event_id = found.split("\x1f")
                row = {"tbl": table, "item_id": key, "at": at, "event_id": int(event_id), "actor": "you", "route": "dashboard",
                       "via": "", "undoes": None}
                for cand in _candidates(row):
                    if cand in wanted and cand in (key, key.split("|")[0]):                  # the item alone or first; the rest are read below
                        if not fresh._has_day(at):
                            odd.add(cand)
                        mine[cand].append(_event(row, bare=not person))
    where = " OR ".join(["item_id LIKE ?"] * len(codes))
    for r in con.execute(ENDS_SQL % where, ["%|" + c + "-%" for c in codes]):
        for cand in _candidates(r):
            if cand in wanted and cand != str(r["item_id"]).split("|")[0]:                  # the item in the middle or at the end
                if not fresh._has_day(r["at"]):
                    odd.add(cand)
                mine[cand].append(_event(r))


def review_events(con, ids, cache=None):
    """{id: events} for every ID in `ids`, holding only the events freshness.freshness can use (an item's first event and its
    latest one by a person, and the same from the rows that name it inside a link's key), so freshness gives the same answer
    as it does from history_many's full events (a test sets the two side by side). With a `cache` (a ReviewCache) the cost
    follows the rows added since the last call, not the length of the log. An item whose first stamp freshness cannot read is
    read whole, by history_many. Read only."""
    ids = list(dict.fromkeys(ids))
    if not ids:
        return {}
    cache = cache or ReviewCache()
    begun = not con.in_transaction
    if begun:
        con.execute("BEGIN")                               # one snapshot: the count, the new rows and the first reads agree
    try:
        with cache.lock:
            top = con.execute("SELECT coalesce(max(rowid), 0) FROM change_log").fetchone()[0]
            count = con.execute("SELECT count(*) FROM change_log").fetchone()[0]          # alone, the database counts pages, not rows
            if cache.mark is not None:
                added = con.execute("SELECT count(*) FROM change_log WHERE rowid > ?", (cache.mark,)).fetchone()[0]
                if top < cache.mark or count != cache.count + added:
                    cache.reset()                          # the log shrank or lost a row: nothing kept can be trusted
            if cache.mark is not None and top > cache.mark and cache.events:
                for r in con.execute(NEW_SQL, (cache.mark, top)):
                    for cand in _candidates(r):
                        if cand in cache.events:
                            cache.events[cand] = _reduce(cache.events[cand] + [_event(r)])
            new = [i for i in ids if i not in cache.events]
            if new:
                mine = {i: [] for i in new}
                odd = set()
                _first_reads(con, set(new), sorted({i.split("-", 1)[0] for i in new}), mine, odd)
                if odd:
                    mine.update(history_many(con, sorted(odd)))
                for i in new:
                    cache.events[i] = _reduce(mine[i])
            cache.mark, cache.count = top, count
            return {i: cache.events[i] for i in ids}
    finally:
        if begun:
            con.execute("COMMIT")


def original_date(con, item_id, current=None):
    """A milestone's Original date: the first agreed date in change_log that is in force (its step not undone, and not put back
    by an undo still in force), else `current`. creaite's milestone_original, plus the reverted rows (Head ruling on #31)."""
    reverted = reverted_rowids(con)
    for r in con.execute("SELECT c.rowid AS rowid, c.new_value FROM change_log c LEFT JOIN applies a ON a.apply_id = c.apply_id "
                         "WHERE c.tbl = 'milestones' AND c.item_id = ? AND c.field = 'baseline_date' "
                         "AND c.new_value IS NOT NULL AND a.undone_at IS NULL AND c.via NOT LIKE 'revert:%' ORDER BY c.rowid",
                         (item_id,)):
        if r["rowid"] not in reverted:
            return r["new_value"]
    return current


# ===== The display rows (#123): one function the peek's Activity tab and the Excel History sheet both call =====

FOOTNOTE = "Names come from this computer until you add your name in Settings \u203a Profile."
NO_ZONE = "Time zone not recorded (shown as UTC)"
ROW_LIMIT = 20000                      # the newest rows the Excel History sheet holds, per project (answered 29-10-2026)
CLOSING_LINE = "Older history is kept in clark. Showing the newest 20,000 changes."
FILTERS = {"all": "All", "changes": "Changes", "comments": "Comments and updates"}      # key -> the words on the tab
EMPTY = {"all": "No history yet.", "changes": "No changes yet.", "comments": "No comments or updates yet."}
OTHER = "Other"                        # a place or route the list below does not know: shown plainly, never as its code
KINDS = ("Created", "Changed", "Removed", "Undone", "Undo undone", "Creation undone", "Archived", "Restored", "Comment", "Email sent")
UNDO_KINDS = ("Undone", "Undo undone")
PAGE_FIELD, LEFT_OUT, PUT_BACK = "Published page", "Left out of the published page", "Put back on the published page"
PUT_BACK_PREFIX = "put back: "          # an Undo that made a removed label or link again

# The eleven "how and where" phrases, written exactly so (design note section 3).
HOW_PEEK, HOW_TABLE, HOW_BOARD, HOW_REPORT, HOW_EYE = "In the peek", "In the table", "On the board", "In the report", "With the eye"
HOW_EXCEL, HOW_ASK, HOW_DRAFT = "By Excel import", "By ask clark", "From a draft email"
HOW_EMAIL, HOW_TEXT, HOW_UNDO = "By a sent email", "From selected text", "Undo"
HOW_UNDO_MANY = "Undo (" + BATCH_UNDO + ")"      # #239: every row of one Undo several names it, so the rows read as one batch
HOW_PLACES = {"peek": HOW_PEEK, "cell": HOW_TABLE, "bulk": HOW_TABLE, "menu": HOW_TABLE, "board": HOW_BOARD, "report": HOW_REPORT,
              "eye": HOW_EYE, "draft": HOW_DRAFT, "email": HOW_EMAIL, "text": HOW_TEXT}
EXCEL_PREFIX = "Excel import:"
FILE_NAME_LIMIT = 60

# Plain names for fields. A column listed here under a table wins; otherwise the same column under COMMON.
COMMON = {
    "owner_id": "Owner (linked person)",
    "name": "Name", "description": "Description", "status": "Status", "owner": "Owner", "priority": "Priority",
    "due_date": "Due date", "raised": "Raised on", "closed": "Closed on", "workstream": "Workstream", "milestone": "Milestone",
    "use_case": "Use case", "client_visible": "Shown to the client", "client_message": "Message to the client",
    "archived": "Archived", "source": "Source", "project": "Project", "sort_order": "Order", "latest_update": "Latest update",
    "state": "State", "state_reason": "Reason for the state", "state_set": "State set on", "baseline_date": "Agreed date",
    "forecast_date": "Forecast date", "actual_date": "Actual date", "percent_complete": "Percent complete",
    "internal_note": "Internal note", "movement": "Movement", "lead": "Lead", "keywords": "Keywords", "aliases": "Other names",
    "created": "Created on", "type": "Type", "response_action": "Response action", "impact": "Impact", "likelihood": "Likelihood",
    "made_by": "Made by", "date": "Date", "needed_by": "Needed by", "reasoning": "Reasoning", "options": "Options",
    "revisit": "Revisit on", "replaces": "Replaces", "decision": "Decision", "title": "Title", "ref": "Reference",
    "headline": "Headline", "standing": "Where it stands", "labels": "Labels", "label_reason": "Reason for the label",
    "label_suggested": "Label suggested", "label": "Label", "added_by": "Added by", "added_at": "Added on", "reason": "Reason",
    "suggested": "Suggested", "health": "Health", "week_ending": "Week ending", "summary": "Summary", "key_changes": "Key changes",
    "from_item": "From item", "to_item": "To item", "kind": "Kind", "item_id": "Item", "body": "Text", "beside": "Beside",
    "hidden": "Hidden", "tile": "Tile", "outline": "Outline", "colour": "Colour", "note": "Note", "behaviour": "Behaviour",
    "default_choice": "Default choice", "builtin": "Built in", "url": "Link address", "path": "Folder", "spec": "View",
    "id": "ID", "code": "Code",
}
FIELD_NAMES = {
    "projects": {"name": "Project name", "phase": "Phase", "sponsor": "Sponsor", "health": "Health", "health_reason": "Reason for the health",
                 "active": "Active", "client_name": "Client", "current_state": "Where things stand", "week_ending": "Week ending",
                 "layout": "Report layout", "publish_local": "Local publish folder", "publish_client": "Client publish folder"},
    "milestones": {"name": "Name", "status": "Status"},
    "actions": {"description": "Action"},
    "raid": {"description": "Description", "type": "Type"},
    "decisions": {"status": "Status"},
    "use_cases": {"title": "Title"},
    "links": {"kind": "Link type"},
    "item_labels": {"item_id": "Item", "label": "Label"},
    "updates": {"health": "Health", "summary": "Summary", "key_changes": "Key changes"},
}
REMOVED_NAME = "Removed"
CONTENT_FIELD, CONTENT_CHANGED = "Content", "Changed"    # a section's body (a needs or tracker list, kept as JSON) is never shown, before or after: only that it changed
THING = {"links": "Link", "item_labels": "Label", "labels": "Label", "report_sections": "Section", "glance_tiles": "Tile",
         "report_hidden": "Hidden item", "saved_views": "Saved view", "documents": "Document", "source_folders": "Folder",
         "projects": "Project", "milestones": "Milestone", "workstreams": "Workstream", "actions": "Action", "raid": "RAID item",
         "decisions": "Decision", "use_cases": "Use case", "updates": "Weekly update"}      # what a Created or Removed row is about


def field_name(table, field):
    """The plain name of `field` in `table`. A field no table above knows is spaced out and capitalised, never shown as written."""
    name = FIELD_NAMES.get(table, {}).get(field) or COMMON.get(field)
    if name:
        return name
    return str(field).replace("_", " ").strip().capitalize() or OTHER


# Where an item's title lives, and the whole of each read (fixed text, no table name is ever put into SQL).
TITLE_COLUMN = {"projects": "name", "milestones": "name", "workstreams": "name", "actions": "description", "raid": "description",
                "decisions": "decision", "use_cases": "title"}
TITLE_SQL = {
    "projects": "SELECT name FROM projects WHERE code = ?", "milestones": "SELECT name FROM milestones WHERE id = ?",
    "workstreams": "SELECT name FROM workstreams WHERE id = ?", "actions": "SELECT description FROM actions WHERE id = ?",
    "raid": "SELECT description FROM raid WHERE id = ?", "decisions": "SELECT decision FROM decisions WHERE id = ?",
    "use_cases": "SELECT title FROM use_cases WHERE id = ?"}
TITLE_LIMIT = 120


def how_text(route, place, src_ref):
    """One of the eleven phrases for how and where a change was made. Anything else is OTHER, never the stored code."""
    if route == "undo":
        return HOW_UNDO_MANY if src_ref == BATCH_UNDO else HOW_UNDO
    if route == "excel":
        name = re.sub(r"\s+", " ", str(src_ref or "")).strip()
        if name[:len(EXCEL_PREFIX)].lower() == EXCEL_PREFIX.lower():
            name = name[len(EXCEL_PREFIX):].strip()
        name = re.split(r"[\\/]", name)[-1].strip()[:FILE_NAME_LIMIT]
        return f"{HOW_EXCEL} ({name})" if name else HOW_EXCEL
    if route == "assistant":
        return HOW_ASK
    return HOW_PLACES.get(place, OTHER)


def offset_of(text):
    """A timezone for a stored '+HH:MM' / '-HH:MM', or None when it is NULL or not that shape."""
    m = re.fullmatch(r"([+-])(\d\d):(\d\d)", str(text or ""))
    if not m or int(m.group(2)) > 23 or int(m.group(3)) > 59:
        return None
    delta = timedelta(hours=int(m.group(2)), minutes=int(m.group(3)))
    return timezone(delta if m.group(1) == "+" else -delta)


def when_text(at, utc_offset):
    """(DD-MM-YYYY HH:MM in the offset it was made at, the words saying the zone was not recorded or ''). A NULL offset shows UTC."""
    tz = offset_of(utc_offset)
    try:
        dt = timefmt.parse(at).astimezone(tz or timezone.utc)
    except (ValueError, OverflowError, OSError):
        return str(at), ("" if tz else NO_ZONE)
    return dt.strftime("%d-%m-%Y %H:%M"), ("" if tz else NO_ZONE)


def plain_value(field, value):
    """A stored value as a person reads it: an on/off column's 1 and 0 as Yes and No (archived has its own words), a logged
    time (YYYY-MM-DD HH:MM:SS.fff, UTC) as DD-MM-YYYY HH:MM. Anything else is returned as it is."""
    if field in FLAG_COLUMNS and str(value) in ("0", "1"):
        return "Yes" if str(value) == "1" else "No"
    if isinstance(value, str) and re.fullmatch(r"\d{4}-\d\d-\d\d \d\d:\d\d:\d\d(\.\d+)?", value):
        return when_text(value, None)[0]
    return value


def rich_plain(text):
    """The words of a rich field's HTML (publish.RICH: current_state, standing), for the rows and the sheet: tags and entities
    are gone, paragraphs become lines. One the cleaner refuses (too long) falls back to a plain tag strip. Never used for a
    plain-text field: that is shown as typed, so a '<' or '>' in it stays."""
    try:
        return plain_text(text)
    except SanitiseError:
        return _plain(text)


def shown_value(table, field, value):
    """plain_value, and for a rich field (publish.RICH) the words without the markup."""
    if isinstance(value, str) and field in RICH.get(table, ()):
        return rich_plain(value)
    return plain_value(field, value)


def _unpack(old, table=""):
    """A removed row's JSON as 'Field: value, Field: value' in plain names; text that is not that JSON is returned as it is."""
    try:
        data = json.loads(old)
    except (TypeError, ValueError):
        return old
    if not isinstance(data, dict):
        return old
    return ", ".join(f"{field_name('', k)}: {'' if v is None else shown_value(table, k, v)}" for k, v in data.items()
                     if k != "updated_at" and not (table == "report_sections" and k == "body"))      # a removed section's content is not unpacked into the row


class _Titles:
    def __init__(self, con):
        self.con, self.seen = con, {}

    def of(self, item_id):
        if item_id in self.seen:
            return self.seen[item_id]
        title = ""
        for table, sql in TITLE_SQL.items():
            r = self.con.execute(sql, (item_id,)).fetchone()
            if r:
                title = r[0]
                break
        if not title:       # an item that has gone (a create undone): the last name the log saw for it
            for table, col in TITLE_COLUMN.items():
                r = self.con.execute("SELECT new_value FROM change_log WHERE tbl = ? AND item_id = ? AND field = ? "
                                     "AND new_value IS NOT NULL ORDER BY rowid DESC LIMIT 1", (table, item_id, col)).fetchone()
                if r:
                    title = r[0]
                    break
        title = re.sub(r"\s+", " ", str(title or "")).strip()
        if len(title) > TITLE_LIMIT:
            title = title[:TITLE_LIMIT - 1] + "\u2026"
        self.seen[item_id] = title
        return title


def _ends(tbl, item_id):
    """The item IDs a change_log key is about: both ends of a link, the item of a label, else the key (a project's own code too)."""
    parts = str(item_id).split("|")
    if tbl == "links":
        return parts[:2]
    if tbl in ("item_labels", "report_hidden", "documents", "glance_tiles", "saved_views", "report_sections"):
        return parts[:1] if tbl != "report_hidden" else parts[1:2]
    if tbl == "updates":
        return parts[1:2]
    return parts[:1]


def _in_project(tbl, item_id, code):
    for end in _ends(tbl, item_id):
        if end == code or end.startswith(code + "-"):
            return True
    return False


def _has_column(con, table, column):
    return any(r[1] == column for r in con.execute("PRAGMA table_info(" + table + ")"))


SELECT_PART = ("SELECT c.rowid AS rowid, c.tbl, c.item_id, c.field, c.old_value, c.new_value, c.op, c.via, c.apply_id, c.at AS logged, "
               "a.by_user, e.event_id, e.route, e.place, e.src_ref, e.undoes, ")
FROM_PART = (" FROM change_log c JOIN item_events e ON e.change = c.rowid LEFT JOIN applies a ON a.apply_id = c.apply_id "
             "WHERE c.field != 'updated_at' AND (")
TAIL_PART = ") ORDER BY e.event_id DESC"


def _change_rows(con, where, params):
    """change_log rows (newest first) for a WHERE on c; applies.utc_offset is read when the column exists and is NULL otherwise."""
    offset = "a.utc_offset AS utc_offset" if _has_column(con, "applies", "utc_offset") else "NULL AS utc_offset"
    return con.execute(SELECT_PART + offset + FROM_PART + where + TAIL_PART, params).fetchall()


def _undo_events(con):
    """The event IDs that were themselves an Undo's put-back (their change's via starts with revert:), so an Undo of one reads
    as 'Undo undone' and not 'Undone' again."""
    return {r[0] for r in con.execute("SELECT e.event_id FROM item_events e JOIN change_log c ON c.rowid = e.change "
                                      "WHERE c.via LIKE ?", (REVERT_VIA + "%",))}


def _display(con, rows, keep):
    """Display rows from change_log rows: the rows of one step and item that made it (a Created item, or a label or link an Undo
    put back) are folded into one line."""
    titles = _Titles(con)
    undos = _undo_events(con)
    out, folded = [], {}
    for r in rows:
        ends = _ends(r["tbl"], r["item_id"])
        if r["via"] == SEED_VIA or not keep(r, ends):      # a new project's starting sections are not a person's change
            continue
        undo = r["route"] == "undo" or r["undoes"] is not None
        again = undo and r["undoes"] in undos              # this Undo reverses an earlier Undo
        undo_kind = "Undo undone" if again else "Undone"
        field_key, before, after = r["field"], r["old_value"], r["new_value"]
        field = field_name(r["tbl"], field_key)
        hidden = r["tbl"] == "report_hidden"
        fold = None
        if field_key == REMOVED:
            if hidden:
                kind, before, after, field = (undo_kind if undo else "Changed"), "", PUT_BACK, PAGE_FIELD
            else:
                kind = (undo_kind if again else "Creation undone") if r["undoes"] is not None else "Removed"
                before, after, field = _unpack(before, r["tbl"]), "", THING.get(r["tbl"], OTHER)
        elif field_key == "archived" and after in ("1", "0"):
            restored = after == "0"
            kind = undo_kind if undo else ("Restored" if restored else "Archived")
            field = ("Restored" if restored else "Archived") if undo else field
            before = after = ""
        elif r["op"] == OP_MADE:
            fold, kind = (r["apply_id"], r["tbl"], r["item_id"]), (undo_kind if undo else "Created")
            if hidden and not undo:
                kind = "Changed"
        elif r["tbl"] == "report_sections" and field_key == "body":      # content, never shown raw as 'Text': only that it changed
            kind, before, after, field = (undo_kind if undo else "Changed"), "", CONTENT_CHANGED, CONTENT_FIELD
        elif undo:
            kind, before, after = undo_kind, shown_value(r["tbl"], field_key, before), shown_value(r["tbl"], field_key, after)
        else:
            kind, before, after = "Changed", shown_value(r["tbl"], field_key, before), shown_value(r["tbl"], field_key, after)
        if fold in folded:
            folded[fold]["_values"][field_key] = after
            continue
        when, note = when_text(r["logged"], r["utc_offset"])
        items = [{"id": e, "title": titles.of(e)} for e in ends if e]
        row = {"when": when, "zone_note": note, "when_text": when + (" - " + note if note else ""), "who": r["by_user"] or "",
               "how": how_text(r["route"], r["place"], r["src_ref"]),
               "item_id": items[0]["id"] if items else "", "title": items[0]["title"] if items else "", "items": items,
               "item": "; ".join((i["id"] + " " + i["title"]).strip() for i in items),
               "field": field, "from": "" if before is None else before, "to": "" if after is None else after, "kind": kind,
               "table": r["tbl"], "event_id": r["event_id"], "step": r["apply_id"], "_at": r["logged"], "_seq": r["event_id"]}
        if fold:
            row["_values"] = {field_key: after}
            row["_back"] = undo
            folded[fold] = row
        out.append(row)
    for row in folded.values():
        vals = row.pop("_values")
        back = row.pop("_back")
        row["field"] = THING.get(row["table"], OTHER)
        col = TITLE_COLUMN.get(row["table"])
        if row["table"] == "report_hidden":
            row["field"], row["to"] = PAGE_FIELD, LEFT_OUT
        elif row["table"] == "links":
            a, b = (row["items"] + [{"id": ""}])[:2]
            row["to"] = f"{a['id']} {vals.get('kind') or 'blocks'} {b['id']}".strip()
        elif row["table"] == "item_labels":
            row["to"] = vals.get("label") or ""
        elif col:
            row["to"] = vals.get(col) or row["title"]
        else:
            row["to"] = vals.get("title") or vals.get("name") or vals.get("tile") or ""
        if row["table"] == "updates":
            row["to"] = vals.get("summary") or row["to"]
        if back and row["table"] != "report_hidden":
            row["to"] = PUT_BACK_PREFIX + row["to"]
    return out


def _comment_rows(con, where, params, titles):
    out = []
    for c in con.execute("SELECT id, item_id, author, at, text FROM comments WHERE " + where + " ORDER BY id DESC", params):
        when, note = when_text(c["at"], None)
        items = [{"id": c["item_id"], "title": titles.of(c["item_id"])}]
        out.append({"when": when, "zone_note": note, "when_text": when + " - " + note, "who": c["author"], "how": "",
                    "item_id": c["item_id"], "title": items[0]["title"], "items": items,
                    "item": (c["item_id"] + " " + items[0]["title"]).strip(), "field": "Comment", "from": "", "to": c["text"],
                    "kind": "Comment", "table": "comments", "event_id": None, "step": None, "_at": c["at"], "_seq": c["id"]})
    return out


# What "I sent it" recorded (#50). The first key is joined from parts: the one-writer test reads a string that begins with the word
# "update" as SQL (draft_email.py does the same).
EMAIL_MODE_WORDS = {"".join(("up", "date_request")): "asking for updates", "chase": "chasing", "decision": "asking for a decision"}


EMAIL_HOW = "in the Draft email"          # the History's "how" for a sent record: who, how and when (FR-43a)


def _email_rows(con, where, params, titles):
    """The "I sent it" records (#50) as rows: who pressed it, when, and the items asked about. Only in All: a sent record is not a
    change and not a comment. The ids are the record's own, in order; the email's words were never stored."""
    out = []
    for e in con.execute("SELECT seq, at, day, mode, by_user FROM email_sent WHERE " + where + " ORDER BY seq DESC", params):
        ids = [x["item_id"] for x in con.execute("SELECT item_id FROM email_sent_items WHERE seq = ? ORDER BY item_id", (e["seq"],))]
        when, note = when_text(e["at"], None)
        items = [{"id": i, "title": titles.of(i)} for i in ids]
        words = f"Emailed {_dmy(e['day'])} ({EMAIL_MODE_WORDS.get(e['mode'], e['mode'])}) about " + ", ".join(ids)
        out.append({"when": when, "zone_note": note, "when_text": when + " - " + note, "who": e["by_user"], "how": EMAIL_HOW,
                    "item_id": ids[0] if ids else "", "title": items[0]["title"] if items else "", "items": items,
                    "item": ", ".join((i["id"] + " " + i["title"]).strip() for i in items), "field": "Email sent", "from": "", "to": words,
                    "kind": "Email sent", "table": "email_sent", "event_id": None, "step": None, "_at": e["at"], "_seq": e["seq"]})
    return out


def _dmy(day):
    y, m, d = str(day).split("-")
    return f"{d}-{m}-{y}"


def _when_key(stamp):
    """A stored time for sorting; one that cannot be read sorts as the oldest, so a single odd comment time cannot break a view."""
    try:
        return timefmt.parse(stamp)
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)


def _finish(rows, kind, limit):
    """Filter, put newest first, cut to `limit`; return (rows, how many were cut)."""
    if kind not in FILTERS:
        raise ValueError(f"kind must be one of {sorted(FILTERS)}")
    if kind == "comments":
        rows = [r for r in rows if r["table"] in ("updates", "comments")]
    elif kind == "changes":
        rows = [r for r in rows if r["table"] not in ("updates", "comments", "email_sent")]
    rows.sort(key=lambda r: (_when_key(r["_at"]), r["table"] != "comments", r["_seq"]), reverse=True)
    cut = 0
    if limit is not None and len(rows) > limit:
        rows, cut = rows[:limit], len(rows) - limit
    for r in rows:
        r.pop("_at"), r.pop("_seq")
    return rows, cut


def rows_for_project(con, code, kind="all", limit=None):
    """The display rows for project `code`, newest first. Read-only. `kind`: "all", "changes" or "comments" (the tab's
    Comments and updates: weekly updates plus the comments table). Each row: when, zone_note ('' or NO_ZONE), when_text (both),
    who, how (one of the eleven phrases, or OTHER), item_id, title, items ([{id, title}], both ends of a link), item, field,
    from, to, kind (one of KINDS), table, event_id, step. `limit` keeps the newest that many."""
    like = (code, code + "-%", code + "|%", "%|" + code + "-%", "%|" + code)
    where = "c.item_id = ? OR c.item_id LIKE ? OR c.item_id LIKE ? OR c.item_id LIKE ? OR c.item_id LIKE ?"
    rows = _display(con, _change_rows(con, where, like), lambda r, ends: _in_project(r["tbl"], r["item_id"], code))
    titles = _Titles(con)
    rows += _comment_rows(con, "project = ?", (code,), titles)
    rows += _email_rows(con, "project = ?", (code,), titles)
    return _finish(rows, kind, limit)[0]


def rows_for_item(con, item_id, kind="all", limit=None):
    """The same display rows for one item (a link or label shows on the item at either end)."""
    where = "c.item_id = ? OR c.item_id LIKE ? OR c.item_id LIKE ? OR c.item_id LIKE ?"
    rows = _display(con, _change_rows(con, where, (item_id, item_id + "|%", "%|" + item_id + "|%", "%|" + item_id)),
                    lambda r, ends: item_id in ends)
    titles = _Titles(con)
    rows += _comment_rows(con, "item_id = ?", (item_id,), titles)
    rows += _email_rows(con, "seq IN (SELECT seq FROM email_sent_items WHERE item_id = ?)", (item_id,), titles)
    return _finish(rows, kind, limit)[0]


def view_for_project(con, code, kind="all", limit=None):
    """What a screen shows: {"rows", "footnote", "empty" (the words when there are no rows, else ''), "closing" (the last line
    when `limit` cut older rows, else '')}. The Excel History sheet calls this with limit=ROW_LIMIT."""
    rows = rows_for_project(con, code, kind)
    cut = limit is not None and len(rows) > limit
    rows = rows[:limit] if cut else rows
    return {"rows": rows, "footnote": FOOTNOTE, "empty": "" if rows else EMPTY[kind], "closing": CLOSING_LINE if cut else ""}


# ===== What the Activity tab asks for (#123): the same rows, with a word diff for text that changed =====

TAG_RE = re.compile(r"<[^>]*>")
WORD_RE = re.compile(r"\s+|[^\s]+")
DIFF_FROM_WORDS = 3                    # a text of at least this many words (either side) is shown as a word diff
DIFF_LIMIT = 20000                     # characters a diff reads from each side; a longer text is shown whole, never cut half way
DIFF_MAX_TOKENS = 400                  # words and spaces compared on each side after the unchanged start and end are set aside (a few ms to 50 ms)
DIFF_BUDGET = 4000                     # words and spaces compared in all, for one request; rows after that are shown whole
NOT_COMPARED = "Too long to compare word by word: the old text is shown struck through and the new text added, whole."


def _plain(text):
    """Rich text as plain words for the diff: tags dropped, a few entities read, white space made single. The page draws every
    piece as text (never as markup), so nothing here needs to be safe to inject."""
    text = TAG_RE.sub(" ", text or "")
    for a, b in (("&nbsp;", " "), ("&lt;", "<"), ("&gt;", ">"), ("&quot;", '"'), ("&#39;", "'"), ("&amp;", "&")):   # &amp; last: "&amp;lt;" is the text "&lt;"
        text = text.replace(a, b)
    return re.sub(r"\s+", " ", text).strip()        # the diff compares words, so a tag, a line break and a space all read as one space


def _pieces(a, b, budget=None):
    """(pieces, compared word by word) for two token lists that differ. The unchanged start and end are set aside first (a straight
    walk), so an edit in a long text costs only the changed stretch. A stretch over DIFF_MAX_TOKENS on a side, or over what is
    left of `budget` (a one-item list: tokens still to spend this request), is not compared: it is one removed piece and one
    added piece, whole. The work is bounded: at most DIFF_MAX_TOKENS squared steps a row."""
    lo = 0
    while lo < len(a) and lo < len(b) and a[lo] == b[lo]:
        lo += 1
    hi = 0
    while hi < len(a) - lo and hi < len(b) - lo and a[-1 - hi] == b[-1 - hi]:
        hi += 1
    head, tail = a[:lo], a[len(a) - hi:]
    ma, mb = a[lo:len(a) - hi], b[lo:len(b) - hi]
    out = []

    def put(op, words):
        text = "".join(words)
        if not text:
            return
        if out and out[-1]["op"] == op:
            out[-1]["text"] += text
        else:
            out.append({"op": op, "text": text})

    cost = max(len(ma), len(mb))
    exact = cost <= DIFF_MAX_TOKENS and (budget is None or cost <= budget[0])
    put("same", head)
    if not exact:
        put("removed", ma)
        put("added", mb)
    else:
        if budget is not None:
            budget[0] -= cost
        for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, ma, mb, autojunk=False).get_opcodes():
            if tag == "equal":
                put("same", ma[i1:i2])
            else:
                put("removed", ma[i1:i2])
                put("added", mb[j1:j2])
    put("same", tail)
    return out, exact


def word_diff(before, after, budget=None, rich=True):
    """Two texts as a list of pieces, in reading order: {"op": "same" | "removed" | "added", "text": ...}. Whole words and the
    single spaces between them; neighbouring pieces of one kind are joined. Empty when the texts read the same. A changed stretch
    too long to compare (see _pieces) comes as one removed and one added piece. `rich` (the default) reads the texts as HTML;
    `rich=False` compares them exactly as typed (a plain-text field, where '<' and '&lt;' are the person's own words)."""
    if rich:
        before, after = _plain(before), _plain(after)
    a, b = WORD_RE.findall(before or ""), WORD_RE.findall(after or "")
    return [] if a == b else _pieces(a, b, budget)[0]


def _with_diff(row, budget=None):
    """A row as the tab gets it: a change to a text of three words or more also carries `diff`; every other row carries none.
    `diff_note` is set (and says so plainly) when the texts were not compared word by word: too long, or this request's budget
    spent. A text over DIFF_LIMIT carries no diff, only the note."""
    before, after = row.get("from") or "", row.get("to") or ""
    if row["kind"] not in ("Changed", *UNDO_KINDS) or not before or not after:
        return dict(row, diff=None)
    if len(before) > DIFF_LIMIT or len(after) > DIFF_LIMIT:
        return dict(row, diff=None, diff_note=NOT_COMPARED)
    a, b = WORD_RE.findall(before), WORD_RE.findall(after)       # the rows already hold plain words for a rich field (_display)
    if max(len(before.split()), len(after.split())) < DIFF_FROM_WORDS:
        return dict(row, diff=None)
    if a == b:
        return dict(row, diff=[])
    pieces, exact = _pieces(a, b, budget)
    return dict(row, diff=pieces) if exact else dict(row, diff=pieces, diff_note=NOT_COMPARED)


def activity_for_project(con, code, kind="all", limit=ROW_LIMIT):
    """What the Activity tab shows for a project, as plain data for the page: the view_for_project result with each row's `diff`,
    the filter words (`filters`: [{key, label}], in the order shown) and the filter chosen. Read only."""
    view = view_for_project(con, code, kind, limit)
    budget = [DIFF_BUDGET]
    view["rows"] = [_with_diff(r, budget) for r in view["rows"]]
    view["filters"] = [{"key": k, "label": v} for k, v in FILTERS.items()]
    view["kind"] = kind
    return view


def activity_for_item(con, item_id, kind="all", limit=ROW_LIMIT):
    """The same for one item (the peek's Activity tab): no footnote counting beyond the rows, and the closing line only when cut."""
    rows = rows_for_item(con, item_id, kind)
    cut = limit is not None and len(rows) > limit
    rows = rows[:limit] if cut else rows
    budget = [DIFF_BUDGET]
    return {"rows": [_with_diff(r, budget) for r in rows], "footnote": FOOTNOTE, "empty": "" if rows else EMPTY[kind],
            "closing": CLOSING_LINE if cut else "", "filters": [{"key": k, "label": v} for k, v in FILTERS.items()], "kind": kind}
