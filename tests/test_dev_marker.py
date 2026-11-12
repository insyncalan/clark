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


class MarkerEdges(unittest.TestCase):
    """Mutation sweep of with_boot and dev_marked: the shapes of page the plain test page does not have."""

    def dev(self, page):
        with mock.patch.dict(os.environ, {"CLARK_DEV": "1"}):
            return sv.with_boot(page)

    def test_values_that_only_look_like_one_do_not_turn_it_on(self):
        for v in (" 1", "1 ", "10", "11", "1\n"):
            with mock.patch.dict(os.environ, {"CLARK_DEV": v}):
                self.assertNotIn("DEV COPY", sv.with_boot(PAGE), repr(v))

    def test_the_boot_block_goes_before_the_last_closing_body(self):
        page = "<html><head><title>clark</title></head><body><script>var s='</body>';</script><p>x</p></body></html>"
        out = sv.with_boot(page)
        self.assertEqual(out.count('id="clark-boot"'), 1)
        self.assertGreater(out.index('id="clark-boot"'), out.index("<p>x</p>"))
        self.assertTrue(out.endswith('</script></body></html>'))

    def test_a_page_with_no_closing_body_still_gets_the_boot_block_at_the_end(self):
        out = sv.with_boot("<html><body><p>x</p>")
        self.assertTrue(out.startswith("<html><body><p>x</p><script"))
        self.assertTrue(out.endswith("</script>"))
        self.assertEqual(out.count('id="clark-boot"'), 1)

    def test_a_body_with_attributes_gets_the_ribbon_inside_it_not_inside_the_tag(self):
        out = self.dev('<html><head><title>clark</title></head><body class="a" data-x="1"><p>x</p></body></html>')
        self.assertIn('<body class="a" data-x="1"><div id="clark-dev-ribbon"', out)

    def test_only_the_first_title_is_marked(self):
        out = self.dev("<html><head><title>clark</title></head><body><script>var t='<title>clark';</script></body></html>")
        self.assertEqual(out.count("<title>DEV clark"), 1)
        self.assertEqual(out.count("<title>clark"), 1)

    def test_a_page_with_no_body_tag_is_left_unmarked_not_given_a_stray_ribbon(self):
        out = self.dev("<html><head><title>clark</title></head></html>")
        self.assertNotIn("clark-dev-ribbon", out)
        self.assertIn("<title>DEV clark</title>", out)

    def test_a_broken_body_tag_with_no_end_is_left_alone(self):
        out = sv.dev_marked("<html><body")
        self.assertNotIn("clark-dev-ribbon", out)
        self.assertEqual(out, "<html><body")

    def test_the_ribbon_floats_on_top_and_never_takes_a_click(self):
        r = sv.DEV_RIBBON
        for part in ("position:fixed", "top:0", "left:50%", "translateX(-50%)", "z-index:2147483647", "pointer-events:none",
                     "background:#d9480f", "color:#fff"):
            self.assertIn(part, r)
        self.assertNotIn("<script", r)
        self.assertNotIn("<style", r)


if __name__ == "__main__":
    unittest.main()
