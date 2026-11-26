"""The test-honesty script (dev/tools/honesty_check.py): three separate checks on the test files a change touches. No test is
deleted, no skip or expected failure is added, and the assert count of a touched test file is not lower. Each fixture diff
fails its own check alone; an honest change passes all three.

Run: python3 dev/run_tests.py test_honesty_check   (quick tier)
"""
import contextlib
import io
import unittest

from _paths import ROOT  # noqa: F401  (puts dev/tools on the path)
from _pr_fixture import PrFixture, TEST_MOD

import honesty_check as hc


def failing(result):
    """The names of the checks that failed."""
    return sorted(k for k in ("deleted", "skips", "asserts") if result[k])


class FixtureDiffTest(unittest.TestCase):
    """One fixture diff per check: each fails its own check alone, and an honest change passes all three."""
    def result(self, old, new):
        with PrFixture() as pr:
            pr.write("tests/test_mod.py", TEST_MOD.replace(old, new))
            pr.commit("change")
            return hc.check(str(pr.dir), pr.base, "HEAD")

    def test_each_fixture_diff_fails_its_own_check_alone(self):
        honest = self.result("    def test_double_negative", "    def test_double_big(self):\n        self.assertEqual(mod.double(50), 100)\n\n"
                             "    def test_double_negative")
        self.assertEqual((failing(honest), honest["ok"], honest["files"]), ([], True, ["tests/test_mod.py"]))
        # the asserts of the deleted test move into a helper, so the assert count is not lower: only the deletion shows
        deleted = self.result("    def test_double_negative(self):\n        self.assertEqual(mod.double(-1), -2)\n",
                              "    def helper(self):\n        self.assertEqual(mod.double(-1), -2)\n")
        self.assertEqual(failing(deleted), ["deleted"])
        self.assertEqual(deleted["deleted"], ["tests/test_mod.py: ModTest.test_double_negative"])
        for marker in ("@unittest.skip('flaky')", "@unittest.expectedFailure"):
            skipped = self.result("    def test_double_negative", "    %s\n    def test_double_negative" % marker)
            self.assertEqual(failing(skipped), ["skips"])
            self.assertEqual(skipped["skips"], ["tests/test_mod.py: 0 -> 1"])
        fewer = self.result("        self.assertEqual(mod.double(0), 0)\n", "")
        self.assertEqual(failing(fewer), ["asserts"])
        self.assertEqual(fewer["asserts"], ["tests/test_mod.py: 3 -> 2"])

    def test_the_command_names_the_failing_check_and_cannot_check_is_exit_2(self):
        with PrFixture() as pr:
            pr.write("tests/test_mod.py", TEST_MOD.replace("        self.assertEqual(mod.double(0), 0)\n", ""))
            pr.commit("one assert fewer")
            for base, code, words in ((pr.base, 1, ("assert count not lower: FAIL", "tests/test_mod.py: 3 -> 2", "no test deleted: pass",
                                                    "Test honesty: FAILED")), ("no-such-ref", 2, ("not checked",))):
                out = io.StringIO()
                with contextlib.redirect_stdout(out):
                    self.assertEqual(hc.main(["--repo", str(pr.dir), "--base", base]), code)
                for word in words:
                    self.assertIn(word, out.getvalue())


if __name__ == "__main__":
    unittest.main()
