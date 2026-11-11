# Row 836: clark.app, the slices after slice 1 (plan, 08-11-2026)

Slice 1 (doctor and data folder, Quit from the app) ships in 1.0.6. This is 1.0.7 work, built locally. Facts are from origin/main and
the open branches named below; nothing marked GUARDED is changed here.

## Built here (not guarded, testable on Linux)
- `dev/tools/build_app.sh`: builds clark.app with osacompile on a Mac, hidden launcher run, dialog with the launcher's own lines on
  failure. Only existing words are used. `tests/test_build_app.py` runs it with a fake `uname` and `osacompile`.

## Already built elsewhere (do not redo)
- Setup service (checks as data, folder answer checked, pointer file): PR 1183, branch the setup-service branch.
- Chrome tab instead of a new window, and the words notes: the prototype app branch (touches `launch.py` and `platform.py`: GUARDED,
  so it needs the guarded-area readers, not this row's builder).

## GUARDED: planned, not built
1. `server.py`: `SetupHandler`, `SETUP_GET_ROUTES` / `SETUP_POST_ROUTES`, `setup=None` on `LocalServer` and `serve()`
   (design-836-setup-mode.md sections 1 to 5). Two critical readers.
2. `launch.py`: `start_setup` and the four hooks of section 6 of the same note, and the `setup=` seam.
3. `src/clark/setup_mode.py` `main()` entry (`python3 -m clark.setup_mode`) waits on 1 (it calls `serve(setup=...)`).
4. Packaging: `package.py`, `release_files.py`, `same_version.mixed`, the update's list of entries to leave alone (clark.app sits beside
   clark.command, outside `.app`), a macOS CI step that runs `build_app.sh`.
5. `clark.command` no-prompt switch, or move its recovery into `launch.py`.

## Mac only: cannot be tested on this box
App Translocation (programs inside the bundle, or ask once for the folder), Gatekeeper Open Anyway, a Mac without the Command Line
Tools, real osacompile output, Chrome-tab behaviour, signing and notarising (money: the owner's decision). The step list is in
TRANSLOCATION-PLAN.md on the prototype app branch.

## Words the owner must give
The applet reuses only the Python-version lines of clark.command. The launcher's lines that say "close this window" or
"double-click clark.command again" are wrong for an app; the tests that pin them change with the owner's new words, not before.
