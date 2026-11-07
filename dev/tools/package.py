"""Build the download for one system: one zip, clark-<version>-<system>.zip, that unzips to one folder, clark/, with the program
files in its hidden .app/ folder (issue 694; #57, step 3 of docs/handoff/packaging-57.md).

Run: python3 dev/tools/package.py mac [--out FOLDER] [--dirty] [--release] [--notes FILE] [--extra-folder PATH]...   # writes dist/clark-<version>-mac.zip
     python3 dev/tools/package.py mac --for-client                # in a checkout of the scrubbed public snapshot only
     python3 dev/tools/package.py windows                         # not built yet (steps 6 and 7 of the note)

Who the zip is for is decided by the tree it is built from, not by a flag (#463). If git tracks any private-only file in
it (any path publish_public.is_excluded names: the notes in EXCLUDED and docs/public/), it is the private copy, and the zip
is for the team only: its files may still carry the team's names in comments and README.md may be the private one. If
git tracks none, the tree holds none of the team's private notes, it is what the public repository holds, and the zip
may be published there. The Built line and START-HERE.txt say which, and nothing else: they never claim the files are
scrubbed. If git cannot say, the zip is for the team only. A zip for a client is built with --for-client, which refuses, and writes nothing, unless (1) this folder is the scrubbed
public snapshot that dev/tools/publish_public.py makes (#94; see snapshot_problem for how that is told) and (2) the name
guard finds nothing in any file going into the zip, START-HERE.txt included. The name guard is the one the publish tool
runs: its own list of the team's and private names (publish_public.guard_kinds) and the hashed list of real client
names in tests/test_no_real_names.py. Nothing here keeps a second list. A refusal names the files, never the names.

What goes in is the one list below: SHARED for every system, plus the short list for each system in SYSTEMS. A folder in
the list means the files git tracks under it, so nothing untracked (a database, a log, __pycache__) can slip in, and
LEFT_OUT drops those even if one is ever tracked. START-HERE.txt is written from START_HERE.

clark-release.json (#109) is written here from the same files it zips: product, version, system, the date of the
last commit, notes, the data layout number (store.SCHEMA_VERSION), min_from, and each file's SHA-256, size and mode. --release
refuses a .dev version. It is how an update is checked; it proves the download is whole, not who made it.

The zip is repeatable: the same files give the same bytes. Every entry has the same fixed time and its mode set by hand
(clark.command keeps its run bit, so Finder's unzip leaves it double-clickable), and the entries are sorted.

It refuses to build from uncommitted changes to the listed files unless --dirty is given. Standard library and git only;
nothing is downloaded.
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DIST = ROOT / "dist"

if str(Path(__file__).resolve().parents[2] / "src") not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from clark.release_files import (EXTRA_TOP, INCLUDE_DEMO, MANIFEST, NOT_BUILT_YET, RUN_BIT, SHARED, START_HERE, START_HERE_NAMES, SYSTEMS, TOP,  # noqa: E402,F401
                                 ZIP_README, place, protected, source, unplace)

# The one list of what the download holds is src/clark/release_files.py (shipped, so the updater reads the same list).


def listed(system):
    """The list for `system`: SHARED plus its own files (read here, from the names imported above)."""
    return SHARED + SYSTEMS[system]


# The two generated pages (#495): never committed, so git cannot list them. They are built here, from the sources at the tag,
# and put in the zip by name. A tree without src/clark/page/src (a test's scratch repo) has none.
GENERATED_PAGES = ("src/clark/page/page.html", "src/clark/page/page-view.html")
BUILD_PAGE = Path("dev") / "tools" / "build_page.py"


def generated_pages(root=ROOT):
    return list(GENERATED_PAGES) if (Path(root) / "src" / "clark" / "page" / "src").is_dir() else []


def make_pages(root=ROOT, twice=False):
    """Build both pages from the sources in `root` (python3 dev/tools/build_page.py) and refuse if either is missing after.
    With `twice` (a release) it builds again and refuses if the second pair differs from the first by a single byte."""
    root = Path(root)
    names = generated_pages(root)
    if not names:
        return
    script = root / BUILD_PAGE

    def run():
        if script.is_file():
            done = subprocess.run([sys.executable, str(script)], cwd=str(root), capture_output=True, text=True)
            if done.returncode != 0:
                raise Refused("The pages could not be built, so nothing was written: "
                              + (done.stderr.strip().splitlines() or done.stdout.strip().splitlines() or ["no reason given"])[-1])
        missing = [n for n in names if not (root / n).is_file()]
        if missing:
            raise Refused(f"A page the download needs has not been built: {', '.join(missing)}. Run python3 dev/tools/build_page.py, "
                          "then build again. Nothing was written.")
        return {n: hashlib.sha256((root / n).read_bytes()).hexdigest() for n in names}

    first = run()
    if twice and script.is_file() and run() != first:
        raise Refused("Two builds of the pages gave different bytes, so this release is refused. Nothing was written.")


LEFT_OUT = re.compile(r"(^|/)(__pycache__|\.DS_Store)(/|\Z)|\.(pyc|db|log)\Z")

TEAM_ONLY = "This download is for the team only; it is built from the private copy."
PUBLIC_BUILD = "This download holds none of the team's private notes."

FIXED_TIME = (2000, 1, 1, 0, 0, 0)  # every entry's time, so two builds are byte for byte the same
UNIX = 3                            # ZipInfo.create_system: the modes below are Unix modes
FILE_MODE = 0o100644
RUN_MODE = 0o100755

START_HERE_MAC = """\
Getting started on a Mac

