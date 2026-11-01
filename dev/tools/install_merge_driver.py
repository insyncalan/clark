"""Set up the merge driver for the built page files in THIS clone (#229; development only).

Run once per clone, and again after merge_page.py changes: python3 dev/tools/install_merge_driver.py

Git does not carry driver settings in the repository, so each clone needs this one command. It does three things:
  1. copies dev/tools/merge_page.py to <git common dir>/clark-merge/ (the clone's .git, shared by all its work trees and outside
     every one of them), so the driver still runs when you are on a branch that has no such file;
  2. checks that the copy runs (python3 merge_page.py --help) and refuses, changing nothing, if it does not;
  3. writes merge.clark-page.name and merge.clark-page.driver to the clone's shared .git/config, pointing at that copy by its
     absolute path.
It also records the commit it copied from in clark-merge/SOURCE-COMMIT; the driver prints that commit to stderr on every run.
A copy inside .git does NOT update with git pull or a branch change: after merge_page.py changes, run this command again.
The entry that uses the driver is in .gitattributes. If the driver cannot finish it writes conflict markers into the page, so a
failed merge is always visible.

READ THIS FIRST: the driver builds the page from the merged sources by running the MERGED branch's own dev/tools/build_page.py
(with the esbuild.py and src/clark/*.py it imports), with your rights, during the merge and before you have read the change. A
bad change to those files spreads through the driver. Before merging a branch you do not trust, check
git diff HEAD...<branch> -- dev/tools src/clark, or do not set the driver up. Undo: git config --local --remove-section merge.clark-page
"""
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NAME = "clark-page"
SCRIPT = Path(__file__).resolve().parent / "merge_page.py"


def git(*args):
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True)


def main():
    if "--help" in sys.argv[1:] or "-h" in sys.argv[1:]:
        print(__doc__)
        return 0
    inside = git("rev-parse", "--is-inside-work-tree")
    if inside.returncode != 0 or inside.stdout.strip() != "true":
        print("Not inside a git work tree: nothing changed.", file=sys.stderr)
        return 2
    if not SCRIPT.is_file():
        print(f"{SCRIPT} is missing, so there is nothing to install: check out a branch that has it, then run this again.", file=sys.stderr)
        return 2
    common = git("rev-parse", "--git-common-dir").stdout.strip()
    if not common:
        print("Could not find the git folder: nothing changed.", file=sys.stderr)
        return 2
    target_dir = (ROOT / common).resolve() / "clark-merge"
    commit = git("rev-parse", "HEAD").stdout.strip() or "unknown"
    if git("status", "--porcelain", "--", "dev/tools/merge_page.py").stdout.strip():
        commit += " (merge_page.py has uncommitted changes)"
    target_dir.mkdir(parents=True, exist_ok=True)
    copy = target_dir / "merge_page.py"
    shutil.copyfile(SCRIPT, copy)
    (target_dir / "SOURCE-COMMIT").write_text(commit + "\n", encoding="utf-8")
    check = subprocess.run(["python3", str(copy), "--help"], capture_output=True, text=True)
    if check.returncode != 0 or "merge_page.py" not in check.stdout:
        print(f"The copy at {copy} does not run ({(check.stderr or check.stdout).strip()[-300:]}): the driver was not set up and "
              "your git settings are unchanged. Fix python3 on your PATH, then run this again.", file=sys.stderr)
        return 1
    # If python3 cannot even start the copy (it was deleted, say), git would leave "ours" with no markers: the small shell wrapper
    # adds them whenever the copy exits non-zero without having written its own. If it cannot write them either it says so on
    # stderr and keeps the non-zero exit, so git reports a conflict and the page is never taken as merged without a word.
    script = (f'python3 {shlex.quote(str(copy))} "$@"; rc=$?; '
              'if [ $rc -ne 0 ] && ! head -n 1 "$2" | grep -q "^<<<<<<< "; then '
              't=$(mktemp "${TMPDIR:-/tmp}/clark-merge.XXXXXX") && '
              '{ printf "<<<<<<< ours (merge driver could not run)\\n"; awk 1 "$2"; printf "=======\\n"; awk 1 "$3"; '
              'printf ">>>>>>> theirs\\n"; } > "$t" && cat "$t" > "$2" && rm -f "$t" || '
              '{ echo "The merge driver could not write conflict markers into $4, so the file may hold only our side. '
              'Rebuild it with python3 dev/tools/build_page.py after the merge, then check it." >&2; '
              '[ $rc -ne 0 ] || rc=1; }; fi; exit $rc')
    driver = f"sh -c {shlex.quote(script)} sh %O %A %B %P"
    for key, value in ((f"merge.{NAME}.name", "Rebuild the built page files"), (f"merge.{NAME}.driver", driver)):
        if git("config", "--local", key, value).returncode != 0:
            print(f"Could not set {key}.", file=sys.stderr)
            return 1
    print(f"Merge driver '{NAME}' set up for {ROOT}: copy at {copy}, from commit {commit}.\n"
          "A copy in .git does not update with git pull: run this command again after merge_page.py changes.\n"
          "Note: the rebuild runs the merged branch's own dev/tools/build_page.py, so read a change to dev/tools and src/clark before merging a branch you do not trust.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
