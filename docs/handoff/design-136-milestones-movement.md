# Design: #136 v0.2 Milestones Movement (#44b): the history read and the milestone change kinds

**Status, 31-10-2026:** built on branch team-a-136-build: commits 1 to 3 (pure view, confirm text, fixtures), G1 to G3 (read, route, change kinds) and commit 7, the page. The page is the Movement block under the Milestones list, in Edit only (`edit/Movement.jsx`, loaded from `GET /api/movement`, words in `edit/movementWords.js`, styles in `edit/edit.css`, none of them in `page-view.html`), with Hold and Move the agreed date (who, reason, source, the confirm, refusals, toasts and Undo). Not in this item: the internal note box, Add a recovery action, Escalate to steering, the decision link opening a peek (shown as text until the peek exists) and the Help entry (held in `helpLater.json` until the Milestones peek arrives). Tests: `tests/test_movement_page.py`.

Written by a teammate, 29-10-2026. Nothing is built; docs only. Size M, review **Full** for the guarded commits (G1 to G3 below), Light for the rest. BRD FR-50 to FR-53 and FR-43a, FR-43c.
**Sources:** #136 and its Done-when; `docs/BRD.md` (FR-43a, FR-43c, FR-50 to FR-53, FR-81, FR-82); `docs/DECISIONS.md` (28-10-2026 slip ruling, "we never delete - we archive", laptop-only 29-10-2026); `docs/handoff/data-model.md` (rebaseline, `movement`); `docs/handoff/readiness-v0.2.md` (#44); the prototype's Movement (`system/prototype/views.js` `moveHtml`, `help.js` "Deal with a slipped milestone", `selftest.js` M5, M6); on main `src/clark/milestone_rows.py` (`movement`, `moves`, `for_client`, `rebaseline_request`), `milestones.py`, `history.py`, `store.py` (`data_for`, `publish_inputs`, `NEVER_PUBLISH`, `reverted_rowids`, `Step`, `_write_rebaseline`), `changes.py` (`CHANGE_KINDS`, `UNDOABLE`), `server.py` (routes), `publish.py`; designs #118 (`design-118-changed-since-last-report.md`) and #123 (`design-123-history.md`).

