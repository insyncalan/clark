"""The dev instance wears a DEV COPY tab (CLARK_DEV=1, set by dev-clark.command); production never does.

Run: python3 dev/run_tests.py test_dev_marker
"""
import os
import unittest
from unittest import mock

from _paths import SRC  # noqa: F401  (puts src on the path)
from clark import server as sv

PAGE = "<!doctype html><html><head><title>clark</title></head><body><p>x</p></body></html>"


class Marker(unittest.TestCase):
    def test_production_has_no_marker(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CLARK_DEV", None)
            out = sv.with_boot(PAGE)
        self.assertNotIn("DEV COPY", out)
        self.assertIn("<title>clark</title>", out)

    def test_only_the_exact_value_one_turns_it_on(self):
        for v in ("0", "", "true", "yes"):
            with mock.patch.dict(os.environ, {"CLARK_DEV": v}):
                self.assertNotIn("DEV COPY", sv.with_boot(PAGE), v)

    def test_dev_has_the_ribbon_and_title(self):
        with mock.patch.dict(os.environ, {"CLARK_DEV": "1"}):
            out = sv.with_boot(PAGE)
        self.assertIn('id="clark-dev-ribbon"', out)
        self.assertIn("DEV COPY", out)
        self.assertIn("<title>DEV clark</title>", out)
        self.assertLess(out.index("clark-dev-ribbon"), out.index("<p>x</p>"))     # first thing in the body

    def test_the_policy_still_covers_the_page(self):
        """The ribbon is a style attribute, so it adds no inline script or style that would need a hash."""
        with mock.patch.dict(os.environ, {"CLARK_DEV": "1"}):
            on = sv.csp_policy(sv.with_boot(PAGE))
        os.environ.pop("CLARK_DEV", None)
        off = sv.csp_policy(sv.with_boot(PAGE))
        self.assertEqual(on, off)


if __name__ == "__main__":
    unittest.main()
