-- clark's database, a use case can be Done (#412): the use_cases table migrate_use_case_done makes, FROZEN. The step number
-- is set where the step is put in MIGRATIONS, not here. Never edit this file for a later version: add a later migration step.
-- It is schema.sql's use_cases as it is today, with 'Done' in the status CHECK (tests pin the two together while this is the
-- newest use_cases).

CREATE TABLE IF NOT EXISTS use_cases (
  id            TEXT PRIMARY KEY CHECK (id GLOB '[A-Z]*-U-[0-9][0-9][0-9]' AND length(id) BETWEEN 9 AND 13 AND substr(id, 1, length(id) - 6) NOT GLOB '*[^A-Z0-9]*'),
  project       TEXT NOT NULL REFERENCES projects(code),
  ref           TEXT NOT NULL DEFAULT '',     -- the project's own reference as shown, e.g. "1.1" or "1.3 and 1.7"
  title         TEXT NOT NULL,
  status        TEXT NOT NULL CHECK (status IN ('On track','Flag','High risk','Done')),
  headline      TEXT NOT NULL DEFAULT '',
  standing      TEXT NOT NULL DEFAULT '',     -- HTML
  sort_order    INTEGER NOT NULL DEFAULT 0,
  client_visible INTEGER NOT NULL DEFAULT 1 CHECK (client_visible IN (0,1)),
  source        TEXT NOT NULL,
  archived      INTEGER NOT NULL DEFAULT 0 CHECK (archived IN (0,1)),
  updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
);
