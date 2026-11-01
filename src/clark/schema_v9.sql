-- clark's database, the people table (#115): the statements migrate_people runs, FROZEN. It is the step that takes a file to the version
-- the owner rules for #115 (8 at the time of writing); the number is set where the step is put in MIGRATIONS, not here.
-- Never edit this file for a later version: add a later migration step instead. Design: docs/handoff/design-115-people-table.md.
-- People belong to the portfolio, not one project, so there is no project column. A person is archived, never deleted.

CREATE TABLE IF NOT EXISTS people (
  id            TEXT PRIMARY KEY CHECK (id GLOB 'P-[0-9][0-9][0-9]'),
  name          TEXT NOT NULL CHECK (length(trim(name)) > 0),
  email         TEXT CHECK (email IS NULL OR (email = lower(trim(email)) AND length(email) BETWEEN 3 AND 254)),   -- stored trimmed and lower-cased; unique when set
  organisation  TEXT,
  role          TEXT,
  label         TEXT CHECK (label IS NULL OR length(label) <= 30),          -- shown after the name when two people share it; never matched on
  aliases       TEXT,                                                       -- ';'-separated, like workstreams.aliases
  kind          TEXT NOT NULL DEFAULT 'person' CHECK (kind IN ('person','group')),
  needs_details INTEGER NOT NULL DEFAULT 0 CHECK (needs_details IN (0,1)),
  archived      INTEGER NOT NULL DEFAULT 0 CHECK (archived IN (0,1)),
  source        TEXT NOT NULL,
  updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE UNIQUE INDEX IF NOT EXISTS people_email ON people(email) WHERE email IS NOT NULL;
