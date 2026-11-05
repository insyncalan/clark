"""Hands `python3 -m clark` (run from the repo's top folder) over to the real launcher in src/clark/__main__.py.

It puts src/ first on the path and vendor/ (the copied libraries, such as openpyxl for Excel) just after it, drops this
stand-in package from the loaded modules so that `import clark` finds the real one, and runs the real launcher. After it has run, `clark.__file__` is under src/. The tests never load this
file: the test runner starts from tests/, where the top folder is not on the path.
"""
import sys
from pathlib import Path

TOP = Path(__file__).resolve().parents[1]
SRC = str(TOP / "src")
VENDOR = str(TOP / "vendor")


def prepare():
    """Make `import clark` find the real package under src/ from now on, and the vendored libraries under vendor/."""
    sys.dont_write_bytecode = True          # as clark/__init__.py does: no __pycache__ in clark's folder (#57)
    for name in [n for n in sys.modules if n == "clark" or n.startswith("clark.")]:
        del sys.modules[name]
    for folder in (VENDOR, SRC):            # src/ ends up first, vendor/ second
        while folder in sys.path:
            sys.path.remove(folder)
        sys.path.insert(0, folder)


# Row 760: the same words as same_version.MESSAGE (a test keeps the two equal); said here when src/clark has no same_version.py,
# which is itself a folder of mixed versions.
MIXED = ("These clark files are not all from the same version, so clark will not start. "
         "Move the clark folder aside (rename it) and unzip the download again.")


def mixed(argv=None):
    """After prepare(): whether the folder is mixed, said on stderr. First, before the imports in the real launcher, which a
    missing or older file would break with a trace. With `argv`, nothing is refused while an interrupted update's marker exists."""
    try:
        from clark import same_version
    except ImportError:
        print(MIXED, file=sys.stderr, flush=True)
        return True
    return same_version.refuse(argv=argv)


def hand_over():
    prepare()
    if mixed(sys.argv[1:]):
        return 1
    from clark import __main__ as real
    return real.run()


if __name__ == "__main__":
    sys.exit(hand_over())
