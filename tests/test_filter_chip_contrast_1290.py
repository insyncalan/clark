"""Item 1290: the filter chip's text (brand blue) on its fill (brand tint) keeps the contrast floor in light and in dark.

Computed from the committed brand tokens, never hard-coded ratios. The floor is 4.5, the one test_dark_contrast and test_app_files use for text.
Run: python3 dev/run_tests.py test_filter_chip_contrast_1290
"""
import re
import unittest

from _paths import ROOT
from test_dark_contrast import dark_blocks, ratio

TOKENS = (ROOT / "src" / "clark" / "brand" / "tokens.css").read_text(encoding="utf-8")
FLOOR = 4.5


def light_token(name):
    m = re.search(r":root\s*\{(.*?)\n\s*\}", TOKENS, re.S)
    return re.search(name + r":\s*(#[0-9A-Fa-f]{6})", m.group(1)).group(1).upper()


class FilterChipContrast(unittest.TestCase):
    def test_light_chip_text_on_the_tint(self):
        r = ratio(light_token("--brand-blue"), light_token("--brand-blue-tint"))
        print(f"1290 chip text contrast, light: {r:.2f}:1")
        self.assertGreaterEqual(r, FLOOR)

    def test_every_dark_block_chip_text_on_the_tint(self):
        # dark chip text is --brand-blue-strong (--brand-blue itself measures 4.18:1 on the tint and stays as it is)
        blocks = dark_blocks(TOKENS)
        self.assertTrue(blocks)
        for b in blocks:
            r = ratio(b["--brand-blue-strong"], b["--brand-blue-tint"])
            print(f"1290 chip text contrast, dark: {r:.2f}:1")
            self.assertGreaterEqual(r, FLOOR)

    def test_the_dark_chip_rules_use_the_strong_text_token_and_light_keeps_brand_blue(self):
        css = (ROOT / "src" / "clark" / "page" / "shell.css").read_text(encoding="utf-8")
        self.assertRegex(css, r"(?m)^\.fchip \{[^}]*color: var\(--brand-blue\);")
        for sel in (r":root\[data-theme=dark\] \.fchip:not\(\.word\)", r":root\[data-theme=auto\] \.fchip:not\(\.word\)"):
            self.assertRegex(css, sel + r" \{ color: var\(--brand-blue-strong\); \}")
        self.assertRegex(css, r"@media \(prefers-color-scheme: dark\) \{ :root\[data-theme=auto\] \.fchip")


if __name__ == "__main__":
    unittest.main()
