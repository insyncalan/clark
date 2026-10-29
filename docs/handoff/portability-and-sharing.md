# Mac first, built ready for Windows, and clark on OneDrive

Written by a teammate, 28-10-2026, after the owner's two asks:
- "how do we tackle portability to mac and windows? I think it's an important part of mvp"
- "clark will most likely sit on a one drive folder and multiple users will edit... we'll need to address database issues (future feature - start with single user for mvp/beta)"

**The owner's decisions, 28-10-2026:**
1. "start with mac we can follow with windows but ensure when we build for mac we make allowances for the future"
2. The Windows test machine and CI: "hold"
3. Dialogs: "systems own dialog"
4. Several users (C then A, never a shared `clark.db` on OneDrive): "agreed... this is a backlog item si low priority for now"
5. The data model points: "agreed with recommendations"

So the MVP ships on **Mac only**, with **the allowances below built in from day one**, so Windows is a port of one module and a package, not a rewrite. The Windows parts of this note (the package, Credential Manager, Windows testing) are kept for when Windows is scheduled.

## The allowances, built in the Mac MVP
These cost little now and are the difference between a port and a rewrite. Each one is pinned by a test that runs on the Mac.
- **One platform module.** Everything system-specific lives in `src/clark/platform.py`: the data folder, OneDrive roots, open and reveal, the Save and folder dialogs, file replace with retry, and the key store choice. Only the Mac branch is written. Each function has a Windows branch that raises "not built yet". A source test bans `osascript`, `ctypes`, `open -R`, `~/Library` and `subprocess` outside `platform.py` and the runner.
- **Windows-safe file names on the Mac too.** `safe_name()` applies Windows' rules to every file clark makes: no `< > : " / \ | ? *`, no `CON`, `NUL` or `COM1` names, no trailing dot or space, and short paths. SharePoint refuses most of the same characters, so this also protects To client today.
- **Text is always UTF-8.** Every `open()` names `encoding="utf-8"` (a source test).
- **Paths only through `pathlib`,** never a hard-coded `/` or a home-folder path outside `platform.py`.
- **Programs are started from an argument list, never `shell=True`,** and a `.cmd` or `.bat` is refused. That matters on Windows, and is good hygiene on the Mac.
- **Files are replaced through one function** (temporary file, then `os.replace`, with a short retry), because Windows and OneDrive lock open files.
- **AI keys go through one `KeyStore` interface** (#54). The Mac Keychain is the only store built. Any other system answers "not connected".
- **The database's place comes from `platform.data_dir()`,** and is never in OneDrive (Part 2).
- **Python 3.9 standard library only,** so the Windows embeddable Python can run the same code later.
- **`.gitattributes` keeps LF line endings,** so a later Windows checkout doesn't rewrite files.

The sections below on Windows describe the later port.

## Part 1: Mac and Windows (Windows is the later port)

### What already works on both
- **Python's standard library**, which is all clark uses: SQLite, `http.server`, `ctypes`, `webbrowser`, `pathlib`, `hashlib` and `zipfile`.
- **The vendored libraries:** openpyxl and pypdf.
- **The page:** one self-contained HTML bundle that runs in any current browser.
- **The Word templates.**

So clark is one code base with a thin platform layer, not two apps.

### What differs, and how clark handles each
| Area | Mac | Windows | How clark does it |
|---|---|---|---|
| **Python** | `/usr/bin/python3` (3.9) comes with the Command Line Tools, as creaite relies on | Not installed by default, and corporate laptops often can't install it | **Windows:** ship Python's official *embeddable package* (a zip from python.org, PSF licence, about 10 MB, no installer) inside clark's Windows download, pinned to a version with its SHA-256. **Mac:** the system Python, as creaite; clark's doctor says how to install the Command Line Tools if it's missing |
| **Starting clark** | A double-click `clark.command` | A double-click `clark.cmd` that runs the bundled `pythonw.exe` (no console window) | Both start the same `python -m clark`. Neither sets clark to start at log-in in the MVP |
| **Opening the page** | `webbrowser.open` | `webbrowser.open` | The same code on both |
| **Opening a file or showing it in its folder** | `open` and `open -R`, as creaite's `live_server.py` does | `os.startfile`, and `explorer /select,` | One function in `src/clark/platform.py`. creaite's calls are replaced when copied |
| **Folder and Save dialogs** ("as a standard save dialog") | `osascript` "choose folder" and "choose file name" | `comdlg32` and the shell's folder picker through `ctypes` | Both live in `platform.py` behind one function, so no other module calls `osascript` or `ctypes`. **Open point 3** |
| **Where data lives** | `~/Library/Application Support/clark/` | `%LOCALAPPDATA%\clark\` | `platform.data_dir()`. Never inside the app folder, and never inside OneDrive (Part 2) |
| **The OneDrive folder** (To client, client changes, source folders) | `~/Library/CloudStorage/OneDrive-<Org>/` | `%OneDriveCommercial%`, or `%OneDrive%` | `platform.onedrive_roots()`. It only suggests folders; the user still picks them |
| **AI keys (#54)** | Keychain, through the Security framework with `ctypes` | Credential Manager, through `advapi32` with `ctypes` | One `KeyStore` interface with two stores. Windows comes into the MVP |
| **Running the Claude command (ask clark)** | `claude` | `claude.exe` from Claude Code's native Windows install | Found with `shutil.which` and started with an argument list, never `shell=True`. **A `.cmd` or `.bat` file is refused,** because Windows passes its arguments through `cmd.exe`, which can turn text in an argument into a command. Whether the native install is always an `.exe` is **to verify** on a Windows machine |
| **Text and files** | UTF-8 | The default code page is cp1252, not UTF-8 | Every `open()` names `encoding="utf-8"`, and `newline=""` for CSV. A source test fails on an `open()` without an encoding |
| **File names** | Few limits | No `< > : " / \ \| ? *`, no `CON`, `NUL` or `COM1` names, no trailing dot or space, and a 260-character path limit by default | One `safe_name()` for every file clark makes, with a test of each rule. Published paths are kept short |
| **Replacing a file** | `os.replace` | `os.replace` fails while another program has the file open (OneDrive, antivirus, Word) | Write to a temporary file and replace it, with a short retry and backoff. A real failure says which file is locked |
| **Browser for the tests** | Chrome | Edge, which every Windows machine has, and which takes the same DevTools pipe | The real-time test runner looks for Chrome, then Edge, on each system |
| **Line endings in the repo** | | | `.gitattributes`: `* text=auto eol=lf`, with `*.cmd` and `*.bat` kept as `crlf` |

### Testing on Windows
- **The rule:** each item's tests run on macOS and Windows before review. That's added to "How to run v0.1".
- **Where Windows runs:**
  1. **GitHub Actions**, with `windows-latest` and `macos-latest` in a matrix, once the billing limit is fixed (decision #58, D-10). This is the real answer. creaite's CI runs on Ubuntu only, so clark is the first to need a Windows runner.
  2. **Until then,** a Windows 11 virtual machine on a team Mac (UTM or Parallels, Windows on Arm, Python for Arm64) for the runner and hand checks.
  3. **Not a Linux machine:** the two boxes are Arm Linux, and a Linux host doesn't offer Windows images.
- **Hand checks on a real Windows laptop** before the beta: the save dialog, Credential Manager, a OneDrive path with spaces, SmartScreen on first start, and what a company laptop's policy blocks.

### Risks on company laptops (ask IT before the beta)
- **Running Python from a user folder:** AppLocker or Defender policies may block an unsigned script or a Python run from the Downloads folder. The embeddable `python.exe` is signed by the PSF, but `clark.cmd` isn't.
- **Gatekeeper:** a downloaded `clark.command` is quarantined on a Mac, so the first start needs right-click > Open. Signing and notarising is a later step.

### Backlog changes (for the project lead)
- **#28 (repo and runner):** Mac only. `.gitattributes` is added now. The Edge fallback and the Windows lane come with the port.
- **#56 "Platform layer": stays in the MVP,** Mac branch only, with the allowances above and their source tests. The native Save and folder dialogs are its Mac `osascript` branch ("systems own dialog"). Size M, Light.
- **#57 "Windows package": moves to later,** with the Windows branch of `platform.py`, Credential Manager and the Windows test lane.
- **#54:** the Windows Credential Manager store moves back to later. The `KeyStore` interface stays.
- **CI (#58): on hold** ("hold"). Tests run locally on the Mac.

## Part 2: clark and OneDrive

### The MVP rule: the database never sits in a synced folder
SQLite's own guidance is not to use a database file on a network or synced file system. OneDrive is worse than a network drive:
- It uploads whatever is on disk when it sees a change, which can be part-way through a write. SQLite's `-wal` and `-shm` files are uploaded separately from the main file.
- It has no file locks, so two machines can both write.
- A clash becomes a second file such as `clark-LAPTOP-2.db`, and nobody merges it.
- "Files On-Demand" can turn a file into an online-only placeholder that isn't on the disk at all.

So in the MVP and the beta:
- **`clark.db` lives in `platform.data_dir()`,** on the machine's own disk. If a chosen data folder turns out to be inside OneDrive, clark refuses it and explains why (a test with a fake OneDrive root).
- **Backups do go to OneDrive.** Each day, and before every import, clark makes a finished copy with SQLite's backup API and writes it as one file into a OneDrive folder the user picks: written to a temporary name, then renamed. A whole file appearing at once is safe to sync. Restore copies a backup back to the data folder. This gives the owner's "on OneDrive" for safety without the risks.
- **Everything else can sit on OneDrive:**
  - Published reports and Excel exports.
  - The client's SharePoint folder (To client and client changes).
  - The source folders, which clark only reads.
- **The app's own files can sit on OneDrive too,** if that's how a team shares the download. clark then:
  - writes no `__pycache__` beside its code (`sys.dont_write_bytecode = True`), so OneDrive isn't kept busy;
  - asks the user to set the clark folder to "Always keep on this device";
  - never writes anything else into its own folder.

### Several users editing the same project (backlog, low priority: the owner, 28-10-2026)
Choices for later, in order of preference:

| Option | How it works | For | Against |
|---|---|---|---|
| **A. A small shared service** | One server holds the database, on company hosting. Each person's clark talks to it, and the page is the same | Real shared editing, one history, one undo, and clark's one-writer rule still holds | Hosting, a company sign-in (Entra ID), a security review, and a step away from "everything on your own machine" |
| **B. One copy each, sharing changes through OneDrive** | Each user keeps their own `clark.db` and writes their steps as change files into a shared OneDrive folder. Each clark reads the others' files and applies them | No server, works offline, and reuses the client changes mechanism (option A in `client-edits.md`) | Merging clashes, the order of steps, and handing out IDs without two people taking the same `<CODE>-A-NNN`. It's a lot of hard code |
| **C. One editor, others read** | One person owns a project's database and publishes. Others see the published page and send changes as client-style change files | Almost free: it's clark's client edits, used inside the team | Not true shared editing |
| Not this: a shared `clark.db` on OneDrive | | | Corruption and clash copies, for the reasons above |

*My recommendation:* C as soon as a team needs it, since it's nearly built already. Then A if teams need real shared editing. Don't attempt B.

**The owner chose C's shape (28-10-2026):** "each user to be able to 'export' a db file to share with me and then an option for me to be able to import it and it updates / syncs the changes to the master db (mine) before publish. Include option to import multiple". The design is in `team-changes.md`. Each teammate gets a starting copy and exports a changes file. The owner imports one or many into the master, clashes are shown side by side, new items are renumbered, and Publish says when files are waiting. It shares one changes inbox with client edits.

**Done now so that A or C stay cheap:**
- Every write is a step through the one writer (`applies`).
- Each step records `by_user` and `device` (in `data-model.md`), with UTC times.
- No state lives outside `clark.db` apart from settings and keys.
- IDs stay creaite's `<CODE>-A-NNN`. Under A the server hands them out, and under C only the owner does, so neither needs a new ID scheme.

## Decided and still open
1. **Mac first, Windows later, with the allowances built in:** decided.
2. **The Windows test machine and CI:** on hold.
3. **Save and folder dialogs:** each system's own dialog. Decided.
4. **Several users:** C first, then A, never a shared `clark.db` on OneDrive. A low-priority backlog item. Decided.
5. **IT, for when Windows is scheduled:** whether company Windows laptops allow the embeddable Python and an unsigned `clark.cmd` to run from a user folder. Not needed now.
