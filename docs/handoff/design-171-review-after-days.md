# Design for #171: "not reviewed after N days", a setting of each project

**Plain words for the owner (this is the change to the store you are asked to approve).** Until now clark has used one fixed number,
14, for every project: an open item that nobody has changed by hand for more than 14 days gets the "Not reviewed in 14 days" note.
This change gives each project its own number. It is kept in the project's own record, as one new whole-number box beside the
project's name, health and week-ending date, and it starts at 14 for every project you already have, so nothing you see changes.
The number can be 1 to 365 and nothing else. It can be changed in one way only, the same way a project's health is changed: one
step you can undo, with a line in the history saying who changed it, how and when. A wrong value (text, a decimal such as 14.5, a
negative, 0, more than 365, a list, empty) is refused with "Choose a whole number of days from 1 to 365. Nothing was changed." and
the old number stays. Opening an existing file adds the box in a safety-copied step (the usual copy taken before an update), and
opening it a second time does nothing. The page for changing the number is not part of this (that is #160, the Settings screen);
this item is the storage and the two routes under it.

## Where it lives, and why there

A per-project setting on clark is a column of the `projects` table (`health`, `health_reason`, `week_ending`, `layout`), written
through the one writer (`changes.py`, kind `projects`, op `update`). `review_after_days` joins them:

```
review_after_days INTEGER NOT NULL DEFAULT 14
  CHECK (typeof(review_after_days) = 'integer' AND review_after_days BETWEEN 1 AND 365)
```

The ticket says "the settings table the other project settings use"; on main the only such table is `app_settings`, and it is one
row for the whole computer (the ask switch, #47), not per project. The projects row is where the per-project settings are, so the
column goes there (no new table, as the ticket asks). The `typeof` test is needed: SQLite turns the text "14" into the number 14
by itself (that is harmless), but a decimal such as 14.5 would otherwise pass `BETWEEN`. The column is last in the table so the
migration's `ALTER TABLE ... ADD COLUMN` gives a brought-up file the same columns, in the same order, as a new file (a test checks it).

## Migration step 12 (store.py, guarded)

`SCHEMA_VERSION` 11 to 12. `migrate_review_after_days` runs `ALTER TABLE projects ADD COLUMN ...` with the same default and CHECK,
only when the column is missing. SQLite accepts a CHECK with a default in `ADD COLUMN`, and every existing project takes 14, so no
table is made again and no frozen `schema_v12.sql` is needed (design-152 asks for one only when a table is rebuilt). The runner
already takes the safety copy before any step, runs it in one transaction with the version written after it, and refuses a file made
by a newer clark. Nothing else is touched (a test compares every other table, index and trigger). `tests/test_store_review_days_migration.py`:
a version 11 file gets 14 on every project (an archived one too) and keeps every other row; a version 1 file goes through all steps;
the safety copy is on disk before the step and holds version 11 without the column; a failed copy changes nothing; opening twice
changes nothing and takes no second copy; running the step twice keeps a changed value; the CHECK refuses 0, 366, 14.5, text, empty,
null and a blob in a brought-up file and in a new one.

## The one writer (changes.py, guarded)

`review_after_days` is added everywhere `week_ending` is listed, because a project field change is one "page family" step:

| Place | What it does for `review_after_days` |
|---|---|
| `CHANGE_KINDS["projects"][UPDATE]` | allows the field |
| `_checked_project_changes` | a real `int` (not `True`, not `14.5`, not `"14"`, not `None`, not a list) from 1 to 365, else `Refused(BAD_REVIEW_DAYS)`, before any step opens, so nothing partial is written |
| `UNDOABLE["projects"]` | Undo may put it back |
| `_row_is_ours`, `_eligible` (`beside`, `page_family`) | the step counts as a project-page step, its `updated_at` stamp passes, and it cannot be mixed with an archive step |
| `_do_project_change` reply and the Undo reply | `project.review_after_days` is returned so the page can show the new number at once |
| Undo words | "Put back: the days before an item counts as not reviewed." |

The store also checks the value itself (`check_values`), so a caller that goes round the route is refused (`Invalid`), and the CHECK
in the schema is the last guard. The history (`history.py`, guarded: one label) names the field "Not reviewed after (days)", so the
line reads who, how, when, from 14 to the new number; an Undo has its own line. "How" is whatever place the caller sends (the Settings
screen, #160, chooses it). With no place it reads "Other"; a new place of its own would need a change to the `item_events` CHECK, so
a second migration, which this item does not add.

`BAD_REVIEW_DAYS` is the exact sentence of the ticket and is the only refusal for every bad value.

## The read, and what reads it

No new GET route. `/api/data` already returns the project's whole row (`Store.data_for`: `SELECT * FROM projects`), so
`project.review_after_days` reaches the page with no new code, under the same token, Host and Origin checks as every route. The
published file reads an allow-list of project columns (`publish.PUBLISH_FIELDS`) that does not name it, so the file is unchanged (a
test checks this, and the publish tests pass).

Readers now use the project's number, with 14 written once as the default on each side:

- `store.review_days_for(project_row)` (the freshness feed's N) reads the row; a missing or out-of-range value gives
  `freshness.DEFAULT_DAYS` (14). `attach_freshness` already passed N into `freshness.py` and into each item's `freshness.days`.
- Page: `filters.js` keeps `REVIEW_DAYS = 14` as the default and holds the current number (`setReviewDays`, called by one effect in
  `stores/report.js` whenever the project's data arrives or changes; a published file has none, so 14). `staleWords`, `notReviewed`'s
  fallback, the Freshness filter's value and `filterLine.js` (the `is:quiet` words, its hint and its "not available" sentence, and its
  fallback count) read it. The peek's chip already read each item's `days`. `stores/changes.js` copies the number from a change reply
  into the page's project record.
- The Publish dialog has no "not reviewed" wording on main (the warnings were taken out of it, #222), so there is nothing to change there.
- The Help page still says "14 days" in its text; it describes the default and #160 will say where to change it.

The server decides which items are flagged. After a change the items' `not_reviewed` come from the next read of the data, so a caller
(the Settings screen) reads the data again after the change, as the page already does after a section change (#188).

## Not built

- The Settings screen to change the number: #160. This item adds no screen, no menu and no Help entry (so the Help floor is unchanged).
- A "settings" place for the history's "how" column (see above).
- Excel or Word carrying the number: it is a setting of this computer's copy of the project, not report content.

## Tests

`tests/test_review_after_days.py`: the writer (one step, Undo, the history line, a mixed health step, every hostile value on the
old number and on a changed one, the store's own refusal, other kinds and keys), the read, the feed counting from the project's
number, and a real server for the token, loopback Host and Origin checks on both routes. `tests/test_store_review_days_migration.py`:
the migration. `tests/test_filter_line_page.py`: the Freshness words follow the number (3, 1 and 365) in the real page. Earlier tests
that pinned the exact reply or the list of project fields (`test_changes_tiles.py`, `test_v060.py`) were updated for the new field.
