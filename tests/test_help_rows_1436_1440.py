"""Rows 1436, 1437, 1438, 1440: the Help lines that did not match the screens (row 1439 is left as it was: the code differs from the wording asked).

Run: python3 dev/run_tests.py test_help_rows_1436_1440
One test per changed line: the new sentence is in helpContent.json exactly once and the old one is gone.
"""
import json
import unittest

from _paths import SRC

HELP = SRC / "clark" / "page" / "src" / "help" / "helpContent.json"


def every_string(node):
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for v in node.values():
            yield from every_string(v)
    elif isinstance(node, list):
        for v in node:
            yield from every_string(v)


STRINGS = list(every_string(json.loads(HELP.read_text(encoding="utf-8"))))
TEXT = "\n".join(STRINGS)


def swapped(test, new, old):
    test.assertEqual(TEXT.count(new), 1, new)
    test.assertNotIn(old, TEXT, old)


class HelpRows(unittest.TestCase):
    def test_1436_import_not_in_clark_yet(self):
        new = ("a line under the list says how many more there are. A milestone or use case that is not in clark yet is listed under "
               "**Not in clark yet**: for each one choose **Create it** or **Use an existing one**, and **Import** waits until every one has an answer. If a row breaks")
        swapped(self, new, "how many more there are. If a row breaks")

    def test_1437_peek_top_bar_more_actions(self):
        new = "the item’s ID, then (in Edit) **More actions**, a menu with **Duplicate**, **Archive** and **Delete**, then **Make this panel fill the screen**"
        swapped(self, new, "(in Edit) **Duplicate** and **Archive**, then")

    def test_1438_warning_line_short(self):
        swapped(self, "A warning shows when an open item is due on a weekend, or an open action is overdue, with one-click fixes such as **Move to Friday** and the date.",
                "A warning shows when an action is overdue or due on a weekend")

    def test_1438_warning_line_peek(self):
        swapped(self, "A warning bar sits above the title (in Edit) when an open item is due on a weekend or an open action is overdue, with fixes such as **Move to Friday** and the date.",
                "A warning bar sits above the title (in Edit) when an action is overdue or due on a weekend")

    def test_1440_timeline_calendar_choice(self):
        swapped(self, "The two buttons at the top right, **Timeline** and **Calendar**, switch between them. In Edit your choice is kept; in a published file it lives only in the page address.",
                "switch between them. Your choice is kept.")

    def test_1440_details_choice(self):
        swapped(self, "**Show milestone details** brings it back. In Edit your choice is kept. On the Dashboard",
                "brings it back. Your choice is kept.")


if __name__ == "__main__":
    unittest.main()
