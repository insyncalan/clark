-- clark's database, the settings step (#47): the statements migrate_settings runs, FROZEN. It is the step that takes a file to
-- version 3 (the next free number after #126's 2 on main). PR #206 (#120) also proposes a step 3: whichever lands second takes
-- the next number at merge (renumber its file and its MIGRATIONS entry, then set SCHEMA_VERSION to the last).
-- Never edit this file for a later version: add a later migration step instead.
--
-- app_settings: one row for this computer, never more. It holds the choices that are a promise about THIS computer, whichever
-- project is open. ask_enabled is the safety switch for asking: 1 is on (the starting value), 0 is off, and nothing is sent to
-- Claude while it is off. The row is made here, so the writer only ever changes it.

CREATE TABLE IF NOT EXISTS app_settings (
  id          INTEGER PRIMARY KEY CHECK (id = 1),
  ask_enabled INTEGER NOT NULL DEFAULT 1 CHECK (ask_enabled IN (0,1)),
  updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

INSERT OR IGNORE INTO app_settings (id) VALUES (1);
