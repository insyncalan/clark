"""#96 G2, the RAID cards template four across (store type raid4): the same checks as three across (test_tpl_raid3.py) with a fourth
card. Run: python3 dev/run_tests.py test_tpl_raid4"""
import json
import unittest

import test_tpl_raid3 as three
from test_server import chrome  # noqa: F401  (a browser test: the tier is read from this text, as in test_run_tests)
from clark.section_kinds import raid4


class Raid4Checker(three.CheckerBase, unittest.TestCase):
    TYPE, SIZE, MODULE = "raid4", 4, raid4

    def test_a_show_choice_that_is_not_one_of_the_three_is_refused_in_the_ruled_words(self):      # row 1270, ruled words
        text = json.dumps({"v": 2, "across": 4, "cards": [{"id": "ABC-001", "source": "client", "show": {"colour": True}}]})
        self.bad(text, "Choose what a card shows: Latest update, Owner, status and date, or Impact and likelihood.")


class Raid4Items(three.Items):
    TYPE, SIZE = "raid4", 4


class Raid4Page(three.PageSide):
    TYPE, SIZE = "raid4", 4


if __name__ == "__main__":
    unittest.main()
