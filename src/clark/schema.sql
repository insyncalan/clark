-- clark's database (SQLite). Written only by src/clark/store.py (#31).
-- creaite's tables are copied from creaite v2.6.9 (db5adb2) system/scripts/schema.sql, with their CHECKs unchanged; every
-- difference is a line marked "-- clark:" (tests/test_store_schema.py compares them). The tables after "clark's own tables"
-- are clark's. Source of truth for the shape: docs/handoff/data-model.md.
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
  contact_name    TEXT CHECK (contact_name IS NULL OR length(contact_name) <= 80),            -- clark: (#51, version 3) the project contact's name
  contact_email   TEXT CHECK (contact_email IS NULL OR length(contact_email) BETWEEN 3 AND 254),   -- clark: (#51, version 3) the outside address a published page's Draft email goes To
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
  route      TEXT NOT NULL CHECK (route IN ('dashboard','assistant','excel','undo','client','team','migrate')),   -- clark: clark's routes (cut down; + client, team)
  place      TEXT CHECK (place IS NULL OR place IN ('peek','cell','bulk','menu','report','dashboard','excel','board')),   -- clark: clark's places (+ board, #126: the board's own moves)
  origin     TEXT CHECK (origin IS NULL OR origin IN ('report','sneak')),   -- clark: clark's origins
  actor      TEXT NOT NULL CHECK (actor IN ('you','clark')),          -- clark: creaite's two values, renamed
  src_ref    TEXT CHECK (src_ref IS NULL OR (length(src_ref) <= 300 AND instr(src_ref, char(10)) = 0)),
  undoes     INTEGER REFERENCES item_events(event_id)
);
CREATE INDEX IF NOT EXISTS item_events_item ON item_events(item_id);
CREATE INDEX IF NOT EXISTS item_events_change ON item_events(change);
CREATE INDEX IF NOT EXISTS change_log_item ON change_log(item_id);

-- ===== clark's own tables (creaite has none of these) =====

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
  archived INTEGER NOT NULL DEFAULT 0 CHECK (archived IN (0,1)),     -- clark (#126, schema version 2)
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
