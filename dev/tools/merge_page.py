"""Git merge driver for the built page files (#229; development only).

src/clark/page/page.html and page-view.html are written by dev/tools/build_page.py from the JSX sources, so merging their text is
pointless and always conflicts. This driver does what a person would: take the other side, then rebuild from the MERGED sources.

Git calls it as: python3 <this clone>/dev/tools/merge_page.py %O %A %B %P   (set up once per clone by dev/tools/install_merge_driver.py)
  %A  the file the result is left in      %B  the other side's version      %P  the path being merged

Git has not written the merged sources into the work tree when it calls a driver, so the driver gets them itself: `git merge-tree`
merges HEAD with the other side in memory, the checked files of the result are written into a temporary folder and the build runs
there. It exits 1 (git reports a conflict) when the sources conflict, when there is no merge in progress it can read (a single
merged commit), when the merge is refused (below), when the build fails, or on any other error. On EVERY such failure it first
writes conflict markers into %A (ours, then theirs), because git alone would leave "ours" staged with no markers and the other
branch's page would be lost without a trace. A good build is written to %A in one piece; a failure never leaves a page that looks merged.

Where it runs from: install_merge_driver.py copies this one file to <git common dir>/clark-merge/ (outside every work tree, so a
branch without this file cannot break it) with a file SOURCE-COMMIT beside it, and the line "installed from commit ..." is
printed to stderr every run, so a stale copy shows. It needs only the Python standard library.

TRUST: the whole repository is the trust boundary, so the driver works from an ALLOW-LIST and never runs code from the branch:
  - the build's code is named in BUILD_CODE (dev/tools/build_page.py, dev/tools/esbuild.py, src/clark/__init__.py and
    src/clark/page/__init__.py, read from their imports); the rebuild runs only those, so they must be exactly HEAD's;
  - every path the merge changes under src/, dev/tools/, dev/.cache/ or vendor/ must be PAGE DATA: the page sources
    (src/clark/page/src/), the shell's CSS (src/clark/page/*.css) and the two built pages, as plain files and never a code file
    (.py, .pyc, .so, .pth and the like). Anything else there (a new or changed .py, a force-added __pycache__ .pyc, a compiled
    module, a vendored library or font, a link) REFUSES the merge: conflict markers and a plain sentence on stderr naming the
    path. It never builds from HEAD's copy instead (the page would not match the merged sources) or from the branch's;
  - only the build's code, the files it reads (BUILD_INPUTS, unchanged from HEAD) and the page data are written into the temporary
    folder, each checked: a plain file, a safe name, never a link, a device or a code file outside BUILD_CODE;
  - the build runs as python3 -I -B with a scrubbed environment (no PYTHONPATH, PYTHONDONTWRITEBYTECODE=1, PYTHONNOUSERSITE=1);
  - the pinned esbuild in the clone's dev/.cache is COPIED into the temporary folder, never linked, so nothing the build writes
    reaches the real dev/.cache.
A branch that changes only page data resolves by itself. Before merging a branch you do not know, look at what it changes:
    git diff HEAD...<branch> -- src dev vendor
UNDO (remove the driver): python3 dev/tools/install_merge_driver.py --uninstall, or by hand:
    git config --unset merge.clark-page.driver ; git config --unset merge.clark-page.name ; rm -r <git-common-dir>/clark-merge
A rebase or cherry-pick runs the driver once per commit it replays; a squash merge runs it once.
"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path



def work_tree():
    """The work tree git is merging in: git runs a driver from its top folder, so this is also right in a linked work tree.
    Falls back to the current folder."""
    try:
        r = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    except OSError:                                # no git on the path: main() reports it as a failure with markers
        return Path.cwd().resolve()
    return Path(r.stdout.strip()).resolve() if r.returncode == 0 and r.stdout.strip() else Path.cwd().resolve()


ROOT = work_tree()
PAGES = ("src/clark/page/page.html", "src/clark/page/page-view.html")
INNER = "CLARK_MERGE_PAGE_INNER"          # set while the driver's own git call runs, so it can never call itself


def git(*args, cwd=ROOT, input_bytes=None):
    env = {k: v for k, v in os.environ.items() if k not in ("GIT_INDEX_FILE", "GIT_DIR", "GIT_WORK_TREE")}
    env[INNER] = "1"
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, env=env, input=input_bytes)


def other_side():
    """The commit being merged in, or None. Git names it for its drivers in GITHEAD_<commit> (one variable per merged head;
    MERGE_HEAD is not written yet); a cherry-pick's is CHERRY_PICK_HEAD. Several heads (an octopus merge) give None."""
    heads = [k[len("GITHEAD_"):] for k in os.environ if k.startswith("GITHEAD_")]
    if len(heads) == 1:
        return heads[0]
    r = git("rev-parse", "-q", "--verify", "CHERRY_PICK_HEAD")
    return r.stdout.decode().strip() if r.returncode == 0 and not heads else None


