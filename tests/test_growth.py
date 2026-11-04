"""The growth check (tests/_growth.py) is only worth trusting if it passes a linear cost and fails a quadratic and a cubic one (known
pure-Python costs) with a clear margin on both sides of the limit."""
import unittest
import unittest.mock

import _growth
from _growth import ABSOLUTE_CAP, GROWTH_LIMIT, GROWTH_STEP, assert_growth, assert_near_baseline, growth_ratio


def linear(n):
    total = 0
    for i in range(n * 400000):
        total += i
    return total


def quadratic(n):
    total = 0
    for i in range(n):
        for j in range(n):
            total += 1
    return total


def cubic(n):
    total = 0
    for i in range(n):
        for j in range(n):
            for k in range(n):
                total += 1
    return total


class TheGrowthCheckTellsLinearFromQuadratic(unittest.TestCase):
    # Linear measures 4 and quadratic 16 (the step is 4n), the limit is 8: each is a factor of two from it. The margins asserted here are
    # looser than that (linear under three quarters of the limit, quadratic over one and a half times it) so a busy machine does not fail
    # this test, but a limit moved back towards the old 3.5 for a step of 2 would still be caught.
    def test_the_step_and_the_limit_leave_a_gap_of_two_each_way(self):
        self.assertEqual(GROWTH_STEP, 4)
        self.assertEqual(GROWTH_LIMIT, 2 * GROWTH_STEP)
        self.assertEqual(GROWTH_STEP ** 2, 2 * GROWTH_LIMIT)

    def test_linear_work_passes_and_quadratic_and_cubic_work_fail_the_limit(self):
        linear_ratio = growth_ratio(linear, 3)[2]
        quadratic_ratio = growth_ratio(quadratic, 1000)[2]
        cubic_ratio = growth_ratio(cubic, 70)[2]
        print("linear ratio=%.2f quadratic ratio=%.2f cubic ratio=%.2f (limit %s)" % (linear_ratio, quadratic_ratio, cubic_ratio, GROWTH_LIMIT))
        self.assertLessEqual(linear_ratio, GROWTH_LIMIT * 0.75)
        self.assertGreater(quadratic_ratio, GROWTH_LIMIT * 1.5)
        self.assertGreater(cubic_ratio, GROWTH_LIMIT * 1.5)

    def test_assert_growth_passes_linear_and_fails_quadratic_and_cubic(self):
        assert_growth(self, linear, 3, "linear")
        for name, work, n in (("quadratic", quadratic, 1000), ("cubic", cubic, 70)):
            with self.assertRaises(AssertionError):
                assert_growth(self, work, n, name)

    def test_a_linear_cost_over_the_absolute_cap_fails(self):
        with unittest.mock.patch.object(_growth, "ABSOLUTE_CAP", 0.0005), unittest.mock.patch.object(_growth, "GROWTH_LIMIT", 1000):
            with self.assertRaises(AssertionError) as caught:
                assert_growth(self, linear, 3, "slow but linear")
        self.assertIn("absolute cap", str(caught.exception))
        self.assertGreater(ABSOLUTE_CAP, 1)


class TheNearBaselineCheckTellsQuadraticFromPlain(unittest.TestCase):
    def test_a_hostile_input_as_quick_as_a_plain_one_passes_and_a_quadratic_one_fails(self):
        assert_near_baseline(self, lambda: linear(1), lambda: linear(1), "same")
        with self.assertRaises(AssertionError):
            assert_near_baseline(self, lambda: quadratic(7000), lambda: linear(1), "quadratic")


if __name__ == "__main__":
    unittest.main()
