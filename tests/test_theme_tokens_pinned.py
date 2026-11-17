"""Row 1260, step 2, mutation survivors: the nine new tokens keep their exact defaults in all three copies of the committed token file.

Run: python3 dev/run_tests.py test_theme_tokens_pinned

The defaults must equal today's look, so each is written out here and compared word for word.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSS = (ROOT / "src" / "clark" / "brand" / "tokens.css").read_text(encoding="utf-8")
DEFAULTS = {
    "--page-bg": "var(--bg)", "--page-grad": "none", "--band-bg": "transparent", "--line-soft": "var(--grey-200)",
    "--gutter-rule": "transparent", "--sec-number-color": "var(--text-muted)", "--sec-number-size": "var(--size-small)",
    "--logo-width": "auto", "--logo-height": "auto",
}


def declared(text):
    return {m.group(1): re.sub(r"\s+", " ", m.group(2)).strip() for m in re.finditer(r"(--[a-z0-9-]+)\s*:\s*([^;]+);", text)}


class ThemeTokenDefaultsPinned(unittest.TestCase):
    def copies(self):
        light = declared(CSS[:CSS.index("/* dark mode")])
        dark = declared(re.search(r":root\[data-theme=dark\]\s*\{(.*?)\n\}", CSS, re.S).group(1))
        auto = declared(re.search(r"@media \(prefers-color-scheme: dark\)\s*\{\s*:root\[data-theme=auto\]\s*\{(.*?)\n  \}\s*\}", CSS, re.S).group(1))
        return {"light": light, "dark": dark, "auto": auto}

    def test_every_default_is_exact_in_light_dark_and_auto(self):
        for mode, got in self.copies().items():
            for name, value in DEFAULTS.items():
                self.assertEqual(got.get(name), value, "%s in %s" % (name, mode))


if __name__ == "__main__":
    unittest.main()