## 0. What the code tells us before design
- **The Movement list already exists as a pure function.** `milestone_rows.movement(events, milestone_id)` turns `history.history()` events into entries (rebaseline with its decision, agreed, forecast, achieved, reopened, cancelled, state, Movement choice, internal note), newest first, with `undone`, `why`, `decision` (the last `ABC-D-001` in the step's note) and `at_text` (local time). `moves()` counts date moves. It has tests (`tests/test_milestone_rows.py`). **What is missing is the read that feeds it:** nothing on main returns a milestone's history to the page. `Store.history(ref)` exists but is one item at a time, and its SQL (`item_id LIKE '%|id|%'`) cannot use the index, so a loop over 60 milestones scans `change_log` 60 times (measured on a scratch copy: 21,200 rows, 60 calls, 73 ms; fine today, wrong shape for a page load).
- **`data_for` is the page-load read** (every table's rows, `SELECT *`, so the owner's page already holds `internal_note`, `movement` and `state_reason` as columns). It is also the function #167 (open, Full tier, the freshness feed) is changing. Adding a history join to it would make every page load pay for Movement and would collide with #167. **This note does not change `data_for`** and gives the read its own method and route (Q1 for the Head).
- **`NEVER_PUBLISH` and `publish_inputs` already keep `internal_note` and `movement` out of a published file** (`store.py`, tested in `tests/test_publish.py`). The published file already carries each milestone's `original_date` (a date, from `publish_inputs["changes"]`, only `baseline_date` rows), and nothing else of its history. That stays exactly as it is.
- **The write side is missing for milestones.** `CHANGE_KINDS` (changes.py) has actions, RAID, decisions (#68), tiles, projects and sections; for milestones it has only `archive` and `restore` (#126). `UNDOABLE["milestones"]` is `("archived",)`, so an Undo from `/api/undo` would refuse a milestone date put back. Both need widening (G3).
- **There is no "in Movement" place.** `item_events.place` is checked in the schema (`peek, cell, bulk, menu, report, dashboard, excel, board`) and in `store.PLACES`. The prototype records "in Movement". See Q2: adding a place is a schema change (main is schema 2; #120 = 3, #115 = 4, so this would be 5).
- **Times.** `change_log.at` is UTC to the millisecond with no offset on main (`store.now()`). The offset arrives with #123. The read returns `at` exactly as stored; the page shows it in local time with `timefmt.local_text`, so it needs nothing from this item either way.
- **Cost, measured on a scratch SQLite file (not the product), 41,200 `change_log` rows: 5,000 actions with 4 changes each, 20,000 rows of another project, 60 milestones with 20 changes each.** The query in G1 (`tbl = 'milestones'`, an `item_id` range, a fixed field list) uses `change_log_item`, returns 1,200 rows in about 1 ms. Work items never enter it, so 5,000 items change its cost by nothing.

## A. What Movement shows

### A1. What a person sees (the owner, in Edit and on the Milestones page)
**Milestones › Movement** (the second button of the Plan / Movement switch, as the prototype). The page is laptop-first: 1400 and 900 px, light and dark (decision of 29-10-2026); no phone layout.
- **A heading and a tag**: "Movement" and the neutral tag "Internal only: never published". Under the switch: "Movement is for you and the team: it is never published."
- **One sentence** about the open milestones (A3).
- **One row per open (Planned) milestone**, worst first: name, state mark and word, "Agreed DD-MM-YYYY" (and "forecast DD-MM-YYYY" when it has slipped), a track (diamond for the original date when the agreed date has moved, bar for agreed, the forecast mark, a red line for the distance past agreed, today), and at the right the **variance** and "Agreed date moved" or "Never moved".
- **The chosen milestone's card**: chips Original, Agreed, Forecast, "Moved N times" or "Never moved", Progress, Owner. Then **What changed**: the history list (A2), newest first. Then **Decide what to do** (Hold, Move the agreed date; A4) and the **Internal note**.
- **Archived milestones are not listed** (FR-43c), and not counted in the sentence. Done and Cancelled milestones are not rows here (their dates still show in the peek's Activity).

### A2. What a "What changed" line says
Each line is one entry of `milestone_rows.movement`, with who and when ("by {name}, DD-MM-YYYY HH:MM", the full name from Settings › Profile as FR-43a, local time). A line shows its reason ("why") under it, and a rebaseline shows its decision as a link to the decision ("Decision ABC-D-001", opening the decision's peek). A line whose step was later undone is shown dimmed with the tag **Undone** (the record shows what was tried); Undo rows themselves are not listed.

| Entry | Words (pinned) |
|---|---|
| Rebaseline | "Rebaselined: agreed date moved from 03-11-2026 to 24-11-2026, forecast now 24-11-2026" (the forecast clause only when the forecast moved with it) |
| Agreed date, no decision | "Agreed date moved from 03-11-2026 to 24-11-2026" / "Agreed date set to 03-11-2026" |
| Forecast | "Forecast moved from 03-11-2026 to 10-11-2026 (+7 days)" / "(-3 days)" / "(+1 day)" / "Forecast set to ..." / "Forecast cleared (it was ...)" |
| Achieved | "Achieved on 10-11-2026" / "Achieved" (no date) / "Achieved date moved from ... to ..." |
| Reopened, cancelled | "Reopened" / "Cancelled" |
| State | "State changed from On track to At risk" (the reason under it; "following the dates" when empty) |
| Movement choice | "Movement choice: Hold" / "Movement choice: cleared" |

The day count follows FR-50's grammar: a sign, then "1 day" or "N days" ("+1 day", "+7 days", "-3 days"); a move of 0 days has no count. Today these words come from `milestone_rows.movement`, unchanged.
**Internal note changes are not lines here.** The read never returns the `internal_note` field's history (A5), so "Internal note changed" and its text are not listed; the note is edited in its own box, and its history is in the peek's Activity (Q3).

### A3. The numbers and sentences (plain words, British English, none starts with the product name)
- Sentence, more than one open milestone: "{n} of {m} open milestones are behind their agreed date; {k} overdue." With one open milestone: "The open milestone is behind its agreed date." / "The open milestone is on its agreed date." With none open: "Every milestone is achieved." With no milestones: "No milestones yet."
- Worst row, appended when something is behind: "{Name} is {N days} behind the agreed date and {M days} behind the original." (the second clause only when the original date differs; "1 day" not "1 days").
- Variance: "{N days} after the agreed date" / "{N days} before the agreed date" / "On the agreed date". The count is `slip_days` (FR-50 and the 28-10-2026 ruling); a Forecast milestone has no slip and reads "No agreed date yet".
- **Original is never blank** (Done-when 4): the first agreed date still in force; else the current agreed date; else the forecast; else "No date yet". The chip and the diamond use the same value.
- Moves: "Never moved" (no date move in force) / "Moved 1 time" / "Moved 3 times". Empty list under What changed: "Nothing has changed since it was first agreed."

### A4. Deciding (the write side)
- **Hold**: "Hold: keep the forecast, agreed date unchanged". Sets the Movement choice to Hold and adds a dated line to the internal note ("DD-MM-YYYY: holding; agreed date unchanged, forecast DD-MM-YYYY."). Toast: "Hold recorded. Undo."
- **Move the agreed date**: a confirm in these words: "Move the agreed date of {name} from {DD-MM-YYYY} to {DD-MM-YYYY}? The original date ({DD-MM-YYYY}) is kept and a decision is recorded. You can undo this." It asks for **who agreed it, the reason and the source** (`rebaseline_request`, unchanged: "Say who agreed the new date.", "Give the reason the agreed date is moving.", "Give the source: where it was agreed, for example the meeting or the email."). Buttons **Move the agreed date** and **Keep the date**. Enabled only when the milestone has slipped. One step: the date, the decision and the note together, one Undo. Toast: "{name}: the agreed date is now {DD-MM-YYYY}. Undo."
- **Add a recovery action** and **Escalate to steering** (a new action, a new decision, linked) are **not in this item** (Q4): `changes.py` has no `new` for actions or decisions (#68 allows only `update`).

### A5. What the client sees, and what is owner-only
- **A client sees none of Movement.** The published Milestones section keeps what `for_client` allows: name, workstream, owner, status, state in the client's word ("Expected later", "Late"), agreed, forecast, achieved, percent, the slip text ("N days later"), the expected date, the marks, and the client wording. The published file already carries `original_date` as one date; that stays.
- **Owner-only, never in a published file, the Word or Excel cover, the client folder copy or Draft email:** every Movement line (who, when, how), every reason, every "agreed with" name, the decision link, the Undone tags, the Movement choice, the internal note and its history, the state reason, the variance sentence.
- **The Movement read never returns `internal_note`.** The SQL names its fields; `internal_note` is not among them (A6, G1).

## B. The data it needs and where it comes from

### B1. The guarded read (G1): `Store.milestone_moves(code)`
**In plain words:** one function on the store, `milestone_moves(code)`, opens its own read-only connection (as `data_for` does), in one transaction, and returns the date-change history of the project's live milestones. It writes nothing, takes no row from another project and never opens the database from anywhere else.
**Returns:** `None` when there is no such project, else
`{"project": code, "milestones": {<milestone id>: {"original": <YYYY-MM-DD or None>, "total": <entries before the cut>, "events": [event, ...]}}, "truncated": <bool>}`
- **One list per live milestone** (`archived = 0`, this project's), including one with no changes (`events: []`, which the page reads as "Never moved").
- **Rows per milestone: up to 50 events, newest first**, in the shape `history.history()` already gives (`event_id, at, step, by_user, table, ref, field, before, after, op, route, place, origin, actor, undoes, is_undo, undone_by, in_force`) so `milestone_rows.movement` runs on them unchanged. `total` says how many there were; the page shows "Showing the latest 50 changes. The peek's Activity has them all." when `total > 50`.
- **A ceiling for the project: 1,000 events in all** (so the reply stays near 300 KB at about 300 bytes an event; a typical project of 60 milestones with 10 changes each is 600 events and about 180 KB). Past the ceiling the oldest milestones' lists are cut, and `truncated` is true.
- **Fields read, a fixed list in the SQL, never from a caller:** `baseline_date, forecast_date, actual_date, status, state, state_reason, movement, note` (and the step's rows needed to find `created`: `id`). **`internal_note` is not in the list.** `note` is the reason written with a step (the rebaseline's "reason. Agreed with X. Decision ABC-D-001"); it is read for `why` and `decision` only.
- **The query:** `change_log` where `tbl = 'milestones'` and `item_id >= '<CODE>-M-'` and `item_id < '<CODE>-M.'` (a range, so `change_log_item` is used; the first form measured above) and `field IN (list)`, joined to `item_events` (as `history.history` does) and `applies` (`undone_at`). `reverted_rowids(con)` is called **once** for the project, not once per milestone. `original` is computed from every row (not the 50), by the same rule as `history.original_date` (first agreed date in force).
- **Rows at 5,000 items:** work items do not enter the query. The rows read are the milestones' own history rows (about 1,200 for 60 milestones with 20 changes each; ceiling in practice a few thousand), about 1 ms on the scratch file above plus a few ms in Python. No index is added; no schema change.
- **No new writer, no schema change.** It uses only `change_log`, `item_events`, `applies`, `milestones`. It is not part of `data_for`, `publish_inputs` or `PUBLISH_FIELDS`.

### B2. The route (G2): `GET /api/movement?project=<CODE>`
The same checks as `/api/data` (project code shape, 404 for a missing project). It returns `{"ok": true, "project": code, "movement": <B1's reply, run through the pure view of C1>}`. The server holds no store import (it calls a method the server is given, as `data_for`). **Not in ask clark's route list** (Q5). The diagnostic log gets the route, the project and the counts, never a value (FR-8b).

### B3. The milestone change kinds (G3): `/api/change` and `/api/undo`
`CHANGE_KINDS["milestones"][UPDATE]` gets the fields **`baseline_date, forecast_date, actual_date, status, state, state_set, state_reason, client_message, movement`** (the issue's "agreed, forecast and achieved dates, state, client wording", with `status` for Done and `movement` for Hold). Not allowed from a request: `internal_note` (Q3), `owner`, `name`, `workstream`, `sort_order`, `project`, `id`, `archived` (archive stays its own op).
- **Each change is checked as a typed change is** (changes.py's eligibility, then the store's own checks): a date is YYYY-MM-DD or empty where it may be; a milestone that is Done or Cancelled refuses an agreed-date move ("Only a planned milestone can be rebaselined; this one is done."); an agreed date can't be cleared once agreed; an archived milestone refuses with `ARCHIVED_MILESTONE` ("That milestone is archived. Restore it first."); another project's or a missing milestone reads `NO_MILESTONE`; a state better than the dates suggest needs its reason (`milestones.needs_reason`); a Forecast never does.
- **Moving the agreed date is a rebaseline.** The request carries `rebaseline: {agreed_with, reason, source, date?}`, which `changes.KIND_OP_KEYS` must allow for milestones (as it does `changes` for a project). Checked by `rebaseline_request`'s rules, written by the store's `_write_rebaseline` in the same step: **one step, one Undo** (the date, the new decision, the note).
- **One step with one Undo:** several fields in one request are one `Store.step`; a refused request writes nothing (the step rolls back); `UNDOABLE["milestones"]` grows to the same field list plus `archived`, `updated_at` and `note` already allowed (`UNDO_ALSO`). An Undo of a rebaseline removes its decision, as the store already does (`revert`).
- **"Recorded in history as in Movement"** (FR-43a): see Q2. The proposal (no schema change) is: `place = "dashboard"` and `src_ref = "Movement"`, and the history display says "in Movement" when it sees both. If the owner wants a true `movement` place, it is a schema 5 migration step (a new CHECK list on `item_events.place`, the table rebuilt by copy as the schema 2 step does), and it should travel with #123's other place changes.

## C. Build order: separate commits

**Unguarded first (pure, no database, no page, no clock):**
1. `#136: pure Movement view` : `src/clark/movement_view.py`. `view(rows, moves_reply, today)` takes the milestone rows and B1's reply and returns what the page draws: for each open milestone its sentence parts, variance, original (never blank), moves count, entries with `internal_note` entries and every `detail` removed, `undone` tags, and the page's summary sentence. Includes the wording table (A2, A3) as constants, and `ALLOWED_KEYS` for a reply. Calls `milestone_rows.movement`, `moves`, `slip_days`; changes none of them. Tests in `tests/test_movement_view.py` (section E).
2. `#136: the Move the agreed date confirm, pure` : in the same module, `confirm_text(row, to, today)` and `refusal_text(...)` for the confirm and the toasts of A4, over `rebaseline_request`. Tests pin each sentence.
3. `#136: Movement fixtures` : `tests/fixtures/movement_events.py`, planted histories (a rebaseline with two decisions cited, a forecast moved and put back, an undone rebaseline, a milestone with none, 120 events, an archived milestone, a planted internal note and marker strings). Shared by the tests of 1, 2 and the guarded ones.

**Guarded, each its own Full-tier commit, two reviewers, the owner's yes on the exact change (the Head approves bytes for G1 and G2 if the note is accepted):**
4. **G1 `store.py`: `Store.milestone_moves(code)`** (B1). Nothing else in `store.py` changes; `data_for`, `publish_inputs`, `NEVER_PUBLISH` are untouched.
5. **G2 `server.py`: `GET /api/movement`** (B2). The route table gets one entry; no body limit needed (a GET).
6. **G3 `changes.py`: the milestone kinds** (B3): `CHANGE_KINDS`, `KIND_OP_KEYS`, `UNDOABLE`, the eligibility words. If Q2 is "a real place", the schema step and `PLACES` ride here as G4 with the migration test, not before.

**Unguarded again (after G1 and G2; G3 for the Decide buttons):**
7. `#136: Movement page` : `src/clark/page/src/` (the Movement view in `Views.jsx`/a new component, rows, track, card, What changed, Decide buttons, internal note box, Help entries), then `python3 dev/tools/build_page.py` (never hand-merged; `--check`). Checked at 1400 and 900 px, light and dark.
8. `#136: docs` : FR-53 line (states Hold and Move here, the rest later), Help (one how-do-I, "Deal with a slipped milestone", words as the prototype), `DECISIONS.md` entry.

Order: 1 to 3 (parallel, Light), then 4, 5, 6 in turn, then 7, 8. Commit 7 can start on the fixtures before G1 lands and only wires to the route afterwards. **Dependencies:** #44a (PR #75, merged) for `milestone_rows`; #126 (schema 2) for `archived`; #68 for the change-kind layout (merged on main: actions, RAID, decisions). #123 (offsets, places) and #167 (`data_for`) touch neighbouring guarded code: this item changes neither `data_for` nor the places, unless Q2 says so.

## D. Tests (python 3.9-safe; targeted runs; wording pinned, NFR-3 and FR-112)
**Unguarded (`tests/test_movement_view.py`, from `tests/fixtures/movement_events.py`)**
- Ordering: newest first, ties by event id; entries of one step stay in one entry (a rebaseline folds its forecast move).
- The decision link takes the **last** cited ID when the reason names an earlier decision too ("see ABC-D-004 ... Decision ABC-D-011" gives ABC-D-011); no ID gives "".
- Undone: an undone rebaseline stays listed with the **Undone** tag and is not counted by "Moved N times"; the Undo's own rows are not listed.
- The 0, 1 and N grammar: "+1 day", "+7 days", "-3 days", "Moved 1 time", "Moved 3 times", "1 of 1", "Every milestone is achieved.", "Never moved", and a move of 0 days has no count.
- Original is never blank (agreed only; none agreed and a forecast; no date at all reads "No date yet"; a rebaselined one shows its first date in force; an undone first agreement is skipped).
- A Forecast milestone has no slip and no "behind" wording; a Done, Cancelled or archived milestone is not a row.
- Every sentence of A2 to A4 pinned as a constant; none starts with the product name; no word the glossary forbids (a source test over the module's strings); dates always DD-MM-YYYY in text, YYYY-MM-DD in data.
- **Internal note:** a planted `internal_note` change and marker is absent from `view()`'s output (no entry, no `detail`), from the keys (`ALLOWED_KEYS` is the whole set), and from the JSON of the reply.
- Python 3.9: no `match`, no `X | Y` types, no parenthesised `with`.

**Guarded read (`tests/test_store_movement.py`)**
- The reply's keys are exactly B1's; no event has `internal_note` as a field; the SQL text constant does not contain `internal_note` (a source test that fails if it is added).
- A milestone with no history returns `events: []`; an archived milestone is absent; another project's milestone never appears (two projects with the same history shapes); a missing project returns `None`; a bad code is refused by the route (400).
- Ordering and the 50 and 1,000 limits (`total`, `truncated`); `original` is computed from all rows, not the 50.
- In force: after an Undo, the reversed row is `in_force` false and the Undo row is `is_undo`; `reverted_rowids` is called once (a counting wrapper).
- A read does not write: row counts and `PRAGMA data_version` identical before and after; the connection is read-only (a write attempt through it fails).
- 5,000 items and 60 milestones with 20 changes each: the query plan uses `change_log_item` (checked with `EXPLAIN QUERY PLAN`), the reply is under 400 KB, and the call finishes in under 1 s on the test machine (a ceiling, not a benchmark).

**Route (`tests/test_server_movement.py`):** missing token or wrong Host refused as `/api/data` is; 404 for a missing project; no `internal_note`, `body` or description key in any reply; the route is not in ask clark's list.

**Change kinds (`tests/test_changes_milestones.py`)**
- Each field is accepted and written as one step with one Undo; a refused request (bad date, a Done milestone, a state needing its reason, an archived or another project's milestone) **writes nothing** (row counts and `change_log` unchanged).
- A date move without who, reason and source is refused in the words of `rebaseline_request`; with them it writes the date, one decision and the note in one step, and **Undo restores the previous date and removes the decision.**
- A field outside the list (`internal_note`, `owner`, `archived`, `sort_order`) is refused; a request carrying extra keys is ignored.
- History: the step's rows carry the profile name, the route and the place of Q2.
- Several milestones' undo does not touch a field changed by a later step (skipped and named, as now).

**Client-safe pin (the test that keeps it true) (`tests/test_movement_never_published.py`)**
- Plants, on one milestone: an `internal_note` with a marker, a `state_reason` marker, a rebaseline whose reason, "agreed with" name and source are markers, a `movement` choice, and a decision cited in the note. **Publishes (To client too), then searches the finished bytes** (the page, the `clark-data` block, the client-folder copy) for every marker, for each pinned Movement phrase of A2 ("Rebaselined", "Movement choice", "Undone", "Internal only"), the decision ID in the history context, and every key name of the Movement reply, in the four spellings #39's helper uses. None present. The one date the file may hold is `original_date`, asserted equal to the first agreed date.
- A source test: `publish.py`, `publish_flow.py`, `to_client.py`, `excel_cover.py`, `draft_email.py` and `store.publish_inputs` do not mention `milestone_moves`, `movement_view` or `milestone_rows.movement`; `NEVER_PUBLISH` still holds `internal_note` and `movement`; `PUBLISH_FIELDS["milestones"]` holds neither.
- The published file is byte-equal with and without Movement history (same inputs, one milestone moved twice and one never).

**Page (browser checks, `chrome_command()` only):** Movement at 1400 and 900 px, light and dark: the sentence, rows, track, card, an undone line dimmed with its tag; the Decide buttons enabled only when slipped; the confirm's words; no horizontal scroll at 900; the published page has no Movement button and no tag.

## E. Wording for every message and label (British English, plain, none starts with the product name)
Labels: "Plan", "Movement", "Internal only: never published", "Original", "Agreed", "Forecast", "Moved N times", "Never moved", "Progress", "Owner", "What changed", "Decide what to do", "Hold: keep the forecast, agreed date unchanged", "Move the agreed date", "Add a recovery action" and "Escalate to steering" (not in this item; hidden until Q4), "Internal note", "Undone", "Edit milestone".
Helper texts: "Movement is for you and the team: it is never published." / "Each choice changes the record at once, with Undo." / "Saves when you leave the box. Never published." / "What is going on, what you are waiting for" (the note's placeholder).
Sentences, lines and toasts: A2, A3, A4.
Messages when it can't:
| When | Words |
|---|---|
| The read fails | "Movement couldn't be loaded. Check that clark is still running, then try again." |
| Not planned | "Only a planned milestone can be rebaselined; this one is {done or cancelled}." |
| Not slipped | "This milestone hasn't slipped, so its agreed date can't be moved yet." |
| Earlier date | "The new agreed date must be later than the current one (DD-MM-YYYY)." |
| Date in the past | "The new agreed date can't be before today (DD-MM-YYYY)." |
| Archived | "That milestone is archived. Restore it first." |
| Not here | "That milestone isn't in this project." |
| Over the limit | "Showing the latest 50 changes. The peek's Activity has them all." |
| Nothing | "Nothing has changed since it was first agreed." |
All but the first and the over-the-limit line already exist in `milestone_rows.py` or `changes.py` and are reused, not re-worded.

## F. Risks
1. **A leak is the only bad outcome.** Movement carries names, reasons and a note. Controlled by: a fixed SQL field list without `internal_note`; the read outside `data_for` and `publish_inputs`; `NEVER_PUBLISH` untouched; the planted-markers test over the finished bytes and the source test over every publishing module.
2. **Collision with #167 and #123** on `store.py`. Avoided by a new method and no edit to `data_for`; G1 adds a function and an import only. If #123 lands first the event shape gains an offset; `milestone_moves` passes it through.
3. **`reverted_rowids` per call.** It scans `change_log` for `revert:%` once; kept to once per read (tested). A very long history makes it the slowest part; still milliseconds at the sizes above.
4. **A rebaseline is a decision write.** An Undo removes the decision; a later change to that decision blocks the Undo and names it (as the store does). G3's tests include it.
5. **Place "in Movement" without a schema change** is a convention (`dashboard` plus `src_ref`). If it is lost, history still reads true, only the label is "in the dashboard". Q2.
6. **The 50 and 1,000 limits** are a choice; a milestone moved more than 50 times is unusual but possible after an import. The notice says so.
7. **Hold appends to the internal note**, which this read does not return. The owner sees the Hold as a "Movement choice" line and in the note box; the note's own history is in the peek.
8. **`Movement` gets read by ask clark** if a route list is wide. G2's route is not in its list (Q5).

## G. Questions
**For the project lead (plain words; each with a recommendation):**
1. **Who sees the "agreed with" name and the reason?** They appear in Movement lines, for the owner only. Recommended: yes, owner only, never published. Reply: **Owner only** / **Hide the name**.
2. **Do Done and Cancelled milestones appear in Movement?** Recommended: no, open milestones only; the peek's Activity shows the rest. Reply: **Open only** / **All live milestones**.
3. **Should "Internal note changed" be a line in What changed?** The read leaves the note's changes out entirely so its text can't travel. Recommended: no line; the note has its own box and Activity. Reply: **No line** / **A line with no text**.
4. **Recover and Escalate** (a new action, a new decision, linked) need a `new` kind for actions and decisions in `changes.py`. Recommended: not in #136; a follow-on item. Hold and Move the agreed date are in. Reply: **Later** / **In this item**.
5. **"Moved N times"** counts agreed and forecast moves not undone (as `moves()` does today). Recommended: as it is. Reply: **As is** / **Agreed date only**.

**For the Head (guarded):**
1. **A separate read and route, not a change to `data_for`?** Recommended: separate (`Store.milestone_moves` and `GET /api/movement`), because `data_for` is on every page load and #167 is changing it. The issue says "data_for history read"; this is its safer reading. Reply: **Separate** / **Inside data_for**.
2. **"In Movement" as a place:** with no schema change, `place = "dashboard"` and `src_ref = "Movement"`, shown as "in Movement". Or a true `movement` place (schema 5, behind #120 = 3 and #115 = 4, best bundled with #123's place list). Recommended: no schema change now. Reply: **No schema change** / **A real place, schema 5**.
3. **Limits:** 50 events a milestone, 1,000 a project, `truncated` flag. Recommended: as written. Reply: **As written** / **Other numbers**.
4. **Does a milestone's `movement` choice and `state_set`/`state_reason` belong in the allowed fields now,** or only dates, state and client wording as the issue lists? Recommended: add `status`, `actual_date`, `state_set`, `state_reason` and `movement` (the first three are needed to mark Done or set a state; the last two for Hold). Reply: **As B3** / **Issue's list only**.
5. **ask clark and the route:** not in its list, so it cannot read owner-only history. Recommended: keep it out. Reply: **Out** / **In**.
6. **Review:** G1 to G3 are three Full-tier commits for two reviewers, as separate approvals. Recommended: yes, one reviewed item with three commits. Reply: **One item, three commits** / **Three items**.

## H. Proposed Done-when (the project lead's six points, with the additions)
1. `Store.milestone_moves(code)` returns, per live milestone, up to 50 date-change events newest first (field, from, to, who, how, when as stored, the decision ID of the last one cited), `original`, `total`, and `truncated`; it reads through the store, with a fixed field list that has no `internal_note`, one query, and writes nothing.
2. `/api/change` accepts the milestone fields of B3, each checked as a typed change is, written as one step with one Undo, recorded in history as "in Movement" (Q2); a refused change writes nothing.
3. Nothing internal leaves: the reply has no `internal_note` (field list and keys tested); the planted-markers test finds no marker, phrase or key in the published bytes, the client copy or the data block; no publishing module imports the read.
4. Movement shows the pinned words of A2 to A4: "Move the agreed date", "On the agreed date", "Never moved", the slip with "+1 day" grammar, and Original never blank.
5. Archived milestones are not listed (FR-43c); a milestone with no moves says "Never moved."
6. Tests: ordering; the decision link takes the last cited ID; a refused change writes nothing; Undo restores the previous date and removes the decision; the limits; the read does not write; Python 3.9-safe; wording pinned (NFR-3, FR-112); the one-writer and guard tests untouched.
7. Checked at 1400 and 900 px, light and dark; the published page has no Movement.
