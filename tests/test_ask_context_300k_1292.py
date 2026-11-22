"""Row 1292, point 9: a project over 300,000 tokens is cut by relevance, with a left-out line, and not refused.

Run: python3 dev/run_tests.py test_ask_context_300k_1292
Fictional data only. No file, network or process is used.
"""
import unittest

from _paths import SRC  # noqa: F401  (puts src/ on the path)
from clark import ask


class OverTheBudget(unittest.TestCase):
    def test_over_300000_tokens_is_cut_not_refused(self):
        # a project bigger than the window: 70 passages of 3,300 characters is 231,000 characters, so the count
        # ceiling cuts it, and a request cap of 100,000 characters (a smaller model window) cuts it again; neither refuses.
        passages = [ask.Passage("notes/p%02d.md" % i, ("passage %d " % i) * 300) for i in range(70)]
        self.assertTrue(all(len(p.text) <= ask.MAX_PASSAGE for p in passages))
        r = ask.build_request("What is late?", passages)                       # over the count ceiling: cut by relevance, not refused
        self.assertEqual((len(r.passages), r.left_out), (ask.MAX_PASSAGES, 70 - ask.MAX_PASSAGES))
        small = ask.build_request("What is late?", passages, max_request=100000)
        self.assertGreaterEqual(len(small.passages), 1)
        self.assertLess(len(small.passages), ask.MAX_PASSAGES)
        self.assertLessEqual(len(small.text), 100000)
        self.assertEqual(small.left_out, 70 - len(small.passages))
        self.assertIn(str(small.left_out), ask.left_out_text(small.left_out))   # the panel says how many were left out
        with self.assertRaises(ask.AskRefused):                                 # refused only when not even one passage fits
            ask.build_request("What is late?", passages, max_request=2000)


if __name__ == "__main__":
    unittest.main()
