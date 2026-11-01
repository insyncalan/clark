"""The growth check (tests/_growth.py) is only worth trusting if it passes a linear cost and fails a quadratic and a cubic one (known
pure-Python costs) with a clear margin on both sides of the limit, and if its floor is the same wherever a test keeps its own copy."""
import re
import unittest
import unittest.mock

from _paths import ROOT
import _growth
from _growth import ABSOLUTE_CAP, GROWTH_FLOOR, GROWTH_LIMIT, GROWTH_STEP, assert_growth, growth_ratio


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


class TheCopyKeepsTheSameFloor(unittest.TestCase):
    """tests/test_publish_public.py keeps its own copy of the helper (its owner reviews changes to it), still measuring n and 2n with a
    limit of 3.5. Only the floor is the same as the shared one; the shared limit and step are asserted above, and the copy is for its
    owner to bring across."""
    def test_the_copy_in_test_publish_public_has_the_same_floor_and_the_same_signature(self):
        text = (ROOT / "tests" / "test_publish_public.py").read_text(encoding="utf-8")
        found = re.findall(r"^GROWTH_FLOOR = ([0-9.]+)", text, re.M)
        self.assertEqual([float(v) for v in found], [GROWTH_FLOOR])
        self.assertIn("def growth_ratio(work, n, tries=3):", text)


if __name__ == "__main__":
    unittest.main()
