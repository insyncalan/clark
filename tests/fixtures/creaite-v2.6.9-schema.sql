-- Portfolio tracker schema (SQLite). Created by: python scripts/tracker.py init
-- Rules are enforced here so bad data cannot get in, whichever route it comes from.
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS projects (
  code            TEXT PRIMARY KEY CHECK (length(code) BETWEEN 3 AND 7 AND code GLOB '[A-Z]*' AND code NOT GLOB '*[^A-Z0-9]*'),
  name            TEXT NOT NULL,
  sponsor         TEXT,
  phase           TEXT,
  health          TEXT CHECK (health IN ('On track','At risk','Off track')),
  health_reason   TEXT,
  next_milestone  TEXT,
  milestone_date  TEXT CHECK (milestone_date IS NULL OR milestone_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
  active          INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0,1)),
  archived        INTEGER NOT NULL DEFAULT 0 CHECK (archived IN (0,1) AND (archived = 0 OR active = 0)),  -- BL-09: an archived project is never active
  updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Milestones (BL-11): baseline vs forecast; slips feed the health criteria.
-- BL-186 (1.5.0): baseline_date is the Agreed date (the first one in change_log is the Original); a rebaseline also records a
-- decision. status is Planned, Done (Achieved) or Cancelled (Missed is retired: tracker.py migrate made each one Planned with
-- state_reason is required when he sets a better state than the dates suggest; client_message when client_visible.
CREATE TABLE IF NOT EXISTS milestones (
  id            TEXT PRIMARY KEY CHECK (id GLOB '[A-Z]*-M-[0-9][0-9][0-9]' AND length(id) BETWEEN 9 AND 13 AND substr(id, 1, length(id) - 6) NOT GLOB '*[^A-Z0-9]*'),
  project       TEXT NOT NULL REFERENCES projects(code),
  name          TEXT NOT NULL,
  description   TEXT,
  baseline_date TEXT CHECK (baseline_date IS NULL OR baseline_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
  forecast_date TEXT CHECK (forecast_date IS NULL OR forecast_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
  status        TEXT NOT NULL DEFAULT 'Planned' CHECK (status IN ('Planned','Done','Cancelled')),
  sort_order    INTEGER NOT NULL DEFAULT 0,
  percent_complete INTEGER CHECK (percent_complete IS NULL OR percent_complete BETWEEN 0 AND 100),
  state         TEXT CHECK (state IS NULL OR state IN ('Achieved','On track','At risk','Slipped','Overdue')),
  state_set     INTEGER NOT NULL DEFAULT 0 CHECK (state_set IN (0,1)),
  state_reason  TEXT,
  owner         TEXT,             -- a full name from the people register (BL-55)
  actual_date   TEXT CHECK (actual_date IS NULL OR actual_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),   -- the Achieved date
  client_visible INTEGER NOT NULL DEFAULT 0 CHECK (client_visible IN (0,1)),
  client_message TEXT,            -- plain wording; required when client_visible = 1 (checked by tracker.py)
  internal_note TEXT,
  source        TEXT NOT NULL,
  archived      INTEGER NOT NULL DEFAULT 0 CHECK (archived IN (0,1)),   -- BL-09
  updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Workstreams (BL-58): part of each project's structure, like milestones. Items name their workstream
-- (actions.workstream, raid.workstream); tracker.py rejects one that isn't an Active workstream of the item's project.
CREATE TABLE IF NOT EXISTS workstreams (
  id         TEXT PRIMARY KEY CHECK (id GLOB '[A-Z]*-W-[0-9][0-9][0-9]' AND length(id) BETWEEN 9 AND 13
                                     AND substr(id, 1, length(id) - 6) NOT GLOB '*[^A-Z0-9]*'),
  project    TEXT NOT NULL REFERENCES projects(code),
  name       TEXT NOT NULL CHECK (length(trim(name)) > 0),
  lead       TEXT,                -- a full name from the people register (BL-55)
  keywords   TEXT,                -- comma-separated
  aliases    TEXT,                -- comma-separated, e.g. "UAT" for Testing
  channel    TEXT,                -- Teams channel, optional
  status     TEXT NOT NULL DEFAULT 'Active' CHECK (status IN ('Active','Closed')),
  created    TEXT NOT NULL CHECK (created GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
  source     TEXT NOT NULL,
  archived   INTEGER NOT NULL DEFAULT 0 CHECK (archived IN (0,1)),   -- BL-09
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE (project, name COLLATE NOCASE)
);

CREATE TABLE IF NOT EXISTS actions (
  id           TEXT PRIMARY KEY CHECK (id GLOB '[A-Z]*-A-[0-9][0-9][0-9]' AND length(id) BETWEEN 9 AND 13 AND substr(id, 1, length(id) - 6) NOT GLOB '*[^A-Z0-9]*'),
  project      TEXT NOT NULL REFERENCES projects(code),
  description  TEXT NOT NULL,
  workstream   TEXT,
  owner        TEXT NOT NULL DEFAULT 'TBC',
  priority     TEXT NOT NULL DEFAULT 'Medium' CHECK (priority IN ('Urgent','High','Medium','Low')),
  due_date     TEXT CHECK (due_date IS NULL OR due_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
  status       TEXT NOT NULL DEFAULT 'Open' CHECK (status IN ('Open','Delayed','Closed','Cancelled')),  -- Delayed counts as open
  raised       TEXT NOT NULL,
  closed       TEXT CHECK (closed IS NULL OR closed >= raised),
  latest_update TEXT,
  client_visible INTEGER NOT NULL DEFAULT 0 CHECK (client_visible IN (0,1)),
  client_message TEXT NOT NULL DEFAULT ('What it is: ' || char(10) || 'What it means for you: ' || char(10) || 'What is being done: '),  -- three headings always present; must be complete when client_visible = 1 (checked by tracker.py)
  milestone    TEXT REFERENCES milestones(id),
  source       TEXT NOT NULL,
  archived     INTEGER NOT NULL DEFAULT 0 CHECK (archived IN (0,1)),   -- BL-09
  updated_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Dates are stored YYYY-MM-DD; the dashboard, documents and messages show DD-MM-YYYY.
-- IDs: actions <CODE>-A-NNN, decisions <CODE>-D-NNN, RAID <CODE>-NNN (type is a field)
CREATE TABLE IF NOT EXISTS raid (
  id           TEXT PRIMARY KEY CHECK (id GLOB '[A-Z]*-[0-9][0-9][0-9]' AND length(id) BETWEEN 7 AND 11 AND substr(id, 1, length(id) - 4) NOT GLOB '*[^A-Z0-9]*'),
  project      TEXT NOT NULL REFERENCES projects(code),
  type         TEXT NOT NULL CHECK (type IN ('Risk','Assumption','Issue','Dependency')),
  workstream   TEXT,
  description  TEXT NOT NULL,
  owner        TEXT NOT NULL DEFAULT 'TBC',
  response_action TEXT,   -- mitigation (risk), resolution (issue), validation (assumption), management (dependency)
  due_date     TEXT CHECK (due_date IS NULL OR due_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),  -- target for the response action
  impact       TEXT CHECK (impact IN ('High','Medium','Low')),
  likelihood   TEXT CHECK (likelihood IN ('High','Medium','Low')),
  priority     TEXT CHECK (priority IN ('Urgent','High','Medium','Low')),   -- calculated from impact and likelihood
  status       TEXT NOT NULL DEFAULT 'Open' CHECK (status IN ('Open','Closed','Cancelled')),
  raised       TEXT NOT NULL,
  closed       TEXT CHECK (closed IS NULL OR closed >= raised),
  client_visible INTEGER NOT NULL DEFAULT 0 CHECK (client_visible IN (0,1)),
  client_message TEXT NOT NULL DEFAULT ('What it is: ' || char(10) || 'What it means for you: ' || char(10) || 'What is being done: '),
  milestone    TEXT REFERENCES milestones(id),
  source       TEXT NOT NULL,
  archived     INTEGER NOT NULL DEFAULT 0 CHECK (archived IN (0,1)),   -- BL-09
  updated_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Decisions (BL-53): a decision can be Pending before it is made. It keeps its D-number when it is made; `made_by` holds who
-- it is asked of while Pending and who made it once Made; `date` is the date it was made, empty while Pending.
CREATE TABLE IF NOT EXISTS decisions (
  id           TEXT PRIMARY KEY CHECK (id GLOB '[A-Z]*-D-[0-9][0-9][0-9]' AND length(id) BETWEEN 9 AND 13 AND substr(id, 1, length(id) - 6) NOT GLOB '*[^A-Z0-9]*'),
  project      TEXT NOT NULL REFERENCES projects(code),
  decision     TEXT NOT NULL,
  made_by      TEXT,
  client_visible INTEGER NOT NULL DEFAULT 0 CHECK (client_visible IN (0,1)),
  client_message TEXT NOT NULL DEFAULT '',   -- plain wording (no headings); required when client_visible = 1 (checked by tracker.py)
  date         TEXT CHECK (date IS NULL OR date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
  status       TEXT NOT NULL DEFAULT 'Made' CHECK (status IN ('Pending','Made','Withdrawn')),
  needed_by    TEXT CHECK (needed_by IS NULL OR needed_by GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
  reasoning    TEXT,
  options      TEXT,
  revisit      TEXT,                         -- a date (YYYY-MM-DD) or a trigger in words ("revisit if adoption falls below 60%")
  replaces     TEXT REFERENCES decisions(id),
  source       TEXT NOT NULL,
  archived     INTEGER NOT NULL DEFAULT 0 CHECK (archived IN (0,1)),   -- BL-09
  updated_at   TEXT NOT NULL DEFAULT (datetime('now')),
  CHECK (status <> 'Made' OR date IS NOT NULL),
  CHECK (replaces IS NULL OR replaces <> id)
);

-- Promises (BL-50): commitments made in passing, lighter than actions (no priority or workstream)
CREATE TABLE IF NOT EXISTS promises (
  id          TEXT PRIMARY KEY CHECK (id GLOB '[A-Z]*-P-[0-9][0-9][0-9]' AND length(id) BETWEEN 9 AND 13 AND substr(id, 1, length(id) - 6) NOT GLOB '*[^A-Z0-9]*'),
  project     TEXT NOT NULL REFERENCES projects(code),
  promised_by TEXT NOT NULL,                 -- full names from the people register (BL-55)
  promised_to TEXT NOT NULL,
  description TEXT NOT NULL,
  due_date    TEXT CHECK (due_date IS NULL OR due_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
  status      TEXT NOT NULL DEFAULT 'Open' CHECK (status IN ('Open','Done','Dropped')),
  raised      TEXT NOT NULL,
  closed      TEXT CHECK (closed IS NULL OR closed >= raised),
  source      TEXT NOT NULL,
  archived    INTEGER NOT NULL DEFAULT 0 CHECK (archived IN (0,1)),   -- BL-09
  updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Links (BL-90 part 2): from_item blocks to_item. Either end is an action, RAID item, milestone, decision or promise,
-- of any project; the IDs are unambiguous by pattern, so there is no table column. tracker.py checks both ends exist.
CREATE TABLE IF NOT EXISTS links (
  from_item   TEXT NOT NULL,                 -- the blocker (e.g. a Dependency)
  to_item     TEXT NOT NULL,                 -- what it blocks
  kind        TEXT NOT NULL DEFAULT 'blocks' CHECK (kind IN ('blocks')),
  source      TEXT NOT NULL,
  created     TEXT NOT NULL DEFAULT (date('now')),
  PRIMARY KEY (from_item, to_item, kind),
  CHECK (from_item <> to_item)
);

-- Labels (BL-94): a managed list. `behaviour` is how the label acts (warn: shown with a warning; exclude: always kept out
-- of client reports); `default_choice` is what the warning card preselects. Sensitive is built in.
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
  item_id    TEXT NOT NULL,                  -- an action, RAID item or decision
  label      TEXT NOT NULL REFERENCES labels(name) ON UPDATE CASCADE,
  added_by   TEXT,
  added_at   TEXT NOT NULL DEFAULT (datetime('now')),
  reason     TEXT,
  suggested  INTEGER NOT NULL DEFAULT 0 CHECK (suggested IN (0,1)),   -- 1 = Claude proposed it
  PRIMARY KEY (item_id, label)
);

CREATE TABLE IF NOT EXISTS updates (
  week_ending  TEXT NOT NULL,
  project      TEXT NOT NULL REFERENCES projects(code),
  health       TEXT NOT NULL CHECK (health IN ('On track','At risk','Off track')),
  summary      TEXT NOT NULL,
  key_changes  TEXT,
  PRIMARY KEY (week_ending, project)
);

-- Every change, from any route, for audit and trends
-- One row per apply, so it can be undone
CREATE TABLE IF NOT EXISTS applies (
  apply_id    INTEGER PRIMARY KEY AUTOINCREMENT,
  at          TEXT NOT NULL DEFAULT (datetime('now')),
  proposals   TEXT NOT NULL,            -- JSON list of proposal files
  file_ops    TEXT,                     -- JSON list of file operations performed
  undone_at   TEXT                      -- set when undone
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
  via        TEXT NOT NULL   -- proposal file name, 'dashboard', 'excel-import', 'cx-edit', 'assistant' or 'undo'
);

-- #241 D: a work item's history (item_history.py; dev/proposals/work-item-history/DESIGN.md). One row per change_log row (never
-- updated_at) and one per rejected update to an existing item, written by tracker.py's log() in the same transaction: the route
-- the change came by, the dashboard's place, the actor and a source reference. Before and after stay in change_log (`change`);
-- this table holds no text of a record or a message: route, place, origin, actor and kind are words from the lists below, and
-- src_ref is one reference (a path, a mail or chat reference, or the proposal's file). `undoes` is the event an undo reverses.
-- Rows written before this table existed have none: item_history.py works their route out from the proposal, as before.
CREATE TABLE IF NOT EXISTS item_events (
  event_id   INTEGER PRIMARY KEY AUTOINCREMENT,
  at         TEXT NOT NULL,
  apply_id   INTEGER REFERENCES applies(apply_id),
  item_id    TEXT NOT NULL,           -- the record's ID; a link's or label's change_log key ("from|to|kind", "item|label")
  change     INTEGER,                 -- the change_log rowid (field, before, after); the `rejected` row for a rejection
  kind       TEXT NOT NULL CHECK (kind IN ('change','reject')),
  route      TEXT NOT NULL CHECK (route IN ('dashboard','review','cx-edit','note','assistant','excel','undo','activity',
                                       'archive','migrate')),
  place      TEXT CHECK (place IS NULL OR place IN ('peek','cell','bulk','menu','board','today','card',
                                                    'dashboard','excel','minutes')),
  origin     TEXT CHECK (origin IS NULL OR origin IN ('sweep','minutes','drafts','report')),
  actor      TEXT NOT NULL CHECK (actor IN ('you','creaite')),
  src_ref    TEXT CHECK (src_ref IS NULL OR (length(src_ref) <= 300 AND instr(src_ref, char(10)) = 0)),
  undoes     INTEGER REFERENCES item_events(event_id)
);
CREATE INDEX IF NOT EXISTS item_events_item ON item_events(item_id);
CREATE INDEX IF NOT EXISTS item_events_change ON item_events(change);
CREATE INDEX IF NOT EXISTS change_log_item ON change_log(item_id);

-- Rejected proposals, so they are not proposed again. BL-133 stage B: the reason given and, for a duplicate, the item it repeats
-- (both optional; a rejection with no reason is stored as before). Extraction reads the reasons as guidance only.
CREATE TABLE IF NOT EXISTS rejected (
  fingerprint  TEXT PRIMARY KEY,  -- hash of project + type + normalised description
  rejected_at  TEXT NOT NULL DEFAULT (datetime('now')),
  via          TEXT,
  reason       TEXT,
  duplicate_of TEXT               -- the item this one repeats (an action, RAID item or decision ID), when the reason is Duplicate
);

-- Full-text search across minutes, transcripts, reports and reference files (a derived index, rebuilt in full by
-- `tracker.py index`; porter stems words so "slip" finds "slipped")
CREATE VIRTUAL TABLE IF NOT EXISTS vault_search USING fts5(path, project, kind, date, content, tokenize = 'porter unicode61');
