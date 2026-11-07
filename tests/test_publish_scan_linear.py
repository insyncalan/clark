"""#112: the new publish scans take time in proportion to the input (split from test_publish_scan_gaps.py so each file stays under the per-file limit on a hosted Mac).

Run: python3 dev/run_tests.py test_publish_scan_linear
Each scan is timed in CPU seconds on 30,000 and on 120,000 repeats of a hostile fragment (best of 3 each); the growth must stay near linear.
"""
import unittest

from _paths import ROOT, SRC, TOOLS  # noqa: F401

from clark import publish  # noqa: E402
from _growth import assert_growth  # noqa: E402


class Linear(unittest.TestCase):
    def test_the_new_scans_are_linear(self):
        # The old check was a wall-clock limit (3 s for 30,000 repeats); it is now the growth from 30,000 to 120,000 repeats in CPU time.
        for name, make in (("open tags", lambda n: "<a " * n), ("open quotes", lambda n: '<a b="' * n),
                           ("entities", lambda n: '<img src="' + "&#47;" * (2 * n) + 'x">'),
                           ("comment openers in style", lambda n: "<style>" + "/*" * n + "</style>"),
                           ("url openers", lambda n: "<style>" + "url(" * n + "</style>"),
                           ("escapes", lambda n: "<style>" + "\\\\" * n + "</style>"), ("hex escapes", lambda n: "<style>" + "\\75 " * n + "</style>"),
                           ("srcset commas", lambda n: '<img srcset="' + "," * n + '">'), ("srcset words", lambda n: '<img srcset="' + "a " * n + '">'),
                           ("style attrs", lambda n: '<a style="' * n), ("ampersands", lambda n: '<a href="' + "&" * n + '">'),
                           ("image-set", lambda n: "<style>" + "image-set(" * n + "</style>")):
            assert_growth(self, lambda size, make=make: publish.outside_addresses(make(size)), 30000, name)


if __name__ == "__main__":
    unittest.main()
