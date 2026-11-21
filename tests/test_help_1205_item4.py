"""Row 1205 item 4 and row 1258: the Help line about the peek **Source** names the source and no person.

Run: python3 dev/run_tests.py test_help_1205_item4
Content test: the Source sentence is a whole string in helpContent.json exactly once, and the old wording that ended the line with by and the name is not there.
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

SOURCE = ("**Source** (in Edit, in View and in a published file): under the details, where the item or milestone came from. It names the source and nothing else: no person. "
          "An item brought in from a Word file reads Word import, then the date (DD-MM-YYYY), the file name and the heading it came under.")


class Item4(unittest.TestCase):
    def test_source_line_is_one_whole_string(self):
        self.assertEqual(STRINGS.count(SOURCE), 1)
        self.assertEqual(TEXT.count(SOURCE), 1)

    def test_old_source_wording_with_by_and_the_name_is_gone(self):
        self.assertNotIn("In Edit and View it ends with by and the name of the person who added it", TEXT)
        self.assertNotIn("the heading it came under, then by and the name", TEXT)


if __name__ == "__main__":
    unittest.main()
