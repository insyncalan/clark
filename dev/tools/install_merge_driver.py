"""Set up the merge driver for the built page files in THIS clone (#229; development only).

Run once per clone: python3 dev/tools/install_merge_driver.py

Git does not carry driver settings in the repository, so each clone needs this one command. It writes two keys, merge.clark-page.name
and merge.clark-page.driver, to the .git/config of the clone this file is in (a clone's worktrees share it), with a fixed
command (dev/tools/merge_page.py): nothing is built from file names. It refuses to run outside a git work tree. The entry that
uses the driver is in .gitattributes. Undo: git config --local --remove-section merge.clark-page
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NAME = "clark-page"
DRIVER = "python3 dev/tools/merge_page.py %O %A %B %P"


def main():
    inside = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--is-inside-work-tree"], capture_output=True, text=True)
    if inside.returncode != 0 or inside.stdout.strip() != "true":
        print("Not inside a git work tree: nothing changed.", file=sys.stderr)
        return 2
    for key, value in ((f"merge.{NAME}.name", "Rebuild the built page files"), (f"merge.{NAME}.driver", DRIVER)):
        if subprocess.run(["git", "-C", str(ROOT), "config", "--local", key, value]).returncode != 0:
            print(f"Could not set {key}.", file=sys.stderr)
            return 1
    print(f"Merge driver '{NAME}' set up for {ROOT}. The page files are now rebuilt when a merge touches them.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
