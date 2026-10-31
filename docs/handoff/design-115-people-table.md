# Design note: #115 people table (v0.6)

Written by a build agent, 29-10-2026; revised after the reviews of 28-10 and 29-10 (the lead's three HIGH, a reviewer's four MEDIUM and four LOW). **Not built.** The table needs changes to `schema.sql` and `store.py` (and a new route in `server.py`, a new `changes.py` path for the Excel and share carry). None of these is approved in #115, so this note stops at the design. It needs the Head's approval to move to a Full-tier item, and it builds **after #126 and #45**.

## What #115 asks for (the owner, 28-10-2026)
A small first version: a `people` table with name, email, organisation, role and aliases, plus a Needs details flag for a person added without details. Filled by Excel or CSV paste. The Microsoft 365 address-book pick is left for later. Owners stay free text until v0.5. #116 (people from mail headers) follows.

## Table (creaite's style)
```
people(
  id          TEXT PRIMARY KEY  -- P-001, P-002 ... (own counter, never reused)
  name        TEXT NOT NULL CHECK length(trim(name)) > 0
  email       TEXT            -- stored trimmed and lower-cased; unique when not null
  organisation TEXT
  role        TEXT
  aliases     TEXT            -- ";"-separated, like workstreams.aliases
  kind        TEXT NOT NULL DEFAULT 'person' CHECK IN ('person','group')
  needs_details INTEGER NOT NULL DEFAULT 0 CHECK IN (0,1)
  archived    INTEGER NOT NULL DEFAULT 0
  source      TEXT NOT NULL
  updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
)
```
People belong to the portfolio, not one project, so there is no project column. `email` has a unique index on the stored (lower-cased, trimmed) value, so `A@x.example` and `a@x.example` clash; a test proves it.

