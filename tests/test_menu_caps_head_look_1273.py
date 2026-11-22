"""Row 1273: the capital-letter head of a menu (the Group by panel head and the .mh head) keeps its type size and letter spacing.

Reads shell.css (no browser): the rule for `.ddmenu .lab.caps, .mh.caps` sets the caption size and the caps tracking token, in capitals.
"""
import re
import unittest

from _paths import ROOT

CSS = re.sub(r"/\*.*?\*/", "", (ROOT / "src" / "clark" / "page" / "shell.css").read_text(encoding="utf-8"), flags=re.S)


def body_for(selector):
    for sel, body in re.findall(r"([^{}]+)\{([^{}]*)\}", CSS):
        if " ".join(sel.split()) == selector:
            return body
    return None


class MenuCapsHead(unittest.TestCase):
    def setUp(self):
        self.body = body_for(".ddmenu .lab.caps, .mh.caps")
        self.assertIsNotNone(self.body, "no rule for the caps head")

    def test_caption_size(self):
        self.assertRegex(self.body, r"font-size\s*:\s*var\(--size-caption\)")

    def test_caps_tracking(self):
        self.assertRegex(self.body, r"letter-spacing\s*:\s*var\(--tracking-caps\)")

    def test_capitals(self):
        self.assertRegex(self.body, r"text-transform\s*:\s*uppercase")


if __name__ == "__main__":
    unittest.main()
