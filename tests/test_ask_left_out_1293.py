"""Row 1293 AP9: the person sees how many were read and how many left out, and, only when some were left out, "A higher size of one question in
Settings reads more." (the ticket's second sentence; the first part is the read line, askWords.js READ_LINE, with the left-out lines of the notes).

Run: python3 dev/run_tests.py test_ask_left_out_1293
Quick tier: no browser; the line is run in node (skips without node). Fictional data only.
"""
import unittest

from test_ask_1367 import read
from test_ask_cite_logic_1292 import words

from clark import ask, ask_data

SECOND = "A higher size of one question in Settings reads more."


class LeftOut(unittest.TestCase):
    def test_the_person_sees_n_read_and_m_left_out(self):
        tight, _ = read(budget=1500)
        counts = ask_data.read_counts(tight)
        m = sum(total - sent for _k, sent, total in tight.counts)
        self.assertGreater(m, 0, "a tight budget leaves rows out")
        self.assertEqual(counts["left_out"], m, "M is exactly the rows cut")
        self.assertGreater(counts["work_items"] + counts["milestones"] + counts["use_cases"], 0, "N is what was read")
        shown = words("W.READ_LINE(%s)" % __import__("json").dumps(counts))
        self.assertIn(" read", shown)
        self.assertTrue(shown.endswith(". " + SECOND), shown)
        self.assertTrue(ask_data.left_out_lines(tight.counts), "the notes say the same in words")

    def test_nothing_left_out_says_no_second_sentence(self):
        whole, _ = read()
        counts = ask_data.read_counts(whole)
        self.assertEqual(counts["left_out"], 0)
        self.assertNotIn(SECOND, words("W.READ_LINE(%s)" % __import__("json").dumps(counts)))
        self.assertEqual(words('W.READ_LINE({work_items:3,milestones:0,use_cases:0,as_at:"",left_out:2})'), "3 work items read. " + SECOND)
        self.assertEqual(words('[W.READ_LINE({work_items:3,left_out:0}), W.READ_LINE({work_items:3,left_out:"2"}), W.READ_LINE({work_items:0,left_out:5})]'),
                         ["3 work items read", "3 work items read", ""])


if __name__ == "__main__":
    unittest.main()
