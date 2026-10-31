# Design note: #57 a download per system (Mac now, Windows ready to follow)

Written by a teammate (a teammate), 29-10-2026, for the Head. A note only: no code is in this branch. Read from `origin/main` `fc7f0fb`: `src/clark/platform.py`, `src/clark/__main__.py`, `src/clark/launch.py`, `clark.command`, the `clark/` stand-in, `.gitattributes`, `tests/test_layout.py`, `docs/handoff/design-71-launcher.md` and `docs/handoff/portability-and-sharing.md`.

## The answer
- **Build the Mac zip now, and the Windows zip later from the same command.** `python3 dev/tools/package.py mac` makes `clark-<version>-mac.zip`; `package.py windows` is written later and adds a pinned Python. One list of files says what goes in both.
- **The Mac zip is the clark folder as it is today, cut down:** `clark.command`, the `clark/` stand-in, `src/clark/`, the runtime parts of `vendor/`, `README.md` and the licences. It uses the Mac's own Python, as now.
- **The Windows zip is the same folder, plus Python's official embeddable package** (one pinned version, its SHA-256 checked at build) and `clark.cmd`.
- **A doctor** (`python3 -m clark.doctor`, opened from the launcher with `--doctor`) checks Python, the data folder, the browser and the Claude command, and says what to do in plain words.
- **Five small Mac changes keep Windows open** (below). None touches a guarded file.
- The owner's ruling (28-10-2026): "start with mac we can follow with windows but ensure when we build for mac we make allowances for the future". So steps 1 to 5 are for now, and steps 6 to 9 wait until Windows is scheduled.

