"""Mergify probe, D2 step 3 (throw-away, deleted after the probe): the red probe of 27-11 (this file asserted that the head ref does not start with
mergify/merge-queue/, so it was red only on Mergify's draft) is now GREEN on the draft too, to see the PR go back through the queue and merge.
Run: python3 dev/run_tests.py test_zz_mergify_probe_red"""
import os
import unittest


class Green(unittest.TestCase):
    def test_green_on_the_pr_and_on_the_mergify_queue_draft(self):
        ref = os.environ.get("GITHUB_HEAD_REF", "")
        self.assertTrue(isinstance(ref, str), "PROBE step 3 green on purpose: head ref %r" % ref)


if __name__ == "__main__":
    unittest.main()
