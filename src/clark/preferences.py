"""Row 1535 step 1: the preference registry. Every preference a person sets, in one list: where it is kept, its scope, its default, its
shape and how it is migrated. tests/test_preferences_1535.py scans the page and settings.py for keys and fails on one that is not here,
so a new preference cannot ship unregistered. Facts about each entry come from the audit on issue #1535 and the code; nothing moves here.

An entry is (key, where, scope, default, shape, migrates). `where` is "db" (clark.db), "file" (the data folder) or "browser"
(localStorage; keys start `clark.`; `*` stands for the part that varies: a project, table or place). `scope` is "app", "per project",
"per table", "per place" or "reader" (a published page's reader; stays in the reader's browser).
"""
import json
import re
import threading
from collections import namedtuple
from pathlib import Path

Preference = namedtuple("Preference", "key where scope default shape migrates")
WHERES = ("db", "file", "browser")
SCOPES = ("app", "per project", "per table", "per place", "reader")

REGISTRY = tuple(Preference(*r) for r in (
    ('app_settings.ask_enabled', 'db', 'app', 'schema default', '0/1', 'frozen schema_vN.sql migration steps'),
    ('app_settings.theme', 'db', 'app', 'schema default', 'classic|cards', 'frozen schema_vN.sql migration steps'),
    ('app_settings.ask_instructions', 'db', 'app', 'schema default', 'text', 'frozen schema_vN.sql migration steps'),
    ('app_settings.ask_files', 'db', 'app', 'schema default', '0/1', 'frozen schema_vN.sql migration steps'),
    ('app_settings.ask_new_projects', 'db', 'app', 'schema default', '0/1', 'frozen schema_vN.sql migration steps'),
    ('install_defaults', 'db', 'app', 'schema default', 'review_days, gantt_editor, gantt_client, gantt_name', 'frozen schema_vN.sql migration steps'),
    ('connector_switches', 'db', 'app', 'schema default', 'one 0/1 per connector', 'frozen schema_vN.sql migration steps'),
    ('projects.layout_brand_review_gantt_client', 'db', 'per project', 'schema default', 'layout, brand, review days, Gantt settings, client name, ask_off', 'frozen schema_vN.sql migration steps'),
    ('report_sections', 'db', 'per project', 'schema default', 'sections, order, titles, hidden', 'frozen schema_vN.sql migration steps'),
    ('glance_tiles', 'db', 'per project', 'schema default', 'dashboard tiles', 'frozen schema_vN.sql migration steps'),
    ('report_hidden', 'db', 'per project', 'schema default', 'item ids left out of the report', 'frozen schema_vN.sql migration steps'),
    ('source_folders', 'db', 'per project', 'schema default', 'folders ask clark may read', 'frozen schema_vN.sql migration steps'),
    ('saved_views', 'db', 'per project', 'schema default', 'name, spec, sort_order (empty today: views are in the browser, see clark.fviews)', 'frozen schema_vN.sql migration steps'),
    ('settings.json:backups_kept', 'file', 'app', '14', 'whole number 1 to 365', 'read with defaults; a bad value falls back'),
    ('settings.json:profile_name', 'file', 'app', 'empty', 'text, 60', 'read with defaults; a bad value falls back'),
    ('settings.json:profile_email', 'file', 'app', 'empty', 'text, 254', 'read with defaults; a bad value falls back'),
    ('settings.json:profile_alias', 'file', 'app', 'empty', 'text, 60', 'read with defaults; a bad value falls back'),
    ('settings.json:backup_copy_folder', 'file', 'app', 'none', 'folder path', 'read with defaults; a bad value falls back'),
    ('settings.json:ai_model', 'file', 'app', 'none', 'model id', 'read with defaults; a bad value falls back'),
    ('settings.json:ai_claude_off', 'file', 'app', 'off', 'bool', 'read with defaults; a bad value falls back'),
    ('settings.json:ai_chatgpt_on', 'file', 'app', 'off', 'bool', 'read with defaults; a bad value falls back'),
    ('settings.json:ai_accepted', 'file', 'app', 'none', 'accepted weaker model', 'read with defaults; a bad value falls back'),
    ('ask_folders_all.json', 'file', 'app', 'empty', 'list of full paths', 'read with defaults; a bad value falls back'),
    ('ask-commands/', 'file', 'app', 'none', 'one JSON per slash command', 'read with defaults; a bad value falls back'),
    ('clark-brand.json', 'file', 'app', 'none', 'branding manifest (also brand-last.json, brand-backups/)', 'read with defaults; a bad value falls back'),
    ('excel-export-state.json', 'file', 'app', 'none', 'what the last export wrote', 'read with defaults; a bad value falls back'),
    ('clark.appearance', 'browser', 'app', 'automatic', 'light|dark|auto', 'none yet (rows 2 to 4 of #1535)'),
    ('clark.density', 'browser', 'app', 'normal', 'density id', 'none yet (rows 2 to 4 of #1535)'),
    ('clark.motion', 'browser', 'app', 'follow the computer', 'on|off', 'none yet (rows 2 to 4 of #1535)'),
    ('clark.single-keys', 'browser', 'app', 'on', 'on|off', 'none yet (rows 2 to 4 of #1535)'),
    ('clark.welcome', 'browser', 'app', 'not seen', "'done'", 'none yet (rows 2 to 4 of #1535)'),
    ('clark.lastProject', 'browser', 'app', 'none', 'project code', 'none yet (rows 2 to 4 of #1535)'),
    ('clark.peekWidth', 'browser', 'app', 'default width', 'pixels', 'none yet (rows 2 to 4 of #1535)'),
    ('clark.peek.details', 'browser', 'app', 'open', 'open|closed', 'none yet (rows 2 to 4 of #1535)'),
    ('clark.askWidth', 'browser', 'app', 'default width', 'pixels', 'none yet (rows 2 to 4 of #1535)'),
    ('clark.helpTab', 'browser', 'app', 'start', 'tab key', 'none yet (rows 2 to 4 of #1535)'),
    ('clark.work.v1', 'browser', 'per project', 'table', 'one object by project: view, group by, swimlane, collapsed, board column order and widths', 'none yet (rows 2 to 4 of #1535)'),
    ('clark.cols.show.*', 'browser', 'per project', 'standard columns', 'column ids, by table and project', 'none yet (rows 2 to 4 of #1535)'),
    ('clark.cols.*', 'browser', 'per table', 'standard widths', 'object of widths by column', 'none yet (rows 2 to 4 of #1535)'),
    ('clark.order.*', 'browser', 'per table', 'standard order', 'list of column ids', 'none yet (rows 2 to 4 of #1535)'),
    ('clark.fviews', 'browser', 'per project', 'none', 'saved views the person created', 'none yet (rows 2 to 4 of #1535)'),
    ('clark.forder', 'browser', 'per project', 'standard', 'view ids in tab order', 'none yet (rows 2 to 4 of #1535)'),
    ('clark.fcore', 'browser', 'per project', 'standard', 'renamed, deleted or changed standard views', 'none yet (rows 2 to 4 of #1535)'),
    ('clark.tlZoom.*', 'browser', 'per place', '1', 'zoom number', 'none yet (rows 2 to 4 of #1535)'),
    ('clark.tlScale.*', 'browser', 'per place', 'month', 'scale key', 'none yet (rows 2 to 4 of #1535)'),
    ('clark.msv.*', 'browser', 'per place', 'line', 'line|cal', 'none yet (rows 2 to 4 of #1535)'),
    ('clark.msv.calv.*', 'browser', 'per place', 'month', 'scale key', 'none yet (rows 2 to 4 of #1535)'),
    ('clark.msDet.*', 'browser', 'per place', 'open', 'bool', 'none yet (rows 2 to 4 of #1535)'),
    ('clark.msAll.*', 'browser', 'per place', 'false', 'bool', 'none yet (rows 2 to 4 of #1535)'),
    ('clark.msp.view', 'browser', 'app', 'plan', 'plan|move', 'none yet (rows 2 to 4 of #1535)'),
    ('clark.ucAll', 'browser', 'app', 'false', 'bool', 'none yet (rows 2 to 4 of #1535)'),
    ('clark.ucPage', 'browser', 'per project', 'none', 'object by project: use case list state', 'none yet (rows 2 to 4 of #1535)'),
    ('clark.recentTemplates', 'browser', 'app', 'none', 'list of template ids', 'none yet (rows 2 to 4 of #1535)'),
    ('clark.assignRecent.*', 'browser', 'per project', 'none', 'list of names', 'none yet (rows 2 to 4 of #1535)'),
    ('clark.dragHintSeen', 'browser', 'app', 'false', 'bool', 'none yet (rows 2 to 4 of #1535)'),
    ('clark.import.sheets', 'browser', 'app', 'none', 'list of sheets', 'none yet (rows 2 to 4 of #1535)'),
    ('clark.askChats.*', 'browser', 'per project', 'none', 'list of chats', 'none yet (rows 2 to 4 of #1535)'),
    ('clark.askChatsKeep', 'browser', 'app', 'a count', 'count from the allowed list', 'none yet (rows 2 to 4 of #1535)'),
    ('clark.reader.name', 'browser', 'reader', 'none', 'text (published page; stays there by design)', 'none yet (rows 2 to 4 of #1535)'),
    ('clark.reader.look', 'browser', 'reader', 'automatic', 'light|dark (published page; stays there by design)', 'none yet (rows 2 to 4 of #1535)'),
    ('clark.fline', 'browser', 'per project', 'none', 'the filter line, kept for the session only (sessionStorage)', 'not kept across sessions by design'),
    ('clark.work.*', 'browser', 'reader', 'none', "published page's own view memory, by project code (clientView STORAGE_PREFIX)", 'none yet (rows 2 to 4 of #1535)'),
))