## What the Mac download holds now, and how it starts
There is no download yet: a person gets the whole repo folder. It starts like this (#71, #90):
1. Double-click `clark.command`. It goes to its own folder, checks `python3` is 3.9 or newer (if not, it explains the Command Line Tools and stops), then runs `python3 -m clark.launch`.
2. The `clark/` stand-in puts `src/` on the path and hands over to `src/clark/launch.py`.
3. The launcher picks the port (`--port`, `CLARK_PORT`, or 8766) and the data folder (`--data`, or `platform.data_dir()` = `~/Library/Application Support/clark/`). It refuses a folder inside OneDrive.
4. It asks `/health` who is on the port. If nothing is there, it starts `sys.executable -m clark --data … --port …` in the background (`platform.start_detached`, with `PYTHONPATH=src` and its output in `server.log` in the data folder), and waits up to 15 seconds.
5. It opens a Chrome app window (`platform.find_chrome`, `open_app_window`), or the default browser if Chrome isn't found.

What is Mac only today, each raising `NotBuiltYet` on Windows: `data_dir`, `onedrive_roots`, `never_read_places`, `open_file`, `reveal_file`, `open_url`, the two dialogs, `launcher_name`, `find_chrome`, `start_detached` and `open_app_window`. `safe_name`, `replace_file` and `write_file` already apply Windows' rules on every system. There is no doctor yet.

**What the Mac zip will hold** (the list lives in `package.py`, and the test reads it):

| In | Out |
|---|---|
| `clark.command` (with its run bit), `clark/`, `src/clark/` (with the built `page.html`), `vendor/openpyxl`, `vendor/et_xmlfile`, `vendor/fonts`, `vendor/licenses`, `vendor/manifest.json`, `README.md`, a short `START-HERE.txt` | `tests/`, `dev/` (but see open question 3), `docs/`, `system/`, `vendor/preact`, `vendor/tiptap` (page build only), `.git*`, any `__pycache__`, `.DS_Store`, `*.db`, `*.log` |

The zip has one top folder, `clark-<version>/`, so unzipping never spills files into Downloads. The run bit is written into the zip entry, so Finder's unzip keeps it.

## What the Windows download will hold (later)
- The same files, with `clark.cmd` in place of `clark.command`.
- `python\`: Python's embeddable package for Windows x64 (`python-3.X.Y-embed-amd64.zip` from python.org). It is about 10 MB, needs no installer, and is signed by the Python Software Foundation. Windows on Arm runs the x64 build, so one Windows zip is enough to start with.
- **Pinning.** `package.py` holds one line, `WINDOWS_PYTHON = ("3.X.Y", "<sha256>")`. The build takes the zip from a local cache folder (it never downloads during a test) and refuses to go on if the SHA-256 differs: "The Python file clark needs isn't the one expected. Download it again." (Reworded at the project lead's review of PR #80.) The pinned hash is worked out once, when the pin changes, from a copy checked against python.org's release signature, and that commit says so. I recommend the newest bugfix release of the newest Python line inside the tested range (3.9 to 3.15).
- **The `._pth` file.** The embeddable Python ignores `PYTHONPATH` and the current folder, and reads its path from `python3X._pth` instead. So the build writes that file with `python3X.zip`, `.`, `..\src` and `..\vendor` in it. The launcher's `PYTHONPATH=src` is then ignored on Windows, which is fine. This is the one real difference, and the test checks the file.
- **`clark.cmd`** (CRLF line endings, kept by `.gitattributes`): `@echo off`, go to its own folder with `cd /d "%~dp0"` (quoted, so a OneDrive path with spaces works), run `python\python.exe -m clark.launch %*`, and wait for a key if it fails, as `clark.command` does. The launcher then starts the server with **`pythonw.exe`**, so no console window stays open while clark runs. The short-lived window that shows the launcher's lines is the same as the Mac's Terminal window (open question 1).
- No Python check is needed in `clark.cmd`: Python is in the zip.

## The build command, and its test
- `python3 dev/tools/package.py mac|windows [--out FOLDER]` builds one zip for that system into `dist/` (git-ignored). It is standard library only (`zipfile`, `hashlib`) and runs on any system, so a Mac can build the Windows zip.
- Before it packs anything it checks that `page.html` is up to date (the `build_page.py` check) and that the tree has no uncommitted changes, unless `--dirty` is given.
- `tests/test_package.py` (quick tier; no network, no Chrome):
  - builds the Mac zip into a temporary folder and checks every name against the list: nothing from the "out" column, one top folder, `clark.command` with its run bit, no `__pycache__`;
  - unzips it and runs `python3 -m clark --help` from the unzipped folder, so a missing file shows up;
  - checks the pin has the right shape (a version and 64 hex characters) and that a cache zip with the wrong hash is refused, using a small fake zip;
  - when Windows is built: checks `python\pythonw.exe`, the `._pth` lines, and that `clark.cmd` is CRLF inside the zip.

## The doctor
`python3 -m clark.doctor`, and `clark.command --doctor` (later `clark.cmd --doctor`). The launcher's "didn't start" line also says to run it. Every check is a small function that returns "ok" or one plain line saying what to do. The system calls stay in `platform.py`.

| Check | When it fails, it says |
|---|---|
| Python is 3.9 or newer, and has SQLite | "This Mac's Python is too old for clark. Type `xcode-select --install` in Terminal, then start clark again." (On Windows: "The Python inside clark's folder is missing. Download clark again.") |
| The data folder can be made and written, and isn't inside OneDrive | "Your clark data can't be saved in ~/Library/Application Support/clark. Check you can save files there." / the OneDrive line `check_data_dir` already gives |
| clark's own folder is inside OneDrive | Not a fault: "Your clark folder is in OneDrive. In Finder, set it to 'Always keep on this device' so its files are always there." |
| The browser: Chrome found, or not | "Chrome wasn't found, so clark will open in your usual browser. Install Chrome to give clark its own window." |
| Something else is on the port | The launcher's own lines (`launch.report`) |
| Claude Code (only if ask clark is on) | "Claude Code wasn't found, so ask clark can't run. The rest of clark works without it. To use ask clark, install Claude Code, then start clark again." (On Windows, a `.cmd` or `.bat` is refused, as a teammate's note says: "The copy of Claude Code on this computer can't be used safely by ask clark. Install Claude Code's own app (claude.exe), then start clark again.") |

It ends with "Everything clark needs is ready." or a count of what to fix. The paths it shows use `with_tilde`, so no account name is shown. Its words follow the product rules: "clark" in lower case, never at the start of a line.

## Mac choices that keep Windows open (do these now)
1. **One file list, two systems.** `package.py` has one list of shared files and a short list for each system, so Windows adds `clark.cmd` and `python\` and nothing else changes.
2. **The background Python comes from `platform.py`.** Add `platform.background_python()`, which gives `sys.executable` on the Mac and `pythonw.exe` beside it on Windows. `launch.py` uses it in place of `sys.executable`.
3. **The command a person types comes from `platform.py`.** `launch.try_another` and the offline page write `./clark.command`. Make a `platform.launcher_command(options)` function that gives `./clark.command --port 8767` on the Mac and `clark.cmd --port 8767` on Windows.
4. **`with_tilde` and other paths.** `with_tilde` joins with "/". Make it use `os.sep` and `Path` so it works for `C:\Users\…`. Keep every path a `Path` and every program an argument list (already true), and never `shell=True`.
5. **`vendor/` on the path in one place.** `excel.py` expects "whoever starts clark" to put `vendor/` on `sys.path`, and nothing does yet. Do it once in the `clark/` stand-in, beside `src/`. Windows does the same through `._pth`.

Already in place, and kept: the data folder only from `platform.data_dir()` (Windows: `%LOCALAPPDATA%\clark\`); OneDrive refused for the database; `safe_name` and the 260-character limit on every system; `replace_file` with retry; LF line endings, with `*.cmd` kept as CRLF. Add **`*.bat text eol=crlf`** to `.gitattributes`, and a line in `test_layout` for it. Also set `sys.dont_write_bytecode = True` in the stand-in, so a clark folder on OneDrive isn't kept busy with `__pycache__`, as a teammate's note asks. No new bash-only tricks go into `clark.command`: it stays a short wrapper, and every decision is made in Python, which both systems share.

## Hand checks
**On a Mac, now:** unzip the download from Safari (so it is quarantined), then first start: what Gatekeeper asks (on recent macOS a Control-click and Open may not be enough, and the person may need System Settings, Privacy & Security, Open Anyway); the run bit is kept; it starts from a folder whose path has spaces; and the doctor on a Mac without the Command Line Tools.

**On Windows 11, later:**
1. Download and unzip into Downloads, then double-click `clark.cmd`: SmartScreen ("Windows protected your PC", More info, Run anyway), and the exact words for the how-to.
2. First start: the window opens in Chrome, or in Edge if Chrome isn't there; no console window stays open.
3. From a OneDrive folder with spaces, for example `C:\Users\demo\OneDrive - Example Ltd\clark`: it starts, the data still goes to `%LOCALAPPDATA%\clark`, and the doctor gives the "Always keep on this device" line.
4. A company laptop: whether AppLocker or Defender blocks `pythonw.exe` run from a user folder.
5. Run it again with clark open: only the window opens. Close the window: clark stops a minute later.

## Risks
- **Gatekeeper and SmartScreen** make the first start a few extra clicks, and neither `clark.command` nor `clark.cmd` is signed. Signing is a later item; the how-to and `START-HERE.txt` must show the clicks.
- **The run bit is lost** when the folder goes through email, Teams or some OneDrive copies. `bash clark.command` is the fallback in `START-HERE.txt`.
- **Company policy** may block Python run from a user folder on Windows. Only IT can answer that (a teammate's open question 5).
- **The `._pth` file** hides `PYTHONPATH`. If it is wrong, clark doesn't start on Windows. The test checks it.
- **No console with `pythonw.exe`:** anything the server prints is lost, so its errors must go to `server.log`, as they already do.
- **An old pin:** a Python security fix means a new pin. It is a one-line change, with the hash checked.
- **The Mac's Python is Apple's 3.9,** the oldest we support. When Apple moves on, the test range has to follow.

## Build steps (each a small item of its own)
| # | Step | Size | When |
|---|---|---|---|
| 1 | `.gitattributes` `*.bat` line, `test_layout` line, `sys.dont_write_bytecode` and `vendor/` on the path in the stand-in | XS | now |
| 2 | `platform.background_python()`, `launcher_command()`, `with_tilde` with `os.sep`; launch and offline page use them; tests | S | now |
| 3 | `dev/tools/package.py mac`, the file list, `dist/` git-ignored, `START-HERE.txt`; `tests/test_package.py` for the Mac zip | S | now |
| 4 | `clark.doctor` with the checks above, `--doctor` in `clark.command`, the launcher's pointer to it; tests with fakes | M | now |
| 5 | Mac hand check from a downloaded zip; the how-to gains "Get clark" | XS | now |
| 6 | Windows branch of `platform.py`: `data_dir`, `onedrive_roots`, `find_chrome` (Chrome then Edge), `start_detached` (`DETACHED_PROCESS`), `open_url`, `launcher_name`, `never_read_places` | M | later |
| 7 | `package.py windows`: the pin, the cache, the hash check, `._pth`, `clark.cmd`; its tests | S | later |
| 8 | The doctor's Windows lines; the system dialogs on Windows (their own item) | S | later |
| 9 | Windows 11 hand checks; the Windows test lane (on hold, decision 2) | S | later |

## Open questions for the Head (recommendation first)
1. **`clark.cmd` runs `python.exe` for the launcher and `pythonw.exe` for the server.** The issue says `clark.cmd` starts `pythonw.exe` with no console. A `.cmd` always opens a console when double-clicked, and with no console the launcher's messages (port taken, didn't start) would not be seen. Recommend: the console shows the launcher's lines and closes on success, and the server runs under `pythonw.exe`. A message box from `platform.py` is the other way. Amend the Done-when?
2. **Mac stays on the system Python** (as decided in #71, open question 5). Shipping a Python in the Mac zip as well is a bigger item. Keep that?
3. **`--demo` in the download.** It needs `dev/demo_data.py`. Recommend: put that one file in the zip, so a person can try clark with fictional data; otherwise drop `--demo` from the download's help.
4. **Who cuts a release zip, and where it is kept.** Recommend: the Head runs `package.py` at the release tag and attaches the zip to the release. Nothing is built in CI until the billing limit is fixed.
5. **The doctor's place:** `--doctor` on the launcher (one file to double-click) as well as `python3 -m clark.doctor`. Recommend both.
