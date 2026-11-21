"""Row 1269, acceptance 2: a project's Brand layers over the Theme in the published file and in the page the PDF is printed from.
Fictional data only. Run: python3 dev/run_tests.py test_theme_brand_published_1269
"""
import re
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import _paths  # noqa: F401
from _demo import DemoStore
from clark import page, publish, publish_flow, publish_pdf

BRAND_CSS = ":root { --page-grad: none; --gutter-rule: transparent; }"


def style_ids(html):
    return re.findall(r'<style\b[^>]*?\bid="([^"]*)"', html)


def theme_block(text):
    return re.search(r'<style\b[^>]*\bid="theme"[^>]*>(.*?)</style>', text, re.S).group(1)


class BrandOverTheme(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store
        self.brand = Path(tempfile.mkdtemp(prefix="clark-test-"))
        self.addCleanup(shutil.rmtree, self.brand, True)
        (self.brand / "tokens.css").write_text(BRAND_CSS, encoding="utf-8")

    def file(self, branding):
        return publish.build(self.s, "ABC", now="2030-01-15", branding=branding, number=1)["body"].decode("utf-8")

    def test_the_published_file_has_the_theme_block_once_and_the_brand_block_after_it(self):
        text = self.file(self.brand)
        ids = style_ids(text)
        self.assertEqual(ids.count("theme"), 1)
        self.assertEqual(ids.count("brand-local"), 1)
        self.assertLess(ids.index("brand-demo"), ids.index("theme"))
        self.assertLess(ids.index("theme"), ids.index("brand-local"))
        self.assertIn("--gutter-rule: transparent", text[text.index('id="brand-local"'):])

    def test_a_file_with_no_brand_has_no_brand_block_and_the_same_theme_block(self):
        without = self.file(page.NO_BRAND)
        self.assertNotIn("brand-local", style_ids(without))
        self.assertEqual(theme_block(self.file(self.brand)), theme_block(without))

    def test_the_page_the_pdf_is_printed_from_carries_the_brand_after_the_theme(self):
        built = publish.build(self.s, "ABC", now="2030-01-15", number=1)
        pub = publish_flow.Publisher(self.s.path, [], by_user=lambda: "x", data_dir=self.s.path.parent, branding=self.brand)
        seen = []
        real = page.page_html
        spy = mock.patch.object(page, "page_html", lambda *a, **k: (seen.append(real(*a, **k)), seen[-1])[1])
        with spy, mock.patch.object(publish_pdf.pdf, "find_chrome", return_value=None):
            publish_pdf.Step({}, pub).prepare(pub, None, built, "2030-01-15", self.s, "ABC", None, "saved")
        self.assertTrue(seen, "the page was drawn")
        ids = style_ids(seen[-1])
        self.assertLess(ids.index("theme"), ids.index("brand-local"))


if __name__ == "__main__":
    unittest.main()
