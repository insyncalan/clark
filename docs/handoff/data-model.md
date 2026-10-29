# Data model (SQLite), aligned with creaite

Written by a teammate, 28-10-2026, and revised the same day after the owner's ask: "ensure that the work item and milestone schemas reflect those of creaite". This replaces the first version, which followed the prototype's stores.

**The rule now:**
- The work item tables (`actions`, `raid`, `decisions`), `milestones`, `workstreams`, `projects` and the history tables are creaite's, from `system/scripts/schema.sql` at release v2.6.9 (`db5adb2`): the same columns, IDs, value lists and CHECKs.
- clark adds columns only where an agreed clark requirement needs one. Each is marked `-- clark:` with its reason, and they are all listed in "What clark adds" below.
- A table creaite doesn't have (use cases, the report's shape, client changes) is clark's own and follows creaite's style.

This is still a proposal: the project lead and the owner decide.

## Conventions (creaite's)
- Dates are stored as `YYYY-MM-DD` and shown as DD-MM-YYYY. Times are UTC, from `datetime('now')`.
- IDs: actions `<CODE>-A-NNN`, RAID items `<CODE>-NNN` (the type is a field), decisions `<CODE>-D-NNN`, milestones `<CODE>-M-NNN`, workstreams `<CODE>-W-NNN`. `next_id` is copied from `tracker.py`.
- `PRAGMA foreign_keys = ON`. Only `store.py` writes.
- Client wording is `client_message`, as in creaite, but in clark it is **optional** (the owner, 28-10-2026, #24: "a single report output managed by the user / editor"). When it is empty, the published page shows the item's own text. creaite's rule that a row needs its three headings filled in before it can be client-visible doesn't apply, and the column starts empty rather than with creaite's three-heading template.
- Rich text (current state, a use case's standing, text sections) is clean HTML from the editor, limited to a short list of allowed tags.

## creaite's tables, as clark uses them

```sql
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS projects (
  code            TEXT PRIMARY KEY CHECK (length(code) BETWEEN 3 AND 7 AND code GLOB '[A-Z]*' AND code NOT GLOB '*[^A-Z0-9]*'),
  name            TEXT NOT NULL,
  sponsor         TEXT,
  phase           TEXT,
  health          TEXT CHECK (health IN ('On track','At risk','Off track')),
  health_reason   TEXT,
  active          INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0,1)),
  archived        INTEGER NOT NULL DEFAULT 0 CHECK (archived IN (0,1) AND (archived = 0 OR active = 0)),
  client_name     TEXT,                                   -- clark: who the reports are for
  current_state   TEXT NOT NULL DEFAULT '',               -- clark: the Current state section (HTML)
  week_ending     TEXT CHECK (week_ending IS NULL OR week_ending GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),  -- clark: the report's date
  layout          TEXT NOT NULL DEFAULT 'boxed' CHECK (layout IN ('boxed','spine','cover')),             -- clark: report layout
  publish_local   TEXT,                                   -- clark: the local folder last used
  publish_client  TEXT,                                   -- clark: the client's SharePoint folder, as synced on this machine
  updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
-- Not copied: next_milestone and milestone_date. clark works the next milestone out from `milestones` (the Next milestone tile).

CREATE TABLE IF NOT EXISTS milestones (
  id            TEXT PRIMARY KEY CHECK (id GLOB '[A-Z]*-M-[0-9][0-9][0-9]' AND length(id) BETWEEN 9 AND 13 AND substr(id, 1, length(id) - 6) NOT GLOB '*[^A-Z0-9]*'),
  project       TEXT NOT NULL REFERENCES projects(code),
  name          TEXT NOT NULL,
  description   TEXT,
  baseline_date TEXT CHECK (baseline_date IS NULL OR baseline_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),   -- the Agreed date
  forecast_date TEXT CHECK (forecast_date IS NULL OR forecast_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
  status        TEXT NOT NULL DEFAULT 'Planned' CHECK (status IN ('Planned','Done','Cancelled')),
  sort_order    INTEGER NOT NULL DEFAULT 0,
  percent_complete INTEGER CHECK (percent_complete IS NULL OR percent_complete BETWEEN 0 AND 100),
  state         TEXT CHECK (state IS NULL OR state IN ('Achieved','On track','At risk','Slipped','Overdue','Forecast')),  -- clark: + Forecast
  state_set     INTEGER NOT NULL DEFAULT 0 CHECK (state_set IN (0,1)),
  state_reason  TEXT,
  owner         TEXT,
  actual_date   TEXT CHECK (actual_date IS NULL OR actual_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),   -- the Achieved date
  client_visible INTEGER NOT NULL DEFAULT 1 CHECK (client_visible IN (0,1)),   -- clark: on by default
  client_message TEXT,
  internal_note TEXT,             -- Movement's note; never in any client output (as in creaite)
  movement      TEXT CHECK (movement IS NULL OR movement IN ('hold','rebaseline','recover','escalate')),   -- clark: FR-53's choice
  workstream    TEXT,                                   -- clark: the prototype groups milestones by workstream (checked like actions.workstream)
  source        TEXT NOT NULL,
  archived      INTEGER NOT NULL DEFAULT 0 CHECK (archived IN (0,1)),
  updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS workstreams (
  id         TEXT PRIMARY KEY CHECK (id GLOB '[A-Z]*-W-[0-9][0-9][0-9]' AND length(id) BETWEEN 9 AND 13
                                     AND substr(id, 1, length(id) - 6) NOT GLOB '*[^A-Z0-9]*'),
  project    TEXT NOT NULL REFERENCES projects(code),
  name       TEXT NOT NULL CHECK (length(trim(name)) > 0),
  lead       TEXT,
  keywords   TEXT,
  aliases    TEXT,
  status     TEXT NOT NULL DEFAULT 'Active' CHECK (status IN ('Active','Closed')),
  created    TEXT NOT NULL CHECK (created GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
  source     TEXT NOT NULL,
  archived   INTEGER NOT NULL DEFAULT 0 CHECK (archived IN (0,1)),
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE (project, name COLLATE NOCASE)
);
-- Not copied: channel (a Teams channel; clark has no Teams).

CREATE TABLE IF NOT EXISTS actions (
  id           TEXT PRIMARY KEY CHECK (id GLOB '[A-Z]*-A-[0-9][0-9][0-9]' AND length(id) BETWEEN 9 AND 13 AND substr(id, 1, length(id) - 6) NOT GLOB '*[^A-Z0-9]*'),
  project      TEXT NOT NULL REFERENCES projects(code),
  description  TEXT NOT NULL,
  workstream   TEXT,
  owner        TEXT NOT NULL DEFAULT 'TBC',
  priority     TEXT NOT NULL DEFAULT 'Medium' CHECK (priority IN ('Urgent','High','Medium','Low')),
  due_date     TEXT CHECK (due_date IS NULL OR due_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
  status       TEXT NOT NULL DEFAULT 'Open' CHECK (status IN ('Open','Delayed','Closed','Cancelled')),
  raised       TEXT NOT NULL,
  closed       TEXT CHECK (closed IS NULL OR closed >= raised),
  latest_update TEXT,
  client_visible INTEGER NOT NULL DEFAULT 1 CHECK (client_visible IN (0,1)),   -- clark: on by default
  client_message TEXT NOT NULL DEFAULT '',   -- clark: optional, no template (#24)
  milestone    TEXT REFERENCES milestones(id),
  use_case     TEXT,                                  -- clark: the use case it belongs to (FR-31; checked by the writer)
  source       TEXT NOT NULL,
  archived     INTEGER NOT NULL DEFAULT 0 CHECK (archived IN (0,1)),
  updated_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS raid (
  id           TEXT PRIMARY KEY CHECK (id GLOB '[A-Z]*-[0-9][0-9][0-9]' AND length(id) BETWEEN 7 AND 11 AND substr(id, 1, length(id) - 4) NOT GLOB '*[^A-Z0-9]*'),
  project      TEXT NOT NULL REFERENCES projects(code),
  type         TEXT NOT NULL CHECK (type IN ('Risk','Assumption','Issue','Dependency')),
  workstream   TEXT,
  description  TEXT NOT NULL,
  owner        TEXT NOT NULL DEFAULT 'TBC',
  response_action TEXT,
  due_date     TEXT CHECK (due_date IS NULL OR due_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
  impact       TEXT CHECK (impact IN ('High','Medium','Low')),
  likelihood   TEXT CHECK (likelihood IN ('High','Medium','Low')),
  priority     TEXT CHECK (priority IN ('Urgent','High','Medium','Low')),   -- worked out from impact and likelihood
  status       TEXT NOT NULL DEFAULT 'Open' CHECK (status IN ('Open','Closed','Cancelled')),
  raised       TEXT NOT NULL,
  closed       TEXT CHECK (closed IS NULL OR closed >= raised),
  client_visible INTEGER NOT NULL DEFAULT 1 CHECK (client_visible IN (0,1)),   -- clark: on by default
  client_message TEXT NOT NULL DEFAULT '',   -- clark: optional, no template (#24)
  milestone    TEXT REFERENCES milestones(id),
  use_case     TEXT,                                  -- clark: as on actions
  source       TEXT NOT NULL,
  archived     INTEGER NOT NULL DEFAULT 0 CHECK (archived IN (0,1)),
  updated_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS decisions (
  id           TEXT PRIMARY KEY CHECK (id GLOB '[A-Z]*-D-[0-9][0-9][0-9]' AND length(id) BETWEEN 9 AND 13 AND substr(id, 1, length(id) - 6) NOT GLOB '*[^A-Z0-9]*'),
  project      TEXT NOT NULL REFERENCES projects(code),
  decision     TEXT NOT NULL,
  made_by      TEXT,
  client_visible INTEGER NOT NULL DEFAULT 1 CHECK (client_visible IN (0,1)),   -- clark: on by default
  client_message TEXT NOT NULL DEFAULT '',
  date         TEXT CHECK (date IS NULL OR date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
  status       TEXT NOT NULL DEFAULT 'Made' CHECK (status IN ('Pending','Made','Withdrawn')),
  needed_by    TEXT CHECK (needed_by IS NULL OR needed_by GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
  reasoning    TEXT,
  options      TEXT,
  revisit      TEXT,
  replaces     TEXT REFERENCES decisions(id),
  use_case     TEXT,                                  -- clark: as on actions
  source       TEXT NOT NULL,
  archived     INTEGER NOT NULL DEFAULT 0 CHECK (archived IN (0,1)),
  updated_at   TEXT NOT NULL DEFAULT (datetime('now')),
  CHECK (status <> 'Made' OR date IS NOT NULL),
  CHECK (replaces IS NULL OR replaces <> id)
);

CREATE TABLE IF NOT EXISTS links (
  from_item   TEXT NOT NULL,
  to_item     TEXT NOT NULL,
  kind        TEXT NOT NULL DEFAULT 'blocks' CHECK (kind IN ('blocks')),
  source      TEXT NOT NULL,
  created     TEXT NOT NULL DEFAULT (date('now')),
  PRIMARY KEY (from_item, to_item, kind),
  CHECK (from_item <> to_item)
);

-- Labels: kept because the built-in Sensitive label (exclude) keeps a row out of the published file, as in creaite.
CREATE TABLE IF NOT EXISTS labels (
  name           TEXT PRIMARY KEY COLLATE NOCASE CHECK (length(trim(name)) > 0 AND instr(name, ',') = 0),
  colour         TEXT NOT NULL DEFAULT 'grey',
  note           TEXT,
  behaviour      TEXT NOT NULL DEFAULT 'warn' CHECK (behaviour IN ('warn','exclude')),
  default_choice TEXT NOT NULL DEFAULT 'include' CHECK (default_choice IN ('include','exclude')),
  builtin        INTEGER NOT NULL DEFAULT 0 CHECK (builtin IN (0,1))
);
INSERT OR IGNORE INTO labels (name, colour, note, behaviour, default_choice, builtin)
  VALUES ('Sensitive', 'red', 'Commercially or client sensitive', 'warn', 'exclude', 1);
CREATE TRIGGER IF NOT EXISTS labels_keep_builtin_delete BEFORE DELETE ON labels WHEN OLD.builtin = 1
  BEGIN SELECT RAISE(ABORT, 'a built-in label cannot be deleted'); END;
CREATE TRIGGER IF NOT EXISTS labels_keep_builtin_rename BEFORE UPDATE OF name, builtin ON labels
  WHEN OLD.builtin = 1 AND (NEW.name <> OLD.name OR NEW.builtin = 0)
  BEGIN SELECT RAISE(ABORT, 'a built-in label cannot be renamed'); END;
CREATE TABLE IF NOT EXISTS item_labels (
  item_id    TEXT NOT NULL,
  label      TEXT NOT NULL REFERENCES labels(name) ON UPDATE CASCADE,
  added_by   TEXT,
  added_at   TEXT NOT NULL DEFAULT (datetime('now')),
  reason     TEXT,
  suggested  INTEGER NOT NULL DEFAULT 0 CHECK (suggested IN (0,1)),
  PRIMARY KEY (item_id, label)
);

-- The weekly health record, one row per project per report date (creaite's `updates`).
CREATE TABLE IF NOT EXISTS updates (
  week_ending  TEXT NOT NULL,
  project      TEXT NOT NULL REFERENCES projects(code),
  health       TEXT NOT NULL CHECK (health IN ('On track','At risk','Off track')),
  summary      TEXT NOT NULL,
  key_changes  TEXT,
  PRIMARY KEY (week_ending, project)
);

-- History and undo: creaite's three tables. One step (a save, a Sneak peek apply, an import, an accepted client change) is one
-- `applies` row; every field it changed is a `change_log` row; each change also has an `item_events` row saying how it came.
CREATE TABLE IF NOT EXISTS applies (
  apply_id    INTEGER PRIMARY KEY AUTOINCREMENT,
  at          TEXT NOT NULL DEFAULT (datetime('now')),
  proposals   TEXT NOT NULL DEFAULT '[]',   -- clark: always '[]' (no proposal files); kept so the copied code is unchanged
  file_ops    TEXT,
  undone_at   TEXT,
  by_user     TEXT NOT NULL,                -- clark: who made the step (the settings name); needed for history now, and for several users later
  device      TEXT NOT NULL                 -- clark: which installation wrote it (a random id made at setup); for several users later
);
CREATE TABLE IF NOT EXISTS change_log (
  at         TEXT NOT NULL DEFAULT (datetime('now')),
  apply_id   INTEGER REFERENCES applies(apply_id),
  tbl        TEXT NOT NULL,
  item_id    TEXT NOT NULL,
  field      TEXT NOT NULL,
  old_value  TEXT,
  new_value  TEXT,
  op         TEXT NOT NULL DEFAULT 'update' CHECK (op IN ('insert','update','undo')),
  via        TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS item_events (
  event_id   INTEGER PRIMARY KEY AUTOINCREMENT,
  at         TEXT NOT NULL,
  apply_id   INTEGER REFERENCES applies(apply_id),
  item_id    TEXT NOT NULL,
  change     INTEGER,
  kind       TEXT NOT NULL CHECK (kind IN ('change','reject')),
  route      TEXT NOT NULL CHECK (route IN ('dashboard','assistant','excel','undo','client','team','migrate')),   -- clark's routes (cut down; + client, team)
  place      TEXT CHECK (place IS NULL OR place IN ('peek','cell','bulk','menu','report','dashboard','excel','board')),
  origin     TEXT CHECK (origin IS NULL OR origin IN ('report','sneak')),
  actor      TEXT NOT NULL CHECK (actor IN ('you','clark')),          -- creaite's two values, renamed
  src_ref    TEXT CHECK (src_ref IS NULL OR (length(src_ref) <= 300 AND instr(src_ref, char(10)) = 0)),
  undoes     INTEGER REFERENCES item_events(event_id)
);
CREATE INDEX IF NOT EXISTS item_events_item ON item_events(item_id);
CREATE INDEX IF NOT EXISTS item_events_change ON item_events(change);
CREATE INDEX IF NOT EXISTS change_log_item ON change_log(item_id);
```

**Not copied from creaite:** `promises`, `rejected` (proposal fingerprints) and `vault_search`. ask clark's index lives in its own file, not in `clark.db`.

## clark's own tables (creaite has none of these)

```sql
CREATE TABLE IF NOT EXISTS use_cases (
  id            TEXT PRIMARY KEY CHECK (id GLOB '[A-Z]*-U-[0-9][0-9][0-9]' AND length(id) BETWEEN 9 AND 13 AND substr(id, 1, length(id) - 6) NOT GLOB '*[^A-Z0-9]*'),
  project       TEXT NOT NULL REFERENCES projects(code),
  ref           TEXT NOT NULL DEFAULT '',     -- the project's own reference as shown, e.g. "1.1" or "1.3 and 1.7"
  title         TEXT NOT NULL,
  status        TEXT NOT NULL CHECK (status IN ('On track','Flag','High risk')),
  headline      TEXT NOT NULL DEFAULT '',
  standing      TEXT NOT NULL DEFAULT '',     -- HTML
  sort_order    INTEGER NOT NULL DEFAULT 0,
  client_visible INTEGER NOT NULL DEFAULT 1 CHECK (client_visible IN (0,1)),
  source        TEXT NOT NULL,
  archived      INTEGER NOT NULL DEFAULT 0 CHECK (archived IN (0,1)),
  updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS report_sections (
  project TEXT NOT NULL REFERENCES projects(code) ON DELETE CASCADE,
  id      TEXT NOT NULL,
  type    TEXT NOT NULL CHECK (type IN ('current','glance','usecases','milestones','text','raid','actions','decisions','docs')),
  title   TEXT NOT NULL,
  body    TEXT NOT NULL DEFAULT '',
  beside  INTEGER NOT NULL DEFAULT 0 CHECK (beside IN (0,1)),
  hidden  INTEGER NOT NULL DEFAULT 0 CHECK (hidden IN (0,1)),
  sort_order INTEGER NOT NULL,
  PRIMARY KEY (project, id)
);

CREATE TABLE IF NOT EXISTS glance_tiles (
  project TEXT NOT NULL REFERENCES projects(code) ON DELETE CASCADE,
  tile    TEXT NOT NULL CHECK (tile IN ('health','overdue','risks','decisions')),
  hidden  INTEGER NOT NULL DEFAULT 0 CHECK (hidden IN (0,1)),
  outline TEXT NOT NULL DEFAULT '' CHECK (outline IN ('','R','A','G','N')),
  sort_order INTEGER NOT NULL,
  PRIMARY KEY (project, tile)
);

CREATE TABLE IF NOT EXISTS report_hidden (            -- rows the editor left out of the published page
  project TEXT NOT NULL REFERENCES projects(code) ON DELETE CASCADE,
  item_id TEXT NOT NULL,                              -- an action, RAID item, decision, milestone or use case id
  PRIMARY KEY (project, item_id)
);

CREATE TABLE IF NOT EXISTS saved_views (
  project TEXT NOT NULL REFERENCES projects(code) ON DELETE CASCADE,
  name    TEXT NOT NULL,
  spec    TEXT NOT NULL,
  sort_order INTEGER NOT NULL,
  PRIMARY KEY (project, name)
);

CREATE TABLE IF NOT EXISTS documents (
  project TEXT NOT NULL REFERENCES projects(code) ON DELETE CASCADE,
  id      TEXT NOT NULL,
  title   TEXT NOT NULL,
  kind    TEXT NOT NULL DEFAULT '',
  url     TEXT NOT NULL,
  date    TEXT,
  sort_order INTEGER NOT NULL,
  archived INTEGER NOT NULL DEFAULT 0 CHECK (archived IN (0,1)),   -- clark (#126, schema version 2): archived, never deleted
  PRIMARY KEY (project, id)
);

CREATE TABLE IF NOT EXISTS source_folders (
  project TEXT NOT NULL REFERENCES projects(code) ON DELETE CASCADE,
  path    TEXT NOT NULL,
  sort_order INTEGER NOT NULL,
  PRIMARY KEY (project, path)
);

CREATE TABLE IF NOT EXISTS publications (
  seq         INTEGER PRIMARY KEY AUTOINCREMENT,
  project     TEXT NOT NULL REFERENCES projects(code),
  at          TEXT NOT NULL DEFAULT (datetime('now')),
  week_ending TEXT,
  local_path  TEXT NOT NULL,
  client_path TEXT,
  word        INTEGER NOT NULL DEFAULT 0 CHECK (word IN (0,1)),
  file_sha256 TEXT NOT NULL,
  checks      TEXT NOT NULL CHECK (checks IN ('passed','not needed')),
  by_user     TEXT NOT NULL
);

-- The changes inbox: changes files from teammates (team-changes.md) and from the published page (client-edits.md, option A).
CREATE TABLE IF NOT EXISTS change_files (
  sha256      TEXT PRIMARY KEY,                       -- a file already handled is never applied twice
  source      TEXT NOT NULL CHECK (source IN ('team','client')),
  project     TEXT NOT NULL REFERENCES projects(code),
  from_name   TEXT NOT NULL,                          -- as entered; a claim, not proof
  device      TEXT,                                   -- team only: the teammate's installation
  base        TEXT NOT NULL,                          -- team: "<master db_id>:<base apply_id>"; client: the published file's SHA-256
  read_at     TEXT NOT NULL DEFAULT (datetime('now')),
  refused     TEXT,                                   -- why the whole file was refused, if it was
  apply_id    INTEGER REFERENCES applies(apply_id)    -- the step that applied it
);
CREATE TABLE IF NOT EXISTS staged_changes (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  file        TEXT NOT NULL REFERENCES change_files(sha256),
  at          TEXT NOT NULL,                          -- when the change was made, from the file
  item_id     TEXT NOT NULL,
  field       TEXT NOT NULL,                          -- checked against the source's allowed list by the writer
  before      TEXT,                                   -- the value the sender started from (JSON)
  after       TEXT NOT NULL,                          -- the value they want (JSON)
  master_now  TEXT,                                   -- the master's value when staged (JSON)
  state       TEXT NOT NULL CHECK (state IN ('clean','same','clash','accepted','rejected')),
  new_id      TEXT,                                   -- team only: the master id given to an item the teammate created
  decided_at  TEXT                                    -- the allowed lists (a client file carries comments only, #21 and #22) are the writer's checks:
);                                                    -- SQLite allows no subquery in a CHECK

CREATE TABLE IF NOT EXISTS comments (
  id      INTEGER PRIMARY KEY AUTOINCREMENT,
  project TEXT NOT NULL REFERENCES projects(code),
  item_id TEXT NOT NULL,
  author  TEXT NOT NULL,
  at      TEXT NOT NULL DEFAULT (datetime('now')),
  text    TEXT NOT NULL CHECK (length(text) <= 2000),
  client_visible INTEGER NOT NULL DEFAULT 1 CHECK (client_visible IN (0,1)),
  source  INTEGER REFERENCES staged_changes(id)
);

CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT NOT NULL);   -- schema_version, created_at, device, db_id, role (owner|teammate), share_folder; on a teammate's copy base_db_id, base_seq, base_apply_id
```

## Milestone states: creaite's rules, plus Forecast
These are copied from `tracker.py`'s `suggested_state` and `milestone_state` at v2.6.9. The state shown is worked out in this order, and the first match wins:

| State | When |
|---|---|
| Achieved | `status = 'Done'` |
| The user's own | `state_set = 1`. At risk is only ever set by the user. A state better than the dates suggest needs a `state_reason` |
| Forecast (clark) | `state_set = 1` with `state = 'Forecast'`: the date isn't agreed yet |
| Overdue | the **agreed** date (`baseline_date`) has passed. In creaite this is the agreed date, not the forecast |
| Slipped | the forecast date is later than the agreed date |
| On track | otherwise |

- **The original date** is the first `baseline_date` in `change_log`, not a column, as in creaite.
- **A rebaseline** changes `baseline_date` and records a decision, as creaite's `_write_rebaseline` does. Choosing "rebaseline" in Movement takes that path.
- **Client wording** uses creaite's `MS_CLIENT_WORD`: Slipped shows as "Expected later" and Overdue as "Late".

## What clark adds to creaite's tables
| Where | Column | Why |
|---|---|---|
| `projects` | `client_name`, `current_state`, `week_ending`, `layout`, `publish_local`, `publish_client` | The report page, layouts and To client (FR-1x, FR-8x) |
| `milestones` | `Forecast` in `state` | "add a 'forecast' state to milestones" |
| `milestones` | `movement` | FR-53's choice for each milestone |
| `milestones` | `workstream` | The prototype groups milestones by workstream. **Open point 3: no recommendation was given, so the owner's "agreed with recommendations" doesn't settle it yet** |
| `actions`, `raid`, `decisions` | `use_case` | FR-31: a use case's work items |
| `actions`, `raid`, `decisions`, `milestones` | `client_visible` defaults to 1, and `client_message` is optional with no template | the owner, 28-10-2026 (#24): "Client visible is toggled on by default for all work items" |
| `applies` | `by_user`, `device` | Who made each step. Needed later for several users (`portability-and-sharing.md`) |
| `item_events` | the `route`, `place` and `origin` lists | Cut down to clark's routes, plus `client` and `team` |

## The client flag per row
- There is **one report output**, managed by the editor (the owner, 28-10-2026, #24: "No - a single report output managed by the user / editor. Client visible is toggled on by default for all work items").
- `client_visible` defaults to 1 on every work item, milestone and use case. The editor turns it off for a row that shouldn't be published.
- A row carrying an `exclude` label (Sensitive) never goes out, as in creaite. `internal_note` is never published.
- The published file only takes client-visible rows that aren't in `report_hidden`. Its build drops the others, so they are never in the file at all. creaite's separate client checks (`client_leak.py`, `client_output.py`, `client_check.py`) aren't copied. The build's own tests check that a hidden row, a row with the flag off, a Sensitive row and an internal note are each absent from the file.

## History and undo
- These are creaite's tables and rules (`tracker.py` `log()`, `cmd_undo`, `_changed_since`). A step is one `applies` row, and undo reverses one `apply_id`, so the toast's Undo reverses exactly its own step. A row changed by a later step is skipped and named, as in creaite.
- The peek's Activity tab reads `item_events` joined to `change_log` for one item, newest first (`item_history.py`).

## Archive, never delete (#126, BRD FR-43c)
- Projects, work items, milestones, use cases and documents are archived, never deleted. They all carry an `archived` flag (0 or 1); `documents` gained it in schema version 2. Archiving does not change the status: a Closed action stays Closed, and Restore brings the record back as it was.
- A project does not have to be closed first: archiving it sets `active = 0` itself and archives everything in it (Restore puts `active` back as it was). Archive and Restore are each one step with one Undo, and the history keeps every row.
- Archived rows are left out of the default views, the counts, the Excel export and the published page. The reads take an `archived` choice: live rows (the default for the page), archived rows only, or all.
- The version 2 migration also adds the board place to the history (`item_events.place`). It takes a safety copy first and refuses to run if it cannot.
- The writer has no delete for these records. What still removes a row: report sections (the owner's exception, with an Undo toast), annotations such as links, labels, tiles and hidden flags, and Undo of something the same step created. Links, labels and report sections are not records in this sense.

## Excel round trip
- The sheets follow creaite's `excel_sync.py`: actions, RAID, decisions and milestones, plus clark's use cases sheet. The columns are the columns above, keyed by id.
- An import matches rows by id, and a row without an id is new. The import is staged, and each accepted row is one step. A work item or milestone that is open and missing from the sheet is staged as "removed from the workbook", and accepting it archives it (the status is not changed). Finished rows missing from the sheet are skipped, and a use case missing from the sheet is only noted.

## What changes for the prototype and the BRD (for the project lead)
- **Health:** G/A/R becomes On track, At risk or Off track. The pill keeps its colours.
- **Statuses:**
  - Actions: Open, Delayed, Closed, Cancelled. The prototype's "In progress" and "Done" go.
  - Decisions: Pending, Made, Withdrawn. "Agreed" becomes "Made".
  - RAID: Open, Closed, Cancelled, with types Risk, Assumption, Issue or Dependency, and impact, likelihood and priority.
- **IDs:**
  - Milestones are `<CODE>-M-NNN` (the prototype uses M1).
  - Risks and issues share `<CODE>-NNN`, with the type as a field. The prototype uses -R- and -I-.
  - Use cases are `<CODE>-U-NNN`, with the shown reference in `ref`.
- **Milestones:** Overdue is worked out from the agreed date, not the forecast. The Agreed date is `baseline_date`.

## Open (the owner's call)
1. **Use clark's additions, or creaite exactly?** Decided ("agreed with recommendations"): keep the additions listed above, each marked in the schema.
2. **RAG on risks and issues (FR-40): decided, the mapping** ("agreed with recommendations"). creaite has no RAG: it works priority out from impact and likelihood. The schema above keeps creaite's model, and the pill shows priority as a colour: Urgent or High is Red, Medium is Amber, Low is Green. Setting the pill sets impact and likelihood. *Recommendation:* this mapping. The other choice is an extra `rag` column, which would sit beside priority and could disagree with it.
3. **Workstream on milestones: still open.** creaite has none. *My recommendation:* keep it. It's an optional column, checked against the project's active workstreams as `actions.workstream` is, and the prototype groups milestones by it.
