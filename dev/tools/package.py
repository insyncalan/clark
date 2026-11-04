"""Build the download for one system: one zip with one top folder, clark-<version>/ (#57, step 3 of
docs/handoff/packaging-57.md).

Run: python3 dev/tools/package.py mac [--out FOLDER] [--dirty] [--release] [--notes FILE]   # writes dist/clark-<version>-mac.zip
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
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DIST = ROOT / "dist"

if str(Path(__file__).resolve().parents[2] / "src") not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from clark.release_files import (INCLUDE_DEMO, MANIFEST, NOT_BUILT_YET, RUN_BIT, SHARED, START_HERE, SYSTEMS)  # noqa: E402,F401

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
PUBLIC_BUILD = "This download is built from the public repository; it holds none of the team's private notes."

FIXED_TIME = (2000, 1, 1, 0, 0, 0)  # every entry's time, so two builds are byte for byte the same
UNIX = 3                            # ZipInfo.create_system: the modes below are Unix modes
FILE_MODE = 0o100644
RUN_MODE = 0o100755

START_HERE_MAC = """\
Getting started on a Mac

These steps are for a Mac.

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
To see what Docker has said, type this in the same folder:
        docker compose -f docker/compose.yaml logs --tail 50
With Docker, your data is kept in the data folder beside the clark files, made
at the first start. Keep that data folder when you swap this folder for a newer
download. To use the data clark.command uses instead, type this in step 3:
        CLARK_DATA_DIR="$HOME/Library/Application Support/clark" docker compose -f docker/compose.yaml up -d
To use another folder, put its full path in CLARK_DATA_DIR the same way.
As a rule, clark will not use a folder inside OneDrive.
Never open the same data from clark.command and from Docker at the same time:
stop one before you start the other.
To use another port, put it in front of the command, for example:
        CLARK_PORT=8800 docker compose -f docker/compose.yaml up -d
then open http://localhost:8800 instead.
If it says port 8766 is already used, another clark is open: close it, or stop
it with the command in step 5, then try again. If it says it cannot connect to
Docker, Docker Desktop is not running yet.

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
   python3 -m clark.doctor
and press Return. It says what is ready and what to fix.

Without Docker, your data is kept in ~/Library/Application Support/clark, not in
this folder, so you can swap this folder for a newer download without losing anything.
"""

START_HERE_DEMO = """
To try it with made-up data first, open Terminal, type cd and a space,
drag this folder into the Terminal window and press Return. Then type:
   python3 -m clark --demo --open
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


def files(system, root=ROOT):
    """The repo files that go in the zip for `system`, sorted (START-HERE.txt is not one: it is written here)."""
    chosen = set()
    for item in listed(system):
        found = tracked(root, [item]) if item.endswith("/") else [item]
        if not found or not all((Path(root) / p).is_file() for p in found):
            raise Refused(f"A file the download needs is missing: {item}. Restore it, then build again.")
        chosen.update(p for p in found if not LEFT_OUT.search(p))
    if "src/clark/" in listed(system):
        for p in generated_pages(root):
            if not (Path(root) / p).is_file():
                raise Refused(f"A page the download needs has not been built: {p}. Run python3 dev/tools/build_page.py, then build again.")
            chosen.add(p)
    return sorted(chosen)


def start_here(system, for_client=False, root=ROOT):
    text = START_HERE_MAC + (START_HERE_DEMO if INCLUDE_DEMO else "")
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
    return f"clark-{version(root)}"


def zip_name(system, root=ROOT):
    return f"{top_folder(root)}-{system}.zip"


def entries(system, root=ROOT):
    """Every name in the zip, in order."""
    top = top_folder(root)
    return sorted(f"{top}/{p}" for p in files(system, root) + [START_HERE])


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
          released=None, min_from="0.0.0"):
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
    changed = [] if dirty else changed_files(uncommitted(root, list(listed(system))))
    if changed:
        raise Refused(f"Some of the files that go in the zip have changes that aren't committed: {', '.join(changed)}. "
                      "Commit them first, or add --dirty to build from them as they are.")
    if "src/clark/" in listed(system):
        make_pages(root, twice=release)
    names = files(system, root)
    top = top_folder(root)
    content = {f"{top}/{p}": ((root / p).read_bytes(), RUN_MODE if p in RUN_BIT else FILE_MODE) for p in names}
    content[f"{top}/{START_HERE}"] = (start_here(system, for_client, root).encode("utf-8"), FILE_MODE)
    if for_client:
        shown_paths, hidden = name_guard_hits({n[len(top) + 1:]: data for n, (data, _) in content.items()}, banned)
        if shown_paths or hidden:
            where = shown_paths + ([f"{hidden} file(s) whose own name holds one (not shown)"] if hidden else [])
            raise Refused("A zip for a client must hold no one's name, and the name guard found one in: "
                          f"{', '.join(where)}. Nothing was written. Take the name out, then build again.")
    content[f"{top}/{MANIFEST}"] = (manifest_bytes(system, content, top, root, released, notes, min_from), FILE_MODE)
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
    p.add_argument("--min-from", metavar="X.Y.Z", default="0.0.0", help="the oldest version that may update to this one")
    args = p.parse_args(argv)
    try:
        notes = Path(args.notes).read_text(encoding="utf-8") if args.notes else ""
        target = build(args.system, args.out, dirty=args.dirty, for_client=args.for_client, release=args.release,
                       notes=notes, min_from=args.min_from)
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
