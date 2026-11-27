"""Mergify probe, step 0 (throw-away, deleted after the probe): does the CI runner hand GITHUB_HEAD_REF to the tests? It FAILS on purpose with the value in its message (a passing test's output is not in the log),
so the run log of the PR shows what a test can read. Run: python3 dev/run_tests.py test_zz_mergify_probe_env"""
import os
import unittest


class Env(unittest.TestCase):
    def test_print_the_head_ref_the_runner_gives(self):
        print("PROBE GITHUB_HEAD_REF=%r GITHUB_EVENT_NAME=%r" % (os.environ.get("GITHUB_HEAD_REF"), os.environ.get("GITHUB_EVENT_NAME")))
        self.fail("PROBE (this failure is the point, never queued) GITHUB_HEAD_REF=%r GITHUB_EVENT_NAME=%r" % (os.environ.get("GITHUB_HEAD_REF"), os.environ.get("GITHUB_EVENT_NAME")))


if __name__ == "__main__":
    unittest.main()
