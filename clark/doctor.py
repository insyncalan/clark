"""Hands `python3 -m clark.doctor` (run from the repo's top folder) over to the real doctor in src/clark/doctor.py, as
launch.py beside it does for the launcher. Without this, the top folder's stand-in `clark` package would hide it.
"""
import sys

from clark.__main__ import mixed, prepare


def hand_over():
    prepare()
    if mixed():                                 # row 760: the check says the same words; it recovers nothing, so no marker is waited for
        return 1
    from clark import doctor as real
    return real.main()


if __name__ == "__main__":
    sys.exit(hand_over())
