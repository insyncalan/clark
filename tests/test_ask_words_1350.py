"""Row 1350: the ask box placeholder and three slash hints carry the approved ticket wording.

Run: python3 dev/run_tests.py test_ask_words_1350
Reads askWords.js as text, so it needs no browser.
"""
import re
import unittest

from _paths import SRC

WORDS = (SRC / "clark" / "page" / "src" / "edit" / "askWords.js").read_text(encoding="utf-8")


def const(name):
    m = re.search(r"export const " + name + r' = "([^"]*)";', WORDS)
    assert m, name
    return m.group(1)


def hint(key):
    m = re.search(r"export const SLASH_HINT = \{(.*?)\n\};", WORDS, re.S)
    k = re.search(r"^\s*" + key + r': "([^"]*)",', m.group(1), re.M)
    assert k, key
    return k.group(1)


class AskWords1350(unittest.TestCase):
    def test_placeholder(self):
        self.assertEqual(const("PLACEHOLDER"), "Ask a question or give an instruction... (type / for shortcuts)")

    def test_summary_hint(self):
        self.assertEqual(hint("summary"), "Summarise this week into a draft")

    def test_overdue_hint(self):
        self.assertEqual(hint("overdue"), "What is overdue?")

    def test_use_cases_hint(self):
        self.assertEqual(hint("usecases"), "Which use cases need attention")

    def test_old_words_gone(self):
        self.assertNotIn("Ask a question about this project", WORDS)


if __name__ == "__main__":
    unittest.main()
