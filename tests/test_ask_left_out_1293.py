"""Row 1293 AP9 / DoD9: the person sees "N items read, M left out." and, only when M is above 0, "A higher size of one question in Settings reads more."

Run: python3 dev/run_tests.py test_ask_left_out_1293
Quick tier: no browser. The server's counts (ask_data.read_counts) feed the page's words (askWords.js READ_LINE) in node (skips without node).
"""
import json
import unittest

import test_ask_cite_logic_1292 as L
from clark import ask_data

MORE = "A higher size of one question in Settings reads more."


def line_for(counts):
    read = ask_data.read_counts(ask_data.ProjectData((), {}, 0, 0, "17-11-2026", counts))
    return L.words(f"W.READ_LINE({json.dumps(read)})")


class LeftOut(unittest.TestCase):
    def test_the_person_sees_n_read_and_m_left_out(self):
        got = line_for((("actions", 5, 9), ("raid", 2, 2), ("decisions", 1, 1), ("milestones", 3, 4), ("use_cases", 0, 2)))
        self.assertEqual(got, f"11 items read, 7 left out. {MORE}")

    def test_a_project_sent_whole_has_no_second_sentence(self):
        got = line_for((("actions", 5, 5), ("milestones", 3, 3)))
        self.assertNotIn(MORE, got)
        self.assertNotIn("left out", got)


if __name__ == "__main__":
    unittest.main()
