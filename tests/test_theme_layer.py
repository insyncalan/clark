"""Row 1260, step 4a: a Theme is layered by page.page_html(theme=...) between the committed tokens and the brand.

Run: python3 dev/run_tests.py test_theme_layer
"""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _paths import ROOT  # noqa: F401  (puts src on the path)

from clark import page, theme

NAME = "prototype-2.0"


def brand_folder(text):
    d = Path(tempfile.mkdtemp())
    (d / "tokens.css").write_text(text, encoding="utf-8")
    return d


class ThemeReading(unittest.TestCase):
    def test_the_shipped_theme_is_listed(self):
        self.assertIn(NAME, theme.installed())

    def test_css_is_tokens_then_rules_without_comments(self):
        text = theme.css(NAME)
        self.assertIn("--page-grad", text)
        self.assertIn(".secs", text)
        self.assertLess(text.index("--page-grad"), text.index(".secs"))
        self.assertNotIn("/*", text)

    def test_no_name_unknown_name_and_paths_are_not_themes(self):
        for bad in (None, "", "nothing", "../themes/" + NAME, str(theme.THEMES / NAME), 5, NAME + "/"):
            self.assertIsNone(theme.css(bad), bad)

    def test_a_file_over_the_size_limit_is_refused_and_one_just_under_passes(self):
        biggest = max((theme.THEMES / NAME / f).stat().st_size for f in theme.FILES)
        with mock.patch.object(theme, "LIMIT", biggest):
            self.assertIsNotNone(theme.css(NAME))
        with mock.patch.object(theme, "LIMIT", biggest - 1):
            self.assertIsNone(theme.css(NAME))

    def test_the_limit_is_128_kilobytes(self):
        self.assertEqual(theme.LIMIT, 128 * 1024)

    def test_every_shipped_theme_file_is_under_the_limit(self):
        """A file over the limit is not read and the whole Theme drops: the next overrun fails here, not on the page."""
        for name in theme.installed():
            for f in theme.FILES:
                size = (theme.THEMES / name / f).stat().st_size
                self.assertLessEqual(size, theme.LIMIT, f"{name}/{f} is {size} bytes, over the {theme.LIMIT} limit")
            self.assertIsNotNone(theme.css(name), name)

    def test_a_symlinked_theme_file_is_refused(self):
        root = Path(tempfile.mkdtemp())
        real = root / "real.css"
        real.write_text(":root { --a: 1; }", encoding="utf-8")
        folder = root / "themes" / "linked"
        folder.mkdir(parents=True)
        (folder / "rules.css").write_text(".x { color: red; }", encoding="utf-8")
        (folder / "rules-2.css").write_text(".y { color: red; }", encoding="utf-8")
        (folder / "tokens.css").symlink_to(real)
        with mock.patch.object(theme, "THEMES", root / "themes"):
            self.assertIn("linked", theme.installed())
            self.assertIsNone(theme.css("linked"))
            (folder / "tokens.css").unlink()
            (folder / "tokens.css").write_text(":root { --a: 1; }", encoding="utf-8")
            self.assertIsNotNone(theme.css("linked"))

    def test_the_served_text_is_tokens_file_then_the_two_rules_files(self):
        def clean(f):
            return page.strip_css_comments((theme.THEMES / NAME / f).read_text(encoding="utf-8")).strip()
        self.assertEqual(theme.css(NAME), page.escape_style(clean("tokens.css") + "\n" + clean("rules.css") + "\n" + clean("rules-2.css")))
        self.assertEqual(theme.FILES, ("tokens.css", "rules.css", "rules-2.css"))


class ThemeLayering(unittest.TestCase):
    def test_default_is_byte_for_byte_today(self):
        nobrand = page.NO_BRAND
        self.assertEqual(page.page_html(branding=nobrand), page.page_html(branding=nobrand, theme=None))
        self.assertEqual(page.page_html(branding=nobrand), page.page_html(branding=nobrand, theme="nothing"))
        self.assertNotIn('id="theme"', page.page_html(branding=nobrand))

    def test_theme_block_sits_after_the_demo_block_and_before_the_brand(self):
        html = page.page_html(branding=brand_folder(":root { --text: #123456; }"), theme=NAME)
        demo, mid, brand = html.index('id="brand-demo"'), html.index('id="theme"'), html.index('id="brand-local"')
        self.assertLess(demo, mid)
        self.assertLess(mid, brand)
        self.assertEqual(html.count('id="theme"'), 1)

    def test_theme_alone_adds_one_block_and_no_brand_block(self):
        base = page.page_html(branding=page.NO_BRAND)
        html = page.page_html(branding=page.NO_BRAND, theme=NAME)
        self.assertEqual(html.count("<style"), base.count("<style") + 1)
        self.assertNotIn('id="brand-local"', html)

    def test_published_page_takes_the_theme_too(self):
        self.assertIn('id="theme"', page.page_html(branding=page.NO_BRAND, view=True, theme=NAME))

    def test_layer_theme_without_css_changes_nothing(self):
        self.assertEqual(page.layer_theme("<x>", None), "<x>")


if __name__ == "__main__":
    unittest.main()
