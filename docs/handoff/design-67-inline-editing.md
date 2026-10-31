# #67 Report editor (3 of 3): what is built, what to build, what is blocked

Plan for the wiring step of #67, read against `origin/main` (bea276b). Nothing here is a design change: it sorts each Done-when
item into built, to build here, or blocked. A guarded file (`changes.py`, `store.py`, `server.py`, `publish.py` scan, schema) is
not touched on this branch.

## Per Done-when item

| # | Done-when | State | Where / blocker |
|---|-----------|-------|-----------------|
| 1 | Inline edit saves at once through `/api/change` as one step; a server test reads `item_events` joined to `change_log`, newest first | Part built; part to build; part blocked | Built: a section title (`edit/Title.jsx`, `actions.rename`) and the work item fields in `changes.CHANGE_KINDS` (status, owner, due date and so on). To build here: the server test for the history read on a work item edit (`history.history` is unguarded). Blocked: headline, a work item's title, use case standing have no kind in `CHANGE_KINDS` (guarded `changes.py`); a use case edit waits for PR #182 (`team-a-164-usecases-edit`) |
| 2 | Rich fields use `clarkEditor()`; plain cells use the same save path; a reload shows the value | Blocked | #66: PR #53 (`team-a-66-wiring`, cleanHtml only, unmerged) is not the editor. No `clarkEditor` is in the page, and a text section's body is not drawn in Edit (`Section.jsx`). Needs #66 wired first |
| 3 | The eye on a row writes `report_hidden`; row greyed with Undo toast, then leaves the editor | Blocked | `changes.py` has no `report_hidden` kind (the table, keys and rules are already in `store.py`). Needs a guarded `changes.py` addition: kind `report_hidden`, ops new and delete, undoable |
| 4 | Undo of the eye by `/api/undo`; a later change to the row is skipped and named | Blocked | Same guarded change (`UNDOABLE` entry and the words) |
| 5 | Publish after an eye click: hidden row absent from the file | Blocked (test) | `publish.select` already drops `report_hidden` rows and #39's check exists; the test needs the eye's write route (item 3) |
| 6 | Picker: hidden rows never in "already on the page"; "Add from your project record" lists only hidden rows, searches, several at once, one step with Undo; Add also sets `client_visible=1`; Sensitive rows never offered; picker data only in the editor | Logic built, wiring blocked | Built: `logic/picker.js`, `components/Picker.jsx` (PR #42). Wiring needs the same guarded `changes.py` change as item 3, plus one step that deletes the `report_hidden` row and sets `client_visible` to 1 |
| 7 | A click on a row outside an editable field, the eye or the ID fires the open-peek call with that id; a click inside a field does not | To build here | `stores/report.js` `openPeek` exists; `components/WorkItems.jsx` rows do not call it. The peek itself is #42 |
| 8 | The minimap lists every visible section and none hidden; hiding or adding updates it; a click scrolls to the section (top in view) | To build here | `components/Minimap.jsx` and `logic/minimap.js` are built (PR #42) but not drawn by `Dashboard.jsx` |
| 9 | The sticky bar stays visible after scrolling at 1400 and 900 px | To build here (test) | `.top` in `shell.css` is already `position: sticky`; no test measures it |
| 10 | In View no eye, picker or editable field; the published page has the minimap and no editing | To build here | View check is `tests/_editor_checks.py` (built); the minimap goes in the same `Dashboard`, so `page-view.html` has it. Add the tests |
| 11 | Every new route passes #33's "every route is authorised" test | Nothing to do here | This branch adds no route. Items 3 to 6 add none either: they are new kinds on `/api/change` |
| 12 | Insert kinds for actions, RAID, decisions, milestones and use cases, ids from `next_id` | Blocked | Guarded `changes.py` (and the page forms); not started |

## Branch base

`origin/main` only. PR #104 (`team-a-101-handle`, the gutter control) rewrites `Handle.jsx`, `Options.jsx` and
`tests/test_report_editor.py`, and holds no eye. PR #53 holds only cleanHtml. Neither is needed for what is built here, so
nothing is stacked. The new tests are in a new file (`tests/test_inline_67.py`) so they cannot conflict with either PR.

## Built on this branch

- Items 7 to 10 and the server test in item 1, with the tests listed in `tests/test_inline_67.py`.

## Needs the owner or the Head (guarded)

- Items 1 (headline, work item title, use case standing), 3, 4, 5, 6 and 12 need additions to `src/clark/changes.py`
  (`CHANGE_KINDS`, `UNDOABLE`, the words), which is a guarded file. Item 2 needs #66's wiring.
