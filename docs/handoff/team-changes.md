# Team sharing: one shared location, a share-only master, and changes files

**On hold (the owner, 28-10-2026, #61):** "Low priority for now... come back to it". Nothing here is in v0.1 or v0.2. The changes inbox is still built once, for client comments first.

Written by a teammate, 28-10-2026, from the owner's words: "On the shared option... we'll need an option for each user to be able to 'export' a db file to share with me and then an option for me to be able to import it and it updates / syncs the changes to the master db (mine) before publish. Include option to import multiple".

Revised the same day with the owner's journey: "for team sharing clark should check on open to se if there is an updated master db available - stored in onedrive but not updated, a share only copy - users should be prompted on opening clark whether they want to update the database. … Single location on sharepoint for master db and extracts and app polls / manages".

This is the multi-user path in `portability-and-sharing.md` (option C), now with the owner's shape. It's a low-priority backlog item, after the single-user MVP. Proposal: the project lead and the owner decide the open points.

## The journey (the owner's five steps)
1. **A teammate opens clark.** clark checks the shared location for a newer master. If there is one, it asks: "A newer master from the owner is available (28-10-2026 14:05). Update now, or later?"
2. **The teammate edits** as normal, in their own local copy.
3. **Their changes are shared:** "Share my changes" exports a changes file into the shared location. With **auto-share** on, clark also does this on close and every 15 minutes when there's something new.
4. **The owner imports.** The owner's clark watches the same location, shows "3 changes files waiting from Sam and Priya", and imports one or many through the review (below). Publish also warns when files are waiting.
5. **The owner shares the master.** After each import, and on close if the owner has edited, clark writes a new **share-only copy** of the master into the location. The other teammates are offered it the next time they open clark (step 1).

**One location** on SharePoint, synced by OneDrive, holds the master copies and the changes files. clark polls it and manages it; nobody moves files by hand.

## The shared location
```
<team share>/                    one SharePoint folder, synced to each machine by OneDrive
  master/
    latest.json                  which copy is current: its number, time, SHA-256 and the changes files it includes
    master-0007.clarkmaster      the share-only copies, numbered; the last 5 are kept
  changes/
    <name>-<device>-<time>.clarkchanges   one file per export; each teammate only ever writes their own
```
- **Nobody ever opens the master in place.** A share-only copy is a finished snapshot made with SQLite's backup API. It holds only the shared projects. Owner-only data is stripped out: source folders, publish and client folders, settings and keys (keys are never in the database anyway). It's written under a temporary name and renamed, and `latest.json` is written last. OneDrive therefore only ever uploads finished files, and the real `clark.db` never sits in OneDrive (`portability-and-sharing.md`).
- **No two people write the same file.** Only the owner's clark writes in `master/`. Each teammate writes only their own uniquely named files in `changes/`. So OneDrive never makes a conflict copy.
- **SharePoint permissions do the guarding:** the owner can edit `master/`, teammates can only read it, and everyone can add to `changes/`. That's a folder setting in SharePoint, made once at setup (an IT or owner step). clark checks it and warns if a teammate can write to `master/`.
- **clark checks a copy before using it:**
  - The SHA-256 must match `latest.json`, so a file still syncing (or an online-only placeholder) is "not ready yet, try later", never half-loaded.
  - The master id is the team's, and the number is higher than the teammate's current copy.
  - The schema version matches.
  - It's opened read-only with `trusted_schema` off, and passes an integrity check, before being copied into the teammate's own data folder.
- **Signing:** a real signature (owner's private key, teammates verify) would stop a forged master even with wrong folder permissions. Python's standard library has no public-key signing, so it's left for later. **Open point 5.**

## Updating, without losing a teammate's work
The prompt in step 1 must never throw away edits. When a teammate presses **Update now**:
1. **Anything not yet shared is exported first,** into `changes/`.
2. **clark checks which of their changes files the new master already includes** (`latest.json` lists them).
3. **The new copy replaces the local one.**
4. **Their changes the owner hasn't imported yet are put back on top,** locally, so they still see their own edits. Those changes are already in a file waiting for the owner, who still decides. They aren't exported again.
5. **A short note says what happened:** "Updated to the owner's master of 28-10 14:05. 2 of your changes are still waiting for the owner, and are kept."

- **Later** keeps the current copy. The teammate's changes still merge, because every changes file carries the copy it started from.
- If a newer master arrives while clark is open, a quiet banner offers it. clark never updates by itself.

## Roles and joining
- **Owner:** the person whose `clark.db` is the master (its `db_id` is the team's). There's one owner per team share, and only the owner publishes.
- **Joining:** Settings › Team › "Join a team share" picks the synced folder and loads the current master copy. That replaces the separate starting-copy file in the first version of this note.
- **Moving ownership** (the owner leaves) is a later step. **Open point 6.**

## Why a changes file and not the whole database
The owner said "a db file", and the user sees it as one: a single `.clarkchanges` file. Underneath, it holds **only the teammate's steps** (each field's value before and after, who, when), not a copy of the whole database. This matters for three reasons:
- **Merging needs the before value.** With it, clark can tell "they changed it and I didn't" (apply) from "we both changed it" (clash). Comparing two whole databases can't tell those apart, so it would quietly overwrite the owner's newer edits.
- **Safer to read.** A file from someone else is outside input. A plain JSON file (zipped, with its own checksum) can only hold the fields clark allows. A SQLite file can carry triggers, views and malformed pages, and opening one safely needs more defences.
- **Smaller and private.** The file carries only what the teammate touched, not every project in their copy.

*If the owner wants a real database file anyway,* the same content can be written as a small SQLite file, opened read-only with `trusted_schema` off and an integrity check first. The merge is the same either way. **Open point 1.**

## The two files
| File | Made by | Holds |
|---|---|---|
| **Share-only master copy** (`master/master-NNNN.clarkmaster`) | The owner's clark: after each import, on close after edits, or Share › "Share master now" | The shared projects' rows, the master's id (`meta.db_id`), its number and last step (the **base**), and the changes files it includes |
| **Changes file** (`<project>-<name>-<date>-<time>.clarkchanges`) | The teammate: "Export my changes" | The master id and base it came from, the teammate's name as set in their clark and their device id, then each step since the base. A step is its time, and for every field: table, item id, field, value before and value after. Plus the file's SHA-256 |

A teammate can export as often as they like. Each export holds only the steps since their last export, so nothing is sent twice. clark also refuses a file it has already imported (by SHA-256).

## Import, one file or many
1. **Pick:** Import changes takes several files at once, or "everything waiting" in the team share's `changes/` folder.
2. **Check each file before anything is staged:**
   - It names this master (`db_id`), its schema version matches, and its checksum is right.
   - It is under the size limit and wasn't imported before.
   - Every table and field is on the allowed list (below), and every value passes the same checks as a typed change (creaite's `check_row` rules).
   - A file that fails any check is refused whole, with the reason, and the other files go on.
3. **Line up:** all steps from all chosen files are put in time order and compared with the master, field by field:
   - **Applies cleanly:** the master's value is still the teammate's "before". They changed it and the owner didn't.
   - **Already the same:** the master already has the teammate's "after". Nothing to do.
   - **Clash with the owner:** the master's value has changed since the base. clark shows the starting value, the owner's value now and the teammate's value, and the owner picks one.
   - **Clash between teammates:** two files change the same field differently. Both are shown, with names and times, and the owner picks one.
   - Rich text (current state, standing, text sections) is chosen whole. clark doesn't mix two versions of a paragraph.
4. **Review screen:** grouped by teammate, then by item, with counts (clean, same, clashes). Actions: **Accept all clean**, accept or reject each change, and pick a side for each clash. Nothing changes until the owner presses Apply.
5. **Apply:** one step per file (an `applies` row with the teammate's name in `by_user` and the route `team`). So each import shows in history under the person who made it, and the toast's Undo, or history, can reverse one teammate's import on its own (creaite's undo rules, including skipping a row changed since).
6. **After Apply,** Excel is refreshed as for any accepted change. clark writes a new share-only master copy into `master/`, so the other teammates are offered it the next time they open clark.

## New items made by a teammate
IDs are creaite's `<CODE>-A-NNN`, handed out in order, so two people adding items offline would both make `DEMO-A-042`.
- On import, **every item a teammate created gets the next free id in the master.** Every reference to it in the same file is rewritten too (a milestone link, a use case, a label, a "blocks" link).
- The review screen shows "new: DEMO-A-042 (was DEMO-A-040 on Sam's copy)". The import result lists the mapping, and the next master copy carries the new ids. When the teammate updates, their local item is replaced by the renumbered one.
- Deleting is archiving, as in creaite (`archived = 1`), so it merges like any other field change.

## What a teammate may change (allowed list)
- **Proposed:** every field of actions, RAID items, decisions, milestones and use cases, the project's current state and health reason, and text sections. New items of those kinds are allowed, and so are comments.
- **Never imported:** settings, keys, source folders, publish folders, the client folder, publications, the client flag (`client_visible`) and what is hidden from the published page, report layout, and anything in a project the master copy didn't include.
- *Why the client flag and hiding stay with the owner:* those decide what reaches a client. A teammate's file must not be able to put a row in front of a client.
- The list is set per project in Settings, with this as the default. **Open point 2.**

## Before publish
- The Publish dialog shows "3 changes files are waiting from Sam and Priya" when the team share's `changes/` folder has files for this project not yet imported, with an **Import first** button. It never imports by itself.
- Publishing with files still waiting is allowed, after the owner confirms. The send log records that some were waiting.

## Same machinery as client edits
Client edits (`client-edits.md`, option A) already need almost all of this: a changes file, outside input checked against an allowed list, staging, the three-value clash view, accepting, and refusing a file seen before. **Build it once** as a "changes inbox" with two sources:

| | Team changes | Client comments |
|---|---|---|
| Made in | the teammate's own clark | the published page |
| Starts from | a share-only master copy (master id and base) | a published file (its SHA-256) |
| Allowed list | wide (above) | comments only, on published work items and use cases (the owner, #21 and #22). Any other field refuses the file |
| New items | yes, renumbered on import | no |
| Who | the name in their clark, as entered | the name the client typed, as entered |

## Schema (added to `data-model.md`)
- `meta`: `db_id` (a random id made when the master is created), and on a teammate's copy `base_db_id` and `base_apply_id`.
- `change_files`: one row per changes file read, for both sources. Columns: `sha256` (key), `source` (`team` or `client`), `project`, `from_name`, `device`, `base` (master base or report SHA-256), `read_at`, `refused`, `apply_id`. This replaces `client_files`.
- `staged_changes`: one row per field change, for both sources. Columns: `file`, `item_id`, `field`, `before`, `after`, `master_now`, `state` (`clean`, `same`, `clash`, `accepted`, `rejected`), `new_id` (for renumbered items), `decided_at`. This replaces `client_changes`.
- `item_events.route` gains `team`.

## Done when (for the build item)
- **On open:** with a newer master in the location, the teammate is asked once, and Later keeps their copy. A copy still syncing, a wrong SHA-256, a wrong master id, an older number or a different schema is never loaded, and each case is tested.
- **Update keeps work:** with unshared edits and edits not yet imported, Update exports first, replaces the copy, and puts the not-yet-imported changes back on top. Nothing is lost, and nothing is exported twice.
- **Share-only copy:** it holds only the shared projects, with no source, publish or client folders, and it's written as a finished file before `latest.json`.
- **Auto-share and polling:** auto-share exports on close and every 15 minutes only when there's something new. The owner's clark lists waiting files within a few minutes, and never imports by itself.
- **No two writers:** a test runs owner and teammate clarks against one folder, and no file is written by both.
- **Export:** it writes only steps since the last export, and an export with nothing new says so instead of writing a file.
- **Import of one file:**
  - Clean changes apply, already-the-same changes are skipped, and clashes wait for a choice.
  - A refused file names the reason. A file seen before is refused.
  - Every check is tested with one bad file per rule: wrong master, wrong schema, bad checksum, too large, a field not on the list, a bad value, a different project.
- **Import of several files:**
  - Three test files from two teammates (one clash between them, one with the owner) give the right review.
  - Applying gives one step per file, and undoing one file's step leaves the others in place.
- **New items:** two teammates each add an item offline. Both get distinct master ids, and their links are rewritten.
- **Before publish:** the dialog shows waiting files and never imports by itself.
- **Nothing reaches a client** through a teammate: a test file that sets `client_visible` or a hidden flag is refused.
- **Review:** Full, because it takes outside input into the master.

## Open (for the owner)
1. **File type:** a changes file in JSON (recommended), or a real SQLite file. The user sees one file either way.
2. **Allowed list:** confirm a teammate may change every work item, milestone and use case field and add items, but never the client flag, what is hidden, or settings.
3. **When:** after the single-user MVP (recommended, as you said: "start with single user for mvp/beta"), or pulled into the beta.
4. **Team folder: decided** ("Single location on sharepoint for master db and extracts and app polls / manages"). One location for the whole team share, not one per project.
5. **Signing master copies:** rely on SharePoint folder permissions plus clark's checks for now (recommended), or add a signature later.
6. **When the owner changes:** later. For now there's one owner, and moving the master is done by hand with help.
7. **Auto-share default:** on (recommended, so the owner sees changes without asking), or off with a reminder on close.
