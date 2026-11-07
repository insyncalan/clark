# Design note: #836 setup mode in the server (step 4 of the build plan; guarded: `server.py` and `launch.py`)

Written 07-11-2026. Review of the build that follows this note: Full (two readers, never the builder). Nothing in this note is
built. Line numbers are `origin/main` at `5c3d6eae3`. The prototype's four files (PHASE2-SPEC, GUARDED-CHANGES, NEW-WORDS,
TRANSLOCATION-PLAN) were read from the prototype branch at `8493cda08`; where this note differs from them it says so.
Main is frozen until 1.0.4 ships, so this is a document only: no code, no test and no string changes.

## Plain words, for the owner

Today, when a check fails, the launcher says one line and stops, and nobody sees a window (`launch.py:167-196`, `:238-243`). A
person who double-clicks clark.app on first run therefore sees a dialog, or nothing. Setup mode is a second, very small clark
server that the launcher starts **instead of** the normal one when a check fails. It has no database, no data folder in use and
none of clark's data routes. It serves one page, the doctor's checks drawn as a page, with a "choose a folder" button and a
"Check again" button. When every check that must pass does pass, the setup server stops and the launcher's ordinary start takes
over on the same port. A person who never has a failed check never meets any of this: the normal start is untouched.

## What is built now, and what waits

Nothing here is built. This note is step 4's design; the prototype's step 3 (doctor as data) must land first, because the page
draws the doctor's lines and `doctor.py` prints them today (`doctor.py:219-229`, `run_check` at `:196`). Step 5 (the real page
and its Help text) waits for the owner's words (`NEW-WORDS.md`, items 8 to 12). Step 4 ships with a plain stand-in page of one
inline script and one inline style, as `PLACEHOLDER` (`server.py:551-558`) does for the normal page, so every route can be tested
without the real page.

## 1. Where the code lives, so the guarded part stays small

- **`server.py` stays free of clark imports** (its own rule, `server.py:593`: "this server imports nothing from clark"). It gets only the
  mechanism: a `SetupHandler(Handler)` class, two small route tables and one new constructor argument `setup=None` on
  `LocalServer.__init__` (`:1436`) and `serve()` (`:1502`), the same way each seam is given (`:1441-1471`). All the logic is in a new
  module `src/clark/setup_mode.py` (not guarded), which holds the checks, the chooser call and the pointer file (section 6).
- **A separate entry point, `python3 -m clark.setup_mode --data F --port N`**, so `__main__.py` is not touched. `__main__.main`
  opens the store (`:440-449`), builds the store's seams (`:455-520`) and holds the data lock (`:238`); setup mode must do none of that. It sets
  the same four module settings `__main__` sets (`:468-471`): `set_open_files` is **not** called (section 2), `set_idle`, `set_data_mark`
  and `set_version` are.
- **Normal mode is byte-for-byte the same.** `serve()` picks `SetupHandler` only when `setup` is given. The normal `Handler` is
  changed in one place (section 3). `GET_ROUTES` (`:1208`) and `POST_ROUTES` (`:1214`) are not edited, so `tests/_routes.py`
  (which compares both tables, `tests/_routes.py:34-38`) and `test_the_only_routes_without_a_token_are_the_listed_ones`
  (`tests/test_server.py:249`) stay as they are. The new tables are separate dicts with their own pinned list (section 8).

## 2. The routes (setup mode only)

One table of GET routes and one of POST routes, `SETUP_GET_ROUTES` and `SETUP_POST_ROUTES`. Every error body is the server's own
`error_body(code)` (`:249`), whose words are the existing `MESSAGES` (`:156-180`). No new `MESSAGES` entry is needed: a refusal
that comes from a check carries that check's existing words, quoted unchanged.

