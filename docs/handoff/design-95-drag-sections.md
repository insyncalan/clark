# Design note: #95 Rearrange the dashboard by dragging sections (guarded changes needed)

Written by a teammate, 28-10-2026, before the build (`Team/01`). Sources: #95 and its prototype comment (`bf7dca4`), FR-14a and FR-14b in the BRD, `system/prototype/views.js` (`secRows`, `placeSec`, `stepSec`, the drag code in `wireSections`) and `selftest.js`, and this repo at `91f4a8b`: `changes.py`, `store.py` (`_section_rules`), `order.py`, `publish.py`, and the page's `edit/` folder, `Dashboard.jsx`, `Section.jsx` and `shell.css`. #101 (the quiet grip and menu) and #96 (Add a template) are not built here. **Two things need a guarded change (section 2), so this note stops there for the owner's approval of the diff.** What is already built without one: `src/clark/page/src/logic/placement.js` and its tests (section 10).

## 1. The data model today
- **One row per section** in `report_sections`: `id`, `type`, `title`, `body`, `beside` (0 or 1), `hidden` (0 or 1), `sort_order`. There are no rows, columns or pair tables.
- **A row of the page is made by reading the list in order** (`slots()` in `Dashboard.jsx`; `secRows` in the prototype): a section with `beside = 1` that has a section after it shares its row with that next one, and the pair is closed. So `beside` means "shares its row with the next section". The next one's own flag is ignored, a flag on the last section is ignored, and pairs never chain. **Any list of flags therefore reads as valid rows of one or two. A row can never hold three.**
- **The cover is not a section.** It is the heading above the sections (client name, project, the counts). It cannot be dragged and nothing can go above it. Dropping above the first section puts the section first. The cover-led layout and "At a glance is not draggable inside the cover" belong to #46, which is in the backlog; Boxed is the only layout (FR-4), so every section can be dragged.
- **Hidden sections** are drawn dimmed in Edit and left out of View and the published file.

**What must change in the data: nothing.** The existing `beside` flag does it for every section type, and no column is added. Two rules in the code must change (section 2), and one bug (below) must be fixed.

**A bug today, the same in View and in the published file.** `Dashboard.jsx` drops hidden sections first and then reads the pairs, and `publish.py` does the same (it leaves hidden sections out and copies each `beside`). So with A beside B and B hidden, Edit shows A with B, but View and the published file show A beside C (the section after B). The prototype's rule is right: read the rows from **all** sections, then take out the hidden ones; a pair with one half hidden shows the other full width. `placement.rows(sections, keep)` does this. The build uses it in `Dashboard.jsx`, and `publish.py` (not guarded) writes `beside: 0` for a shown section whose partner is hidden (section 7).

## 2. Two guarded changes, and why
Today a change request is one op on one section and makes one step (`changes.py`: `new`, `update`, `move`, `delete`). `move` writes only `sort_order`; `update` writes only that section's `title`, `hidden` or `beside`.

1. **`store.py`, `_section_rules`: remove "Only a text section can sit beside another."** (two lines). Without it, no section other than text can be placed beside another, and the Done-when line "every section type can be placed" cannot hold. `test_beside_and_body_only_on_a_text_section` (test_sections_store.py) and `test_beside_on_a_section_that_is_not_text_is_refused_in_words` (test_changes.py) are replaced by tests that every type can sit beside another (the owner approves that test change with the diff). The body rule stays: only a text section has a body.
2. **`changes.py`: `move` gains one optional key, `flags`**, so a drop is ONE step. A drop changes the moved section's place **and** up to three flags: the moved section's own, its old partner's (when it was the second half, the first must go back to full width, or it would pair with whatever follows), the section it lands beside, and the one before the place it lands (a stray flag there would pull it in). Today that is two or three requests, so two or three Undo steps. The request:

