"""The fictional demo projects a brand-new data folder opens with (#731), and how they are taken away again.

Rule: a data folder that holds nothing at all (no project, no person, no step ever made, and no note that the demo was
removed) is given the made-up projects of dev/demo_data.py when clark starts. Never otherwise: not when any data is there,
not after a restore or an import (they leave data), not once the person has removed the demo. If dev/demo_data.py is not
there the folder is left empty, one line goes in the log, and nothing fails.

How it is marked (no schema change; SCHEMA_VERSION stays): three keys in the existing `meta` table.
  demo_projects  JSON list of the demo project codes
  demo_applies   JSON list of the apply ids of the steps that made them
  demo_removed   "1" once the demo was removed (or nothing of it was left to remove): it is never loaded again
A demo project counts as demo only while it is untouched: any step other than the loading ones that wrote a row of it
(an edit, a new row inside it), or a publication, sent email, saved view or comment that names it, makes it the person's.
Remove takes away only demo projects still untouched; when unsure it keeps. A safety copy is taken first; if it can't be
made nothing is removed.
"""
import json
import logging
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

from clark import backup, store as clark_store
from clark.changes import _call
from clark.store import key_of

LOG = logging.getLogger("clark.demo")
DEV = Path(__file__).resolve().parents[2] / "dev"
PROJECTS, APPLIES, REMOVED = "demo_projects", "demo_applies", "demo_removed"
# tables whose rows carry a `project` column (their key is built by store.key_of)
OWN = ("milestones", "workstreams", "actions", "raid", "decisions", "use_cases", "updates", "report_sections", "glance_tiles",
       "report_hidden", "documents", "source_folders")
# rows of these name a project but the demo never writes them and they are never deleted: any one makes the project the person's
PERSONS = ("SELECT 1 FROM saved_views WHERE project = ?", "SELECT 1 FROM comments WHERE project = ?",
           "SELECT 1 FROM publications WHERE project = ?", "SELECT 1 FROM email_sent WHERE project = ?")
NOTHING_TO_REMOVE = "There is no demo data to remove."
FAILED = "The demo data could not be removed, and nothing was changed."


def _get(con, key):
    row = con.execute("SELECT v FROM meta WHERE k = ?", (key,)).fetchone()
    return row[0] if row else None


def _is_empty(con):
    """True when the file holds nothing at all and was never told the demo is gone."""
    if _get(con, REMOVED) or _get(con, PROJECTS):
        return False
    return not any(con.execute(sql).fetchone() for sql in ("SELECT 1 FROM projects", "SELECT 1 FROM people", "SELECT 1 FROM applies"))


def load_if_fresh(store, onedrive_roots=None):
    """The store to use: `store`, or (when its file is brand new and empty) a new one holding the demo projects. The file is
    built whole in a scratch folder beside it, with its markers written, then moved into place: all of it or none of it."""
    if not _is_empty(store.con):
        return store
    path = store.path
    try:
        if str(DEV) not in sys.path:
            sys.path.insert(0, str(DEV))
        import demo_data
    except ImportError:
        LOG.warning("demo data not loaded: dev/demo_data.py is missing")
        return store
    old = {r[0]: r[1] for r in store.con.execute("SELECT k, v FROM meta WHERE k IN ('created_at', 'device', 'db_id')")}
    store.close()
    scratch = None
    try:
        scratch = Path(tempfile.mkdtemp(prefix=".demo-", dir=str(path.parent)))      # its own backups folder, so no copy of an empty file lands in the real one
        built = scratch / path.name
        demo_data.build(built, demo_data.parse_now(os.environ.get("CLARK_NOW")), onedrive_roots)
        made = clark_store.open_store(built, onedrive_roots=onedrive_roots)
        try:
            made.mark_demo(old)                                # this installation's own identity, not the demo build's, and the demo's marks
        finally:
            made.close()
        demo_data.remove_database(path)
        os.replace(str(built), str(path))
        LOG.info("a new data folder: opened with the demo projects")
    except Exception as e:                                     # whatever goes wrong the folder is left empty, and clark starts
        LOG.warning("demo data not loaded: %s", e)
    finally:
        if scratch is not None:
            _clear(scratch)
    return clark_store.open_store(path, onedrive_roots=onedrive_roots)


def _clear(folder):
    import shutil
    shutil.rmtree(str(folder), ignore_errors=True)


def _keys(store, code):
    """Every (table, key) of the rows a project holds, itself included."""
    keys = {("projects", code)}
    ids = set()
    for t in OWN:
        for r in store.read(t, project=code):
            keys.add((t, key_of(t, r)))
            if t in ("milestones", "workstreams", "actions", "raid", "decisions", "use_cases"):
                ids.add(r["id"])
    for r in store.read("links"):
        if r["from_item"] in ids or r["to_item"] in ids:
            keys.add(("links", key_of("links", r)))
    for r in store.read("item_labels"):
        if r["item_id"] in ids:
            keys.add(("item_labels", key_of("item_labels", r)))
    return keys


def removable(store):
    """{code: keys} of the demo projects that are still there and untouched."""
    con = store.con
    if _get(con, REMOVED):
        return {}
    try:
        marked = json.loads(_get(con, PROJECTS) or "[]")
        made = set(json.loads(_get(con, APPLIES) or "[]"))
    except ValueError:
        return {}
    later = {(t, i) for t, i, a in con.execute("SELECT tbl, item_id, apply_id FROM change_log") if a is None or a not in made}
    staged = {r[0] for r in con.execute("SELECT item_id FROM staged_changes")}       # a teammate's change waiting on one of its rows
    found = {}
    for code in marked:
        if not con.execute("SELECT 1 FROM projects WHERE code = ?", (code,)).fetchone():
            continue
        if any(con.execute(sql, (code,)).fetchone() for sql in PERSONS):
            continue
        keys = _keys(store, code)
        if keys & later or {k for _, k in keys} & staged:
            continue
        found[code] = keys
    return found


def remove(store):
    """Take the untouched demo projects away: the safety copy first (nothing is removed if it can't be made), then every row of
    theirs and its change history in one transaction (store.remove_demo), and the note that the demo is gone. Returns how many
    projects went."""
    found = removable(store)
    if found:
        backup.take(store, "daily")                  # Invalid, in plain words, if it can't be made: nothing has changed yet
    store.remove_demo({code: sorted(keys) for code, keys in found.items()})
    return len(found)


class Demo:
    """The seam the server calls for GET /api/demo and POST /api/demo/clear, for the database at `path`."""

    def __init__(self, path, onedrive_roots=None):
        self.path, self.onedrive_roots = path, onedrive_roots

    def status(self):
        """(200, {"ok": True, "demo": bool}): whether demo data is on show."""
        return _call(self.path, self.onedrive_roots, None, lambda store, who, req: (200, {"ok": True, "demo": bool(removable(store))}), None)

    def remove(self, req=None):
        def work(store, who, req):
            try:
                n = remove(store)
            except sqlite3.Error as e:
                LOG.warning("removing the demo data failed: %s", e)
                return 400, {"ok": False, "message": FAILED, "code": "refused"}
            LOG.info("demo data removed (%d projects)", n)
            return 200, {"ok": True, "removed": n}
        return _call(self.path, self.onedrive_roots, None, work, req)
