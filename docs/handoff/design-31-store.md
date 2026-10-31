# Design note: #31 Schema and the one writer (guarded)

Written by a teammate, 28-10-2026. Required before the build (`Team/01`): what is copied from creaite, what is cut, the changed lines in outline, and the tests that pin it. The source is creaite release tag **v2.6.9 (`db5adb2`)** only, read from a copy of the tag; nothing in creaite is edited. Review: **Full, two independent reviewers**, never the builder. The owner approves the exact copy.

## What creaite has (v2.6.9)
- `system/scripts/tracker.py` (5,009 lines) is the only writer of `tracker.db`. It includes:
  - `connect()`: autocommit, rows by name, foreign keys on.
  - `BEGIN IMMEDIATE` around every apply and undo.
  - `check_values` / `check_row` and the per-table rule functions (`_milestone_rules`, `_decision_rules`…).
  - `write_item` → `_insert_row` / `_update_row`.
  - `log()`: one `change_log` row per field, plus an `item_events` row.
  - `cmd_undo` with `_changed_since` and `_reverse_item`.
  - `undo-changes` (revert chosen rows), `migrate`, `milestone_state`, `next_id`.
  - Plus a great deal clark doesn't need.
- `system/scripts/schema.sql`: the CHECK-heavy schema, with `applies`, `change_log` and `item_events`.
- `system/scripts/item_history.py`: one item's history, newest first, with undo links.

## What is copied (as patterns and code, cut down)
| creaite | clark (`src/clark/store.py`, `schema.sql`, `history.py`) |
|---|---|
| `connect()` (`isolation_level=None`, `Row`, `PRAGMA foreign_keys = ON`) | the same, plus `PRAGMA journal_mode = WAL` and `busy_timeout`, because the server and an import may overlap. WAL is safe only on the machine's own disk, and clark never opens a database inside OneDrive (`portability-and-sharing.md`) |
| `BEGIN IMMEDIATE` … `COMMIT` / `ROLLBACK` around a whole step | the same: one step is one transaction, so a failure leaves nothing half written |
| `schema.sql` | creaite's tables for projects, milestones, workstreams, actions, RAID, decisions, links, labels, updates and history, with their CHECKs unchanged, plus clark's own tables and the few marked clark columns (`data-model.md`, revised 28-10-2026: "ensure that the work item and milestone schemas reflect those of creaite") |
| `check_values` / `check_row` and the per-table rules (`_milestone_rules`, `_decision_rules`, `_item_workstream`, the complete client message) | copied as they are for the creaite tables; new rules only for clark's own tables (a use case existing in the same project) |
| `log()` → `applies`, `change_log` (`old_value` / `new_value` / `op` / `via`) and `item_events` | the same three tables. `applies` gains `by_user` and `device`, and `item_events` uses clark's routes |
| `next_id(con, table, project)` | the same rule and IDs: `<CODE>-A-NNN`, `<CODE>-NNN` (RAID), `<CODE>-D-NNN`, `<CODE>-M-NNN`, `<CODE>-W-NNN`, plus clark's `<CODE>-U-NNN` for use cases |
| `cmd_undo`: reverse the newest step not undone, `_changed_since`, `_reverse_item` (an insert deleted, a removed row put back, fields restored), in one transaction | the same behaviour, by `apply_id` rather than always the newest, so the toast's Undo reverses exactly its own step. **As in creaite, a row changed by a later step is skipped and named, and the rest are reversed.** (This replaces the "refused" wording in `data-model.md`.) |
| `milestone_state` / `suggested_state` / `MS_CLIENT_WORD` | goes to #32, copied as they are, plus Forecast |
| `item_history.history_of` | `history.py`: one row's history, newest first, with undo links |

## What is cut
- Proposals and staging files, file operations (copy, move, remove, mkdir, write), and cards.
- Promises, workstream renames, rejected fingerprints, recode, archiving by age. (Labels and links are kept: the Sensitive label keeps a row out of the published file.)
- `vault_search` and the index, minutes, transcripts, PDF and mail text, backups to OneDrive.
- The CLI. clark's writer is a library that the server and the importers call.
- Anything reading `paths.py`, the vault or creaite's settings. The database path is passed in.

## The interface (outline)
```python
open_store(path) -> Store                       # creates from schema.sql if missing; refuses a newer schema_version
Store.read(kind, project, ref=None) -> rows
Store.step(via, by_user, note="") -> Step       # context manager: BEGIN IMMEDIATE … COMMIT, one applies row
  Step.create(kind, values) -> ref               # next_id, insert, one change_log row (field '+')
  Step.update(kind, project, ref, {field: value})  # only fields that differ; one change_log row each
  Step.delete(kind, project, ref)                # change_log field '-', the whole row as JSON in before
Store.undo(step_id) -> {reversed: [...], skipped: [{ref, why, by_step}]}
Store.history(kind, project, ref) -> events, newest first
```
Every write in clark goes through `Step`. No other module imports `sqlite3` for writing.

## Tests that pin it
1. **Only one writer:** a test scans `src/clark/` and fails if any module other than `store.py` runs `INSERT`, `UPDATE` or `DELETE`, or opens the database without `mode=ro`.
2. **Every CHECK refuses bad data:** a table-driven test with one bad row per rule (id pattern, date format, the enums, closed ≥ raised, the client message). **And the creaite tables match:** a test compares each creaite table's columns and CHECKs with `schema.sql` at v2.6.9, and allows only the columns marked `-- clark:`.
3. **One step, one transaction:** an error raised mid-step leaves the database byte-for-byte the same (compared with `iterdump`).
4. **Logging:** an update of three fields writes one `applies` row, three `change_log` rows and three `item_events` rows with the right before and after values. An update to the same value writes nothing.
5. **Undo:** each case reverses correctly (create, update, delete), the links between steps are set, and an undo of an undo restores the change.
6. **Undo skips a row changed since,** naming the later step, as in creaite's pinned case (`dev/tests/pinned/undo_skips_a_row_changed_since.json` at v2.6.9, re-made with clark's demo data).
7. **History:** newest first, with undo links, for a row with five steps.
8. **Two connections writing at once** (the server and an import) end with both steps applied in order, or one waits; neither is lost.
9. **The copy is recorded:** the reuse record lists `tracker.py`, `schema.sql` and `item_history.py` at v2.6.9 `db5adb2`. A test checks that the row exists.

## Review focus
Transaction edges (an exception inside `Step`), JSON before and after (`None` against the empty string), the undo rule for skipped rows, SQL built from field names (they must come from the table's own column list, never from the request).
