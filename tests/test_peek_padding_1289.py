"""Row 1289: the peek's side padding is 20 px (the final mock-up), Classic only (rules-2.css); the shared frame in shell.css is untouched.
Run: python3 dev/run_tests.py test_peek_padding_1289.py
"""
import re
import unittest

from _paths import ROOT

T = ROOT / "src" / "clark" / "themes" / "prototype-2.0"
R2 = (T / "rules-2.css").read_text(encoding="utf-8")
SHELL = (ROOT / "src" / "clark" / "page" / "shell.css").read_text(encoding="utf-8")


class Padding(unittest.TestCase):
    def test_classic_peek_side_padding_is_20(self):
        m = re.search(r"(?m)^\.peek \{[^}]*padding:\s*var\(--space-3\) 20px var\(--space-5\);[^}]*\}", R2)
        self.assertTrue(m, "rules-2.css needs .peek { padding: var(--space-3) 20px var(--space-5); }")

    def test_the_shared_frame_keeps_its_rule(self):
        self.assertIn("padding: var(--space-3) var(--space-5) var(--space-5); }", SHELL)
        self.assertNotIn("padding", " ".join(re.findall(r"(?m)^\.peek \{[^}]*\}", (T / "rules.css").read_text(encoding="utf-8"))))


if __name__ == "__main__":
    unittest.main()
