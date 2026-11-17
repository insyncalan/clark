"""Item 1260, step 2: the nine new Theme tokens are declared, with defaults that equal today's look, in light and in both dark copies."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSS = ROOT / "src" / "clark" / "brand" / "tokens.css"
NEW = ("--page-bg", "--page-grad", "--band-bg", "--line-soft", "--gutter-rule", "--sec-number-color", "--sec-number-size", "--logo-width", "--logo-height")


def declared(text):
    return {m.group(1): re.sub(r"\s+", " ", m.group(2)).strip() for m in re.finditer(r"(--[a-z0-9-]+)\s*:\s*([^;]+);", text)}


class ThemeTokens(unittest.TestCase):
    def setUp(self):
        self.css = CSS.read_text(encoding="utf-8")
        self.light = declared(self.css[:self.css.index("/* dark mode")])
        self.dark = declared(re.search(r":root\[data-theme=dark\]\s*\{(.*?)\n\}", self.css, re.S).group(1))
        self.auto = declared(re.search(r"@media \(prefers-color-scheme: dark\)\s*\{\s*:root\[data-theme=auto\]\s*\{(.*?)\n  \}\s*\}", self.css, re.S).group(1))

    def test_the_nine_names_are_declared_in_light_and_in_both_dark_copies(self):
        for name in NEW:
            self.assertIn(name, self.light, name)
            self.assertIn(name, self.dark, name)
            self.assertIn(name, self.auto, name)

    def test_each_default_reads_as_today_and_is_the_same_in_every_copy(self):
        for name in NEW:
            self.assertEqual(self.light[name], self.dark[name], name)
            self.assertEqual(self.dark[name], self.auto[name], name)
        self.assertEqual(self.light["--page-bg"], "var(--bg)")
        self.assertEqual(self.light["--page-grad"], "none")
        self.assertEqual(self.light["--band-bg"], "transparent")

    def test_nothing_in_the_page_css_uses_them_yet(self):
        used = ""
        for path in (ROOT / "src" / "clark" / "page").rglob("*.css"):
            used += path.read_text(encoding="utf-8")
        for name in NEW:
            self.assertNotIn("var(%s" % name, used, name)


if __name__ == "__main__":
    unittest.main()
