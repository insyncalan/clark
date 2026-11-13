"""Every input and textarea placeholder uses the muted text colour, so none falls back to the browser grey (3.1:1 on the dark surface).

Run: python3 dev/run_tests.py test_placeholder_colour
"""
import re
import unittest

from _paths import ROOT

SHELL = ROOT / "src" / "clark" / "page" / "shell.css"


class PlaceholderColour(unittest.TestCase):
    def test_global_placeholder_rule(self):
        css = SHELL.read_text(encoding="utf-8")
        m = re.search(r"(?m)^input::placeholder,\s*textarea::placeholder\s*\{([^}]*)\}", css)
        self.assertIsNotNone(m, "no global input/textarea placeholder rule in shell.css")
        self.assertIn("color: var(--text-muted)", m.group(1))
        self.assertIn("opacity: 1", m.group(1))


if __name__ == "__main__":
    unittest.main()
