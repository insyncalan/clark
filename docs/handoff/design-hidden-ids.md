# Design note: the page can read which rows are left out of the published page

Guarded file touched: `src/clark/store.py` (`Store.data_for`), one small addition. No other source file changes.

## What is added
`Store.data_for(code)` (the read behind `GET /api/data`) now returns one more key, `hidden`: a sorted list of id strings, for example `["ABC-M-002", "ABC-M-007"]`.

- They are the rows of THIS project that the eye has left out of the published page (the `report_hidden` table).
- Ids only. No names, no text, no counts of other projects.
- Only ids that still name a row of this project (an action, risk or issue, decision, milestone or use case). An id whose row is gone, or that names another project's row, or that is not an id at all, is skipped. An archived row stays listed, so Restore brings it back with its eye state kept.
- The list is the same for `archived=hide`, `show` and `only`.
- No hidden rows: `[]`. Unknown project: `data_for` returns nothing, as before.
- Order is plain string order, the same as the change route's `hidden` reply, so it is steady between reads.
- The list can never be longer than the number of rows the project has (every id must match a row).

Note: `data_for` also carries `report_hidden` (the project's raw list, for a template's live part). `hidden` is the stricter list: only ids that still name a row of this project.

## Why
The write route (`/api/change`, kind `report_hidden`, op `new` or `delete`) already hides and shows a row, and its reply carries `hidden`. But after a reload the page had no way to learn the state, so it could not draw the eye pressed or mark a row as left out. `publish_inputs` read the ids for publishing only.

## What a hostile caller can do
Nothing new. `/api/data` already needs the same Host check and session token as before, and returns far more (every row of the project). The new key is ids that are already in that reply's rows. Nothing is written by the read.

## What the published file never carries
The published file is made from `publish_inputs` (its own read, in its own transaction), never from `data_for`. `publish_inputs` applies its list to leave the rows out, then the file is written from the kept rows and a fixed list of fields. There is no copy of unknown keys. So the published file has no `hidden` key and no list of hidden ids, and the left-out rows are not in it at all, not even by name.

`tests/test_store_hidden_ids.py` proves it: a project with a left-out milestone is published, and the file holds neither the id nor the name, no `hidden` key anywhere in its data block, and no mention of `report_hidden`.

## Tests
`tests/test_store_hidden_ids.py`: empty list; unknown project; hide, show and Undo (both directions) are seen at once; stable sorted order; the same under every archive view; archived row stays listed; a deleted row is not listed; another project's ids never appear (and a stray row naming another project's item, a non-id or a missing id is skipped); a long list is bounded by the rows; ids only; the published file carries none.
