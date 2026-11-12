"""Edges of the commitment words the reader finds in a sentence (sneak.COMMIT_WORDS): each word stands alone, so a longer word that
merely contains one is not a flag. Fictional data only.

Run: python3 dev/run_tests.py test_sneak_commit_words_edges
"""
import unittest

from clark import sneak
from test_sneak_milestone_usecase import DATA, NOW


def flag(words):
    r = sneak.read(DATA, "U-1", words, NOW)
    return [c["to"] for c in r.get("changes", []) if c["field"] == "commitment"]


class CommitWordEdges(unittest.TestCase):
    def test_each_word_alone_is_the_flag(self):
        for words, want in (("planned 2026", "Planned 2026"), ("planned for 2027", "Planned 2027"), ("committed", "Committed")):
            self.assertEqual(flag(words), [want], words)

    def test_a_longer_word_holding_the_word_is_not_the_flag(self):
        for words in ("uncommitted", "committeds", "replanned 2026", "replanned for 2027", "planned 20271", "planned 2026x", "planned 2027x"):
            self.assertEqual(flag(words), [], words)


if __name__ == "__main__":
    unittest.main()