def keys(where=None):
    return {p.key for p in REGISTRY if where is None or p.where == where}


# ===== Step 3: the person's browser preferences, kept in the data folder too =====
# `<data folder>/preferences.json`, beside settings.json: {"version": 1, "imported": bool, "values": {"clark.<key>": "<the text the browser holds>"}}.
# The browser stays the fast copy; the page asks for this file as it opens (the server puts it in the page), writes each change through
# POST /api/preferences, and the first time it finds the file empty it offers what its own browser holds (the one-time import). The values are the
# browser's own text, kept as they are: a key this release does not know is kept, never dropped. A published page's reader preferences
# (`clark.reader.`) stay in the reader's browser and are never taken here. Nothing here is logged, sent anywhere or published.
FILE = "preferences.json"
VERSION = 1
KEY = re.compile(r"clark\.[A-Za-z0-9_.\-]{1,200}")
NOT_KEPT = ("clark.reader.",)
VALUE_MAX = 1024 * 1024          # one key's text; a larger one is left in the browser only
FILE_MAX = 16 * 1024 * 1024      # a larger file is not read
LOCK = threading.RLock()


def kept(key):
    """True for a key that goes into the data folder: a `clark.` key, not a reader's."""
    return isinstance(key, str) and KEY.fullmatch(key) is not None and not key.startswith(NOT_KEPT)


