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

    def test_a_project_over_the_character_budget_is_cut_by_the_budget(self):
        # 400 passages of the largest size (4,000 characters) is 1,600,000 characters, over the 1,200,000 budget. build_request cannot
        # hold that many (its count ceiling is 60 passages), so the budget cut is run as the request builder runs it: choose() at BUDGET.
        size = ask.MAX_PASSAGE
        chosen = [("notes/p%03d.md" % i, ("filler %d " % i).ljust(size, "x")) for i in range(400)]
        chosen[399] = ("notes/last.md", "late late late ".ljust(size, "x"))      # the most relevant one is the last in the list
        self.assertGreater(sum(len(t) for _l, t in chosen), ask.BUDGET)
        keep, more = ask.choose(chosen, "What is late?", ask.BUDGET, len(chosen))
        self.assertEqual(len(keep), ask.BUDGET // size)                        # 300 fit
        self.assertEqual(more, 400 - len(keep))                                # the other 100 are counted as left out
        self.assertLessEqual(sum(len(chosen[i][1]) for i in keep), ask.BUDGET)
        self.assertIn(399, keep)                                               # the relevant one stays although it came last
        self.assertEqual(keep, sorted(keep))                                   # in their original order
        exact = ask.choose(chosen[:300], "What is late?", ask.BUDGET, 300)     # exactly the budget: all stay
        self.assertEqual((len(exact[0]), exact[1]), (300, 0))
        over = ask.choose(chosen[:301], "What is late?", ask.BUDGET, 301)      # one character over is not allowed
        self.assertEqual((len(over[0]), over[1]), (300, 1))

    def test_one_passage_over_the_ceiling_is_left_out_and_counted(self):
        at = ("a" * ask.MAX_PASSAGE, "b" * (ask.MAX_PASSAGE + 1), "c" * (ask.MAX_PASSAGE + 50))
        r = ask.build_request("What is late?", [("notes/at.md", at[0]), ("notes/over1.md", at[1]), ("notes/over2.md", at[2])])
        self.assertEqual((len(r.passages), r.kept, r.left_out), (1, (0,), 2))   # the one at the ceiling is sent; each one over it adds one
        self.assertIn("notes/at.md", r.text)
        self.assertNotIn("notes/over1.md", r.text)

    def test_when_the_text_is_still_too_long_the_least_relevant_passage_goes_first_and_is_counted(self):
        body = lambda w: (w + " ").ljust(1000, "x")
        passages = [("notes/first.md", body("alpha")), ("notes/late.md", body("late")), ("notes/other.md", body("zzz"))]
        full = ask.build_request("What is late?", passages)
        self.assertEqual((full.kept, full.left_out), ((0, 1, 2), 0))
        two = ask.build_request("What is late?", passages, max_request=len(full.text) - 1)
        self.assertEqual((two.kept, two.left_out), ((0, 1), 1))                 # the one that does not match the question went, and only one
        self.assertEqual(len(two.passages), 2)
        self.assertNotIn("notes/other.md", two.text)
        one = ask.build_request("What is late?", passages, max_request=len(two.text) - 1)
        self.assertEqual((one.kept, one.left_out), ((0,), 2))                   # the first is always kept; the matching one goes next
        self.assertEqual(len(one.passages), 1)
        with self.assertRaises(ask.AskRefused):                                 # a single passage that does not fit is refused, not emptied
            ask.build_request("What is late?", passages[:1], max_request=len(one.text) - 1)
        with self.assertRaises(ask.AskRefused):
            ask.build_request("What is late?", passages[:1], max_request=10)

    def test_a_file_added_to_the_question_goes_last_even_when_it_shares_no_word_with_the_question(self):
        body = lambda w: (w + " ").ljust(1000, "x")
        passages = [("project", body("alpha")), ("notes/a.md", body("zzz")), ("notes/b.md", body("yyy")), ("notes/c.md", body("xxx")), ("upload.txt", body("qqq"))]
        full = ask.build_request("What is late?", passages, files=1)
        cut = ask.build_request("What is late?", passages, max_request=len(full.text) - 1, files=1)
        self.assertEqual((cut.kept, cut.left_out), ((0, 1, 2, 4), 1))           # item 1292: a folder passage went, the file stayed (the file is last, so a tie used to cut it first)
        self.assertIn("upload.txt", cut.text)
        every = ask.build_request("What is late?", passages, max_request=len(full.text) - 3000, files=1)
        self.assertEqual(every.kept, (0, 4))                                    # the file goes only when no other passage can
        self.assertEqual(ask.build_request("What is late?", passages, max_request=len(full.text) - 4000, files=1).kept, (0,))      # then the file goes, never the first passage
        self.assertEqual(ask.build_request("What is late?", passages, max_request=len(full.text) - 1).kept, (0, 1, 2, 3))      # no files named: unchanged

    def test_earlier_turns_go_before_any_passage_is_left_out(self):
        passages = [("notes/a.md", "alpha " * 100), ("notes/b.md", "late " * 100)]
        earlier = [("user", "first " * 100), ("assistant", "reply " * 100)]
        full = ask.build_request("What is late?", passages, earlier=earlier)
        self.assertEqual((full.dropped_turns, full.left_out, len(full.passages)), (0, 0, 2))
        r = ask.build_request("What is late?", passages, earlier=earlier, max_request=len(full.text) - 1)
        self.assertEqual((r.dropped_turns, r.left_out, r.kept), (1, 0, (0, 1)))   # the oldest turn went, no passage did


if __name__ == "__main__":
    unittest.main()