```json
{"project": "ABC", "kind": "report_sections", "op": "move", "id": "ABC-S-009",
 "before": "ABC-S-010", "flags": {"ABC-S-009": 1, "ABC-S-010": 0}, "place": "report"}
```

   - `flags`: optional; an object of at most 4 entries, each key a section of this project (anything else: "Your page is out of date. Reload it, then try again.", the same as `before`) and each value exactly 0 or 1 (`_flag`, "That must be 0 or 1."). It is the only new key; it can only ever set `beside` (`CHANGE_KINDS["report_sections"]["move"] = ("beside",)`, checked against the table's columns like every other field).
   - In the same `store.step`: the `sort_order` writes from `order.section_slot` as now, then `st.update(table, id, {"beside": v})` for each flag. One `apply_id`, one Undo. A request that changes nothing makes no step (`peek_apply_id()` is `None`, as now), so a move to where a section already is shows no Undo.
   - **No server rule about the shape of the rows**, because any flags read as valid rows (section 1). The server cannot be made to produce a row of three. The page works out the flags (`placement.js`); a stale page gets the same result `move` has today.
   - Undo needs no change: `Store.undo` reverses each field of the step, and `changes.words` already says "the place of …" and "… is full width again". Several lines are folded into "N changes to the sections", as now.
   - **A plain move (no `flags`) is exactly today's request**, so the keyboard moves of a lone section, the existing tests and `moveBefore` keep working.

**Is `placement.js`'s payload what `changes.py` accepts today?** Partly. A move with no flags is. A move with `flags`, and any flag of 1 on a section that is not text, is not: both need the changes above. `placement.js` never sends a flag key unless a flag changes.

**Alternative, not recommended:** a new op `place` instead of `flags` on `move`. The same work and the same tests, one more op in the allow-list and `OP_KEYS`. Recommend the optional key: a plain move stays unchanged.

## 3. The drop targets and the rule for each
The moved section is M. The page works from its list in the order clark sent (`data.report_sections`) with M taken out; M's old partner counts as alone. Rows are read from all sections, hidden ones included (Edit shows them).

| Drop | Where the pointer is | Result | Indicator |
|---|---|---|---|
| **Between rows** | The top or bottom quarter (at most 56 px) of a section, or the gap between two rows | M alone, at full width, in its own row there | A line across the whole row, above or below it |
| **Left or right half of a lone section** R | The middle of R, left or right of its centre | M and R share the row: M on the chosen side, R on the other, 50% each. M goes before R (left) or after R (right) in the order | An outline round that half of R |
| **Onto a pair** (the middle of a row of two others) | The middle of either half | A row never holds more than two, so it is **not** a half drop. It becomes a drop above or below that pair, by which half of its height the pointer is in | The line, as for between rows |
| **Onto the cover** (above the first section) | Anywhere above the first row | M alone, first | A line above the first row |
| **Below the last row** | Anywhere below the last row | M alone, last | A line below the last row |
| **Onto itself** | Over M, or over M's own half | Nothing: no step, no message, no indicator | None |
| **Onto its partner** | The middle of the other half of M's pair | They swap sides (M is on the chosen side of the partner, which is alone once M is lifted). The same side again is "already there": nothing | The outline on that half |
| **Where it already is** (the gap next to a lone M, or the same half again) | | Nothing: no step, no message | None |

Taking one half of a pair to any other target leaves its partner alone at full width: the flag that would have kept the pair is cleared in the same step.

**Refusals, in plain words** (the page never sends these; none is a server error):
- Beside a section that already shares its row, by the keyboard or any path other than the pointer: "A row holds two sections at most. Put it between rows, or beside a section on its own."
- Place beside the next, with no section after it: "This is the last section, so there is nothing to sit beside." With a pair after it: "The next row already has two sections. Move one of them first, or move this section between rows." With M already in a pair: "This section already shares its row. Choose Full width to give it a row of its own."
- Full width, when it already has its own row: "This section already has its own row."
- Move up on the first row and Move down on the last: "This section is already first." and "This section is already last." (the words the page has today).
- Inside a pair (a `before` that is the second half of a pair): not offered by the pointer; refused as "A section can't go in the middle of a pair. Put it between rows."
- A section that is no longer in the list: "That section isn't in the report any more. Reload the page."
- Quiet, no words: onto itself, and where it already is.

## 4. One change step for each move
Every move is one `move` request with `place: "report"` (pointer and Alt keys) or `"menu"` (the menu) and one Undo. `placement.js` returns it; `before` is always the section M ends up directly before (`null`: last), and `flags` lists only the flags that change.

| Move | `before` | `flags` |
|---|---|---|
| A lone section to a full row | the first section of the row it goes above, or `null` | none (usually) |
| Half of a pair to a full row | as above | its partner's flag (or its own) set to 0 |
| A section onto the left of a lone R | R | M: 1, and R: 0 if it was 1 |
| A section onto the right of a lone R | the section after R (or `null`) | R: 1, M: 0 |
| Place beside the next | the next section | M: 1 |
| Full width | M's own next section | the first half's flag: 0 |
| Move up / Move down | by rows, see section 5 | as the result needs |

## 5. Keyboard and screen reader
- **The menu** (Options, until #101 replaces it) keeps Move up and Move down. It already has "Place beside the next section" and "Full width", for text sections only and "Full width" only on the first half; they now work for every type, and "Full width" is offered on **both** halves (on the second, the first half's flag is cleared). An item that cannot apply stays in the menu, marked unavailable, as today, with the refusal above as its reason.
- **Alt+Up and Alt+Down** on the handle (as today) move by **rows**, not by single sections: a section on its own passes the whole neighbouring row (a pair counts as one). A half of a pair steps out of the pair: towards its partner it lands just beside the pair at full width (the first half down goes just below its partner; the second half up goes just above), and away from its partner it goes out and past the next row, at full width. This is the prototype's rule. The partner stays alone, at full width.
- **Focus** stays on the moved section's handle after any move (`keep(…, id, "handle")`, as today), and returns to the menu button after a menu move. A refusal moves nothing and leaves focus where it was.
- **Live region.** The toast is already `role="status"` `aria-live="polite"` and is always in the page in Edit, so each result is read out once. The words say what happened, with the section's title (cut at 40 characters):
  - "Moved Risks and issues beside Open actions, on the left." (or "on the right")
  - "Moved Risks and issues to its own row, above Decisions." / "…, at the end." / "…, at the top."
  - "Moved Risks and issues up." / "Moved Risks and issues down."
  - "Risks and issues is now full width."
  - A refusal is a "note" toast (nothing to undo), as "This section is already first." is today.
- The handle's label already says "Move <title>. Press Alt with the up or down arrow, or drag." It adds nothing about pairs; the menu has them.

## 6. The drop indicator
- **Between rows:** a 3 px line in the brand cyan across the row (both halves of a pair), above it (`.drop-before`, as today) or below the last row (`.secs.drop-end`, as today). The line sits in the grid gap, so nothing moves while dragging.
- **A half:** a 2 px cyan outline over the left or right half of R (`.drop-left`, `.drop-right`; a pseudo-element, so R's own size does not change).
- `placement.indicator(sections, id, target)` gives what to draw (or nothing where the drop would do nothing or be refused), so the indicator and the drop cannot disagree: both come from the same function. The target comes from `placement.targetAt(...)`, which maps the pointer and the sections' rectangles to a target.
- At phone width (below) there is only one column, so a half is not possible and only lines show.
- The pointer's drag uses pointer events, as `Handle.jsx` does today, so a mouse, a pen and a finger all work; BRD FR-14a says "touch screens use the menu", which still holds, but a finger can drag too. The drag moves into `edit/drag.js` (the pointer handling, the moves, the indicator) and `Handle.jsx` only starts it, so #101's new grip calls the same function.

## 7. Phone width, and the published file
- **Stacking.** The page stacks a pair at 900 px and below (`shell.css`, one column), the same breakpoint as the table rules and the no-sideways-scroll test. The prototype stacks at 700 px and FR-14a says 700. See question 1.
- **Any type side by side.** The grid is two equal columns (`slot-left`, `slot-right`, `slot-full`), set by `slots()` with no look at type. Nothing in the CSS or the markup is about text. What each section draws inside half the width is each section's own job (#66, #45 and the others); a table in a half has `min-width: 0` on the section and scrolls in its own box.
- **The published file carries the rows exactly.** `publish.select()` copies `beside` for each shown section, in order. That is right except for the hidden-half bug (section 1): the fix is in `publish.py`, which is not guarded. For each shown section it writes `beside: 1` only when the section after it **in the full list** is shown too and is its partner; otherwise 0. The published page (`page-view.html`) draws with the same `slots()` and the same stacking. No test pins `beside` in the published file today; the build adds them (section 9).
- **Reload.** The flags and orders are in the database, so the layout survives a reload.

## 8. Where it meets other work
- **#101** (the quiet grip and menu) replaces `Handle.jsx` and `Options.jsx`. This build keeps its edits to them small: the handle calls `startDrag()` and the menu calls the same `placement` functions. #101 keeps both calls. #101 must keep the keyboard moves, the menu's four layout items and the focus rules in sections 5.
- **#96** (Add a template) places a new section beside the next one. It should use the same rule: beside only a section that is alone (`placement.beside`'s check), and the same payload shape if it ever changes flags.
- **PR #42 (#67, picker and minimap)** adds `src/clark/page/src/logic/` too (`picker.js`, `minimap.js`). `placement.js` is a new file in the same folder; no file is shared. Its test copies the way `test_picker_minimap.py` bundles the logic (that test is not on main yet, so the harness lines are repeated, not imported).
- **PR #53 (#66 wiring)** touches `Section.jsx` to draw bodies and edits `test_report_editor.py`. The drag build changes the section's class list only (`drop-*`) and `Dashboard.jsx`'s `slots`; expect a small merge in `Section.jsx`.

## 9. Tests, one for each Done-when line
**Pure logic (built):** `tests/test_placement.py`, in headless Chrome with the logic bundled by the pinned esbuild (section 10).
**After approval of the guarded changes:**
1. *Dragged into a new full row, beside another, and out of a pair.* `test_changes.py`: a move with `flags` is one step, one `apply_id`; it changes the place and the flags; a plain move is as before; a flag that is not 0 or 1, an unknown id, another project's id, more than 4 entries or a `flags` that is not an object are each refused in words and change nothing; Undo restores the place and every flag in one go; a move that changes nothing makes no step. `test_sections_store.py`: every type can be set beside another. `test_report_editor.py` (real page, real routes, real store): drag a section to a full row (the request equals the one `placement.js` gave), onto the half of a lone section of a **non-text** type, and one half of a pair away (the partner is alone, full width); the drop line and outline show while dragging and go after; one Undo each puts the layout back; a drop onto itself and a drag of under 4 px send nothing.
2. *The layout survives a reload and is the same in Preview and the published file.* The editor test reloads the page and checks the rows are the same. `test_publish.py`: `beside` is in the published sections for a pair of **any** two types; with one half hidden the other is written with `beside: 0`; hidden between two sections does not pair the two outer ones; and the file drawn in Chrome (`page-view.html`) shows the same rows as View for the same data, including the hidden-half case.
3. *Keyboard moves do the same.* In the same test: Alt+Up and Alt+Down by rows on a lone section, on each half of a pair; "Place beside the next section" and "Full width" (both halves) from the menu for a non-text section; focus on the handle after each; the toast words in section 5 come out of the live region; each refusal is a note and sends nothing.
4. *The self-test covers each placement.* `test_placement.py` has a test for every row of the table in section 3 and every refusal in section 3, and for each payload in section 4, with Undo's shape (the flags that change are exactly those that differ).
5. *Phone width and no regressions.* `test_report_editor.py` at 1400 and 900 px: a pair is two columns above 900 and one column at 900 or below; no sideways scroll; the 13 px floor and the no-hard-coded-colour tests pass with the new classes.

## 10. What is built before approval
`src/clark/page/src/logic/placement.js` (pure; no DOM, no signals) and `tests/test_placement.py` (and its small entry `tests/fixtures/placement_demo.js`):
- `rows(sections, keep)` and `slots(sections, keep)`: the rows as drawn, reading all sections and then leaving out those `keep` refuses (hidden).
- `place(sections, id, target)`: a target is `{before: id|null}` or `{beside: id, side: "left"|"right"}`. It returns `{ok: true, payload, words}` or `{ok: false, why, message, quiet}`.
- `step(sections, id, dir)`, `beside(sections, id)`, `fullWidth(sections, id)`: Move up and Move down, Place beside the next, Full width, as the same kind of result.
- `targetAt(sections, id, rects, point, {columns})`: the pointer to a target. `indicator(sections, id, target)`: what to draw for it.
- `applied(sections, payload)`: what clark will do with the payload, the model the tests use to check that the rows after are the rows meant. It is also what a Python test of the new `flags` can be compared with.

Nothing in the page uses it yet. `tests/test_placement.py` has a test for each row and refusal of section 3 and each change of section 4, a check against a second way of working the rows out (every section, every target, seven layouts including stray flags: the rows after, the refusal, and the shape of each change), and a test that sends the flag-less changes through the real `changes.make_change` and gets the order the logic said. A change with `flags` is not sent to `changes.py` there, because today it refuses it; the guarded build adds that test.

## 11. Open questions (for the Head and the owner)
1. **Stacking width: 900 px (what the page does and its tests check) or 700 px (the prototype and FR-14a)?** Recommend 900: half of 900 is 438 px, narrow for a table; the existing no-sideways-scroll test is at 900. FR-14a's "700 px" would be changed to 900. Default: 900.
2. **Approve the two guarded changes (section 2):** the two-line removal in `store.py` and `flags` on `move` in `changes.py`, with the tests that change. Or `place` as its own op. Default: `flags` on `move`.
3. **Onto the middle of a pair:** a line above or below it (the prototype, and the indicator always shows where it goes), or a refusal while dragging ("A row holds two sections at most")? Default: the line.
4. **Move up and Move down for the half of a pair** follow the prototype (towards its partner it steps out beside the pair; away it passes the next row). Alternative: always step out of the pair first, and move a row only on the next press. Default: the prototype.
5. **Fix the hidden-half bug in this issue (View and the published file pair the wrong sections)?** It is not in the Done-when, but "appears the same in Preview and the published file" does not hold without it. Default: yes, in `Dashboard.jsx` and `publish.py`.
6. **Words** (section 5): "Moved X beside Y, on the left." and "Moved X to its own row, above Y." the owner or the Head to approve the plain words.
