"""The one list of what a clark download holds (#57, #109).

dev/tools/package.py builds the download from this list; the updater (updates.py) checks a new download's top-level
entries against it, as the closed list of what clark may replace. Nothing else keeps a copy of it. Standard library only,
Python 3.9; it imports nothing, so the updater can read it from any folder.

A name ending in "/" is a folder: every file git tracks under it, so nothing untracked can slip in.
"""

# Whether dev/demo_data.py is in the download, so that --demo works there (open question 3 in docs/handoff/packaging-57.md).
INCLUDE_DEMO = True

# For every system.
SHARED = (
    "README.md",
    "LICENSE",                  # item 4 of the licence: it must not be removed from copies
    "NOTICE.md",                # the MIT, OFL, PSF and ISC texts the bundled code and fonts require (#639)
    "clark/",                   # the stand-in that hands `python3 -m clark` to src/clark/
    "docker/",                  # item 427: the compose file (a stock Python image runs this folder), for a computer that uses Docker
    "src/clark/",               # with the built page.html
    "vendor/README.md",         # vendor/manifest.json lists it
    "vendor/ed25519_verify/",
    "vendor/et_xmlfile/",
    "vendor/fonts/",
    "vendor/licenses/",
    "vendor/manifest.json",
    "vendor/openpyxl/",
    "vendor/pypdf/",            # #891: reads the text of a PDF (BSD-3, pure Python)
    "vendor/typing_extensions.py",   # pypdf's one dependency on Python 3.9 and 3.10 (PSF-2.0; licence in vendor/licenses/)
) + (("dev/demo_data.py",) if INCLUDE_DEMO else ())

# What each system adds. Windows will add clark.cmd and python\ here; nothing else changes.
SYSTEMS = {
    "mac": ("clark.command",),
}
NOT_BUILT_YET = {"windows"}

RUN_BIT = {"clark.command"}     # files that must stay runnable after unzipping
START_HERE = "START-HERE.md"    # written by package.py, not taken from the repo (the reader also accepts START-HERE.txt: zips up to 1.0.4 carry it)
START_HERE_NAMES = ("START-HERE.md", "START-HERE.txt")   # a reader accepts either as the one start file at the top (zips up to 1.0.4 carry the .txt; package.py writes the .md)
MANIFEST = "clark-release.json" # written by package.py from the files it zips; it does not list itself


# --- where a name sits inside the zip (issue 694) -------------------------------------------------------------------------
# The repository stays flat (src/ at its root). Only the zip puts the program files in one hidden folder, so the list above
# is never edited for it: place() maps any name the list produces to its place in the zip.
TOP = "clark"                   # the one folder the zip unzips to, whatever the version (the zip file keeps clark-<version>-<system>.zip)
HIDDEN = ".app"                 # the one hidden folder that holds every program file
CODE_ROOT_MARK = HIDDEN + "/"
# What stays visible at the top of the clark folder. A name ending in "/" is a folder.
AT_TOP = ("README.md", "START-HERE.txt", "START-HERE.md", "clark.command", "clark.cmd", MANIFEST, "docker/")
# The README the zip carries is not the repository's README.md (that one is written for people reading the repository): its
# words live in docs/zip/README.md and the zip puts them at the top under the name README.md. Only the zip does this.
ZIP_README = "docs/zip/README.md"
SOURCE_OF = {"README.md": ZIP_README}


def source(rel):
    """The repo file whose bytes the zip holds for the name `rel`: the file itself, except the README (see ZIP_README)."""
    return SOURCE_OF.get(rel, rel)


# Top-level names that belong to the person. They are never in a zip, never listed, backed up, replaced or removed.
PROTECTED = ("system", "data")
# Extra top-level folders a release may carry beside the program files (issue 716): files the Head puts in at build time
# (dev/tools/package.py --extra-folder), never tracked by git. The allow-list is closed: a reader accepts a folder only if
# its exact name is here, so a stray folder in a download is still refused as outside the list.
EXTRA_TOP = ("meet clark", "intake")


def listed(system):
    """The list for `system`: SHARED plus its own files."""
    return SHARED + SYSTEMS[system]


def protected(rel):
    """Whether `rel` (a "/" name) is, or is inside, a folder that belongs to the person. Case does not matter: a Mac disk
    treats System and system as one folder."""
    head = rel.replace("\\", "/").split("/")[0].casefold()
    return head in PROTECTED


def extra(rel):
    """Whether `rel` (a name below the top folder, "/" only) is a file inside one of the declared extra top-level folders."""
    head, sep, rest = rel.partition("/")
    return bool(sep and rest) and head in EXTRA_TOP


def at_top(rel):
    """Whether the repo-relative name `rel` stays at the top of the clark folder."""
    return any(rel == item or (item.endswith("/") and rel.startswith(item)) for item in AT_TOP)


def place(rel):
    """Where the repo-relative name `rel` (a file, or a folder ending in "/") sits in the zip, below the top folder."""
    return rel if at_top(rel) else CODE_ROOT_MARK + rel


def unplace(placed):
    """The inverse of place(): the repo-relative name of a name in the zip."""
    return placed[len(CODE_ROOT_MARK):] if placed.startswith(CODE_ROOT_MARK) else placed


def covers(system, rel):
    """Whether the file `rel` (its place in the zip, below the top folder, "/" only) belongs to a download for `system`.

    Anything protected is refused first, whatever the list says."""
    if protected(rel):
        return False
    if rel in START_HERE_NAMES + (MANIFEST,):
        return True
    if extra(rel):                      # a declared extra folder (issue 716); optional, so check_coverage never asks for it
        return True
    for item in listed(system):
        placed = place(item)
        if item.endswith("/"):
            if rel.startswith(placed):
                return True
        elif rel == placed:
            return True
    return False
