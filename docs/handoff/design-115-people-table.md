# Design note: #115 people table (v0.5)

Written by a build agent, 29-10-2026. **Not built.** The table needs changes to `schema.sql` and `store.py` (and a new route in `server.py`, a new `changes.py` path for the Excel and share carry). None of these is approved in #115, so this note stops at the design. It needs the Head's approval to move to a Full-tier item.

## What #115 asks for (the owner, 28-10-2026)
A small first version: a `people` table with name, email, organisation, role and aliases, plus a Needs details flag for a person typed in on the fly. Filled by Excel or CSV paste. The Microsoft 365 address-book pick is left for later. Owners stay free text until v0.5. #116 (people from mail headers) follows.

## Table (creaite's style)
```
people(
  id          TEXT PRIMARY KEY  -- P-001, P-002 ... (next_id, never reused)
  name        TEXT NOT NULL CHECK length(trim(name)) > 0
  email       TEXT            -- lower case; UNIQUE when not null
  organisation TEXT
  role        TEXT
  aliases     TEXT            -- ";"-separated, like workstreams.aliases
  kind        TEXT NOT NULL DEFAULT 'person' CHECK IN ('person','group')   -- groups and lists stay apart from individuals
  needs_details INTEGER NOT NULL DEFAULT 0 CHECK IN (0,1)
  archived    INTEGER NOT NULL DEFAULT 0
  source      TEXT NOT NULL
  updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
)
```
People belong to the portfolio, not one project, so there is no project column.

## Owners point at a row
`actions.owner`, `raid.owner`, `milestones.owner`, `workstreams.lead` and `decisions.made_by` are free text today (`TBC` default). Two options:

1. **Keep the text, add an optional `owner_id`** beside it (recommended for v0.5). The text stays the shown name, so reports, Excel and the existing demo data keep working. A save with a name that matches a person's name or alias (case-insensitive, one match) sets `owner_id`; a new name creates a person with `needs_details = 1`. Rename writes the new name into every row that points at the person, in the same step.
2. Replace the text with a foreign key. Cleaner, but it changes every list, report and export at once. Not recommended in a small release.

## Writers (all in `store.py`, one Undo step each, as the other tables)
- `add_person`, `edit_person`: through the existing `write_item` path, so they land in `applies`, `change_log` and `item_events`.
- `rename`: person row plus every pointing owner text, one step.
- `merge(from, into)`: repoints owners, moves the source's email and aliases onto the target (the target's wins on a clash), archives the source. One step.
- `delete`: only when nothing points at the person; otherwise the answer is "merge or archive". One step.
- Import: rows pasted from Excel or CSV go through the same check as a save, dedupe on email then on name or alias, and are one import step (the route `excel` already exists in `change_log`).

## Rules and checks
- Email: one `@`, no spaces, lower-cased; blank allowed (that is what Needs details is for). Duplicate email is refused with the existing person named.
- A group (`kind = 'group'`) can own nothing a person owns? Decision for the Head: allow as owner (a team owns the action) but never count it as a person. Recommended: allow.
- No real names in tests, fixtures or demo data (RULES); use the fictional demo people.

## Page and share
- A People list under Settings (name, email, organisation, role, aliases, Needs details badge, count of owned items), with add, edit, merge, archive and an import box (paste CSV or tab-separated text, shown before applying).
- Owner fields become a type-ahead on the people list, with "Add as new person" keeping the typed text.
- The team share (`portability-and-sharing.md`) and the Excel export carry a People sheet; teammates' changes to people arrive as ordinary `team` route changes.

## Files touched when approved
`src/clark/schema.sql` (table, `owner_id` columns, schema version bump), `store.py` (writers, checks, `data_for` adds `people`), `server.py` (people routes), `changes.py` (the team and Excel carry), page source under `src/clark/page/src/`, and tests: `test_people_store.py`, `test_people_import.py`, page test. Estimate: one Full-tier item for store, schema and routes; one Normal item for the page.

## Questions for the Head
1. Approve option 1 (text plus `owner_id`)?
2. May groups own items (above)?
3. Approve the guarded changes in `schema.sql`, `store.py`, `server.py` and `changes.py` as a Full-tier item for the builder, with a schema version bump and a migration for existing databases?
