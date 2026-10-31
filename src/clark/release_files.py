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
    "clark/",                   # the stand-in that hands `python3 -m clark` to src/clark/
    "src/clark/",               # with the built page.html
    "vendor/README.md",         # vendor/manifest.json lists it
    "vendor/et_xmlfile/",
    "vendor/fonts/",
    "vendor/licenses/",
    "vendor/manifest.json",
    "vendor/openpyxl/",
) + (("dev/demo_data.py",) if INCLUDE_DEMO else ())

# What each system adds. Windows will add clark.cmd and python\ here; nothing else changes.
SYSTEMS = {
    "mac": ("clark.command",),
}
NOT_BUILT_YET = {"windows"}

RUN_BIT = {"clark.command"}     # files that must stay runnable after unzipping
START_HERE = "START-HERE.txt"   # written by package.py, not taken from the repo
MANIFEST = "clark-release.json" # written by package.py from the files it zips; it does not list itself


def listed(system):
    """The list for `system`: SHARED plus its own files."""
    return SHARED + SYSTEMS[system]


def covers(system, rel):
    """Whether the file `rel` (relative to the top folder, "/" only) belongs to a download for `system`."""
    if rel in (START_HERE, MANIFEST):
        return True
    for item in listed(system):
        if item.endswith("/"):
            if rel.startswith(item):
                return True
        elif rel == item:
            return True
    return False
