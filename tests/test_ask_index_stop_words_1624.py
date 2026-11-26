"""Row 1624: the index search leaves the common words of a question out, so a file that shares only "the" or "is" with it is not found.

Run: python3 dev/run_tests.py test_ask_index_stop_words_1624
Tests only, no browser. Every file is made in the test from made-up text.
"""
import unittest

from _paths import SRC  # noqa: F401

from test_ask_index_1366 import Base, ix
from clark import ask_index

QUESTION = "when is the zebrafish tank cleaned"


class StopWords(Base):
    def setUp(self):
        super().setUp()
        self.put("tank.txt", "The zebrafish tank is cleaned on Tuesdays.")
        self.put("other.txt", "The quokka enclosure opens at nine.")
        self.build()

    def labels(self, question):
        return [p.label if hasattr(p, "label") else p[0] for p in ix.search(self.data, "P1", question)]

    def test_a_file_that_shares_only_common_words_with_the_question_is_not_found(self):
        got = self.labels(QUESTION)
        self.assertEqual(len(got), 1, got)
        self.assertIn("tank.txt", got[0])

    def test_a_question_made_only_of_common_words_finds_nothing_and_does_not_crash(self):
        for q in ("when is the", "what is this", "THE", "is it the", ""):
            self.assertEqual(ix.search(self.data, "P1", q), [], q)

    def test_a_word_that_is_not_common_still_finds_its_file(self):
        self.assertEqual(len(self.labels("quokka")), 1)
        self.assertEqual(len(self.labels("When does the QUOKKA enclosure open")), 1)

    def test_the_list_of_common_words_has_no_word_a_person_would_search_for(self):
        for w in ("zebrafish", "tank", "risk", "budget", "owner", "plan", "date", "open", "report", "client", "project"):
            self.assertNotIn(w, ask_index.STOP_WORDS)


if __name__ == "__main__":
    unittest.main()
