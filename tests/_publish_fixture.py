"""The test plant for #39: one fictional project, PUB, with rows that must reach the published file and rows that must not.

tests/fixtures/publish-plant.json holds it: `data` (as Store.data_for gives it, WITH the dropped and archived rows, and with
fields and tables the file must never carry), `hidden`, `sections`, `label_rules`, `changes`, `as_at`, `markers` (text that
must never be in the file, by where it was planted), `kept_markers` (text that must be), and the `kept` and `dropped` ids.
Every marker starts ZQ-, so it can't be a word in the page's own code.

load() gives a fresh copy; build_db() puts the same plant in a real clark store (src/clark/schema.sql), for the tests that
read the database.
"""
import copy
import html
import json
from pathlib import Path

from clark.store import open_store

PLANT = Path(__file__).resolve().parent / "fixtures" / "publish-plant.json"



def load():
    """A fresh copy of the plant."""
    return json.loads(PLANT.read_text(encoding="utf-8"))


def inputs(plant=None):
    """What publish.select() takes: the plant without its test-only parts."""
    plant = copy.deepcopy(plant or load())
    return {k: plant[k] for k in ("as_at", "data", "hidden", "sections", "label_rules", "changes", "undone")}


def spellings(marker):
    """The four ways a marker could be in a file: as typed, HTML-escaped, JSON-escaped (ASCII, with < > & as \\u escapes) and
    lower-cased."""
    jsoned = json.dumps(marker, ensure_ascii=True)[1:-1]
    for ch in "<>&":
        jsoned = jsoned.replace(ch, "\\u%04x" % ord(ch))
    return [marker, html.escape(marker), html.escape(marker, quote=False), jsoned, marker.lower()]


def _insert(con, table, row):
    cols = list(row)
    con.execute(f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})", [row[c] for c in cols])


def build_db(path, plant=None):
    """The plant in a real clark store at `path` (src/clark/schema.sql, made by open_store). The rows go in by raw SQL on the
    store's own connection, past the writer, because the plant must hold rows the writer would refuse or can't write yet
    (archived and flag-off rows with planted markers, report_hidden and report_sections until #65, change_log history)."""
    plant = plant or load()
    d = plant["data"]
    store = open_store(Path(path), onedrive_roots=[])
    con = store.con
    con.execute("PRAGMA foreign_keys = OFF")
    try:
        con.execute("BEGIN")
        _insert(con, "projects", d["project"])
        for table in ("milestones", "workstreams", "actions", "raid", "decisions", "use_cases", "links", "comments"):
            for row in d[table]:
                _insert(con, table, {k: v for k, v in row.items() if v is not None})
        for item, names in d["labels"].items():
            for name in names:
                con.execute("INSERT OR IGNORE INTO labels (name) VALUES (?)", (name,))
                _insert(con, "item_labels", {"item_id": item, "label": name})
        for rule in plant["label_rules"]:
            con.execute("DELETE FROM labels WHERE name = ? AND builtin = 0", (rule["name"],))
            con.execute("INSERT OR REPLACE INTO labels (name, behaviour, default_choice) VALUES (?, ?, ?)",
                        (rule["name"], rule["behaviour"], rule["default_choice"]))
        for item in plant["hidden"]:
            _insert(con, "report_hidden", {"project": d["project"]["code"], "item_id": item})
        for s in plant["sections"]:
            _insert(con, "report_sections", s)
        for c in plant["changes"]:
            if c["apply_id"] is not None:
                con.execute("INSERT OR IGNORE INTO applies (apply_id, by_user, device) VALUES (?, 'Demo User', 'demo')",
                            (c["apply_id"],))
            _insert(con, "change_log", {k: v for k, v in c.items() if v is not None})
        for a in plant["undone"]:
            con.execute("INSERT OR IGNORE INTO applies (apply_id, by_user, device) VALUES (?, 'Demo User', 'demo')", (a,))
            con.execute("UPDATE applies SET undone_at = '2026-10-01 00:00:00.000' WHERE apply_id = ?", (a,))
        con.execute("COMMIT")
    except BaseException:
        con.execute("ROLLBACK")
        raise
    finally:
        con.execute("PRAGMA foreign_keys = ON")
        store.close()
    return Path(path)
