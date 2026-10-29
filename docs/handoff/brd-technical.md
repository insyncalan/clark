# Technical considerations (for docs/BRD.md)

Written by a teammate (technical architect), 28-10-2026, for the BRD. It reads with `docs/ARCHITECTURE.md`. Fictional names only.

## Platform and runtime
- **Mac first, built ready for Windows** ("start with mac we can follow with windows but ensure when we build for mac we make allowances for the future"). Everything that differs by system sits in `platform.py`, with only the Mac branch built. Windows-safe file names, UTF-8 everywhere, `pathlib` paths, argument lists, one file-replace function and one `KeyStore` interface are all pinned by tests on the Mac. Save and folder dialogs are the system's own. The Windows port (the embeddable Python package, Credential Manager, Windows tests) comes later. Details are in `docs/handoff/portability-and-sharing.md`.
- **The database stays on the machine's own disk,** never in a OneDrive folder. Backups, reports, exports and the client folder may be on OneDrive. One user per database in the MVP and the beta. Several users come later, and the options are in the same note.
- **Python 3.9 or later, standard library only**, as creaite. Excel uses the vendored openpyxl and PDF text uses the vendored pypdf, with their licences kept. Nothing is installed from the internet when clark runs. Developers test on 3.9 (the oldest supported) and on the newest Python.
- **The page:** creaite's front-end stack ("ensure we leverage the tech from creaite e.g. preact etc."). Components are Preact 10.29.8 in JSX, page state is @preact/signals 2.11.2, and the one rich editor is Tiptap 3.31.3. All are vendored from creaite v2.6.9 with their MIT licences and SHA-256 manifests. The pinned esbuild 0.28.2 bundles them into one script, in development only, and the built page is committed. It loads nothing from the internet, and fonts and icons are bundled with it. The published page is the same bundle in view-only mode. Details are in `docs/ARCHITECTURE.md`, "The page: creaite's front-end stack".
- **ask clark** needs the Claude command installed and signed in on the user's machine. Without it, the rest of clark still works and ask clark says it isn't set up.

## Local server and its security
- It listens on 127.0.0.1 only, on a port set in Settings. It is never reachable from another machine.
- A random token is made each time the server starts, and only the page it serves knows it. Every API call must carry it.
- The Host header must be `127.0.0.1` or `localhost`, which blocks DNS-rebinding attacks.
- The page's Content Security Policy allows no outside scripts, styles or connections.
- These rules are copied from creaite's `live_server.py` (guarded) and keep their tests.

## The store
- **One SQLite file per user** (`clark.db`), in the user's data folder, never in the repo. The tables are in `data-model.md`.
- **One writer.** Only `store.py` writes to the database. Every route goes through it: the page, the peek, ask clark, Excel and Word imports, and client changes.
- **The rules sit in the schema** (CHECK constraints and foreign keys), so bad data can't get in by any route. Dates are stored as YYYY-MM-DD and shown as DD-MM-YYYY.
- **A change log** records every change, one row per field: who made it, how, from what, to what, and when. Undo replays it backwards and is a change in its own right. The peek's Activity tab reads the same log.
- **Changes save at once** (Enter or ⌘↵) and Undo sits in the toast, as in creaite's sneak peek. A change that came from text in a source file must be confirmed first, never applied on Enter alone.

## Excel and Word in and out
- **Excel export** writes one workbook with a sheet each for actions, risks and issues, decisions, milestones and use cases. Dates are real Excel dates shown as DD-MM-YYYY.
- **Excel import** compares the workbook with the database and stages the differences. The user accepts or rejects them, and accepted ones go through the one writer. The workbook is never the record. An export refuses to overwrite a workbook that has edits not yet imported.
- **Word:** reports fill the Word templates (`docx_tools.py`). A Word import reads text only, to seed items for the user to accept.
- Imports get the same checks as typed changes. A file that can't be read is reported, never half-applied.

