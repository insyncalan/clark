"""Git merge driver for the built page files (#229; development only).

src/clark/page/page.html and page-view.html are written by dev/tools/build_page.py from the JSX sources, so merging their text is
pointless and always conflicts. This driver does what a person would: take the other side, then rebuild from the MERGED sources.

Git calls it as: python3 <this clone>/dev/tools/merge_page.py %O %A %B %P   (set up once per clone by dev/tools/install_merge_driver.py)
  %A  the file the result is left in      %B  the other side's version      %P  the path being merged

Git has not written the merged sources into the work tree when it calls a driver, so the driver gets them itself: `git merge-tree`
merges HEAD with the other side in memory, the result is unpacked into a temporary folder and that folder's own build_page.py
makes the page. It exits 1 (git reports a conflict) when the sources conflict, when there is no merge in progress it can read
(a single merged commit), when the build fails, or on any other error. On EVERY such failure it first writes conflict markers into
%A (ours, then theirs), because git alone would leave "ours" staged with no markers and the other branch's page would be lost
without a trace. A good build is written to %A in one piece; a failure never leaves a page that looks merged.

Where it runs from: install_merge_driver.py copies this one file to <git common dir>/clark-merge/ (outside every work tree, so a
branch without this file cannot break it) with a file SOURCE-COMMIT beside it, and the line "installed from commit ..." is
printed to stderr every run, so a stale copy shows. It needs only the Python standard library.

TRUST: the rebuild runs the MERGED branch's own dev/tools/build_page.py (and the esbuild.py and src/clark/*.py it imports), with
your rights, during the merge and before you have read the change. A bad change to those files therefore spreads through the
driver. Before you merge a branch you do not trust, look at what it changes under dev/tools and src/clark
(git diff HEAD...<branch> -- dev/tools src/clark); if you have not read it, do not merge with the driver set up.
"""
import io
import os
import shutil
import subprocess
import sys
import tarfile
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


def git(*args, cwd=ROOT):
    env = {k: v for k, v in os.environ.items() if k not in ("GIT_INDEX_FILE", "GIT_DIR", "GIT_WORK_TREE")}
    env[INNER] = "1"
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, env=env)


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


def rebuilt(tree, name, into):
    """Unpack `tree` into `into`, run its build_page.py there, return the bytes of the page `name`."""
    archive = git("archive", "--format=tar", tree)
    if archive.returncode != 0:
        return None
    with tarfile.open(fileobj=io.BytesIO(archive.stdout)) as tar:
        tar.extractall(into)
    cache = ROOT / "dev" / ".cache"               # the pinned esbuild is kept once per clone, not once per merge
    cache.mkdir(parents=True, exist_ok=True)
    (Path(into) / "dev" / ".cache").symlink_to(cache, target_is_directory=True)
    built = subprocess.run([sys.executable, str(Path(into) / "dev" / "tools" / "build_page.py")], cwd=into, capture_output=True,
                           text=True, encoding="utf-8")
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
    with tempfile.TemporaryDirectory(prefix="clark-merge-page-") as tmp:
        data = rebuilt(tree, Path(path).name, tmp)
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