These steps are for a Mac.

What is in this folder: README.md says what clark is. START-HERE.txt is this
page. Double-click clark.command to start clark. docker is for starting clark
with Docker. system/branding holds your own logo and colours, if you add them.
The program files are in a hidden folder called .app: you do not need to open
it.

If your Mac will not open clark.command (a work Mac often will not), or you
already use Docker, use Docker instead. You only need Docker and Chrome.
  1. Open Docker Desktop and wait until it says it is running.
  2. Open Terminal, type cd and a space, drag this folder into the Terminal
     window and press Return.
  3. Type this and press Return (the first time it takes a few minutes):
        docker compose -f docker/compose.yaml up -d
  4. Open Chrome and go to http://localhost:8766
     To keep clark as its own app, choose the Install clark button at the
     right end of Chrome's address bar. Open it from there on later days.
  5. To stop clark, type this in the same folder and press Return:
        docker compose -f docker/compose.yaml down
Use the clark download, not a copy of the source code: a copy of the source
has no built page, and Docker stops with a message saying so.
Start Docker from the clark folder.
To see what Docker has said, type this in the same folder:
        docker compose -f docker/compose.yaml logs --tail 50
With Docker, your data is kept in ~/Library/Application Support/clark, the same
place clark.command uses, not in this folder, so you can swap this folder for a
newer download without losing anything. To use another folder, put its full
path in CLARK_DATA_DIR in front of the command in step 3:
        CLARK_DATA_DIR="/full/path" docker compose -f docker/compose.yaml up -d
A folder inside OneDrive cannot be used by clark.
If an earlier Docker start kept your data in a data folder inside the clark
folder, move that data folder out of the clark folder first, or name it
with CLARK_DATA_DIR.
By default clark.command and Docker use the same data.
IMPORTANT: Never open the same data from clark.command and from Docker at the
same time: stop one before you start the other.
To use another port, put it in front of the command, for example:
        CLARK_PORT=8800 docker compose -f docker/compose.yaml up -d
then open http://localhost:8800 instead.
If it says port 8766 is already used, another clark is open: close it, or stop
it with the command in step 5, then try again. If it says it cannot connect to
Docker, Docker Desktop is not running yet.

If you already have clark:
  1. Close clark.
  2. Rename your old clark folder (for example to clark-old) or move it away,
     so the two folders do not clash.
  3. Unzip this download.
  4. If you added your own logo or colours, copy the system/branding folder
     from the old clark folder into the new one. An update never changes that
     folder, but replacing the whole clark folder by hand removes it.
  5. If you use Docker and your data is in a data folder inside the old clark
     folder, move that data folder out of it before you delete the old folder,
     or start Docker with CLARK_DATA_DIR naming it.
  6. Double-click clark.command. Your Mac may ask you to confirm clark.command
     again: do as in step 2 under "Without Docker" below.