def merged_tree(theirs):
    """The tree git's own merge of HEAD and `theirs` gives, or None when anything but the page files conflicts."""
    r = git("merge-tree", "--write-tree", "--name-only", "--no-messages", "HEAD", theirs)
    lines = r.stdout.decode().splitlines()
    if r.returncode not in (0, 1) or not lines:
        return None
    conflicted = [x for x in lines[1:] if x]
    return lines[0] if all(x in PAGES for x in conflicted) else None


# THE BUILD'S CODE: every file of the repository that runs when dev/tools/build_page.py builds the page, found by reading the
# imports (the standard library left out): build_page.py imports esbuild (dev/tools/esbuild.py) and clark.page, which loads
# src/clark/__init__.py and src/clark/page/__init__.py; those import only the standard library. These four, and nothing else
# Python could load, are unpacked from the merged tree, and the merge is refused unless all four are exactly HEAD's.
# tests/test_merge_driver.py fails if one of them gains an import from outside this set.
BUILD_CODE = ("dev/tools/build_page.py", "dev/tools/esbuild.py", "src/clark/__init__.py", "src/clark/page/__init__.py")
# What the build reads as data and the merge may NOT change (a change refuses): the vendored libraries and fonts it bundles, the
# demo brand's tokens and the page's pictures. They are unpacked so the build can read them.
BUILD_INPUTS = ("vendor/preact/", "vendor/tiptap/", "vendor/fonts/", "src/clark/brand/tokens.css", "src/clark/page/assets/")
# Where the repository's code and build tools live. Any path the merge changes under these (compared in lower case, so a
# look-alike such as src/Clark counts) must be page data, or the merge is refused.
GUARDED = ("src/", "dev/tools/", "dev/.cache/", "vendor/")
CODE_SUFFIXES = (".py", ".pyc", ".pyo", ".pyd", ".so", ".dylib", ".dll", ".pth")
REGULAR = ("100644", "100755")


class Refused(Exception):
    """The merged tree holds something the driver will not unpack or run; the message says what, in plain words."""


def page_data(path):
    """The page's data: the paths a merge may change and still be rebuilt by itself. The page sources (src/clark/page/src/),
    the shell's CSS (src/clark/page/*.css) and the two built pages; never a code file, even in those folders."""
    if path.lower().endswith(CODE_SUFFIXES) or "__pycache__" in path.split("/"):
        return False
    if path.startswith("src/clark/page/src/") or path in PAGES:
        return True
    return path.startswith("src/clark/page/") and path.endswith(".css") and "/" not in path[len("src/clark/page/"):]


def unpacked_path(path):
    """True for the files the rebuild needs: the build's code, its inputs and the page data. Nothing else is ever unpacked."""
    return path in BUILD_CODE or page_data(path) or any(path == p or (p.endswith("/") and path.startswith(p)) for p in BUILD_INPUTS)


def refusal(tree):
    """Why the merged `tree` may not be built by itself, or None. Every path that differs from HEAD (additions, deletions and
    mode changes; renames count as both) must be page data and a plain file, or lie outside the guarded folders."""
    r = git("diff-tree", "-r", "-z", "--no-renames", "--no-commit-id", "HEAD", tree)
    if r.returncode != 0:
        return "git could not compare the merged sources with HEAD"
    fields = r.stdout.decode("utf-8", "surrogateescape").split("\0")
    for meta, path in zip(fields[0::2], fields[1::2]):
        new_mode = meta.split(" ")[1] if meta.count(" ") >= 4 else ""
        if page_data(path):
            if new_mode not in REGULAR + ("000000",):
                return f"the merge makes {path} something other than a plain file"
        elif path.lower().startswith(GUARDED):
            return f"the merge changes {path}, which is not page data"
    return None