| Route | Token | Request | Reply |
|---|---|---|---|
| `GET /health` | no (as everywhere, `:1380`) | `X-Clark-Data` optional | the existing `health_answer` (`:297-308`), with `DATA_MARK` set to the mark of the folder the launcher was going to use, so a second double-click sees `ours` (`launch.py:174-175`) and only opens the window, not "another copy ... different data" (`launch.py:88`) |
| `GET /` and `GET /setup` | no (as `/`, `:1381`) | none | 200 the setup page with the token in the `clark-boot` block (`with_boot`, `:565`), CSP from the bytes (`send`, `:1295-1307`). `/` is the same bytes because the launcher opens `/` (`launch.py:64-66`, `:198`). `page_load_is_ours` (`:931`) decides whether it counts as "a window is open" |
| `GET /api/setup/checks` | yes | none (a body is 400, as `movement_route`, `:597-598`) | 200 `{"ok":true,"ready":bool,"folder":"~/...","checks":[{"id","status","required","words"}]}`. `status` is the doctor's `ready`, `fix`, `advice` or `not checked` (`doctor.py:37`); `words` is the doctor's line unchanged. `ready` is true when no required check is `fix` or `not checked` (the doctor's own rule, `doctor.py:206-216`). The folder is shown with `~` (`platform.with_tilde`, `:636`) |
| `POST /api/setup/folder` | yes | `{}` only | The request never names a path (as `/api/section-file`, `server.py:66-67`): the folder comes only from the system dialog. See section 5 for the replies: 200 `{"ok":true,"chosen":false}` on Cancel; 200 `{"ok":true,"chosen":true,"folder","checks","ready"}`; 409 with the check's own refusal words (`code:"folder_refused"`); 409 `dialog_failed`; 409 `busy` |
| `POST /api/setup/finish` | yes | `{}` only | Runs `launch.finish_update` (`launch.py:114-147`) with a `say` that collects its lines. 200 `{"ok":true,"finished":bool,"words":[...]}`. The words are `update_helper.MESSAGES` (`update_helper.py:103-127`) and the helper's own result message, unchanged. One at a time (409 `busy` for a second at the same moment) |
| `POST /api/setup/done` | yes | `{}` only | Re-runs every check **now**. Any required check not ready: 409 `{"ok":false,"code":"not_ready","checks":[...]}` and the server goes on. All ready: 200 `{"ok":true,"restart":true}`, sent first, then the server stops (the pattern of `update_route`, `:1190-1194`); `setup_mode.main` then starts the normal clark (section 4). Nothing is trusted from the page: "done" re-checks |
| `POST /api/here` | yes | `{}` | the existing `here_route` (`:942-945`), so the idle stop counts the open setup page as "here" (section 4) |

Everything else is refused as today: an `/api/` path that is not in these tables gives 403 without the token and 404 with it
(`:1391-1396`); a path that is not under `/api/` gives 404 (`:1397`); OPTIONS 403 (`:1364`). **Not served in setup mode:**
`/past`, `/preview`, `/assets/`, `/csp-report`, `/manifest.webmanifest`, `/sw.js`, `/offline`, `/app/*` (the six open files,
`:881-896`). A person gets no "install as an app" offer on a page that is going away, and no report endpoint with no log behind it
(no logging is set up before a data folder exists, `__main__.py:392`).

Bodies: a POST goes through the same gate order as every other (token, Content-Type 415, length 411, body 400, `:1399-1425`); the
three setup POSTs then also refuse any body that is not exactly `{}` (400 `bad_request`), so a route cannot be given a path, a
command or a setting to carry.

## 3. How the page is booted with a token, with no database and no normal API

- **The token is this process's own** (`TOKEN = secrets.token_urlsafe(24)` at `server.py:150`, new at every start). The page gets it
  in the `clark-boot` data block (`with_boot`, `:565-571`: JSON, `<` escaped, never run, so it needs no hash). The setup page reads
  it the way the normal page does and sends it as `X-Clark-Token` (`:151`).
- **The normal API is not reachable by construction, three ways.** (1) `SetupHandler.do_GET` does not read `GET_ROUTES`,
  `page_route`, `preview_page_route`, `past_page_route` or `brand_picture_route`; its `post_table()` returns `SETUP_POST_ROUTES`.
  (2) The server object is built with **no** seams (`data_for`, `change`, `publisher` ... all `None`/default, `:1441-1471`), so even
  a handler bug would answer the existing 404/503, never data. (3) The process never opens the store: it does not import
  `store`, `changes` or `publish*` (a test reads `setup_mode.py` and `sys.modules` after a request).
- **Why the page can reload itself into the normal clark.** When setup stops and the normal server starts on the same port, the
  new process has a new `TOKEN`, so the setup page's next call with the old token gets 403 `stale` (`:1337-1338`, "This page is out
  of date because clark was restarted. Reload the page and try again."). After a successful "done" the stand-in page and the real page
  poll `GET /api/setup/checks` every second and reload `/` on the first 403 `stale` (or when the connection comes back). No
  new `/health` key is needed (`/health` stays `{"ok":true,"version"}` plus `this_data` when asked, test 8).
- **The one change to the normal `Handler`.** `do_POST` looks the route up in one place (`:1422`:
  `here_route if route == HERE_ROUTE else POST_ROUTES.get(route)`). Recommended: move that line into a method `post_route(route)`
  that `SetupHandler` overrides, rather than copy `do_POST` (about 25 lines of gate order that must not drift). `SetupHandler.do_GET`
  is written out in full (about 15 lines): its list of routes is the point. Alternative, if the owner prefers no change to the
  normal `Handler` at all: copy `do_POST` into `SetupHandler` and pin the copy with a test that sends the same probes to both
  handlers and compares the answers (section 8, test 7).

## 4. Origin and Host checks, as the other mutating routes

Nothing new is invented; the setup routes use the existing functions, in the existing order.

- **Host:** `host_ok()` (`:1276`) on every GET (`:1371-1374`) and, inside `csp_local`, on every API call (`:402-405`): exactly
  `127.0.0.1`, `localhost` or `[::1]` with a port from 1 to 65535 (`host_allowed`, `:265`). Two Hosts or two Content-Lengths: 400
  (`headers_ok`, `:1280`). A DNS-rebinding page gets 403.
- **Origin and cross-site:** `authorised()` (`:1326`) calls `csp_local`: every `Origin` must equal `http://<Host>`, any
  `Sec-Fetch-Site: cross-site` is refused (`:408-414`), and the peer must be local (`local_peer`, `:121`). A page on another port is
  another site. No Origin (a plain client) is allowed, as today; the token still has to match, in constant time (`token_ok`, `:272`).
- **Token:** none at all is 403 `not_allowed`; a wrong one 403 `stale`, which is what lets an old setup tab know it should reload.
- **Container mode:** the container refusal (`:1375-1377`) applies unchanged. Setup mode is started only by `launch.py`, which is the
  Mac's path; `python3 -m clark` by hand keeps printing its line (`__main__.py:450-452`).
- **Why a folder-choosing POST needs all of that:** it opens a window on the person's screen. A web page the person happens to have
  open must not be able to do that. The token is in a data block that a page of another origin cannot read (it cannot read `GET /`
  cross-origin), and the Origin and `Sec-Fetch-Site` checks refuse the request before the dialog is touched.

## 5. How the system folder chooser is called safely

- **One function, one seam.** `platform.choose_folder(prompt, start=None, run=None, on=None)` (`platform.py:423-426`) runs
  `osascript` through `_dialog` (`:445-451`). `setup_mode.Setup.__init__` takes `choose_folder=None` and uses
  `choose_folder or platform.choose_folder`, the way `AskFolders` (`ask_folders.py:75`) and `Publisher` (`publish_flow.py:183`) do. A
  test passes its own function; the real one is never named at import time and never run in a test.
- **The no-dialog rule for every test run.** `PATH=/tmp/nodialog:$PATH` puts a stub `osascript` first; it prints "nodialog stub:
  osascript refused" and exits 1. `_dialog` turns a non-zero exit that is not "-128" (Cancel, `platform.py:45`) into `PlatformError`
  "The folder window could not be opened. Try again; if it keeps happening, restart clark." (`:449-450`, `TRY_AGAIN` at `:386`), so a
  test that forgot its fake gets the 409 `dialog_failed` path, not a window. On Linux, `_only_mac` raises `NotBuiltYet` first. One
  test builds the service with **no** fake and asserts that exactly this happens (the real function, the stub, the 409), and
  another asserts `Setup(...).choose_folder is platform.choose_folder` by identity without calling it.
- **One dialog at a time.** A lock around the call; a second POST while a dialog is open is 409 `busy`, never a second window. The
  dialog has **no timeout** (`_run`, `platform.py:349-351`, passes none) and blocks one server thread until the person answers. That
  is acceptable here: it is a threaded server (`:1428`), the POST counts as busy (`run_route`, `:1349-1358`) so the idle stop waits for
  it (`:1523-1525`), and the setup page shows its own "waiting" state.
- **The answer is untrusted text and is checked in this order**, nothing written until all pass: it is an absolute path of at most
  1,000 characters with no control character (the rule `settings.set_backup_copy_folder` applies, design-622); it exists and is a
  real folder, not a link; `platform.check_data_dir(path, roots)` (`platform.py:219-238`, the OneDrive refusal, which is also
  where the Dropbox/iCloud/Google Drive check of step 6 will sit); `doctor._can_save_in` (`doctor.py:95-109`, a temporary file made and
  removed). A refusal is the check's own words in a 409; Cancel changes nothing and says nothing.
- **The prompt** is a string shown in the dialog. An existing one (`ask_folders.PICK_PROMPT`, `publish_flow`'s) is not about the data
  folder, so the prompt is **NEW** (open question 7).

## 6. What launch.py changes (each hook, from the current code)

The prototype's `GUARDED-CHANGES.md` (section "For the setup page (Task D)") names server routes, a "setup mode before a data folder
passes `check_data_dir`", the page and its CSP hashes, `idle.py` and `appfiles.OPEN_FILES`. It does not name any `launch.py` line;
the hooks are these. `launch()` today says a line and returns 1 at six places (`:167`, `:169`, `:173`, `:178`, `:187`, `:196`), and `main()` at two more (`:238-243`).

| Hook | Now | Becomes |
|---|---|---|
| `launch.py:238-240` `except platform.PlatformError` in `main` (the OneDrive refusal of `check_data_dir`, `:233`) | `say(str(e)); return 1` | start setup mode with `reason="data_folder"`; the OneDrive case is the main first-run use. `main` has not made the folder (`:234`), so setup must not either |
| `launch.py:241-243` `except OSError` (folder can't be made) | `say("The data folder can't be made ...")` | same, `reason="data_folder"` |
| `launch.py:166-167` `if not finish(folder, say): return 1` | the update helper's `not_restored` or `busy` line | setup with `reason="update"` (the page's "Check again" is `POST /api/setup/finish`) |
| `launch.py:168-169` `same_version.refuse()` | prints `MESSAGE` to stderr itself (`same_version.py:130`, no `say`) and returns 1 | setup with `reason="version"`. `refuse()` prints to the terminal, so the hook calls `same_version.mixed()` (`:62`) and passes `MESSAGE` as the check's words |
| `launch.py:171-173` `OTHER_DATA` / `NOT_CLARK` | `say(report(...))` | **unchanged in this step** (open question 2: the port is the thing that is taken) |
| `launch.py:176-178` `lock_refusal` | `say(refusal)` | unchanged (there is nothing the person can fix on a page) |
| `launch.py:189-196` the started clark did not answer | `say("Nothing opened ...")` | unchanged |
| `launch.py:158-160` `launch()` signature | seams `start`, `health`, `wait`, `free`, `finish` | one more seam, `setup=start_setup`, so tests pass a fake that records the call (like `start` at `:184`) |

New in `launch.py`: `start_setup(port, folder, reason, say, environ, start, health, wait, ...)`, about 25 lines, built from what is
already there: it starts `[sys.executable, "-m", "clark.setup_mode", "--data", str(folder), "--port", str(port)]` with the environment of
`:182` (`CLARK_LAUNCHED=1`, `CLARK_PORT`, `PYTHONPATH`), waits with `wait_for_clark` (`:95-105`, unchanged; the setup server answers
`/health` with the mark of `folder`, `appfiles.data_mark`, `:165`) and then `open_clark` (`:201-214`, unchanged). `launch.py:25`'s
import line does not change: the setup server is a separate process named by a string, so `launch` does not import `setup_mode`.

- **Two details the existing `start` call forces.** `start(argv, env, log, cwd=str(folder))` (`launch.py:184`) puts the log in
  `<data folder>/server.log` and runs in the data folder. In the refused case that folder is the one that must not be touched, so
  setup uses `platform.log_dir()/setup.log` (`platform.py:121-124`, `~/Library/Logs/clark/`) and `cwd=str(SRC)` (`launch.py:33`).
- **Idle stop.** `CLARK_LAUNCHED=1` makes `serve()` start `IDLE.watch` (`server.py:1523-1525`, `idle.py:46-69`) after 60 s without
  `/api/here`. The page must send the heartbeat (`idle.HEARTBEAT` 10 s, `idle.py:19`) or setup would stop under a person who is
  reading it. This is why `/api/here` is in the setup table, and it is the one idle-related line the prototype names.
- **"Done" starts the normal clark**: after `serve()` returns (`server.py:1530-1535`, jobs waited for, socket closed), `setup_mode.main`
  runs the same `start_detached` call as `launch.py:184` with the chosen folder, then exits. The port is free by then, so there is no
  race with a second listener. If that start fails, the person gets the existing "Nothing opened ..." text from the log
  (`launch.py:193-195` words) on the next double-click, not a half-state.
- **Where the chosen folder is remembered (open question 1).** There is no stored choice of data folder anywhere today: only `--data`
  (`launch.py:232`, `__main__.py:440`) or `platform.data_dir()` (`platform.py:109-113`). `settings.json` is inside the data folder, so it
  cannot hold it. Recommended: a one-line file, `clark-data-folder`, **beside** the default folder (in `~/Library/Application Support/`,
  not in it), written with `platform.replace_file` (`:483`) after the checks in section 5 pass, and read in one place, `launch.main`
  at `:232`, with the same checks re-run at every read (an unreadable or refused value is ignored, not trusted). That makes the launcher
  the only reader. `__main__.py:440`, `doctor.py:69`, `same_version.py:106`, `publish_flow.py:187` and `platform.py:782` read the
  default; the launcher and the updater always pass `--data` (`platform.py:124`), so they follow the launcher. Making
  `platform.data_dir()` itself read the file would reach all seven callers and the log rule at `platform.py:137`; not recommended.

## 7. What is not in scope

- The real page, its Help text and its words (step 5); Dropbox, iCloud Drive and Google Drive checks (step 6); Windows (step 7).
- Moving or copying data. Choosing a new folder starts a **new, empty** one (the demo projects load only into a folder with nothing in
  it, `__main__.py:449`); data already in the refused folder is left exactly where it is. Open question 3.
- Any change to the store, the schema, migrations, publishing, Excel, Word, `updates`, `package`, `release_files`, `__main__.py`,
  `idle.py`, `appfiles.py`, `platform.py`'s existing functions or `doctor.py`'s wording.
- The applet and App Translocation (`TRANSLOCATION-PLAN.md`); the "port taken" and "lock held" cases (section 6).
- A typed path box. The page offers the system chooser only; the request never carries a path.

## 8. The tests that will pin it

New files (plain `unittest`, temporary folders only, `PATH=/tmp/nodialog:$PATH`, no real data folder, no real port):
`tests/test_setup_mode.py` (the service: checks, chooser, pointer file, done) and `tests/test_server_setup.py` (the routes over a real
`LocalServer` on port 0). `test_launcher.py` gains the hook cases. Browser tests wait for step 5, one file at a time.

1. **The exact route lists:** `SETUP_GET_ROUTES` and `SETUP_POST_ROUTES` equal written-out lists in the test (the idea of `tests/_routes.py`,
   not editing its `unplanned`, so the normal lists keep their tests).
2. **Nothing normal is reachable:** for every path in `GET_ROUTES` and `POST_ROUTES` and the three page routes, a setup server answers
   403 with no token and 404 with the token, and a spy seam on every `LocalServer` argument is never called.
3. **No data:** after every request in the suite, the data folder (a temporary one) is unchanged byte for byte, and only the pointer
   file is ever written, and only after a chosen folder passes; `store`, `changes` and `publish` are not in `sys.modules`; `setup_mode.py`
   does not contain `milestone_moves`, `/api/movement` or `movement` (see below).
4. **Gates:** the token, Host, Origin, `Sec-Fetch-Site`, 415, 411, 400 and OPTIONS cases of `test_server.py:211-300` and
   `Here` (`:955-975`) repeated on each setup route, and a body other than `{}` is 400.
5. **Chooser:** a fake returning a folder, `None`, a relative path, a path with a control character, a link, a file, a OneDrive
   folder (refused with `platform.py:235-238`'s words) and a read-only folder; a raising fake gives 409; a second POST during a held
   dialog gives 409 `busy`; the stub run without a fake gives 409 and no process is started.
6. **Launcher hooks:** each of the four hooks in section 6 calls the `setup` seam once with the right `reason` and port, and the five
   unchanged cases still say their old lines (`test_launcher.py`, `test_launcher_words.py`, `test_launch_e2e.py` are not weakened);
   setup logs to `log_dir`, never the data folder; `/health` of a fake setup server counts as `ours`.
7. **If `do_POST` is copied rather than parametrised:** the differential test of section 3.
8. **Done:** with all checks ready it answers 200 `restart:true`, the server stops and the fake `start` is called with the chosen
   folder; with one `fix` it answers 409 and keeps running; a stale token after the restart is 403 `stale`.

**The five movement files stay green and are untouched:** `test_movement_hostile`, `test_movement_never_published`,
`test_store_movement`, `test_server_movement` and `test_movement_fixtures`. They are at risk in these exact ways, so each is run before
and after the build: `test_server_movement.py:141-147` scans every `src/clark/*.py` except `server.py`, `__main__.py`, `store.py` and
`movement_read.py` for `/api/movement` and `milestone_moves`, so `setup_mode.py` must contain neither; `:153-155` pins the strings
`movement_read.make_read(store.milestone_moves, store.data_for)` in `__main__.py` and `"/api/movement": movement_route` in `server.py`, so
neither line may be edited; `test_movement_never_published.py:155-181` names the publishing modules and `Store.publish_inputs`, none of
which are touched; the hostile and fixtures files build a `LocalServer` through the publish rig, so `setup=None` must be the default and
change nothing. `test_server_movement.py:149-151` says `reach.py` and `platform.py` never contain "movement": the pointer function added
to `platform.py` (if the owner agrees) must not say it.

## 9. The guarded-reader checklist (two readers, never the builder)

**Reader one, the server and the page's trust (a HIGH here blocks):**
- [ ] `SetupHandler` reads no table but the two setup tables; `GET_ROUTES`/`POST_ROUTES` are unedited (diff shows none).
- [ ] The server is built with no seams; `setup_mode.py` imports no `store`, `changes`, `publish*`, `excel*`, `docx_*`, `updater`.
- [ ] Every setup POST runs `authorised()` before anything, and the folder POST cannot open a dialog without the token, a local Host,
      a same-origin `Origin` and a non-cross-site fetch (probe each, as `test_server.py:211-300`).
- [ ] No setup request carries a path, a command or a setting; the chosen folder comes only from the dialog and is checked in the order
      of section 5 before anything is written.
- [ ] Nothing but the pointer file is written, nowhere inside a refused folder; the log is outside the data folder.
- [ ] The six open files and `/csp-report` are not served; `with_boot` is the only place the token is put in a page, and it is not
      in any reply that is not HTML.
- [ ] `/health` does not gain a key; the setup server cannot be mistaken for another clark's data (`this_data` uses the mark).

**Reader two, the launcher and the person's data (a HIGH here blocks):**
- [ ] The normal start is unchanged: with every check passing, `launch()` makes the same calls in the same order (`:165-198`).
- [ ] Only the four hooks of section 6 start setup; the port-taken, lock and did-not-start paths still say their lines.
- [ ] Setup never opens the store, takes the data lock (`platform.hold_data_lock`) or creates the refused folder; "done" starts the
      normal clark only after re-running every required check.
- [ ] The idle stop: a setup page that is open is kept alive; one that is closed stops within a minute and leaves no process.
- [ ] A second double-click while setup is open reaches the existing window (`ours`), not "another copy", and not a second setup.
- [ ] The pointer is re-validated at every read; a missing, unreadable or refused one falls back to the default and is never fatal.
- [ ] A person with data in the refused folder is told (owner's words) that choosing a folder starts a new one; nothing is deleted
      or moved. The five movement tests, `test_server.py`, `test_launcher*`, `test_idle`, `test_launch_e2e`, `test_no_real_names` pass.

## Open questions for the owner (recommendation first)

1. **Remember the chosen folder?** Recommend yes: a one-line file beside the default folder, read only by the launcher (section 6).
   Without it the person chooses again at every launch. It needs a function in `platform.py` (not on the guarded list).
2. **The "port is taken" case on the next free port?** The prototype's table says setup opens there. Recommend no, for now: nothing on
   the page can fix it, and a second port is a second address, with a second token and its own installed-app identity (`launch.py:64-66`).
   The dialog or line stays.
3. **Data already in the refused folder.** Recommend: leave it, say so in words, move nothing in this step. Moving a database is a
   restore/backup job (`backup.restore_into`, design-622) and would put the store back into setup mode's reach.
4. **Which checks block "done".** Recommend: the doctor's `required` ones (`doctor.py:185-193`): Python, data folder, OneDrive,
   nothing in the way; the advice ones (Chrome, the clark folder, Claude Code) never block.
5. **`do_POST` parametrised (one line in the normal `Handler`) or copied.** Recommend parametrised, with the differential test
   listed anyway. The copy is longer but leaves the normal handler untouched.
6. **Reused words that are wrong on a page.** `doctor.py:125-130` ends with Terminal steps ("open Terminal, type cd ... `--data`") and
   `launch.py:91` says "Terminal window"; the page needs app versions (`NEW-WORDS.md` items 5 and 9). Until the owner approves them
   step 5 cannot ship the OneDrive case, only step 4's stand-in page.
7. **NEW strings this note implies, none yet written into code:** the folder dialog's prompt (for example "Choose a folder for your clark
   data"), and, from `NEW-WORDS.md`, items 8 to 12 (heading, "Check again", status labels, setup-mode notice, "Everything is ready.
   Opening clark."). Each is marked NEW in the code with a comment until approved.
8. **Step 3 first.** Recommend building the doctor-as-data split (the prototype's step 3) before this one; otherwise `setup_mode.py`
   must call `doctor.run_check` over `doctor.CHECKS` (`:185-193`, which have names but no stable ids) and map names to ids itself.
