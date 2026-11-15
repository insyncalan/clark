"""Item 1202: every peek starts below the nav banner and runs to the bottom of the screen. Run: python3 dev/run_tests.py test_peek_below_banner_1202

Read from the stylesheet: the item peek's rule starts at the banner's height (--topbar), stays flush right and to the bottom,
and has no inset and no rounded outer corners. Not run in a browser.
"""
import re
import unittest

from _paths import ROOT

CSS = (ROOT / "src" / "clark" / "page" / "shell.css").read_text(encoding="utf-8")


def rule(selector):
    m = re.search(r"^" + re.escape(selector) + r" \{([^}]*)\}", CSS, re.M)
    assert m, selector
    return m.group(1)


class PeekBelowBanner(unittest.TestCase):
    def test_starts_below_the_banner(self):
        body = rule(".peek")
        self.assertRegex(body, r"top:\s*var\(--topbar\)")
        self.assertRegex(body, r"right:\s*0[;\s]")
        self.assertRegex(body, r"bottom:\s*0[;\s]")

    def test_no_inset_and_no_rounded_corners(self):
        body = rule(".peek")
        self.assertNotIn("border-radius", body)
        self.assertNotRegex(body, r"top:\s*(0|16px)\b")


if __name__ == "__main__":
    unittest.main()
