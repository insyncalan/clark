"""Row 1293 (AP12): the cost of one question at the budget, pinned as three arithmetic figures. At 1,200,000 characters (300,000 tokens, 4
characters each), input only, at list prices (not a bill): Sonnet 5.5 $0.60, Opus 5.5 $1.20, Fable 5.2 $2.40 (the figures of the cost check on
row 1293). This row builds no cap and no brake: nothing here compares a figure with a limit.

Run: python3 dev/run_tests.py test_ask_cost_at_budget_1293
"""
import unittest
from decimal import Decimal

from _paths import SRC  # noqa: F401
from clark import ask, settings

PER_MILLION_INPUT_TOKENS = {"Sonnet 5.5": Decimal("2.00"), "Opus 5.5": Decimal("4.00"), "Fable 5.2": Decimal("8.00")}      # list price in dollars for 1,000,000 input tokens


class Cost(unittest.TestCase):
    def test_cost_at_the_budget_is_the_three_list_price_figures(self):
        tokens = ask.BUDGET // settings.ASK_SIZE_CHARS_PER_TOKEN
        self.assertEqual((ask.BUDGET, tokens, settings.ASK_SIZE_DEFAULT), (1_200_000, 300_000, 300_000))
        cost = {m: (Decimal(tokens) * price / 1_000_000).quantize(Decimal("0.01")) for m, price in PER_MILLION_INPUT_TOKENS.items()}
        self.assertEqual(cost, {"Sonnet 5.5": Decimal("0.60"), "Opus 5.5": Decimal("1.20"), "Fable 5.2": Decimal("2.40")})


if __name__ == "__main__":
    unittest.main()
