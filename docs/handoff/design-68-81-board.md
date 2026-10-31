# Design note: #68 Work items board and Group by, #81 board full screen (guarded changes needed)

Written 28-10-2026, before the build. Sources: #68 and #81 (bodies and comments, including the lead's quotes), BRD FR-41 and FR-42, the prototype at `origin/pm-brief-and-prototype` (`system/prototype/views.js` lines 696 to 834, `app.css` lines 161 to 180 and 971 to 1007, `selftest.js` lines 451 to 464; it is local to that branch and **absent from `main`**, so read it with `git show`), creaite v2.6.9's BRD rows FR-89, FR-110 and FR-116 and its `sprint-work-views` plan, and this repo at `dad989e`: `workItems.js`, `components/WorkItems.jsx`, `router.js`, `changes.py`, `store.py`, `schema.sql`, `server.py`, `shell.css`, `page.html`. Also `design-36-work-items-list.md` and `design-95-drag-sections.md` (on `origin/team-a-95-drag`, not yet on `main`). **Not found:** `DESIGN-SYSTEM.md` (there is no such file here; tokens come from `page.html` and `shell.css`), and no "FR-43c" or "we never delete, we archive" text in `docs/`. The rule is real in code: `archived` is set only by archiving and `refuse_archived_field` turns it away from an edit, and a closed item has `Cancelled`. **#42 (the peek) and #64a (the filters) are not on `main` either.** **Part of this needs a guarded change (section 2), so this note stops there for the lead's approval of the diff.** No code or test is written.