def _clean(values):
    return {k: v for k, v in values.items() if kept(k) and isinstance(v, str) and len(v) <= VALUE_MAX} if isinstance(values, dict) else {}


def read(data_dir):
    """{"imported": bool, "values": {...}} from the data folder; an empty one when the file is missing, not a JSON object or too large."""
    path = Path(data_dir) / FILE
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > FILE_MAX:
            return {"imported": False, "values": {}}
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, RecursionError):
        return {"imported": False, "values": {}}
    if not isinstance(doc, dict):
        return {"imported": False, "values": {}}
    return {"imported": doc.get("imported") is True, "values": _clean(doc.get("values"))}


def _save(data_dir, doc):
    from clark import platform
    platform.write_file(Path(data_dir) / FILE, json.dumps({"version": VERSION, **doc}, indent=1, sort_keys=True) + "\n")


def _unreadable(data_dir):
    """True when the file is there but could not be read as ours: it is never replaced then (it may hold what a person set)."""
    path = Path(data_dir) / FILE
    if not (path.is_symlink() or path.exists()):
        return False
    try:
        return not (not path.is_symlink() and path.is_file() and path.stat().st_size <= FILE_MAX and isinstance(json.loads(path.read_text(encoding="utf-8")), dict))
    except (OSError, ValueError, RecursionError):
        return True


class Preferences:
    """The seam of GET and POST /api/preferences (server.py): (status, body) for each."""

    def __init__(self, data_dir):
        self.data_dir = Path(data_dir)

    def get(self):
        return 200, {"ok": True, **read(self.data_dir)}

    def values(self):
        """What the page is given as it opens: {"imported", "values"}."""
        return read(self.data_dir)

    def save(self, req):
        """{"set": {key: text}, "remove": [key], "import": {key: text}, "reset": true}, each part optional. `set` and `remove` are changes the
        person made; `import` is the browser's old values, taken only while the file has never been imported (so a second import changes
        nothing); `reset` empties the file (and says it was imported, so the old browser values are not taken back). A key or value that is
        not allowed is skipped, never an error. (200, {"ok": true, "imported", "values"}) or (400, ...) for a body that is not this shape."""
        allowed = {"set", "remove", "import", "reset"}
        if (not isinstance(req, dict) or not set(req) <= allowed or not req
                or not all(isinstance(req.get(k, {}), dict) for k in ("set", "import"))
                or not isinstance(req.get("remove", []), list) or not isinstance(req.get("reset", False), bool)):
            return 400, {"ok": False, "message": "That could not be read. Nothing was saved.", "code": "bad_request"}
        with LOCK:
            if _unreadable(self.data_dir):
                return 400, {"ok": False, "message": "Your preferences file could not be read, so nothing was changed. Nothing was lost.", "code": "unreadable"}
            doc = read(self.data_dir)
            values, imported = dict(doc["values"]), doc["imported"]
            changed = False
            if req.get("reset"):
                values, imported, changed = {}, True, True
            offered = _clean(req.get("import"))
            if offered and not imported:
                values = {**offered, **values}
                imported, changed = True, True
            if "set" in req:
                values.update(_clean(req["set"]))
                changed = True
            for k in req.get("remove", []):
                if kept(k):
                    changed = values.pop(k, None) is not None or changed
            if changed and (values != doc["values"] or imported != doc["imported"]):
                _save(self.data_dir, {"imported": imported, "values": values})
            return 200, {"ok": True, "imported": imported, "values": values}
