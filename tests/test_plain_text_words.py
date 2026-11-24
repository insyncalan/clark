"""Hunt 13: the page's words for the server's plain-text refusal fit every field that can raise it (title, notes, client wording),
so they say "That", not "A name".

Run: python3 dev/run_tests.py test_plain_text_words     No browser. Fictional data.
"""
import re
import unittest

from _paths import SRC

from clark import changes

REPORT = SRC / "clark" / "page" / "src" / "stores" / "report.js"
WANT = "That can only be plain text, with no line breaks or hidden characters. Nothing was changed."


class PlainTextWords(unittest.TestCase):
    def test_the_page_maps_the_servers_sentence_to_field_neutral_words(self):
        src = REPORT.read_text(encoding="utf-8")
        m = re.search(r'^\s*"' + re.escape(changes.ITEM_TEXT_WORDS) + r'":\s*"([^"]*)"', src, re.M)
        self.assertIsNotNone(m, "the page has no mapping for the server's plain-text sentence")
        self.assertEqual(m.group(1), WANT)
        self.assertNotIn("A name can only", src)


if __name__ == "__main__":
    unittest.main()
