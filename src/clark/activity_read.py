"""The one function behind GET /api/activity (#42): one item's Activity tab in the peek, for the owner only (Edit mode).

The server imports nothing from clark, so this is the seam it is given (as it is given `movement`). It checks the item is one of
the project's, opens its own read-only connection, asks history.activity_for_item and keeps only what the tab draws: for each
change, who made it, how, when, what changed and from what to what, newest first, and, for a change Undo several would refuse, the
plain reason (`undo_refused`, else "") so the tab withholds the tick. Writes nothing. No publishing module uses it.
It is thin in what it does, not in what it loads: it imports `changes` (a large module) for the one function undo_refusals, which
shares its checks with Undo several, so importing it keeps the tab and Undo in step.
Standard library only, Python 3.9."""

from clark import changes, history
from clark.source_name import source_name
from clark.store import OP_MADE, Store, connect

TABLES = ("actions", "raid", "decisions", "milestones")      # the rows a peek opens on
ROW_KEYS = ("step", "when_text", "who", "how", "kind", "field", "from", "to", "diff", "diff_note", "from_file", "undo_refused")
ROW_LIMIT = 200                      # the newest changes the tab shows; the closing line says when older ones are left out
CLOSING = "Older changes are kept in clark. Showing the newest 200."
TEXT_LIMIT = 4000                    # characters of a from or to value the tab gets; a longer text ends with an ellipsis


def _short(value):
    text = "" if value is None else str(value)
    return text if len(text) <= TEXT_LIMIT else text[:TEXT_LIMIT] + "…"


def _row(r):
    out = {k: r.get(k) for k in ROW_KEYS}
    out["from"], out["to"] = _short(out["from"]), _short(out["to"])
    out["undo_refused"] = out["undo_refused"] or ""
    if out["diff_note"] is None:
        out.pop("diff_note")
    if not out["from_file"]:
        out.pop("from_file")
    return out


def has_item(data, item_id):
    """True when `item_id` is a row of the project's data (an action, a register item, a decision or a milestone)."""
    return any(isinstance(r, dict) and r.get("id") == item_id for t in TABLES for r in (data.get(t) or []))


def source_line(con, item_id, events):
    """The Source line for the Peek: the item's stored `source` words by NAME (source_name: the last part of any path, the date day first;
    row 1077), then " by <name>" when its first insert step has a name. A published file carries the name itself (publish.select), so it
    asks no server. "" when the row has none (the table name is from TABLES, never a caller's)."""
    for table in TABLES:
        row = con.execute("SELECT source FROM " + table + " WHERE id = ?", (item_id,)).fetchone()
        if row is not None:
            break
    else:
        return ""
    words = source_name(row[0])                                          # the stored text has YYYY-MM-DD and may hold a path; the person reads DD-MM-YYYY and the name. The column is untouched
    made = [e for e in events if e.get("op") == OP_MADE and e.get("ref") == item_id and e.get("table") == table]
    who = str(made[-1].get("by_user") or "").strip() if made else ""      # events are newest first: the last is the first insert
    return words + (" by " + who if who and words else "")


def make_read(path, data_for):
    """`read(code, item_id)` for the server: None when the project or the item isn't there, else {"rows", "empty", "closing"}.
    `path` is clark.db; `data_for(code)` is Store.data_for."""
    def read(code, item_id):
        data = data_for(code)
        if data is None or not has_item(data, item_id):
            return None
        con = connect(path, readonly=True)
        try:
            view = history.activity_for_item(con, item_id, "all", ROW_LIMIT)
            source = source_line(con, item_id, history.history(con, item_id))
            refused = changes.undo_refusals(Store(con, path), code, {r["step"] for r in view["rows"] if isinstance(r.get("step"), int)})
        finally:
            con.close()
        rows = [_row(dict(r, undo_refused=refused.get(r.get("step"), ""))) for r in view["rows"]]
        return {"rows": rows, "empty": "" if rows else "Nothing has changed on this item yet.",
                "closing": CLOSING if view["closing"] else "", "source": source}
    return read
