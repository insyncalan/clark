# #67 guarded changes: what each guarded file changes, and where to attack it

Branch `team-a-67-changes` on `origin/main` (bea276b). Approved as one Full-tier diff on #67. Readers: two code readers and the
infrastructure architect, fresh, before merge. No route is added: everything is a kind or an op on `POST /api/change` and `POST /api/undo`.

## Commits (in order, each green on 3.14 and 3.9 before the next)

| # | Guarded file | Change |
|---|--------------|--------|
| 0 | `store.py` | One word: `"report_hidden"` in `REVERT_CREATED`, added on a line of its own (`REVERT_CREATED += ("report_hidden",)`) so it merges with the other pull request that adds a word to the same tuple. Without it an Undo of a hide is skipped ("a new report_hidden can't be removed by an undo") and the eye can never be undone. **This is outside the approved `changes.py`-only diff**; it is its own commit so it can be taken or refused alone. Tests: `tests/test_hidden_store.py` |
| 1 | `changes.py` | Kind `report_hidden`, ops `new` (hide) and `delete` (show): `id` only, checked before any write. `UNDOABLE` entry, `_row_is_ours` / `_eligible` know the pair `CODE\|item`, plain words for the Undo |
| 2 | `changes.py` | Op `pick` on `report_hidden` (`ids`, at most 100): the picker's Add as ONE step: removes each `report_hidden` row and sets `client_visible` to 1 where it is 0. Refuses the whole request for a Sensitive (any excluding label) or archived item, an item already on the page, another project's item |
| 3 | `changes.py` | `update` for a work item's title: `description` (actions, raid) and `decision` (decisions). Same one-line plain-text check as the other item fields; cannot be cleared; not said back in the reply |
| 4 | `changes.py` | `new` for actions, raid, decisions, milestones: the id comes from the store's `next_id` (inside the step), `project`, `raised`, `status` and `source` are clark's |

Not here: use cases (no create path, and their update is PR #182 / #164), a section's rich body (#66), a document's eye (the store's
`_hidden_item` rule does not accept a document id).

## Request shapes (for the page work)

- Hide: `{project, kind: "report_hidden", op: "new", id: "ABC-A-001"}`; show: `op: "delete"`. Reply: `{ok, apply_id, ref, hidden: [ids]}`.
- Add from the picker: `{project, kind: "report_hidden", op: "pick", ids: [...]}`. Reply: `{ok, apply_id, added, shown_to_client, hidden}`. The page says "This also shows it to the client" for the ids in `shown_to_client`.
- Title: `{kind: "actions"|"raid", op: "update", id, changes: {description}}`, `{kind: "decisions", ..., changes: {decision}}`.
- New row: `{kind, op: "new", values: {...}}` with the fields in `CHANGE_KINDS[kind]["new"]`. Reply: `{ok, apply_id, ref, item}`.
- Undo reply for the eye and the picker carries `hidden` (the ids the report hides now) and plain `words`.

## Reviewer attack points

1. **No SQL, no new literal that trips the one-writer test.** `changes.py` still writes only through `Store.step`, `Step.create/update/cancel` and `Store.undo`. `PICK` is a constant built in the existing `split()` line. `test_store_writer` is untouched and passes.
2. **Ids from a request.** `_hidable` (regex `store.ITEM_ID` and `item_table` in the five kinds) runs before any read of the id; every refusal says `ITEM_NOT_MINE` and never quotes the id. Try: another project's id, `ABCD-A-001`, a pair `ABC|ABC-A-001`, unicode digits, a lone surrogate, a list, null.
3. **The pair key in Undo.** `_row_is_ours` accepts `report_hidden` only when the key starts `CODE|CODE-` (the separator keeps project ABC from matching ABCD). `_eligible` treats a step with a `report_hidden` row or a picker note (see 11) and a `client_visible` row as the picker's family; a step with only `client_visible` rows is NOT undoable from here (another route's, e.g. the Work items eye).
4. **Undo of a pick is per field.** A `client_visible` changed later is skipped and named; the `report_hidden` row is still put back. Judge whether that half-undo is acceptable (it is named in the words).
5. **Sensitive.** `_blocked_labels` repeats `publish._excluded_labels` (Sensitive, any label whose behaviour or default choice is exclude). Two copies of one rule: check they agree. A test covers `Sensitive`, `Embargoed` (default exclude), `Commercial` (behaviour exclude) and a warning-only label.
6. **Item kinds in `_eligible`.** `milestones` joins the `items` regexes so a new milestone can be undone; `CHANGE_KINDS[...].get(UPDATE, ())` avoids a KeyError for it. A milestone has no `closed` or `priority`, so nothing else changes for it.
7. **`ITEM_REF` now matches `-M-`** (words only). `HIDDEN_REF` is separate (`A D M U`).
8. **New rows.** `_fields` skips `_item_field_words` for `new` (so a raid can take `type`); every other field not in the list is refused as before. A closed set is checked against `store.ALLOWED` before the store (`NOT_A_CHOICE`). A decision defaults to Pending (the prototype's default); a made one needs its date (the store's words).
9. **Tests changed (none is a guard test):** `test_changes.py` (kinds and ops sets, "no new for a work item", `description` is now editable), `test_changes_archive.py` (the "title edit is not undoable" tests use `client_message`), `test_changes_tiles.py` (the `UNDOABLE` set; `report_hidden` now has an op error not a kind error).
10. **Text in words.** The title undo says "the title of ABC-A-001 is back as it was", never the old text. Item ids are the only names used for the eye.

## Tests

`tests/test_hidden_store.py` (3), `tests/test_changes_hidden.py` (eye, picker, titles, inserts, allow-list). Run on both Pythons:
`python3 dev/run_tests.py test_hidden_store test_changes_hidden test_changes test_changes_archive test_changes_tiles test_store_writer`.

## After review (changes since the first head)

11. **Off but not hidden (was HIGH).** A picker Add of a row with `client_visible` 0 and no hidden row made a step of only `client_visible` and `updated_at` rows, which no Undo family recognised (Undo answered 400 and the row stayed published). That row's update now carries a history-only note ("Added to the report", `PICK_NOTE`), which `_eligible` recognises as the picker's step. A row that was also hidden carries no note (its `report_hidden` row marks the step). A step that only turned a flag on is still refused. Tests: Add then Undo for an action and a milestone, checking the flag and what `publish.select` returns.
12. **Another project's code.** A test hides an `ABCD` item and shows project ABC cannot undo it (kills the `startswith(project)` mutant of `_row_is_ours`).
13. **Replies.** A new row's reply no longer says its title (`description`, `decision`, a milestone's `name`).
14. **Words.** `ITEM_REF` and `_kind_word` know use cases (`-U-`), so a pick that includes one reads "ABC-U-001 is hidden from the client again" and a long one says "changes to the work items". An Undo skipped because something now refers to the row, or other data depends on it, says "Something is linked to it now."
15. **Archived project.** Show, hide, pick and a new row are refused at the top with `PROJECT_NOT_ACTIVE`, writing nothing.
16. **New rows.** `archived` and a risk's `priority` get their plain words (`NO_ARCHIVE`, `NO_RAID_PRIORITY`) on a new row too.
17. **Milestone state gates.** `publish.GATES` lists `state` and `state_set` for milestones, but `publish.select` only reads them (they are not in `keep`), so a milestone with no state is published once `client_visible` is 1. Not a gate for the picker; no change.
