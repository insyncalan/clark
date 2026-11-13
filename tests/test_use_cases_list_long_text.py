"""The Use cases list keeps long text inside the page: the no-match message wraps, and the headline and milestone cells stop at two lines."""
import re
import unittest

from _paths import SRC

CSS = (SRC / "clark" / "page" / "src" / "edit" / "edit.css").read_text(encoding="utf-8")


def rule(selector):
    return " ".join(re.findall(r"(?m)^\s*" + re.escape(selector) + r" \{([^}]*)\}", CSS))


class LongText(unittest.TestCase):
    def test_no_match_message_wraps(self):
        self.assertIn("overflow-wrap: anywhere", rule(".ucl-none"))

    def test_headline_and_milestones_clamp_to_two_lines(self):
        body = rule(".ucl-head, .ucl-ms")
        self.assertIn("-webkit-line-clamp: 2", body)
        self.assertIn("overflow: hidden", body)

    def test_narrow_headline_small_clamps(self):
        narrow = CSS[CSS.index("@media (max-width: 1100px)"):]
        self.assertRegex(narrow, r"\.ucl-name small \{[^}]*-webkit-line-clamp: 2")


if __name__ == "__main__":
    unittest.main()
