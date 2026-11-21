"""Row 1205, item 4: the Help lines about **Latest update** and **Shown to the client**.

Run: python3 dev/run_tests.py test_help_1205_item4
Content test: the ruled sentences are whole strings in helpContent.json exactly once, and the old wording and the shown-to-the-client wording are gone.
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

HOWTO = "**Latest update**: click to write it."
PEEK = "**Latest update** (in Edit; a published file shows it as a read-only line), then when it was last updated."


class Item4(unittest.TestCase):
    def test_howto_line_is_one_whole_string(self):
        self.assertEqual(STRINGS.count(HOWTO), 1)

    def test_peek_line_is_one_whole_string(self):
        self.assertEqual(STRINGS.count(PEEK), 1)
        self.assertEqual(TEXT.count(PEEK), 1)

    def test_old_unqualified_peek_wording_is_gone(self):
        self.assertNotIn("**Latest update**, and the words **Shown to the client**", TEXT)

    def test_shown_to_the_client_wording_is_gone(self):
        self.assertNotIn("**Shown to the client**", TEXT)


if __name__ == "__main__":
    unittest.main()
