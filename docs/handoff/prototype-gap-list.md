# Prototype gap list: 0.2.1 against the prototype

The prototype (`system/prototype/`) is the reference for screens and behaviour (`docs/ARCHITECTURE.md`). This list compares it with the released 0.2.1 screen by screen, with demo data, at 1400 and 900 px, and matches each difference to a board item and its release, or marks it. Laptop widths only. It is a reading of what is on screen and in the code at the 0.2.1 tag: nothing was changed to make it.

## 1. Release check

- The latest release on the public repository is **v0.2.1** ("clark 0.2.1 (Beta)", a pre-release), and the code at that tag says version 0.2.1.
- **0.2.1 shows its version nowhere in the app.** Settings holds only Client folder, Personal and Backups; there is no "clark version" card. That card comes with the Update from Settings item (#109), which is not built. So the check "the version clark shows is 0.2.1" cannot be made on screen yet; the tag and the release page are the evidence.

## 2. Summary for the decision

179 differences were listed, each counted once under its main match.

| Where it is on the board | Differences |
|---|---|
| v0.3 | 25 |
| v0.4 | 45 |
| v0.5 | 12 |
| v0.6 | 7 |
| v0.7 | 5 |
| after 0.7 or unscheduled | 6 |
| no item yet (a decision is needed) | 67 |
| mockup only (a prototype choice, not a target) | 5 |
| changed by a decision (not a gap) | 7 |
| **Total** | **179** |

Of these, 66 are for items that are built and in review or merged but are not in 0.2.1; they are counted in their release above.

**Does the board reach the prototype by v0.7? No.** 94 differences have an item scheduled for v0.3 to v0.7, but 67 have no item at all and 6 sit after v0.7 or unscheduled. To reach the prototype by v0.7 the board needs new items, and a size and release for each, for the 67 "no item yet" differences below (the biggest groups: dashboard (11), milestones: plan (9), work items table, view mode (7), settings (6), help (4)), or a decision on each that the prototype choice is not a target.

Board states that disagree with the 0.2.1 code (for the board owner to check): #79, #141 and #186 show Shipped but 0.2.1 does not show them; #101 and #95 show In review but are already in the 0.2.1 code.

### Differences with no item yet

| # | Screen | Difference |
|---|---|---|
| A-D1 | Dashboard (View and Edit) | Cover: prototype has a dark band with the project name, "WEEKLY REPORT", the week-ending date and "for <client>". 0.2.1 has a small client line above a plain title,... |
| A-D2 | Dashboard (View and Edit) | Bar above the page: prototype has View/Edit, a Week ending date field, a "Draft - not published yet" chip, and in Edit the notes "Editing: each change saves on its... |
| A-D5 | Dashboard (View and Edit) | Risks and issues, Open actions, Decisions: prototype draws the rows (status pill, owner, date, priority, id, eye) with an "Add a risk: type Owner: what it is" line... |
| A-D10 | Dashboard (View and Edit) | Use case summary in View: prototype shows the reference in a small box (merged references read "1.3 + 1.4"), a download icon for the use cases Excel sheet, and a grey... |
| A-D11 | Dashboard (View and Edit) | A use case row opened: prototype opens two columns, "Where it stands" on the left and "Next steps · 3" on the right, each step "Owner: what it is" with the work item... |
| A-D13 | Dashboard (View and Edit) | Add in Edit: prototype has the growing Add button (a "+" at rest that grows to "Add use case" on pointer or keyboard focus) and "Add a use case from your project... |
| A-D16 | Dashboard (View and Edit) | Hint line under the tiles in Edit: prototype says "Drag a tile to reorder it (or Alt with the arrow keys); the eye hides it; right-click a tile to change its colour.... |
| A-D19 | Dashboard (View and Edit) | Tiles in Edit: 0.2.1 draws a drag grip and an eye on every tile, and "High risks and issues" runs into the grip and eye (1400 and 900); at 900 the Decisions tile text... |
| A-D21 | Dashboard (View and Edit) | Contents list (opened by pointer at 1400): both list the sections with the current one marked. Prototype adds counts ("3 flagged", "2 slipped", "1 red", "1 late", "2"... |
| A-D25 | Dashboard (View and Edit) | Bar: prototype has a project switcher (a menu with the project name and a chevron); 0.2.1 shows the project name as plain text. |
| A-D26 | Dashboard (View and Edit) | Bar: 0.2.1 has a Settings tab; the prototype has Dashboard, Work items, Milestones and Use cases only, and reaches Settings from the profile menu (the 0.2.1 menu also... |
| A-S1 | Settings | Page head: prototype has "Settings", a line of help and a row of jump chips (Profile, Personal, AI, Projects, People, Asking, Publishing, Published reports, Data,... |
| A-S4 | Settings | Section style: prototype shows four picture cards (a small drawing of each) under "Dashboard sections", and says the style is used on the published report too. 0.2.1... |
| A-S6 | Settings | Projects table (Name, Code, Client, Workstreams, Items; Open, Edit, Archive, Show archived, add a project): not in 0.2.1. |
| A-S9 | Settings | Publishing card (Local folder and a typed Client folder address) in the prototype. 0.2.1 has a "Client folder" card with a Choose folder button (a folder picker, not... |
| A-S11 | Settings | Data card (Export workbook, Import workbook, Reset demo data): not in 0.2.1 Settings (export is in the profile menu, import on Work items). |
| A-S15 | Settings | Backups card: 0.2.1 has it (list, Preview with a panel, Restore with a confirm step, "How many backups to keep: 14"). The prototype has no Backups card at all. |
| B-3 | Work items table, View mode | Prototype: intro line "Select an item to open it beside the list. The eye shows or hides it from the client."; plain project name above the title. 0.2.1:... |
| B-4 | Work items table, View mode | Prototype: Import and Export icon buttons beside Add on Work items (and an Import and Export workbook pair in Settings). 0.2.1: none on the page or in Settings; the... |
| B-5 | Work items table, View mode | Prototype: a "Show archived" button with a count and an archived list under the table; an archived item opens read-only with Restore. 0.2.1: nothing on the page. |
| B-6 | Work items table, View mode | Prototype table: no Type column; a letter badge (A, I, R, D) in the Item cell; an eye button in a Client-visible column that turns client-visible on or off; each... |
| B-7 | Work items table, View mode | 0.2.1 only: the word "Dependency" breaks as "Dependenc / y" in the Type column at 900. Prototype: a letter badge, no break (the prototype's own due date wraps "04-11-... |
| B-8 | Work items table, View mode | Prototype: Add item opens a menu (Add action, risk, issue, decision) and the new item is created, opens in the peek with a toast and Undo ("PDF-A-026 added"). 0.2.1:... |
| B-9 | Work items table, View mode | Prototype: owner, due, priority and status cells are editable in the table at any time (there is no Edit mode). 0.2.1: only in Edit mode. |
| B-12 | Work items table, Edit mode and inline pickers | Prototype: the status picker on a risk or issue has a Rating section (Red, Amber, Green) under Open, Closed, Cancelled, so the table can change the colour. 0.2.1... |
| B-13 | Work items table, Edit mode and inline pickers | Prototype: the Status cell shows the live look (Due soon, Overdue, Red, Green) and the picker sets the raw status. 0.2.1 Edit shows the raw status word (a code note... |
| B-15 | Board | Prototype cards: letter badge, ID, eye only when shown to the client, a "..." Move to menu always present, compact. Dragging a card or using Move to works with no... |
| B-16 | Board | Prototype: drag a column heading to move the column, drag its right edge to resize (260 to 640 px, double-click resets), Alt+Left or Right moves it from the keyboard.... |
| B-26 | Peek and Sneak peek | Latest update field with a Draft button (writes a line by rules) and a "Last updated" stamp. |
| B-28 | Peek and Sneak peek | Warning bar above the title: "3 days overdue (due ...)" with Move to Friday and Move a week on; a due date on a weekend gets "a working day is usually meant" with... |
| C-M1 | Milestones: Plan (timeline, Today line, labels, Legend, markers, list) | Prototype has a page header: project name above, title, a one-sentence summary ("<last milestone> is agreed for ..., 1 achieved, 5 to come."). 0.2.1 has only the... |
| C-M2 | Milestones: Plan (timeline, Today line, labels, Legend, markers, list) | Prototype has a Plan / Movement switch under the header, with a hint line for each. 0.2.1 has no switch: Movement sits under the list and shows only in Edit. |
| C-M3 | Milestones: Plan (timeline, Today line, labels, Legend, markers, list) | Prototype has an "Add milestone" (+) button; it adds a milestone 30 days out and opens it in the peek with the name selected. 0.2.1 has no way to add a milestone on... |
| C-M4 | Milestones: Plan (timeline, Today line, labels, Legend, markers, list) | Prototype has a "Show archived" pill with a count; on, it shows an "Archived" box ("No archived milestones." when empty; otherwise muted rows with an "Archived" tag... |
| C-M5 | Milestones: Plan (timeline, Today line, labels, Legend, markers, list) | Timeline/Calendar switcher: prototype buttons show icon and word ("Timeline", "Calendar"). 0.2.1 shows two small icon buttons with no words. |
| C-M6 | Milestones: Plan (timeline, Today line, labels, Legend, markers, list) | "Hide/Show milestone details" toggle above the list (remembered). 0.2.1 has no toggle; the list is always shown. |
| C-M10 | Milestones: Plan (timeline, Today line, labels, Legend, markers, list) | Row text: prototype "Expected a date · 4 days later" is one line; 0.2.1 wraps the same words over two lines at 1400 (narrower date column). |
| C-M11 | Milestones: Plan (timeline, Today line, labels, Legend, markers, list) | At 900 px, 0.2.1's list rows stack (state and progress drop under the name and date); the prototype keeps one row. |
| C-M12 | Milestones: Plan (timeline, Today line, labels, Legend, markers, list) | The Week / Month / Quarter control in 0.2.1 has a clipped edge: the selected pill is cut by the control's border (a small arc at the left of "Week" and the right of... |
| C-C2 | Milestones: Calendar (Week, Month, Quarter) | Chips show the full milestone name in the prototype (Week and Month at 1400; wrapped in Week at 900). In 0.2.1 the chip is cut ("Expected: Staff trai...") at 1400 and... |
| C-V1 | Milestones: Movement (Edit only in 0.2.1) | Prototype: a table with month names across the top, one track per milestone on a shared scale, a Variance column and a key line (Original, Agreed, Forecast, Distance... |
| C-V2 | Milestones: Movement (Edit only in 0.2.1) | Prototype decisions: Hold, Move the agreed date, Add a recovery action, Escalate to steering (the last two create a linked work item and open it). 0.2.1: Hold and... |
| C-V3 | Milestones: Movement (Edit only in 0.2.1) | Prototype has an Internal note box (saves on leaving the box, never published). 0.2.1 Movement has no note box; Hold writes a line into the change record shown under... |
| C-H5 | Help | Opening: prototype has Help reachable from the top bar and the page shows "Back"; 0.2.1 has Help only in the profile menu and the ? key, and a "Close Help" button. |
| C-H6 | Help | Search box: prototype has a search icon and a "/" key chip inside the box; 0.2.1 has the box with neither. The "/" key itself works in both (focus went to the box in... |
| C-H7 | Help | Layout: prototype is a page of cards with a contents rail and the search at the top right; 0.2.1 is a bordered panel with search on the left, a Close button and a tab... |
| C-H9 | Help | Search results: prototype marks the matched word (yellow background) in titles and text; 0.2.1 lists the same two results for "keyboard" with the same layout ("2... |
| C-X1 | Excel import screens | Prototype has "Export workbook" and "Import workbook" buttons (Settings > Data, and on Work items) and an "Import from Excel" dialog (what is read, the columns, Get... |
| C-X2 | Excel import screens | Prototype's "Get the template" workbook: 0.2.1 has no template download. |
| C-X4 | Excel import screens | The two workbooks do not share a layout. The 0.2.1 export names work items by "Description" and adds Project, Order, Source and Updated; the prototype's importer... |
| D-8 | Profile menu and top bar | Prototype has a project switcher in the top bar; 0.2.1 shows the project name as plain text. |
| D-9 | Profile menu and top bar | Prototype Dashboard has a Week ending date box and a status chip ("Draft - not published yet", then "Published ... locally"). 0.2.1 has no week box in the bar, and... |
| D-14 | Publish dialog | To client line: prototype says "Set it in Settings, Publishing" with a link to the Publishing card; 0.2.1 says "Set it in Settings." as plain words (no link) and... |
| D-15 | Publish dialog | Local line: prototype adds "it opens where you last saved" (and falls back to downloads when there is no save window); 0.2.1 says only that you choose folder and name... |
| D-16 | Publish dialog | Working and finished states: prototype puts a spinner on the Publish button, then a tick with "Published (Publication N)", closes itself after about a second and... |
| D-17 | Publish dialog | Warning shown when To client is ticked: prototype says "The client will see this page. Only what is shown in View mode is included."; 0.2.1 says only "The client will... |
| D-18 | Preview and the published file | Preview in 0.2.1 gives a one-use link: opening the same address a second time answers "That could not be found. Reload the page and try again." as plain text on a... |
| D-23 | Preview and the published file | Published Milestones: same timeline, same list, same status words. The prototype's two view buttons carry words (Timeline, Calendar) and Legend has an icon; 0.2.1... |
| D-24 | Preview and the published file | Published Milestones list at 900: the prototype keeps one row per milestone (date, name, state, progress). 0.2.1 stacks the state under the date and pushes the name... |
| D-25 | Preview and the published file | Published Milestones list: 0.2.1 shows five rows and "Show all 6 milestones"; the prototype lists them all. |
| D-27 | Export (Excel) and Word | Excel import: the prototype has Import workbook (Settings > Data, and an upload icon on Work items) and Get the template; 0.2.1 has the import engine but no route and... |
| D-28 | Export (Excel) and Word | Export places: the prototype exports from Settings > Data, from a download icon on Work items and, for use cases only, from the Use Cases page; 0.2.1 exports only... |
| D-29 | Export (Excel) and Word | Export file name: prototype "<date> <project name> work items.xlsx"; 0.2.1 "<code>-<date>.xlsx". |
| D-37 | ask clark | Ctrl or Cmd+J opens and closes the panel in the prototype. |
| D-48 | Settings (backups, version, the rest) | Settings layout: the prototype has an intro line and a side list of sections (Profile, Personal, AI, Projects, People, Asking, Publishing, Published reports, Data,... |
| D-50 | Settings (backups, version, the rest) | Projects card (list, add, edit, archive, show archived). 0.2.1 has none. |
| D-52 | Settings (backups, version, the rest) | Publishing card: Local folder and Client folder. 0.2.1 has a Client folder card only (Choose folder, Clear) and no Local folder setting. |

## 3. The gap list, screen by screen

Columns: the difference (what the prototype does, what 0.2.1 does), the width it was seen at, and the board item with its release, or the mark. A row id starts with the letter of the group of screens it was read in.

### Dashboard (View and Edit)

| # | Difference | Seen at | Board item and release, or mark |
|---|---|---|---|
| A-D1 | Cover: prototype has a dark band with the project name, "WEEKLY REPORT", the week-ending date and "for <client>". 0.2.1 has a small client line above a plain title, no band. | both | no item yet (#176 v0.4 Merged covers only the logo and picture on the cover, not the band) |
| A-D2 | Bar above the page: prototype has View/Edit, a Week ending date field, a "Draft - not published yet" chip, and in Edit the notes "Editing: each change saves on its own", "Drag to move, + to add a template" and the "Start from last week's report" button. 0.2.1 has View/Edit in the top bar only. | both | no item yet (the last-week button is D7) |
| A-D3 | Section look: prototype draws each section as its own card with a small coloured square before the heading and a slim gap between cards. 0.2.1 draws plain bold headings in one frame divided by a thin line (its own "Slim gaps"). The two "Slim gaps" mean different things. | both | #87 v0.4 (In review), partly; the card look itself has no item. Built after 0.2.1 |
| A-D4 | Current state, Summary, This week, Next week: prototype shows the text and, in Edit, writing prompts ("Say what matters this week"). 0.2.1 shows "Not shown on this page yet." in View and in Edit; there is no editor on these bodies. | both | #220 v0.7 (On hold) for Edit; the View side has no item of its own |
| A-D5 | Risks and issues, Open actions, Decisions: prototype draws the rows (status pill, owner, date, priority, id, eye) with an "Add a risk: type Owner: what it is" line and "Add from your project record (N)" in Edit. 0.2.1 draws only the "Not shown on this page yet." line (#96 adds RAID card and Work items list templates, which are new sections, not these three). | both | no item yet |
| A-D6 | Supporting documents: prototype lists links with an eye and an options menu and "Add a document link". 0.2.1 shows the placeholder. | both | #74 v0.7 (On hold) |
| A-D7 | "Since the last report" block (only you see this) and the "Start from last week's report" button: prototype has them, 0.2.1 neither. | both | #118 v0.7 (On hold) |
| A-D8 | Which use cases the dashboard shows: prototype has an eye on each use case (in Edit) and the dashboard shows only the ones switched on (here 6 of 8). 0.2.1 shows every use case that is not archived and has no way to leave one off the dashboard. | both | #157 v0.4 (Ready): the "On the dashboard" switch is part of its Use cases page; #163 v0.4 (In review) is the published side |
| A-D9 | Line under the summary: prototype ends with "2 more on the Use cases page" (a link to the page), in View and Edit. 0.2.1 has no such line and no page. | both | #157 v0.4 (Ready), point 5 names this exact line |
| A-D10 | Use case summary in View: prototype shows the reference in a small box (merged references read "1.3 + 1.4"), a download icon for the use cases Excel sheet, and a grey tint on a row under the pointer. 0.2.1 shows the reference as plain text, no download icon (Export is in the profile menu), no tint. | both | no item yet (#157 point 6 puts an Export button on the new page) |
| A-D11 | A use case row opened: prototype opens two columns, "Where it stands" on the left and "Next steps · 3" on the right, each step "Owner: what it is" with the work item id as a link and a due date, then "See all 5 work items for 1.1" (counts all linked items). 0.2.1 opens one column: "Where it stands", "Next steps" as "Owner: what it is" with no id or date, then "See all 2 open work items" (counts only open ones, and the steps are only actions). Both open in place, both close on a second click. | 1400 (900 opened row: p-uc-open-900.png, same two-column idea) | no item yet |
| A-D12 | Use case summary in Edit: prototype has a status button on each row ("Status: Flag. Change"), headline and name editable in place, and the opened row editable. 0.2.1 has none of this; every row is read-only. | both | #164 v0.4 (In review) is editing on the Use cases page; the same on the dashboard has no item of its own. Built after 0.2.1, partly |
| A-D13 | Add in Edit: prototype has the growing Add button (a "+" at rest that grows to "Add use case" on pointer or keyboard focus) and "Add a use case from your project record (2)". 0.2.1 has neither on the dashboard (the growing button exists only on Work items). The separate "Add tiles" in the brief does not exist in the prototype: tiles are hidden and shown with the eye. | both | no item yet for the dashboard (#88 v0.4 Building is only the design entry for "the Add tiles and the growing Add button"; #157 point 5 has Add a use case on the new page) |
| A-D14 | At a glance tiles: prototype tiles fill the row (the health tile is double width and takes the space the others leave; one or two tiles fill it). 0.2.1 tiles keep a fixed width, left aligned, with empty space at 1400; at 900 the Decisions tile wraps to a second line. | both | #79 v0.4 (board says Shipped, but 0.2.1 does not show it: flag for the PM) |
| A-D15 | Health tile text: prototype adds "Suggested: At risk, because 2 slipped milestones and 3 red risks or issues. Your choice matches it." 0.2.1 shows only the reason box. | both | #122 Unscheduled (an Idea): after 0.7 |
| A-D16 | Hint line under the tiles in Edit: prototype says "Drag a tile to reorder it (or Alt with the arrow keys); the eye hides it; right-click a tile to change its colour. Hidden tiles are left out of the published page." 0.2.1 has the same abilities (drag, Alt-arrows, eye, right-click colour) but says nothing on the page. | both | no item yet |
| A-D17 | Health pill menu: prototype lists On track, At risk, Off track as coloured pills with a tick on the current one. 0.2.1 lists the same three words as plain text rows. The prototype's pill is a filled "AT RISK" block; 0.2.1's is a small outlined pill with a chevron. | both | #87 v0.4 (In review), partly. Built after 0.2.1 |
| A-D18 | Tile status word ("Overdue", "High"): both show it. Prototype draws it as a small bordered chip; 0.2.1 as plain text under the figure. Same information. | both | #140 v0.6 (Shipped) covers the word; the chip look has no item |
| A-D19 | Tiles in Edit: 0.2.1 draws a drag grip and an eye on every tile, and "High risks and issues" runs into the grip and eye (1400 and 900); at 900 the Decisions tile text "Oldest a date" is overlapped by "Hidden from the published report". Prototype draws only the eye (no grip) and nothing overlaps. | both | no item yet (#139 v0.6 is the section handle at 900, not the tile grip) |
| A-D20 | Contents rail at 900: prototype swaps it for an "On this page" button at the bottom right that opens the list. 0.2.1 keeps the thin line rail at the right edge at 900 (it sits over the page edge). | 900 | #141 v0.6 (board says Shipped; flag, as the 0.2.1 rail is the line form at 900) |
| A-D21 | Contents list (opened by pointer at 1400): both list the sections with the current one marked. Prototype adds counts ("3 flagged", "2 slipped", "1 red", "1 late", "2" documents) and a "Back to top" link; 0.2.1 has labels only. | both | no item yet (counts follow #67's rail; none names the counts) |
| A-D22 | Milestones block on the dashboard: prototype has the words Timeline and Calendar on its switch, a per-row eye and a progress bar (20%, 10%) in the list. 0.2.1 has an icon-only switch, no per-row eye, no progress bar; at 900 it stacks the status under the date. (The Milestones page is another group's.) | both | #76 and #146 v0.4 (In review) for the Calendar; eye and progress bar on rows: no item yet. Built after 0.2.1, partly |
| A-D23 | Footer line "Prototype with demo data..." with a Reset demo data link exists only in the prototype. | both | mockup only |
| A-D24 | Bar: prototype has an "ask clark" button with a "/" key hint; 0.2.1 has none (its profile menu is the only control besides View/Edit). | both | #47 v0.3 (In review), #214 v0.3 (Building). Built after 0.2.1 |
| A-D25 | Bar: prototype has a project switcher (a menu with the project name and a chevron); 0.2.1 shows the project name as plain text. | both | no item yet |
| A-D26 | Bar: 0.2.1 has a Settings tab; the prototype has Dashboard, Work items, Milestones and Use cases only, and reaches Settings from the profile menu (the 0.2.1 menu also has Settings). | both | no item yet |
| A-D27 | Use cases tab in the bar: prototype has it, 0.2.1 has none. | both | #157 v0.4 (Ready) |
| A-D28 | Look: 0.2.1 has a dark teal bar, a teal underline, purple accents and a heavier heading face; the prototype has a dark navy bar, a blue accent and a lighter body face for headings. Layout is otherwise the same where compared. | both | #186 v0.4 (board Shipped; flag) and #176 v0.4 (Merged); Word and Excel look is #187 v0.5. Built after 0.2.1 |

### Dashboard section controls and Add (Edit)

| # | Difference | Seen at | Board item and release, or mark |
|---|---|---|---|
| A-C1 | Section menu: prototype items have icons, show "Alt ↑" and "Alt ↓" hints, have separator lines and a red Delete section. 0.2.1 has plain text items, no hints, no separators, Delete not red. Both list Add a template below, Move up, Move down, Leave out of the published page, Delete section. | both | #101 v0.4 (In review; the control itself is already in 0.2.1); look #87 v0.4. Built after 0.2.1 |
| A-C2 | "Place beside the next section": 0.2.1 lists it (greyed with the reason). The prototype menu has no such item (it places by drag and by "Place it" in the template dialog). | 1400 | #95 v0.4 (In review). Built after 0.2.1 |
| A-C3 | Section handle and plus: prototype draws two small boxed buttons that darken on hover; 0.2.1 draws bare dots and a plus. Same place (left margin). At 900 the 0.2.1 handle sits over the start of the heading. | both | #87 v0.4 and #101 v0.4; the 900 overlap is #139 v0.6 (waiting for a word). Built after 0.2.1 |
| A-C4 | Add a template: prototype opens the "Add a section" dialog (search, 6 groups, 20 templates, preview with "Holds" and "Place it", Full or Half, Recently used, About section templates, Cancel, Add section; it fits at 900 with 3 columns). In 0.2.1, the plus and "Add a template below" add a plain "New section" at once with an Undo toast (a stand-in). | both | #96 v0.4 (In review; board says 19 templates, prototype shows 20). Built after 0.2.1 |

### Use cases page

| # | Difference | Seen at | Board item and release, or mark |
|---|---|---|---|
| A-U1 | The page and tab: prototype has a Use cases tab and a page (title, one line of help, Export to Excel, "Add a use case"). 0.2.1 has neither; its only use case surface is the dashboard summary (D8 to D13). The list at 1400 has seven columns (Ref, Use case, Where it stands, Status, Work items "5 linked, 5 open", Milestones, Home dashboard with an eye and words). At 900 it hides Where it stands and Milestones and shows the headline under the name. | both | #157 v0.4 (Ready) is the product build; #163 v0.4 (In review) the read route; #168 v0.4 (Building) the published tab; #162 is the prototype (Shipped). Built after 0.2.1, partly |
| A-U2 | List tools: prototype has search, a Status filter, All / On the dashboard / Not on the dashboard with counts, a sort (Reference, Status, Open work items), a "Showing 8 of 8 · 6 on the dashboard" line, an empty message with "Clear the filters", an archived list ("Show archived", Restore) and a dark look. 0.2.1 has none of it. | both | #157 v0.4 (Ready), point 4 and point 5 |
| A-U3 | One use case on its own page: prototype shows the title (click to edit), a status word, "5 of 5 work items open · 1 milestone", Change status, On the dashboard / Take off the dashboard, a "Where it stands" editor, a Work items list (status chip, due date, "Open all 5 in Work items", "Add a next step", "Link an existing work item"), Details (owner, group, dashboard, last change), Milestones, History and "Archive this use case. It can be restored; nothing is deleted." At 900 the side cards stack under the main card. 0.2.1 has only the accordion row (D11). | both | #157 v0.4 (Ready); editing in #164 v0.4 (In review); Archive and Restore data side #126 v0.2 (Shipped). Built after 0.2.1, partly |

### Profile menu (opened on screen in both)

| # | Difference | Seen at | Board item and release, or mark |
|---|---|---|---|
| A-P1 | First line: prototype shows "NAME · EMAIL" (or "No name yet: add it in Settings > Profile"). 0.2.1 has no such line. | both | #180 v0.3 (In review). Built after 0.2.1 |
| A-P2 | The circle: prototype shows your initials once a name is set (an outline person icon until then); 0.2.1 always shows the outline person icon (it has no name to show). Tooltip is the same in both. | both | #180 v0.3 (In review), partly. Built after 0.2.1 |
| A-P3 | Dark mode: prototype has a Dark mode choice in the menu (and Light, Dark, System in Settings) and a full dark look on every screen compared. 0.2.1 has no dark mode: with the Mac set to dark the page stays light. | both | #179 v0.3 (In review). Built after 0.2.1 |
| A-P4 | "Published reports" item (jumps to the Settings card): prototype only. | both | #120 v0.5 (In review). Built after 0.2.1 |
| A-P5 | "Past reports (mockup)" item: prototype only. | both | mockup only (#125 Unscheduled) |
| A-P6 | Look of the menu: prototype items have icons, one-line labels and a wider panel; 0.2.1 has plain text and wraps "Preview the page in a new tab" onto two lines. Publish, Preview, Export, Settings and Help are in both. | both | #87 v0.4 (In review). Built after 0.2.1 |

### Settings

| # | Difference | Seen at | Board item and release, or mark |
|---|---|---|---|
| A-S1 | Page head: prototype has "Settings", a line of help and a row of jump chips (Profile, Personal, AI, Projects, People, Asking, Publishing, Published reports, Data, Version, Diagnostics). 0.2.1 has "Settings are not ready yet." in a card and no chips. | both | no item yet (the empty card is a stand-in) |
| A-S2 | Profile card (Name, Alias, Email, Phone number, Organisation; saves on leaving the field with an Undo toast): not in 0.2.1. | both | #180 v0.3 (In review) for name and email; #174 Unscheduled (first-run prompt, after 0.7); alias, phone, organisation have no item. Built after 0.2.1, partly |
| A-S3 | Appearance (Light, Dark, System; System is the default): not in 0.2.1. | both | #179 v0.3 (In review). Built after 0.2.1 |
| A-S4 | Section style: prototype shows four picture cards (a small drawing of each) under "Dashboard sections", and says the style is used on the published report too. 0.2.1 has four radio choices with one line each, no pictures, and says the published page uses Slim gaps for now. At 900 the prototype cards wrap three and one. | both | no item yet (the published page following the style is in no item) |
| A-S5 | AI card (Claude "Not connected" with Connect, OpenAI "Later", Model for ask clark): not in 0.2.1. | both | #54 v0.5 (In review); #52 v0.5 (Idea); #53 v0.5 (On hold). Built after 0.2.1 |
| A-S6 | Projects table (Name, Code, Client, Workstreams, Items; Open, Edit, Archive, Show archived, add a project): not in 0.2.1. | both | no item yet (archive data side is #126 v0.2, Shipped) |
| A-S7 | People table (email, organisation, role, Paste from Excel): not in 0.2.1. | both | #115 v0.5 (In review), partly (the table from day one). Built after 0.2.1 |
| A-S8 | Asking card (ask clark switch with On/Off words, "Folders ask clark may read", Choose folder opens a list of places in the prototype, "0 of 20 folders", Remove): not in 0.2.1. Turning it off keeps the card and shows "Off" and a toast with Undo. | both | #47 v0.3 (In review), #214 v0.3 (Building); #170 v0.3 is its prototype (Shipped). Built after 0.2.1 |
| A-S9 | Publishing card (Local folder and a typed Client folder address) in the prototype. 0.2.1 has a "Client folder" card with a Choose folder button (a folder picker, not a typed address) and no Local folder. | both | no item yet (#43 v0.2 built the 0.2.1 client folder) |
| A-S10 | Published reports card (a table of publications with Open): prototype only. | both | #120 v0.5 (In review). Built after 0.2.1 |
| A-S11 | Data card (Export workbook, Import workbook, Reset demo data): not in 0.2.1 Settings (export is in the profile menu, import on Work items). | both | no item yet for the card (export in the menu is #147 v0.2, Shipped) |
| A-S12 | Reset demo data: prototype only. | both | mockup only |
| A-S13 | Version and updates card (Installed, Update with "Review 0.3.0" and a review dialog with What's new and Install, Choose zip, Undo update): not in 0.2.1. | both | #109 v0.4 (In review). Built after 0.2.1 |
| A-S14 | Diagnostics card (Normal or Debug, log folder, Copy diagnostics, errors in the last 7 days): not in 0.2.1. | both | #110 v0.4 (In review). Built after 0.2.1 |
| A-S15 | Backups card: 0.2.1 has it (list, Preview with a panel, Restore with a confirm step, "How many backups to keep: 14"). The prototype has no Backups card at all. | both | no item yet for the prototype (the product side is #111 v0.4 and #86 v0.2, both Shipped) |
| A-S16 | Settings layout: prototype is one column of compact cards with a form look and (at 900) a chip row that runs past the right edge (Diagnostics is cut off); 0.2.1 cards are wide, centred, larger type. At 900 both stack. | both | #87 v0.4 (In review). Built after 0.2.1 |

### Work items table, View mode

| # | Difference | Seen at | Board item and release, or mark |
|---|---|---|---|
| B-1 | Prototype: one filter line with removable chips, autocomplete with counts, plain-words search, a plain sentence for a wrong value, hint chips, saved-view tabs (Open items, Overdue, Waiting on the client, My actions) with counts, Save as a new view. 0.2.1: two switch groups (type, open or closed), nine "Filter by" menus (is any of / is not, Select all, Clear), no search box, no saved views. | both | #153 v0.6 (in review, so built after 0.2.1; prototype side #145 v0.6) |
| B-2 | Prototype: the View menu holds Group by (Workstream, Status, Due, Owner, Priority, Milestone, Type, Nothing) and the swimlanes. 0.2.1: a "Group by: X" button with the same eight choices beside the layout switch; swimlanes in a bar on the board. The eight choices and their wording match. | both | #153 v0.6 (item 1 moves both into one View menu; built after 0.2.1) |
| B-3 | Prototype: intro line "Select an item to open it beside the list. The eye shows or hides it from the client."; plain project name above the title. 0.2.1: small-capitals project name, no intro line. | both | no item yet |
| B-4 | Prototype: Import and Export icon buttons beside Add on Work items (and an Import and Export workbook pair in Settings). 0.2.1: none on the page or in Settings; the profile menu holds Publish, Preview, Export to Excel, Settings, Help (no Import anywhere in the page). | both | no item yet (#77 and #147 shipped Export in the profile menu only; #38 is the import engine, shipped, with no page button) |
| B-5 | Prototype: a "Show archived" button with a count and an archived list under the table; an archived item opens read-only with Restore. 0.2.1: nothing on the page. | both | no item yet (#126 item 10 left the page side "later, with #64 and #67"; both shipped without it; #166 is the prototype reference) |
| B-6 | Prototype table: no Type column; a letter badge (A, I, R, D) in the Item cell; an eye button in a Client-visible column that turns client-visible on or off; each group is its own bordered card. 0.2.1: a Type column with a word badge, a "Shown to client" tag in the item line, no eye toggle on this page, one table with group rows. | both | no item yet (the peek has the eye, #42 v0.4) |
| B-7 | 0.2.1 only: the word "Dependency" breaks as "Dependenc / y" in the Type column at 900. Prototype: a letter badge, no break (the prototype's own due date wraps "04-11- / 2026" at 900). | 900 | no item yet (#203 covers cell wrapping in Edit only, not this) |
| B-8 | Prototype: Add item opens a menu (Add action, risk, issue, decision) and the new item is created, opens in the peek with a toast and Undo ("PDF-A-026 added"). 0.2.1: the menu is there but every choice says "Add action is coming with a later release. Nothing was added." | both | no item yet (the peek is #42 v0.4; no item builds Add itself; #204 only removed the dead button from the published file) |
| B-9 | Prototype: owner, due, priority and status cells are editable in the table at any time (there is no Edit mode). 0.2.1: only in Edit mode. | both | no item yet (#80 v0.3 shipped them in Edit only; it looks like a deliberate product choice but I found no decision that says so) |

### Work items table, Edit mode and inline pickers

| # | Difference | Seen at | Board item and release, or mark |
|---|---|---|---|
| B-10 | 0.2.1: Priority is not editable on risks, issues and decisions (no button). Prototype: editable on every row. | 1400 | after 0.7 (#210 is an Idea with release Unscheduled) |
| B-11 | 0.2.1: cells look cramped ("Medium" wraps, owner caret on its own line, status pill tall); at 900 the due date wraps "05-11- / 2026" and a Dependency badge breaks. Prototype cells are one line. | both | #203 v0.4 (in review, built after 0.2.1; covers Edit cells, not the View badge in 7) |
| B-12 | Prototype: the status picker on a risk or issue has a Rating section (Red, Amber, Green) under Open, Closed, Cancelled, so the table can change the colour. 0.2.1 Edit: the picker offers only Open, Closed, Cancelled; a risk reads "Red" in View and "Open" in Edit, and its rating cannot be changed in the table. | 1400 | no item yet |
| B-13 | Prototype: the Status cell shows the live look (Due soon, Overdue, Red, Green) and the picker sets the raw status. 0.2.1 Edit shows the raw status word (a code note says this is on purpose, "the pick and the cell say the same"); View shows the live pill. | 1400 | no item yet (the team to decide; no issue states the choice) |

### Empty states

| # | Difference | Seen at | Board item and release, or mark |
|---|---|---|---|
| B-14 | Prototype: "No open items match “zzzz”." in a dashed box with Clear search. 0.2.1: "No items match these filters." with Clear all, plus the chip row. Same idea, different words. An empty project (no items at all) could not be reached in either demo set. | 1400 | #153 v0.6 (in review, built after 0.2.1) |

### Board

| # | Difference | Seen at | Board item and release, or mark |
|---|---|---|---|
| B-15 | Prototype cards: letter badge, ID, eye only when shown to the client, a "..." Move to menu always present, compact. Dragging a card or using Move to works with no Edit mode (a drag showed "PDF-002 moved. Undo"). 0.2.1 cards: word badge, eye, bigger; in View the bar says "Switch to Edit to move cards" and there is no "..."; in Edit, drag and Move to… both work (toast "TUL-A-001 is now Delayed. Undo"). | 1400 | no item yet (same root as 9) |
| B-16 | Prototype: drag a column heading to move the column, drag its right edge to resize (260 to 640 px, double-click resets), Alt+Left or Right moves it from the keyboard. 0.2.1: none of these. | 1400 | no item yet (#68 and #81 do not list them) |
| B-17 | Prototype: swimlanes (No lanes, Type, Workstream) inside the View menu. 0.2.1: a "Swimlanes" menu on the board bar (None, Type, Workstream when the columns are not workstreams). Same choices, different place. | 1400 | #153 v0.6 (in review, built after 0.2.1) |

### Peek and Sneak peek

| # | Difference | Seen at | Board item and release, or mark |
|---|---|---|---|
| B-18 | The peek itself: opens beside the list, address changes to `&item=ID` and replaces (not pushes) when stepping with Previous and Next (checked in the prototype), Esc closes and gives the focus back to the row. 0.2.1: nothing opens. | both | #42 v0.4 (Building) |
| B-19 | Whole-screen button in the peek top bar (and Back to your width); width drag with double-click to reset. The width drag is in #42; the whole-screen button is not in its Done-when. | both | #42 v0.4 partly |
| B-20 | Coloured icons in the peek (status, priority, due by their colour). | both | #78 v0.4 (in review, built after 0.2.1) |
| B-21 | Activity tab: every history row with who, how, field, from to, with the filter All, Changes, Comments and updates; Updates and Source tabs. | both | #123 v0.4 (in review, built after 0.2.1) |
| B-22 | "Raised ... Last reviewed ..." line and the "Not reviewed in 14 days" chip. | both | #158 v0.5 (in review, built after 0.2.1) |
| B-23 | Needed from the client switch ("Lists it under Needs from you"). | both | #121 v0.5 (Building; prototype side #144 v0.5, Ready) |
| B-24 | Sneak peek: the sparkle button or two slash keys open a box; typed words ("move to friday, owner Jo, high priority") are read by plain code into a from-to card (Due 29-10 to 06-11, Owner changed); Enter applies at once with a toast and Undo; Esc closes. Confirmed it is plain code, not a model. 0.2.1: none. | both | #42 v0.4 (Building) |
| B-25 | Draft email button in the peek (also the C key). | both | #50 v0.3 (in review, built after 0.2.1) |
| B-26 | Latest update field with a Draft button (writes a line by rules) and a "Last updated" stamp. | both | no item yet |
| B-27 | Details block, editable in place: Description, Type, Workstream, Milestone, Use case, Client wording; the title edits in place. 0.2.1 cannot edit any of these (the table edits only four fields). #42 says the peek shows the item's fields; it does not say they are editable. | both | #42 v0.4 partly |
| B-28 | Warning bar above the title: "3 days overdue (due ...)" with Move to Friday and Move a week on; a due date on a weekend gets "a working day is usually meant" with Move to Friday and Move to Monday. | both | no item yet |
| B-29 | More menu: Duplicate and Archive (Undo in the toast); Copy link button; an archived item opens read-only with a Restore button. #97 lists Duplicate, Archive and Copy link only for the right-click menu. | both | #97 v0.4 partly (Building) |
| B-30 | The prototype peek and its cells always edit (no Edit and View modes); #42 says that in View and in the published file the peek shows fields only. A deliberate difference, not a gap to close. | both | changed by a decision (#42 Done-when: "In View and in the published file the peek shows fields only") |

### Milestones: Plan (timeline, Today line, labels, Legend, markers, list)

| # | Difference | Seen at | Board item and release, or mark |
|---|---|---|---|
| C-M1 | Prototype has a page header: project name above, title, a one-sentence summary ("<last milestone> is agreed for ..., 1 achieved, 5 to come."). 0.2.1 has only the title "Milestones" in a card. | both | no item yet |
| C-M2 | Prototype has a Plan / Movement switch under the header, with a hint line for each. 0.2.1 has no switch: Movement sits under the list and shows only in Edit. | both | no item yet (the switch is a prototype choice; #44 and #136 built Movement as an Edit block) |
| C-M3 | Prototype has an "Add milestone" (+) button; it adds a milestone 30 days out and opens it in the peek with the name selected. 0.2.1 has no way to add a milestone on the page. | both | no item yet (the page-side add is not on the board; #44 and #126 do not cover it) |
| C-M4 | Prototype has a "Show archived" pill with a count; on, it shows an "Archived" box ("No archived milestones." when empty; otherwise muted rows with an "Archived" tag and linked work items). 0.2.1 has none, though archive exists in the store (#126). | both | no item yet for the product page (#166 is the prototype reference, v0.4, Shipped; #126 item 10 leaves the page side "later") |
| C-M5 | Timeline/Calendar switcher: prototype buttons show icon and word ("Timeline", "Calendar"). 0.2.1 shows two small icon buttons with no words. | both | no item yet (small) |
| C-M6 | "Hide/Show milestone details" toggle above the list (remembered). 0.2.1 has no toggle; the list is always shown. | both | no item yet |
| C-M7 | List rows: prototype shows a progress bar and per cent (from data). 0.2.1 shows "Not set" for every milestone in the demo; the column exists, but progress can only be set through the peek. | both | covered by #42 (v0.4) |
| C-M8 | In Edit, the prototype list rows carry an eye to take a milestone off the client page. 0.2.1 has no eye on milestone rows (client visibility cannot be changed on the page). | both | #42 (v0.4, peek eye) partly; no item for the row eye |
| C-M9 | Timeline drawing, Today line and label, expected (dashed ring) markers, connector line, zoom by dragging the bottom edge, Earlier/Later/Today buttons, Legend (hover and focus, same words): same in both. Label overlap in 0.2.1 at 1400 ("Staff training complete" over the Today line and the "Expected" text) is still there in the demo; the prototype keeps its labels in separate lanes. Labels at the left and right edge of the line are cut off in both at 900 (not a gap). | both | built after 0.2.1: #227 "Milestone timeline label" (v0.3, In review) |
| C-M10 | Row text: prototype "Expected a date · 4 days later" is one line; 0.2.1 wraps the same words over two lines at 1400 (narrower date column). | 1400 | no item yet (minor) |
| C-M11 | At 900 px, 0.2.1's list rows stack (state and progress drop under the name and date); the prototype keeps one row. | 900 | no item yet (minor) |
| C-M12 | The Week / Month / Quarter control in 0.2.1 has a clipped edge: the selected pill is cut by the control's border (a small arc at the left of "Week" and the right of "Quarter"). The prototype's control is clean. | both | no item yet (minor look) |

### Milestones: Calendar (Week, Month, Quarter)

| # | Difference | Seen at | Board item and release, or mark |
|---|---|---|---|
| C-C2 | Chips show the full milestone name in the prototype (Week and Month at 1400; wrapped in Week at 900). In 0.2.1 the chip is cut ("Expected: Staff trai...") at 1400 and shows only the icon at 900. Expected chips in 0.2.1 carry an "Expected:" prefix; the prototype shows the bare name. | both | no item yet (minor) |

### Milestones: Movement (Edit only in 0.2.1)

| # | Difference | Seen at | Board item and release, or mark |
|---|---|---|---|
| C-V1 | Prototype: a table with month names across the top, one track per milestone on a shared scale, a Variance column and a key line (Original, Agreed, Forecast, Distance past agreed, Today); at 900 it keeps the table. 0.2.1: each milestone is its own bordered row with a track zoomed to that row, no month scale and no key line; at 900 each row becomes a stacked card. | both | no item yet |
| C-V2 | Prototype decisions: Hold, Move the agreed date, Add a recovery action, Escalate to steering (the last two create a linked work item and open it). 0.2.1: Hold and Move the agreed date only. | both | no item yet for Recovery and Escalate |
| C-V3 | Prototype has an Internal note box (saves on leaving the box, never published). 0.2.1 Movement has no note box; Hold writes a line into the change record shown under "What changed". | both | no item yet (#44 Done-when mentions an internal note) |
| C-V4 | Prototype has an "Edit milestone" button on the chosen milestone card and chips (Original, Agreed, Forecast, Moved n times, Progress, Owner). 0.2.1 has the same facts as text but no Edit milestone button. | both | #42 (v0.4) |
| C-V5 | Move the agreed date: in the prototype Movement button it happens at once (one toast with Undo; the confirm dialog is in the peek). 0.2.1 opens a form (new date, who agreed it, reason, source) with a written confirmation sentence and "Move the agreed date" / "Keep the date". 0.2.1 is ahead here. | both | changed by #136 (v0.2, Shipped): not a gap |

### Milestone editing and rebaseline (the peek)

| # | Difference | Seen at | Board item and release, or mark |
|---|---|---|---|
| C-P1 | Prototype peek: state buttons (Forecast, On track, At risk, Slipped, Overdue, Achieved) with the reason line, dates (agreed, forecast, achieved), a "Move the agreed date..." dialog (Cancel / Move the agreed date, "the original date is kept, and Movement shows the change"), progress slider and number, description, owner, workstream, client switch and client wording, linked work items, All / Activity / Updates / Source tabs, eye, Sneak peek, Previous/Next. 0.2.1: none of it; a click opens nothing, and progress, owner and client wording cannot be set from the page. Only Movement's Hold and Move can change a milestone. | both | #42 (v0.4, Building; the field list is not in its Done-when, which names work items first) |

### Help

| # | Difference | Seen at | Board item and release, or mark |
|---|---|---|---|
| C-H1 | Prototype Start here (hero, the loop, first ten minutes, twelve jobs, where things are, four rules): 0.2.1 shows the empty-state sentence. | both | #82 (v0.4, In review); parts release as the held list is emptied |
| C-H2 | How do I...: prototype has 24 tasks in 6 groups; 0.2.1 shows 1 task. | both | #82 (v0.4); each held entry waits for its own item (peek #42, filters, Publish, ask clark #47, templates #96...) |
| C-H3 | Reference: prototype has about 28 sections in 6 groups with a contents list on the left (at 900 the list is a narrow rail); 0.2.1 has one section (keys) and a one-line contents list. Icons, Milestone states and marks sections are held. | both | #82 (v0.4); milestone sections wait for #42 |
| C-H4 | Keys table: prototype lists all keys (/, double /, Esc, Enter, Shift+Enter, Mod+Enter, Alt+/, and more); 0.2.1 shows 6 (?, menu arrows, V, E, Alt+arrows, Home/End). 15 are held until their parts exist. | both | #82 (v0.4); keys follow #47, #42, #72, #193 (v0.7) |
| C-H5 | Opening: prototype has Help reachable from the top bar and the page shows "Back"; 0.2.1 has Help only in the profile menu and the ? key, and a "Close Help" button. | both | no item yet for a top-bar button (#82 text says ? opens it and "Help in the profile menu") |
| C-H6 | Search box: prototype has a search icon and a "/" key chip inside the box; 0.2.1 has the box with neither. The "/" key itself works in both (focus went to the box in both when pressed outside it). | both | no item yet (look) |
| C-H7 | Layout: prototype is a page of cards with a contents rail and the search at the top right; 0.2.1 is a bordered panel with search on the left, a Close button and a tab underline (at 900 the search sits under the heading, full width). | both | no item yet (look) |
| C-H8 | Held entries (19 passages in helpHeld.json, prototype-only or creaite-only text) deliberately left out; the prototype still shows them (e.g. "In this prototype..." notes). | both | changed by #82 review (helpHeld.json: "the review decides what replaces it"); #209 (v0.4) covers one example |
| C-H9 | Search results: prototype marks the matched word (yellow background) in titles and text; 0.2.1 lists the same two results for "keyboard" with the same layout ("2 results", group labels) but no mark. Snippet wording differs where the prototype uses a symbol ("press ...") and 0.2.1 spells it out ("the three-dots button"). | both | no item yet (look) |
| C-H10 | Empty search result: prototype says "Nothing in Help for ... Try another word, or ask clark." with an ask clark button; 0.2.1 says "Try another word, or look through the tabs." | both | #47 (v0.3, In review) partly (ask clark itself) |
| C-H11 | Search over held content: "milestone peek" finds 13 results in the prototype and none in 0.2.1 (the entries are held, so they are not searchable). | both | #82 (v0.4); follows as entries are released |

### Past reports and Publications

| # | Difference | Seen at | Board item and release, or mark |
|---|---|---|---|
| C-R1 | Prototype has a Past reports page (address #past; profile menu entry "Past reports (mockup)", tagged "Mockup for review") with three ways in (Week picker with "As published" / "As at that date"; Published reports list with Open buttons; Timeline of publications), a banner "You are looking at ..., as it was published. Back to now", a tinted read-only frame and a watermark. 0.2.1 has no such page and no list of publications: addresses such as #past, #publications, #history and #activity fall back to the Dashboard. | both | mockup only (#125: "a design and review item, not a build"; board state In review). Build follows from #120 (v0.5) numbered publications |
| C-R2 | Prototype Settings has a "Published reports" section (open the kept copy, numbered, last 10 kept); 0.2.1 Settings has none and no publication numbers. | both | #120 (v0.5, In review) |

### History / Activity

| # | Difference | Seen at | Board item and release, or mark |
|---|---|---|---|
| C-A1 | Prototype's peek has an Activity tab (All, Activity, Updates, Source tabs, a Changes / Comments and updates filter, "Nothing here yet." when empty). 0.2.1 has no peek, so no Activity tab anywhere; the only history on a page is Movement's "What changed" feed. | both | #123 (v0.4, In review) and #42 (v0.4, Building) |

### Excel import screens

| # | Difference | Seen at | Board item and release, or mark |
|---|---|---|---|
| C-X1 | Prototype has "Export workbook" and "Import workbook" buttons (Settings > Data, and on Work items) and an "Import from Excel" dialog (what is read, the columns, Get the template, Cancel, Choose a file), then a "Check the import" dialog (counts new, updated, skipped; per-sheet line; first 8 rows; "and 1 more"; Cancel / Import 9 rows). 0.2.1 has Export to Excel in the profile menu (#77, #147, Shipped) but no import button, no route and no screen: `server.py` says "later items: /api/import". The import code (#38, #129, #143) is shipped as code only. | both | no item yet for the page, route and review screen (#38, #129, #143 are Shipped and cover the code; #169 and #202 are v0.4 and only change the record) |
| C-X2 | Prototype's "Get the template" workbook: 0.2.1 has no template download. | both | no item yet |
| C-X3 | Prototype's review is simple (counts and the first rows); the product's code (excel_import.py) already stages new, changed and removed rows with clashes: the product's design is richer than the prototype's. | n/a | changed by #38 and #129 (Shipped) |
| C-X4 | The two workbooks do not share a layout. The 0.2.1 export names work items by "Description" and adds Project, Order, Source and Updated; the prototype's importer expects Type, Title, Rating, Latest update. Feeding the real 0.2.1 export to the prototype reads 6 milestones and 3 use cases, and skips all 37 work-item rows as "no name". The product's own sheet and header names are the real target. | both | no item yet (the team decides which layout the prototype should show; #143 only handles old names) |

### Profile menu and top bar

| # | Difference | Seen at | Board item and release, or mark |
|---|---|---|---|
| D-1 | Prototype menu has a Dark mode entry (System, Light, Dark); the 0.2.1 menu has none. | both | #179, v0.3, In review **Built after 0.2.1.** |
| D-2 | Prototype menu opens with a name line ("No name yet: add it in Settings > Profile"); 0.2.1 has no such line. | both | #180, v0.3, In review **Built after 0.2.1.** |
| D-3 | Prototype menu has Published reports (the numbered list of what was published); 0.2.1 has no list of past publications. | both | #120, v0.5, In review (numbered publications; the list page is not named in the item, so partly) **Built after 0.2.1.** |
| D-4 | Prototype menu has Past reports (mockup); 0.2.1 has none. | 1400 | Mockup only (#125, a design backlog item to keep and show a historic view) |
| D-5 | Prototype top bar has an "ask clark" button with a "/" key hint; 0.2.1 has no button, no panel and no route. | both | #47, v0.3, In review; #214 (the panel), v0.3, Building **Built after 0.2.1.** |
| D-6 | Prototype top bar has a "?" Help button; 0.2.1 has Help only inside the profile menu. | 1400 | #82, v0.4, In review **Built after 0.2.1.** |
| D-7 | Prototype has a Use Cases tab; 0.2.1 has Dashboard, Work items, Milestones, Settings. | both | #157, v0.4, Ready (editor page; the published side is #168, v0.4, Building) |
| D-8 | Prototype has a project switcher in the top bar; 0.2.1 shows the project name as plain text. | both | No item yet (the shell group should confirm; not covered by any board title) |
| D-9 | Prototype Dashboard has a Week ending date box and a status chip ("Draft - not published yet", then "Published ... locally"). 0.2.1 has no week box in the bar, and its "Published ... to the client" note shows at 1400 only (it is gone at 900, so after publishing nothing in the bar says so). | both | No item yet |

### Publish dialog

| # | Difference | Seen at | Board item and release, or mark |
|---|---|---|---|
| D-10 | Subtitle: prototype says "this will be Publication N" and "last published ..."; 0.2.1 shows project and week ending, plus "Published <day> to the client or locally" once something was published. Only the publication number is missing. | both | #120, v0.5, In review **Built after 0.2.1.** |
| D-11 | Prototype has "Also a Word document"; 0.2.1 has no Word tick (docx_build.py exists but no route or button calls it). | both | #48, v0.3, Building (build done, route and button left); #219, v0.3, In review **Built after 0.2.1.** |
| D-12 | Prototype has "Also a PDF"; 0.2.1 has none. | both | #124, v0.5, In review **Built after 0.2.1.** |
| D-13 | Prototype shows an amber box warning about open items with no owner or date and items not reviewed in 14 days (Show them). 0.2.1 shows the "no owner or no date" line with Show them in a plain box. | both | Changed by a decision: the warnings are to be removed from the dialog (#222, v0.3, In review); the prototype still shows them **Built after 0.2.1.** |
| D-14 | To client line: prototype says "Set it in Settings, Publishing" with a link to the Publishing card; 0.2.1 says "Set it in Settings." as plain words (no link) and Settings has no card named Publishing, only Client folder. | both | No item yet (small) |
| D-15 | Local line: prototype adds "it opens where you last saved" (and falls back to downloads when there is no save window); 0.2.1 says only that you choose folder and name in the save window. | both | No item yet (wording only) |
| D-16 | Working and finished states: prototype puts a spinner on the Publish button, then a tick with "Published (Publication N)", closes itself after about a second and shows a toast with Undo. 0.2.1 dims the buttons and shows "Publishing..." under the options, then keeps the dialog open with a green message (it says what happened to the client copy) and a Close button; no auto-close, no Undo toast. | 1400 | No item yet (the "Publication N" words come with #120, v0.5) |
| D-17 | Warning shown when To client is ticked: prototype says "The client will see this page. Only what is shown in View mode is included."; 0.2.1 says only "The client will see this page." | 1400 | No item yet (wording only) |

### Preview and the published file

| # | Difference | Seen at | Board item and release, or mark |
|---|---|---|---|
| D-18 | Preview in 0.2.1 gives a one-use link: opening the same address a second time answers "That could not be found. Reload the page and try again." as plain text on a white page. The prototype writes the page into the new tab, so it can be reloaded. | both | No item yet |
| D-19 | Published page top: prototype has a dark banner (project name, "WEEKLY REPORT - Week ending - for <client>") with the tabs inside it; 0.2.1 has a top bar with the tabs, the project name in the first card and "As at <date>" at the right. | both | #176, v0.4, Merged (the local look and the still picture; partly) **Built after 0.2.1.** |
| D-20 | At 900 px the prototype page has an "On this page" button; 0.2.1 has only the thin tick rail. | 900 | #141, v0.6; the board shows it as Shipped, but the 0.2.1 page does not have it, so the board state is ahead of the tag (the item is in main after 0.2.1) **Built after 0.2.1.** |
| D-21 | Published tabs: prototype has Dashboard, Work items, Milestones, Use Cases; 0.2.1 has the first three. | both | #168, v0.4, Building (file side); #163, v0.4, In review (read route) **Built after 0.2.1.** |
| D-22 | Published Work items: the prototype shows client items as cards grouped by type (Actions, Risks and issues, Decisions) with Overdue and Due soon pills, a search box and drop-down filters. 0.2.1 shows the editor's table grouped by workstream, with Open, Closed and All counts, Group by and the editor's filter row. | both | Changed by a decision: the client page gets the editor's filters (#69, v0.4, In review); the prototype page was not updated **Built after 0.2.1.** |
| D-23 | Published Milestones: same timeline, same list, same status words. The prototype's two view buttons carry words (Timeline, Calendar) and Legend has an icon; 0.2.1 uses icon-only buttons and a plain Legend. | both | No item yet (look only) |
| D-24 | Published Milestones list at 900: the prototype keeps one row per milestone (date, name, state, progress). 0.2.1 stacks the state under the date and pushes the name to a second column, so each row is about twice as tall. | 900 | No item yet |
| D-25 | Published Milestones list: 0.2.1 shows five rows and "Show all 6 milestones"; the prototype lists them all. | 1400 | No item yet (for the product owner to say which is the target) |

### Export (Excel) and Word

| # | Difference | Seen at | Board item and release, or mark |
|---|---|---|---|
| D-26 | Excel follows the committed look: 0.2.1 writes its sheets in Arial and the demo's token colours; the committed look is Inter and Montserrat. (The prototype's own workbook has no styling at all, so this is a gap against the committed look, not against the prototype.) | n/a (file) | #226, v0.3, In review (merged in main); Word and email too: #187, v0.5, Ready **Built after 0.2.1.** |
| D-27 | Excel import: the prototype has Import workbook (Settings > Data, and an upload icon on Work items) and Get the template; 0.2.1 has the import engine but no route and no button (the server notes "later items: /api/import"). | both | No item yet (#38 shipped the engine only; no board item names the page part) |
| D-28 | Export places: the prototype exports from Settings > Data, from a download icon on Work items and, for use cases only, from the Use Cases page; 0.2.1 exports only from the profile menu, one whole workbook. | both | No item yet (the use-cases-only export may follow #157, v0.4, Ready; not named in it) |
| D-29 | Export file name: prototype "<date> <project name> work items.xlsx"; 0.2.1 "<code>-<date>.xlsx". | n/a (file) | No item yet (for the product owner to say which name is the target) |
| D-30 | The user's own Word template ({{NAME}} placeholders): the prototype has no template feature; 0.2.1 has none; the fill is merged in main as a function with no route or button. | n/a | #219, v0.3, In review (part of #48, v0.3, Building) **Built after 0.2.1.** |

### ask clark

| # | Difference | Seen at | Board item and release, or mark |
|---|---|---|---|
| D-31 | The ask clark panel: the prototype has a full-height right panel (navy head with a new-chat and a close button, "Answers are worked out from this project's data", a greeting, bubbles with the clark icon, a box with a send button). 0.2.1 has none of it. Pressing / and Ctrl or Cmd+J in 0.2.1 does nothing. | both | #47, v0.3, In review (slices); the panel is #214, v0.3, Building **Built after 0.2.1.** |
| D-32 | Pills and the working line: one row of six pills that scrolls sideways; while a question runs the pills go and dots with a changing office line sit above the box. None in 0.2.1. | both | #102, v0.3, Shipped in the prototype only; product part is #214, v0.3, Building, inside #47, In review **Built after 0.2.1.** |
| D-33 | "What will be sent" line with Show details above the box (sources, word counts, provider). | both | Changed by a decision: removed completely (comment on #122); the prototype still shows it |
| D-34 | Asking off: the prototype shows "Asking is off. Turn it on in Settings." in the panel, and Settings has an Asking card with an On/Off switch, the connect sentence and a list of folders ask clark may read (Choose folder, up to 20). 0.2.1 has no Asking card. | both | #170, v0.3, Shipped in the prototype only; product: #47 and #214, v0.3 (the folder reading is #212, #213 and #215, v0.3, In review) **Built after 0.2.1.** |
| D-35 | The panel can be dragged wider, keeps its width, and a double-click puts the usual width back. | 1400 | #47 (47a: drag wider, keeps its width), v0.3, In review; the double-click is not in the item **Built after 0.2.1.** |
| D-36 | Keys: / opens the panel outside a field, Esc closes it, Enter sends, Shift+Enter makes a new line. | n/a (keys) | #47 and #214, v0.3 (/ and Esc are named) **Built after 0.2.1.** |
| D-37 | Ctrl or Cmd+J opens and closes the panel in the prototype. | n/a (keys) | No item yet (not in #47 or #214; for the product owner to say whether it is a target) |
| D-38 | Action buttons inside answers (Show it, Save as the latest update, Use it as the Summary, change health), each with an Undo toast. | 1400 | #47, v0.3 ("changes save with Undo"); which buttons exist is not listed there, so partly **Built after 0.2.1.** |
| D-39 | Settings > AI: Claude Connect, OpenAI "Later", model choice. 0.2.1 has no AI card. | both | #54, v0.5, In review (v0.3 is Claude only through #47) **Built after 0.2.1.** |

### AI menu in the editors

| # | Difference | Seen at | Board item and release, or mark |
|---|---|---|---|
| D-40 | The editor toolbar has a "AI" button, a "/ for commands and AI" hint and Alt+/ on selected text, with the options grouped (Improve, Structure, Make into, Ask...). 0.2.1 has none, and in 0.2.1 no rich text editor can be opened at all (see the last row of this table). | both | #72, v0.3, Building; #217 (places and groups), v0.3, Building. The page logic is already merged in main, not shown to a user **Built after 0.2.1.** |
| D-41 | The suggestion card: shows the result with Show changes, Try again, Discard and Accept; nothing changes before Accept. None in 0.2.1. | 1400 | #218, v0.3, Building (the card is merged in main, not wired to an editor) **Built after 0.2.1.** |
| D-42 | "Draft from the project" and a Draft latest update button. | 1400 | #72, v0.3, Building **Built after 0.2.1.** |
| D-43 | Text sections (Current state, Summary, This week, Next week) can be edited in place in the prototype. In 0.2.1 the editor is switched off (its writes list is empty), so these sections show "Not shown on this page yet." in Edit; this also blocks the AI menu. | 1400 | #220, v0.7, On hold |

### Draft email

| # | Difference | Seen at | Board item and release, or mark |
|---|---|---|---|
| D-44 | The Draft email dialog (kind, To, Subject, Reply by, tone, Include the latest update, an editable preview, Copy for Outlook, Copy as text, "I sent it" with an Undo toast). 0.2.1 has none mounted: the builder and the dialog component exist, with no route and no button. | both | #50, v0.3, In review **Built after 0.2.1.** |
| D-45 | The envelope button and the C key that open it from the peek. 0.2.1 has no peek. | 1400 | #42 (the peek), v0.4, Building |
| D-46 | Tone steps read First, Second, Firmer in the prototype; the board wants First chase, Second chase, Firmer chase wherever a person sees them. | 1400 | After 0.7: #208, Unscheduled, Building |
| D-47 | Draft email on the client page: not in the prototype; 0.2.1 has the component but nothing mounts it. | n/a | After 0.7: #51, Unscheduled, In review (#49, Unscheduled, On hold) **Built after 0.2.1.** |

### Settings (backups, version, the rest)

| # | Difference | Seen at | Board item and release, or mark |
|---|---|---|---|
| D-48 | Settings layout: the prototype has an intro line and a side list of sections (Profile, Personal, AI, Projects, People, Asking, Publishing, Published reports, Data, Version, Diagnostics). 0.2.1 has a card that says "Settings are not ready yet." and three cards (Client folder, Personal, Backups), with no list. | both | No item yet |
| D-49 | Profile card (name, alias, email, phone, organisation). 0.2.1 has none, yet its Excel History sheet tells the user to add a name in Settings > Profile. | both | After 0.7: #174, Unscheduled, Idea (first-run profile prompt); the menu line is #180, v0.3 |
| D-50 | Projects card (list, add, edit, archive, show archived). 0.2.1 has none. | both | No item yet (#126 shipped the archive in the store; the page part is not named) |
| D-51 | People card (everyone who owns an item, with email, organisation, role). 0.2.1 has none. | both | #115, v0.5, In review **Built after 0.2.1.** |
| D-52 | Publishing card: Local folder and Client folder. 0.2.1 has a Client folder card only (Choose folder, Clear) and no Local folder setting. | both | No item yet (Local always uses the save window) |
| D-53 | Version card (installed version, Update, install from a zip, roll back). | both | #109, v0.4, In review **Built after 0.2.1.** |
| D-54 | Diagnostics card (Normal or Debug, log folder, Copy diagnostics). | both | #110, v0.4, In review **Built after 0.2.1.** |
| D-55 | Dashboard block "Since the last report" and a Start from last week's report button (shown in Edit, next to the numbered publication). | 1400 | #118, v0.7, On hold |

## 4. Not checked

The prototype's folder, restore, install and connect flows were opened only as far as their first dialog; the native folder windows cannot show in a headless browser; dark mode on 0.2.1 was only checked by asking the browser for dark, because the app has no setting for it; phone widths are out of scope (laptop only); the launcher and a true first run were read in code, not run.
