"""Row 1205, item 4: the Help lines about **Latest update** and **Shown to the client**.

Run: python3 dev/run_tests.py test_help_1205_item4
Content test: the ruled sentences are in helpContent.json exactly once, and the old unqualified wording is gone.
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

HOWTO = ("**Latest update**: click to write it. On an item shown to the client, the box says **Shown to the client**, "
         "because the client sees this text.")
PEEK = ("**Latest update** (in Edit; a published file shows it as a read-only line), and the words **Shown to the client** "
        "when the item is shown to the client; then when it was last updated.")


class Item4(unittest.TestCase):
    def test_howto_line_is_one_whole_string(self):
        self.assertEqual(STRINGS.count(HOWTO), 1)

    def test_peek_line_is_in_one_string(self):
        self.assertEqual(TEXT.count(PEEK), 1)
        self.assertEqual(sum(PEEK in s for s in STRINGS), 1)

    def test_old_unqualified_peek_wording_is_gone(self):
        self.assertNotIn("**Latest update**, and the words **Shown to the client**", TEXT)

    def test_shown_to_the_client_is_tied_to_a_shown_item(self):
        for s in STRINGS:
            if "the words **Shown to the client**" in s or "the box says **Shown to the client**" in s:
                self.assertIn("shown to the client", s.replace("**Shown to the client**", ""))


if __name__ == "__main__":
    unittest.main()
