"""One row's history, newest first, with undo links (#31). Cut down from creaite's item_history.py at v2.6.9 (db5adb2): only
change_log joined to item_events; no proposals, chases or mentions. Reads only."""
from clark.store import REVERT_VIA, reverted_rowids

JOINED = ("links", "item_labels")      # rows keyed by an item's ID with another: "from|to|kind", "item|label"


def touches(r, item_id):
    """True when a change_log row is about the item: its own row, or a link or label row with the item at one end."""
    if r["tbl"] not in JOINED:
        return True
    parts = str(r["item_id"]).split("|")
    return item_id in (parts[:2] if r["tbl"] == "links" else parts[:1])


def history(con, item_id):
    """[event, ...] for `item_id`, newest first. Each event: event_id, at, step, by_user, table, field, before, after, op,
    route, place, origin, actor, undoes (the event it reverses), undone_by (the event that reversed it) and in_force (False once
    an undo still in force has reversed it, or its own step was undone)."""
    rows = con.execute(
        "SELECT c.rowid AS rowid, c.tbl, c.item_id, c.field, c.old_value, c.new_value, c.op, c.via, c.apply_id, "
        "a.by_user, a.undone_at, e.event_id, e.at, e.route, e.place, e.origin, e.actor, e.src_ref, e.undoes "
        "FROM change_log c JOIN item_events e ON e.change = c.rowid LEFT JOIN applies a ON a.apply_id = c.apply_id "
        "WHERE c.field != 'updated_at' AND (c.item_id = ? OR c.item_id LIKE ? OR c.item_id LIKE ?) ORDER BY e.event_id",
        (item_id, item_id + "|%", "%|" + item_id + "|%")).fetchall()
    rows = [r for r in rows if touches(r, item_id)]
    reverted = reverted_rowids(con)
    undone_by = {r["undoes"]: r["event_id"] for r in rows if r["undoes"] is not None}
    events = []
    for r in rows:
        events.append({
            "event_id": r["event_id"], "at": r["at"], "step": r["apply_id"], "by_user": r["by_user"], "table": r["tbl"],
            "ref": r["item_id"], "field": r["field"], "before": r["old_value"], "after": r["new_value"], "op": r["op"],
            "route": r["route"], "place": r["place"], "origin": r["origin"], "actor": r["actor"], "src_ref": r["src_ref"],
            "undoes": r["undoes"],
            "is_undo": str(r["via"]).startswith(REVERT_VIA), "undone_by": undone_by.get(r["event_id"]),
            "in_force": not r["undone_at"] and r["rowid"] not in reverted,
        })
    events.reverse()
    return events


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
