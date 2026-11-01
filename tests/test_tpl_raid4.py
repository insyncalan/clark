"""#96 G2, the RAID cards template four across (store type raid4): the same checks as three across (test_tpl_raid3.py) with a fourth
card. Run: python3 dev/run_tests.py test_tpl_raid4"""
import unittest

import test_tpl_raid3 as three
from test_server import chrome  # noqa: F401  (a browser test: the tier is read from this text, as in test_run_tests)
from clark.section_kinds import raid4


class Raid4Checker(three.CheckerBase, unittest.TestCase):
    TYPE, SIZE, MODULE = "raid4", 4, raid4


class Raid4Items(three.Items):
    TYPE, SIZE = "raid4", 4


class Raid4Page(three.PageSide):
    TYPE, SIZE = "raid4", 4


if __name__ == "__main__":
    unittest.main()
