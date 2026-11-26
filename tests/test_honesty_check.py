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


class CountsTest(unittest.TestCase):
    def test_tests_are_named_by_class_and_function(self):
        self.assertEqual(hc.tests_in(TEST_MOD), {"ModTest.test_double", "ModTest.test_double_negative"})
        self.assertEqual(hc.tests_in("def test_plain():\n    assert True\n\ndef helper():\n    pass\n"), {"test_plain"})

    def test_asserts_count_statements_and_assert_methods(self):
        self.assertEqual(hc.asserts_in(TEST_MOD), 3)
        self.assertEqual(hc.asserts_in("def test_a():\n    assert 1\n    assert 2\n"), 2)

    def test_skip_markers_are_counted_in_every_form(self):
        src = ("import unittest\n\n\nclass A(unittest.TestCase):\n"
               "    @unittest.skip('later')\n    def test_a(self):\n        pass\n\n"
               "    @unittest.skipIf(True, 'x')\n    def test_b(self):\n        pass\n\n"
               "    @unittest.expectedFailure\n    def test_c(self):\n        pass\n\n"
               "    def test_d(self):\n        self.skipTest('no')\n\n"
               "    def test_e(self):\n        raise unittest.SkipTest('no')\n")
        self.assertEqual(hc.skips_in(src), 5)
        self.assertEqual(hc.skips_in(TEST_MOD), 0)


class FixtureDiffTest(unittest.TestCase):
    def check(self, pr):
        return hc.check(str(pr.dir), pr.base, "HEAD")

    def test_an_honest_change_passes_all_three(self):
        with PrFixture() as pr:
            pr.write("tests/test_mod.py", TEST_MOD.replace(
                "    def test_double_negative", "    def test_double_big(self):\n        self.assertEqual(mod.double(50), 100)\n\n"
                "    def test_double_negative"))
            pr.commit("one more test")
            r = self.check(pr)
            self.assertEqual(failing(r), [])
            self.assertTrue(r["ok"])
            self.assertEqual(r["files"], ["tests/test_mod.py"])

    def test_a_deleted_test_function_fails_that_check_alone(self):
        with PrFixture() as pr:
            # the two asserts move into the test that stays, so the assert count is not lower: only the deletion shows
            pr.write("tests/test_mod.py", TEST_MOD.replace(
                "    def test_double_negative(self):\n        self.assertEqual(mod.double(-1), -2)\n",
                "    def helper(self):\n        self.assertEqual(mod.double(-1), -2)\n"))
            pr.commit("drop a test")
            r = self.check(pr)
            self.assertEqual(failing(r), ["deleted"])
            self.assertEqual(r["deleted"], ["tests/test_mod.py: ModTest.test_double_negative"])
            self.assertFalse(r["ok"])

    def test_a_deleted_test_file_fails_the_deleted_check(self):
        with PrFixture() as pr:
            pr.remove("tests/test_mod.py")
            pr.commit("drop the file")
            r = self.check(pr)
            self.assertEqual(failing(r), ["deleted"])
            self.assertEqual(len(r["deleted"]), 2)

    def test_a_test_moved_to_another_changed_file_is_not_deleted(self):
        with PrFixture() as pr:
            pr.git("mv", "tests/test_mod.py", "tests/test_mod_moved.py")
            pr.commit("rename the file")
            self.assertEqual(failing(self.check(pr)), [])

    def test_an_added_skip_fails_that_check_alone(self):
        with PrFixture() as pr:
            pr.write("tests/test_mod.py", TEST_MOD.replace(
                "    def test_double_negative", "    @unittest.skip('flaky')\n    def test_double_negative"))
            pr.commit("skip one")
            r = self.check(pr)
            self.assertEqual(failing(r), ["skips"])
            self.assertEqual(r["skips"], ["tests/test_mod.py: 0 -> 1"])

    def test_an_added_expected_failure_fails_the_skip_check(self):
        with PrFixture() as pr:
            pr.write("tests/test_mod.py", TEST_MOD.replace(
                "    def test_double_negative", "    @unittest.expectedFailure\n    def test_double_negative"))
            pr.commit("xfail one")
            self.assertEqual(failing(self.check(pr)), ["skips"])

    def test_a_skip_in_a_new_test_file_is_a_new_skip(self):
        with PrFixture() as pr:
            pr.write("tests/test_new.py", "import unittest\n\n\nclass N(unittest.TestCase):\n"
                                          "    def test_n(self):\n        self.skipTest('later')\n")
            pr.commit("new file that skips")
            self.assertEqual(failing(self.check(pr)), ["skips"])

    def test_fewer_asserts_fails_that_check_alone(self):
        with PrFixture() as pr:
            pr.write("tests/test_mod.py", TEST_MOD.replace("        self.assertEqual(mod.double(0), 0)\n", ""))
            pr.commit("one assert fewer")
            r = self.check(pr)
            self.assertEqual(failing(r), ["asserts"])
            self.assertEqual(r["asserts"], ["tests/test_mod.py: 3 -> 2"])

    def test_a_change_outside_tests_is_not_read(self):
        with PrFixture() as pr:
            pr.write("src/clark/mod.py", "def double(n):\n    return n + n\n")
            pr.commit("code only")
            r = self.check(pr)
            self.assertTrue(r["ok"])
            self.assertEqual(r["files"], [])

    def test_a_test_file_that_does_not_parse_is_not_a_pass(self):
        with PrFixture() as pr:
            pr.write("tests/test_mod.py", "def test_x(:\n")
            pr.commit("broken")
            r = self.check(pr)
            self.assertFalse(r["ok"])
            self.assertEqual(r["errors"], ["tests/test_mod.py: does not parse"])


class CommandTest(unittest.TestCase):
    def run_main(self, pr):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = hc.main(["--repo", str(pr.dir), "--base", pr.base])
        return code, out.getvalue()

    def test_exit_0_and_one_line_per_check_on_a_pass(self):
        with PrFixture() as pr:
            pr.write("src/clark/mod.py", "def double(n):\n    return n + n\n")
            pr.commit("code only")
            code, out = self.run_main(pr)
            self.assertEqual(code, 0)
            self.assertIn("no test deleted: pass", out)
            self.assertIn("no new skip or xfail: pass", out)
            self.assertIn("assert count not lower: pass", out)
            self.assertIn("Test honesty: passed", out)

    def test_exit_1_and_the_failing_check_named(self):
        with PrFixture() as pr:
            pr.write("tests/test_mod.py", TEST_MOD.replace("        self.assertEqual(mod.double(0), 0)\n", ""))
            pr.commit("one assert fewer")
            code, out = self.run_main(pr)
            self.assertEqual(code, 1)
            self.assertIn("assert count not lower: FAIL", out)
            self.assertIn("tests/test_mod.py: 3 -> 2", out)
            self.assertIn("no test deleted: pass", out)
            self.assertIn("Test honesty: FAILED", out)

    def test_exit_2_when_the_base_is_not_a_commit(self):
        with PrFixture() as pr:
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = hc.main(["--repo", str(pr.dir), "--base", "no-such-ref"])
            self.assertEqual(code, 2)
            self.assertIn("not checked", out.getvalue())


if __name__ == "__main__":
    unittest.main()