Your projects are not in the old clark folder: they stay in
~/Library/Application Support/clark. Updating from inside clark is switched off,
so install this version by hand.

Without Docker:

1. Double-click clark.command in this folder.

2. The first time, your Mac may say it could not verify clark.command and
   offer only Move to Trash and Done. This is expected, not a fault. Do not
   choose Move to Trash: choose Done. Then open System Settings, choose
   Privacy & Security, scroll down and choose Open Anyway beside clark.command,
   then double-click it again. On a computer your employer manages, Open Anyway
   may ask for an administrator's password, and your employer may not allow it.
   If you cannot get past it, use the typed way below, which needs no password.

3. A Terminal window starts clark, then its window opens in Chrome
   (or in your usual browser if Chrome isn't there).

4. After a while with no window open, clark stops by itself. To use it again,
   double-click the file again.

Double-clicking while clark is open just opens another window.

If it says nothing was started because clark is already open in another
Terminal window, or another program is using the connection it needs, close
that Terminal window or program, then double-click clark.command again.

If you can't close it, the message also gives a line to type in Terminal that
starts clark on a different connection. Type it as shown and press Return. If
that does not work either, run the check described below: it says what to fix.

The typed way: open Terminal, type cd and a space, drag this folder into the
Terminal window and press Return. Then type:
   bash clark.command
and press Return. Use this too if double-clicking does nothing.

If your Mac is missing something it needs, clark.command says how to get it.

To check what your Mac needs for clark, open Terminal, type cd and a space,
drag this folder into the Terminal window and press Return. Then type:
   bash clark.command --check
and press Return. It says what is ready and what to fix.

Without Docker, your data is kept in ~/Library/Application Support/clark, not in
this folder, so you can swap this folder for a newer download without losing anything.
"""

START_HERE_DEMO = """
To try it with made-up data first, open Terminal, type cd and a space,
drag this folder into the Terminal window and press Return. Then type:
   bash clark.command --demo --open
and press Return. Nothing you do there is kept.
"""


class Refused(Exception):
    """A plain one-line reason the zip can't be built."""


def version(root=ROOT):
    """The version in src/clark/__init__.py, read as text so this tool never imports clark."""
    text = (Path(root) / "src" / "clark" / "__init__.py").read_text(encoding="utf-8")
    found = re.search(r'^__version__ = "([^"]+)"', text, re.M)
    if not found:
        raise Refused("The version can't be found in src/clark/__init__.py.")
    return found.group(1)


def tracked(root, paths):
    out = subprocess.run(["git", "-C", str(root), "ls-files", "-z", "--", *paths], capture_output=True, check=True).stdout
    return [p for p in out.decode("utf-8").split("\0") if p]


def zip_source(name, root=ROOT):
    """The repo file the zip's `name` is read from: docs/zip/README.md for README.md (release_files.source). Every build refuses
    to go on without it (build() says so in plain words), so the repository's own README.md can never be shipped by mistake."""
    return source(name)


def files(system, root=ROOT):
    """The repo files that go in the zip for `system`, sorted (START-HERE.txt is not one: it is written here)."""
    chosen, kept = set(), set()
    for item in listed(system):
        found = tracked(root, [item]) if item.endswith("/") else [item]
        if not found or not all((Path(root) / zip_source(p, root)).is_file() for p in found):
            raise Refused(f"A file the download needs is missing: {item}. Restore it, then build again.")
        kept.update(p for p in found if protected(p))
        chosen.update(p for p in found if not LEFT_OUT.search(p))
    if kept:
        raise Refused(f"The download must never hold the person's own folders (system, data), and git tracks files in them: "
                      f"{', '.join(sorted(kept))}. Nothing was written. Untrack them, then build again.")
    if "src/clark/" in listed(system):
        for p in generated_pages(root):
            if not (Path(root) / p).is_file():
                raise Refused(f"A page the download needs has not been built: {p}. Run python3 dev/tools/build_page.py, then build again.")
            chosen.add(p)
    return sorted(chosen)


# issue 716: one sentence for each extra folder a download carries; said in START-HERE only when the folder is in the zip.
EXTRA_SENTENCES = {"intake": "intake holds a sample workbook with made-up data, in the same layout clark exports.",
                   "meet clark": "meet clark holds an overview and a getting-started guide as PDFs."}


def with_extra_folders(text, names):
    """`text` (START-HERE) with a sentence about each extra folder in `names` added to "What is in this folder", the paragraph
    wrapped again so that no line starts with the product name."""
    import re
    import textwrap
    head, found, rest = text.partition("What is in this folder:")
    para, blank, tail = rest.partition("\n\n")
    if not found or "system/branding holds" not in para:
        raise Refused("START-HERE has no 'What is in this folder' paragraph to add the extra folders to.")
    flat = " ".join(para.split()).replace("system/branding holds", " ".join(EXTRA_SENTENCES[n] for n in names) + " system/branding holds", 1)
    glued = re.sub(r" (clark)", "\x00\\1", "What is in this folder: " + flat, flags=re.I)
    return head + textwrap.fill(glued, width=78, break_on_hyphens=False).replace("\x00", " ") + blank + tail


def start_here(system, for_client=False, root=ROOT, extra=()):
    text = START_HERE_MAC + (START_HERE_DEMO if INCLUDE_DEMO else "")
    names = [n for n in EXTRA_SENTENCES if n in extra]       # intake first, then meet clark
    if names:
        text = with_extra_folders(text, names)
    return text if for_client else f"{audience(root)}\n\n{text}"


def publish_tool():
    """dev/tools/publish_public.py of this checkout: the scrub's own name guard and the snapshot's own constants."""
    here = str(Path(__file__).resolve().parent)
    if here not in sys.path:
        sys.path.insert(0, here)
    import publish_public
    return publish_public


def private_paths(root):
    """The paths git tracks in `root` that only the private copy holds (publish_public.is_excluded); None when git
    cannot say, which the caller treats as private."""
    pub = publish_tool()
    try:
        return [p for p in tracked(root, []) if pub.is_excluded(p)]
    except (subprocess.CalledProcessError, OSError):
        return None


def audience(root=ROOT):
    """The audience line of a default build (not --for-client): TEAM_ONLY if `root` tracks any private-only path, or if
    git cannot say; else PUBLIC_BUILD. The Built line, START-HERE.txt and the tests all read it from here."""
    found = private_paths(root)
    return TEAM_ONLY if found is None or found else PUBLIC_BUILD


def snapshot_problem(root):
    """None when `root` is the scrubbed public snapshot; else a plain reason it isn't.

    publish_public.py writes no marker file, so the signal is what the snapshot is made of. Two things are checked, and
    both must hold:
    - none of the private-only files is tracked: the notes in EXCLUDED and docs/public/ (the public README's source,
      which the snapshot puts in place of README.md and then leaves out). Every private checkout tracks
      docs/public/README.md (the publish tool refuses without it), and no snapshot can (the tool checks it is gone);
    - the last commit is by the tool's own neutral author and committer (AUTHOR_NAME, AUTHOR_EMAIL), as every snapshot
      commit is, and no commit in the private repo is.
    A remote's address was not chosen: a copy of either repo can have any remote, or none, and the address says
    nothing about the files themselves. The constants are read from the tool, so a change there changes this too."""
    pub = publish_tool()
    private = private_paths(root)
    if private is None:
        return "git could not list this folder's files, so it can't be told from the private copy"
    if private:
        return "this folder is the private copy: it holds the team's own notes that the public snapshot leaves out"
    log = subprocess.run(["git", "-C", str(root), "log", "-1", "--format=%an%n%ae%n%cn%n%ce"],
                         capture_output=True, text=True)
    neutral = [pub.AUTHOR_NAME, pub.AUTHOR_EMAIL] * 2
    if log.returncode != 0 or log.stdout.splitlines() != neutral:
        return "its last commit was not made by the publish tool, so it isn't a public snapshot"
    return None


def name_guard_hits(content, banned=None):
    """The paths in `content` ({path in the repo: bytes}) where the name guard finds a name. A path that itself holds a
    name is never shown: it is counted instead. Never the name."""
    pub = publish_tool()
    guard = pub.load_guard()
    banned = guard.BANNED if banned is None else banned
    shown, hidden = [], 0
    for path, data in sorted(content.items()):
        if pub.guard_kinds("", path.encode("utf-8", "surrogateescape")) or guard.name_banned(path, banned):
            hidden += 1
            continue
        hit = bool(pub.guard_kinds(path, data))
        if not hit and data[:2] == b"PK":
            hit = bool(pub.zip_findings(data, "", 1, [pub.MAX_ZIP_BYTES], lambda part: pub.guard_kinds("", part), True))
        if not hit and not guard.SKIP.search(path):
            text = guard.text_of(data)
            hit = text is not None and bool(guard.text_hits("", text, banned))
            for _, name, part in guard.parts(data):
                hit = hit or part is None or guard.name_banned(name, banned) or (
                    guard.text_of(part) is not None and bool(guard.text_hits("", guard.text_of(part), banned)))
        if hit:
            shown.append(path)
    return shown, hidden


def schema_version(root=ROOT):
    """SCHEMA_VERSION in src/clark/store.py, read as text so this tool never imports the store."""
    text = (Path(root) / "src" / "clark" / "store.py").read_text(encoding="utf-8")
    found = re.search(r"^SCHEMA_VERSION = ([0-9]+)", text, re.M)
    if not found:
        raise Refused("The data layout number can't be found in src/clark/store.py.")
    return int(found.group(1))


def released_on(root=ROOT):
    """The date of the last commit, YYYY-MM-DD, so two builds of the same commit are byte for byte the same."""
    out = subprocess.run(["git", "-C", str(root), "log", "-1", "--format=%cs"], capture_output=True, text=True)
    day = out.stdout.strip()
    return day if out.returncode == 0 and re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", day) else datetime.date.today().isoformat()


def manifest_bytes(system, content, top, root=ROOT, released=None, notes="", min_from="0.0.0"):
    """clark-release.json: what the updater checks a download against, written from the very `content` that is zipped
    (so the two can't drift). `content` is {name in the zip: (bytes, mode)}. Each file has its SHA-256, size and mode
    (644 or 755), keyed by its name without the top folder. The manifest does not list itself."""
    files = {}
    for name in sorted(content):
        data, mode = content[name]
        files[name[len(top) + 1:]] = {"sha256": hashlib.sha256(data).hexdigest(), "size": len(data),
                                       "mode": format(mode & 0o777, "o")}
    doc = {"product": "clark", "version": version(root), "system": system,
           "released": released or released_on(root), "notes": notes,
           "schema_version": schema_version(root), "min_from": min_from, "files": files}
    return (json.dumps(doc, indent=2, sort_keys=True) + "\n").encode("utf-8")


def top_folder(root=ROOT):
    """The one folder the zip unzips to: always `clark`, whatever the version (issue 694)."""
    return TOP


def zip_name(system, root=ROOT):
    """The zip file keeps its version: clark-<version>-<system>.zip."""
    return f"clark-{version(root)}-{system}.zip"


COMPOSE = "docker/compose.yaml"
COMPOSE_WORKDIR = "    working_dir: /clark\n"
COMPOSE_WORKDIR_HIDDEN = "    working_dir: /clark/.app\n"


def compose_for_zip(data):
    """The compose file as the zip holds it: the program files sit in .app, so the container starts there. Exactly one
    `working_dir: /clark` line is changed (the bind of the whole folder stays, so system/branding is still seen);
    anything else about it is refused, so a changed compose file never ships half-changed."""
    text = data.decode("utf-8")
    lines = [ln for ln in text.splitlines(keepends=True) if ln.rstrip("\r\n") == COMPOSE_WORKDIR.rstrip("\n")]
    if len(lines) != 1:
        raise Refused(f"{COMPOSE} must hold exactly one line '{COMPOSE_WORKDIR.strip()}' for the download to change, and it holds "
                      f"{len(lines)}. Nothing was written. Fix the compose file or this tool, then build again.")
    ending = lines[0][len(lines[0].rstrip("\r\n")):]
    return text.replace(lines[0], COMPOSE_WORKDIR_HIDDEN.rstrip("\n") + ending).encode("utf-8")


def placed_bytes(name, data):
    """The bytes the zip holds for the repo file `name`: the file itself, except the compose file."""
    return compose_for_zip(data) if name == COMPOSE else data


# --- extra folders (issue 716) ----------------------------------------------------------------------------------------
# Folders that are not in git (written at build time) go at the top of the clark folder under their own names. At most
# EXTRA_MAX_BYTES of files in all of them; regular files only; a link anywhere refuses the build.
EXTRA_MAX_BYTES = 5 * 1024 * 1024
RESERVED_TOP = (".app", "README.md", *START_HERE_NAMES, MANIFEST, "clark.command", "clark.cmd", "docker", "system", "data", "clark")


def extra_name(path):
    """The top-level name an extra folder takes in the zip: its own name. A plain Refused if that can't be a safe name."""
    text = str(path)
    name = os.path.basename(os.path.abspath(text))
    if not name or name.startswith(".") or "/" in name or "\\" in name or ".." in name or text.rstrip("/\\").endswith(".."):
        raise Refused(f"The extra folder {text!r} has a name that can't be used (empty, starts with a dot, or holds "
                      "a separator or ..). Nothing was written.")
    if name.casefold() in [r.casefold() for r in RESERVED_TOP]:
        raise Refused(f"The extra folder name {name!r} is one clark uses itself. Nothing was written. Rename the folder.")
    if name not in EXTRA_TOP:
        raise Refused(f"The extra folder name {name!r} is not one a download may carry ({', '.join(EXTRA_TOP)}). "
                      "Nothing was written. Rename the folder or add the name to EXTRA_TOP in src/clark/release_files.py.")
    return name


def extra_content(folders):
    """{name below the top folder: bytes} for every file in the extra `folders`, or Refused. Never follows a link."""
    from clark import updates
    out, seen, total = {}, set(), 0
    for folder in folders:
        name = extra_name(folder)
        if name.casefold() in seen:
            raise Refused(f"The extra folder {name!r} is given twice. Nothing was written.")
        seen.add(name.casefold())
        base = Path(os.path.abspath(str(folder)))
        try:
            st = os.lstat(base)
        except OSError:
            raise Refused(f"The extra folder {str(folder)!r} does not exist. Nothing was written.")
        if stat.S_ISLNK(st.st_mode) or not stat.S_ISDIR(st.st_mode):
            raise Refused(f"The extra folder {str(folder)!r} is not a folder (a link or a file does not count). Nothing was written.")
        found, stack = [], [base]
        while stack:
            here = stack.pop()
            try:
                children = sorted(os.scandir(here), key=lambda e: e.name)
            except OSError:
                raise Refused(f"The extra folder {name!r} can't be read. Nothing was written.")
            for e in children:
                rel = Path(e.path).relative_to(base).as_posix()
                if e.name.startswith(".") and e.name != ".DS_Store":
                    raise Refused(f"The extra folder {name!r} holds a hidden file or folder: {rel}. Nothing was written. "
                                  "Take it out of the folder; a download carries no hidden files.")
                info = os.lstat(e.path)
                if stat.S_ISLNK(info.st_mode):
                    raise Refused(f"The extra folder {name!r} holds a link: {rel}. Nothing was written. Replace it with a real file.")
                if stat.S_ISDIR(info.st_mode):
                    stack.append(Path(e.path))
                elif not stat.S_ISREG(info.st_mode):
                    raise Refused(f"The extra folder {name!r} holds something that is not a regular file: {rel}. Nothing was written.")
                elif not LEFT_OUT.search(rel):
                    found.append((rel, e.path, info.st_size))
        if not found:
            raise Refused(f"The extra folder {name!r} holds no files. Nothing was written.")
        for rel, path, size in sorted(found):
            total += size
            if total > EXTRA_MAX_BYTES:
                raise Refused(f"The extra folders hold more than {EXTRA_MAX_BYTES // (1024 * 1024)} MB in all, so nothing was written.")
            full = f"{name}/{rel}"
            problem = updates.path_problem(full)
            if problem:
                raise Refused(f"The extra folder {name!r} holds a name that can't go in a download ({problem}): {rel}. Nothing was written.")
            if protected(full):
                raise Refused(f"The extra folder {name!r} would put a file in a folder that belongs to the person. Nothing was written.")
            data = Path(path).read_bytes()
            if len(data) != size:
                raise Refused(f"A file in the extra folder {name!r} changed while it was read: {rel}. Nothing was written.")
            out[full] = data
    clash = updates.collisions(list(out))
    if clash:
        raise Refused("The extra folders hold names that clash on a Mac or Windows disk: " + ", ".join(clash[:5]) + ". Nothing was written.")
    return out


def entries(system, root=ROOT, extra_folders=()):
    """Every name in the zip, in order."""
    top = top_folder(root)
    return sorted([f"{top}/{place(p)}" for p in files(system, root) + [START_HERE]]
                  + [f"{top}/{n}" for n in extra_content(extra_folders)])


def uncommitted(root, paths):
    out = subprocess.run(["git", "-C", str(root), "status", "--porcelain", "--", *paths],
                         capture_output=True, check=True, text=True).stdout
    return out.rstrip()                 # the first line's leading space is part of its status


def tag_problem(root, ver):
    """Why a release zip can't be built from `root`: HEAD is not the commit tagged v<ver>, or git can't say. None when it is.
    The v0.2.1 download was built from a tree that was not its tag (#400)."""
    run = subprocess.run(["git", "-C", str(root), "tag", "--points-at", "HEAD"], capture_output=True, text=True)
    if run.returncode != 0:
        return "git could not say which tag this folder is at"
    if f"v{ver}" not in run.stdout.split():
        return f"this folder is not at the tag v{ver}"
    return None


def changed_files(porcelain):
    """The file names in `git status --porcelain` output (for a rename, the new name)."""
    return [line[3:].split(" -> ")[-1] for line in porcelain.splitlines() if line.strip()]


def entry(name, mode):
    info = zipfile.ZipInfo(name, date_time=FIXED_TIME)
    info.create_system = UNIX
    info.external_attr = mode << 16
    info.compress_type = zipfile.ZIP_DEFLATED
    return info


def build(system, out=DIST, root=ROOT, dirty=False, for_client=False, banned=None, release=False, notes="",
          released=None, min_from="0.0.0", extra_folders=()):
    """Build the zip for `system` into the folder `out`; its path. With `for_client`, only from the scrubbed snapshot
    and only when the name guard finds nothing (`banned` replaces the hashed list, for the tests)."""
    if system in NOT_BUILT_YET:
        raise Refused(f"The {system.capitalize()} download isn't built yet. Only the Mac one is: package.py mac")
    if system not in SYSTEMS:
        raise Refused(f"There is no download for {system!r}. Choose mac.")
    root = Path(root)
    if release and not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version(root)):
        raise Refused(f"Version {version(root)} is not a release number (it must be three numbers, like 0.3.1). "
                      "Nothing was written. Set the version in src/clark/__init__.py, then build again.")
    if release:
        if dirty:
            raise Refused("A release zip is built only from committed files, so --release can't be used with --dirty. "
                          "Nothing was written.")
        problem = tag_problem(root, version(root))
        if problem:
            raise Refused(f"A release zip must be built from its tag, and {problem}. Nothing was written. Check out the tag "
                          f"in an empty folder (dev/RELEASING.md step 5), then build again.")
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", min_from):
        raise Refused("The oldest version that may update to this one must be three numbers, like 0.2.0.")
    if for_client:
        if dirty:
            raise Refused("A zip for a client is built only from committed files, so --for-client can't be used with "
                          "--dirty. Nothing was written.")
        problem = snapshot_problem(root)
        if problem:
            raise Refused(f"A zip for a client must be built from the scrubbed public snapshot, and {problem}. "
                          "Nothing was written. Build it in a checkout of the snapshot that dev/tools/publish_public.py "
                          "makes, or leave out --for-client to build one for the team.")
    if "README.md" in listed(system) and not (root / ZIP_README).is_file():
        raise Refused(f"A release or a client zip carries {ZIP_README} as its README.md, and that file is missing. "
                      "Nothing was written. Restore it, then build again.")
    extra = extra_content(extra_folders)            # before anything is written; a plain Refused if a folder is not fit
    changed = [] if dirty else changed_files(uncommitted(root, [zip_source(p, root) for p in listed(system)]))
    if changed:
        raise Refused(f"Some of the files that go in the zip have changes that aren't committed: {', '.join(changed)}. "
                      "Commit them first, or add --dirty to build from them as they are.")
    if "src/clark/" in listed(system):
        make_pages(root, twice=release)
    names = files(system, root)
    top = top_folder(root)
    content = {f"{top}/{place(p)}": (placed_bytes(p, (root / zip_source(p, root)).read_bytes()), RUN_MODE if p in RUN_BIT else FILE_MODE)
               for p in names}
    content[f"{top}/{place(START_HERE)}"] = (start_here(system, for_client, root, {n.split("/")[0] for n in extra}).encode("utf-8"), FILE_MODE)
    content.update({f"{top}/{n}": (data, FILE_MODE) for n, data in extra.items()})      # issue 716: not in git, so not in `names`
    if for_client:
        shown_paths, hidden = name_guard_hits({unplace(n[len(top) + 1:]): data for n, (data, _) in content.items()}, banned)   # repo names, as the builder knows them
        if shown_paths or hidden:
            where = shown_paths + ([f"{hidden} file(s) whose own name holds one (not shown)"] if hidden else [])
            raise Refused("A zip for a client must hold no one's name, and the name guard found one in: "
                          f"{', '.join(where)}. Nothing was written. Take the name out, then build again.")
    content[f"{top}/{place(MANIFEST)}"] = (manifest_bytes(system, content, top, root, released, notes, min_from), FILE_MODE)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    target = out / zip_name(system, root)
    fd, part = tempfile.mkstemp(dir=str(out), suffix=".part")
    os.close(fd)
    try:
        with zipfile.ZipFile(part, "w") as z:
            for name in sorted(content):
                data, mode = content[name]
                z.writestr(entry(name, mode), data, compresslevel=9)
        os.chmod(part, 0o644)           # mkstemp makes it private; the zip is meant to be shared
        os.replace(part, target)
    finally:
        if os.path.exists(part):
            os.remove(part)
    return target