def checked_members(tree):
    """(path, blob id, mode) for each file to unpack from `tree`. Raises Refused for any of them that is not a plain file
    (a link, a submodule) or whose name could leave the folder."""
    r = git("ls-tree", "-r", "-z", "--full-tree", tree)
    if r.returncode != 0:
        raise Refused("git could not list the merged tree")
    out = []
    for entry in r.stdout.decode("utf-8", "surrogateescape").split("\0"):
        if not entry:
            continue
        meta, path = entry.split("\t", 1)
        mode, _kind, blob = meta.split(" ")
        if not unpacked_path(path):
            continue
        parts = path.split("/")
        if (mode not in REGULAR or any(x in ("", ".", "..") or x.lower() == ".git" or "\\" in x for x in parts)
                or (path not in BUILD_CODE and path.lower().endswith(CODE_SUFFIXES))):
            raise Refused(f"the merged tree holds an unsafe entry ({path}): not unpacked")
        out.append((path, blob))
    return out


def unpack(tree, into):
    """Write the checked files of `tree` into `into`, each as a new plain file (never through an existing name)."""
    members = checked_members(tree)
    batch = git("cat-file", "--batch", input_bytes=b"".join(blob.encode() + b"\n" for _p, blob in members))
    if batch.returncode != 0:
        raise Refused("git could not read the merged files")
    data, at, target = batch.stdout, 0, os.path.realpath(into)
    for path, blob in members:
        head_end = data.index(b"\n", at)
        sha, kind, size = data[at:head_end].decode().split(" ")
        if sha != blob or kind != "blob":
            raise Refused(f"git gave something unexpected for {path}")
        body = data[head_end + 1:head_end + 1 + int(size)]
        at = head_end + 1 + int(size) + 1
        where = os.path.join(target, *path.split("/"))
        if os.path.commonpath([target, os.path.realpath(os.path.dirname(where))]) != target:
            raise Refused(f"the merged tree holds an unsafe entry ({path}): not unpacked")
        os.makedirs(os.path.dirname(where), exist_ok=True)
        with open(where, "xb") as f:
            f.write(body)


def copy_cache(into):
    """Copy the clone's pinned esbuild (dev/.cache/esbuild, plain files only) into the temporary folder. A copy, not a link: the
    build can write to its own dev/.cache and nothing reaches the clone's real one, which every later build trusts. (The pinned
    hash is the download's, not the program's, so the program could not be checked again instead without fetching it.)"""
    real = ROOT / "dev" / ".cache" / "esbuild"
    for folder, dirs, files in os.walk(real):
        dirs[:] = [d for d in dirs if not os.path.islink(os.path.join(folder, d))]
        for name in files:
            source = os.path.join(folder, name)
            if os.path.islink(source) or not os.path.isfile(source):
                continue
            dest = Path(into) / "dev" / ".cache" / "esbuild" / os.path.relpath(source, real)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, dest)


def build_env():
    """A scrubbed environment for the build: no PYTHONPATH or other inherited Python or git settings."""
    env = {k: os.environ[k] for k in ("PATH", "HOME", "TMPDIR", "LANG", "LC_ALL", "LC_CTYPE", "SYSTEMROOT") if k in os.environ}
    env.update(PYTHONDONTWRITEBYTECODE="1", PYTHONNOUSERSITE="1")
    return env


def rebuilt(tree, name, into):
    """Unpack the checked files of `tree` into `into`, run build_page.py there (HEAD's own, as refusal() made sure), return the
    bytes of the page `name`."""
    unpack(tree, into)
    copy_cache(into)
    built = subprocess.run([sys.executable, "-I", "-B", str(Path(into) / "dev" / "tools" / "build_page.py")], cwd=into,
                           capture_output=True, text=True, encoding="utf-8", env=build_env())
    if built.returncode != 0:
        print((built.stdout + built.stderr)[-2000:], file=sys.stderr)
        return None
    return (Path(into) / "src" / "clark" / "page" / name).read_bytes()


