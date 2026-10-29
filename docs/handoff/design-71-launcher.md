# Design note: #71 Launcher and clark as a Chrome app (guarded: it changes the server's policy and routes)

Written by a teammate, 28-10-2026. Required before the server change (`Team/01`). Read from: issue #71 and its readiness check and builder's note (a teammate, comments of 15:16 and 15:50); creaite release tag **v2.6.9 (`db5adb2`)** `system/scripts/launch.py`, `live_server.py`, `system/templates/app/{sw.js,offline.html}` (read from the tag; nothing in creaite is edited); clark `origin/main` `6cef420` (`server.py`, `platform.py`, `__main__.py`, `page/__init__.py`, `publish.py`); PR #41's `server.py` diff. Review: **Full, two independent reviewers** (one reads the code, one tests from outside), never the builder. The owner approves the exact `server.py` diff and the one guard test it changes. The issue's Done-when is a draft: where this note differs, the differences are in "Open questions".

## What is built now, and what waits
Built, pure and not wired (no change to `server.py`, `page.html` or the page's source): `src/clark/appfiles.py` (manifest, offline page, worker, the list of open files, the data mark, `/health`'s answer to it), `src/clark/app/{sw.js,offline.html}`, `src/clark/idle.py` (the idle stop), `src/clark/launch.py` (port check, start, open), `platform.py`'s new section (find Chrome, start detached, open an app window, the launcher's name), `clark.command`, and `clark/launch.py` (the stand-in, so `python3 -m clark.launch` works from the top folder as `python3 -m clark` does). Their tests are in `tests/test_app_files.py`, `test_idle.py`, `test_launcher.py` and `test_app_browser.py`.
Waits for the Head and the owner: the `server.py` change (routes, policy, `/api/here`, the mark on `/health`, the watcher), the guard-test change it needs, and the page's side (manifest link, theme colour, registering, heartbeat), which belongs after #41.

## What I ran in headless Chrome (so the CSP claims are tested, not argued)
- With today's policy, `navigator.serviceWorker.register("/sw.js")` is refused: "The provided scriptURL ... violates the Content Security Policy". A worker script falls back worker-src, then child-src, then script-src, and script-src is hashes only. So `worker-src` is needed.
- With `worker-src 'self'` added, and `/sw.js` sent with its own `default-src 'none'; connect-src 'self'`: it registers and activates, takes over the page on the next load, `caches.keys()` is `["clark-offline-v1"]` and the cache holds only `/offline`, `/csp-report` hears nothing, `Page.getAppManifest` reads the manifest with no errors, and **`Page.getInstallabilityErrors` is empty** (Chrome offers Install). A link added by script works the same as one in the HTML.
- With the server stopped, a page load shows the offline page; Check again says "Still not running." while it is stopped and goes back to clark once the server is back on the same port.
- Chrome opens spare connections before it needs them; a test that "stops the server" must also drop the connections it has accepted, or a thread keeps answering. `tests/test_app_browser.py` does.

## 1. Routes (`server.py`)
**Open, no token, GET only.** One table, `OPEN_FILES`, read once from `appfiles.open_files()`. In `do_GET` it is checked **after** the Host check and after `/health` and `/`, **before** `GET_ROUTES`. The match is by exact path with the query dropped (so `?v=` on an icon works); nothing builds a file path from a request, so there is no traversal.

| Path | Returns | Content-Type | Also |
|---|---|---|---|
| `/manifest.webmanifest` | the manifest (`appfiles.manifest_json`) | `application/manifest+json` | |
| `/sw.js` | the worker script | `text/javascript` | `Content-Security-Policy: default-src 'none'; connect-src 'self'` (the worker may fetch from clark and load nothing else) |
| `/offline` | the offline page | `text/html` | the normal page policy, from `send()`: its one style and one script are hashed |
| `/app/icon-192.png`, `/app/icon-512.png`, `/app/icon-maskable-512.png` | #73's PNGs, from `src/clark/page/assets/` (one copy, not three) | `image/png` | |