## 1. The data
`GET /api/data` gives `actions`, `raid` and `decisions` (archived rows left out), `workstreams`, `milestones`, `use_cases` and `labels`. `rowsOf()` (#36) makes one row list but drops what a move needs; the build keeps, for each row, `table` (`actions`, `raid`, `decisions`), `workstream`, `milestone_id` (it keeps only the name today), `owner`, `priority`, `status`, `client_visible`, and the date and the date's column (`due_date`, or a decision's `needed_by` while Pending). That is `workItems.js`, which is not guarded.

**What each kind has** (the schema is the rulebook, so a drop is offered only where the column exists):

| Column | Action | Risk, Issue, Assumption, Dependency | Decision |
|---|---|---|---|
| Status | Open, Delayed, Closed, Cancelled | Open, Closed, Cancelled | Pending, Made, Withdrawn |
| Workstream | yes (an active one, or blank) | yes | **none** |
| Owner | `owner` (`TBC` when unset) | `owner` | `made_by` |
| Due | `due_date` | `due_date` | `needed_by`, Pending only |
| Priority | set directly | **worked out** from impact and likelihood | none |
| Milestone | yes, or none | yes, or none | **none** |
| Type | fixed | fixed | fixed |

**Group by** (the issue's list; the prototype's `GROUPS`): Workstream, Status, Due, Owner, Priority, Milestone, Type, and **Nothing for the table only**. On the board "Nothing" is not offered, and a saved "Nothing" reads as Status. It sets the table's groups and the board's columns. Workstream is also a filter (the chips from #64a). Default: Workstream (table), the same choice on the board.

**Columns** (a column for every value, so no card can vanish):
- **Status:** the statuses of the kinds shown (the type filter and Open/Closed/All narrow it). One column per word, so Open holds actions and RAID items together; Pending, Made and Withdrawn are columns of their own.
- **Due:** Overdue, This week, Next week, Later, No date. The week ends on Sunday. A decision that is not Pending goes in No date. Closed items are in the list only when Show is Closed or All, and then sit in their date column drawn quiet.
- **Owner:** the signed-in person first ("(me)"), then by number of items, then name, then **No owner** (`TBC`).
- **Priority:** Urgent, High, Medium, Low, then **Not rated** (a risk with no impact or likelihood, and every decision). The prototype has no such column and would lose the decisions.
- **Milestone:** each milestone in order, then **No milestone**. **Workstream:** each active workstream, then **No workstream** (all decisions are there). **Type:** Actions, Risks and issues, Decisions.
- A column keeps its place when empty ("Nothing here"), so it can be dropped on.

**Swimlanes:** one level, Workstream or Type, chosen on the bar above the board (default None; the group already chosen is not offered). A card is in the lane of its own value. Lanes list **every active workstream** (and "No workstream" when it holds a card) so an empty lane can be a target; the prototype lists only populated ones (question 6). The counts in a lane heading and a column heading are the cards shown there, after the filters and search.

## 2. The guarded changes, and why
Today `/api/change` knows one kind: `report_sections`. Nothing in the page can edit a work item. #68 needs the first work item edit, and so does #42's Sneak peek, so **whichever lands first owns this change and the other reuses it**.
1. **`changes.py`: `CHANGE_KINDS` gains `actions`, `raid` and `decisions`, `update` only** (no `new`, `move` or `delete`). The allowed fields, each also checked as a column: actions `status`, `workstream`, `owner`, `priority`, `due_date`, `milestone`; raid `status`, `workstream`, `owner`, `due_date`, `milestone` (**no `priority`**: it is worked out, `store._derive_raid`); decisions `status`, `made_by`, `needed_by`, `date`. The request is the existing one: `{"project":"ABC","kind":"actions","op":"update","id":"ABC-A-003","changes":{"status":"Closed","workstream":"Data"},"place":"board"}`. **Several fields in one `changes` object are one row update and so one step with one Undo, which is how a lane and a column move in one step. No `flags`-style new key is needed.**
2. **`PLACES` gains `"board"`** (and `"peek"` if #42 has not added it), so the step records where the change was made.
3. **`_do_change` and `_eligible` are section-only today.** `_do_change` reads the sections and looks up `id` among them; `_eligible` accepts only keys starting `ABC-S-`. Both need a branch for work items: the id must be a row of **this project's** table (another project's and a missing id get the same words, as now), and `_eligible` accepts a step whose rows are all in these tables, are this project's, and came via the dashboard. The reply carries the changed row (not the sections). `words()` already describes a field change; it needs plain words for these fields ("ABC-A-003 is now Closed").
4. **`store.py`: nothing.** `Step.update` already runs every rule: `CLOSING` fills or clears `closed`, a `Made` decision needs its date, a `Made` decision can't go back to `Pending` (`_check_decision`), a workstream must be active (`_item_workstream`), a milestone must be this project's, `archived` can't be set. **Not changed, not loosened.**
5. **`server.py`: nothing** (the route, token, body limit of 16 KB and the Host check are as they are). **`publish.py`: nothing**, unless the board is put on the published page (question 5).
6. **There is no delete path.** No op, button, column or key deletes an item. The nearest thing, a Cancelled column, is a status change. A request with `op: "delete"` for these kinds is refused as today ("That isn't a change clark can make."), and a test pins that. Archive stays with the archiving flow, which is not part of this issue.

**The one rule the server does not hold: "a due date is never in the past".** The store accepts any real date (the peek must be able to enter a past one). The board's picker enforces it with `min = today`, and the build says so in the note to the reviewers. See question 3.

## 3. The card
Fields, from #68: **type** (the word, as #36's badge: Action, Risk, Issue, Assumption, Dependency, Decision, using `.type.k-*`), **ID**, the **client eye** (shown only when `client_visible`, an icon with the tooltip and screen-reader text "Shown to the client"; display only, question 4), the **title** (three lines, then cut with an ellipsis, full text in the peek), **owner initials** (`.av`, 26 px, the full name in `title` and as hidden text; none for `TBC`), **due in words** (`dueCell`: "3 days late" in red text, nothing for a closed item) and the **state pill** (`pillOf`). A **Move to…** button (a quiet "more" icon, faint until the card is hovered or focused, as #101's grip) sits at the top right.

Look: a white card on a white column with the `--shadow`, `--grey-200` border and `--radius`; **white columns, not grey** (the lead, 28-10-2026). The selected card (the one in the peek) has a `--brand-blue` border. Dragging dims the card to 0.5. Sizes: text 13 px or more (`--size-small` is the floor). No hard-coded colours: tones come from `--status-*` and `--brand-*`.

**Column headings** carry the state's colour for Status, Due and Priority (the lead, 28-10-2026, #68 comment): a 9 px dot, the label in `--status-*-text`, and a 3 px line along the top. Open and Pending blue, Delayed and This week amber, Overdue and Urgent red, Made and Later green, Closed, Cancelled, Withdrawn and No date grey (the prototype's `TONE`). The colour is never the only signal: the count and the word are there too.

**Column widths and order** (the lead's added scope): width 260 to 640 px, default 272, from a handle on the column's right edge (drag, or Left and Right Arrow in 16 px steps, double-click resets), remembered per grouping; order by dragging a heading onto another column, or Alt+Left and Alt+Right on a focused heading, remembered per grouping. The handle is a `role="separator"` with `aria-valuemin`, `aria-valuemax` and `aria-valuenow`, as the prototype.

## 4. Moving a card: the rules, the refusals, the request
A card moves by **dragging** (pointer events: a mouse, a pen or a finger) or by its **Move to…** menu (the keyboard path; drag is never the only way). The menu lists "Move to <group>" with every column the card can go to, then, when a lane is chosen, "Move to <lane>". A column or lane the card cannot go to is **left out of the menu** and refuses when dropped on. A move to where the card already is does nothing, with no message and no step.

One move is one `update` request, with `place: "board"`, one Undo. A move across a lane and a column has both fields in the one `changes` object. The toast says what happened ("ABC-A-003 is now Closed, in the Data workstream.") with **Undo**; a refusal is a "note" toast with nothing to undo. The words are plain and name the item and the reason:

| Group | Drop on | Request `changes` | Refusal (words) |
|---|---|---|---|
| Workstream | a workstream | `{workstream: name}` | A decision: "A decision isn't part of a workstream." A closed workstream isn't a column. |
| Workstream | No workstream | `{workstream: null}` | same for a decision |
| Status | an allowed status | `{status}`; closing sets `closed` to today by the store, reopening clears it | Not for the kind: "A risk can't be Delayed. It can be Open, Closed or Cancelled." A Made or Withdrawn decision: "A decision that has been made can't be moved. Record a new one that replaces it." Pending to Made: see question 2. |
| Due | This week, Next week, Later | asks for a date (clark's own picker: one panel, one Esc, minimum today, default the Friday of that week or today if past); `{due_date}`, or `{needed_by}` for a Pending decision | A past date: the picker will not offer it. A decision that is not Pending: "A decision that has been made has no due date." |
| Due | **Overdue** | **not a drop target** (the column is drawn with `nodrop` and `aria-disabled`; the menu leaves it out) | "Overdue is worked out from the due date. Drop the card on This week, Next week or Later and choose a date." |
| Due | No date | `{due_date: null}` (`needed_by: null`) | none |
| Owner | a person | `{owner}` (`made_by` for a Pending decision) | A decision that has been made: as above |
| Owner | No owner | `{owner: "TBC"}` (`made_by: null`) | |
| Priority | Urgent, High, Medium, Low | `{priority}` (actions only) | A risk or issue: "A risk's priority comes from its impact and likelihood. Change those in its details." A decision: "A decision has no priority." Not rated: not a target. |
| Milestone | a milestone | `{milestone: id}` | A decision: "A decision isn't tied to a milestone." |
| Milestone | No milestone | `{milestone: null}` | same for a decision |
| Type | any | none | "An action can't change its type." (all kinds, by name) |

A lane move adds its field to the same object: Workstream lane `{workstream}` (a decision refused as above), Type lane refused as for the Type column. If **one** half is refused, **neither** is made and the refusal says which. If the server refuses (a stale page, "Your page is out of date. Reload it, then try again."; a busy store), the card goes back where it was and the toast carries the server's words.

**While dragging:** a column that would accept the card shows a `--brand-blue-tint` outline; one that would refuse shows nothing (the refusal comes on drop). The pure function `board.moveFor(row, group, lane, target)` gives `{ok, changes}` or `{ok: false, message}`, and the drop indicator, the menu and the drop all use it, so they cannot disagree.

## 5. Columns: counts, collapse, and what is remembered
- A column heading is a button: click or Enter toggles collapse (`aria-expanded`), a collapsed column is a 44 px strip with its name turned sideways and its count. The collapse applies to the column in **every lane**.
- **Remembered:** layout (table or board), Group by, swimlanes, the collapsed columns, widths and column order, **per project**. Where: `localStorage`, one key (`clark.work.v1`, an object by project code), every read and write in try/catch, the page working with defaults when it is blocked (private window, `file://` of the published file). **Not the address:** the router's `f` is an opaque filter string (600 characters, no parsing, owned by #64a's codec); the layout, grouping and widths are the person's taste, not a place, and none of them should go in a link that is shared or bookmarked. A change of layout or group adds **no history entry** (it never calls `navigate`). The filters and search keep to `f`, as #64a decides.
- **Guarded-file implications:** none. This state is in the browser, not in `clark.db`, so there is no store, changes, server or publish change for it, no backup, and it is not in a step or Undo. It is not carried to another browser or laptop (question 1).
- A saved collapsed column whose grouping or value has gone is ignored, never an error. Widths are clamped to 260 to 640 on read.

## 6. Peek and Sneak peek
- **A click on a card** (not on its Move button, and not the end of a drag) opens the peek: `navigate({...state, item: id})`, one history entry; **with the peek open, another card replaces it** (`navigate` with `replace`, so Back closes the peek, as #63 does for the table). Enter or Space on a focused card does the same. This is #42's contract and the table's.
- The card whose id is in the address has the selected look. The Sneak peek (`//` and plain words) is #42's; it changes the item through the same `/api/change`, and the board redraws from the same data, so a status changed in the peek moves the card to its new column with no board code.
- **Drag never opens the peek**, and the click that ends a drag is ignored.
- **Full screen and the peek:** the peek opens above the board (its layer is above the frozen headings, whose z-index is below 30), the board stays scrollable to its left, and clicking another card moves the peek, in full screen as in the page.
- The peek and the Sneak peek are not built in this repo yet; the board's tests use whatever #42 provides and fall back to checking the address (`item=`).

## 7. Full screen (#81)
- **The icon** is on the swimlane row (the bar above the board, at its right), a `button` with `aria-pressed`, the label "View full screen" or "Leave full screen" and a tooltip ("(Esc)" on the second). Esc or the icon leaves.
- **What changes:** the top bar and the page heading are hidden and the board's area fills the window (`body.board-full`; the top bar's height token becomes 0). **Kept:** the page picture and colours (the `body` background and tokens are not touched), the filters and the Swimlanes control, which are the first things in the scrolling area and **scroll away** as the board scrolls (the lead's "they scroll away"), and the peek.
- **Scrolling:** the full-screen area is the one scroll container (`overflow: auto`, `overscroll-behavior: contain`, height 100vh), so the page behind it does not scroll. **Frozen headings:** a lane heading is `position: sticky; top: 0; left: 0` and a column heading `position: sticky` under it (`top: var(--lane-h)`, a fixed 40 px). Each lane is wrapped in its own element, so its headings stick only while that lane is on screen and the next lane's take over. With no lanes, the column headings stick at `top: 0`. A heading has an opaque background so cards do not show through. The heading's z-index (3) stays below the peek, menus and the date picker.
- **Space at the bottom** (the lead: "to not cut into ticket items"): the area has `padding-bottom` of at least 48 px plus the safe-area inset, and `scroll-padding-bottom` the same, so the last card of the longest column can be scrolled clear and focus never leaves it under the edge. The same applies outside full screen, where the board has its own scroll (`max-height: calc(100vh - var(--topbar) - 16px)`).
- **Columns show every card:** columns have no height cap and grow with their cards (no inner scroll in a column); one scroll only.
- **Esc:** it closes the innermost thing first (a menu or date picker, then the peek), and leaves full screen when none is open. So Esc from a peek over a full-screen board closes the peek only (question 7).
- **Focus:** on entering, focus stays on the icon; on leaving, it returns to the icon. Full screen is not remembered (it is a moment, not a taste), and survives a layout redraw (a move) because the class is on `body`, not on the board.

## 8. Keyboard and screen reader
- The board is a `region` named "Work items board". Each column is a `section` with its heading (the button) and a list of cards; each card is a focusable `article`-as-button with the label "<ID> <title>" and its status in words, so a reader says "ABC-A-003, Update the data map, Open, due in 3 days". Tab goes through the headings and cards in reading order (lane, then column, then card).
- **Move to…** is a real button ("Move ABC-A-003 to…", `aria-haspopup="menu"`); the menu is the app's menu (arrows, Home, End, Esc, Enter) and is the whole keyboard path for a move. Alt+Left and Alt+Right move a focused column heading; the width handle takes Left and Right.
- **A live region** (`role="status"`, `aria-live="polite"`, always in the page) says the result of each move or refusal once: "ABC-A-003 moved to Closed.", the refusal words, "Showing the board, grouped by Status." on a switch, "Full screen on." and "Full screen off."
- **The switch** is two icon buttons in a `role="group"` named "Layout" (`aria-pressed`), with tooltips Table and Board; Group by is a menu button reading "Group by: Status". Tooltips also work on focus.
- Tap targets: the icon buttons 34 px square; the card's Move button 24 px with a larger hit area. The 13 px floor and the no-hard-coded-colour tests apply.

## 9. Layout: desktop and 900 px
Desktop (1400) and 900 px only (the lead, 15-10 and NFR-5): no 320 or 640 checks, shots or CSS. The board is wider than the window, so it **scrolls sideways inside its own area** (the board's scroll box, not the page: `document.documentElement.scrollWidth <= innerWidth` still holds at 900, as the list test requires). Columns are 272 px by default, so at 900 px about three show. The table keeps #36's layout and the 900 px rule that it may not scroll sideways. Collapsed strips and the width handle are the same at both.

## 10. Where it meets other work
- **#36 (list)** supplies `rowsOf`, `dueCell`, `pillOf`, `ownerOf` and the type words; the build adds `board.js` (pure logic: `groups`, `columns`, `lanes`, `moveFor`, `statusFor`) next to them in `src/clark/page/src/logic/`, and the card and board components in `components/`. The table keeps #36's rows; Group by adds collapsible group headers with counts to the table (open or closed remembered).
- **#31 (one writer, Undo):** the work item update is a store step like the sections'. This is where section 2 matters.
- **#42 (peek):** section 6; also shares section 2's `changes.py` change. If #42 lands first, #68 only adds `place: "board"`.
- **#64a (filters):** the board is drawn from the filtered, searched list the table uses. #64a owns `f`; the board reads the same result and adds no filter of its own.
- **#95 (drag sections):** its placement pattern is pointer events through `edit/drag.js` (threshold, capture, indicator from a pure function, the drag started by a handle). The board uses the **same helper** if it has landed, with a card as the handle. If #95 has not landed, #68 writes the generic helper (`start`, 4 px threshold, `onMove`, `onDrop`, `onCancel`) and #95 adopts it; the two must not each keep a copy (question 8).
- **#101 (quiet grip and menu):** the card's Move button follows its look (faint, then solid); no code is shared.
- **#81 (full screen)** extends #68 and is built in the same change; it adds the bar's icon, `body.board-full`, and the sticky headings. It touches no guarded file.

## 11. Tests, one for each Done-when line
**Pure logic** (`tests/test_work_board.py`, headless Chrome, logic bundled by the pinned esbuild, as `test_placement.py`): `columns` for each Group by with counts, including the extra No owner, Not rated, No milestone and No workstream columns and decisions in each; `moveFor` for every row of section 4, each refusal's words, the two-field lane move, "Overdue is not a target", "No date clears", a past date never offered; no result that sets `priority` on a risk, a status the kind lacks, or a `delete` op.
**Changes** (`tests/test_changes.py`, after approval): a work item `update` is one step and one `apply_id`; a status and a workstream together are one step, and Undo restores both; closing fills `closed` and reopening clears it; `priority` on a risk, a `Made` to `Pending` decision, an inactive workstream, another project's milestone and another project's item are each refused in words with nothing changed; `new`, `move` and `delete` on a work item kind are refused; a past `due_date` **is accepted** (pins that the rule is the page's); a request for a section still works as before; Undo of a work item step works from the board and not for another project's.
**Browser** (`tests/test_work_board_browser.py`, 1400 and 900 px, the real page and server):
1. *Table or board icon, tooltips, remembered.* Switch, reload, same layout; blocked storage still works with defaults.
2. *Group by replaces the workstream dropdown, sets groups and columns; workstream is a filter.* Each option; "Nothing" only for the table.
3. *The board as creaite's.* Cards show type, ID, eye, title, initials, due words and state; one level of lanes by workstream and by type; the filters and search change the cards and the counts.
4. *Drag and Move to… are one step with Undo; lane and column in one.* A drag, the menu, and a cross-lane drag, each checked against the database's step count; one Undo each puts it back; the refusals (a decision to a workstream, Delayed on a risk, priority on a risk, a Made decision, Type) leave the database unchanged and show their words.
5. *Due asks for a date, never past; Overdue not a target; No date clears.* The picker's earliest day is today; Overdue neither takes a drop nor is in the menu.
6. *Counts, collapse, remembered.* Collapse in two lanes at once; reload; the same columns are shut; widths and order survive a reload.
7. *A card opens the peek; another card moves it.* The address `item=` changes, replacing; a drag does not open it.
8. *#81:* the icon is on the swimlane row; full screen hides the top bar, keeps the background and the filters (which scroll away); lane and column headings stay in view after scrolling (their rectangle stays at the top); the last card has at least 48 px below it; a click opens the peek in full screen; Esc and the icon leave, and focus returns to the icon; no sideways page scroll at 900.
9. *No delete anywhere:* a test reads the board's source and requests for `delete` and for the word "Delete" in its controls.

## 12. Open questions (for the lead; a default for each)
1. **Remembered state: `localStorage` per project (recommended) or in the address?** The address would make a link carry the view and sit beside `f`, which #64a owns. Default: `localStorage`, `f` left to #64a. Not carried between browsers.
2. **Pending decision dragged to Made.** The store needs the date. Recommend one step `{status: Made, date: today}` with the toast "Made, dated today"; the date is changed in the peek. Alternative: open a Record-the-decision form (creaite). Also: stricter than the store, a Made or Withdrawn decision never moves (creaite's rule); the store allows Made to Withdrawn. Default: today's date, and Made or Withdrawn stay put.
3. **Past due dates:** keep the "never past" rule in the page only (recommended; the peek must still allow them), or also in `changes.py` for `place: "board"`? Default: page only.
4. **The client eye on a card:** display only (recommended), or a working toggle as in the table? Default: display only.
5. **Board on the published and client page?** Drag is an editing act. Recommend the published file keeps the table with Group by headings and no board in v0.3. Default: no board there.
6. **Lanes:** all active workstreams (recommended, so an empty lane can be a target) or only those that hold a card (the prototype)? Default: all.
7. **Esc order in full screen over an open peek:** the peek first (recommended), then full screen. Alternative: Esc always leaves full screen. Default: the peek first.
8. **Who writes the drag helper if #95 has not landed:** #68 writes it generically (recommended) or waits for #95. Default: write it, #95 adopts it.
9. **Guarded diff (section 2):** approve the `changes.py` work item kinds, the `"board"` place, and the `_do_change` and `_eligible` branches, with the tests that change. And who owns it, #68 or #42. Default: whichever merges first; this note's diff is ready to hand over.
