"""Hands `python3 -m clark.doctor` (run from the repo's top folder) over to the real doctor in src/clark/doctor.py, as
launch.py beside it does for the launcher. Without this, the top folder's stand-in `clark` package would hide it.
"""
import sys

from clark.__main__ import prepare


def hand_over():
    prepare()
    from clark import doctor as real
    return real.main()


if __name__ == "__main__":
    sys.exit(hand_over())
