# Build spec: #36 Work items list (read only)

Written by a teammate's agent, 28-10-2026, as groundwork. #36 depends on #35 (page shell, not built) and #30 (demo data, in progress), so the page cannot be built yet. This spec is what can be settled now. Fixtures: `tests/fixtures/work-items-list-cases.json` (37 due/pill cases, 5 colour cases, 8 owner cases, one sort case).

**Sources read** (all read-only): #36's issue; #64's issue; BRD FR-40, FR-41, NFR-5; `docs/handoff/data-model.md`; `store.py` `data_for` at `origin/team-a-31-store` (dd71e30); `server.py` at `origin/team-a-33-server` (2c3ed6b); `dev/demo_data.py` at `origin/team-a-30-demo-data` (bf92168); the prototype's `db.js`, `core.js`, `views.js`, `app.css` (working tree); `comms/mockups/work-items-filters/findings.md`; creaite v2.6.9 `core/page.js`, `core/data.js`, `work.js`, `meetings.js`.

**Done when** (#36): the view lists one project's actions, risks, issues and decisions from `/api/data`, with type, owner, due date in words, status and priority, as in the prototype's screens; a browser test at 1400 and 900 px finds every demo row; no editing.

## 1. What `/api/data` gives today

`GET /api/data?project=CODE` returns `{"ok": true, "project": CODE, "data": {...}}`. `data` has these keys, from `data_for`: `project` (one row), `milestones`, `workstreams`, `actions`, `raid`, `decisions`, `use_cases`, `links`, `labels`. Lists hold full table rows (`SELECT *`, `archived = 0` only; milestones and use cases by `sort_order, id`, the rest by `id`). `labels` is `{item_id: [label, ...]}`. 400 for a bad code, 404 for no such project, 403 for a missing or stale token.

| List | Columns the list uses (data-model.md) |
|---|---|
| `actions` | `id`, `description`, `workstream` (a name), `owner` (default `TBC`), `priority`, `due_date`, `status` (Open, Delayed, Closed, Cancelled), `closed`, `milestone` (an ID), `use_case` (an ID), `client_visible` |
| `raid` | `id`, `type` (Risk, Assumption, Issue, Dependency), `description`, `workstream`, `owner`, `due_date`, `impact`, `likelihood`, `priority` (worked out; null if either is unset), `status` (Open, Closed, Cancelled), `closed`, `milestone`, `use_case`, `client_visible` |
| `decisions` | `id`, `decision` (the text), `made_by`, `status` (Pending, Made, Withdrawn), `needed_by`, `date`, `use_case`, `client_visible`. **No** workstream, owner, priority or due column |

**Gaps in `data_for` for the list.** None blocks the rows; two need a decision.
1. **The page does not know which project to ask for.** `clark-boot` carries only `{"token"}` (server.py `with_boot`), and there is no route that lists projects. Needed: the boot block (or a `GET /api/projects`) gives `{code, name}` for each project and a default. Owner: #33's server (a teammate, guarded) with #35 for the switcher. Until then #36 reads the code from the address, as the prototype does (`#work&p=TUL`).
2. **No "today" from the server.** The page uses the browser's date. The demo dates are offsets from `CLARK_NOW`, so the browser test must run with the same date (section 6). Adding `today` to `data_for` would be a `store.py` change (guarded, under review); not recommended (Q8).
Not gaps: milestone names (map `milestone` through `data.milestones`), use case references (`use_case` through `data.use_cases[].ref`), owners (plain text names, no user table needed).

## 2. The row model

The page turns each list into one array of rows with a `kind`: `action`, `risk`, `issue`, `assumption`, `dependency` (lower-cased `raid.type`), or `decision`.

| Column | Action | Risk, Issue, Assumption, Dependency | Decision |
|---|---|---|---|
| Item (title) | `description` | `description` | `decision` |
| Type | "Action" | `raid.type` in words | "Decision" |
| Meta line | `id` · "UC " + use case `ref` · milestone name · workstream (each only if set) | same | `id` · "UC " + `ref` |
| Owner | `owner` | `owner` | `made_by` |
| Due (the date) | `due_date` | `due_date` | Pending: `needed_by`; Made or Withdrawn: `date` |
| Priority | `priority` | `priority`, or "—" if null | "—" (decisions have none; the prototype showed "Medium" only because its items all carry a default) |
| Status pill | section 5 | section 5 | section 5 |
| Client | static "Client" tag if `client_visible` | same | same |

- **Type badge.** The prototype used one letter (A, R, I, D). Assumption and Dependency would clash with A and D, so #36 shows the word in the badge, coloured as the prototype's `.type` classes: Action blue, Risk amber, Issue red, Decision green; Assumption and Dependency grey (Q2).
- **Open and closed.** Open = action Open or Delayed; RAID Open; decision Pending. Closed = Closed, Cancelled, Made, Withdrawn (prototype `C.isOpen`; creaite `OPENST` and `CLOSEDST`).
- **Sort** (Q5): open rows first; then the row's date ascending (no date last); then `id` ascending. The date is the Due field above. Fixture `sort` checks it. Closed rows keep the same rule, below the open ones.
- **No filters yet.** All of the project's rows are listed, so the browser test can find every row. Closed rows are drawn quieter (grey pill, no words), not hidden.
- **Dates** are shown DD-MM-YYYY (RULES.md); stored YYYY-MM-DD never reaches the screen.

## 3. Due date in words

Copied from the prototype's `C.dueWords`, which is a copy of creaite's `rel` (core/page.js v2.6.9). `n` = whole calendar days from today to the Due date (`due - today`, both read as plain dates, so a clock change never moves a count).

| `n` | Words | Class on the words |
|---|---|---|
| 0 | Today | none |
| 1 | Tomorrow | none |
| 2 and over | In n days | none |
| -1 | Yesterday | `late` |
| -2 and under | n days late | `late` |

The cell is two lines: the date (or "—") and the words under it (prototype `.due-l`, 12 px, muted; `late` is `--status-red-text`).
- **Words and `late` appear only for an open row** (creaite `OPENST`; the owner's review in findings.md lists "a closed item still says 9 days late" as a fault). A closed, cancelled, made or withdrawn row shows its date and nothing under it (Q3).
- **No date:** "—" and no words (creaite's `rel` says "No date"; the prototype's table shows "—"; the table follows the prototype).
- **A stored date that is not a real day** (the database's check accepts `2026-02-30`): show it as stored, DD-MM-YYYY, no words.
- Weeks and months are not used: "In 30 days" stays "In 30 days" (prototype and creaite have no week or month wording).
- The prototype's peek also has a short form (`Due soon` within 7 days); that is the pill (section 5), not the words.

`todayIso()` is the only place that reads the clock (section 6). The fixtures (`due_and_pill`) hold 37 cases at today = 2026-10-28; some carry their own `today` for the clock-change and leap-day days:

| Group | Cases (name in the fixture) |
|---|---|
| The five steps | today, tomorrow, in 2 days, yesterday, 2 days late |
| The pill edges | in 7 days (Due soon), in 8 days (Open), 7 days late |
| Long spans | 30 days, 400 days, month boundary (to 01-11-2026), year boundary (to 01-01-2027) |
| Clock and calendar | 25-10-2026 clocks back, 29-03-2026 clocks forward, 29-02-2028 leap year, a date that is not a real day |
| No date, closed | action with no date; closed, cancelled with and without dates; risk closed; issue cancelled |
| Each kind | action Open and Delayed; risk, issue, assumption, dependency; decision Pending (ahead, late, no date), Made (with and without an old `needed_by`), Withdrawn |

## 4. Priority and colour (D-12)

A risk or issue's colour is its priority; there is no RAG column (data-model.md open point 2, decided; BRD FR-40). Colours are the prototype's tokens: `--status-red`, `--status-amber`, `--status-green` and their `-tint` and `-text` pairs.

| `priority` | Colour | Pill word | Pill class |
|---|---|---|---|
| Urgent | red | Red | `r` |
| High | red | Red | `r` |
| Medium | amber | Amber | `a` |
| Low | green | Green | `g` |
| null (impact or likelihood unset) | grey | Not rated | `n` (Q7) |

The Priority column always shows the word (Urgent, High, Medium, Low), never the colour name. The colour pill applies to Risk and Issue only (FR-40); Assumption and Dependency show the stored status in a blue pill ("Open"). Closed or Cancelled RAID rows are grey with the status word.

## 5. Status pill (prototype `C.look`)

| Kind | Rule, in order | Word, class |
|---|---|---|
| Action | Closed or Cancelled | the status, `n` |
| | due date before today | Overdue, `r` |
| | status Delayed | Delayed, `a` |
| | due within 0 to 7 days | Due soon, `a` |
| | otherwise | Open, `b` |
| Risk, Issue | Closed or Cancelled | the status, `n` |
| | otherwise | the colour (section 4) |
| Assumption, Dependency | Closed or Cancelled | the status, `n` |
| | otherwise | Open, `b` |
| Decision | Made / Withdrawn / Pending | Made `g` / Withdrawn `n` / Pending `b` |

The pill states are worked out (Overdue, Due soon), while a later Status filter lists stored statuses; findings.md calls that mismatch a problem (point 5). #36 copies the prototype (Q6). Class names `r a g b n` and `.pill` follow the prototype; the colour word is never the only signal: the pill carries a text word and the dot is decoration.

Owner (fixtures `owner`): initials are the first letters of the first two words, upper case (`C.initials`); "TBC", empty or null show no circle: "TBC" or "—" in muted text.

## 6. How the page gets its data

1. Read the token: `JSON.parse(document.getElementById("clark-boot").textContent).token`.
2. `fetch("/api/data?project=" + code, {headers: {"X-Clark-Token": token}, cache: "no-store"})`. Same origin, GET, no cookies. The page never writes the token anywhere (no storage, no URL).
3. On `{ok: true}`, build the rows (section 2) and draw. Keep `data` in the page's signals store (#35's layout) so later items read the same copy.

Plain words on screen (British English, no codes; the server's own `message` is used where it has one):

| Moment | Words |
|---|---|
| Loading | "Loading work items." (a polite status line; the page below it does not jump) |
| 200, no rows | "This project has no work items yet." |
| 403 with `stale: true` | the server's text: "The server was restarted since this page was opened. Reload the page (Cmd+R) and try again." |
| 404 | "There is no project with that code." |
| 400 | the server's message |
| No project chosen | "Choose a project to see its work items." (until Q1 is settled) |
| Network failure or non-JSON | "clark could not reach its server. Check that it is still running, then reload the page." with a "Try again" button |
| Any other failure | "The work items could not be loaded." plus a "Try again" button |

## 7. Test plan

**Unit (plain JS).** The functions live in one DOM-free module, `src/clark/page/workItems.js` (`rowsOf(data)`, `dueCell(row, today)`, `pillOf(row, today)`, `colourOf(priority)`, `ownerOf(name)`, `sortRows(rows, today)`), so #65's report-section rows can import them. A test reads `tests/fixtures/work-items-list-cases.json` and checks every case: `due_and_pill[].expect.due` and `.pill`, `priority_colour`, `owner`, and `sort.expected_order`. Until #35 gives a JS harness, a Python mirror of the same five functions runs the same file (the fixture file was checked that way when it was written; the mirror is what pins the expected values).

**Browser (Chrome headless, as the #33 test does), at 1400 and 900 px** (NFR-5, one check each):
- Build the demo database with `CLARK_NOW=2026-10-28` (`dev/demo_data.py`), start the server on it, open `#work&p=TUL`, then `#work&p=MOSS`.
- Fix the page's date to 2026-10-28 with a script added before the page loads (Chrome DevTools `Page.addScriptToEvaluateOnNewDocument` replacing `Date`); no test hook in the shipped page.
- The expected row count comes from the database (`actions + raid + decisions`, `archived = 0`, for that project), not a typed number. Today's demo has 16 for TUL (6 actions, 6 RAID, 4 decisions) and 16 for MOSS. The test also checks each row by its ID text (`TUL-A-001` and so on), so a missing row is named.
- No horizontal page scroll: `document.documentElement.scrollWidth <= innerWidth` at both widths. At 900 px the table may shrink the Item column and wrap titles; it may not scroll sideways (a wide table inside its own scroll box is not allowed either, so the test fails on any `overflow-x` scroll inside the list).
- Spot checks on the screen: a late open action reads "N days late" in red text; a closed action shows no words; the Red pill is on `Urgent` and `High`; dates read DD-MM-YYYY (no `\d{4}-\d{2}-\d{2}` in the list's text).
- Failure states: stale token (start a second server) shows the reload words; a 404 project shows its words.
- Read-only: no input, button or `contenteditable` in the list that changes data (the "Client" tag is not a button).

## 8. What #36 takes from the prototype, and what is #64

| Prototype behaviour | Goes to |
|---|---|
| Table: Item (type badge, title, meta line), Owner (initials circle), Due (date and words), Priority, Status pill | **#36** |
| "Client" tag (shown, not clickable) | **#36** |
| Open / Closed / All switch with counts; "Filter by" row, dot, chips, Clear all; Add buttons; Excel icons; profile circle; dark mode | **#64** (its text, the owner 28-10-2026) |
| The eye as a working toggle; filters, saved views (FR-41); row click opening the peek | later: FR-41 item, peek #42 |
| Type switch (All, Actions, Risks and issues, Decisions), search box, Group by, Board layout, collapsible workstream groups | **unassigned** (not in #36's or #64's text); not in #36 (Q4) |

Why not workstream groups in #36: decisions have no workstream column, so under the prototype's default "Group by workstream" every decision would fall into one "No workstream" group.

## 9. From creaite (v2.6.9) for #65 and #66

Reused by #36 as logic (rewritten, not pasted): `fd`, `days`, `rel` (core/page.js), `OPENST`, `overdue` (core/data.js, page.js), `PRIOS`, the "words only when open" rule in `cell("due")` (work.js). #65 (report sections) and #66 (editor) should import `workItems.js`, not copy again. Not used by #36: `work.js` columns and saved views, `NewTile.jsx` (#64's Add button), grouping and the Board (work.js GROUPS), `decLateWords` (creaite writes "1 day late" where the prototype writes "Yesterday"; #36 follows the prototype).

## 10. Open questions (for the owner or the Head)

1. **Which project, and how does the page know the list?** Recommend: #33's boot block gets `projects: [{code, name}]` and a default `project`; the Head to assign (a teammate owns #33, guarded). Default for #36: the address (`#work&p=CODE`), "Choose a project" when absent.
2. **Show Assumptions and Dependencies?** The demo has them (2 per project); the done-when names only actions, risks, issues and decisions. Recommend: yes, all four RAID types, labelled by word (BRD FR-40 names all four). Default: yes. The owner.
3. **Closed rows: nothing under the date, or the closed date?** Recommend nothing (creaite, and the review's complaint). Default: nothing. The owner.
4. **Which list controls (type switch, search, Group by, Board) does #36 carry?** Recommend none; the Head to assign them (they are in neither #36 nor #64). Default: a flat list.
5. **Default order.** Recommend open first, then date, then ID (section 2). creaite sorts each type differently (actions overdue first, RAID by priority, decisions pending first); one list needs one rule. Default: as recommended. The owner.
6. **Pill words:** worked out (Overdue, Due soon, Red) as the prototype, or the stored status. Recommend the prototype. Default: the prototype. The owner.
7. **A risk with no priority:** grey "Not rated" (recommended), or amber as the prototype's fallback. Default: grey.
8. **Today:** the browser's clock (recommended, default), or the server sends it. The test fixes the date from outside either way.
9. **Narrow screens:** below 900 px is out of scope (NFR-5). Default: the layout may stack, but no promise is made. The Head.

## 11. What #36 needs from #35

- A mounted view for `#work&p=CODE`, a signals store for `data`, and the bundle's rule that page code imports only from `src/` and the vendored folders.
- The token names the prototype uses (`--status-*` with `-tint` and `-text`, `--grey-50..900`, `--brand-blue`, `--brand-blue-tint`, `--text-muted`, `--surface`, `--border`, `--radius-*`) in the demo `tokens.css`, and the page CSS tested at 1400 and 900 px with no horizontal scroll.
- A JS test harness that can import a plain module and read a JSON fixture (or confirmation that the Python mirror is the plan until one exists), and a headless-Chrome helper the browser test can share with #33's.
- A single `todayIso()` seam in page code.
