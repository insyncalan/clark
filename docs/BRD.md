# clark: business requirements

Written by the project lead, 28-10-2026, from the approved brief (`PROJECT-BRIEF.md`), the owner's decisions (`DECISIONS.md`), the editor prototype (`system/prototype/`) and a teammate's architecture proposal (`ARCHITECTURE.md`, PR #4). The technical considerations in section 8 were written with a teammate.

**Status:** approved by the owner, 28-10-2026 ("Approved BRD (this will evolve)"); kept up to date as he decides.

**How to read it:** each requirement has an ID (BR- for business, FR- for function, NFR- for quality). Board items on the planning repo quote these IDs. Where the prototype already shows the behaviour, it's the reference ("as the prototype"). The prototype is a reference for screens and behaviour, not for code.

---

## 1. Why clark

Programme managers spend hours each week turning their work items into a report for clients and the team. They copy rows out of spreadsheets, retype status lines and rebuild the same tables. creaite solved this for one person on one laptop. clark takes creaite's report builder and makes it a product other programme managers can use: one place for work items and milestones, an editor for the weekly report, and a published page that clients can read and, from now on, respond to.

**Outcomes we want:**
- **O-1:** A weekly report takes minutes, not hours, once the work items are up to date.
- **O-2:** The client sees one clear, branded report, interactive in a browser, with no internal text in it.
- **O-3:** Work items live in one database with history. Excel and Word are ways in and out, never the record.
- **O-4:** Any programme manager can set up their own projects and brand without code changes.
- **O-5:** Client comments come back into clark without anyone retyping them (new, 28-10-2026).

## 2. Scope

**In scope:**
- Projects
- Work items: actions, risks, issues, decisions
- Milestones
- Use cases
- The report editor
- At a glance tiles
- ask clark, on Claude or OpenAI, whichever the user signs in to
- Import and export with Excel (and Word for the report)
- Publishing to HTML and Word, Local and To client
- The client page
- Client comments
- Draft email, in the editor and on the client page, ready to paste into Outlook
- Settings
- The design system and brand layering
- **Mac first, built ready for Windows** ("start with mac we can follow with windows but ensure when we build for mac we make allowances for the future")
- One user per database. clark's files may sit on OneDrive, but the database stays on the computer's own disk

**Out of scope for now:**
- Reading mail, Teams, calendars or transcripts.
- Sending by email or message. clark never sends mail and never makes an Outlook draft: Draft email only puts text on the clipboard for the user or the client to paste. Putting a file in the client's SharePoint folder is allowed only on the user's tick (approved 28-10-2026).
- Anything from creaite's private repos.
- Any real client, company or person's name in the repo. Demo data is fictional.
- Windows, which follows the Mac MVP. The MVP is built ready for it (section 8).
- Several people editing the same project's data. This comes later, at low priority ("start with single user for mvp/beta"); the options are D-11.

## 3. Who uses it

| Who | What they do |
|---|---|
| **Programme or project manager (the user)** | Keeps work items and milestones, edits the report, publishes it, reads and answers client comments |
| **Client reader** | Reads the published page, opens items, and comments on work items and use cases (new) |
| **Team reader** | Reads the published page |
| **Administrator (the same user, at first)** | Sets up projects, folders and brand in Settings |

## 4. Business requirements

| ID | Requirement | Source |
|---|---|---|
| BR-1 | Make the weekly report fast to produce from current work items | Brief |
| BR-2 | Publish one report per project, as an interactive HTML page and a Word document, with only the items and sections the user chose | Brief; the owner 27-10-2026 "one report" |
| BR-3 | Keep work items, milestones and use cases in a database with full history and undo; import from and export to Excel | Brief; the owner 27-10-2026 "a must" |
| BR-4 | Support many projects and many users, each with their own brand | Brief; the owner 27-10-2026 "keep multiple projects" |
| BR-5 | Capture client comments from the published page, into the database first, then into the Excel workbook automatically | the owner 28-10-2026; comments only, the owner 28-10-2026, amended by D-2 on 29-10-2026 (a client may also approve or decline a decision marked Needed) |
| BR-6 | Reuse as much of creaite as possible, copied with a record | Brief |
| BR-7 | Help the user make the most accurate report possible with ask clark, working only on the report's own data and listed source folders |  |
| BR-8 | One report, managed by the user: what the user shows is what the client sees, and nothing the user hides or keeps internal is in the published file | Brief; the owner 28-10-2026 |
| BR-9 | Let the user, and the client, draft an email about the report's items, ready to paste into Outlook, as creaite's Draft email does. clark never sends it |  |
| BR-10 | Let each user sign in to Claude or OpenAI for ask clark, reusing creaite's AI models work. clark works fully without either |  |
| BR-11 | Let teammates share their changes with the project's owner as a file, and let the owner import one or many into the master database before publishing |  |

## 5. Functional requirements

### 5.1 Projects and settings
- **FR-1:** Create, edit and archive projects (never delete, FR-43c): code, name, client name, week ending and health (On track, At risk or Off track, as in creaite) with its reason. Settings stay simple ("simple is best").
- **FR-2:** For each project, a Publishing setting: a local folder, and a client folder for To client.
- **FR-3:** For each project, the source folders ask clark may read.
- **FR-4:** **One report layout: Boxed** ("only have boxed as default - not in settings for selection"). There is no layout choice in Settings. Health spine and Cover-led are in the backlog at low priority (#46).
- **FR-5:** Reset demo data (prototype and demo builds only).
- **FR-8a (Update, 28-10-2026):** "add an 'update' functionality to settings like creaite". Settings › **clark version and updates** shows the installed version and installs a newer one from a **release file** (`clark-X.Y.Z.zip`; the source-code zip is refused with a plain message). There is **no online check** in the MVP: clark offers **Review X.Y.Z** only when the file is found in Downloads or chosen with **Choose zip…**. The review shows the version change, the release date, the release notes (copyable), the files replaced and added, and that projects, settings and published reports are kept. **Every file is checked against the release's checksum list before anything changes**; everything is **backed up first**, and a failed step **rolls back** to the old version. The last update shows with **Undo update** (a first click arms it, a second within 5 seconds undoes it). The prototype simulates all of it (no real files).
- **FR-8b (Logs, 28-10-2026):** "add logging to the application - log or debug set in settings". clark writes **one log file a day** to `~/Library/Logs/clark/`, **5 MB at most a day**, and keeps **7 days**, as creaite does. Settings › **Diagnostics** sets the level, **Normal** (info) or **Debug**, with a gentle note once Debug has been on more than 7 days. A log line holds only **counts, IDs and times, never content**: no report text, names, emails or keys. **Open the folder** shows the logs in Finder. **Copy diagnostics** puts a plain-text report on the clipboard from an **allow-list**: version, browser, system, log level, counts, safe settings (appearance, section style, layout by project code) and the last 20 log lines, never names, emails, project names or report text; if the clipboard is refused, the text is shown to select and copy. Errors of the last 7 days are listed, or "None".
- **FR-8c (Appearance, 28-10-2026):** "appearance - add system". Settings › Personal › Appearance offers **Light**, **Dark** and **System**, and **System is the default** for new users. System follows the Mac's setting (`prefers-color-scheme`) and changes live when the Mac switches. **Dark mode** in the profile circle menu sets an explicit Light or Dark.

### 5.2 The report editor
- **FR-19 (backlog, 28-10-2026):** **Standard browser navigation** ("backward swipe on trackpad should navigate back a page... standard browser navigation should apply"). Each page (Dashboard, Work items, Milestones, Settings), each opened peek and each project has its own address, so Back and Forward (the trackpad swipe, the mouse buttons, the keyboard) step through them, a page can be bookmarked or reloaded where it was, and Back from the first page leaves clark as usual. The same on the published client page for its tabs and the open detail.
- **FR-10:** There is one report per project with no internal and external versions. Sections: Current state, At a glance, Use case summary, Milestones, Summary, This week and Next week, Risks and issues, Open actions, Decisions, Supporting documents, plus any text sections the user adds.
- **FR-11:** View mode is read-only and shows exactly what the client will see. Edit mode makes everything editable in place.
- **FR-12:** **One editor everywhere.** Every rich text field uses the same full editor:
  - a toolbar
  - a formatting bubble when text is selected
  - a `/` menu
  - save on a click elsewhere or ⌘↵, cancel on Esc

  AI actions appear only where they're allowed. Current state has no AI.
- **FR-13:** All fields edit inline with no edit icon. This covers section titles, headlines and work item cells.
- **FR-14:** Sections can be moved by drag or by Alt and the arrow keys, hidden from the published page, and added as text sections.
- **FR-14a (#95, 28-10-2026):** **Two placements for every section** ("Either alone on a horizontal and taking up the entire row or two side by side taking up 50% of horizontal each"). In Edit, a section is dragged by its grip to a full row (a line between rows) or beside a section that is alone (a half outline). A row never holds more than two. Taking one half out leaves its partner full width. The section menu does the same by keyboard (Move up, Move down, Place beside the next section, Full width). Each move is one step with Undo. The published page keeps the rows; at 700 px or less a pair stacks. Touch screens use the menu.
- **FR-14b (#101, 28-10-2026):** **The section handle and menu** ("1. A 2. Accepted. include add a template below also"; option A, "Gutter handle"). In Edit only, each section has a grip in the page's left gutter with a **+** under it. Both are faint (about 0.3) until the pointer is over the section or the control has focus. They sit outside the card, so no section moves or narrows between View and Edit; the right half of a pair has its control in the gap between the cards. The grip is named "Move or change <title>" with the tooltip "Drag to move · click for options". Dragging keeps FR-14a. A click, or Enter or Space, opens the menu: Add a template below…, Move up (Alt ↑), Move down (Alt ↓), Place beside the next section or Full width, Leave out of the published page or Include, and Delete section (text sections and templates only). Alt ↑ and Alt ↓ work with focus on the grip. A section left out shows an eye-off mark on its handle. "Add a text section below" and any "+ Add a section" line between sections are gone; the **+** under the last section is the way to add at the end.
- **FR-14c (#96, 28-10-2026):** **Add a template: the dialog and its Help link.** The **+**, or the menu's first entry, opens "Add a section": a search box, kinds with counts (All, Text and pictures, Figures, Work items (RAID), Files and links, People and dates, Notes) and Recently used, a grid of the 18 templates (a sketch, a name, Full and Half chips), and a preview with what it holds, "Place it" (On its own row, or Beside the next section at half width when that section is alone and the template can be half width), and a link to Help. Arrow keys move through the templates, Enter adds, Esc closes, and the search filters as you type. Text adds a text section; every other template adds an empty section with each part labelled, a heading that can be renamed, and focus on that heading. It is one step with Undo (e.g. "Key figures, four added below Current state"). While empty, a template is left out of View, the published page and the Word file. Two links open Help › Reference › Section templates; Help also has the task "Add a section from a template". Filling the parts in is #96's build.
- **FR-14d (28-10-2026):** **View and Edit keys** ("in dashboard screen "v" will engage View Mode and "e" will engage edit mode"). On the Dashboard, V and E (no modifier) switch to View and Edit, as the buttons do (tooltips "View (V)", "Edit (E)"). They are ignored while typing in a field, heading or editor, and while a menu, dialog, ask clark or the peek is open. Help's keys table lists them.
- **FR-15:** The eye takes an item off the page. The item stays in view while an Undo toast shows, then leaves the editor.
- **FR-16:** "Add from your project record" opens a searchable picker with several selections at once.
- **FR-17:** A single click on a work item row, outside an editable field, opens its peek.
- **FR-18:** A discreet contents minimap sits at the right. It opens on hover or focus and closes when it loses focus. The section bar sticks to the top.

### 5.3 At a glance
- **FR-20:** The tiles are Project health (a pill and a multi-line reason; click the pill to change it), Overdue actions, High risks and issues, and optionally Decisions. Tiles can be reordered and hidden.
- **FR-21:** The tiles are neutral, with a thin status-colour outline fading from the bottom-left corner. The colour is automatic, and a right-click overrides it ("Outline fading from the bottom-left corner winner").

### 5.4 Use case summary
- **FR-30:** A summary strip shows the total, the count for each status and a meter. Below it are slim rows: an ID tag, the name, the headline, the status as a coloured word in one aligned column, and the open next steps (option D2).
- **FR-31:** A row opens in place to show Where it stands (rich text), its next steps as "Owner: what it is", a link to all its work items, and "Link an existing work item".
- **FR-32:** Use cases can be exported to and imported from Excel (a Use cases sheet).

### 5.5 Work items
- **FR-40:** Report sections show work items as list rows rather than boxed tables: a state pill, the item, who and when, and the ID. Statuses are creaite's: an action is Open, Delayed, Closed or Cancelled; a decision is Pending, Made or Withdrawn; a RAID item (Risk, Assumption, Issue or Dependency) is Open, Closed or Cancelled, with impact, likelihood and a priority worked out from them. A risk or issue's pill shows its priority as a colour (Urgent or High red, Medium amber, Low green), and picking a colour sets impact and likelihood (decided, D-12); then Close or Reopen.
- **FR-41:** The Work items view has creaite's full filters and an inline eye for client visibility (filters as option A, the owner 28-10-2026). **Table or board** by an icon switch, and **Group by** in place of the workstream dropdown ("the ability to have a table view or board view... copy all the capabilities of creaite work items board"). The board is creaite's (its FR-89, FR-110, FR-116): cards in columns grouped by workstream, status, due, owner, priority, milestone or type, with one level of swimlanes; dragging a card or its Move to… menu changes the item as an edit does, one step with Undo, both changes in one step across a lane and a column; Due asks for a date (never a past one; Overdue is not a drop target); columns count, collapse and are remembered; the same filters and search as the table. Workstream is a filter and a Group by choice.
- **FR-42:** The peek works as creaite's does. Its width can be dragged, and double-click resets it. It includes Sneak peek: `//` and plain words to change fields. Both Enter and Shift+Enter apply ("both"), and a toast offers Undo.
- **FR-43:** Every change is kept in the item's history and can be undone.
- **FR-43a (new, 28-10-2026):** The history is detailed enough to answer who changed what, where and when ("ensure that our work items all capture a detailed history of activity against changes", the owner). It covers work items, milestones and use cases.
  - Each history row holds: **when** (stored with its offset from UTC, shown in the viewer's local time as DD-MM-YYYY HH:MM), **who** (the full name from Settings › Profile, first), **how or where** (in the peek, in the table, on the board, in the report, with the eye, by Excel import with the file name, via ask clark, with a draft, from selected text, by sending an email, in words, or by undo), the **item**, the **field**, and the value **from** and **to**.
  - A create, an archive, a restore and an undo are each recorded. An undo writes one row for each field put back, with its from and to; undoing a create writes "Creation undone".
  - Rich text (a latest update, a note) keeps its whole from and to; the peek shows a compact word diff.
  - History is never pruned.
  - The peek's **Activity** tab lists the rows newest first, with the field's plain name and the values as a person reads them (dates DD-MM-YYYY, owners as names, statuses as words, "none" for empty), and a filter: **All**, **Changes**, **Comments and updates**.
  - The Excel export has a **History** sheet (When, Who, How, Item, Field, From, To, in plain values); the import ignores it.
  - Changes made by ask clark and by an import carry the person's name and say so ("<name>, via ask clark").
  - History is data, not logs: the diagnostic log never holds report text, names or values (FR-8b); a log line for a saved change holds only the kind, the ID and the field.
- **FR-43c (28-10-2026):** **Nothing is ever deleted; it is archived** ("we never delete - we archive"). Projects, work items, milestones, use cases and supporting documents have **Archive** where they had Delete. An archived record:
  - leaves the default views, the counts and the published page;
  - is found with **Show archived** (Work items, Milestones and Settings › Projects);
  - opens read-only with **Restore**;
  - keeps all its history.

  Archiving a project archives everything in it, recording one history row per record, and Restore brings them all back. Archive and Restore are each one step with Undo. ask clark, Excel import and the right-click menu archive and never delete. **The one exception is report sections** ("'Delete this section' an exception... this is simple work product allow delete and an undo toast"): a section is the user's own report layout and text, not a record, so **Delete this section** stays, with an Undo toast. The database keeps `archived` (it's already in the schema) and has no delete path for these records (Undo of something the same step just created still takes it back; report sections, links, labels and hidden flags are not records in this sense).
- **FR-44 (new, 28-10-2026):** **Draft email**, as in creaite (its FR-79, FR-186 and FR-241). It opens from the peek (an envelope left of Copy link, key C) for one open item, and from an owner's name for all of that person's open items.
  - The wording is plain code with no model call: a greeting by the time of day, the items grouped by project with overdue and due soon shown in colour and in words, a kind request for an update, an optional Reply by date, and a Subject that starts with the project's name.
  - Three modes: an update request, a chase (First, Second, Firmer, stepping up with each chase recorded) and a decision request to a decision's maker.
  - Items can be unticked, and the wording can be edited in the preview before copying.
  - **Copy for Outlook** puts the HTML and the plain text on the clipboard; **Copy as text** gives the plain text. Nothing is sent and no Outlook draft is made.
  - **I sent it** records the item IDs, the date and the mode in the item's history, never the email's text.
- **FR-45 (new):** For an address outside the user's own domains, items not marked client-visible start unticked and tagged "internal". Internal notes, hidden rows and the source of an item are never put in an email. The email is drawn on white with inline styles and simple tables, whatever the theme, so it pastes into Outlook as it looks. Polish the wording (a model call) waits for ask clark.

### 5.6 Milestones
- **FR-50:** Milestone states are creaite's (Achieved, On track, At risk, Slipped, Overdue) plus Forecast, worked out by creaite's rules: Overdue counts from the **agreed** date, not the forecast, and only At risk and Forecast are set by the user. A rebaseline records a decision, as in creaite. The client page uses creaite's client words: Slipped reads "Expected later" and Overdue reads "Late". Forecast reads "Forecast". **Slip in days** follows creaite v2.6.9: only a milestone with an agreed date that isn't achieved or a Forecast counts; it is expected on the later of its forecast (or its agreed date) and, once the agreed date has passed, today; slip is the days from the agreed date to then. A Forecast never needs a reason (the Head's rulings on #32, 28-10-2026).
- **FR-51:** A horizontal timeline that scrolls left and right, today line, slippage shown as in creaite (ghost marker and dashed line), and zoom by dragging its height.
- **FR-52:** The milestone list uses the design system's rail format. It shows 5 milestones, then "Show all", and has an eye in Edit mode.
- **FR-53:** The Movement view: what moved and why, with a decision for each milestone (hold, rebaseline, recover or escalate) and an internal note that is never published.
- **FR-54:** Milestones can be imported and exported on their own Excel sheet. Suggested milestones are removed.

### 5.7 ask clark
- **FR-60:** A full-height panel that can be dragged wider. `/` opens it. Esc or a click outside closes it. While it works it shows office quips.
- **FR-60a (28-10-2026):** **How the panel looks** (the owner chose "Wash" from four options, mockups in `comms/mockups/ask-clark/`): a light panel under a navy head with the brand picture, a soft blue glow rising from the bottom, clark's replies as plain text beside its icon and the user's as blue bubbles. The suggestions (Check this report, What's overdue?, Which risks are red?, Next milestone?, Summarise this week, Use cases) are one row of small pills, scrolling sideways. While it works the pills give way to the working line (dots and an office quip) above the box, and they return with the answer.
- **FR-61:** It works only on the report's project data and that project's source folders. It has no mail, Teams, calendar or web access.
- **FR-62:** Changes it proposes save as Sneak peek does, with an Undo toast. A change that comes from a source file always needs a confirm step.
- **FR-62a (28-10-2026):** **ask clark can create, read, change and archive every work item and milestone** (never delete, FR-43c) of the open project ("ensure clark has the permissions to CRUD all work items and milestones"): actions, risks, issues, decisions and milestones, every field the user can edit, and several at once ("close all of Sam's overdue actions"). Each change goes through the same one writer, history and checks as a change made by hand, under the user's name with "via ask clark". Changes are shown before they save, with Accept and Undo. A delete, and any change to more than five items at once, always asks first and lists what it touches. It never changes settings, keys, the published page's hidden items or another project.
- **FR-63 (new, 28-10-2026):** **Sign in to Claude or OpenAI** ("include logging into Claude and OpenAI as options for AI using ask clark"). Settings › AI shows one card per provider, as in creaite's AI models page (creaite #132):
  - **Claude:** sign in with a Claude subscription through the Claude command, or use an API key.
  - **OpenAI:** an API key, billed to the OpenAI account. Signing in with a ChatGPT account is open (D-7).
  - **Connect** tests the sign-in and asks the provider which models it can use; the user ticks the ones to offer. A refused key keeps the box open and says why (for example "OpenAI did not accept this key (401)"). **Disconnect** removes the sign-in, and anything set to that provider's models goes back to the recommended one.
  - With nothing connected, ask clark says it isn't set up and links to Settings › AI. The rest of clark works as before.
- **FR-64 (new):** **Keys are kept in the computer's own keychain** (the macOS Keychain), never in clark's database, settings, backups, logs, published files or the repo, and never shown again after they are entered.
- **FR-65 (new):** **Model choice:** ask clark's model list shows only the models of connected providers. The recommended model is marked and is the default. Choosing a weaker one asks first. The connect box says in plain words that the passages sent leave the computer and are billed to that account.
- **FR-66 (new):** **Limits:** when a provider's limit is reached, ask clark says so and offers the other connected provider or a smaller model. It never switches by itself.
- **FR-67 (new):** **The same ask clark on either provider.** The model needs no tools: clark searches the data and the source folders itself and sends only the chosen passages; the reply's proposed changes come back in a fixed form that clark checks against the data before showing them (from creaite's claims check and `EDIT:` lines). So Claude and OpenAI give the same features, the same checks and the same confirm step.
- **FR-63a (28-10-2026):** **Until v0.5, Claude only.** In v0.3 ask clark and the AI menu use Claude, through the Claude command or a Claude API key, as creaite works today. The connect box says plainly that passages go to Claude. The OpenAI card shows "Coming in a later version". FR-63 to FR-68 apply in full from v0.5 (#54).
- **FR-68 (new):** **Claude and OpenAI are handled the same** ("Both openai and claude handled the same.. no differnetiation."). There is no per-project switch: ask clark sends the same passages to whichever provider the user signed in to. The connect box says so in plain words (FR-65).

### 5.8 Import and export
- **FR-70:** A workbook export has the sheets Actions, Risks and issues, Decisions, Milestones and Use cases. Export buttons are icons with tooltips and are hidden in Edit mode.
- **FR-71:** An import is shown as changes for the user to accept. Nothing is written until then.
- **FR-70a (backlog, 28-10-2026):** **A better formatted, branded Excel export**: a cover sheet first (Current state, the At a glance health, Summary, This week, Next week and the text sections), the date it was exported and who exported it, a caution that it doesn't show changes made after that, and a note asking for updates to come back to the report's owner; frozen header panes, colour for status and priority, wrapped text and sensible widths; and AI help with the layout. The caution and the note use wording the owner approves (drafted in `comms/`).
- **FR-70b (28-10-2026, the owner):** **The Cover follows Option A**: one column in the dashboard's order. Current state comes first, then At a glance with the health pill and tiles, then Summary, This week and Next week. The export details sit in a quiet "About this export" block at the bottom ("Option A").
- **FR-70c (28-10-2026, "All work item sheets need to have dropdowns and colouring"):** **Every work item sheet has dropdowns and colouring.**
  - Every column with a fixed set of values has a dropdown with exactly clark's values, and anything else is refused by the sheet: Type, Status, Priority, Impact, Likelihood, RAG, Workstream, Use case, Milestone and Client-visible (Yes/No). Owner is a dropdown of the project's people when they exist (FR-31a), or a free-text column with a note otherwise.
  - Status, Priority, RAG and the health words are coloured with conditional formatting from the clark tokens, so a value changed in Excel recolours itself. Overdue dates are red.
  - Colour is never the only signal: the words stay.
- **FR-70d (28-10-2026, "Work item IDs need to be LOCKED because they cannot be edited and if someone adds a work item they will not provide an ID - that will be provided when the workbook is imported after update"):** **IDs are locked.**
  - The ID column is protected, with no password needed to read it. Every other cell stays editable, and adding rows, sorting and filtering still work.
  - A new row is added with the ID left empty. clark gives it the next free ID when the workbook is imported (FR-71), and the import shows "New: <title>" and the ID it will get.
  - An ID typed into a new row is ignored and named in the import plan. A changed or pasted-over existing ID is refused for that row, with a plain message, and the rest of the import continues.
- **FR-72:** The report can also be exported to Word.

### 5.9 Publishing
- **FR-80:** Publish asks where it goes: **Local** is always ticked, and **To client** is a tick each time. A standard save dialog lets the user choose the folder and overwrite or rename.
- **FR-81:** The HTML page is one self-contained file that refers to no outside address at all; fonts and pictures are embedded. It holds only what the user chose: anything left out is dropped before the file is made, not hidden.
- **FR-82:** **One output** (the owner, 28-10-2026, D-3: "a single report output managed by the user / editor"). There is no separate client version and creaite's client checks are not copied. The build leaves out everything the user has hidden and every internal note (FR-81), and a test checks the finished file for them.
- **FR-83:** Every publish is logged: what, where, when and who.

### 5.10 The client page
- **FR-90:** The client page has three tabs: Dashboard, Work items and Milestones. It has the same look and markup as the editor's View mode, the contents minimap, peeks that open on a single click, use cases that open in place, and search.
- **FR-90a (backlog, 28-10-2026):** **The client can filter work items as in the editor** ("in client report the client should be able to filter actions just like editor"): the type switch, Open / Closed / All, the Filter by row, chips, search and Group by, on the published rows only, inside the one file, remembered in the client's own browser.
- **FR-91 (new, 28-10-2026):** **The client can comment on work items and use cases** in the client page, and change nothing ("Clients can only add comments to work items also"; use cases: "only comment").
- **FR-92 (new):** Client comments go **to the database first**, where the user sees them. Each one records who wrote it (as entered) and when. They are **saved to the project's Excel workbook automatically**.
- **FR-93 (new):** The client sees their earlier comments, and the user's replies, on the next published page.
- **FR-94 (on hold, "Put this on hold for the client for now - editor only"):** **The client can draft an email too.** On the client page, an envelope in an item's peek, or on a set of ticked items, drafts an email to the project contact the user chose at publish: a question or an update about those items.
  - The same builder and look as FR-44, run inside the page: no server and no model. Nothing leaves the page except what the client copies.
  - Copy for Outlook, Copy as text, and Open in mail app (plain text only, for a short email).
  - Only rows and fields that were published can appear. The contact's name and address are put in the page at publish. Team members' addresses are never in the page.
- **FR-95 (new):** A Draft email never carries a change into clark. The client's edits come back only through the changes file (FR-92). The email may remind the reader that changes were saved.
- **How FR-91 to 93 work** is open (section 10, D-1). The recommendation, for the owner's decision:
  - The page stays one file with no server.
  - The client's comments are saved as a small changes file in the same SharePoint folder the report came from.
  - clark watches that folder through the user's OneDrive sync and shows the changes for review.
  - Accepted changes go through the one writer, and the Excel workbook is rewritten automatically.

### 5.10a Team changes (new, 28-10-2026)
"On the shared option... we'll need an option for each user to be able to 'export' a db file to share with me and then an option for me to be able to import it and it updates / syncs the changes to the master db (mine) before publish. Include option to import multiple". This is the several-users path for later (D-11, option C), in the owner's shape. The design is a teammate's `docs/handoff/team-changes.md`.
Then, the same day: "for team sharing clark should check on open to se if there is an updated master db available - stored in onedrive but not updated, a share only copy - users should be prompted on opening clark whether they want to update the database. so the journey is 1. they open, check performed to see if there is a new db, if so prompted to update 2. user edits 3. user extracts and shares / auto shares to a one drive location 4. I imort the extract and update the master db 5. db is available for the other users to copy an import. Single location on sharepoint for master db and extracts and app polls / manages".

**The journey:** (1) a teammate opens clark, it checks the shared location for a newer master, and if there is one asks whether to update; (2) they edit; (3) their changes are exported to the shared location, by hand or automatically; (4) the owner imports them into the master; (5) clark writes a new master copy for everyone else to take.
- **FR-96:** **The owner keeps the master** database and is the only person who publishes. **One shared location on SharePoint** (synced by OneDrive) holds the whole team share: `master/`, with `latest.json` and numbered share-only copies of the master (the last 5 kept), and `changes/`, with one file per export, each teammate writing only their own. No file is ever written by two people, so OneDrive never makes conflict copies. The real `clark.db` never sits there: a share-only copy is a finished snapshot of the shared projects, without the owner's folders, written under a temporary name and renamed, with `latest.json` written last. A teammate joins with **Join a team share**, and their copy is marked "copy of <owner>'s master, number N".
- **FR-96a:** **On open,** a teammate's clark looks for a newer master and asks once whether to update; Later keeps their copy. A copy is only loaded when its checksum matches `latest.json` (so one still syncing counts as "not ready"), it names the right master, its number is higher, its schema matches, and it passes an integrity check, opened read-only. **Updating never loses work:** clark exports the teammate's unshared edits first, replaces the copy, and puts back on top any of their changes the owner hasn't imported yet (`latest.json` lists which changes files each master includes).
- **FR-97:** **Export my changes** writes one changes file into `changes/` holding only the teammate's changes since their last export: for each field, its value before and after, who and when, with the file's checksum. With nothing new it writes nothing. **Auto-share** exports on close and every 15 minutes when there's something new (on by default, to confirm, D-13). The file type, JSON (recommended) or a small SQLite file, is open (D-13).
- **FR-97a:** **The owner's clark polls** the location and lists the changes files waiting, but never imports by itself. After each import, and on close after the owner's own edits, it writes a new master copy. SharePoint folder permissions back this up: `master/` is read-only for teammates and `changes/` lets everyone add, and clark warns a teammate who can write to `master/`.
- **FR-98:** **Import changes** takes one file, several at once, or everything waiting in `changes/`. Each file is checked before anything is staged: the right master, the right schema version, its checksum, its size, not imported before, only allowed fields, and every value through the same checks as a typed change. A file that fails is refused whole, with the reason, and the other files go on.
- **FR-99:** **Review before anything changes.** All the changes are put in time order and compared field by field with the master: applies cleanly, already the same, a clash with the owner, or a clash between teammates. A clash shows the values side by side (the starting value, the owner's and the teammate's, or both teammates' with names and times), and rich text is chosen whole. The owner can Accept all clean, accept or reject each change, and pick a side for each clash. Apply makes one step per file under the teammate's name, so each teammate's import can be undone on its own. Excel is then refreshed, and a new master copy is written for the team.
- **FR-99a:** **New items** a teammate made get the next free ID in the master, and every reference to them in the same file is rewritten. The review shows the old and new IDs.
- **FR-99b:** **What a teammate may change:** every field of work items, milestones and use cases, a project's current state and health reason, text sections, new items and comments. **Never:** settings, keys, folders, publications, the report layout, the client flag or what is hidden from the published page. Only the owner decides what reaches a client. The list is set per project, with this as the default (to confirm, D-13).
- **FR-99c:** **Before publish,** the Publish dialog says how many changes files are waiting and from whom, with **Import first**. It never imports by itself. Publishing anyway is allowed after a confirm, and the publish log records that files were waiting.
- **FR-99d:** Team changes and client comments (FR-91 to FR-93) are **built once, as one changes inbox** with two sources. A client file may only carry comments.

### 5.11 Supporting documents
- **FR-100:** Supporting documents is a list of links with a type and a date. Each can be shown, hidden or edited.

### 5.12 Design system and brand
- **FR-110:** The look comes from design tokens. The repo carries a fictional demo brand. A user's real brand is a local override in `system/branding/`, which is never committed.
- **FR-111:** The client brand uses the client's logo only.
- **FR-112 (28-10-2026):** **"ask clark" is always written in lower case** ("Ask clark always in lowercase"), like clark itself: in the interface, Help, emails, documents and the published page, and at the start of a sentence too. Rephrase a sentence so it does not need a capital, for example "In ask clark, choose…".

### 5.12a Accepted candidates ("candidates as recommended")
Raised by the second the project lead, reviewed by the lead.
- **FR-31a (v0.5, #115; moved from v0.2 by the owner, 28-10-2026):** **People are rows, not typed names.** Each person holds a name, email, organisation, role and aliases. An owner points at a person. Someone typed in on the fly is saved with a **Needs details** flag. Groups and distribution lists are kept apart from individuals. Rename, merge and delete are each one step with Undo. Excel and the team share carry the people. People are filled by Excel or CSV paste; picking from the Microsoft 365 address book comes later.
- **FR-35a (v0.5, #119):** **How fresh each item is**, worked out from history with no new columns: when it was raised, when it was last reviewed, and "not reviewed in N days". A missing owner or date is flagged before publish.
- **FR-83a (v0.5, #120):** **Numbered publications.** Each publish keeps a copy of the file and gets a number, listed in a Published reports list. A client comment is later tied to the publication the client saw.
- **FR-83b (v0.5, #124):** **PDF as a third publish format**, ticked beside Word and the web page.
  - It's made by printing the published page to PDF with Chrome, so it holds exactly what the page shows: the three tabs stacked, no controls, sections kept whole, page numbers, light mode, and the publish number in the footer.
  - The finished-file scan also runs on the PDF's text.
  - If Chrome is missing, the PDF tick is greyed out with a plain line saying why.
- **FR-12b (v0.5, #121, #144):** **"Needs from you"** is a section template.
  - It lists, soonest first, open decisions the client can see that are marked pending, and items marked **Needed from the client**, drawn live.
  - It also lists lines added by hand, each with what is needed, an owner and a due date (DD-MM-YYYY).
  - A late line says **"Overdue"** in words.
  - When it's empty, the published page leaves the section out and the editor shows "Nothing needed from you this week."
  - On the published page it sits straight after At a glance.
  - Lines are archived, never deleted.
- **FR-12c (v0.5, #118):** **"Changed since the last report":** a block worked out from history. A new week's report starts from the last one, with the text sections carried forward.
- **FR-62b (v0.5, #122):**
  - Before an AI request, **show what will be sent**: the sources, the size and the provider.
  - A **rule-based health suggestion**, with its reasons, sits beside the user's own health and never replaces it.
- **Backlog, low:**
  - **#116:** suggest people from mail headers. It's a narrow, opt-in exception to "no mail": headers only, run only on the user's click, from Settings › People, after FR-31a.
  - **#117:** a client approves a decision marked Needed. It's built inside the client-comments work and needs a D-2 amendment.

### 5.13 Help (v0.4, #82)
"Let's build a help for clark.... emulate the help built for creaite. review creaite help and capture ALL features and functions".
- **FR-120:** **Help is one page in three tabs**, all from one source of content: **Start here** (the report loop, the first ten minutes and the twelve everyday jobs), **How do I…** (26 tasks, each as numbered steps) and **Reference** (30 sections covering every view, field, key and the icon legend). The counts are as at 28-10-2026; the prototype's Help (`system/prototype/help.js`) is the source of truth for the list.
- **FR-121:** **One search across all three tabs** finds a word in titles and text, shows where each match sits, and opens it in place.
- **FR-122:** **Help opens from the profile menu** and from the **"?"** key anywhere outside a text field. Esc or Back returns to where the user was.
- **FR-123:** Other parts of clark can **open Help at a given place** (a task or a reference section), for example from an empty state or a setting's note.
- **FR-124:** Help works offline, follows light and dark mode, and is kept in step with the build: a test checks that every link inside Help finds its place and every screen it sends you to exists.

## 6. Quality requirements

| ID | Requirement |
|---|---|
| NFR-1 | **Private by default.** User data lives outside the repo. Nothing leaves the machine except To client copies, on the user's tick, and the passages ask clark sends to the AI provider the user signed in to. |
| NFR-2 | **Security:** the local server listens on 127.0.0.1 only, with a per-run token and a Host check. No secrets in the repo. No Microsoft sign-in held by clark. |
| NFR-3 | **Plain words and British English** in everything a user reads. creaite's banned-words list applies. Dates are shown DD-MM-YYYY and stored YYYY-MM-DD. "clark" is lower case and never starts a line. |
| NFR-4 | **Accessibility:** keyboard reachable, visible focus, a contrast ratio of at least 4.5:1 for text, and reduced motion respected. Impeccable's checks pass. |
| NFR-5 | **Screens are checked at 1400 px and 900 px.** |
| NFR-6 | **Tests:** everything that can be a test is a test. A hand check holds only judgement. The reviewer is never the builder. |
| NFR-7 | **Every change has a way back:** history and undo for data, and branches and pull requests for code. |
| NFR-8 | **Performance:** up to 20 projects, 5,000 work items and 500 milestones per user. A project opens in under 1 second, a change saves in under 200 ms, an import of 1,000 Excel rows takes under 5 seconds, and a page publishes in under 3 seconds. A published page stays under 5 MB and opens offline. |
| NFR-9 | **Built ready for Windows:** tests run on macOS. Source tests stand in for Windows readiness: nothing outside the platform layer calls a system-specific command, every `open()` names UTF-8, and file names follow Windows' rules. |
| NFR-10 | **Keyboard and phone** (a teammate's review, 28-10-2026; #87): every menu opens with focus on its first or chosen item and moves with the arrow keys, Home and End; the peek takes focus when it opens and gives it back to the row or card on close; board cards are buttons with a visible focus ring; calendar days move with the arrow keys; at 390 px wide nothing scrolls sideways and the top bar takes a second row for the tabs. |

## 7. Data (summary)

The data model is a teammate's `docs/handoff/data-model.md` (25 tables, checked in SQLite), revised on 28-10-2026 after the owner's ask: "ensure that the work item and milestone schemas reflect those of creaite...".
- **creaite's tables, unchanged:** projects, milestones, workstreams, actions, raid, decisions, links, labels, item_labels, updates, applies, change_log and item_events are copied from creaite v2.6.9: the same columns, IDs, value lists and checks. A test compares them with v2.6.9.
- **IDs are creaite's:** actions `<CODE>-A-NNN`, RAID items `<CODE>-NNN` (risks and issues share one series, the type is a field), decisions `<CODE>-D-NNN`, milestones `<CODE>-M-NNN`, workstreams `<CODE>-W-NNN`, and clark's use cases `<CODE>-U-NNN`.
- **Client wording** is creaite's `client_message`, with its three headings ("What it is", "What it means for you", "What is being done"). It is optional in clark: every work item is client-visible by default ("Client visible is toggled on by default for all work items"), so creaite's rule that a row needs its client wording before it can be shown does not apply.
- **clark's additions** to creaite's tables are marked `-- clark:` in the schema and listed in the model (the report fields on projects, Forecast and Movement on milestones, a use case link on work items, and who and which device made each step). Keeping them is D-12.
- **clark's own tables** cover use cases, the report's sections, tiles and hidden rows, saved views, documents, source folders, publications, client files, client changes and comments.
- History and undo are creaite's: one step per change, and Undo reverses exactly its own step. A row changed by a later step is skipped and named.

## 8. Technical considerations

Written by a teammate (technical architect), 28-10-2026. It reads with `ARCHITECTURE.md`. The full data model (25 SQLite tables, with the schema's checks run in SQLite) is in a teammate's `docs/handoff/data-model.md`, and it moves into `docs/` with her branch.

### Platform and runtime
- **Mac first, built ready for Windows** ("start with mac we can follow with windows but ensure when we build for mac we make allowances for the future"). The Windows port (Python's embeddable package and `clark.cmd`, Credential Manager, Windows tests) comes later. The allowances, each pinned by a test that runs on the Mac:
  - **One platform module.** Everything system-specific lives in `src/clark/platform.py`: the data folder, OneDrive roots, open and reveal, the Save and folder dialogs, replacing a file with a retry, and the key store choice. Only the Mac branch is written; each Windows branch raises "not built yet". A source test bans `osascript`, `ctypes`, `open -R`, `~/Library` and `subprocess` outside it and the runner.
  - **Windows-safe file names on the Mac too:** no `< > : " / \ | ? *`, no `CON`, `NUL` or `COM1` names, no trailing dot or space, and short paths. SharePoint refuses most of the same characters, so this also protects To client today.
  - **Text is always UTF-8,** paths only go through `pathlib`, and programs start from an argument list, never `shell=True`, with a `.cmd` or `.bat` refused.
  - **Files are replaced through one function** (a temporary file, then `os.replace`, with a short retry), because Windows and OneDrive lock open files.
  - **AI keys go through one `KeyStore` interface** (#54). Only the Mac Keychain is built; any other system answers "not connected".
  - **Python 3.9 standard library only,** so the Windows embeddable Python can run the same code later, and `.gitattributes` keeps LF line endings.
- **Save and folder dialogs are the system's own** ("systems own dialog"): on the Mac, `osascript` "choose folder" and "choose file name", inside `platform.py`.
- **Data lives** in `~/Library/Application Support/clark/` (later `%LOCALAPPDATA%\clark\` on Windows), never inside the app folder and never inside OneDrive.
- **CI is on** ("Review test and deployment rules from creaite and match them here... creaite optimised testign and CI"; this lifts the earlier "hold"): every push and pull request runs the suite on Ubuntu with Python 3.9 and the newest Python, and a macOS run is required at the release gate. The rules are the team repo `Projects/clark/testing-and-ci.md` and `release-process.md`; the build is #70. The Windows test machine stays on hold. Details of the platform work are in `docs/handoff/portability-and-sharing.md`.
- **Python 3.9 or later, standard library only**, as creaite. Excel uses the vendored openpyxl and PDF text uses the vendored pypdf, with their licences kept. Nothing is installed from the internet when clark runs. Developers test on 3.9 (the oldest supported) and on the newest Python.
- **The page:** creaite's front-end stack ("ensure we leverage the tech from creaite e.g. preact etc."). Components are Preact 10.29.8 in JSX, page state is @preact/signals 2.11.2, and the one rich editor is Tiptap 3.31.3. All are vendored from creaite v2.6.9 with their MIT licences and SHA-256 manifests. The pinned esbuild 0.28.2 bundles them into one script, in development only, and the built page is committed. It loads nothing from the internet, and fonts and icons are bundled with it. The published page is the same bundle in view-only mode, so the Draft email builder (FR-44, FR-94) is one component in both. Details are in `docs/ARCHITECTURE.md`, "The page: creaite's front-end stack".
- **ask clark** needs Claude or OpenAI connected in Settings › AI (FR-63). Without one, the rest of clark still works and ask clark says it isn't set up.

### Local server and its security
- It listens on 127.0.0.1 only, on a port set in Settings. It is never reachable from another machine.
- A random token is made each time the server starts, and only the page it serves knows it. Every API call must carry it.
- The Host header must be `127.0.0.1` or `localhost`, which blocks DNS-rebinding attacks.
- The page's Content Security Policy allows no outside scripts, styles or connections.
- These rules are copied from creaite's `live_server.py` (guarded) and keep their tests.

### The store
- **One SQLite file per user** (`clark.db`), in the user's data folder, never in the repo. The tables are in `data-model.md`.
- **One writer.** Only `store.py` writes to the database. Every route goes through it: the page, the peek, ask clark, Excel and Word imports, and client changes.
- **The rules sit in the schema** (CHECK constraints and foreign keys), so bad data can't get in by any route. Dates are stored as YYYY-MM-DD and shown as DD-MM-YYYY.
- **A change log** records every change, one row per field: who made it, how, from what, to what, and when. Undo replays it backwards and is a change in its own right. The peek's Activity tab reads the same log.
- **Changes save at once** (Enter or ⌘↵) and Undo sits in the toast, as in creaite's sneak peek. A change that came from text in a source file must be confirmed first, never applied on Enter alone.

### Excel and Word in and out
- **Excel export** writes one workbook with a sheet each for actions, risks and issues, decisions, milestones and use cases. Dates are real Excel dates shown as DD-MM-YYYY.
- **Excel import** compares the workbook with the database and stages the differences. The user accepts or rejects them, and accepted ones go through the one writer. The workbook is never the record. An export refuses to overwrite a workbook that has edits not yet imported.
- **Word:** reports fill the Word templates (`docx_tools.py`). A Word import reads text only, to seed items for the user to accept.
- Imports get the same checks as typed changes. A file that can't be read is reported, never half-applied.

### Publishing
- **One report per project.** There is no separate internal and external version: what the editor chooses to show is what is published.
- **Layout:** Boxed only; spine and cover are in the backlog (#46).
- **The published page** uses the editor's own markup in a view-only mode, in one self-contained HTML file (no server, nothing from the internet). An optional Word version goes alongside it.
- **The page holds only what the editor chose.** Anything left out is dropped before the file is made, never just hidden on the page.
- **Local** is always on. The user picks the folder and name, and clark remembers the folder for each project.
- **To client** (approved by "The brief - yes") has to be ticked each time. clark copies the file into the client's SharePoint folder as synced on this machine by the user's OneDrive app. clark holds no Microsoft sign-in, token or network code. A send never runs by itself, and every send is logged.
- **Client comments** on the published page are a new requirement (28-10-2026; comments only). See `client-edits.md`.

### Draft email
- One builder, a pure function with no page reads, takes the items, the options and the time and returns the To, the Subject, the HTML and the plain text. It is a Preact component, from creaite's `ChasePane.jsx`, and the editor and the published page bundle the same code.
- The HTML is for Outlook's Word engine: inline styles on every element, tables with cellpadding and bottom borders, Calibri or Arial at 11 pt, no classes, variables, images or web fonts. The colours come from one small table, tested at 4.5:1 on white.
- Copying uses `navigator.clipboard.write` with `text/html` and `text/plain`. A page opened from a file or from SharePoint over https is a secure context. If the browser refuses, the preview is selected and the page says "Press ⌘C to copy". It never fails silently.
- Open in mail app uses a `mailto:` link with the plain text only, offered only under about 1,800 characters, because longer links are cut off by some mail apps.
- Reuse: the wording, the rules and the tests come from creaite's Draft email and Draft chase (BL-83, BL-224, BL-298) and are recorded in the reuse record. creaite's `drafts.py` is mostly model drafting and is not copied. None of this is a guarded file.
- Tests run with a fixed clock: the greeting at 09:00, 13:00 and 19:00, the subject, overdue and due-soon marking, inline styles only, internal items unticked for an outside address, no hidden or internal text, and both clipboard types on a stubbed clipboard.

### One output, no client checks
- The owner, 28-10-2026 (D-3): one report, managed by the user. Every work item is client-visible by default and the eye hides it. There is no separate client version, and creaite's `client_leak.py`, `client_output.py` and `client_check.py` are not copied.
- The build still leaves out hidden rows and sections, internal notes and Movement, and a test searches the finished file for each of them (FR-81, FR-82).

### ask clark
- Its purpose is the most accurate report possible, not a general assistant.
- **What it reaches:** the open report's project, which means clark's data for that project plus the source folders listed for it in Settings. It only reads those folders and never writes to them. Paths are resolved first, so a link that points outside a folder is refused.
- **Nothing else:** no mail, Teams, calendar, web or other connectors. Every run is started with them denied by name.
- **Search first:** plain code picks the best passages (creaite's `search.py`), and only those go to the model. Every answer links to its source.
- **Providers (FR-63 to FR-68), from creaite #132:** creaite has built this as `providers.py` (the key store, model lists, direct calls, routing, limits and fake providers for tests) and its AI models page, on branch `v27-132-build`. It isn't in a release yet: its guarded patches to `live_server.py` and `reach.py` are still in review. clark copies only from release tags, so the copy waits for the creaite release that includes #132 (D-8).
- **How each sign-in runs** (checked by a teammate against creaite's `v27-132-build`, 28-10-2026):
  - **Claude subscription:** the Claude command with no tools, as creaite's edit-ai runs at v2.6.9: `--tools "" --strict-mcp-config` and the chosen `--model`, started from an empty folder outside the data folder with creaite's no-context arguments. The run's environment is cleared of `ANTHROPIC_*`, `CLAUDE_CODE_USE_*`, `CLAUDE_CODE_OAUTH_TOKEN` and `CLAUDE_CODE_SIMPLE`, so a key in the user's shell can't quietly move every run to paid API billing (creaite patch 01). `--bare` is never used, because it turns hooks off.
  - **OpenAI API key:** creaite's direct call, one HTTPS request with no tools and no files to `api.openai.com/v1/chat/completions` with `store: false`.
  - **Claude API key:** a direct Messages API call to `api.anthropic.com/v1/messages`. This is **new code**, one more host in the direct caller, not a copy: creaite's own Claude-key route (G8, through the Claude command) isn't built. Because ask clark uses no tools, no Claude command process ever holds the key.
  - **ChatGPT sign-in,** if D-7 allows it: OpenAI's Codex command, signed in with ChatGPT. None of its flags has been checked yet. The spike must prove it runs with no tools and with the chosen model, and that the ChatGPT plan's terms allow it.
- **Every outgoing call** takes no proxy from the environment and follows no redirect. It goes only to a fixed host (`api.openai.com`, `api.anthropic.com`) with TLS verified, and has limits on time and size. IT confirmed for creaite that no proxy is needed (17-10-2026).
- **The keychain** is reached through Apple's Security framework with `ctypes`, never the `security` command, so a key is never on a command line. Each key is stored per user data folder, and checking that a key exists never reads it. **Windows, later:** Credential Manager through `advapi32` (`CredWriteW`, `CredReadW`, `CredDeleteW`) with `ctypes`, not an encrypted key file. Until then, any system other than macOS shows "not connected".
- **Lessons from creaite #132:**
  - Tests never touch the real keychain. `CLARK_FAKE_PROVIDERS=1` switches on fakes (a memory store and a fake model lister, as creaite's `MemoryStore` and `FakeLister`), but only in the development repo or a test's temporary folder, so a stray switch can never fake a real sign-in. Every test key ends in TESTONLY.
  - A run can never read the key store, and no permission rule may name the keychain, the `security` command or the providers code (creaite's `reach.py` patches 03 and 04). In clark no run has tools, so this is a second safeguard on the subscription route, and it's still copied.
  - Provider and limit wording is pinned by tests, so the settings page and the error cards can't drift apart.
- **Without tools, ask clark still gets what it needs:**
  - **More passages:** the reply can ask with a fixed-form `NEED: <query>` line, and clark answers with its own search, at most two rounds, the same on both providers.
  - **Size:** a limit for each provider, from the model's context size, not creaite's 16,000 characters, which is too small to check a whole report. ask clark says when passages were left out.
  - **Citations:** passages carry IDs and the answer cites them; clark checks that every ID exists. A reply that doesn't parse is shown as text, with no change offered.
  - clark itself does the search, reads files (pypdf, `docx_tools`) and checks changes, so nothing in FR-60 to FR-62 needs the model to have tools.
- The readiness note for #54 is a teammate's `docs/handoff/readiness-54-providers.md` (branch `a teammate-handoff`, head 6eea73e).
- **Review:** this touches secrets, so it gets a Full review with two reviewers, the same as a guarded copy, and the owner approves the exact copy.

### Brand layering and the two brand tests
- The committed demo `tokens.css` and demo logo are the default. A user's own `system/branding/tokens.css` and logo are layered on top, if present (that folder is ignored by git). Exports copy in the values in use, so a file is self-contained.
- **Test 1:** fails if anything under `system/branding/` is tracked by git.
- **Test 2:** fails if the local tokens aren't layered over the demo set (the override wins, and the token names match).
- **Test 3**, when a deny list exists: fails if a published sample contains a name from the deny list kept in `system/branding/`. It is skipped when that file is absent, as on a fresh checkout.

### Guarded copies from creaite
- Copied from release tag v2.6.9 (`db5adb2`). Each copy is listed in the reuse record with its path and commit.
- The guarded files clark is likely to copy: `live_server.py` (cut down to clark's routes), `tracker.py` (becomes `store.py`), `reach.py` and `edit_ai.py`. `client_leak.py` is no longer needed (D-3).
- **Review:** each guarded copy gets a Full review with two independent reviewers, never the builder. Until the owner names a second reader, the Head is one of them (`RULES.md`). The owner approves each exact copy in his own words.
- When creaite ships a security fix to one of these files, the Head tells the project lead, and clark takes the fix as a new item.

### Testing
- **CI is on** ("Review test and deployment rules from creaite and match them here... creaite optimised testign and CI"; this lifts the earlier "hold"): every push and pull request runs the suite on Ubuntu with Python 3.9 and the newest Python, and a macOS run is required at the release gate. The rules are the team repo `Projects/clark/testing-and-ci.md` and `release-process.md`; the build is #70.
- **One local runner** (`dev/run_tests.py`) runs Python unit tests, the page's own tests in a headless browser, and the brand tests.
- **Everything that can be a test is a test** (`RULES.md`). A hand check is only for judgement or live-only steps. Visual checks happen at 1400 and 900 px only.
- Tests use the fictional demo data, made by the demo data script, never a copy of real data.

### Performance and size
- **Target size:** up to 20 projects, 5,000 work items and 500 milestones per user.
- **Targets on a normal laptop:** opening a project in under 1 second, a change saved in under 200 ms, an Excel import of 1,000 rows in under 5 seconds, and a published page in under 3 seconds.
- **The published page** stays under 5 MB, pictures included. Pictures are downsized when they are embedded.

### Backup and restore
- **The database never sits in a synced folder.** OneDrive can upload a file part-way through a write, uploads SQLite's `-wal` and `-shm` files separately, has no locks, turns clashes into copies such as `clark-LAPTOP-2.db`, and can leave a file online only. clark refuses a data folder inside OneDrive and says why.
- clark keeps a daily copy of `clark.db`, and one before every import, made with SQLite's own backup command so it is always a clean copy. The copies can go to a OneDrive folder the user picks: each is written under a temporary name, then renamed, so a whole file appears at once. The last 14 are kept.
- Reports, Excel exports, the client folder and the source folders can all sit on OneDrive. If clark's own app files are shared through OneDrive, clark writes no `__pycache__` beside them, and the folder should be set to "Always keep on this device".
- Restore is a menu item that swaps in a chosen copy after confirming. A backup is made of the current database first.
- clark doesn't back up the source folders or the SharePoint folder; they belong to the user.

### Several users, later
- The MVP and the beta have one user per database ("start with single user for mvp/beta"). Several users is a backlog item at low priority ("agreed... this is a backlog item si low priority for now").
- **Decided for later (D-11): option C in the owner's shape** (section 5.10a): teammates export a changes file and the owner imports one or many into the master before publishing. One SharePoint location holds the master's share-only copies and the changes files; clark checks for a newer master on open, and the real database never sits in OneDrive. A changes file rather than a whole database, because the merge needs each field's before value to tell "they changed it" from "we both did", and because a file from someone else is safer to read when it can only hold allowed fields. A small shared service (option A) stays possible later if teams need live shared editing. Not each user's copy merged through OneDrive, which is a lot of hard code. Never a shared `clark.db` on OneDrive.
- Done now so that A and C stay cheap: every write is a step through the one writer, each step records the user and the device, times are UTC, and IDs stay creaite's.

### Risks
1. **Something hidden reaching the client.** With one output and everything visible by default, the eye is the only control. Mitigated by leaving hidden rows, hidden sections and internal notes out at build time, with a test on the finished file.
2. **A real client brand in the repo.** Mitigated by the ignore rule and brand tests 1 and 3.
3. **Text in a source file steering ask clark.** Mitigated by the read-only folders, the mark on any run that has read outside text, and the confirm step for its changes.
4. **Client comments coming back** (new). A file from outside, so it is checked before it is read, and it may only carry comments; see `client-edits.md`.
5. **Guarded copies drifting from creaite's fixes.** Mitigated by recording the tag and the Head's notice of fixes.
6. **Tests skipped before a merge.** Mitigated by CI on every push and pull request, and the macOS run at the release gate (#70).
7. **ask clark depending on a provider sign-in** for other programme managers. It's optional, clark works without it, and a user can pick Claude or OpenAI.
8. **AI keys on a shared or lost laptop.** Mitigated by keeping them in the keychain only (FR-64) and by Disconnect.
9. **Windows readiness drifting** while only the Mac is built. Mitigated by the source tests in NFR-9. Before the Windows port, IT is asked whether company laptops let the embeddable Python and an unsigned `clark.cmd` run.
10. **OneDrive damaging the database.** Mitigated by keeping it off OneDrive (refused in code) and writing only finished backup files there.

## 9. Assumptions and dependencies

- A Mac with Python 3.9 or later, and any modern browser. Windows comes later. A client's direct save into the folder needs Chrome or Edge; download-and-drop works in any browser.
- For ask clark, optional: a Claude subscription with the Claude command, or a Claude or OpenAI API key (or a ChatGPT sign-in if D-7 allows it).
- creaite's AI models work (#132) in a creaite release, for FR-63 to FR-68.
- GitHub Actions for CI (Ubuntu, Python 3.9 and newest), and a Mac for the release gate's macOS run.
- The user's OneDrive app syncs the client's SharePoint folder, for To client and for client changes.
- creaite's release tag v2.6.9 (`db5adb2`) is the source for copies.
- FDE teams join only when the owner says.

## 10. Open decisions (for the owner)

| ID | Decision | Recommendation |
|---|---|---|
| D-1 | How client comments come back (FR-91 to 93) | Comments only (decided, see D-2). The way back is still open: the recommendation is a small comments file the client saves into the shared SharePoint folder, which clark picks up through OneDrive |
| D-2 | What a client may change | **Decided**: nothing. Clients only comment, on work items and on use cases. **Amended**: a client may also **approve or decline a decision marked Needed**, with a note (#117). Nothing else changes |
| D-3 | Client output and team output | **Decided**: "No - a single report output managed by the user / editor. Client visible is toggled on by default for all work items" |
| D-4 | Who reviews guarded copies here | **Decided**: "the Head Reads" |
| D-5 | Who leads clark, and which FDE teams join | **Decided:** the Head leads and is Head ("the Head will. lead and owns HEAD"). Which teams build is the Head's to propose |
| D-6 | Who a client can email from the client page (FR-94) | **On hold**: Draft email is for the editor only for now |
| D-7 | How a user signs in to OpenAI (FR-63) | **Decided**: "ChatGPT sign-in too", as well as an API key. The ChatGPT route through OpenAI's Codex command starts with a spike that proves it runs with no tools, with the chosen model, and within the ChatGPT plan's terms |
| D-8 | Where clark's AI providers code comes from | **Decided**: wait for the creaite release that includes #132, with its guarded patches 01, 03 and 04 |
| D-9 | Whether a project's data may go to OpenAI (FR-68) | **Decided**: Claude and OpenAI are handled the same, with no per-project switch |
| D-10 | Mac and Windows, and testing | **Decided**: Mac first, built ready for Windows ("start with mac we can follow with windows but ensure when we build for mac we make allowances for the future"); the system's own dialogs ("systems own dialog"); CI and the Windows test machine on hold ("hold") |
| D-11 | Several users, later (low priority) | **Decided**: each teammate exports their changes and the owner imports one or many into the master before publish (FR-96 to FR-99d). A shared database on OneDrive is ruled out |
| D-12 | Data model details | **Decided** ("agreed with recommendations"): keep clark's marked additions to creaite's tables; show a risk's priority as red, amber or green, with no separate RAG column. A workstream on milestones, which creaite doesn't have, is kept as an optional field ("keep it, as an optional field") |
| D-13 | Team changes details (FR-96 to FR-99d) | **Later, low priority** ("come back to it"). The recommendations stand for when it's picked up |

## 11. Releases

- **v0.1 First slice:** the 12 items #28 to #39, plus #56 (the platform layer, Mac branch only):
  - the report as wide as the Work items page ("Make Dashboard same width as work items... can we get it into 0.1"), in the page shell (#35) and the published report (#39)
  - demo data, the store, milestone state, the local server, Excel export and import, a read-only work items list, and one HTML report published with the demo brand
  - two guarded copies, #31 (the store, from `tracker.py`) and #33 (the server, from `live_server.py`), each with a design note and two reviewers
  - the three brand tests: nothing tracked under `system/branding/` (#29), the deny list (#29, skipped when absent) and token layering (#35)
- Every v0.1 item's tests pass on macOS, with the Windows-readiness source tests (NFR-9).
- **v0.2:** the report editor (#65 to #67), the peek (#42), milestones with the Calendar and Legend (#44), tiles and use cases with the section styles (#45), To client (#43), (backlogged 28-10-2026: the Health spine and Cover-led layouts) (#46), Back and Forward (#63), and the Work items filters, Add buttons, profile, dark mode and client page look (#64).
- **v0.3:** ask clark and creaite's AI menu on **Claude only, as creaite works today** (#47, #72; "interim Claude-only route in v0.3, as creaite works today"): a Claude subscription through the Claude command, or a Claude API key. Draft email in the editor (#50), Word (#48), and the Work items board and Group by (#68; "68 in v.0.3"), with board full screen (#81), table edits in place (#80) and Publish, Preview and Excel export in the profile menu (#77); and a launcher and clark as a Chrome app ("Let's also ensure we have a launcher plus I want to be able to download as a Chrome App. Put both into 0.3").
- **v0.4:** Help (#82), client page filters (#69), the milestone calendar (#76), Excel export branding (#85), the design-system pass and entries (#87, #88) and the smaller prototype changes.
- **v0.5:** **OpenAI and the ChatGPT sign-in** (#54, FR-63 to FR-68 in full; it waits for the creaite release with #132, D-8), and the README (#93).
- **v0.6: the UX release** ("0.6 is a ux release... load it up with ux improvements we find from now on"). The accepted screen-by-screen UX findings (#132), and every user-experience improvement found from now on.
- **Later:** the Windows port (#57); client comments and the changes inbox (#21, #40, #62); Draft email on the client page (#51, on hold); team changes (#61, on hold, low priority).
- The waves and lanes are in the release plan, approved by the owner on 28-10-2026: the work list on the planning repo #5.

## 12. Acceptance

Each board item carries a Done-when that a test proves. A release ships only when the full suite is green on the exact commit, with the reviews its items require (Team/04).

**Approval and privacy** ("You do not need my eyes to publish." "Keep clark private and alert me before I have to spend money."): clark stays private, always. A private release publishes when its gates are green, without the owner's sign-off. Anything that would cost money goes to the owner first. Guarded copies still need the owner's approval of the exact copy (`RULES.md`).
