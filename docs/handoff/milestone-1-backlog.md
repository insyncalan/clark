# Milestone 1 (first slice): backlog

Written by a teammate, 28-10-2026, for the project lead to put on the planning repo board. The goal is to go from demo data to one published HTML report with the demo brand, proving the store, Excel import, publishing and brand layering. Review tiers follow `Team/04`. **Guarded** marks an item that copies a guarded creaite file: it needs two independent reviewers, never the builder, and the owner's approval of the exact copy.

Teams are teammates. A teammate takes the items first suggested for teammates those suggested for a teammate.

| # | Title | Size | Tier | Team |
|---|---|---|---|---|
| 1 | Repo layout and local test runner | S | Light |  |
| 2 | Brand tests: nothing tracked under system/branding/, deny list | S | Light |  |
| 3 | Demo data script | S | Light |  |
| 4 | Schema and the one writer, with change log and undo (**guarded**) | L | Full |  |
| 5 | Milestone state and slip | S | Light |  |
| 6 | Local server skeleton and its security (**guarded**) | M | Full |  |
| 7 | Vendored libraries and reuse records | S | Light |  |
| 8 | Page shell, the bundle and design token layering | M | Light |  |
| 9 | Work items list (read only) | M | Light |  |
| 10 | Excel export | M | Light |  |
| 11 | Excel import: stage differences, accept or reject | M | Light |  |
| 12 | Publish one HTML report, Local, boxed layout | M | Light |  |

## 1. Repo layout and local test runner
- **Done when:** the repo has `src/clark/`, `tests/` and `dev/run_tests.py`. `python3 dev/run_tests.py` runs every test on Python 3.9 and on the newest Python on macOS, and exits 0 with one sample test. `.gitattributes` keeps line endings as LF, so a later Windows checkout changes nothing. The README says how to run it. No package is installed from the internet.
- **Touches:** new folders, README, `.gitattributes`. **Depends on:** none.

## 2. Brand tests
- **Done when:**
  - Test A fails if `git ls-files system/branding` lists anything (proved by staging a dummy file in a temporary copy).
  - Test B reads `system/branding/deny-list.txt`. It fails if a published sample contains any listed name, and is skipped with a clear message when the file is absent.
  - `.gitignore` covers `system/branding/` and `comms/`.
- **Touches:** `tests/`, `.gitignore`. **Depends on:** 1.

## 3. Demo data script
- **Done when:** `python3 dev/demo_data.py` builds a fresh `clark.db` with two fictional projects (actions, risks, issues, decisions, milestones in every state, and use cases). It gives the same result on every run when `CLARK_NOW` fixes the clock. A test checks that no name outside the script's own fictional list appears in the data.
- **Touches:** `dev/`, `tests/`. **Depends on:** 4.

## 4. Schema and the one writer (guarded: from creaite `tracker.py`, `schema.sql`, `item_history.py`)
- **Done when:**
  - `schema.sql` follows `docs/handoff/data-model.md`.
  - `store.py` is the only module that writes. A test fails if any other module opens the database for writing.
  - Tests prove each CHECK refuses bad data.
  - A change writes one `applies` row plus one `change_log` and one `item_events` row per field, as in creaite.
  - Undo restores the before values and links both steps.
  - Undo is refused when a later step changed the same field.
  - The history of one row reads back newest first.
- **Touches:** `src/clark/store.py`, `schema.sql`. **Depends on:** 1.

## 5. Milestone state and slip
- **Done when:** copies of creaite's `suggested_state`, `milestone_state` and `MS_CLIENT_WORD` (v2.6.9) return each state by the rules in `data-model.md`. Those are creaite's five states plus Forecast, with Overdue worked out from the agreed date. There's one test per state, and the order between them is tested, including a user-set state with its reason. Slip in days is tested, including no forecast. The original date is read from `change_log`.
- **Touches:** `src/clark/milestones.py`. **Depends on:** 4.

