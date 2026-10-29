-- clark's database, schema version 2: the tables migrate_to_2 makes, FROZEN. Version 2 is what these statements say, whatever a later
-- version does to schema.sql. Never edit this file for a later version: add a later migration step instead.
-- (Only the tables a version-1 file may lack, plus item_events with the 'board' place, which the step makes again.)

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
