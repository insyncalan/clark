# Guarded files: what would need to change (nothing here is changed in the worktree)

## For the browser change (Task A)
- None. platform.py and launch.py are not guarded; tests changed: test_launcher.py, test_launcher_words.py, test_launch_e2e.py.
- docs/handoff/design-71-launcher.md: one phrase changed ("--app=" window now "a plain tab"). Its section 6 table row still reads `--app=` window; update the row when the design note is next edited.

## For the applet (Task C)
- package.py / release_files.py: ship `clark.app`? It is built by dev/tools/build_app.sh on a Mac and must not be committed. If the zip is to carry it, the packaging step must run osacompile (macOS runner only) and add clark.app to the release file list; the zip list, the "mixed versions" manifest and the update's swap step (updates swap `.app`, the hidden folder) must know the new entry, or an update leaves an old clark.app that points at nothing new. A clark.app next to clark.command must also be in the zip's expected top-level names (same_version.mixed, the unknown-entry check of issue 743).
- updates / update_helper.py: the update must keep clark.app in place (it is not inside `.app`), and its compiled applet does not change with a version, so it needs no swap; only the list of entries the update leaves alone.
- ci_scan / workflows: the release workflow needs a macOS job step to run `dev/tools/build_app.sh` before packaging, and the CI scan's file-name rules must allow a `clark.app` folder in the release zip.
- clark.command restore logic (the missing .app/src recovery) is not repeated in the applet: the applet calls the launcher directly. Either the applet runs the same recovery (move it into python, launch.py), or the applet calls `bash clark.command` without its "Press any key" prompts (needs a no-prompt switch in clark.command; clark.command is shipped text).

## For the setup page (Task D)
- server.py: new routes (GET /setup page, GET /api/setup/checks, POST /api/setup/choose-folder, POST /api/setup/done). A "setup mode" in which the server runs before a data folder passes platform.check_data_dir (today the launcher refuses and never starts the server). The Host/token/CSP rules for the new routes (guard tests change: the exact route table in tests that pin it).
- page: a new page file or a route in the page's source (src/clark/page/src), built by build_page.py; its CSP hashes change.
- idle.py: setup mode must count as "here" (the page's heartbeat already does) and must never stop while the page is open.
- appfiles.OPEN_FILES: only if the setup page is served without a token (it should not be: serve it with the same token boot as the main page).
