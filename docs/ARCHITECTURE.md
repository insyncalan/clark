# How clark is built

Proposal by a teammate (technical architect), 27-10-2026. For the project lead (product lead) to review, then the owner. Nothing here is decided until the owner says so; open points are listed at the end. No code is written yet.

## In five lines

1. clark is one app that runs on the user's own computer. It is a small local server and a page in the browser, and it is reused from creaite's live server.
2. Work items, milestones and use cases live in one SQLite database file per user. One module writes to it, it checks every change, and it keeps the history that undo needs.
3. Excel and Word are ways in and out, never the record. An import is shown as changes the user accepts.
4. A report is one self-contained HTML file with its data inside, the same as creaite's documents. Word, HTML and the dashboard are all made from that data.
5. The look comes from a design tokens file. The repo carries a fictional demo brand, and a real client brand is a local override that never leaves the machine.

## The parts

| Part | What it does | From creaite (v2.6.9, `db5adb2`) |
|---|---|---|
| **Local server** | Serves the page on 127.0.0.1 only. Each run gets a random token that only its own page has. Runs saves, imports and publishing | `live_server.py` (guarded), `report_server.py`. Copy only the routes clark needs: about 10% of creaite's 9,400 lines |
| **Store** | `clark.db` (SQLite). The schema's own checks hold the rules, so bad data can't get in by any route. A change log gives undo and an item's history | `schema.sql`, `tracker.py` (guarded), `item_history.py`. creaite's work item, milestone, workstream and history tables are kept as they are, with a few marked clark columns, plus clark's own tables (`docs/handoff/data-model.md`; "ensure that the work item and milestone schemas reflect those of creaite") |
| **The page** | Every screen, the editor and the published page, built as one bundle from creaite's front-end stack (see "The page: creaite's front-end stack" below) | Preact and signals, Tiptap, the pinned esbuild and the dashboard's components (`system/templates/dashboard/src/`) |
| **Work items view** | The list plus the peek panel to view and change one item, and its Activity tab | The dashboard's `Peek.jsx`, `Toast.jsx`, `core/instant.js`, `sneak.js`, and `sneak_peek.py` on the server |
| **Milestones** | Plan, list, and the state worked out from the dates (Forecast, On track, At risk, Slipped, Overdue, Achieved). Imported and exported on their own Excel sheet. Suggest milestones was removed ("remove suggested milestones") | `tracker.py` milestone rules and state, `forecast.py` |
| **Use case summary** | A report section with its own table: reference, title, status (On track, Flag, High risk), headline and standing, plus the work items linked to each use case | New in clark. The data model is in `docs/handoff/data-model.md` |
| **Excel in and out** | Export a workbook with a sheet each for actions, risks and issues, decisions, milestones and use cases. Importing it stages the differences for the user to accept | `excel_sync.py`, with the vendored openpyxl (licence kept) |
| **Word in and out** | Fill the report templates. Read a Word file's text for an import | `docx_tools.py`, the Word templates (`weekly-report`, `client-report`) |
| **Reports and publishing** | **One report per project,** with no separate internal and external version: what the editor chooses to show is what is published. Layouts: boxed (the standard), spine and cover. The published page is the editor's own markup in a view-only mode, in one self-contained file that loads nothing from the internet. Word is optional, alongside it | `creaite_doc.py`, `report_doc.py`, `export_page.py`, `build_dashboard.py` |
| **Client output checks** | Make sure nothing team-only reaches a client file | `client_leak.py` (guarded), `client_output.py`, `client_check.py`. See open point 2 |
| **ask clark** | The built-in assistant: works on clark's own data and searches the user's source folders (see "ask clark" below) | `edit_ai.py` (guarded), `search.py` (the index and "what to read first"), `reach.py` (guarded, cut down to clark's folders) |

Left out on purpose: mail, Teams, calendars, transcripts, the sweep, minutes, the VIP check, the update and backup engines (these come later if clark needs them), and anything from creaite's private repos.

Each copy is listed in the reuse record before it's used, and is taken from the release tag. Copies of guarded files get a second reader (`RULES.md`).

## The page: creaite's front-end stack ("ensure we leverage the tech from creaite e.g. preact etc.")

clark's page is built the way creaite's dashboard is, from the same pinned libraries and tools. It is not plain JavaScript and it doesn't use a new framework. Everything below is at v2.6.9 (`db5adb2`), is MIT-licensed, and is vendored with its licence and a manifest of SHA-256 hashes.

| Piece | What clark uses it for | From creaite v2.6.9 |
|---|---|---|
| **Preact 10.29.8**, with its hooks and JSX runtime | Every screen is a Preact component, written in JSX | `system/templates/vendor/preact/preact/` and `manifest.json` |
| **@preact/signals 2.11.2** and **signals-core 1.14.4** | Page state: a store module for each area (work items, milestones, report, settings), as in creaite's `src/stores/` | `system/templates/vendor/preact/signals*/` |
| **Tiptap 3.31.3**, one minified ES module with ProseMirror and creaite's Markdown writer | The one rich editor: toolbar, bubble and the `/` menu. This was already the owner's call (27-10-2026: "editor is full rich editor tiptap, like creaite") | `system/templates/vendor/tiptap/`, built from `dev/tiptap/` by `dev/tools/tiptap.py` |
| **esbuild 0.28.2**, the native binary only | Bundles `src/main.js` and its imports into one script, with JSX through Preact's automatic runtime. Each library name is mapped to its vendored file, so nothing is looked up anywhere else | `dev/tools/esbuild.py` (downloads the binary and checks its SHA-256; no Node or npm), `dev/tools/build_dashboard_js.py` (`preact_flags()`), `dev/tools/split_dashboard.py` |
| **The components** | Peek, Toast with Undo, slash menu, editor bar, menus, combobox, dialog, tabs, item picker, status dot, chip | `system/templates/dashboard/src/components/` (`Peek.jsx` and `peek/`: `PeekProps.jsx`, `SneakPeek.jsx`, `ChasePane.jsx`; `Toast.jsx`, `SlashMenu.jsx`, `EditorBar.jsx`, `TextEditor.jsx`, `Menu.jsx`, `Combobox.jsx`, `Dialog.jsx`, `Tabs.jsx`, `ItemPicker.jsx`, `StatusDot.jsx`, `Chip.jsx`) |
| **The core modules** | One editor wrapper, instant save, undo steps, key handling | `src/core/editor.js`, `instant.js`, `undoSteps.js`, `keys.js` |
| **The checks** | The vendored files match their manifests, every rich field uses the one editor, and the bundle builds the same bytes from the same sources | `dev/tests/test_vendor_preact.py`, `test_vendor_tiptap.py`, `test_one_editor_gate.py`, `test_dashboard_split.py` |

The rules:
- **The tools are for development only.** The built page is committed, and nothing is downloaded, installed or built when clark runs. This is creaite's NFR-12, and clark keeps it.
- **One bundle, two modes.** The published page is the same component tree with a view-only flag (see "The published page is interactive" below). The publish build drops whatever the editor left out before the file is made.
- **Copied, then cut down.** Components are copied from the tag and stripped of creaite-only parts (mail, meetings, the vault). Names change from `creaite` to `clark`; for example `creaiteEditor()` becomes `clarkEditor()`. Each file has a row in the reuse record. None of these files is guarded.
- **Upgrades** go through creaite's own scripts with new pins (`fetch_preact.sh` and `vendor_preact.py`; `tiptap.py fetch` and `vendor`). A new version must be at least two weeks old (`Team/03`).
- **Type checking** (`dev/tools/typecheck.py`, TypeScript's checkJs) needs Node, so it is optional on a developer's machine and not a gate.
- **The prototype** stays the reference for screens and behaviour. Its classic-script Tiptap copy is not carried into the real build.

## How data moves

```
Excel / Word ──import──▶ staged changes ──user accepts──▶ clark.db (one writer, change log)
                                                              │
                     work items view, peek, milestones ◀──────┤
                                                              ▼
                                   report document (HTML page with its data inside)
                                        │                │                │
                                     Word file       HTML file       dashboard page
                                  (team or client: client output is checked first)
```

Nothing is deleted. A project, work item, milestone, use case or document is archived instead: it is hidden from the views, the counts and the published page, keeps its history, and Restore brings it back (the owner, 28-10-2026; BRD FR-43c). The one writer has Archive and Restore beside Update, ask clark and the Excel import use them, and each is one step with one Undo. Report sections are the exception: a section is the user's own layout and text, so it can still be deleted, with an Undo toast.

Everything stays on the user's machine unless the user ticks "To client" when publishing (below).

## Publishing: Local and To client (the owner, 27-10-2026; approved 28-10-2026: "The brief - yes")

Publish offers two places:
- **Local**, always on: the files are written on the user's machine.
- **To client**, a tick box: the client version is also put in the client's SharePoint folder. That folder is set per project in Settings.

The rules:
- Sending to SharePoint is an outward action. It needs the user's tick every time and never runs by itself, on a schedule, from ask clark, or from an import.
- Only the client version is ever sent, and only after the client checks pass on the finished file. If a check fails, nothing is sent.
- Every send is logged: what was sent, where, when and by whom.
- **How it sends:** clark copies the file into the SharePoint folder that the user's OneDrive app already syncs to the machine. clark holds no Microsoft sign-in, token or network code, and the user's own sync does the upload. This is in the brief the owner approved on 28-10-2026.

## ask clark

The owner's words: "ask clark should work directly on the data available with the reporting structure but also we should be able (in settings) to identify multiple 'source' project folders that ask creaite can and will search for any answers you have. Only information in the folders saved - no emails / teams / calendar etc (for now)".

And: "ask clark's purpose is to help the user create the most accurate report possible... not boil the ocean".

So ask clark is a report checker and helper, not a general assistant. It works on the report in hand and that report's project. It answers questions about them, checks the report's facts against clark's data and the project's source files, points out what is missing, out of date or in conflict, and suggests corrections with the source for each one. It doesn't search everything, make up content, or work outside the report.

How that is built:
- **Scope:** a run covers one report's project. That means its data and the source folders listed for that project, not every folder in Settings.
- **clark's data:** ask clark reads work items, milestones and reports. Any change it makes saves at once, as in creaite's sneak peek, through the store's one writer. It is logged and can be undone from the toast.
- **Source folders:** Settings holds a list of folders the user picks, each tied to a project (one or several per project). ask clark searches only inside them and reads what is saved there: Word, Excel, PDF, text and Markdown files. Paths are resolved first, so a link or `..` that points outside a listed folder is refused. It never writes, moves or deletes anything in a source folder.
- **Search first, then Claude:** plain code finds the best passages from an index of the source folders and clark's data (creaite's `search.py`), and only those passages go to Claude. Every answer links to the file it came from.
- **Nothing else:** no mail, Teams, calendar, web or other connectors. Each run is started with those denied by name, as creaite does.
- **Outside text is not instructions:** a run that has read a source file is marked. A marked run can still propose a change to clark's data, but the user must accept it first. A change that comes from text in a source file keeps a confirm step and never applies on Enter alone (agreed with the project lead, 27-10-2026).
- **Client output:** text found in a source folder never goes into a client report by itself. It reaches one only as an item the user has marked as client-visible.

## The published page is interactive (the owner, 27-10-2026; built this way in the prototype)

The owner's words: "the published user page should be hyper interactive - just like the clark editor.... only difference is that the client user cannot edit the data nor can they selct which data is shown etc. So e.g. the peek on actions should work but it's uneditable - view only, milestones etc. all view only... client user should be able to navigate in a view similar to editor ut read only based on what the editor decides."

What this means for the architecture, so nothing built now blocks it:
- The published page uses the editor's own page code in a view-only mode, in one self-contained file. It needs no server and nothing from the internet.
- **The page holds only what the editor chose to publish.** Anything left out is dropped before the file is made, not hidden on the page, because a reader can open a file and see everything in it. The client checks run on the file's contents.
- There is one report per project, so there is one selection, the editor's.
- **Changed 28-10-2026:** the owner now wants clients to edit work items and comment on use cases on the published page. The options and a recommendation are in `docs/handoff/client-edits.md`, for his decision.

## Where files live (proposal)

- `src/`: clark's code. `tests/`: its tests. Demo data comes from a script, never a copy of real data.
- **User data lives outside the repo.** `clark.db` is in the system's app data folder on the machine's own disk (`~/Library/Application Support/clark`, `%LOCALAPPDATA%\clark`), never in a OneDrive folder. Reports, exports and daily backups may go to OneDrive. Nothing a user makes is committed. See `docs/handoff/portability-and-sharing.md`.
- `src/.../brand/tokens.css` and the demo logo: the fictional demo brand, committed. This is the default look.
- `system/branding/` (git ignores it): a user's own brand. If present, its `tokens.css` and logo are layered over the demo set. This applies to the app, the dashboard and the Word templates' colours. The token names are the same in both, so a brand is a file swap, not a code change.
- A test fails if anything under `system/branding/` is ever tracked.
- A second test fails if a published sample contains a name from a deny list. The deny list holds the client's name, so it lives in `system/branding/` too (ignored by git). When the file is absent, as on a fresh checkout, the test is skipped, not failed.

## Design tokens (the project lead's ask)

The design system's token names become the contract. The page reads `--brand-*`, `--grey-*`, `--status-*` and the other token names in the committed demo `tokens.css` from the committed demo `tokens.css`. At start-up, the server adds the local override if one exists. Exports copy the resolved values into the file, so a published HTML or Word file is self-contained and shows the brand that was active when it was made. The editor prototype is the reference for screens and behaviour, not for code.

## First slice (accepted by the project lead as the basis for milestone 1; she shapes it after the owner has read this note)

Demo data, then the store, then Excel import, then a read-only work items list, then one HTML report published with the demo brand. The two brand tests come with it from day one: nothing under `system/branding/` is tracked, and the local tokens are layered over the demo set. It is small and testable from end to end, and it proves the store, import, publishing and the token layering before any guarded copy (client checks, ask clark) is needed.

## Open (the owner's call; flagged, not decided)

1. **What ask clark may reach: decided** (the owner, 27-10-2026; see "ask clark" above). **How it makes changes: decided** ("see how we did sneak peek in creaite and emulate experience - shift enter immediate save, toast with undo etc. all UX from ask creaite and sneak peek on ask creaite to be replicated"). Changes save at once through the store's one writer, and a toast offers Undo. The design detail is the project lead's. This needs creaite's instant save and undo path (`core/instant.js`, `/api/undo`, `sneak.js`, `sneak_peek.py`) in the reuse list. Each user needs the Claude command installed.
2. **How client output is kept apart from team output.** (a) A "client can see" flag on each item, plus creaite's checks on both the data and the finished file before any client export. (b) A separate client build that reads only client-safe rows. *My recommendation:* (a), because it's proven in creaite, but it means copying creaite's three client checks, one of them guarded (`client_leak.py`). The owner's "one report per project" (28-10-2026) fits (a): the editor's selection decides what is in the file, and the checks run before To client.
3. **Which computers clark runs on: decided 28-10-2026.** "start with mac we can follow with windows but ensure when we build for mac we make allowances for the future". The MVP is Mac only. Everything system-specific sits in one `platform.py` (Mac branch only), with Windows-safe file names, UTF-8, `pathlib`, argument lists, one file-replace function and one `KeyStore` interface, all pinned by tests. Dialogs are the system's own ("systems own dialog"). Windows CI and test machines are on hold. Several users is a low-priority backlog item (team changes files, `docs/handoff/team-changes.md`), and the database is never in OneDrive. See `docs/handoff/portability-and-sharing.md`.
4. **The data model**: in `docs/handoff/data-model.md`, following creaite's `schema.sql` at v2.6.9. clark's marked columns are kept and RAG on risks is shown from priority ("agreed with recommendations"). A workstream on milestones is still open.
5. **Client edits on the published page** (new, 28-10-2026): see `docs/handoff/client-edits.md`.

## Risks, security first

- **A client brand leaking into the repo:** the ignore rule, the tracked-file test and the deny-list test above.
- **Client data leaking into a client report:** open point 2. Whichever way is chosen, it's tested on demo data before any real use.
- **The local server:** 127.0.0.1 only, the per-run token and the Host check stay as they are in creaite. No public address, ever.
- **Guarded copies drift from creaite's fixes:** each copy records its tag. The Head tells the project lead when creaite ships a security fix to one of them.
- **No CI yet:** GitHub Actions won't start on this account (the billing limit, 25-10-2026). Tests run locally until the owner fixes that.
