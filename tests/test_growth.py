"""The growth check (tests/_growth.py) is only worth trusting if it passes a linear cost and fails a cubic one (known pure-Python costs),
and if its limits are the same wherever a test keeps its own copy."""
import re
import unittest
import unittest.mock

from _paths import ROOT
import _growth
from _growth import ABSOLUTE_CAP, GROWTH_LIMIT, assert_growth, growth_ratio


def linear(n):
    total = 0
    for i in range(n * 400000):
        total += i
    return total


def cubic(n):
    total = 0
    for i in range(n):
        for j in range(n):
            for k in range(n):
                total += 1
    return total


class TheGrowthCheckTellsLinearFromCubic(unittest.TestCase):
    def test_linear_work_passes_and_cubic_work_fails_the_limit(self):
        self.assertLessEqual(growth_ratio(linear, 3)[2], GROWTH_LIMIT)
        self.assertGreater(growth_ratio(cubic, 160)[2], GROWTH_LIMIT)

    def test_assert_growth_passes_linear_and_fails_cubic(self):
        assert_growth(self, linear, 3, "linear")
        with self.assertRaises(AssertionError):
            assert_growth(self, cubic, 160, "cubic")

    def test_a_linear_cost_over_the_absolute_cap_fails(self):
        with unittest.mock.patch.object(_growth, "ABSOLUTE_CAP", 0.0005), unittest.mock.patch.object(_growth, "GROWTH_LIMIT", 1000):
            with self.assertRaises(AssertionError) as caught:
                assert_growth(self, linear, 3, "slow but linear")
        self.assertIn("absolute cap", str(caught.exception))
        self.assertGreater(ABSOLUTE_CAP, 1)


class NoCopyHasDifferentLimits(unittest.TestCase):
    """tests/test_publish_public.py keeps its own copy of the helper (its owner reviews changes to it): its limits must match the shared ones."""
    def test_the_copy_in_test_publish_public_has_the_same_limit_and_floor(self):
        text = (ROOT / "tests" / "test_publish_public.py").read_text(encoding="utf-8")
        for name in ("GROWTH_LIMIT", "GROWTH_FLOOR"):
            found = re.findall(r"^%s = ([0-9.]+)" % name, text, re.M)
            self.assertEqual([float(v) for v in found], [getattr(_growth, name)], name)
        self.assertIn("def growth_ratio(work, n, tries=3):", text)


if __name__ == "__main__":
    unittest.main()
