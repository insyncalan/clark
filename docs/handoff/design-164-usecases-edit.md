# Design note: editing an existing use case (#164, Full tier)

Writer side only. The Use Cases page's editing controls are a separate item (#157 part 1 and the page); this branch adds no page code.

## What each guarded file changes

- `src/clark/changes.py` (the only guarded file touched):
  - `CHANGE_KINDS["use_cases"]` gains `update` with five fields: `title` (the name), `headline`, `status`, `standing`, `client_visible` (the eye). The archive and restore ops already on that kind are #126's and are untouched.
  - `_checked_use_case_changes`: name and headline are plain one-line text (NFC, trimmed, no control or invisible characters, 120 and 300 characters), status is one of the store's closed set, `standing` goes through `sanitise.clean_html` (the cleaner the published file uses), the eye is 0 or 1 (`_flag`). Each refusal is a fixed sentence that never quotes the value.
  - `_do_use_case_change`: one step for all the fields (one Undo, one history line per field). Another project's use case and a missing one get the same words; an archived one is refused; nothing is written on any refusal. Store rule refusals pass through `_store_words`.
  - Undo: `_eligible` treats a use case of this project like a work item (one family of fields); `UNDOABLE["use_cases"]` lists the fields; the words call the use case by its name and never quote a text (`_use_case_words`).
- `src/clark/store.py`, `src/clark/server.py`, the schema: not changed. `/api/change` and `/api/undo` are the existing routes; history is recorded by the store for any update (`history.history` reads it).
- `tests/test_changes.py`: one expectation widened (`test_the_route_admits_only_the_approved_kinds` now lists `update` for use cases). The one-writer guard test is untouched and passes; changes.py builds no SQL.

## Landing with the status change on the At a glance branch (#186)

Both branches change `CHANGE_KINDS["use_cases"]`, `UNDOABLE["use_cases"]`, `_eligible`'s `items`, the `ITEM_REF` line and the field-name table in `changes.py`, and the status line of one test in `test_changes.py`. A trial merge (never pushed) gives a conflict in four hunks, and one more hazard that git does not show.

What wins, hunk by hunk (this branch's side is the superset; the other branch's status-only version adds nothing the page uses):

1. `CHANGE_KINDS["use_cases"]`: keep this branch's five fields (`title`, `headline`, `status`, `standing`, `client_visible`). Status is in both.
2. `UNDOABLE["use_cases"]`: keep this branch's list (`archived` plus the five).
3. `_eligible`'s `items`: keep one `use_cases` entry. Where `ITEM_REF` gains `U`, keep the use case check (`only_uc`) above the work item check (`only_items`), or a use case Undo is worded as "N changes to the work items".
4. Field names: keep this branch's `UC_FIELD_NAMES` and `UC_REF`; add the other branch's `"use_case": "use case"` entry to `ITEM_FIELD_NAMES`.

The hazard: the other branch's `ITEM_LIKE` includes `use_cases`, and its test of the dispatch line merges without a conflict. If a `kind in ITEM_LIKE` line stood before the use case line, `_do_use_case_change` would never run: the standing text would be stored as plain text without the rich-text cleaner, the eye would be refused as "not text", and the reply would carry `item`, not `use_case`. So this branch puts the `use_cases` dispatch **first** in `_do_change`, above the work item line. The merge then either conflicts on those lines (visible) or keeps the use case line first. The resolver must keep the use case line first and remove `use_cases` from `ITEM_LIKE`, `ITEM_SHOWN` and any `_fields` work item check, so the use case has one dispatch path. `test_use_case_updates_always_reach_the_use_case_writer` fails if the work item path ever takes a use case (it checks the writer is called, the standing text is cleaned, the eye is accepted as a whole number, and the reply has `use_case`).

## Not done, on purpose

- No create path and no delete or move path: `new`, `move`, `delete` are refused for use cases (`BAD_OP`), and a test lists the server's routes. Use cases still come from the project record and the Excel import.
- Status "Done": was refused here while the schema allowed On track, Flag and High risk only. It is a status since #412, which
  widened the CHECK with its own migration step; the status menu offers it and the refusal names the four.
- The eye is `use_cases.client_visible`. The `report_hidden` route (#67) is not built, so the eye cannot yet hide a use case by that route.
- Linking a work item and adding a next step use the work item's own change path (#68 and the work item `use_case` field is not in its list yet): not changed here.

## Review changes

- A step that only *made* a use case is not undone from the dashboard (the Undo would delete the row; use cases are archived, never deleted). Not reachable today, since use cases are only made by the Excel import; a test covers it.
- Undo after the use case was archived writes nothing, and the toast now says to restore it first.
- An archived use case of this project gets its own words ("That use case is archived. Restore it first."), while another project's and a missing one share one sentence. The split is deliberate: the page's user is told what to do about their own project's row, and nothing about another project's is revealed.
- The eye's Undo words say "on the dashboard" or "off the dashboard". The eye is `use_cases.client_visible`, which `publish.select` filters on, so it also decides what the published file carries. Whether the words should say "published" is a question for the owner and the product owner; not changed.

## Open: archive

`use_cases` is in `ARCHIVABLE` since #126, so `archive` and `restore` still work on `/api/change` for a use case. The owner's decision says no Archive for use cases. Removing it means changing #126's tests; left for the Head/the project lead to decide.

## Reviewer attack points

1. A request that reaches the store with a field outside the five (`archived`, `ref`, `sort_order`, `project`): refused by `_fields`.
2. Standing text with script, event attributes, `javascript:` links, over-long text.
3. Another project's use case, a missing one, a non-string id: same words, nothing written.
4. Undo from another route or project; undo twice; undo after a later change (left as it is, said in words).
5. The eye with a bool, a float, a string.
6. Undo words quote no text (standing, headline).

## Landing after the report-row changes (#67)

The report-row changes (the eye, the picker, titles and inserts) are on main, so this branch was merged with them. Every conflict
in `changes.py` kept both sides: the use case kind and the report-row kinds are separate entries; the use case dispatch stays
first in `_do_change`, ahead of the new-row line, so a use case is never taken by the work item path; the Undo family check
lists use cases beside the other items; the Undo words and the reply carry both the use case and the hidden ids. One existing
assertion in `tests/test_changes_hidden.py` changed: a use case put back in a picker step is worded by its name and the
dashboard ("is off the dashboard again"), as for any use case Undo, while the hidden row beside it still says the report.
