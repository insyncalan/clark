"""Item 1129: a long unbroken folder path (a copy folder with no spaces) wraps inside the Settings card instead of pushing past it.
The error line, the field hint, the field error, the buttons and the Use {path} suggestion all break anywhere.

Run: python3 dev/run_tests.py test_long_path_wrap
"""
import re
import sys
import unittest

from _paths import TOOLS

sys.path.insert(0, str(TOOLS))
import build_page  # noqa: E402


def rule(css, selector):
    return " ".join(re.findall(r"(?m)^" + re.escape(selector) + r"\s*\{([^}]*)\}", css))


class LongPathWrap(unittest.TestCase):
    css = (build_page.PAGE / "shell.css").read_text(encoding="utf-8")

    def test_these_break_anywhere(self):
        for sel in (".setting p.error", ".fld small", ".fld-bad", ".btn"):
            self.assertIn("overflow-wrap: anywhere", rule(self.css, sel), sel)

    def test_the_suggestion_button_stays_inside_the_card(self):
        body = rule(self.css, "[data-copy-suggestion]")
        self.assertIn("max-width: 100%", body)
        self.assertIn("text-align: left", body)


if __name__ == "__main__":
    unittest.main()
