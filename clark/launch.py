"""Hands `python3 -m clark.launch` (run from the repo's top folder) over to the real launcher in src/clark/launch.py, as
__main__.py beside it does for `python3 -m clark`. Without this, the top folder's stand-in `clark` package would hide
src/clark/launch.py. clark.command runs this.
"""
import sys

from clark.__main__ import prepare


def hand_over():
    prepare()
    from clark import same_version              # row 760: first, before the imports in the real launcher, which a missing or older file would break
    if same_version.refuse(argv=sys.argv[1:]):
        return 1
    from clark import launch as real
    return real.main()


if __name__ == "__main__":
    sys.exit(hand_over())