def installed_from():
    """The commit the installer copied this file from (SOURCE-COMMIT beside it), or a plain 'unknown'."""
    try:
        return (Path(__file__).resolve().parent / "SOURCE-COMMIT").read_text(encoding="utf-8").strip() or "unknown"
    except OSError:
        return "unknown (run in the source tree, not an installed copy)"


def older_than_branch():
    """True only when the copy was installed from a commit that is NOT an ancestor of (or equal to) this clone's HEAD. When git
    cannot tell (no stamp, an unknown commit, no git), False: this note never matters enough to say something unsure."""
    try:
        words = (Path(__file__).resolve().parent / "SOURCE-COMMIT").read_text(encoding="utf-8").split()
        stamped = words[0] if words else ""
        if len(stamped) < 7 or any(c not in "0123456789abcdef" for c in stamped):
            return False
        head = git("rev-parse", "HEAD")
        if head.returncode != 0 or head.stdout.decode().strip() == stamped:
            return False
        return git("merge-base", "--is-ancestor", stamped, "HEAD").returncode == 1
    except Exception:
        return False


def write_markers(mine, theirs_file, why):
    """Leave conflict markers in %A so git and the person see a conflict; never raises."""
    try:
        ours = Path(mine).read_bytes()
        theirs = Path(theirs_file).read_bytes()
        Path(mine).write_bytes(b"<<<<<<< ours (merge_page.py: " + why.encode("utf-8", "replace") + b")\n" + ours.rstrip(b"\n")
                               + b"\n=======\n" + theirs.rstrip(b"\n") + b"\n>>>>>>> theirs\n")
    except Exception as exc:                       # even this must not hide the failure: the message below still says so
        print(f"merge_page.py: could not write conflict markers: {exc}", file=sys.stderr)


def merge(mine, theirs_file, path):
    """Returns (exit code, reason); a non-zero code means the caller writes markers."""
    theirs = other_side()
    tree = merged_tree(theirs) if theirs else None
    if tree is None:
        return 1, "the sources conflict, or this is not a merge it can read: resolve them, then run python3 dev/tools/build_page.py"
    why = refusal(tree)
    if why:
        return 1, (f"{why}, and the driver will not run code from the branch being merged or build from anything but page "
                   "data: read the change (git diff HEAD...<branch> -- src dev vendor), then run python3 dev/tools/build_page.py")
    try:
        with tempfile.TemporaryDirectory(prefix="clark-merge-page-") as tmp:
            data = rebuilt(tree, Path(path).name, tmp)
    except Refused as exc:
        return 1, f"{exc}; resolve this page by running python3 dev/tools/build_page.py after the merge"
    if data is None:
        return 1, "the rebuild failed: resolve this page by running python3 dev/tools/build_page.py after the merge"
    Path(mine).write_bytes(data)
    return 0, ""


def main(argv):
    if argv in (["--help"], ["-h"]):
        print("usage: merge_page.py %O %A %B %P  (a git merge driver; set up by dev/tools/install_merge_driver.py)\n"
              f"installed from commit {installed_from()}")
        return 0
    print(f"merge_page.py: installed from commit {installed_from()}", file=sys.stderr)
    if len(argv) != 4:
        print("usage: merge_page.py %O %A %B %P", file=sys.stderr)
        return 2
    if older_than_branch():
        print("This copy of the merge driver is older than the branch you are on. Run the installer again.", file=sys.stderr)
    _base, mine, theirs_file, path = argv
    if path not in PAGES:
        print(f"merge_page.py only merges {', '.join(PAGES)}", file=sys.stderr)
        write_markers(mine, theirs_file, "not a page file")
        return 2
    if os.environ.get(INNER):                      # git called us from our own merge-tree: any answer will do, it is rebuilt
        shutil.copyfile(theirs_file, mine)
        return 0
    try:
        code, why = merge(mine, theirs_file, path)
    except BaseException as exc:                   # any failure at all must show as a conflict, never as a silent loss
        code, why = 1, f"unexpected error {type(exc).__name__}: {exc}"
    if code != 0:
        print(f"merge_page.py: {why}", file=sys.stderr)
        write_markers(mine, theirs_file, why)
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
