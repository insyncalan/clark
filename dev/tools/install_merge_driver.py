"""Set up the merge driver for the built page files in THIS clone (#229; development only).

Run once per clone: python3 dev/tools/install_merge_driver.py

Git does not carry driver settings in the repository, so each clone needs this one command. It writes two keys, merge.clark-page.name
and merge.clark-page.driver, to the .git/config of the clone this file is in (a clone's worktrees share it), with a fixed
command (dev/tools/merge_page.py, by its absolute path in this clone, so it runs from any of the clone's work trees and is the
copy you installed, not a branch's): nothing is built from file names. It refuses to run outside a git work tree. The entry that
uses the driver is in .gitattributes.

READ THIS FIRST: the driver builds the page from the merged sources by running the MERGED branch's own dev/tools/build_page.py
(with the esbuild.py and src/clark/*.py it imports), with your rights, during the merge and before you have read the change. A
bad change to those files spreads through the driver. Before merging a branch you do not trust, check
git diff HEAD...<branch> -- dev/tools src/clark, or do not set the driver up. Undo: git config --local --remove-section merge.clark-page
"""
import shlex
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NAME = "clark-page"
DRIVER = f"python3 {shlex.quote(str(ROOT / 'dev' / 'tools' / 'merge_page.py'))} %O %A %B %P"


def main():
    inside = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--is-inside-work-tree"], capture_output=True, text=True)
    if inside.returncode != 0 or inside.stdout.strip() != "true":
        print("Not inside a git work tree: nothing changed.", file=sys.stderr)
        return 2
    for key, value in ((f"merge.{NAME}.name", "Rebuild the built page files"), (f"merge.{NAME}.driver", DRIVER)):
        if subprocess.run(["git", "-C", str(ROOT), "config", "--local", key, value]).returncode != 0:
            print(f"Could not set {key}.", file=sys.stderr)
            return 1
    print(f"Merge driver '{NAME}' set up for {ROOT}. The page files are now rebuilt when a merge touches them.\n"
          "Note: the rebuild runs the merged branch's own dev/tools/build_page.py, so read a change to dev/tools and src/clark before merging a branch you do not trust.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