**ID shape (LOW 1, LOW 4).** `P-001` is a new shape: it needs an entry in `ID_PREFIX`, its own counter (`next_id(con, table, project)` is per project, so people use a portfolio counter, the next number over all `people.id`, and an archived person's number is never reused), the 999 limit, `KEYS`, `REQUIRED_NEW`, `ALLOWED` and the id GLOB check. `people` is not in `DELETED_ON_CANCEL`. Test that the ID scans (doclinks, `ITEM_REF`, the item-ID detail in the log) do not read `P-001` as a work item.

## Owners point at a row
`actions.owner`, `raid.owner`, `milestones.owner`, `workstreams.lead` and `decisions.made_by` are free text today (`TBC` default). Two options:

1. **Keep the text, add an optional `owner_id`** beside it (recommended; a reviewer agrees). The text stays the shown name, so reports, Excel and the existing demo data keep working.
2. Replace the text with a foreign key. Cleaner, but it changes every list, report and export at once. Not recommended in a small release.

### One resolver, in `store.py`
The writer, never the page, resolves a name. Every route that writes owner text goes through the same function: the page's edit, the Excel import (the owner cell), a teammate's changes file (`team` route), the board's drag and ask clark. A save whose text matches **exactly one** person sets `owner_id`; otherwise it keeps the text and sets no `owner_id`.

**Matching (LOW 3).** The normalisation key is NFKC, casefold, collapse whitespace, then `confusables.skeleton` (the repo's reading of text), so accents and look-alike letters are treated as the repo already treats them. Exact match on the key of the name or any alias; no fuzzy matching. `TBC` and blank map to no person. A text that matches two people sets **no** `owner_id` and the save says why in plain words (below): it never guesses. Alias and name uniqueness use the same key, so adding an alias that another person already has is refused.

### A new name never creates a person by itself (MEDIUM 2)
Saving or typing a name that matches no one keeps the text and sets no `owner_id`. Nothing creates a people row as a side effect: not a save, not typing, and not an Excel import (an import can carry hundreds of distinct owner texts, and typos would become junk people). People are made in only three places:
- the People list's Add;
- the import box on the People list (rows pasted there are people rows, checked like any save);
- the owner box, when the person confirms a prompt: **"Add Sam Reed as a new person?"** with the replies **Add person** and **Keep as text**. Add person creates the person with `needs_details = 1` and sets `owner_id`, in the same step as the save; Keep as text changes nothing but the text.

The People list also shows **Not on the people list yet**: the distinct owner texts that match no one, with a count each, and an **Add** beside each, so several can be added in one go. The Excel import of work items only ever sets `owner_id` for an existing person (name or alias match) and reports the unmatched names after it ("3 owner names are not on the people list"); it creates no one.

The **Needs details** flag clears in the same step when a save adds an email (LOW 4 of the first review), so it cannot go stale.

### Migration and backfill
Schema version 3, built on **the same runner as #126's version 2** (HIGH 2): one ordered `MIGRATIONS` table in `open_store`, `{2: …, 3: …}`, walked from the file's version. #126 lands as 2 (`documents.archived`, copy-first through `backup.make`), **#45 lands next if it needs a step**, and #115 is the next entry after both. The note adds **no `open_store` branch of its own**. The runner takes one safety copy before the first step that runs (not one per step), every step is idempotent and re-reads the version after `BEGIN IMMEDIATE`, and `check_copy` accepts any version from 1 to the current. Step 3, in one transaction: `CREATE TABLE IF NOT EXISTS people` first, then five `ALTER TABLE … ADD COLUMN owner_id TEXT REFERENCES people(id)` (a column with a default of NULL is allowed in SQLite; the table exists before the columns point at it).

**Backfill (HIGH 3).** The migration creates no people and sets every `owner_id` to NULL. The existing owner text keeps working exactly as today. Linking happens later, when the owner has filled the People list: the list offers **Link existing items** (a button, one step, with a count shown first), which runs the same resolver over the owner text of every live row: exact match on the key, one match only, `TBC` to none, no fuzzy matching. It is deterministic, repeatable and Undoable. Tests: a version 1 file with data migrates to 3 through 2; a version 2 file migrates to 3; running the step twice changes nothing; an older clark refuses the newer file; the safety copy exists and opens.

## Writers (all in `store.py`, one Undo step each, as the other tables)
- `add_person`, `edit_person`: through the existing `write_item` path, so they land in `applies`, `change_log` and `item_events`. Email is checked (below).
- `rename`: the person row plus the owner text of every **live** row that points at the person, one step. See "Where people changes are made and undone".
- `merge(from, into)`: one step. Repoints the owner text and `owner_id` of live rows, moves the source's aliases (and its name, as an alias) onto the target, the target's email wins on a clash, **clears the source's email before archiving it** (the unique index would refuse otherwise), then archives the source and records the mapping (below).
- `archive` and `restore`: the only way a person leaves the lists (MEDIUM 4, below).
- Import: rows pasted from Excel or CSV go through the same checks as a save, dedupe on email then on name or alias, and are one import step. A refused row is named ("row 7: the email has a space"); the other rows still apply only if the owner confirms the preview.

## People are archived, never deleted (MEDIUM 4; FR-43c)
There is no `delete` for a person. **Archive** and **restore** are the two ways (consistent with #126). A hard removal exists only as the Undo of a person created in the same step (the decided rule for creations). `merge` archives the source, the same call. `people` takes a person-specific `archived` column (above) and is listed among #126's archivable kinds; #126 lands first, so the order is #126, then #115.

What archive means:
- An archived person stays as the owner text on old items; nothing is rewritten and the history keeps the name at the time.
- Archived people are hidden from the owner pickers, the type-ahead and **Not on the people list yet**, and are not matched by new saves (a name that matches only an archived person keeps its text and sets no `owner_id`; the prompt offers **Restore Sam Reed**).
- They are shown on the People list under **Archived**, with a **Restore** button. Restore is one Undoable step and also puts back the email if it is still free (if not, it says so in plain words and restores without it).
- Items already pointing at an archived person keep `owner_id`; an item's owner field shows the text.

## Where people changes are made and undone (MEDIUM 3)
`changes.py` (`UNDOABLE`, `_row_is_ours`) lets an Undo reverse only steps whose rows belong to one project. A rename or merge touches owner text in several projects, so no project's Undo accepts it, and it must not run on a project-scoped route. So:
- People changes (add, edit, rename, merge, archive, restore, import, Link existing items) are made on **portfolio-level routes** (`/api/people/...`), not under a project.
- Each is **one step**, and a step has its own portfolio-level **Undo** on the People list ("Undo last people change"). A project's own Undo never offers a people step; a work-item step made in a project is undone there as today.
- **What Undo does.** Undo of a rename restores the person's name **and** `owner_id` and owner text on every row that step touched, everywhere, in one go. Undo of a merge restores the source person (name, email, aliases, not archived), the target's earlier aliases and email, and the owner text and `owner_id` of every row the step repointed. The step records the exact rows and their earlier values, so Undo puts back values, never recomputes them.
- **Order.** A people step can be undone only while nothing later has touched the same person or rows; otherwise Undo is refused in plain words and names the later step: "Can't undo the rename of Sam Reed: the person was changed again afterwards. Undo that change first." A merge records the mapping (source id to target id, and the rows moved) so an older step on the source (an edit made before the merge) is refused with "Sam Reed was merged into Sam Reid. Undo the merge first." rather than writing to an archived person.
- **A project's Undo and a people step.** If a project edit wrote the owner text that a later rename changed, the project's Undo restores only that item's own fields; if its text now differs from what that step wrote, the Undo says "The owner was renamed after this change. Undo the rename first." and changes nothing.
- The toast after a rename or merge says what happened and how many rows: "Renamed to Sam Reid on 14 items in 3 projects. Undo." Counts include only live rows.
- **Archived projects and archived rows (first review, MEDIUM 2).** `_project_exists` refuses writes to an archived project and #126 makes archived rows read-only. A rename or merge updates **live rows only** and leaves archived rows' text as it was; the history shows the name at the time. The step's toast counts live rows and, when there are archived ones, adds "(and left 6 archived items as they were)". Test: a person who owns an item in an archived project is renamed; the live rows change, the archived one does not, and the step is one Undo.

## Rules and checks
- **Email (MEDIUM 1).** One strict single-address rule, in `store.py`, **shared with the Draft email builder (#50)**, which takes its To line and `mailto:` link from this table and must call the same function, not its own check. The rule: the value is trimmed then lower-cased; **exactly one address**; no space, `,` `;` `<` `>` `(` `)` `[` `]` `"` `'` `\` `?` `#` `%` or backtick; no control character and no invisible or bidirectional-control character (including zero-width and the bidi marks); exactly one `@`; a non-empty local part (at most 64 characters); a domain that has a dot, no empty label, no leading or trailing dot or hyphen on a label; the whole address at most 254 characters. `a,b@x.example`, `a@x.example;b@x.example`, `Sam <a@x.example>` and `a@x` are all refused. Blank is allowed (that is what Needs details is for). A duplicate is refused with the existing person named. A pasted CSV or Excel row goes through the same check and a refused email says which row. Tests: each of the above refused; a Draft email test that a person with a stored address can never produce a To line with two recipients.
- A group (`kind = 'group'`) may own items (a team owns the action), but is never counted as a person. Agreed (a reviewer LOW 3; the lead's earlier lean to "people only, groups later" is dropped by the Head's agreement; to be confirmed in question 2).
- No real names in tests, fixtures or demo data (RULES); use the fictional demo people.

## Personal data stays in (MEDIUM 5 of the first review; LOW 2)
`people` holds email addresses.
- `people`, `email` and `owner_id` are in **no** publish whitelist (`PUBLISH_FIELDS`); `owner_id` is added to `NEVER_PUBLISH`; `publish_inputs` and `publish.select` never read the table, and are untouched. A published file and the client copy hold the owner's name as typed and no email, organisation or id. Test: plant an email, an organisation and an `owner_id` and find none of them anywhere in a publish or the client file.
- The People sheet is in the **internal** Excel export only. It passes every cell through `escape_text` (a name of `=HYPERLINK(...)` is text) and has the same row limits as the other sheets. A People sheet is never in a client copy.
- A teammate's changes file may **not** create or edit people unless FR-99b's list is widened (today it names work items, milestones, use cases, current state, health reason, text sections, new items and comments, not people). Decision for the Head (question 4); this note assumes **not widened**: people changes arrive by the People list only, and an owner name in a teammate's file goes through the resolver and sets `owner_id` for an existing person, nothing more.
- The safety copies and the team share carry the whole database, so they carry the people table. The note for the owner should say so.

## Page and share
- A People list under Settings (name, email, organisation, role, aliases, Needs details badge, count of owned items), with add, edit, merge, archive and restore, Link existing items, **Not on the people list yet**, Undo last people change, and an import box (paste CSV or tab-separated text, shown before applying).
- Owner fields become a type-ahead on the live people (not archived), with the prompt "Add Sam Reed as a new person?" when the typed name matches no one and the person leaves the box; Keep as text keeps the text.
- The team share (`portability-and-sharing.md`) and the internal Excel export carry a People sheet as above.

## Plain-words messages
- Add prompt: "Add Sam Reed as a new person?" Replies: **Add person**, **Keep as text**.
- Two matches: "Sam matches two people (Sam Reed, Sam Reid). The owner was kept as text. Pick one to link it."
- Email refused: "That email can't be used: it holds more than one address or a character that isn't allowed." With a row: "Row 7: that email holds more than one address."
- Duplicate email: "That email already belongs to Sam Reed."
- Rename toast: "Renamed to Sam Reid on 14 items in 3 projects. Undo."
- Merge toast: "Merged Sam Reed into Sam Reid. 14 items now show Sam Reid. Undo."
- Archive: "Sam Reed archived. Old items keep the name. Restore from the Archived list."
- Undo refused: "Can't undo the rename of Sam Reed: the person was changed again afterwards. Undo that change first."
- Import summary: "3 owner names are not on the people list."

## Test list
`test_people_store.py`: table and index shape; the email rule (valid, each refusal, case clash, a merge frees the source's email first); the resolver (exact, alias, accent and look-alike, two matches sets none and says why, `TBC` none, archived person not matched); no person made by a save, by typing or by an import of work items; the prompt path creates one with `needs_details = 1` and the flag clears when an email is added; rename (live rows change, an archived-project row does not, one step); merge (repoints, mapping recorded, one step); archive and restore (no delete route, a hard removal only as the Undo of a creation); Undo of rename and merge restores `owner_id` and text everywhere; Undo refused in plain words after a later change, after a merge and after a later rename; the `P-` counter never reuses; ID scans ignore `P-001`. `test_people_migrate.py`: v1 with data to 3 through 2, v2 to 3, idempotent, older clark refuses a newer file, one safety copy, backfill is NULL then Link existing items sets only exact single matches. `test_people_import.py`: row-level refusals, preview, one import step and Undo. `test_people_privacy.py`: planted email, organisation and `owner_id` absent from a publish and the client file; People sheet only in the internal export, `escape_text` on every cell; a teammate's file cannot create or edit people. Page test: type-ahead, the prompt, Not on the people list yet, Archived list.

## Order of commits (after #126 and #45)
1. Migration step 3 as the next entry in #126's `MIGRATIONS` table (after #126's 2 and #45's step if any): `people`, the five `owner_id` columns, the version bump, its tests.
2. `store.py`: the ID shape and counter, the email rule (shared with #50), the resolver, `add_person` and `edit_person`, with tests.
3. `store.py`: rename, merge, archive and restore, the mapping, Undo and its refusals, with tests.
4. `server.py` and `changes.py`: the portfolio-level people routes and Undo, the Excel and share carry, the privacy guards, with tests.
5. Page (Normal item): the People list, type-ahead, the add prompt, Not on the people list yet, Link existing items.

## Files touched when approved
`src/clark/schema.sql` (table, `owner_id` columns, schema version 3), `store.py` (writers, checks, resolver, `data_for` adds `people`), `server.py` (people routes), `changes.py` (the portfolio-level Undo, the team and Excel carry), `publish.py` (the never-publish check only), page source under `src/clark/page/src/`, and the tests above. Estimate: one Full-tier item for store, schema and routes; one Normal item for the page.

## Questions for the Head
1. Approve option 1 (text plus `owner_id`, set only by the writer's resolver)? Reply **yes** or **no**.
2. May groups own items? Recommended **yes** (as agreed), never counted as people.
3. Approve the guarded changes in `schema.sql`, `store.py`, `server.py`, `changes.py` and the never-publish check in `publish.py` as a Full-tier item for the builder, as version 3 after #126 and #45? Reply **yes** or **no**.
4. May a teammate's changes file create or edit people? Recommended **no** (FR-99b's list stays as it is).
5. Confirm the Undo rule: people changes have their own portfolio-level Undo, and a project's Undo refuses, in plain words, a change a later rename touched. Reply **yes** or **no**.