- **Why no token:** a browser fetches a manifest, a worker script and an icon with no custom header, so it cannot send `X-Clark-Token`. Each is fixed bytes with no data in it and no token (a test checks the token is in none). What they tell a stranger is that a clark is on this port, which `/health` already says. The Host check still applies (a rebinding page gets 403).
- **Everything else:** `/app/anything-else`, `/offline/`, `/sw.js/`, `/app/../health`, `/OFFLINE` give 404 with the existing error body. A POST to these is not a route (the token check comes first, as for any POST); OPTIONS is 403 as everywhere.
- **Headers:** every reply already carries `no-store` and the four security headers (from `end_headers`). `no-store` on `/sw.js` is what we want (the browser always asks for the worker again); on the manifest and icons it costs a few small fetches. `send()` adds `; charset=utf-8` to every type, including `image/png`. It is harmless and creaite did the same; fixing it is one line in `send()` and I recommend leaving it.
- **Scope rules:** the worker is served from `/sw.js`, so its scope is `/` and cannot be wider: **no `Service-Worker-Allowed` header** (creaite sent one; not needed). The manifest has `id`, `start_url` and `scope` all `/`.

**New, token-checked:** `POST /api/here` in `POST_ROUTES` (so the one dispatcher's token, Origin, 415, 411 and 400 checks apply). It sets the "last seen" time and answers `{"ok": true}`. Set as `POST_ROUTES["/api/here"] = here_route` in the new block, not inside the dict literal #41 edits. Opening `/` also counts as "here". `/health` and the open routes do not. It is added to the quiet routes so the log has no line every 10 seconds. This is how the idle stop is detected **without a new open route**: only a page that has the token can say it is open.

**`/health`:** a plain call still gets exactly `{"ok": true}` (guard test 8 stays unchanged). With the header `X-Clark-Data: <mark>` it adds `"this_data": true|false` (`appfiles.health_answer`). The mark is the first 16 hex of the SHA-256 of the resolved data folder (`appfiles.data_mark`); `__main__` gives it to the server with `server.set_data_mark(mark)` (a module setting, so `serve()`'s signature, which #41 changes, is untouched). A web page cannot send this header without a preflight, and every preflight is refused.

## 2. The policy, exactly
One line in `csp_policy`, after `script-src`:
```
"default-src 'self'", f"script-src {scripts}", "worker-src 'self'",
```
- **`manifest-src`: no change.** It falls back to `default-src 'self'` (the manifest loaded in the run above).
- **Must not allow:** `'self'` in `script-src` (the page is hashes only; `/sw.js` can be a worker but not a `<script>`); `blob:` or `data:` in `worker-src`; any outside address; `child-src`. The existing test that no outside source is allowed stays.
- **Why `worker-src 'self'` is safe:** it lets a page ask for a worker from this address. A worker must be JavaScript, `nosniff` is on, and the only JavaScript clark sends is `/sw.js`: every other path (JSON, HTML, the manifest, an image) is refused (`test_no_route_but_the_worker_script_can_be_started_as_a_worker`). And a page that could inject script is already stopped by the hashes.
- **The worker's own policy:** `default-src 'none'; connect-src 'self'` on `/sw.js` (above), so even a changed worker could reach nothing but clark.
- **Guard test that must change (the owner's approval, `Team/04`):** `tests/test_server.py:270`, `self.assertNotIn("worker-src", policy)`, becomes `self.assertIn("worker-src 'self'", policy)`, with `assertNotIn("blob:", ...)` and the other assertions beside it kept. Test 9 (one `live_server.py` row at v2.6.9) stays: this branch extends that one row instead of adding a second.

## 3. The page's side (not `server.py`; after #41)
A small module in the page's source, run only when the `clark-boot` data block is there (the live page; never the published file):
- adds `<link rel="manifest" href="/manifest.webmanifest">` and `<meta name="theme-color">`, and calls `navigator.serviceWorker.register("/sw.js")`;
- sets the theme colour from `--brand-navy` (the top bar, which the app window's title bar takes on) in Light and Dark, and again when the person changes it;
- sends `POST /api/here` with the token every `idle.HEARTBEAT` (10) seconds, and once when the page becomes visible.
**Why not in `page.html`:** the publish scan rejects any `<link` except the three icon links, and the published file is what a client opens. A link added by script, with the registering code inert there (no token, and a file cannot register a worker), keeps the published bytes as they are. **Do not hand-edit or hand-merge `page.html`:** #41 changes `boot.jsx`, `main.jsx` and `page.html`, so this is built after it and rebuilt with `dev/tools/build_page.py`.

## 4. The launcher (`clark.command`, `launch.py`)
**Form: `clark.command`**, a shell script in the top folder beside `README.md` and `src/`. It needs no build, no signing and no extra file, and runs from a downloaded folder. A small `.app` would need either signing or Gatekeeper's "damaged" warning, and is a later item. Costs: the first run of a downloaded file is right-click, Open (Gatekeeper, as `portability-and-sharing.md` says); the executable bit must survive the download; Terminal leaves its window open after it. `bash clark.command` works without the bit.
**What it runs:** `cd` to its own folder, check `python3` is 3.9 or newer, then `python3 -m clark.launch "$@"`. If not, it says (and runs nothing): "clark needs Python 3.9 or newer, and this Mac doesn't have it yet. Apple's free Command Line Tools include it. If a window just asked to install them, choose Install. Otherwise open Terminal, type: xcode-select --install. When that has finished, double-click clark.command again." A Mac without the tools has a `python3` stub that opens that Apple window; the check treats a stub and a too-old Python the same. It installs and downloads nothing (a test reads the script).
**`launch.py`** (logic only; every system call is in `platform.py`):
1. Port: `--port`, else `CLARK_PORT`, else 8766 (`__main__.port_number`, so one validator). Data folder: `--data`, else `platform.data_dir()`, refused inside OneDrive, made if missing (the log goes in it).
2. **Port check:** `GET /health` on 127.0.0.1 with `X-Clark-Data: <mark>`, 1 second, no proxy. No new open route, nothing taken over:

| Answer | Meaning | What the launcher does |
|---|---|---|
| connection refused | nothing there | starts clark, waits up to 15 s |
| `{"ok": true, "this_data": true}` | clark, our data folder | says "clark is already running on port N.", opens the window |
| `this_data` false | clark, another data folder | "Port N is in use by clark with a different data folder (this one uses FOLDER). Close that clark and start this one again, or use another port, for example: ./clark.command --port M." Starts and opens nothing. |
| anything else that answers or holds the port: `{"ok": true}` with no mark (creaite), HTML, 403, not JSON, over 4 KB, no answer in time | not clark | "Port N is in use by another program. Close that program and start clark again, or use another port, for example: ./clark.command --port M." Starts and opens nothing. |

   Creaite counts a missing mark as ours; clark counts it as **not ours**.
3. **Start:** `[python, "-m", "clark", "--data", FOLDER, "--port", N]`, `CLARK_LAUNCHED=1`, `CLARK_PORT=N`, `PYTHONPATH=src`, a session of its own (it outlives the Terminal window), output added to `FOLDER/server.log` (started again if over 1 MB). It waits for `this_data: true`. If the process has gone, one last look (a second launch that won the port counts); if it never answers: "clark didn't start: LAST LOG LINE. The log is in FOLDER/server.log." (clark's own start-up lines are already plain words, `#90`.)
4. **Open:** `http://127.0.0.1:N/` always (Chrome offers Install only from a loopback address). Chrome found (`CLARK_BROWSER`, else `/Applications`, else `~/Applications`): `[chrome, "--app=URL"]`. Not found: the default browser, and "Chrome wasn't found, so clark opened in your default browser: URL. Install Chrome to give clark its own window." Edge is left for later.
5. **Idle stop:** a server the launcher started stops when nothing has said "still here" for **60 seconds**, never while a job runs (`idle.Idle`, a monotonic clock, so a change of the computer's clock cannot stop it; the Mac's monotonic clock should not run during sleep, which a hand check confirms: close the lid for two minutes with a window open). In `serve`, when `idle.launched(environ)`, a daemon thread runs `Idle.watch(httpd.shutdown, busy)` every 5 s. **Busy** = a counter of POST routes mid-run, added in `run_route`, so a later Publish or Import is covered without remembering to register it. A server started by hand, or by a sign-in agent, never stops. Until the server step lands, a launcher-started server simply does not stop by itself.

## 5. The offline page (exact words)
Title and heading: **clark isn't running**. Body: "clark's window needs clark to be running on this computer. Double-click **clark.command** in your clark folder, or open Terminal in that folder and type:" then `./clark.command`. "clark stops by itself a minute after its last window closes. Nothing is lost when it stops: your data stays on this computer." Button **Check again**; if clark isn't there: "Still not running."; if it is: it goes to clark. No "server", no port, no path. The launcher's name comes from `platform.launcher_name()` (Windows: `clark.cmd`, #57). Its colours are clark's tokens (a test checks each), light and dark by the system setting; it loads nothing.

## 6. Tests per Done-when line
| Done-when | Test | State |
|---|---|---|
| Double-clickable launcher | `test_launcher.Command` (executable, runs from its own folder, passes options and exit code, missing or old Python says what to do); `RunsFromTheTopFolder` (the real `python3`, no `PYTHONPATH`) | built |
| Starts clark if nothing answers; another data folder reported, never taken over | `PortCheck` (fake servers: ours, another folder, creaite's `{"ok": true}`, HTML, 403, not JSON, too big, silent, nothing, not HTTP), `Launch`, `Wait`, `AgainstAFakeServer` | built |
| Stops a minute after the last page closes | `test_idle` (fake clock, busy job, real short run); with the server: `test_idle_stop`, `test_idle_stop_waits_for_a_running_post`, `test_hand_started_server_never_stops`, `test_here_needs_the_token` | logic built; server tests wait |
| Manifest: name, standalone, theme, icons 192, 512, maskable, sizes true, byte-identical to #73 | `test_app_files.Manifest`, `OpenFiles`; served: `test_manifest_and_icons_are_served` in `test_server.py` | content built; served waits |
| Theme colour follows the page | a browser test at 1400 and 900 px (Light, Dark, System) | waits for the page |
| Service worker; offline page says clark isn't running, with the start command and Check again | `test_app_files.ServiceWorker`, `OfflinePage`; `test_app_browser` (registers under the policy, `/csp-report` silent, only `/offline` cached, offline at 1400 and 900 px light and dark, Check again returns) | built, with routes of its own until the server serves them |
| Chrome offers Install | `test_app_browser`: `Page.getInstallabilityErrors` is empty | built |
| `--app=` window, or the default browser | `test_launcher.Launch`, `PlatformCalls` (a stub browser; no real Chrome) | built |
| Works from a download with nothing installed | `TheStartFilesNameNoOutsideAddress` (launcher, manifest, worker, offline page), `Command.test_it_installs_and_downloads_nothing`, `RunsFromTheTopFolder` | built |
| Only the open routes answer without the token | in `test_server.py`: `test_open_routes_are_exactly_these` (set equality with the six; each 200 with no token; wrong Host 403; `/app/x`, `/app/../health`, `/offline/` 404; each header once), `test_open_routes_are_fixed_bytes`, `test_policy_has_worker_src_self_and_nothing_outside`, `test_health_mark_only_when_asked`; #33's token test, which reads `GET_ROUTES` and `POST_ROUTES`, checks `/api/here` for free and stays unchanged | waits |
| Mac code only in `platform.py` | `test_platform_source` unchanged and green; `PlatformCalls.test_every_windows_branch_is_not_built_yet` | built |
| The copies are recorded | `test_app_files.TheCopiesAreRecorded` | built |

## 7. What is Mac only, and what Windows needs from `platform.py`
Mac only today, each with an `on=` argument and `NotBuiltYet` on Windows: `launcher_name()` (`clark.command`), `find_chrome()`, `start_detached()` (`start_new_session`), `open_app_window()`. `launch.py`, `idle.py` and `appfiles.py` hold no system call (the source test proves it). For Windows (#57): `launcher_name` gives `clark.cmd`, which runs the bundled `pythonw.exe -m clark.launch`; `find_chrome` also looks for Edge and the `Program Files` paths; `start_detached` uses `DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP`; `data_mark` already uses `os.path.normcase`; the offline page's `./` becomes `.\`. Nothing else changes.

## 8. How this meets PR #41 (still open; it also changes `server.py`, `platform.py`, `page.html`)
Built so far touches none of #41's hunks: new files, one appended section of `platform.py`, one extended row in the reuse record. The later `server.py` change is made as one new block (the open files, `here_route`, the mark, the watcher), plus one-line edits in `csp_policy`, `do_GET`, `run_route` and `serve`; it adds `/api/here` with its own statement and leaves `POST_ROUTES`, `ROUTE_BODY_LIMITS`, `LocalServer.__init__` and `serve()`'s signature, which #41 edits, alone. `/api/here` inherits #41's stricter `authorised()` (Origin must be this Host), which the page's own same-origin POST meets.

## Open questions for the Head and the owner (recommendation first)
1. **Six open routes, not two.** The draft Done-when says the manifest and the offline page. A browser also fetches the worker and the icons with no token. Recommend: the six above, in their own table, GET only, Host-checked, fixed bytes; amend the Done-when. *Security.*
2. **Approve `worker-src 'self'` and the one-line change to the guard test** (`tests/test_server.py:270`). Recommend yes. *The owner.*
3. **How the launcher recognises its own data folder.** Recommend the mark on `/health` (a guarded change, test 8 untouched). The other way is a file in the data folder naming the pid and port; it cannot tell "another clark" from "another program" and a stale file can mislead, so I do not recommend it. *The owner.*
4. **The idle stop's detection.** Recommend the 10-second heartbeat (creaite's, proven). Risk: Chrome slows a hidden window's timers to about one a minute after five minutes, which could pass the 60 s limit under an open but hidden window (nothing is lost; the offline page recovers it). A hand check (minimise for six minutes) decides; if it fails, make the limit 120 s and the words "two minutes", or hold an open request instead of timers. Keep 60 s for now?
5. **A fresh Mac with no Python.** The docs decided the system `python3` (Apple's Command Line Tools) with a plain message (`portability-and-sharing.md`); `#90` has the same assumption. So "nothing installed from the internet" holds for clark's own code but a Mac without those tools has to install Apple's. Recommend: accept for 0.3; shipping a Python in the Mac download is a bigger item, like Windows'. Does the Head accept that reading?
6. **Where the launcher lives in the download, and who makes the download.** Here: the top folder, beside `README.md`, `src/` and the `clark/` stand-in, so the download is the whole folder. A zip made by Finder or `git archive` keeps the executable bit; a copy through OneDrive, Teams or email may not, so `bash clark.command` is the fallback to say in the how-to. Is there a release zip, and does its build check the bit?
7. **`clark.command` only in 0.3,** a small app (with the icon, in `~/Applications`) later. Recommend yes. Terminal's window stays open after the launcher ends; acceptable?
8. **Light-mode title bar:** navy like the top bar (recommended) or the page's grey. *The owner.*
9. **Port 8766 is also the default of a creaite development checkout.** A worker and manifest belong to an address and port, so two apps that both use 127.0.0.1:8766 in one Chrome profile replace each other's worker, and each deletes the other's offline cache. The port check handles two running at once; it does not handle this. Keep 8766, or give clark its own default?
10. **Who builds the page side, and when:** after #41 (it changes `boot.jsx`, `main.jsx` and `page.html`). Recommend a teammate, as its own small commit with a rebuilt `page.html`.
11. **The window opens `/`,** not `#dashboard&p=CODE` as `#90`'s `--open` does (that needs the store). Recommend the page chooses a default project and the launcher stays free of the store. Confirm.
12. **Optional hardening, beyond #71:** `Cross-Origin-Resource-Policy: same-origin` on every reply would stop another site probing whether clark is on a port with an image or script tag. Recommend as its own small guarded change.
13. **"Start clark when you sign in"** (scope added to #71, 28-10-2026) is not designed here: it needs a Settings switch and a launch-agent function in `platform.py` (create, remove, status), and a server it starts is not `CLARK_LAUNCHED`, so it never stops by itself. Recommend its own item, after this one.