## Publishing
- **One report per project.** There is no separate internal and external version: what the editor chooses to show is what is published.
- **Layouts:** boxed (the standard), spine and cover. The choice is made per project in Settings.
- **The published page** uses the editor's own markup in a view-only mode, in one self-contained HTML file (no server, nothing from the internet). An optional Word version goes alongside it.
- **The page holds only what the editor chose.** Anything left out is dropped before the file is made, never just hidden on the page.
- **Local** is always on. The user picks the folder and name, and clark remembers the folder for each project.
- **To client** (approved by "The brief - yes") has to be ticked each time. clark copies the file into the client's SharePoint folder as synced on this machine by the user's OneDrive app. clark holds no Microsoft sign-in, token or network code. A send never runs by itself, and every send is logged.
- **One output** (the owner, 28-10-2026, #24): "a single report output managed by the user / editor. Client visible is toggled on by default for all work items". There is no separate client version of the report.
- **Client comments** on the published page (the owner, #21 and #22): clients add comments to work items and use cases and change nothing. How the comments come back is open (D-1); see `client-edits.md`.

## What goes into the published file
- The build takes only rows with the client flag on (the default) that aren't hidden, and never a Sensitive row or an internal note. Everything else is left out of the file, never just hidden on the page.
- creaite's client checks (`client_leak.py`, `client_output.py`, `client_check.py`) aren't copied, because there is one output (#24). The build's own tests plant a hidden row, a row with the flag off, a Sensitive row and an internal note, and check each is absent from the file.

## ask clark
- Its purpose is the most accurate report possible, not a general assistant.
- **What it reaches:** the open report's project, which means clark's data for that project plus the source folders listed for it in Settings. It only reads those folders and never writes to them. Paths are resolved first, so a link that points outside a folder is refused.
- **Nothing else:** no mail, Teams, calendar, web or other connectors. Every run is started with them denied by name.
- **Search first:** plain code picks the best passages (creaite's `search.py`), and only those go to the provider. Every answer links to its source.
- **Providers:** Claude or OpenAI, whichever the user connects, handled the same ("Both openai and claude handled the same.. no differnetiation."). No per-project switch. Claude by subscription or API key; OpenAI by API key, and ChatGPT sign-in too after a spike proves the route (#52). The code is copied from the creaite release that includes #132 (#53: "wait fo release"). See `readiness-54-providers.md`.

## Brand layering and the two brand tests
- The committed demo `tokens.css` and demo logo are the default. A user's own `system/branding/tokens.css` and logo are layered on top, if present (that folder is ignored by git). Exports copy in the values in use, so a file is self-contained.
- **Test 1:** fails if anything under `system/branding/` is tracked by git.
- **Test 2:** fails if the local tokens aren't layered over the demo set (the override wins, and the token names match).
- **Test 3**, when a deny list exists: fails if a published sample contains a name from the deny list kept in `system/branding/`. It is skipped when that file is absent, as on a fresh checkout.

## Guarded copies from creaite
- Copied from release tag v2.6.9 (`db5adb2`). Each copy is listed in the reuse record with its path and commit.
- The guarded files clark is likely to copy: `live_server.py` (cut down to clark's routes), `tracker.py` (becomes `store.py`), `reach.py` and `edit_ai.py`. `client_leak.py` is no longer copied (#24).
- **Review:** each guarded copy gets a Full review with two independent reviewers, never the builder. The Head, who is Head and leads clark (#26), is one of them ("the Head Reads", #25). The owner approves each exact copy in his own words.
- When creaite ships a security fix to one of these files, the Head tells the project lead, and clark takes the fix as a new item.

## Testing
- **There is no CI yet.** GitHub Actions won't start on the account because of its billing or spending limit (since 25-10-2026). Until the owner fixes that, the full suite runs locally before every push, and the pull request records the result and the commit.
- **One local runner** (`dev/run_tests.py`) runs Python unit tests, the page's own tests in a headless browser, and the brand tests.
- **Everything that can be a test is a test** (`RULES.md`). A hand check is only for judgement or live-only steps. Visual checks happen at 1400 and 900 px only.
- Tests use the fictional demo data, made by the demo data script, never a copy of real data.

## Performance and size
- **Target size:** up to 20 projects, 5,000 work items and 500 milestones per user.
- **Targets on a normal laptop:** opening a project in under 1 second, a change saved in under 200 ms, an Excel import of 1,000 rows in under 5 seconds, and a published page in under 3 seconds.
- **The published page** stays under 5 MB, pictures included. Pictures are downsized when they are embedded.

## Backup and restore
- clark keeps a daily copy of `clark.db` in its data folder, made with SQLite's own backup command so it is always a clean copy. The last 14 are kept.
- Restore is a menu item that swaps in a chosen copy after confirming. A backup is made of the current database first.
- clark doesn't back up the source folders or the SharePoint folder; they belong to the user.

## Risks
1. **Team-only data in the published file.** Mitigated by leaving rows out at build time, with the flag, hiding and the Sensitive label, and by the build's absence tests. The editor manages the one output (#24).
2. **A real client brand in the repo.** Mitigated by the ignore rule and brand tests 1 and 3.
3. **Text in a source file steering ask clark.** Mitigated by the read-only folders, the mark on any run that has read outside text, and the confirm step for its changes.
4. **Client comments coming back** (new). This needs integrity checks, a comments-only rule and PM acceptance; see `client-edits.md`.
5. **Guarded copies drifting from creaite's fixes.** Mitigated by recording the tag and the Head's notice of fixes.
6. **No CI.** A local suite is easy to skip. Mitigated by the pull request recording the run, until the owner fixes the billing limit.
7. **ask clark depending on the Claude command** being installed for other programme managers. It's optional, and clark works without it.
