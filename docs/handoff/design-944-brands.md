# Design note: #944 brands, a library of client looks chosen per project (release 1.0.5; guarded: store, schema, migrations, changes, history, publish, publish_flow, server, excel*, docx_build)

Written 07-11-2026. READY FOR READ (design). Review of this note and of every build that follows it: Full (two critical
readers, never the builder): the guarded-code reader first, the project lead second. Nothing in this note is built. Line numbers
are `origin/main` at `91c92da25`. Facts come only from the rows of the five fact tables that a second reader confirmed; a row
marked NOT CONFIRMED there is not used here, or is named as unchecked. Main is frozen, so this is a document only: no code, no
test and no string changes.

## Plain words, for the owner

Today clark has one brand: whatever sits in `system/branding` is the look of every project, in the editor, the published page and
the Excel workbook. After this row clark keeps a **library** of brands, each in its own folder `system/branding/<id>/`, brought in
from a zip with a plain review first, and replaced, removed or put back with Undo. Each **project** chooses Generic (the committed
look) or one installed brand. That project's editor, published page, Excel workbook, client workbook and Word colours use that
brand and no other. The brand's id and name never appear in anything a client receives; only its look does. The Word template and
the PDF are not in 1.0.5: they go to 1.0.6 (section 3, T4).

## 1. Scope and decisions

The 49 open questions from the five fact topics were deduped to 18 (on the board, 07-11 12:25). The owner answered them
(through the project lead, 07-11 15:0x). Each is restated as a decision. DEFAULT means the recommended default stands;
CHANGED means the owner changed it.

**Two points the finders disagreed on:**
- **A. Generic on the Excel Cover: DECIDED, clark's icon.** Generic shows **clark's own icon** (today's "no branding folder" case,
  `excel_picture.py:34` `OWN_LOGO`, `branding_base` `:110-114`, `load` `:172-180`). **`None` cannot carry this:** `branding_base(None)`
  falls back to `page.BRANDING` (the `system/branding` folder), which exists as soon as any brand is installed, so `load` takes the
  folder branch and `local_logo` finds no logo: Generic would get NO logo. The design therefore needs a DISTINCT signal: a module
  constant `brands.GENERIC` (a sentinel, not `None`, not a path) which `brands.folder` returns for Generic, and an explicit branch at
  the top of `excel_picture.load` (and the same in `excel_palette.palette`, which has the same None-means-default fallback) that
  answers clark's icon / the committed palette for `GENERIC`. An existing folder with no logo gives no logo, and an installed
  brand with no logo file gives no logo, as today. The T4 test for decision A MUST run with `system/branding` present AND another
  brand installed (the case where `None` would silently give no logo).
- **B. The editor follows the open project's brand: CHANGED, yes.** One brand block in the page at any time, swapped when the open
  project changes. This needs a `server.py` change (guarded): T3.

**Storage and data**
1. **DEFAULT.** `projects.brand TEXT NOT NULL DEFAULT 'generic' CHECK (length(brand) BETWEEN 1 AND 60)`, data layout step 20, no
   foreign key. The legacy single folder (a `tokens.css` at the top of `system/branding`) is the brand with id `local-brand`.
2. **DEFAULT.** The column is not checked against the disk. The change route checks the id is `generic` or installed; every reader
   falls back to Generic with a note when the folder is gone.
3. **DEFAULT, made exact by the owner.** The id is **GATES-only**: never in `PUBLISH_FIELDS` (`publish.py:80-81`), so no published
   file carries it. The published page **is** shown in the client's brand: the page carries the brand's look, never the id.
4. **DEFAULT.** Step 20 means a 1.0.4 build refuses 1.0.5 data. `test_update_17_to_18.py:38` `NEW_LAYOUT` moves to 20;
   `test_v060.py:407` pins `SCHEMA_VERSION = 20`; a 1.0.5 notes test, if one is written, skips when the layout is higher, as
   `test_v104.py` does.
5. **DEFAULT.** A brand change is in the project's history with its own plain label and its own undo phrase (not folded into the
   Gantt phrase).

