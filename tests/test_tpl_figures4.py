"""#96 G1, Key figures, four across (store type 'figures4'): the checker and its limits, hostile bodies, the published
figures (live ones are the At a glance figures of the rows publish kept; typed ones carry their words and as-of date; an empty or
half-filled template stays out of the file; a hidden item is never counted), one save = one step = one Undo, and the page's View
and Edit parts. The cases are shared with the other Key figures template (_tpl_figures.py).

Run: python3 dev/run_tests.py test_tpl_figures4
Needs Chrome (the #33 harness): the page tests fail, never skip, without it. Fictional data only.
"""
import unittest

from _tpl_figures import make_cases
from test_server import chrome  # noqa: F401  (these cases drive Chrome: the browser tier)

_cases = make_cases("figures4", 4)


class Contract(_cases[0]):
    pass


class Published(_cases[1]):
    pass


class ThroughTheStore(_cases[2]):
    pass


class PageSide(_cases[3]):
    pass


class InThePage(_cases[4]):
    pass



if __name__ == "__main__":
    unittest.main()