def shown(path):
    """`path` as the builder reads it: from the repo's top folder when it is inside it, else with ~ for the home folder."""
    path = Path(path).resolve()
    for base, prefix in ((ROOT.resolve(), ""), (Path.home().resolve(), "~/")):
        try:
            return prefix + path.relative_to(base).as_posix()
        except ValueError:
            pass
    return str(path)


def main(argv=None):
    p = argparse.ArgumentParser(prog="package.py", description="Build the clark download for one system.")
    p.add_argument("system", choices=sorted(set(SYSTEMS) | NOT_BUILT_YET), help="which system the download is for")
    p.add_argument("--out", metavar="FOLDER", default=str(DIST), help="where the zip goes (default: dist/)")
    p.add_argument("--dirty", action="store_true", help="build even if the listed files have uncommitted changes")
    p.add_argument("--for-client", action="store_true",
                   help="a zip for a client: only from the scrubbed public snapshot, and only if the name guard finds nothing")
    p.add_argument("--release", action="store_true", help="refuse a version that is not three numbers (a .dev build), a tree not at its tag vX.Y.Z, and --dirty")
    p.add_argument("--notes", metavar="FILE", help="a text file of release notes, kept in clark-release.json")
    p.add_argument("--extra-folder", metavar="PATH", action="append", default=[],
                   help="put this folder's files at the top of the clark folder under the folder's own name "
                        f"({', '.join(EXTRA_TOP)}); repeat for more; at most 5 MB in all; never committed")
    p.add_argument("--min-from", metavar="X.Y.Z", default="0.0.0", help="the oldest version that may update to this one")
    args = p.parse_args(argv)
    try:
        notes = Path(args.notes).read_text(encoding="utf-8") if args.notes else ""
        target = build(args.system, args.out, dirty=args.dirty, for_client=args.for_client, release=args.release,
                       notes=notes, min_from=args.min_from, extra_folders=args.extra_folder)
    except OSError:
        print("The release notes file can't be read. Check its name, then build again.", file=sys.stderr)
        return 1
    except Refused as e:
        print(e, file=sys.stderr)
        return 1
    who = ("It is for a client: it was built from the scrubbed public snapshot and the name guard found nothing."
           if args.for_client else audience(ROOT))
    print(f"Built the {args.system.capitalize()} download: {shown(target)}. {who}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