## 6. Local server skeleton and its security (guarded: from creaite `live_server.py`)
- **Done when:**
  - The server binds to 127.0.0.1 only.
  - A request with a wrong Host header gets 403, and an API call without the run's token gets 403.
  - The page is served with a Content Security Policy that allows no outside source.
  - `GET /` serves the page and `GET /api/data` returns one project's data.
  - Each rule has a test.
  - Only the routes clark needs are copied, and each is listed in the reuse record.
- **Touches:** `src/clark/server.py`. **Depends on:** 4, 7.

## 7. Vendored libraries and reuse records
- **Done when:**
  - openpyxl and its dependency et_xmlfile are in place with their licences and versions in `vendor/manifest.json`.
  - creaite's front-end libraries are copied from v2.6.9 unchanged, each folder with its own `manifest.json`: Preact 10.29.8 with hooks and the JSX runtime, @preact/signals 2.11.2 and signals-core 1.14.4 (`system/templates/vendor/preact/`), and Tiptap 3.31.3 (`system/templates/vendor/tiptap/`, with every licence file).
  - The pinned esbuild 0.28.2 is fetched by a copy of creaite's `dev/tools/esbuild.py`, which checks the binary's SHA-256 and needs no Node or npm.
  - Copies of `test_vendor_preact.py` and `test_vendor_tiptap.py` pass: every vendored file matches its manifest hash.
  - Every file copied from creaite in this milestone has a row in the reuse record with its path and tag v2.6.9 (`db5adb2`).
- **Touches:** `vendor/`, `dev/tools/`, the reuse record. **Depends on:** 1.

## 8. Page shell, the bundle and design token layering
- **Done when:**
  - One build command bundles the page code into one file with the pinned esbuild. It is a copy of creaite's `build_dashboard_js.py` and `split_dashboard.py`, cut down, with `preact_flags()`: JSX through Preact's automatic runtime, and every library name mapped to its vendored file.
  - The page code is Preact components in JSX, with page state in signals stores, as in creaite's `system/templates/dashboard/src/`. A test fails if the bundle imports anything outside `src/` and the vendored folders.
  - The build is repeatable: the same sources give the same bytes (from creaite's `test_dashboard_split.py`). The built page is committed, and nothing is built when clark runs.
  - The page loads the committed demo `tokens.css`, then `system/branding/tokens.css` on top if present.
  - Test C (brand layering): with a test override that sets one token, the page uses the override's value. Without it, the page uses the demo value, and both files have the same token names.
- **Touches:** `src/clark/page/`, `src/clark/brand/`. **Depends on:** 6.

## 9. Work items list (read only)
- **Done when:** the Work items view lists one project's actions, risks, issues and decisions from `/api/data`, with type, owner, due date in words, status and priority, as in the prototype's screens. A browser test at 1400 and 900 px finds every demo row. No editing yet.
- **Touches:** `src/clark/page/`. **Depends on:** 3, 8.

## 10. Excel export
- **Done when:** the export writes a workbook with sheets for actions, risks and issues, decisions, milestones and use cases. Dates are real Excel dates shown as DD-MM-YYYY. Opening the file back gives the same values as the database. The export refuses to overwrite a workbook that has edits not yet imported.
- **Touches:** `src/clark/excel.py`. **Depends on:** 4, 7.

## 11. Excel import: stage differences, accept or reject
- **Done when:** an import compares the workbook with the database by id. It lists new, changed and removed rows as staged changes and applies only the accepted ones, through the one writer, as one step with Undo. A row that breaks a rule is reported and never half-applied. Tests cover each case.
- **Touches:** `src/clark/excel.py`, `store.py` (calls only). **Depends on:** 10.

## 12. Publish one HTML report, Local, boxed layout
- **Done when:**
  - Publish writes one self-contained HTML file for a project in the boxed layout, with the demo brand's values copied in.
  - A test fails if the file refers to any outside address (script, style, font or image).
  - Rows in `report_hidden` are absent from the file's text.
  - The publish is logged in `publications` with the file's SHA-256.
  - The file opens in a browser with no server.
- **Touches:** `src/clark/publish.py`, the page's view-only mode. **Depends on:** 5, 8, 9.

## Not in milestone 1
Editing in the peek, ask clark, Word, To client, client comments, the spine and cover layouts, backup and restore.