**Library, ids, remove**
6. **DEFAULT.** Id: lowercase letters, digits and hyphen, 1 to 40 characters. Reserved: `assets`, `design-system`, `generic`,
   `local-brand` (the first two are the legacy folder's own sub-folders, `page/__init__.py:52-55`, `excel_picture.py:32-33`).
7. **DEFAULT.** Replace = swap the whole `<id>/` folder by two renames. The review's "removed" list is the old folder's files that
   the zip lacks.
8. **DEFAULT.** Remove leaves the project column as it is; readers fall back to Generic. Undo of a Remove restores every project's
   brand with no data change. Undo of an install does not touch any project. Remove follows the spec's two clicks (a Remove button, then a plain confirm; decided, replacing "asks once"); Undo is one click.
9. **DEFAULT.** A crash between the two renames leaves folders with a fixed hidden prefix that every brand reader ignores; the next
   brand action rolls them back or cleans them. No change to the update helper.

**Import and checks**
10. **DEFAULT.** Zip name `clark-brand-<id>-X.Y.Z.zip`; "newest in Downloads" = newest modified time among matching regular files;
    the name's id and the manifest's id must agree; a browser ` (1)` suffix only for a chosen file. `tools/make_brand_zip.py` writes
    Unix modes 0644/0755.
11. **DEFAULT, made exact.** Caps: zip 16 MB, one file 5 MB, 50 files. The cap that applies to `tokens.css` is **256 KB**, not
    1 MB: `excel_palette.py:120` `MAX_BRAND_BYTES = 256 * 1024` (applied at `:131-133`, bigger is not read and the export falls
    back to the committed look). `page.local_tokens` (`page/__init__.py:104`) and `publish.check_brand` (`publish.py:807`) have no
    size cap of their own, so 256 KB is the only true one. Rule: nothing the install accepts may be refused or ignored later at
    export, so the install refuses a `tokens.css` over 256 KB (the generic 5 MB per-file cap still holds for pictures). The earlier
    "1 MB" is dropped (section 5). Also in the hostile caps (T2): total unpacked size, ratio, zip comment, member count from the
    end record, zip64, overlap.
12. **DEFAULT, wording corrected.** No picture decoder exists; structure checks only: `excel_picture.read_size` (`:63`) for PNG, new header checks for
    JPEG and WebP. Allowed names: exactly the union read today: `assets/cover.png|jpg|jpeg|webp`, `logo.png`,
    `design-system/logo.png`, `assets/logo-*.png`, `assets/cover-*.png`. The logo is a picture file, not a `data:` rule;
    `check_brand` is not edited. The `.logo-icon` data rule (`publish.py:663` `LOGO_RULE`) and the still circle picture on
    `.logo` (`publish.py:692-703` `CIRCLE_MAX`, `_circle_picture`) stay allowed exactly as `check_brand` allows them today.
13. **DEFAULT, wording corrected.** Tokens check: whatever `page.check_brand` accepts today. In this tree that function is
    `publish.check_brand` (`publish.py:807`; there is no `page.check_brand`), plus the outside-address scan
    `publish.outside_addresses` (`publish.py:1200`, which `to_client.py:379` and `publish_pdf.py:210` also run). The install calls
    both on the text wrapped in a `<style>`, unchanged; it adds no rule of its own (no "only `:root` and `@font-face`" list), so a
    brand the publish would accept is accepted and one it would refuse is refused. The `.logo-icon` and circle exceptions
    (decision 12) are kept. A `url()` that names a picture is refused only as `check_brand` already does.
14. **DEFAULT.** The zip is read once into memory (`updates.read_once`, `:349`), no kept copy; the review holds the bytes up to 15
    minutes. The whole-zip sha256 is shown; each file's sha256 in `clark-brand.json` is checked; no signature.
15. **DEFAULT.** New module `src/clark/brands.py`; it imports the public `path_problem` (`updates.py:189`), `collisions` (`:219`),
    `read_once` (`:349`) and copies the few private helpers. Nothing in `updates.py`, `update_install.py`, `update_helper.py`,
    `updater.py` is edited. No restart and no global 503; a brand-level lock refuses an install or remove while an export or publish
    of that brand runs. Whether anything caches the page's style hash: checked by the first reader (section 6).
16. **DEFAULT, keep 5.** Backup `<data>/brand-backups/<stamp>-<id>/`, outside `system/`; the last 5 sets are kept, older pruned; one-level Undo of the last brand change only.
17. **DEFAULT.** Deny-list: a plain list of words in a file inside the code, checked on the brand's name, its file names and its
    `tokens.css`; the refusal names no word.

**Outputs**
18. **CHANGED in part.** In 1.0.5: Word colours only (`docx_build.build(published, colours=)`, `:641`); the client workbook in the
    published page takes the project's palette per call, no logo; the brand's NAME appears in no output. **To 1.0.6:** the Word
    template (`word_template.py`, no caller today) and the PDF. `publish_flow.py`, `publish_pdf.py`, `pdf.py`, `word_route.py` are
    guarded for this row. Picture URL per brand `/assets/<id>/cover.png`, id looked up in the installed list, never joined onto a
    path; `img-src` in `csp_policy` gets the prefix. Mac-only screens, as the update screen.

**Premise corrected:** a link under `system/branding` does not block updates (`walk_app` skips `system/` and `data/`,
`updates.py:609`, `:621-622`; pinned by `test_update_placed.py:317`). Link refusal lives only in the brand import and backup.

## 2. The file:line map (confirmed rows only)

| What | Where | Today |
|---|---|---|
| Brand folder | `page/__init__.py:44` `branding_folder`, `:51` `BRANDING` | one folder `system/branding`, fixed at import |
| Tokens file | `page/__init__.py:52` `LOCAL_TOKENS`, `:95` `local_tokens_file`, `:104` `local_tokens` | first of two names, read per call, takes `branding=` |
| Editor pictures | `page/__init__.py:55` `PICTURES`, `:119` `brand_picture(name, branding=None)` | four cover names, 5 MB, magic bytes, stays inside |
| Client brand block | `page/__init__.py:57` `CLIENT_BRAND`, `:315` `page_html(branding=None, view=False)` | `<style id="brand-local">` after the demo block, per request |
| Editor route | `server.py:994` `page_html()` with no argument; `__main__.py:489` seam | one brand for every project |
| Picture route | `server.py:526` `BRAND_PICTURES`, `:529` `brand_picture_route`; `__main__.py:513` | name only, no project; a test keeps both lists equal |
| CSP | `server.py:353` `csp_policy`, `:364` `img-src` | `data:`, `blob:`, `http://<host>/assets/`, `/app/` |
| Publish | `publish.py:1349` `build(..., branding=None, ...)`, `:807` `check_brand` | takes a folder; check runs on the whole page text |
| Publish allow-list | `publish.py:80-81` `PUBLISH_FIELDS["projects"]`, `:98-102` `GATES` | Gantt settings are GATES-only: the precedent |
| One brand for all | `publish_flow.py:188` `self.branding`; `__main__.py:492` builds `Publisher` with none | every publish, preview, Excel, PDF uses `BRANDING` |
| Excel | `publish_flow.py:591` `export_project(..., branding=self.branding)`; `excel_palette.py:140` `palette(css, branding, warnings)`, `:120` 256 KB | colours, logo and wave from one folder |
| Excel logo | `excel_picture.py:32-34`, `:63` `read_size`, `:110` `branding_base`, `:172` `load` | no folder: clark's icon; folder, no logo: none |
| Client workbook | `excel_client.py:38` `PALETTE`, `:192` `workbook_bytes`, `:226` `embed` | committed colours fixed at import |
| Word | `word_route.py:544` `docx_build.build(published)`; `docx_build.py:81` `palette(colours)`, `:641` `build(published, colours=None)` | no colours passed today |
| PDF | `publish_pdf.py:149` `make(body_bytes, ...)`, `:287` `page_html(pub.branding, view=True)` | a print of the published bytes (1.0.6) |
| Layout number | `store.py:37` `SCHEMA_VERSION = 19`, `:2593-2598` `MIGRATIONS` | literal per step; a test pins them equal |
| ADD COLUMN precedent | `store.py:2471` `migrate_review_after_days`, `:2552` `migrate_gantt` | skipped when the column exists; no frozen schema file |
| Copy before migrate | `store.py:1996-2012` `bring_up_to_date` | backup first; no copy, no step |
| Editor read | `store.py:3022` `SELECT * FROM projects`, `:3028` | a new column reaches the page with no code change |
| Project changes | `changes.py:60-61` `GANTT_PROJECT_FIELDS`, `PROJECT_FIELDS` | the only project fields a request may change |
| History labels | `history.py:307` `FIELD_NAMES["projects"]` | one plain label per field |
| Zip reading model | `updates.py:189`, `:219`, `:320` `_check_structure`, `:349` `read_once`, `:601` `_is_link` | public: `path_problem`, `collisions`, `read_once` |
| Layout pins | `test_v060.py:407` (`SCHEMA_VERSION = 19\b`), `test_update_17_to_18.py:38` (`NEW_LAYOUT = 19`) | both move to 20 |

## 3. Four tracks

Build order: T1, then T2 (needs only the id rules), then T3 and T4 (both need T1's column and T2's resolver). T3 and T4 may run
side by side after this note has two reads. Every track: the five movement files `test_movement_hostile`,
`test_movement_never_published`, `test_store_movement`, `test_server_movement`, `test_movement_fixtures` stay green, run and named
with their test counts in each READY FOR READ; plus `test_no_real_names`. Readers for every track: the guarded-code reader first,
the project lead second. Proposed builders: builder A for T1 and T2; builder B for T3; builder C for T4 (names on the board).

### T1 storage and layout 20 (size M; builder A)

- **Files:** `store.py` (`SCHEMA_VERSION` to 20 and its comment; `BRAND_STEP = 20`, `migrate_brand(con)`; `(20, migrate_brand)` in
  `MIGRATIONS`), `schema.sql` (last `projects` column, the same text), `changes.py` (`"brand"` in `PROJECT_FIELDS`; its check in
  the project-change validation; the reply and undo reply hand back `brand`), `history.py` (label and undo phrase),
  `publish.py` (`GATES["projects"]` gains `"brand"`; `PUBLISH_FIELDS` unchanged), `page/src/stores/changes.js` (merge `brand`
  from the reply, if it lists fields by name).
- **Column, exactly:** `brand TEXT NOT NULL DEFAULT 'generic' CHECK (length(brand) BETWEEN 1 AND 60)`. `migrate_brand` is
  `ALTER TABLE projects ADD COLUMN` with that text, skipped when `columns(con, 'projects')` has it, as step 14 (`store.py:2471`).
  The backup before migrating comes free from `bring_up_to_date`. No frozen schema file.
- **Seam:** `changes` checks the id with an injected `brand_ids()` (returns the set of installed ids plus `generic`; T2 gives the
  real one; T1 ships with `{"generic"}`). Unknown id: refused before the step opens, with an existing refusal.
- **Refusals:** an id that is not `generic` or installed; empty; over 60; not a string.
- **Tests (NEW):** `test_store_brand_migration.py`, modelled on `test_gantt_migration.py`: literal equals table; 19 to 20 keeps
  rows and gives `generic`; copy first; no copy, no step; second open changes nothing; an older clark refuses the new file;
  1 to 20; new equals migrated columns; touches no other table; rollback; CHECK refusals. `test_project_brand_setting.py`: change,
  undo, history label, unknown id refused. **EDIT (WEAKENS: none, a pin moves forward):** `test_v060.py:407`
  before `r"SCHEMA_VERSION = 19\b"`, after `r"SCHEMA_VERSION = 20\b"` (and the comment's history); `test_update_17_to_18.py:38`
  before `NEW_LAYOUT = 19`, after `NEW_LAYOUT = 20` (its docstring says 17 to 20). Other pins that move with the layout (found by the check): `test_gantt_migration.py:188` (`[-6:] == NEW_COLUMNS`, `brand` becomes the last column), `test_gantt_section_type.py:162` (`version == "19"`) and `:65-66` (`SCHEMA_VERSION == STEP`, `MIGRATIONS[-1][0] == STEP`), `test_update_17_to_18.py:259` (`leave_out` gains `brand`), the `later` column sets at `test_store_section_templates_migration.py:71` and `test_store_use_case_done_migration.py:103`, `test_changes_tiles.py` (`GANTT_DEFAULTS`, `CHANGE_KINDS`, `UNDOABLE`, `PROJECT_FIELDS`), and the `-- clark:` marker rule for `schema.sql` (`test_store_schema.py`). All move forward, WEAKENS: none. Run set: `test_store_migration`,
  `test_migration_chain`, `test_store_schema`, `test_store_flags`, `test_gantt_migration`, `test_gantt_section_type`,
  `test_update_17_to_18`, `test_update_layout_newer`, `test_release_manifest`, `test_v060`, `test_v104`, the five movement files.
- **Never:** `brand` in `PUBLISH_FIELDS`; a test asserts `"brand" not in PUBLISH_FIELDS["projects"]` and that it is in `GATES`.

### T2 the brand library, `src/clark/brands.py` (size L; builder A)

- **Files:** NEW `src/clark/brands.py`; NEW `tools/make_brand_zip.py`; `page/__init__.py` (a resolver beside `branding_folder`);
  `server.py` (routes, body limits, route table: guarded); NEW Settings screen under `page/src/edit/` modelled on `Update.jsx`.
  Nothing in `updates.py`, `update_install.py`, `update_helper.py`, `updater.py`.
- **Interfaces:**
  - `brands.installed(root) -> list[{"id", "name", "version"}]`: lists `system/branding/<id>/` folders with a valid
    `clark-brand.json`, plus `local-brand` when a top-level `tokens.css` exists. Ignores hidden-prefix folders. Read per Settings
    call, never per page request.
  - `brands.folder(root, brand_id) -> Path | None`: `brands.GENERIC` (a distinct sentinel, never `None`: `excel_picture.load(None)` falls back to system/branding) for `generic`, for an unknown id and for a removed brand (the read-time
    fallback); the top folder for `local-brand`; otherwise `system/branding/<id>`, the id looked up in `installed()`, never joined
    from request text.
  - `brands.review(path) -> {"review_id", "id", "name", "version", "zip_sha256", "added", "replaced", "removed"}`: one
    `read_once(path, max_zip=16 MB)`; bytes held 15 minutes.
  - `brands.install(review_id)`, `brands.remove(brand_id)`, `brands.undo()`: each takes the brand lock and a backup first.
- **Zip shape:** one top folder `<id>/`, holding `clark-brand.json` = `{"id", "name", "version": "X.Y.Z", "files": [{"path",
  "size", "sha256", "mode"}]}`, `tokens.css`, and only the allowed picture names (decision 12). Every member: `path_problem` clean,
  no `collisions`, no link, mode 0644/0755, made on Unix, no folder entries, not encrypted, stored or deflated, counted read
  against its declared size, size and sha256 equal to its manifest row, no file unlisted, no row without a file.
- **Checks in order:** name pattern; caps (hostile caps below; zip 16 MB, file 5 MB, 50 files, `tokens.css` 256 KB); manifest shape; id
  rules and reserved list; deny-list on name, file names, `tokens.css`; `tokens.css` UTF-8 and at most 256 KB,
  `check_brand("<style>" + css + "</style>")` and `outside_addresses` pass as they are today (decision 13); pictures: PNG through `read_size` (1 MB, 2000 px for the Excel
  files), JPEG and WebP header and structure checks, each reader's own cap.
- **Install:** write into `system/branding/.clark-brand-new-<id>/` (0700, `xb`), re-check hashes; back up the old `<id>/` to
  `<data>/brand-backups/<stamp>-<id>/`; rename old to `.clark-brand-old-<id>`, rename new to `<id>`, then delete old. Any leftover
  hidden folder at the next brand action: rolled back if `<id>/` is missing, else removed. Remove = backup, then rename to the old
  name and delete. Undo = put back the last backup set by the same two renames.
- **Hostile caps (design requirements, all checked before anything is extracted or parsed further):**
  - member count read from the end-of-central-directory record before any member is parsed; over 50 is refused (50 files);
  - zip64 refused (a zip64 end record or locator, or a size/offset field at its sentinel);
  - total unpacked size cap and a compression ratio cap, counted while reading, not trusted from the headers (numbers to be
    taken from the import spec);
  - overlapping members refused (two members whose local-header ranges cross, or share data);
  - zip comment length cap (number to be taken from the import spec);
  - every symlink or link re-checked in the staged tree (`system/branding/.clark-brand-new-<id>/`) before the install renames;
  - zip 16 MB, one file 5 MB as above.
- **Zip-structure failures reuse the existing damaged-file refusal, no new sentence.** An encrypted member, compression method
  99 (AES) or any structure failure (`RuntimeError`, `BadZipFile`, `EOFError`, `zlib.error`, `OSError`, `ValueError`) gives the
  same refusal the update zip gives for a damaged file (`updates.py:106` `"damaged"`, raised from the `except` at `:469`). The
  pattern is PR 934's catch in `excel_import.check_sheets_early` (commit `de750126f66e543927da20ed29f590ce691f9423`, on the row 966 import-caps branch,
  `excel_import.py:1326`, its `except` at `:1361`: `_TextTooLong, zipfile.BadZipFile, zlib.error,
  EOFError, OSError, ValueError, RuntimeError`); that commit is not in this tree.
- **Refusals:** each check above fails with one plain sentence (section 4), never naming a deny-list word or showing a path from
  the request. The page never sends a path: the file comes from the system dialog or Downloads (`platform.py:429`, `:115`).
- **Tests (NEW):** `test_brands_zip.py` (every refusal, one per check, with hostile zips built in temp dirs: `..`, absolute,
  backslash, case clash, link member, odd mode, oversize declared and actual, unlisted file, wrong hash, reserved id, deny-list hit,
  `@import`, `url()` to a picture, a PNG with a bad CRC, a JPEG cut short, a WebP with a wrong length, plus the missing hostile cases: an encrypted member, compression method 99, 51
  members (count from the end record), zip64, a member whose declared size lies (actual bytes differ), overlapping members, an
  over-long zip comment, a link found only in the staged tree); `test_brands_install.py`
  (install, replace with "removed" shown, remove, undo, crash between renames rolled back, backup outside `system/`, lock refuses
  while a publish of that brand runs); `test_brand_routes.py` (body limits, token, no path accepted). Existing kept green:
  `test_brand.py`, `test_brand_picture.py`, `test_page_branding_root.py`, `test_updates.py`, `test_update_placed.py`.

### T3 the editor follows the open project's brand (size M; builder B; guarded `server.py`)

- **Files:** `server.py`, `__main__.py` (seams), `page/__init__.py`, the page's project-change code under `page/src/`.
- **Seams:** `page_html(project=None)` on the server: `__main__` passes a function that reads the open project's `brand`, calls
  `brands.folder`, then `page.page_html(branding=folder)`; the `GENERIC` sentinel gives no brand block (the page has no brand look; the Excel Cover
  keeps clark's icon through the explicit `GENERIC` branch, `CLIENT_BRAND` only goes in with a brand). `brand_picture(name, brand_id)`: two arguments; the id must be in `installed()`; the
  name in `BRAND_PICTURES`. The test string `brand_picture=page.brand_picture` in `test_brand_picture.py:229-237` changes with the
  seam (WEAKENS: none; the string is replaced by the new seam's text, the equality check of the two lists stays).
- **Swap on project change:** the CSP's style hashes are computed per response from the page bytes (`server.py:353`), so a style
  element added later by script would be refused. The one brand block is therefore swapped by the server, not by script: on
  project change the page loads `GET /?project=<code>`, and the server sends the page with that project's single
  `<style id="brand-local">` (none for Generic) and the hashes of those bytes. Never two brand blocks, no CSP loosening. An
  unknown code gives the page with no brand block. (Alternative for the first reader: a route returning the block, with the
  page's CSP listing hashes of every installed brand; not recommended, it names every brand's bytes on every page.)
- **Pictures:** `/assets/<id>/cover.png` (and the other three names); `img-src` gains nothing new if the prefix stays
  `http://<host>/assets/`; the route splits exactly two parts and refuses anything else with the existing 404.
- **Refusals:** an id not installed: 404 `picture_not_found` (existing); a project code unknown: the existing not-found.
- **Tests (NEW):** `test_editor_brand.py`: project on brand X gets X's block and not Y's; Generic gets no `brand-local` and keeps the
  icon; a removed brand gives Generic; `/assets/x/../y/cover.png`, `/assets/unknown/cover.png`, `/assets/x/logo.png` all 404; the
  page source holds one `brand-local` at most. Existing: `test_page.py`, `test_brand_picture.py` Layering, `test_server.py`
  route pins, the five movement files.

### T4 outputs (size M; builder C; guarded publish, publish_flow, excel*, docx_build, word_route)

- **Files:** `publish_flow.py` (resolve the project's folder at each call instead of `self.branding`: `:234`, `:264`, `:275`,
  `:550`, `:591`), `publish.py` (`build` passes the folder to the client workbook), `excel_client.py` (`workbook_bytes(published,
  palette=None)`, `embed(published, palette=None)`; `PALETTE` stays the default), `word_route.py:544` (pass `colours=`),
  `excel.py` only if `export` needs the Generic rule.
- **Generic:** `brands.folder` returns the sentinel `brands.GENERIC` (NOT `None`: `branding_base(None)` falls back to
  `page.BRANDING`, see decision A), and `excel_picture.load` and `excel_palette.palette` answer clark's icon and the committed palette
  for it, by an explicit first branch. An installed brand without a logo: no logo.
- **Word colours:** `colours = {token: "rrggbb"}` from the brand's `tokens.css` through the same reader Excel uses
  (`excel_palette`), passed as `docx_build.build(published, colours=colours)`; `palette()` already ignores what is not six hex.
- **Client workbook palette:** `{"fill", "text"}` taken from the same palette, per call; no module state changes.
- **Published page:** carries the brand's look (its `brand-local` block, checked by `check_brand`), never the id, never the name.
- **Not in 1.0.5 (say so in the release notes):** the Word template and the PDF. The PDF stays a print of the published bytes;
  `publish_pdf.py:287` re-reads `page_html` only for markers and must be given the same folder as the build (one line, in T4).
- **Tests (NEW):** `test_brand_isolation.py`: two brands X and Y with distinct names, colours and pictures; project P on X; P's
  published page, preview, Excel workbook, client workbook and Word file contain none of Y's name, colours or picture bytes, and
  none contains X's id or name; Generic P gets clark's icon on the Cover, with `system/branding` present and a second brand installed (the case a `None` fallback would break). Existing: `test_excel_brand_export.py`,
  `test_excel_cover_brand.py` (incl. `NotOnThePublishedPage`), `test_excel_picture.py`, `test_brand_circle.py`,
  `test_docx_build.py`, `test_to_client.py`, the five movement files.

## 4. The words

See spec 944 section 2: every on-screen sentence there is NEW and goes to the project lead for approval before any build ships it.
This note adds two NEW strings of its own, also for approval: the history label `Brand` and the undo phrase `the brand`. "Back
to the default look" is the spec's sentence (NEW). Ids (`generic`, `local-brand`), file names and API refusal codes are
identifiers, not words shown as sentences.

## 5. Risks and what is not covered

- **Caps that disagree.** The page reads any size, Excel only 256 KB (`excel_palette.py:120`); the install refuses over 256 KB
  so no brand fails later. Pictures: Excel files 1 MB and 2000 px, served covers 5 MB.
- **CSP and the swapped block** (T3): a fresh page load is recommended exactly because the style hash is per response.
- **Brand lock vs publish.** A remove during a long publish of the same brand is refused, not queued.
- **Not covered:** Windows and Linux screens (Mac only); a brand signature; the Word template; the PDF; the brand name anywhere in
  output; a brand's own font file other than a `data:` font in `tokens.css`; teammate copies carrying the column (not traced).
- **Unchecked facts (not used as fact):** whether the server caches a style hash; how `history.py`
  shows a field with no label; whether `page/src/stores/changes.js:60` lists reply fields by name.

## 6. Open questions left

1. The first reader confirms nothing caches the page or its style hash (decision 15), and agrees the T3 swap is a server-side
   page load (this note's recommendation) rather than a returned block with every brand's hash.
None open. Settled here: Generic Excel Cover is clark's icon (via `brands.GENERIC`); brand backups keep 5 sets (decision 16;
`update_install.py:50` `KEEP = 3` is the update set's own count and is not changed); Remove follows the spec's two clicks.
