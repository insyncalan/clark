"""Row 1293 AP12: a question at the budget (1,200,000 characters, 300,000 tokens) is held to the token cap.

On main there is no dollar cap on a question (ask_claude.py: "no per-question cost cap, the person has a plan"), and the ticket records no ruling on
one (AP12 open question), so no dollar figure is pinned here. What is pinned is the real brake: a question stuffed to the budget and beyond is cut
to it, the whole request stays within MAX_REQUEST, and its size in tokens (4 characters each) is no more than 300,000 plus the fixed overhead.

Run: python3 dev/run_tests.py test_ask_cost_at_budget_1293
Quick tier: no browser. Fictional data only.
"""
import unittest

from clark import ask

TOKENS = 4


class Cost(unittest.TestCase):
    def test_cost_at_the_budget_stays_under_the_cap(self):
        self.assertEqual(ask.BUDGET, 1_200_000)
        passages = [("Item %d" % i, ("w%d " % i) * 150) for i in range(ask.MAX_PASSAGES)]       # more than a small project
        request = ask.build_request("What is open?", passages, budget=ask.BUDGET)
        self.assertLessEqual(len(request.text), ask.MAX_REQUEST)
        self.assertLessEqual(len(request.text) / TOKENS, 300_000 + ask.REQUEST_OVERHEAD / TOKENS)
        flood = [("Item %d" % i, "x" * 1100) for i in range(ask.MAX_PASSAGES)]
        small = ask.build_request("What is open?", flood, budget=40_000)      # a lower size is held to as well
        self.assertLessEqual(sum(len(p) for p in [small.text]), 40_000 + ask.REQUEST_OVERHEAD)
        self.assertGreater(small.left_out, 0)


if __name__ == "__main__":
    unittest.main()
