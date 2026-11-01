# Design note: the database migration framework (guarded)

How clark brings an older database up to date when an update changes the data layout, and how the update's undo puts it back.
Review: Full (two readers, and the owner approves the exact change to the store). This note was written before the build and
updated with the rulings and with what was built.

## What existed before

Most of a runner was already on main:
- `SCHEMA_VERSION = 2` and `MIGRATIONS = ((2, migrate_to_2),)`: a version number, then the step that brings a file *to* it.
- `migration_plan(version)` refuses a table with a gap or a wrong end, a version below 1 and a version above `SCHEMA_VERSION`.
- `migrate(con)` turns foreign keys off, takes one `BEGIN IMMEDIATE`, reads the version again once the lock is held (so a
  second window does nothing), runs every step in order, writes the version after each, compares foreign-key problems before
  and after (only a *new* one refuses) and rolls everything back on any error.
- Opening a database checked the plan, took a safety copy (`backup.make(..., "migrate")`), then migrated.
- `migrate_to_2` reads a frozen copy of version 2's tables (`schema_v2.sql`), never the live `schema.sql`.

Two branches add steps (publications as 3, the Word route as 5; people is 4). One of them carried a second runner of its own,
which refused on *any* foreign-key row and rebuilt a table from the live `schema.sql`. The update-from-Settings build refuses any
release whose data layout differs from the installed one ("install it by hand").

## What the framework guarantees

1. **Refuses gaps.** The table runs 2, 3, 4 ... with no hole and ends at `SCHEMA_VERSION`. Checked before anything is touched;
   a refusal makes no copy.
2. **All or nothing.** All pending steps in one transaction, the version written after each step, one commit at the end. Any
   failure rolls the lot back: "The database could not be updated. Nothing was changed." No step number is shown.
3. **Backup first.** The copy is taken, in the `migrate` family with its own retention, before the first step; if it cannot be
   made, nothing runs. One function does plan, copy and migrate, so no caller can migrate without the copy.
4. **Never loses data.** A rebuilt table copies by column name and keeps ids and sequences. A step adds or reshapes; it never
   drops a column or table that holds a person's data (the one allowed `DROP` is the old copy of a table the same step rebuilt).
5. **Idempotent.** A step run twice, or on a file that already has its change, changes nothing.
6. **Forward only.** No down steps. A newer file is refused: "This data needs a newer clark." Nothing is changed and no copy is
   made. Going back is a restore of the copy.
7. **Frozen steps.** A step never reads the live `schema.sql`. If it needs table definitions it carries its own frozen file.
8. **Same file, either way.** A brought-up file and a new file have the same tables, columns, indexes and keys.
9. **Undo after a migration.** The old app cannot open newer data, so the update's undo restores the copy from guarantee 3,
   after saying "Changes made since the update will be lost."
10. **Plain words.** Every refusal says what happened, whether anything was changed, and what to do next. No SQLite text.

## Rulings on the open questions

1. *One transaction for all the steps, or one per step?* One around the whole run; the version is written after each step
   inside it. Per-step commits would leave a file part way, which the old app cannot open either.
2. *Which foreign-key problems refuse?* Only a new one, counted by table, parent and key (not by row, which a rebuilt table
   renumbers). A row that was already wrong never blocks an update.
3. *In what order do new steps land?* In number order, 3, 4, then 5; a step that lands late never takes a lower number. A
   branch that carried its own runner drops it and uses this one.
4. *How long is the copy kept?* Until the next update has succeeded, and at least 14 days. Nothing is deleted; we archive.
5. *Where is the update's undo record kept?* Beside the installed-files record, never in the database (a restore must not
   depend on the file it restores).
6. *Table definitions for a rebuilding step: inline or a file?* A frozen file per step, pinned by a test.
7. *Where are the numbers claimed?* The table in `store.py` is the one list of numbers; no separate list.
8. *Split the work?* Yes: (a) the store and the chain test first; (b) the update side once the update-from-Settings build is
   on main. Removing that build's "install it by hand" refusal is its own last commit, so it can be reverted alone.
9. *Lowest SQLite?* State the lowest the code is written for and test on both Pythons; no new minimum is enforced.

Safety conditions from the infrastructure read, all kept:
- No `executescript` (or `COMMIT`, `ROLLBACK`, `BEGIN`) in a step: it ends the open transaction half way through a chain. A
  test reads every step and every store function it calls for them, and the runner stops a step that ended the transaction and
  says the file may be part way (never "nothing was changed").
- The foreign-key comparison stays keyed by table, parent and key; a test rebuilds a table with renumbered rows.
- The undo restore is atomic and keeps the newer file: the copy is written beside the database and checked, the newer database
  is copied and moved aside (never deleted), then the copy is moved into place. It runs before the older app starts and is
  refused while the database is open in a running clark.
- A static test rejects SQL newer than the stated lowest SQLite: window functions, `DROP COLUMN`, `RETURNING`, `STRICT`
  tables, generated columns, `RENAME COLUMN`, `NULLS FIRST` or `LAST`, the JSON arrows, `iif()` and `unixepoch()`.

## What was built in part (a)

- `store.bring_up_to_date(con, path, onedrive_roots)`: reads the version, refuses a newer file (`NEWER_DATA`), checks the plan,
  takes the copy, migrates, and returns the copy's path (None when already up to date). `open_store` calls it and keeps the
  path on the store as `migration_backup`, for the update's undo record.
- `store.migrate`: stops a step that ended the transaction (`MIGRATE_PART_WAY`), and rolls back only an open transaction.
- `store.MIN_SQLITE = (3, 24, 0)`: stated, not enforced.
- `backup.restore_before_update(path, name, confirmed=...)`: takes only a `migrate` copy, refuses when it has gone, changes
  nothing until confirmed (it says the changes since the update will be lost), then restores through `restore_path`.
- `tests/test_migration_chain.py`: the chain through every real step, every start, a failure at every step after partial
  writes, a full disk, a read-only folder, running twice, the same shape as a new file, a newer file, gaps, a step that
  commits, old and new dangling rows, the undo reading the same rows and keeping the newer file, and the static checks.

## Left for part (b), the update side

- Record the copy's name, the version before and after, beside the installed-files record.
- "Undo update" puts the old files back, then, if a migration ran, calls `restore_before_update` after the person says yes;
  if the copy has gone, the undo of the data is refused rather than leave old code on a newer file. If no migration ran, the
  database is not touched.
- Remove the "install it by hand" refusal last, in its own commit, once the chain test and the first real migration are on
  main.
- Keep the migrate copy at least 14 days whatever the backups setting says (today retention keeps the newest of each family by
  count, never by the clock).

## Files that are guarded (Full tier)

`src/clark/store.py` (the runner, the table, the entry point, `SCHEMA_VERSION`), `src/clark/schema.sql` and every frozen
`schema_vN.sql`, `src/clark/backup.py` (the restore entry point), and later the update code and `VERSION`. The one-writer guard
test is read, never edited, and passes unchanged.
