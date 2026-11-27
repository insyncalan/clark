"""Mergify probe, D2 red (throw-away, deleted after the probe): green on an ordinary PR run, red only on the run Mergify's merge queue makes on its draft PR
(branch mergify/merge-queue/<n>). Step 0 (clark#2506, 27-11) showed the runner gives tests GITHUB_HEAD_REF. Never merged by hand.
Run: python3 dev/run_tests.py test_zz_mergify_probe_red"""
import os
import unittest


class Red(unittest.TestCase):
    def test_red_only_on_the_mergify_queue_draft(self):
        ref = os.environ.get("GITHUB_HEAD_REF", "")
        self.assertFalse(ref.startswith("mergify/merge-queue/"), "PROBE red on purpose: run on Mergify's draft, head ref %r" % ref)


if __name__ == "__main__":
    unittest.main()
