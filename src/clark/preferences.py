"""Row 1535 step 1: the preference registry. Every preference a person sets, in one list: where it is kept, its scope, its default, its
shape and how it is migrated. tests/test_preferences_1535.py scans the page and settings.py for keys and fails on one that is not here,
so a new preference cannot ship unregistered. Facts about each entry come from the audit on issue #1535 and the code; nothing moves here.

An entry is (key, where, scope, default, shape, migrates). `where` is "db" (clark.db), "file" (the data folder) or "browser"
(localStorage; keys start `clark.`; `*` stands for the part that varies: a project, table or place). `scope` is "app", "per project",
"per table", "per place" or "reader" (a published page's reader; stays in the reader's browser).
"""
from collections import namedtuple

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
