"""Mergify probe, step 0 (throw-away, deleted after the probe): does the CI runner hand GITHUB_HEAD_REF to the tests? It always passes and prints the value,
so the run log of a PR shows what a test can read. Run: python3 dev/run_tests.py test_zz_mergify_probe_env"""
import os
import unittest


class Env(unittest.TestCase):
    def test_print_the_head_ref_the_runner_gives(self):
        print("PROBE GITHUB_HEAD_REF=%r GITHUB_EVENT_NAME=%r" % (os.environ.get("GITHUB_HEAD_REF"), os.environ.get("GITHUB_EVENT_NAME")))
        self.assertTrue(True)


if __name__ == "__main__":
    unittest.main()
